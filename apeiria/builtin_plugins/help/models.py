from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class HelpCommandItem:
    name: str
    aliases: list[str] = field(default_factory=list)
    description: str = ""
    usage: str = ""
    admin_only: bool = False


@dataclass(slots=True)
class HelpPluginItem:
    plugin_id: str
    module_name: str
    name: str
    description: str = ""
    usage: str = ""
    plugin_type: str = "application"
    source: str = "user"
    icon_url: str = ""
    commands: list[HelpCommandItem] = field(default_factory=list)

    @property
    def command_count(self) -> int:
        return len(self.commands)

    @property
    def is_builtin(self) -> bool:
        return self.source == "builtin"
