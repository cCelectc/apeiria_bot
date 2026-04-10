"""Phase-3 model facade over provider, profile, and adapter services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.app.ai.model.client import ai_model_client
from apeiria.app.ai.model.factory import build_provider_adapter
from apeiria.app.ai.model.profile_service import ai_model_profile_service
from apeiria.app.ai.model.provider import AIModelGenerateRequest
from apeiria.app.ai.model.provider_service import ai_provider_service

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.model.bindings import AIModelBindingSpec, AIModelBindingTarget
    from apeiria.app.ai.model.models import (
        AIModelProfileDefinition,
        AIModelRouteQuery,
    )
    from apeiria.app.ai.model.provider import (
        AIModelGenerateResponse,
        AIProviderModelItem,
    )
    from apeiria.app.ai.model.providers import AIProviderDefinition
    from apeiria.app.ai.model.selection import AISelectedModel


class AIModelFacade:
    """Unified model boundary used by runtime and admin surfaces."""

    async def list_providers(
        self,
        session: "AsyncSession",
    ) -> list["AIProviderDefinition"]:
        return await ai_provider_service.list_providers(session)

    async def list_profiles(
        self,
        session: "AsyncSession",
    ) -> list["AIModelProfileDefinition"]:
        return await ai_model_profile_service.list_profiles(session)

    async def list_bindings(
        self,
        session: "AsyncSession",
    ) -> list["AIModelBindingSpec"]:
        return await ai_model_profile_service.list_bindings(session)

    async def list_provider_models(
        self,
        session: "AsyncSession",
        *,
        provider_id: str,
        api_key: str,
    ) -> list["AIProviderModelItem"]:
        providers = await ai_provider_service.list_providers(session)
        provider = next(
            (item for item in providers if item.provider_id == provider_id),
            None,
        )
        if provider is None:
            return []
        self._register_provider(provider, api_key=api_key)
        return await ai_model_client.list_models(
            provider_id=provider.provider_id,
            api_key=api_key,
        )

    async def select_model(
        self,
        session: "AsyncSession",
        query: "AIModelRouteQuery | None" = None,
        *,
        target: "AIModelBindingTarget | None" = None,
    ) -> "AISelectedModel | None":
        return await ai_model_profile_service.select_model(
            session,
            query=query,
            target=target,
        )

    async def generate_text(
        self,
        selected: "AISelectedModel",
        *,
        prompt: str,
    ) -> "AIModelGenerateResponse | None":
        api_key = ai_provider_service.get_provider_api_key(selected.provider)
        model_name = self.resolve_model_name(selected)
        if not api_key or not model_name:
            return None

        self._register_provider(selected.provider, api_key=api_key)
        return await ai_model_client.generate_text(
            AIModelGenerateRequest(
                provider_id=selected.provider.provider_id,
                model_name=model_name,
                prompt=prompt,
            )
        )

    @staticmethod
    def resolve_model_name(selected: "AISelectedModel") -> str | None:
        model_name = selected.profile.model_name.strip()
        if model_name:
            return model_name
        default_model = selected.provider.default_model
        if isinstance(default_model, str) and default_model.strip():
            return default_model.strip()
        return None

    @staticmethod
    def _register_provider(
        provider: "AIProviderDefinition",
        *,
        api_key: str,
    ) -> None:
        ai_model_client.registry.register(
            provider.provider_id,
            build_provider_adapter(provider, api_key=api_key),
        )


ai_model_facade = AIModelFacade()
