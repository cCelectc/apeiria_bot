from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import md5
from typing import Literal

HelpViewRole = Literal["user", "admin", "owner"]


@dataclass(slots=True)
class CommandHelpInfo:
    name: str
    description: str = ""
    aliases: list[str] = field(default_factory=list)
    usage: str = ""
    admin_only: bool = False
    custom_prefix: str | None = None


@dataclass(slots=True)
class PluginHelpInfo:
    plugin_id: str
    module_name: str
    name: str
    display_name: str
    description: str = ""
    usage: str = ""
    plugin_type: str = "normal"
    version: str = ""
    source: str = "user"
    icon_url: str = ""
    menu_category: str = ""
    introduction: str = ""
    precautions: list[str] = field(default_factory=list)
    owner_help: str = ""
    commands: list[CommandHelpInfo] = field(default_factory=list)
    order: int = 99

    @property
    def initials(self) -> str:
        compact = "".join(ch for ch in self.display_name if ch.isalnum())
        if compact:
            return compact[:2].upper()
        return self.display_name.strip()[:2] or "?"

    @property
    def accent_color(self) -> str:
        digest = md5(self.module_name.encode("utf-8")).hexdigest()
        hue = int(digest[:2], 16) % 360
        return f"hsl({hue} 68% 56%)"

    @property
    def command_count(self) -> int:
        return len(self.commands)

    @property
    def is_builtin(self) -> bool:
        return self.source == "builtin"
