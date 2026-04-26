"""Recent-target browsing over session read models."""

from __future__ import annotations

from apeiria.conversation.identity import build_participant_subject_id

from .models import AIRecentTarget
from .scenes import list_recent_sessions


async def list_recent_targets(
    *,
    limit: int = 20,
) -> list[AIRecentTarget]:
    sessions = await list_recent_sessions(limit=limit)
    targets: list[AIRecentTarget] = []
    seen_users: set[str] = set()
    seen_participants: set[str] = set()

    for item in sessions:
        summary = (item.summary_text or "").strip()
        conversation_title = summary or item.session_id[:12]
        conversation_subtitle = f"{item.platform} · {item.scene_type} · {item.scene_id}"
        targets.append(
            AIRecentTarget(
                target_type="scene",
                anchor_type="scene",
                anchor_id=item.session_id,
                title=conversation_title,
                subtitle=conversation_subtitle,
                scene_id=item.session_id,
                platform=item.platform,
                scope_type=item.scene_type,
                scope_id=item.scene_id,
                user_id=item.subject_id,
                last_active_at=item.last_message_at.isoformat(),
            )
        )

        if item.scene_type == "group":
            participant_user_ids = await _list_recent_user_ids_for_session(
                session_id=item.session_id,
                limit=3,
            )
        else:
            participant_user_ids = [item.subject_id or item.scene_id]

        for user_id in participant_user_ids:
            if not user_id:
                continue
            if item.scene_type == "group":
                participant_id = build_participant_subject_id(
                    scene_type=item.scene_type,
                    scene_id=item.scene_id,
                    user_id=user_id,
                )
                if participant_id not in seen_participants:
                    seen_participants.add(participant_id)
                    targets.append(
                        AIRecentTarget(
                            target_type="participant",
                            anchor_type="participant",
                            anchor_id=participant_id,
                            title=user_id,
                            subtitle=f"{item.platform} · group participant",
                            scene_id=item.session_id,
                            platform=item.platform,
                            scope_type=item.scene_type,
                            scope_id=item.scene_id,
                            user_id=user_id,
                            last_active_at=item.last_message_at.isoformat(),
                        )
                    )
            if user_id in seen_users:
                continue
            seen_users.add(user_id)
            user_subtitle = f"{item.platform} · {item.scene_type}"
            targets.append(
                AIRecentTarget(
                    target_type="user",
                    anchor_type="user",
                    anchor_id=user_id,
                    title=user_id,
                    subtitle=user_subtitle,
                    scene_id=item.session_id,
                    platform=item.platform,
                    scope_type=item.scene_type,
                    scope_id=item.scene_id,
                    user_id=user_id,
                    last_active_at=item.last_message_at.isoformat(),
                )
            )

    return targets[: limit * 2]


async def _list_recent_user_ids_for_session(
    *,
    session_id: str,
    limit: int,
) -> list[str]:
    from apeiria.conversation.service import chat_session_service

    return await chat_session_service.list_recent_user_ids_for_session(
        session_id=session_id,
        limit=limit,
    )
