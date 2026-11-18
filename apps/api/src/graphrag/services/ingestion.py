"""Document jobs, run by the worker (SQS) or in the API process (inline queue).

- **parse**: load the original (from storage, or fetch the URL and keep a snapshot), parse it
  into sections, clean and chunk them, embed the chunks and swap them in one transaction,
  then queue the extract job. A document is never half chunked for a reader.
- **extract**: entities and relations from the chunks (services/extraction.py).
- **build**: communities and reports for the project (services/builds.py).

All three are idempotent: a duplicated message for finished work is a no-op, and a retry after
a crash redoes the work from the stored inputs.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import anyio
import numpy as np

from graphrag.core import metrics
from graphrag.core.errors import AppError
from graphrag.core.logging import get_logger
from graphrag.core.text import normalize
from graphrag.ingestion.chunkers import ChunkingOptions, chunk_sections
from graphrag.ingestion.cleaning import CleaningOptions, clean_sections
from graphrag.ingestion.parsers.registry import parse
from graphrag.ingestion.sniff import FILE_EXTENSIONS, MIME_TYPES, kind_for_response
from graphrag.ingestion.types import Block, ParsedSection, ParseError, ParseLimits
from graphrag.integrations.queue import Job
from graphrag.integrations.storage import document_key
from graphrag.models import Document, DocumentSection, Project
from graphrag.models.enums import DocumentKind, JobStatus, SectionKind, SourceType, Stage
from graphrag.repositories.chunks import ChunkRepository
from graphrag.repositories.documents import DocumentRepository
from graphrag.services.builds import MAX_ATTEMPTS, BuildService, Outcome, project_settings
from graphrag.services.container import Container
from graphrag.services.extraction import ExtractionService

log = get_logger("graphrag.ingestion")
EMBED_BATCH = 64
# A claim younger than this belongs to a worker that is still on the job: a second delivery
# of the same message (SQS is at-least-once) is dropped instead of doing the work twice. It
# is shorter than the queue's visibility timeout, so the message of a worker that died is
# redelivered after the claim has aged and is then taken over.
DUPLICATE_WINDOW = timedelta(seconds=120)

__all__ = ["MAX_ATTEMPTS", "IngestionService", "Outcome"]


def _claimed_recently(status: str, stage: str, updated_at: datetime | None) -> bool:
    return (
        status == JobStatus.PROCESSING
        and stage in (Stage.PARSING, Stage.EMBEDDING)
        and updated_at is not None
        and updated_at > datetime.now(UTC) - DUPLICATE_WINDOW
    )


def sections_from_rows(rows: list[DocumentSection]) -> list[ParsedSection]:
    return [
        ParsedSection(
            SectionKind(row.kind),
            row.label,
            [Block(b["text"], b.get("level")) for b in row.blocks],
        )
        for row in rows
    ]


class IngestionService:
    def __init__(self, container: Container) -> None:
        self.c = container
        self.limits = ParseLimits(max_pages=container.settings.max_document_pages)
        self.extraction = ExtractionService(container)

    async def handle(self, job: Job, *, final_attempt: bool = True) -> Outcome:
        if job.kind == "parse" and job.document_id is not None:
            return await self.parse(job.document_id, final_attempt=final_attempt)
        if job.kind == "extract" and job.document_id is not None:
            return await self.extraction.run(job.document_id, final_attempt=final_attempt)
        if job.kind == "build" and job.build_id is not None:
            async with self.c.db.session() as session:
                return await BuildService(self.c, session).execute(
                    job.build_id, final_attempt=final_attempt
                )
        log.warning("job_ignored", kind=job.kind)
        return Outcome.DONE

    # Parsing ----------------------------------------------------------------------------

    async def parse(self, document_id: uuid.UUID, *, final_attempt: bool) -> Outcome:
        async with self.c.db.session() as session:
            document = await DocumentRepository(session).get_for_update(document_id)
            if document is None or document.status == JobStatus.READY:
                return Outcome.DONE
            if _claimed_recently(document.status, document.stage, document.updated_at):
                log.info("duplicate_delivery_dropped", kind="parse", document_id=str(document_id))
                return Outcome.DONE
            project = await session.get(Project, document.project_id)
            if project is None:
                return Outcome.DONE
            document.status = JobStatus.PROCESSING
            document.stage = Stage.PARSING
            document.attempts += 1
            document.error = None
            snapshot = _Snapshot.of(document)
            settings = project_settings(project)
            await session.commit()

        started = time.perf_counter()
        kind = snapshot.kind
        dim = self.c.embedders.spec.dim
        try:
            with anyio.fail_after(self.c.settings.job_timeout_s):
                if snapshot.source_type == SourceType.URL:
                    data, kind, fetched = await self._fetch(snapshot)
                else:
                    if snapshot.storage_key is None or kind is None:
                        raise ParseError("The original of this document is missing.")
                    data, fetched = await self.c.storage.get(snapshot.storage_key), {}
                parsed = await anyio.to_thread.run_sync(parse, kind, data, self.limits)
                rows: list[dict[str, Any]] = [
                    {
                        "ordinal": ordinal,
                        "kind": section.kind.value,
                        "label": section.label[:300],
                        "blocks": [
                            {"text": block.text, "level": block.heading_level}
                            for block in section.blocks
                        ],
                        "text": section.text,
                        "token_count": self.c.tokens.count(section.text),
                    }
                    for ordinal, section in enumerate(parsed.sections)
                ]
                cleaned, _ = await anyio.to_thread.run_sync(
                    clean_sections, parsed.sections, CleaningOptions()
                )
                drafts = await anyio.to_thread.run_sync(
                    chunk_sections,
                    cleaned,
                    self.c.tokens,
                    ChunkingOptions(
                        strategy="recursive",
                        chunk_tokens=settings.chunk_tokens,
                        overlap_tokens=settings.overlap_tokens,
                    ),
                )
                embedder = self.c.embedders.get(str(snapshot.project_id))
                title = snapshot.default_title
                texts = [
                    "\n".join(part for part in (title, d.heading, d.text) if part) for d in drafts
                ]
                batches = [
                    await embedder.embed_documents(texts[i : i + EMBED_BATCH])
                    for i in range(0, len(texts), EMBED_BATCH)
                ]
                vectors = np.concatenate(batches) if batches else np.zeros((0, dim), np.float32)
        except (ParseError, AppError) as exc:
            await self._fail_document(document_id, _message(exc), kind)
            return Outcome.DONE
        except TimeoutError:
            await self._fail_document(document_id, "Parsing took too long and was stopped.", kind)
            return Outcome.DONE
        except Exception:
            log.exception("parse_error", document_id=str(document_id))
            if final_attempt:
                await self._fail_document(document_id, "Parsing failed. Try reprocessing.", kind)
                return Outcome.DONE
            await self._requeue_document(document_id)
            return Outcome.RETRY

        async with self.c.db.session() as session:
            documents = DocumentRepository(session)
            document = await documents.get_for_update(document_id)
            if document is None:
                return Outcome.DONE
            await documents.replace_sections(document.id, rows)
            await ChunkRepository(session).replace_for_document(
                project_id=document.project_id,
                document_id=document.id,
                drafts=drafts,
                embeddings=vectors,
                dim=dim,
            )
            for name, value in fetched.items():
                setattr(document, name, value)
            title = normalize(parsed.title or "")
            if title and 3 <= len(title) <= 200 and _title_is_derived(document, snapshot):
                document.title = title
            document.kind = kind.value if kind else None
            document.section_count = len(rows)
            document.token_count = sum(int(row["token_count"]) for row in rows)
            document.chunk_count = len(drafts)
            document.parsed_at = datetime.now(UTC)
            document.stage = Stage.EXTRACTING
            if not drafts:
                document.status = JobStatus.FAILED
                document.error = "No text was found in this document."
            await session.commit()
        metrics.DOCUMENTS_PARSED.labels(kind.value if kind else "unknown", "ready").inc()
        metrics.CHUNKS_WRITTEN.inc(len(drafts))
        log.info(
            "parsed",
            document_id=str(document_id),
            sections=len(rows),
            chunks=len(drafts),
            seconds=round(time.perf_counter() - started, 2),
        )
        if drafts:
            await self.c.queue.enqueue(Job.extract(snapshot.project_id, document_id))
        return Outcome.DONE

    async def _fetch(self, snapshot: _Snapshot) -> tuple[bytes, DocumentKind, dict[str, Any]]:
        if not snapshot.source_uri:
            raise ParseError("This URL source has no address.")
        page = await self.c.fetcher.fetch(snapshot.source_uri)
        if not page.data:
            raise ParseError("The page was empty.")
        kind = kind_for_response(page.content_type, page.url, page.data[:8192])
        key = document_key(snapshot.project_id, snapshot.id, FILE_EXTENSIONS[kind])
        await self.c.storage.put(key, page.data, MIME_TYPES[kind])
        return (
            page.data,
            kind,
            {
                "storage_key": key,
                "mime_type": MIME_TYPES[kind],
                "size_bytes": len(page.data),
                "sha256": hashlib.sha256(page.data).hexdigest(),
            },
        )

    async def _fail_document(
        self, document_id: uuid.UUID, message: str, kind: DocumentKind | None
    ) -> None:
        metrics.DOCUMENTS_PARSED.labels(kind.value if kind else "unknown", "failed").inc()
        log.info("parse_failed", document_id=str(document_id), reason=message)
        async with self.c.db.session() as session:
            await DocumentRepository(session).mark(
                document_id, status=JobStatus.FAILED, stage=Stage.QUEUED, error=message[:1000]
            )
            await session.commit()

    async def _requeue_document(self, document_id: uuid.UUID) -> None:
        async with self.c.db.session() as session:
            await DocumentRepository(session).mark(
                document_id, status=JobStatus.QUEUED, stage=Stage.QUEUED
            )
            await session.commit()

    # Recovery ---------------------------------------------------------------------------

    async def reap_stale(self) -> int:
        """Recover work stuck unfinished: a lost message or a crashed worker.

        Queued work is re-sent only while the queue is empty; with a backlog its message is
        most likely still waiting. Re-sent rows restart their clock, so each is re-sent at
        most once per window, and rows out of attempts are marked failed. A document stuck
        in extraction starts again from parsing, which is idempotent.
        """
        now = datetime.now(UTC)
        cutoff = now - timedelta(minutes=self.c.settings.stale_job_minutes)
        idle = await self.c.queue.backlog() == 0
        jobs: list[Job] = []
        reaped = 0
        async with self.c.db.session() as session:
            for document in await DocumentRepository(session).unfinished_before(cutoff):
                if document.status == JobStatus.QUEUED and not idle:
                    continue
                reaped += 1
                if document.attempts >= MAX_ATTEMPTS:
                    document.status = JobStatus.FAILED
                    document.error = "Processing did not finish after several attempts."
                else:
                    document.status = JobStatus.QUEUED
                    document.stage = Stage.QUEUED
                    document.updated_at = now
                    jobs.append(Job.parse(document.project_id, document.id))
            await session.commit()
        async with self.c.db.session() as session:
            reaped += await BuildService(self.c, session).reap(cutoff)
        for job in jobs:
            await self.c.queue.enqueue(job)
        if reaped:
            log.info("reaped_stale_work", count=reaped, requeued=len(jobs))
        return reaped


@dataclass(frozen=True, slots=True)
class _Snapshot:
    """What a parse job needs from the document row, read inside the claiming transaction."""

    id: uuid.UUID
    project_id: uuid.UUID
    source_type: str
    source_uri: str | None
    storage_key: str | None
    kind: DocumentKind | None
    default_title: str

    @classmethod
    def of(cls, document: Document) -> _Snapshot:
        return cls(
            id=document.id,
            project_id=document.project_id,
            source_type=document.source_type,
            source_uri=document.source_uri,
            storage_key=document.storage_key,
            kind=DocumentKind(document.kind) if document.kind else None,
            default_title=document.title,
        )


def _title_is_derived(document: Document, snapshot: _Snapshot) -> bool:
    """Whether the title the content declares may replace the document's current one.

    Only a title the system made up is replaced: a file's comes from its name and a URL's from
    the address itself, so the page's own title is better. A title a person typed (a text
    source, or a URL that was given one) stays, and so does one edited while the job ran.
    """
    if document.title != snapshot.default_title:
        return False
    if snapshot.source_type == SourceType.FILE:
        return True
    # Intake stores an untitled URL under the address itself (cut to the column width).
    return (
        snapshot.source_type == SourceType.URL
        and document.title == (snapshot.source_uri or "")[:300]
    )


def _message(exc: Exception) -> str:
    if isinstance(exc, AppError):
        return exc.message
    return str(exc) or "The document could not be parsed."
