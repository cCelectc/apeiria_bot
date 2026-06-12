"""SQLAlchemy ORM model definitions for all Apeiria database tables."""

from apeiria.db.models.ai_knowledge import AIKnowledgeChunk, AIKnowledgeDocument
from apeiria.db.models.ai_memory import AIMemoryItem
from apeiria.db.models.ai_persona import AIPersona, AIPersonaBinding
from apeiria.db.models.ai_relationship import (
    AIAffinity,
    AIProfile,
    AIRelationshipEvent,
)
from apeiria.db.models.ai_routing import (
    AIModelBinding,
    AIModelProfile,
    AIModelRoute,
    AIModelRouteBinding,
    AIModelRouteMember,
)
from apeiria.db.models.ai_session import AIManagedSession
from apeiria.db.models.ai_settings import AIRuntimeSettings
from apeiria.db.models.ai_source import (
    AIChatModel,
    AIEmbeddingModel,
    AIRerankModel,
    AISource,
    AISTTModel,
    AITTSModel,
)
from apeiria.db.models.ai_tasks import AIDeliveryAttempt, AIFutureTask
from apeiria.db.models.ai_tools import AIToolPolicy
from apeiria.db.models.ai_usage import AIModelUsageEvent, AIModelUsageHourly
from apeiria.db.models.auth import WebUIAccount, WebUIAuthSecret
from apeiria.db.models.conversation import (
    ChatMessage,
    ChatSession,
    ChatSessionContextSummary,
)
from apeiria.db.models.governance import (
    AccessRule,
    GroupDisabledPlugin,
    GroupState,
    PluginState,
)
from apeiria.db.models.meta import ApeiriaSchemaMetaModel

__all__ = [
    "AIAffinity",
    "AIChatModel",
    "AIDeliveryAttempt",
    "AIEmbeddingModel",
    "AIFutureTask",
    "AIKnowledgeChunk",
    "AIKnowledgeDocument",
    "AIManagedSession",
    "AIMemoryItem",
    "AIModelBinding",
    "AIModelProfile",
    "AIModelRoute",
    "AIModelRouteBinding",
    "AIModelRouteMember",
    "AIModelUsageEvent",
    "AIModelUsageHourly",
    "AIPersona",
    "AIPersonaBinding",
    "AIProfile",
    "AIRelationshipEvent",
    "AIRerankModel",
    "AIRuntimeSettings",
    "AISTTModel",
    "AISource",
    "AITTSModel",
    "AIToolPolicy",
    "AccessRule",
    "ApeiriaSchemaMetaModel",
    "ChatMessage",
    "ChatSession",
    "ChatSessionContextSummary",
    "GroupDisabledPlugin",
    "GroupState",
    "PluginState",
    "WebUIAccount",
    "WebUIAuthSecret",
]
