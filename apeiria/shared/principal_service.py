"""Principal builders for governance-facing identity objects."""

from __future__ import annotations

from apeiria.shared.principal import Principal
from apeiria.shared.principal_roles import ROLE_OWNER, role_for


class PrincipalService:
    """Build and resolve governance principal objects."""

    def build_webui_account_principal(
        self,
        *,
        user_id: str,
        username: str,
        role: object,
    ) -> Principal:
        resolved_role = role_for(role, fallback=ROLE_OWNER)
        if resolved_role is None:
            msg = "unsupported_role"
            raise ValueError(msg)
        return Principal(
            principal_kind="webui_account",
            principal_id=user_id,
            display_name=username,
            role=resolved_role,
            metadata={"username": username},
        )

    def build_system_actor(self, actor_name: str = "system") -> Principal:
        resolved_role = role_for(ROLE_OWNER, fallback=ROLE_OWNER)
        assert resolved_role is not None
        return Principal(
            principal_kind="system_actor",
            principal_id=f"system:{actor_name}",
            display_name=actor_name,
            role=resolved_role,
        )

    def build_host_operator(self, actor_name: str = "host") -> Principal:
        resolved_role = role_for(ROLE_OWNER, fallback=ROLE_OWNER)
        assert resolved_role is not None
        return Principal(
            principal_kind="host_operator",
            principal_id=f"host:{actor_name}",
            display_name=actor_name,
            role=resolved_role,
        )

    def build_bot_subject(
        self,
        *,
        subject_id: str,
        display_name: str,
        role: object = ROLE_OWNER,
    ) -> Principal:
        resolved_role = role_for(role, fallback=ROLE_OWNER)
        assert resolved_role is not None
        return Principal(
            principal_kind="bot_subject",
            principal_id=subject_id,
            display_name=display_name,
            role=resolved_role,
        )


principal_service = PrincipalService()
