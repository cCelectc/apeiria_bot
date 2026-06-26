from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class PluginType(StrEnum):
    NORMAL = "normal"
    SUPERUSER = "superuser"


@dataclass
class RegisterConfig:
    key: str
    default: Any
    help: str = ""
    type: object = str
    choices: list[Any] = field(default_factory=list)
    choice_labels: dict[str, str] = field(default_factory=dict)
    item_type: object | None = None
    key_type: object | None = None
    allows_null: bool = False
    fields: list["RegisterConfig"] = field(default_factory=list)
    item_schema: "RegisterConfig | None" = None
    key_schema: "RegisterConfig | None" = None
    value_schema: "RegisterConfig | None" = None
    label: str = ""
    order: int = 99
    secret: bool = False


@dataclass
class CommandDeclaration:
    name: str
    description: str = ""
    usage: str = ""
    aliases: list[str] = field(default_factory=list)
    custom_prefix: str | None = None


@dataclass
class HelpExtra:
    category: str = ""
    introduction: str = ""
    precautions: list[str] = field(default_factory=list)
    owner_help: str = ""


@dataclass
class UiExtra:
    label: str = ""
    icon: str = ""
    order: int = 99
    hidden: bool = False


@dataclass
class ConfigExtra:
    fields: list[RegisterConfig] = field(default_factory=list)


@dataclass
class PluginExtraData:
    author: str = "apeiria"
    version: str = "0.1.0"
    plugin_type: PluginType = PluginType.NORMAL
    help: HelpExtra = field(default_factory=HelpExtra)
    ui: UiExtra = field(default_factory=UiExtra)
    config: ConfigExtra = field(default_factory=ConfigExtra)
    commands: list[str | CommandDeclaration] = field(default_factory=list)
    required_plugins: list[str] = field(default_factory=list)

    @property
    def configs(self) -> list[RegisterConfig]:
        return self.config.fields

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["plugin_type"] = self.plugin_type.value
        data["_apeiria"] = True
        return data

    @classmethod
    def from_extra(cls, extra: dict[str, Any]) -> "PluginExtraData | None":
        if not extra.get("_apeiria"):
            return None
        try:
            return cls(
                author=extra.get("author", "unknown"),
                version=extra.get("version", "0.0.0"),
                plugin_type=PluginType(extra.get("plugin_type", "normal")),
                config=ConfigExtra(fields=list(extra.get("configs", []))),
                commands=list(extra.get("commands", [])),
                required_plugins=list(extra.get("required_plugins", [])),
            )
        except (ValueError, TypeError, KeyError):
            return None
