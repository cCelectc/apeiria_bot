from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from nonebot.log import logger

from apeiria.ai.agent.context import assemble_prompt, collect_fragments
from apeiria.ai.agent.events import AgentEvent, EventBus
from apeiria.ai.model.exceptions import AIModelContextLengthError
from apeiria.ai.types import (
    StreamEventType,
    ToolResult,
    TurnResult,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from apeiria.ai.types import (
        Message,
        PromptFragment,
        SessionContext,
        TokenUsage,
        Tool,
        ToolCall,
    )

_MAX_TOOL_ROUNDS = 30
_STREAM_TIMEOUT = 120
_COMPACTION_DEFAULT_THRESHOLD = 0.8


class Agent:
    def __init__(  # noqa: PLR0913
        self,
        session_id: str,
        *,
        stream_fn: Callable[..., AsyncIterator[Any]],
        tools: list[Tool] | None = None,
        handlers: (
            list[
                Callable[
                    [SessionContext],
                    Awaitable[PromptFragment | None],
                ]
            ]
            | None
        ) = None,
        context_window: int = 128000,
        compaction_threshold: float = _COMPACTION_DEFAULT_THRESHOLD,
        self_review_enabled: bool = False,
        compaction_fn: (Callable[..., Awaitable[None]] | None) = None,
    ) -> None:
        self.session_id = session_id
        self.is_streaming = False
        self._stream_fn = stream_fn
        self._tools = {t.name: t for t in (tools or [])}
        self._handlers = handlers or []
        self._context_window = context_window
        self._compaction_threshold = compaction_threshold
        self._self_review_enabled = self_review_enabled
        self._compaction_fn = compaction_fn
        self._last_prompt_tokens: int | None = None
        self._events = EventBus()
        self._tool_ctx: dict[str, Any] | None = None

    @property
    def event_bus(self) -> EventBus:
        return self._events

    async def run(
        self,
        messages: list[Message],
        ctx: SessionContext | None = None,
    ) -> TurnResult:
        await self._events.emit(AgentEvent(type="turn:start"))
        self.is_streaming = True
        try:
            result = await self._execute_turn(messages, ctx)
        except Exception as e:  # noqa: BLE001
            logger.exception("Agent turn failed")
            result = TurnResult(has_reply=False, error=str(e))
            await self._events.emit(AgentEvent(type="error", data={"error": str(e)}))
        finally:
            self.is_streaming = False
        await self._events.emit(
            AgentEvent(
                type="turn:end",
                data={
                    "has_reply": result.has_reply,
                    "reply_text": result.reply_text,
                },
            )
        )
        return result

    async def _execute_turn(
        self,
        messages: list[Message],
        ctx: SessionContext | None,
    ) -> TurnResult:
        await self._maybe_compact(messages)

        if ctx:
            self._tool_ctx = await self._build_tool_ctx(ctx)

        fragments: list[PromptFragment] = []
        if ctx and self._handlers:
            fragments = await collect_fragments(ctx, self._handlers)

        llm_messages = assemble_prompt(fragments, messages)
        tool_defs = self._build_tool_defs()

        result: TurnResult = TurnResult(has_reply=False)
        try:
            result = await self._stream_and_process(llm_messages, tool_defs)
        except _ContextLengthError:
            result = await self._handle_context_overflow(fragments, messages, tool_defs)
        if result.has_reply and result.reply_text and self._self_review_enabled:
            reviewed = await self._self_review(result.reply_text, llm_messages)
            if reviewed:
                result = TurnResult(
                    has_reply=True,
                    reply_text=reviewed,
                    usage=result.usage,
                )

        return result

    async def _build_tool_ctx(self, ctx: SessionContext) -> dict[str, Any]:
        tool_ctx: dict[str, Any] = {
            "session_id": ctx.session_id,
            "user_id": ctx.user_id,
            "platform": ctx.platform,
            "scene_type": ctx.scene_type,
            "scene_id": ctx.scene_id,
        }
        try:
            from sqlalchemy import select as sa_select

            from apeiria.db.engine import get_session
            from apeiria.db.models.ai_settings import AIRuntimeSettings

            async with get_session() as db:
                settings = (
                    await db.execute(
                        sa_select(AIRuntimeSettings).where(AIRuntimeSettings.id == 1)
                    )
                ).scalar_one_or_none()
            if settings:
                tool_ctx["settings"] = settings
        except (RuntimeError, OSError):
            pass
        return tool_ctx

    async def _handle_context_overflow(
        self,
        fragments: list[PromptFragment],
        messages: list[Message],
        tool_defs: list[dict[str, Any]] | None,
    ) -> TurnResult:
        logger.info("Context length exceeded, compacting and retrying")
        if not self._compaction_fn:
            return TurnResult(has_reply=False, error="Context length exceeded")
        try:
            await self._compaction_fn()
        except Exception:  # noqa: BLE001
            logger.warning("Compaction failed during fallback", exc_info=True)
            return TurnResult(
                has_reply=False,
                error="Context length exceeded, compaction failed",
            )
        llm_messages = assemble_prompt(fragments, messages)
        try:
            return await self._stream_and_process(llm_messages, tool_defs)
        except Exception as retry_err:  # noqa: BLE001
            return TurnResult(has_reply=False, error=str(retry_err))

    async def _stream_and_process(
        self,
        llm_messages: list[dict[str, str]],
        tool_defs: list[dict[str, Any]] | None,
    ) -> TurnResult:
        try:
            return await self._run_with_tools(llm_messages, tool_defs)
        except _ContextLengthError:
            raise
        except Exception as first_err:  # noqa: BLE001
            logger.warning("LLM call failed, retrying: {}", first_err)
            try:
                return await self._run_with_tools(llm_messages, tool_defs)
            except Exception as retry_err:  # noqa: BLE001
                return TurnResult(has_reply=False, error=str(retry_err))

    async def _run_with_tools(  # noqa: C901
        self,
        llm_messages: list[dict[str, Any]],
        tool_defs: list[dict[str, Any]] | None,
    ) -> TurnResult:
        current_messages: list[dict[str, Any]] = list(llm_messages)
        accumulated_text = ""

        for _round_num in range(_MAX_TOOL_ROUNDS):
            reply_text, tool_calls, usage = await self._stream_llm(
                current_messages, tool_defs
            )

            if usage:
                self._last_prompt_tokens = usage.prompt_tokens

            if tool_calls and tool_calls[0].name == "skip_if_not_worth_it":
                return TurnResult(has_reply=False)

            if not reply_text and not tool_calls:
                if accumulated_text:
                    return TurnResult(
                        has_reply=True,
                        reply_text=accumulated_text,
                    )
                return TurnResult(has_reply=False)

            if reply_text and not tool_calls:
                accumulated_text += reply_text
                return TurnResult(
                    has_reply=True,
                    reply_text=accumulated_text,
                    usage=usage or None,
                )

            if tool_calls:
                current_messages.append(
                    {
                        "role": "assistant",
                        "content": reply_text or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.name,
                                    "arguments": json.dumps(tc.arguments),
                                },
                            }
                            for tc in tool_calls
                        ],
                    }
                )

                for tc in tool_calls:
                    await self._events.emit(
                        AgentEvent(
                            type="tool:start",
                            data={
                                "name": tc.name,
                                "arguments": tc.arguments,
                            },
                        )
                    )
                    tool_result = await self._execute_tool(tc)
                    await self._events.emit(
                        AgentEvent(
                            type="tool:end",
                            data={
                                "name": tc.name,
                                "result": tool_result,
                            },
                        )
                    )
                    current_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": tool_result.content or tool_result.error or "",
                        }
                    )

                if reply_text:
                    accumulated_text += reply_text

        if accumulated_text:
            return TurnResult(has_reply=True, reply_text=accumulated_text)
        return TurnResult(has_reply=False)

    async def _stream_llm(  # noqa: C901
        self,
        messages: list[dict[str, Any]],
        tool_defs: list[dict[str, Any]] | None,
    ) -> tuple[str, list[ToolCall], Any]:
        text = ""
        tool_calls: list[ToolCall] = []
        usage: TokenUsage | None = None

        async def _do_stream() -> None:
            nonlocal text, usage
            kwargs: dict[str, Any] = {"messages": messages}
            if tool_defs:
                kwargs["tools"] = tool_defs
            async for event in self._stream_fn(**kwargs):
                if event.type == StreamEventType.TEXT_DELTA and event.text:
                    text += event.text
                    await self._events.emit(
                        AgentEvent(
                            type="message:delta",
                            data={"text": event.text},
                        )
                    )
                elif event.type == StreamEventType.TOOL_CALL_END and event.tool_call:
                    tool_calls.append(event.tool_call)
                elif event.type == StreamEventType.USAGE and event.usage:
                    usage = event.usage
                elif event.type == StreamEventType.ERROR and event.error:
                    if "context length" in event.error.lower():
                        raise _ContextLengthError(event.error)
                    msg = f"LLM error: {event.error}"
                    raise RuntimeError(msg)

        try:
            await asyncio.wait_for(_do_stream(), timeout=_STREAM_TIMEOUT)
        except _ContextLengthError:
            raise
        except AIModelContextLengthError as e:
            raise _ContextLengthError(str(e)) from e
        except asyncio.TimeoutError:
            logger.warning("LLM stream timed out after {}s", _STREAM_TIMEOUT)
            msg = f"LLM streaming timed out after {_STREAM_TIMEOUT}s"
            raise RuntimeError(msg) from None

        return text, tool_calls, usage

    async def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
        tool = self._tools.get(tool_call.name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Unknown tool: {tool_call.name}",
            )
        try:
            kwargs = dict(tool_call.arguments)
            if self._tool_ctx is not None:
                kwargs["_ctx"] = self._tool_ctx
            result = tool.execute(**kwargs)
            if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                result = await result
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "Tool %s failed: %s",
                tool_call.name,
                e,
                exc_info=True,
            )
            return ToolResult(success=False, error=str(e))
        else:
            if not isinstance(result, ToolResult):
                return ToolResult(success=True, content=str(result))
            return result

    async def _maybe_compact(self, _messages: list[Message]) -> None:
        if self._last_prompt_tokens is None:
            return
        if self._context_window <= 0:
            return
        ratio = self._last_prompt_tokens / self._context_window
        if ratio > self._compaction_threshold and self._compaction_fn:
            logger.info(
                "Compaction triggered: ratio=%.2f threshold=%.2f",
                ratio,
                self._compaction_threshold,
            )
            try:
                await self._compaction_fn()
            except Exception:  # noqa: BLE001
                logger.warning("Compaction failed", exc_info=True)

    async def _self_review(
        self,
        reply_text: str,
        original_messages: list[dict[str, str]],
    ) -> str | None:
        try:
            review_messages: list[dict[str, str]] = list(original_messages)
            review_messages.append({"role": "assistant", "content": reply_text})
            review_messages.append(
                {
                    "role": "user",
                    "content": (
                        "请检查你上面的回复是否完整、正确、符合上下文。"
                        "如果有错误请修正后输出完整回复；"
                        "如果没有问题，请原样输出。"
                    ),
                }
            )

            reviewed = ""
            async for event in self._stream_fn(messages=review_messages):
                if event.type == StreamEventType.TEXT_DELTA and event.text:
                    reviewed += event.text
            return reviewed.strip() or None
        except Exception:  # noqa: BLE001
            logger.warning(
                "Self-review failed, keeping original",
                exc_info=True,
            )
            return None

    def _build_tool_defs(self) -> list[dict[str, Any]] | None:
        if not self._tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]


class _ContextLengthError(Exception):
    pass
