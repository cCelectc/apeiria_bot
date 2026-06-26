from __future__ import annotations

import time

from nonebot import on_command
from nonebot.adapters import Bot, Event  # noqa: TC002
from nonebot.permission import SUPERUSER

_start_time = time.monotonic()
_llm_call_count = 0
_llm_call_date: str | None = None


def increment_llm_counter() -> None:
    global _llm_call_count, _llm_call_date  # noqa: PLW0603
    from datetime import datetime, timezone

    today = str(datetime.now(timezone.utc).date())
    if _llm_call_date != today:
        _llm_call_count = 0
        _llm_call_date = today
    _llm_call_count += 1


def _session_id_from_event(bot: Bot, event: Event) -> str:
    from apeiria.bot.platform import build_session_id

    return build_session_id(bot, event)


_persona_cmd = on_command("persona", permission=SUPERUSER, priority=5, block=True)


@_persona_cmd.handle()
async def handle_persona(bot: Bot, event: Event) -> None:
    from sqlalchemy import select

    from apeiria.db.engine import get_session
    from apeiria.db.models.ai_persona import Persona, PersonaBinding

    args = str(event.message).strip().split(maxsplit=1)
    cmd_arg = args[1] if len(args) > 1 else ""
    session_id = _session_id_from_event(bot, event)

    if cmd_arg == "clear":
        async with get_session() as db:
            binding = (
                await db.execute(
                    select(PersonaBinding).where(
                        PersonaBinding.session_id == session_id
                    )
                )
            ).scalar_one_or_none()
            if binding:
                await db.delete(binding)
                await db.commit()
        await bot.send(event, "已清除人设绑定，将使用默认人设")
        return

    if cmd_arg:
        async with get_session() as db:
            stmt = select(Persona).where(Persona.enabled == 1)
            if cmd_arg.isdigit():
                stmt = stmt.where(Persona.id == int(cmd_arg))
            else:
                stmt = stmt.where(Persona.name == cmd_arg)
            persona = (await db.execute(stmt)).scalar_one_or_none()
            if not persona:
                await bot.send(event, f"未找到人设: {cmd_arg}")
                return
            existing = (
                await db.execute(
                    select(PersonaBinding).where(
                        PersonaBinding.session_id == session_id
                    )
                )
            ).scalar_one_or_none()
            if existing:
                existing.persona_id = persona.id
            else:
                db.add(PersonaBinding(session_id=session_id, persona_id=persona.id))
            await db.commit()
        await bot.send(event, f"已切换人设: {persona.name}")
        return

    async with get_session() as db:
        personas = list(
            (await db.execute(select(Persona).where(Persona.enabled == 1)))
            .scalars()
            .all()
        )
    if not personas:
        await bot.send(event, "暂无可用人设")
        return
    lines = []
    for p in personas:
        default_mark = " [默认]" if p.is_default else ""
        lines.append(f"  {p.id}. {p.name}{default_mark}")
    await bot.send(event, "可用人设:\n" + "\n".join(lines))


_model_cmd = on_command("model", permission=SUPERUSER, priority=5, block=True)


@_model_cmd.handle()
async def handle_model(bot: Bot, event: Event) -> None:
    from sqlalchemy import select

    from apeiria.db.engine import get_session
    from apeiria.db.models.ai_source import AIChatModel

    args = str(event.message).strip().split(maxsplit=1)
    cmd_arg = args[1] if len(args) > 1 else ""
    session_id = _session_id_from_event(bot, event)

    if cmd_arg:
        async with get_session() as db:
            model = (
                await db.execute(
                    select(AIChatModel).where(
                        AIChatModel.model_id == cmd_arg,
                        AIChatModel.enabled == 1,
                    )
                )
            ).scalar_one_or_none()
            if not model:
                await bot.send(event, f"未找到模型: {cmd_arg}")
                return
        from apeiria.conversation.service import update_session_model_override

        await update_session_model_override(session_id, cmd_arg)
        await bot.send(event, f"已切换模型: {model.display_name}")
        return

    async with get_session() as db:
        models = list(
            (await db.execute(select(AIChatModel).where(AIChatModel.enabled == 1)))
            .scalars()
            .all()
        )
    if not models:
        await bot.send(event, "暂无可用模型")
        return
    lines = [f"  {m.model_id} ({m.display_name})" for m in models]
    await bot.send(event, "可用模型:\n" + "\n".join(lines))


_ai_cmd = on_command("ai", permission=SUPERUSER, priority=5, block=True)


@_ai_cmd.handle()
async def handle_ai(bot: Bot, event: Event) -> None:
    from sqlalchemy import select

    from apeiria.ai.persona.resolver import resolve
    from apeiria.db.engine import get_session
    from apeiria.db.models.ai_settings import AIRuntimeSettings

    session_id = _session_id_from_event(bot, event)

    async with get_session() as db:
        settings = (
            await db.execute(select(AIRuntimeSettings).where(AIRuntimeSettings.id == 1))
        ).scalar_one_or_none()

    persona = await resolve(session_id)
    persona_name = persona.name if persona else "无"
    model = settings.default_chat_model or "未设置" if settings else "未设置"
    talk = settings.talk_value if settings else 0

    uptime = int(time.monotonic() - _start_time)
    hours, remainder = divmod(uptime, 3600)
    minutes, seconds = divmod(remainder, 60)

    await bot.send(
        event,
        f"AI 状态:\n"
        f"  人设: {persona_name}\n"
        f"  模型: {model}\n"
        f"  talk_value: {talk}\n"
        f"  运行时间: {hours}h{minutes}m{seconds}s\n"
        f"  今日LLM调用: {_llm_call_count}",
    )


_rel_cmd = on_command("rel", permission=SUPERUSER, priority=5, block=True)


@_rel_cmd.handle()
async def handle_rel(bot: Bot, event: Event) -> None:
    from sqlalchemy import select

    from apeiria.ai.relationship.service import project_emotion
    from apeiria.bot.platform import resolve_session
    from apeiria.db.engine import get_session
    from apeiria.db.models.ai_relationship import RelationshipScore

    _, scene_type, _ = resolve_session(bot, event)
    if scene_type != "group":
        await bot.send(event, "请在群聊中使用 /rel")
        return

    session_id = _session_id_from_event(bot, event)
    async with get_session() as db:
        scores = list(
            (
                await db.execute(
                    select(RelationshipScore)
                    .where(RelationshipScore.session_id == session_id)
                    .order_by(RelationshipScore.score.desc())
                )
            )
            .scalars()
            .all()
        )

    if not scores:
        await bot.send(event, "暂无关系数据")
        return

    lines = []
    for s in scores:
        emotion = project_emotion(s.score)
        lines.append(f"  {s.user_id}: {s.score:.0f}/100 ({emotion})")
    await bot.send(event, "群聊关系:\n" + "\n".join(lines))
