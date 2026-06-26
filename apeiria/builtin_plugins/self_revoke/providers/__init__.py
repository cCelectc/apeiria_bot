from ._types import (
    FeedbackKind,
    RevokeActionResult,
    RevokeTarget,
    SelfRevokeProvider,
    SelfRevokeProviderRegistry,
)
from .discord import DiscordSelfRevokeProvider
from .feishu import FeishuSelfRevokeProvider
from .onebot_v11 import OneBotV11SelfRevokeProvider
from .onebot_v12 import OneBotV12SelfRevokeProvider
from .qq_guild import QQGuildSelfRevokeProvider
from .satori import SatoriSelfRevokeProvider
from .telegram import TelegramSelfRevokeProvider

OneBotSelfRevokeProvider = OneBotV11SelfRevokeProvider

self_revoke_provider_registry = SelfRevokeProviderRegistry(
    providers=(
        OneBotV11SelfRevokeProvider(),
        OneBotV12SelfRevokeProvider(),
        TelegramSelfRevokeProvider(),
        DiscordSelfRevokeProvider(),
        FeishuSelfRevokeProvider(),
        SatoriSelfRevokeProvider(),
        QQGuildSelfRevokeProvider(),
    )
)

__all__ = [
    "DiscordSelfRevokeProvider",
    "FeedbackKind",
    "FeishuSelfRevokeProvider",
    "OneBotSelfRevokeProvider",
    "OneBotV11SelfRevokeProvider",
    "OneBotV12SelfRevokeProvider",
    "QQGuildSelfRevokeProvider",
    "RevokeActionResult",
    "RevokeTarget",
    "SatoriSelfRevokeProvider",
    "SelfRevokeProvider",
    "SelfRevokeProviderRegistry",
    "TelegramSelfRevokeProvider",
    "self_revoke_provider_registry",
]
