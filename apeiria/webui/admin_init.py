from __future__ import annotations

from apeiria.db.models.ai_knowledge import KnowledgeChunk, KnowledgeDocument
from apeiria.db.models.ai_memory import Fact
from apeiria.db.models.ai_persona import Persona, PersonaBinding
from apeiria.db.models.ai_relationship import AIProfile
from apeiria.db.models.ai_source import (
    AIChatModel,
    AIEmbeddingModel,
    AIRerankModel,
    AISource,
)
from apeiria.db.models.conversation import Message
from apeiria.db.models.conversation import Session as SessionModel
from apeiria.db.models.infrastructure import ACPAgent, MCPServer
from apeiria.webui.admin_registry import register
from apeiria.webui.admin_service import GenericAdminService
from apeiria.webui.schemas.admin import (
    ACPAgentCreate,
    ACPAgentResponse,
    ACPAgentUpdate,
    AIChatModelCreate,
    AIChatModelResponse,
    AIChatModelUpdate,
    AIEmbeddingModelCreate,
    AIEmbeddingModelResponse,
    AIEmbeddingModelUpdate,
    AIProfileCreate,
    AIProfileResponse,
    AIProfileUpdate,
    AIRerankModelCreate,
    AIRerankModelResponse,
    AIRerankModelUpdate,
    AISourceCreate,
    AISourceResponse,
    AISourceUpdate,
    FactResponse,
    KnowledgeChunkResponse,
    KnowledgeDocumentCreate,
    KnowledgeDocumentResponse,
    KnowledgeDocumentUpdate,
    MCPServerCreate,
    MCPServerResponse,
    MCPServerUpdate,
    MessageResponse,
    PersonaBindingCreate,
    PersonaBindingResponse,
    PersonaCreate,
    PersonaResponse,
    PersonaUpdate,
    SessionResponse,
)


def init_admin_resources() -> None:  # noqa: PLR0915
    svc = GenericAdminService()
    svc.model = KnowledgeDocument
    svc.response_cls = KnowledgeDocumentResponse
    svc.pk_field = "id"
    svc.create_cls = KnowledgeDocumentCreate
    svc.update_cls = KnowledgeDocumentUpdate
    register("knowledge-documents", svc)

    svc = GenericAdminService()
    svc.model = KnowledgeChunk
    svc.response_cls = KnowledgeChunkResponse
    svc.pk_field = "id"
    svc.allow_create = False
    svc.allow_update = False
    svc.allow_batch_delete = True
    register("knowledge-chunks", svc)

    svc = GenericAdminService()
    svc.model = Persona
    svc.response_cls = PersonaResponse
    svc.pk_field = "id"
    svc.create_cls = PersonaCreate
    svc.update_cls = PersonaUpdate
    register("personas", svc)

    svc = GenericAdminService()
    svc.model = PersonaBinding
    svc.response_cls = PersonaBindingResponse
    svc.pk_field = "session_id"
    svc.create_cls = PersonaBindingCreate
    svc.allow_update = False
    register("persona-bindings", svc)

    svc = GenericAdminService()
    svc.model = AIProfile
    svc.response_cls = AIProfileResponse
    svc.pk_field = "id"
    svc.create_cls = AIProfileCreate
    svc.update_cls = AIProfileUpdate
    register("profiles", svc)

    svc = GenericAdminService()
    svc.model = Fact
    svc.response_cls = FactResponse
    svc.pk_field = "id"
    svc.allow_create = False
    svc.allow_update = False
    svc.allow_batch_delete = True
    register("memories", svc)

    svc = GenericAdminService()
    svc.model = AISource
    svc.response_cls = AISourceResponse
    svc.pk_field = "source_id"
    svc.create_cls = AISourceCreate
    svc.update_cls = AISourceUpdate
    register("ai-sources", svc)

    svc = GenericAdminService()
    svc.model = AIChatModel
    svc.response_cls = AIChatModelResponse
    svc.pk_field = "model_id"
    svc.create_cls = AIChatModelCreate
    svc.update_cls = AIChatModelUpdate
    register("chat-models", svc)

    svc = GenericAdminService()
    svc.model = AIEmbeddingModel
    svc.response_cls = AIEmbeddingModelResponse
    svc.pk_field = "model_id"
    svc.create_cls = AIEmbeddingModelCreate
    svc.update_cls = AIEmbeddingModelUpdate
    register("embedding-models", svc)

    svc = GenericAdminService()
    svc.model = AIRerankModel
    svc.response_cls = AIRerankModelResponse
    svc.pk_field = "model_id"
    svc.create_cls = AIRerankModelCreate
    svc.update_cls = AIRerankModelUpdate
    register("rerank-models", svc)

    svc = GenericAdminService()
    svc.model = SessionModel
    svc.response_cls = SessionResponse
    svc.pk_field = "id"
    svc.allow_create = False
    svc.allow_update = False
    register("sessions", svc)

    svc = GenericAdminService()
    svc.model = Message
    svc.response_cls = MessageResponse
    svc.pk_field = "id"
    svc.allow_create = False
    svc.allow_update = False
    svc.allow_batch_delete = True
    register("messages", svc)

    svc = GenericAdminService()
    svc.model = ACPAgent
    svc.response_cls = ACPAgentResponse
    svc.pk_field = "id"
    svc.create_cls = ACPAgentCreate
    svc.update_cls = ACPAgentUpdate
    register("acp-agents", svc)

    svc = GenericAdminService()
    svc.model = MCPServer
    svc.response_cls = MCPServerResponse
    svc.pk_field = "id"
    svc.create_cls = MCPServerCreate
    svc.update_cls = MCPServerUpdate
    register("mcp-servers", svc)
