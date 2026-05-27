"""Principal builders for governance-facing identity objects."""

from __future__ import annotations

from apeiria.access.principal import Principal, PrincipalRole

_FULL_ACCESS_ROLE = PrincipalRole(
    role_id="webui_local_account",
    capabilities=("control_panel", "account_manage"),
)


class PrincipalService:
    """Build and resolve governance principal objects."""

    def build_webui_account_principal(
        self,
        *,
        user_id: str,
        username: str,
    ) -> Principal:
        return Principal(
            principal_kind="webui_account",
            principal_id=user_id,
            display_name=username,
            role=_FULL_ACCESS_ROLE,
            metadata={"username": username},
        )

    def build_system_actor(self, actor_name: str = "system") -> Principal:
        """Reserved for Phase 3 runtime ingress.

        Not yet wired to any caller; kept so that non-WebUI audit/ingress
        paths can resolve a stable governance principal without inventing
        a second Principal factory.
        """
        return Principal(
            principal_kind="system_actor",
            principal_id=f"system:{actor_name}",
            display_name=actor_name,
            role=_FULL_ACCESS_ROLE,
        )

    def build_host_operator(self, actor_name: str = "host") -> Principal:
        """Reserved for Phase 3 runtime ingress.

        Intended caller: host-side recovery / CLI that needs to present a
        governance principal but cannot use the WebUI account path.
        """
        return Principal(
            principal_kind="host_operator",
            principal_id=f"host:{actor_name}",
            display_name=actor_name,
            role=_FULL_ACCESS_ROLE,
        )

    def build_bot_subject(
        self,
        *,
        subject_id: str,
        display_name: str,
    ) -> Principal:
        """Reserved for Phase 3 runtime ingress.

        Intended caller: message ingress normalization, where the incoming
        bot identity needs to become a governance principal for audit /
        permission attribution.
        """
        return Principal(
            principal_kind="bot_subject",
            principal_id=subject_id,
            display_name=display_name,
            role=_FULL_ACCESS_ROLE,
        )


principal_service = PrincipalService()
