from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AdminListResponse(BaseModel):
    items: list
    total: int
    page: int
    size: int
    pages: int


class DeleteBatchRequest(BaseModel):
    ids: list[int | str]


class DeleteBatchResponse(BaseModel):
    deleted: int
    failed: int


# ── KnowledgeDocument ──────────────────────────────────────────


class KnowledgeDocumentCreate(BaseModel):
    title: str
    source_file_name: str


class KnowledgeDocumentUpdate(BaseModel):
    title: str | None = None
    source_file_name: str | None = None
    status: str | None = None


class KnowledgeDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    source_file_name: str
    content_hash: str
    status: str
    chunk_count: int
    last_error: str | None = None
    created_at: str
    updated_at: str


# ── KnowledgeChunk (read-only) ─────────────────────────────────


class KnowledgeChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    content: str
    chunk_index: int
    embedding_model: str | None = None
    embedding_status: str
    created_at: str


# ── Persona ────────────────────────────────────────────────────


class PersonaCreate(BaseModel):
    name: str
    prompt: str
    enabled: bool = True
    is_default: bool = False


class PersonaUpdate(BaseModel):
    name: str | None = None
    prompt: str | None = None
    enabled: bool | None = None
    is_default: bool | None = None


class PersonaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    prompt: str
    enabled: bool
    is_default: bool
    created_at: str
    updated_at: str


# ── PersonaBinding ────────────────────────────────────────────


class PersonaBindingCreate(BaseModel):
    session_id: str
    persona_id: int


class PersonaBindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    persona_id: int
    created_at: str


# ── AIProfile ─────────────────────────────────────────────────


class AIProfileCreate(BaseModel):
    platform: str
    user_id: str
    display_name: str | None = None


class AIProfileUpdate(BaseModel):
    platform: str | None = None
    user_id: str | None = None
    display_name: str | None = None


class AIProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: str
    user_id: str
    display_name: str | None = None
    created_at: str
    updated_at: str


# ── Fact / Memories (read-only) ────────────────────────────────


class FactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    session_id: str
    content: str
    importance: float
    embedding_status: str
    last_reinforced_at: str
    created_at: str


# ── AISource ──────────────────────────────────────────────────


class AISourceCreate(BaseModel):
    source_id: str
    name: str
    adapter: str
    api_base: str | None = None
    api_key_env: str | None = None
    enabled: bool = True
    timeout_seconds: int | None = None


class AISourceUpdate(BaseModel):
    name: str | None = None
    adapter: str | None = None
    api_base: str | None = None
    api_key_env: str | None = None
    enabled: bool | None = None
    timeout_seconds: int | None = None


class AISourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_id: str
    name: str
    adapter: str
    api_base: str | None = None
    enabled: bool
    timeout_seconds: int | None = None
    extra_config_json: str
    created_at: str
    updated_at: str


# ── AIChatModel ───────────────────────────────────────────────


class AIChatModelCreate(BaseModel):
    model_id: str
    source_id: str
    model_identifier: str
    display_name: str
    context_window: int = 128000
    supports_reasoning: bool = False
    enabled: bool = True
    is_default: bool = False


class AIChatModelUpdate(BaseModel):
    source_id: str | None = None
    model_identifier: str | None = None
    display_name: str | None = None
    context_window: int | None = None
    supports_reasoning: bool | None = None
    enabled: bool | None = None
    is_default: bool | None = None


class AIChatModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model_id: str
    source_id: str
    model_identifier: str
    display_name: str
    context_window: int
    supports_reasoning: bool
    enabled: bool
    is_default: bool
    extra_params_json: str
    created_at: str
    updated_at: str


# ── AIEmbeddingModel ──────────────────────────────────────────


class AIEmbeddingModelCreate(BaseModel):
    model_id: str
    source_id: str
    model_identifier: str
    display_name: str
    dimensions: int | None = None
    enabled: bool = True
    is_default: bool = False


class AIEmbeddingModelUpdate(BaseModel):
    source_id: str | None = None
    model_identifier: str | None = None
    display_name: str | None = None
    dimensions: int | None = None
    enabled: bool | None = None
    is_default: bool | None = None


class AIEmbeddingModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model_id: str
    source_id: str
    model_identifier: str
    display_name: str
    dimensions: int | None = None
    enabled: bool
    is_default: bool
    extra_params_json: str
    created_at: str
    updated_at: str


# ── AIRerankModel ─────────────────────────────────────────────


class AIRerankModelCreate(BaseModel):
    model_id: str
    source_id: str
    model_identifier: str
    display_name: str
    enabled: bool = True
    is_default: bool = False


class AIRerankModelUpdate(BaseModel):
    source_id: str | None = None
    model_identifier: str | None = None
    display_name: str | None = None
    enabled: bool | None = None
    is_default: bool | None = None


class AIRerankModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model_id: str
    source_id: str
    model_identifier: str
    display_name: str
    enabled: bool
    is_default: bool
    extra_params_json: str
    created_at: str
    updated_at: str


# ── Session (read-only + delete) ──────────────────────────────


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    platform: str
    scene_type: str
    scene_id: str
    model_override: str | None = None
    created_at: str
    last_active_at: str
    last_compacted_message_id: int | None = None


# ── Message (read-only + delete) ──────────────────────────────


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: str
    role: str
    type: str
    user_id: str | None = None
    content: str
    message_id: str | None = None
    meta_json: str | None = None
    created_at: int


# ── ACPAgent ──────────────────────────────────────────────────


class ACPAgentCreate(BaseModel):
    name: str
    command: str
    args_json: str | None = None
    env_json: str | None = None
    workspace: str | None = None
    enabled: bool = True


class ACPAgentUpdate(BaseModel):
    name: str | None = None
    command: str | None = None
    args_json: str | None = None
    env_json: str | None = None
    workspace: str | None = None
    enabled: bool | None = None


class ACPAgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    command: str
    args_json: str | None = None
    env_json: str | None = None
    workspace: str | None = None
    enabled: bool
    created_at: str
    updated_at: str


# ── MCPServer ─────────────────────────────────────────────────


class MCPServerCreate(BaseModel):
    name: str
    transport: str
    command: str | None = None
    args_json: str | None = None
    env_json: str | None = None
    url: str | None = None
    headers_json: str | None = None
    enabled: bool = True


class MCPServerUpdate(BaseModel):
    name: str | None = None
    transport: str | None = None
    command: str | None = None
    args_json: str | None = None
    env_json: str | None = None
    url: str | None = None
    headers_json: str | None = None
    enabled: bool | None = None


class MCPServerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    transport: str
    command: str | None = None
    args_json: str | None = None
    env_json: str | None = None
    url: str | None = None
    headers_json: str | None = None
    enabled: bool
    created_at: str
    updated_at: str
