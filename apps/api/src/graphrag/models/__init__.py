"""Every model, imported here so `Base.metadata` is complete for Alembic and the tests."""

from graphrag.models.api_key import ApiKey
from graphrag.models.audit import AuditEvent
from graphrag.models.chunk import Chunk
from graphrag.models.community import Community, CommunityMember, GraphBuild
from graphrag.models.document import Document, DocumentSection
from graphrag.models.graph import Entity, EntityMention, Relation, RelationEvidence
from graphrag.models.project import Membership, Project
from graphrag.models.query_log import QueryLog
from graphrag.models.user import User

__all__ = [
    "ApiKey",
    "AuditEvent",
    "Chunk",
    "Community",
    "CommunityMember",
    "Document",
    "DocumentSection",
    "Entity",
    "EntityMention",
    "GraphBuild",
    "Membership",
    "Project",
    "QueryLog",
    "Relation",
    "RelationEvidence",
    "User",
]
