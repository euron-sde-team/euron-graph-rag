"""Value sets stored as text with CHECK constraints (cheaper to evolve than Postgres enums)."""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"

    @property
    def rank(self) -> int:
        return {Role.VIEWER: 1, Role.EDITOR: 2, Role.OWNER: 3}[self]

    def allows(self, required: Role) -> bool:
        return self.rank >= required.rank


class SourceType(StrEnum):
    FILE = "file"
    URL = "url"
    TEXT = "text"


class DocumentKind(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    MD = "md"
    HTML = "html"
    TXT = "txt"
    CSV = "csv"


class SectionKind(StrEnum):
    PAGE = "page"
    SECTION = "section"
    TABLE = "table"


class JobStatus(StrEnum):
    """The state of a document in the pipeline."""

    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


UNFINISHED = (JobStatus.QUEUED, JobStatus.PROCESSING)


class Stage(StrEnum):
    """Where an unfinished document is in the pipeline, shown in the ingestion view."""

    QUEUED = "queued"
    PARSING = "parsing"
    EMBEDDING = "embedding"
    EXTRACTING = "extracting"
    DONE = "done"


class BuildStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SearchMode(StrEnum):
    LOCAL = "local"
    GLOBAL = "global"
    HYBRID = "hybrid"


class EntityType(StrEnum):
    """The default entity vocabulary. Projects may narrow it; other types fall to OTHER."""

    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    LOCATION = "LOCATION"
    PRODUCT = "PRODUCT"
    TECHNOLOGY = "TECHNOLOGY"
    EVENT = "EVENT"
    CONCEPT = "CONCEPT"
    OTHER = "OTHER"
