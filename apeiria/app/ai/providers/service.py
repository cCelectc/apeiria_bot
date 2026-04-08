"""Provider registry service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from sqlalchemy import select

from apeiria.app.ai.providers.models import AIProviderDefinition, AIProviderType
from apeiria.infra.db.models import AIProvider

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class AIProviderCreateInput:
    """Create payload for one provider registry entry."""

    name: str
    provider_type: AIProviderType
    api_base: str | None = None
    api_key_env_name: str | None = None
    enabled: bool = True
    default_model: str | None = None


class AIProviderService:
    """Provider registry CRUD service."""

    async def list_providers(
        self,
        session: AsyncSession,
    ) -> list[AIProviderDefinition]:
        result = await session.execute(
            select(AIProvider).order_by(AIProvider.name.asc(), AIProvider.id.asc())
        )
        return [
            AIProviderDefinition(
                provider_id=row.provider_id,
                name=row.name,
                provider_type=cast("AIProviderType", row.provider_type),
                api_base=row.api_base,
                api_key_env_name=row.api_key_env_name,
                enabled=row.enabled,
                default_model=row.default_model,
            )
            for row in result.scalars().all()
        ]

    async def create_provider(
        self,
        session: AsyncSession,
        create_input: AIProviderCreateInput,
    ) -> AIProvider:
        row = AIProvider(
            provider_id=f"provider_{uuid4().hex}",
            name=create_input.name,
            provider_type=create_input.provider_type,
            api_base=create_input.api_base,
            api_key_env_name=create_input.api_key_env_name,
            enabled=create_input.enabled,
            default_model=create_input.default_model,
        )
        session.add(row)
        await session.flush()
        return row

    @staticmethod
    def get_provider_api_key(provider: AIProviderDefinition) -> str | None:
        if not provider.api_key_env_name:
            return None
        value = os.getenv(provider.api_key_env_name)
        return value.strip() if isinstance(value, str) and value.strip() else None


ai_provider_service = AIProviderService()
