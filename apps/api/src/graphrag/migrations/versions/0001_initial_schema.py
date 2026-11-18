"""Initial schema: accounts, projects, documents, chunks, the knowledge graph, communities, queries.

Revision ID: 0001
Revises:
Create Date: 2026-10-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

from graphrag.db.types import Embedding

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = pg.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)
# Frozen here rather than imported: a later width is a new migration with its own index.
HNSW_DIMS = (384, 768, 1024, 1536)
JOB_STATUSES = "status IN ('queued', 'processing', 'ready', 'failed')"


def _id() -> sa.Column[object]:
    return sa.Column("id", UUID, nullable=False)


def _created() -> sa.Column[object]:
    return sa.Column("created_at", TS, nullable=False, server_default=sa.func.now())


def _updated() -> sa.Column[object]:
    return sa.Column("updated_at", TS, nullable=False, server_default=sa.func.now())


def _fk(column: str, table: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], [f"{table}.id"], ondelete=ondelete)


def _jsonb(name: str, default: str) -> sa.Column[object]:
    return sa.Column(
        name, pg.JSONB(), nullable=False, server_default=sa.text(f"'{default}'::jsonb")
    )


def _width_in() -> str:
    return f"embedding_dim IN ({', '.join(str(d) for d in HNSW_DIMS)})"


def _hnsw(table: str) -> None:
    """One HNSW index per supported width, each over a cast expression and limited to rows of
    that width. Queries repeat the same cast and width predicate as SQL literals, so the
    planner can match the partial index on every execution."""
    for dim in HNSW_DIMS:
        op.execute(
            f"CREATE INDEX ix_{table}_embedding_hnsw_{dim} ON {table} USING hnsw "
            f"((embedding::vector({dim})) vector_cosine_ops) WITH (m = 16, ef_construction = 64) "
            f"WHERE embedding_dim = {dim}"
        )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "users",
        _id(),
        sa.Column("email", pg.CITEXT(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("session_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("failed_logins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", TS),
        sa.Column("last_login_at", TS),
        _created(),
        _updated(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "projects",
        _id(),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        _jsonb("settings", "{}"),
        sa.Column("graph_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", UUID),
        _created(),
        _updated(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
        _fk("created_by", "users", "SET NULL"),
    )

    op.create_table(
        "memberships",
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        _created(),
        sa.PrimaryKeyConstraint("project_id", "user_id"),
        _fk("project_id", "projects", "CASCADE"),
        _fk("user_id", "users", "CASCADE"),
        sa.CheckConstraint("role IN ('owner', 'editor', 'viewer')", name="role"),
    )
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])

    op.create_table(
        "api_keys",
        _id(),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("created_by", UUID),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("prefix", sa.String(16), nullable=False),
        sa.Column("secret_hash", sa.String(64), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("last_used_at", TS),
        sa.Column("expires_at", TS),
        sa.Column("revoked_at", TS),
        _created(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("prefix"),
        _fk("project_id", "projects", "CASCADE"),
        _fk("created_by", "users", "SET NULL"),
        sa.CheckConstraint("role IN ('editor', 'viewer')", name="role"),
    )
    op.create_index("ix_api_keys_project_id", "api_keys", ["project_id"])

    op.create_table(
        "audit_events",
        _id(),
        sa.Column("project_id", UUID),
        sa.Column("actor_user_id", UUID),
        sa.Column("actor_api_key_id", UUID),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.String(64)),
        _jsonb("details", "{}"),
        _created(),
        sa.PrimaryKeyConstraint("id"),
        _fk("project_id", "projects", "CASCADE"),
        _fk("actor_user_id", "users", "SET NULL"),
        _fk("actor_api_key_id", "api_keys", "SET NULL"),
    )
    op.create_index(
        "ix_audit_events_project_id_created_at", "audit_events", ["project_id", "created_at"]
    )

    op.create_table(
        "documents",
        _id(),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("source_type", sa.String(8), nullable=False),
        sa.Column("source_uri", sa.String(2048)),
        sa.Column("kind", sa.String(8)),
        sa.Column("mime_type", sa.String(160)),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("sha256", sa.String(64)),
        sa.Column("storage_key", sa.String(400)),
        _jsonb("metadata", "{}"),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("stage", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("error", sa.Text()),
        sa.Column("section_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("entity_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("relation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", UUID),
        sa.Column("parsed_at", TS),
        sa.Column("extracted_at", TS),
        _created(),
        _updated(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "external_id"),
        _fk("project_id", "projects", "CASCADE"),
        _fk("created_by", "users", "SET NULL"),
        sa.CheckConstraint(JOB_STATUSES, name="status"),
        sa.CheckConstraint("source_type IN ('file', 'url', 'text')", name="source_type"),
        sa.CheckConstraint(
            "kind IS NULL OR kind IN ('pdf', 'docx', 'md', 'html', 'txt', 'csv')", name="kind"
        ),
    )
    op.create_index("ix_documents_project_id_created_at", "documents", ["project_id", "created_at"])
    # The same bytes uploaded twice to one project are one document; the same URL too.
    op.create_index(
        "uq_documents_project_id_sha256",
        "documents",
        ["project_id", "sha256"],
        unique=True,
        postgresql_where=sa.text("source_type IN ('file', 'text')"),
    )
    op.create_index(
        "uq_documents_project_id_source_uri",
        "documents",
        ["project_id", "source_uri"],
        unique=True,
        postgresql_where=sa.text("source_type = 'url'"),
    )
    # Small partial index for the reaper: only unfinished documents are in it.
    op.create_index(
        "ix_documents_unfinished",
        "documents",
        ["updated_at"],
        postgresql_where=sa.text("status IN ('queued', 'processing')"),
    )

    op.create_table(
        "document_sections",
        _id(),
        sa.Column("document_id", UUID, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("label", sa.String(300), nullable=False),
        _jsonb("blocks", "[]"),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "ordinal"),
        _fk("document_id", "documents", "CASCADE"),
    )

    op.create_table(
        "chunks",
        _id(),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("document_id", UUID, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("section_ordinal", sa.Integer(), nullable=False),
        sa.Column("heading", sa.Text(), nullable=False, server_default=""),
        sa.Column("location", sa.String(300), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", Embedding(), nullable=False),
        sa.Column("embedding_dim", sa.SmallInteger(), nullable=False),
        sa.Column(
            "tsv",
            pg.TSVECTOR(),
            sa.Computed(
                "to_tsvector('english', coalesce(heading, '') || ' ' || text)", persisted=True
            ),
        ),
        sa.PrimaryKeyConstraint("id"),
        _fk("project_id", "projects", "CASCADE"),
        _fk("document_id", "documents", "CASCADE"),
        sa.CheckConstraint(_width_in(), name="embedding_dim"),
        sa.CheckConstraint("vector_dims(embedding) = embedding_dim", name="embedding_width"),
    )
    op.create_index("ix_chunks_document_id_ordinal", "chunks", ["document_id", "ordinal"])
    op.create_index("ix_chunks_project_id", "chunks", ["project_id"])
    op.create_index("ix_chunks_tsv", "chunks", ["tsv"], postgresql_using="gin")
    _hnsw("chunks")

    op.create_table(
        "entities",
        _id(),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("key", sa.String(300), nullable=False),
        sa.Column("type", sa.String(24), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        _jsonb("aliases", "[]"),
        sa.Column("mention_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("degree", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("importance", sa.Float(), nullable=False, server_default="0"),
        sa.Column("embedding", Embedding(), nullable=False),
        sa.Column("embedding_dim", sa.SmallInteger(), nullable=False),
        _created(),
        _updated(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "key"),
        _fk("project_id", "projects", "CASCADE"),
        sa.CheckConstraint(_width_in(), name="embedding_dim"),
        sa.CheckConstraint("vector_dims(embedding) = embedding_dim", name="embedding_width"),
    )
    op.create_index("ix_entities_project_id_type", "entities", ["project_id", "type"])
    op.create_index(
        "ix_entities_project_id_importance", "entities", ["project_id", sa.text("importance DESC")]
    )
    op.execute("CREATE INDEX ix_entities_name_trgm ON entities USING gin (name gin_trgm_ops)")
    _hnsw("entities")

    op.create_table(
        "entity_mentions",
        sa.Column("entity_id", UUID, nullable=False),
        sa.Column("chunk_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("document_id", UUID, nullable=False),
        sa.Column("surface", sa.String(300), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("entity_id", "chunk_id"),
        _fk("entity_id", "entities", "CASCADE"),
        _fk("chunk_id", "chunks", "CASCADE"),
        _fk("project_id", "projects", "CASCADE"),
        _fk("document_id", "documents", "CASCADE"),
    )
    op.create_index("ix_entity_mentions_chunk_id", "entity_mentions", ["chunk_id"])
    op.create_index("ix_entity_mentions_document_id", "entity_mentions", ["document_id"])
    op.create_index("ix_entity_mentions_project_id", "entity_mentions", ["project_id"])

    op.create_table(
        "relations",
        _id(),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("source_id", UUID, nullable=False),
        sa.Column("target_id", UUID, nullable=False),
        sa.Column("predicate", sa.String(48), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1"),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="1"),
        _created(),
        _updated(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "target_id", "predicate"),
        _fk("project_id", "projects", "CASCADE"),
        _fk("source_id", "entities", "CASCADE"),
        _fk("target_id", "entities", "CASCADE"),
        sa.CheckConstraint("source_id <> target_id", name="no_self_loop"),
    )
    op.create_index("ix_relations_project_id", "relations", ["project_id"])
    op.create_index("ix_relations_target_id", "relations", ["target_id"])

    op.create_table(
        "relation_evidence",
        sa.Column("relation_id", UUID, nullable=False),
        sa.Column("chunk_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("quote", sa.Text(), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("relation_id", "chunk_id"),
        _fk("relation_id", "relations", "CASCADE"),
        _fk("chunk_id", "chunks", "CASCADE"),
        _fk("project_id", "projects", "CASCADE"),
    )
    op.create_index("ix_relation_evidence_chunk_id", "relation_evidence", ["chunk_id"])

    op.create_table(
        "graph_builds",
        _id(),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("trigger", sa.String(16), nullable=False),
        _jsonb("params", "{}"),
        _jsonb("stats", "{}"),
        sa.Column("error", sa.Text()),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", UUID),
        sa.Column("started_at", TS),
        sa.Column("finished_at", TS),
        _created(),
        _updated(),
        sa.PrimaryKeyConstraint("id"),
        _fk("project_id", "projects", "CASCADE"),
        _fk("created_by", "users", "SET NULL"),
        sa.CheckConstraint("status IN ('queued', 'running', 'completed', 'failed')", name="status"),
    )
    op.create_index(
        "ix_graph_builds_project_id_created_at", "graph_builds", ["project_id", "created_at"]
    )
    op.create_index(
        "ix_graph_builds_unfinished",
        "graph_builds",
        ["updated_at"],
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )

    op.create_table(
        "communities",
        _id(),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("build_id", UUID, nullable=False),
        sa.Column("parent_id", UUID),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        _jsonb("findings", "[]"),
        sa.Column("entity_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("relation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rank", sa.Float(), nullable=False, server_default="0"),
        sa.Column("reporter", sa.String(32), nullable=False, server_default="local"),
        sa.Column("embedding", Embedding(), nullable=False),
        sa.Column("embedding_dim", sa.SmallInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("build_id", "level", "ordinal"),
        _fk("project_id", "projects", "CASCADE"),
        _fk("build_id", "graph_builds", "CASCADE"),
        _fk("parent_id", "communities", "CASCADE"),
    )
    op.create_index("ix_communities_project_id_level", "communities", ["project_id", "level"])
    op.create_index("ix_communities_parent_id", "communities", ["parent_id"])

    op.create_table(
        "community_members",
        sa.Column("community_id", UUID, nullable=False),
        sa.Column("entity_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.PrimaryKeyConstraint("community_id", "entity_id"),
        _fk("community_id", "communities", "CASCADE"),
        _fk("entity_id", "entities", "CASCADE"),
        _fk("project_id", "projects", "CASCADE"),
    )
    op.create_index("ix_community_members_entity_id", "community_members", ["entity_id"])

    op.create_table(
        "query_logs",
        _id(),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("user_id", UUID),
        sa.Column("api_key_id", UUID),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False, server_default=""),
        sa.Column("answerer", sa.String(32), nullable=False, server_default="local"),
        _jsonb("result", "{}"),
        sa.Column("citation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached", sa.Boolean(), nullable=False, server_default=sa.false()),
        _created(),
        _updated(),
        sa.PrimaryKeyConstraint("id"),
        _fk("project_id", "projects", "CASCADE"),
        _fk("user_id", "users", "SET NULL"),
        _fk("api_key_id", "api_keys", "SET NULL"),
        sa.CheckConstraint("mode IN ('local', 'global', 'hybrid')", name="mode"),
    )
    op.create_index(
        "ix_query_logs_project_id_created_at", "query_logs", ["project_id", "created_at"]
    )


def downgrade() -> None:
    for table in (
        "query_logs",
        "community_members",
        "communities",
        "graph_builds",
        "relation_evidence",
        "relations",
        "entity_mentions",
        "entities",
        "chunks",
        "document_sections",
        "documents",
        "audit_events",
        "api_keys",
        "memberships",
        "projects",
        "users",
    ):
        op.drop_table(table)
