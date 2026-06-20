from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from apeiria.db.engine import get_session
from apeiria.db.models.ai_source import (
    AIChatModel,
    AIEmbeddingModel,
    AIRerankModel,
    AISource,
)
from apeiria.webui.auth import require_auth

router = APIRouter()


# --- Source ---


class SourceResponse(BaseModel):
    source_id: str
    name: str
    adapter: str
    api_base: str | None
    api_key_env: str | None
    enabled: bool
    timeout_seconds: int | None
    extra_config_json: str
    created_at: str
    updated_at: str


class SourceCreate(BaseModel):
    source_id: str
    name: str
    adapter: str
    api_base: str | None = None
    api_key_env: str | None = None
    enabled: bool = True
    timeout_seconds: int | None = None
    extra_config_json: str = "{}"


class SourceUpdate(BaseModel):
    name: str | None = None
    api_base: str | None = None
    api_key_env: str | None = None
    enabled: bool | None = None
    timeout_seconds: int | None = None
    extra_config_json: str | None = None


def _source_to_response(s: AISource) -> SourceResponse:
    return SourceResponse(
        source_id=s.source_id,
        name=s.name,
        adapter=s.adapter,
        api_base=s.api_base,
        api_key_env=s.api_key_env,
        enabled=bool(s.enabled),
        timeout_seconds=s.timeout_seconds,
        extra_config_json=s.extra_config_json,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


@router.get("/sources", response_model=list[SourceResponse])
async def list_sources(
    _: Annotated[Any, Depends(require_auth)],
) -> list[SourceResponse]:
    async with get_session() as db:
        result = await db.execute(
            select(AISource).order_by(AISource.source_id),
        )
        return [_source_to_response(r) for r in result.scalars()]


@router.post("/sources", response_model=SourceResponse, status_code=201)
async def create_source(
    body: SourceCreate,
    _: Annotated[Any, Depends(require_auth)],
) -> SourceResponse:
    async with get_session() as db:
        s = AISource(
            source_id=body.source_id,
            name=body.name,
            adapter=body.adapter,
            api_base=body.api_base,
            api_key_env=body.api_key_env,
            enabled=int(body.enabled),
            timeout_seconds=body.timeout_seconds,
            extra_config_json=body.extra_config_json,
        )
        db.add(s)
        await db.commit()
        await db.refresh(s)
        return _source_to_response(s)


@router.patch("/sources/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: str,
    body: SourceUpdate,
    _: Annotated[Any, Depends(require_auth)],
) -> SourceResponse:
    async with get_session() as db:
        s = await db.get(AISource, source_id)
        if not s:
            raise HTTPException(404, "Source not found")
        for key, val in body.model_dump(exclude_unset=True).items():
            if val is None:
                continue
            if key == "enabled":
                val = int(val)  # noqa: PLW2901
            setattr(s, key, val)
        await db.commit()
        await db.refresh(s)
        return _source_to_response(s)


@router.delete("/sources/{source_id}", status_code=204)
async def delete_source(
    source_id: str,
    _: Annotated[Any, Depends(require_auth)],
) -> None:
    async with get_session() as db:
        s = await db.get(AISource, source_id)
        if not s:
            raise HTTPException(404, "Source not found")
        await db.delete(s)
        await db.commit()


# --- Chat Model ---


class ChatModelResponse(BaseModel):
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


class ChatModelCreate(BaseModel):
    model_id: str
    source_id: str
    model_identifier: str
    display_name: str
    context_window: int = 128000
    supports_reasoning: bool = False
    enabled: bool = True
    is_default: bool = False
    extra_params_json: str = "{}"


class ChatModelUpdate(BaseModel):
    display_name: str | None = None
    context_window: int | None = None
    supports_reasoning: bool | None = None
    enabled: bool | None = None
    is_default: bool | None = None
    extra_params_json: str | None = None


def _chat_to_response(m: AIChatModel) -> ChatModelResponse:
    return ChatModelResponse(
        model_id=m.model_id,
        source_id=m.source_id,
        model_identifier=m.model_identifier,
        display_name=m.display_name,
        context_window=m.context_window,
        supports_reasoning=bool(m.supports_reasoning),
        enabled=bool(m.enabled),
        is_default=bool(m.is_default),
        extra_params_json=m.extra_params_json,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


@router.get("/chat", response_model=list[ChatModelResponse])
async def list_chat_models(
    _: Annotated[Any, Depends(require_auth)],
) -> list[ChatModelResponse]:
    async with get_session() as db:
        result = await db.execute(
            select(AIChatModel).order_by(AIChatModel.model_id),
        )
        return [_chat_to_response(r) for r in result.scalars()]


@router.post("/chat", response_model=ChatModelResponse, status_code=201)
async def create_chat_model(
    body: ChatModelCreate,
    _: Annotated[Any, Depends(require_auth)],
) -> ChatModelResponse:
    async with get_session() as db:
        m = AIChatModel(
            model_id=body.model_id,
            source_id=body.source_id,
            model_identifier=body.model_identifier,
            display_name=body.display_name,
            context_window=body.context_window,
            supports_reasoning=int(body.supports_reasoning),
            enabled=int(body.enabled),
            is_default=int(body.is_default),
            extra_params_json=body.extra_params_json,
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)
        return _chat_to_response(m)


@router.patch("/chat/{model_id}", response_model=ChatModelResponse)
async def update_chat_model(
    model_id: str,
    body: ChatModelUpdate,
    _: Annotated[Any, Depends(require_auth)],
) -> ChatModelResponse:
    async with get_session() as db:
        m = await db.get(AIChatModel, model_id)
        if not m:
            raise HTTPException(404, "Chat model not found")
        bool_keys = {"enabled", "is_default", "supports_reasoning"}
        for key, val in body.model_dump(exclude_unset=True).items():
            if val is None:
                continue
            if key in bool_keys:
                val = int(val)  # noqa: PLW2901
            setattr(m, key, val)
        await db.commit()
        await db.refresh(m)
        return _chat_to_response(m)


@router.delete("/chat/{model_id}", status_code=204)
async def delete_chat_model(
    model_id: str,
    _: Annotated[Any, Depends(require_auth)],
) -> None:
    async with get_session() as db:
        m = await db.get(AIChatModel, model_id)
        if not m:
            raise HTTPException(404, "Chat model not found")
        await db.delete(m)
        await db.commit()


# --- Embedding Model ---


class EmbeddingModelResponse(BaseModel):
    model_id: str
    source_id: str
    model_identifier: str
    display_name: str
    dimensions: int | None
    enabled: bool
    is_default: bool
    extra_params_json: str


class EmbeddingModelCreate(BaseModel):
    model_id: str
    source_id: str
    model_identifier: str
    display_name: str
    dimensions: int | None = None
    enabled: bool = True
    is_default: bool = False
    extra_params_json: str = "{}"


def _emb_to_response(m: AIEmbeddingModel) -> EmbeddingModelResponse:
    return EmbeddingModelResponse(
        model_id=m.model_id,
        source_id=m.source_id,
        model_identifier=m.model_identifier,
        display_name=m.display_name,
        dimensions=m.dimensions,
        enabled=bool(m.enabled),
        is_default=bool(m.is_default),
        extra_params_json=m.extra_params_json,
    )


@router.get("/embedding", response_model=list[EmbeddingModelResponse])
async def list_embedding_models(
    _: Annotated[Any, Depends(require_auth)],
) -> list[EmbeddingModelResponse]:
    async with get_session() as db:
        result = await db.execute(
            select(AIEmbeddingModel).order_by(
                AIEmbeddingModel.model_id,
            ),
        )
        return [_emb_to_response(r) for r in result.scalars()]


@router.post(
    "/embedding",
    response_model=EmbeddingModelResponse,
    status_code=201,
)
async def create_embedding_model(
    body: EmbeddingModelCreate,
    _: Annotated[Any, Depends(require_auth)],
) -> EmbeddingModelResponse:
    async with get_session() as db:
        m = AIEmbeddingModel(
            model_id=body.model_id,
            source_id=body.source_id,
            model_identifier=body.model_identifier,
            display_name=body.display_name,
            dimensions=body.dimensions,
            enabled=int(body.enabled),
            is_default=int(body.is_default),
            extra_params_json=body.extra_params_json,
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)
        return _emb_to_response(m)


@router.delete("/embedding/{model_id}", status_code=204)
async def delete_embedding_model(
    model_id: str,
    _: Annotated[Any, Depends(require_auth)],
) -> None:
    async with get_session() as db:
        m = await db.get(AIEmbeddingModel, model_id)
        if not m:
            raise HTTPException(404, "Embedding model not found")
        await db.delete(m)
        await db.commit()


# --- Rerank Model ---


class RerankModelResponse(BaseModel):
    model_id: str
    source_id: str
    model_identifier: str
    display_name: str
    enabled: bool
    is_default: bool
    extra_params_json: str


class RerankModelCreate(BaseModel):
    model_id: str
    source_id: str
    model_identifier: str
    display_name: str
    enabled: bool = True
    is_default: bool = False
    extra_params_json: str = "{}"


def _rerank_to_response(m: AIRerankModel) -> RerankModelResponse:
    return RerankModelResponse(
        model_id=m.model_id,
        source_id=m.source_id,
        model_identifier=m.model_identifier,
        display_name=m.display_name,
        enabled=bool(m.enabled),
        is_default=bool(m.is_default),
        extra_params_json=m.extra_params_json,
    )


@router.get("/rerank", response_model=list[RerankModelResponse])
async def list_rerank_models(
    _: Annotated[Any, Depends(require_auth)],
) -> list[RerankModelResponse]:
    async with get_session() as db:
        result = await db.execute(
            select(AIRerankModel).order_by(AIRerankModel.model_id),
        )
        return [_rerank_to_response(r) for r in result.scalars()]


@router.post(
    "/rerank",
    response_model=RerankModelResponse,
    status_code=201,
)
async def create_rerank_model(
    body: RerankModelCreate,
    _: Annotated[Any, Depends(require_auth)],
) -> RerankModelResponse:
    async with get_session() as db:
        m = AIRerankModel(
            model_id=body.model_id,
            source_id=body.source_id,
            model_identifier=body.model_identifier,
            display_name=body.display_name,
            enabled=int(body.enabled),
            is_default=int(body.is_default),
            extra_params_json=body.extra_params_json,
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)
        return _rerank_to_response(m)


@router.delete("/rerank/{model_id}", status_code=204)
async def delete_rerank_model(
    model_id: str,
    _: Annotated[Any, Depends(require_auth)],
) -> None:
    async with get_session() as db:
        m = await db.get(AIRerankModel, model_id)
        if not m:
            raise HTTPException(404, "Rerank model not found")
        await db.delete(m)
        await db.commit()
