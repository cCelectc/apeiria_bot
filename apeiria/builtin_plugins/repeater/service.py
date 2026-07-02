from __future__ import annotations

import time
from hashlib import sha256
from random import random
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .config import RepeaterConfig


class _RoundState:
    """同一群内同一内容的一轮复读追踪状态。

    一轮 = 群友连续发送相同 content_hash 的消息，直到有人换内容为止。
    last_triggered_at 为 0.0 表示本轮还没复读过，> 0 表示已触发过复读。
    """

    __slots__ = (
        "content_hash",  # 当前轮内容哈希
        "count",  # 当前轮累计次数
        "last_triggered_at",  # 本轮上一次复读时间戳，0.0 = 未复读
        "last_updated_at",  # 最近更新（含普通计数），用于过期清理
        "last_user_id",  # 上一个说话的用户
        "message",  # 原始消息对象
    )

    def __init__(  # noqa: PLR0913
        self,
        content_hash: str,
        message: Any,
        count: int,
        last_user_id: str,
        last_triggered_at: float,
        last_updated_at: float | None = None,
    ) -> None:
        self.content_hash = content_hash
        self.message = message
        self.count = count
        self.last_user_id = last_user_id
        self.last_triggered_at = last_triggered_at
        self.last_updated_at = (
            last_updated_at if last_updated_at is not None else time.monotonic()
        )


def hash_message(message: Any) -> str:
    """对消息内容做稳定哈希，用于判断两条消息是否"相同"。"""
    raw = str(message)
    return sha256(raw.encode("utf-8")).hexdigest()


class RepeaterService:
    """复读机核心逻辑，按群维度追踪复读轮次并决定是否触发。

    生命周期：全局单例，内存状态，重启清空。
    """

    _CLEANUP_INTERVAL = 50

    def __init__(self) -> None:
        self._states: dict[str, _RoundState] = {}
        self._call_count = 0

    def _cleanup_stale(self, now: float, ttl: float) -> None:
        """清除超过 ttl 秒没更新的僵死状态，防止长期不活跃的群占用内存。"""
        self._states = {
            k: v for k, v in self._states.items() if now - v.last_updated_at < ttl
        }

    def evaluate(  # noqa: PLR0911
        self,
        group_scope: str,
        content_hash: str,
        message: Any,
        user_id: str,
        *,
        config: RepeaterConfig,
    ) -> Any | None:
        """根据当前消息评估是否复读，返回原始消息表示触发，None 表示跳过。

        判据链路（任一不满足即返回 None）：
        1. 同群同一内容（content_hash）累计次数 >= repeat_threshold
        2. 本轮尚未复读过（last_triggered_at == 0）
        3. 距上次复读 >= cooldown_seconds
        4. random() < probability
        """
        now = time.monotonic()
        self._call_count += 1

        # ---- 周期性清理僵死状态 ----
        if self._call_count % self._CLEANUP_INTERVAL == 0:
            self._cleanup_stale(now, config.cooldown_seconds * 5)

        # ---- 定位当前群的状态 ----
        previous = self._states.get(group_scope)

        if previous is not None:
            previous.last_updated_at = now
            # 内容变了 → 开启新一轮
            if previous.content_hash != content_hash:
                previous = None
            # 同一用户连续发 → 不计入
            elif previous.last_user_id == user_id:
                return None

        # 无历史或内容已变 → 初始化新轮
        if previous is None:
            self._states[group_scope] = _RoundState(
                content_hash=content_hash,
                message=message,
                count=1,
                last_user_id=user_id,
                last_triggered_at=0.0,
                last_updated_at=now,
            )
            return None

        # ---- 本轮存在，递增加 ----
        count = previous.count + 1
        state = _RoundState(
            content_hash=content_hash,
            message=message,
            count=count,
            last_user_id=user_id,
            last_triggered_at=previous.last_triggered_at,
            last_updated_at=now,
        )

        # 未达阈值
        if count < config.repeat_threshold:
            self._states[group_scope] = state
            return None

        # 本轮已复读过 → 不再复读
        if previous.last_triggered_at > 0:
            self._states[group_scope] = state
            return None

        # 冷却中
        if now - previous.last_triggered_at < config.cooldown_seconds:
            self._states[group_scope] = state
            return None

        # 概率拦截
        if random() >= config.probability:
            self._states[group_scope] = state
            return None

        # ---- 触发复读 ----
        self._states[group_scope] = _RoundState(
            content_hash=content_hash,
            message=message,
            count=count,
            last_user_id=user_id,
            last_triggered_at=now,
            last_updated_at=now,
        )
        return message

    def reset(self, group_scope: str) -> None:
        """重置指定群的状态（测试/调试用）。"""
        self._states.pop(group_scope, None)


__all__ = ["RepeaterService", "hash_message"]
