"""Plugin metadata types and configuration models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class PluginType(str, Enum):
    """Plugin type classification."""

    NORMAL = "normal"
    SUPERUSER = "superuser"


def normalize_plugin_type_value(value: object) -> str:
    """Normalize persisted plugin type values to the supported subset."""

    if not isinstance(value, str):
        return PluginType.NORMAL.value
    normalized = value.strip().lower()
    if normalized in {"admin", "hidden", "parent"}:
        return PluginType.NORMAL.value
    if normalized == PluginType.SUPERUSER.value:
        return PluginType.SUPERUSER.value
    return PluginType.NORMAL.value


@dataclass
class RegisterConfig:
    """Declares a plugin configuration item."""

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
    """Declares one command help entry for plugin metadata."""

    name: str
    description: str = ""
    usage: str = ""
    aliases: list[str] = field(default_factory=list)
    custom_prefix: str | None = None


@dataclass
class HelpExtra:
    """Help-specific plugin metadata."""

    category: str = ""
    introduction: str = ""
    precautions: list[str] = field(default_factory=list)
    owner_help: str = ""


@dataclass
class UiExtra:
    """Plugin list and card UI metadata."""

    label: str = ""
    icon: str = ""
    order: int = 99
    hidden: bool = False


@dataclass
class ConfigExtra:
    """Apeiria-specific config metadata enhancements."""

    fields: list[RegisterConfig] = field(default_factory=list)


@dataclass
class PluginExtraData:
    """Extended metadata for apeiria plugins."""

    author: str = "apeiria"
    version: str = "0.1.0"
    plugin_type: PluginType = PluginType.NORMAL
    help: HelpExtra = field(default_factory=HelpExtra)
    ui: UiExtra = field(default_factory=UiExtra)
    config: ConfigExtra = field(default_factory=ConfigExtra)
    commands: list[str | CommandDeclaration] = field(default_factory=list)
    required_plugins: list[str] = field(default_factory=list)

    @property
    def menu_category(self) -> str:
        return self.help.category

    @property
    def introduction(self) -> str:
        return self.help.introduction

    @property
    def precautions(self) -> list[str]:
        return self.help.precautions

    @property
    def owner_help(self) -> str:
        return self.help.owner_help

    @property
    def configs(self) -> list[RegisterConfig]:
        return self.config.fields

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["plugin_type"] = self.plugin_type.value
        data["_apeiria"] = True
        return data

    @classmethod
    def from_extra(cls, extra: dict[str, Any]) -> PluginExtraData | None:
        if not extra.get("_apeiria"):
            return None
        try:
            plugin_type = PluginType(
                normalize_plugin_type_value(extra.get("plugin_type", "normal"))
            )

            help_raw = extra.get("help")
            if not isinstance(help_raw, dict):
                help_raw = {}
            ui_raw = extra.get("ui")
            if not isinstance(ui_raw, dict):
                ui_raw = {}
            config_raw = extra.get("config")
            if not isinstance(config_raw, dict):
                config_raw = {}

            configs_raw = config_raw.get("fields", extra.get("configs", []))
            configs = [
                _coerce_register_config(item) if isinstance(item, dict) else item
                for item in configs_raw
            ]
            commands_raw = extra.get("commands", [])
            commands = [
                _coerce_command_declaration(item) if isinstance(item, dict) else item
                for item in commands_raw
            ]

            return cls(
                author=extra.get("author", "unknown"),
                version=extra.get("version", "0.0.0"),
                plugin_type=plugin_type,
                help=HelpExtra(
                    category=str(
                        help_raw.get("category", extra.get("menu_category", ""))
                    ),
                    introduction=str(
                        help_raw.get("introduction", extra.get("introduction", ""))
                    ),
                    precautions=[
                        str(item)
                        for item in help_raw.get(
                            "precautions",
                            extra.get("precautions", []),
                        )
                        if isinstance(item, str) and item.strip()
                    ],
                    owner_help=str(
                        help_raw.get("owner_help", extra.get("owner_help", ""))
                    ),
                ),
                ui=UiExtra(
                    label=str(ui_raw.get("label", "")),
                    icon=str(ui_raw.get("icon", "")),
                    order=int(ui_raw.get("order", 99) or 99),
                    hidden=bool(ui_raw.get("hidden", False)),
                ),
                config=ConfigExtra(fields=configs),
                commands=commands,
                required_plugins=extra.get("required_plugins", []),
            )
        except (ValueError, TypeError, KeyError):
            return None


def _coerce_register_config(raw: dict[str, Any]) -> RegisterConfig:
    fields = [
        _coerce_register_config(item)
        for item in raw.get("fields", [])
        if isinstance(item, dict)
    ]
    item_schema = raw.get("item_schema")
    key_schema = raw.get("key_schema")
    value_schema = raw.get("value_schema")
    return RegisterConfig(
        key=str(raw.get("key", "")),
        default=raw.get("default"),
        help=str(raw.get("help", "")),
        type=raw.get("type", str),
        choices=list(raw.get("choices", [])),
        choice_labels={
            str(key): str(value)
            for key, value in raw.get("choice_labels", {}).items()
            if isinstance(key, str) and isinstance(value, str)
        },
        item_type=raw.get("item_type"),
        key_type=raw.get("key_type"),
        allows_null=bool(raw.get("allows_null", False)),
        fields=fields,
        item_schema=(
            _coerce_register_config(item_schema)
            if isinstance(item_schema, dict)
            else None
        ),
        key_schema=(
            _coerce_register_config(key_schema)
            if isinstance(key_schema, dict)
            else None
        ),
        value_schema=(
            _coerce_register_config(value_schema)
            if isinstance(value_schema, dict)
            else None
        ),
        label=str(raw.get("label", "")),
        order=int(raw.get("order", 99) or 99),
        secret=bool(raw.get("secret", False)),
    )


def _coerce_command_declaration(raw: dict[str, Any]) -> CommandDeclaration:
    raw_custom_prefix = raw.get("custom_prefix")
    return CommandDeclaration(
        name=str(raw.get("name", "")),
        description=str(raw.get("description", "")),
        usage=str(raw.get("usage", "")),
        aliases=[
            str(item)
            for item in raw.get("aliases", [])
            if isinstance(item, str) and item.strip()
        ],
        custom_prefix=raw_custom_prefix if isinstance(raw_custom_prefix, str) else None,
    )
