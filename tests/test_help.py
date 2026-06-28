from __future__ import annotations

import pytest


@pytest.fixture(scope="module", autouse=True)
def _require_help_deps(after_nonebot_init: None) -> None:  # noqa: ARG001
    from nonebot import require

    require("nonebot_plugin_alconna")
    require("nonebot_plugin_htmlrender")


def test_parse_pipe_command() -> None:
    from apeiria.builtin_plugins.help.generator import _parse_pipe_command

    cmd = _parse_pipe_command("名称|描述|!")
    assert cmd is not None
    assert cmd.name == "名称"
    assert cmd.description == "描述"
    assert cmd.custom_prefix == "!"

    only = _parse_pipe_command("only")
    assert only is not None
    assert only.name == "only"
    assert only.custom_prefix is None

    assert _parse_pipe_command("") is None
    assert _parse_pipe_command("   ") is None


def test_display_name() -> None:
    from apeiria.builtin_plugins.help.commands import _display_name

    assert _display_name("/", "help", None) == "/help"
    assert _display_name("/", "help", "!") == "!help"


def test_dedupe_and_normalize_commands() -> None:
    from apeiria.builtin_plugins.help.generator import _dedupe_and_normalize_commands
    from apeiria.builtin_plugins.help.models import CommandHelpInfo

    a = CommandHelpInfo(name="x", description="desc")
    b = CommandHelpInfo(name="x", aliases=["y"])
    out = _dedupe_and_normalize_commands([a, b])
    assert len(out) == 1
    assert out[0].description == "desc"
    assert "y" in out[0].aliases


def test_merge_declared_commands() -> None:
    from apeiria.builtin_plugins.help.generator import _merge_declared_commands
    from apeiria.builtin_plugins.help.models import CommandHelpInfo
    from apeiria.plugin.metadata.api import CommandDeclaration

    existing = [CommandHelpInfo(name="a")]
    declared = ["b", CommandDeclaration(name="c", description="cc", aliases=["cx"])]
    out = _merge_declared_commands(existing, declared)
    by_name = {c.name: c for c in out}
    assert set(by_name) == {"a", "b", "c"}
    assert by_name["c"].description == "cc"
    assert "cx" in by_name["c"].aliases


def test_apply_overrides() -> None:
    from apeiria.builtin_plugins.help.config import PluginOverride
    from apeiria.builtin_plugins.help.generator import _apply_overrides
    from apeiria.builtin_plugins.help.models import PluginHelpInfo

    plugins = [
        PluginHelpInfo(plugin_id="p1", module_name="m1", name="P1", display_name="P1")
    ]
    overrides = [
        PluginOverride(
            plugin_name="p1",
            display_name="New",
            description="D",
            category="Cat",
            order=5,
            extra_commands=["cmd|desc"],
        )
    ]
    _apply_overrides(plugins, overrides)
    assert plugins[0].display_name == "New"
    assert plugins[0].description == "D"
    assert plugins[0].menu_category == "Cat"
    assert plugins[0].order == 5
    assert any(c.name == "cmd" for c in plugins[0].commands)


def test_plugin_help_info_properties() -> None:
    from apeiria.builtin_plugins.help.models import CommandHelpInfo, PluginHelpInfo

    p = PluginHelpInfo(
        plugin_id="p",
        module_name="m",
        name="N",
        display_name="Hello",
        source="builtin",
        commands=[CommandHelpInfo(name="a"), CommandHelpInfo(name="b")],
    )
    assert p.command_count == 2
    assert p.is_builtin is True
    assert p.initials == "HE"

    other = PluginHelpInfo(
        plugin_id="q", module_name="m2", name="Q", display_name="Q", source="user"
    )
    assert other.is_builtin is False


def test_build_menu_data_expands_commands() -> None:
    from apeiria.builtin_plugins.help.config import HelpAppearanceConfig, HelpConfig
    from apeiria.builtin_plugins.help.models import CommandHelpInfo, PluginHelpInfo
    from apeiria.builtin_plugins.help.renderer import _build_menu_data

    plugins = [
        PluginHelpInfo(
            plugin_id="p",
            module_name="m",
            name="N",
            display_name="N",
            commands=[CommandHelpInfo(name="a", description="da")],
        )
    ]
    expanded = HelpConfig(appearance=HelpAppearanceConfig(expand_commands=True))
    data = _build_menu_data(plugins, prefix="/", config=expanded, role="user")
    entry = data["plugins"][0]
    assert "commands" in entry
    assert entry["commands"][0]["display_name"] == "/a"
    assert entry["commands"][0]["description"] == "da"

    collapsed = HelpConfig(appearance=HelpAppearanceConfig(expand_commands=False))
    data2 = _build_menu_data(plugins, prefix="/", config=collapsed, role="user")
    assert "commands" not in data2["plugins"][0]


def test_format_detail_text() -> None:
    from apeiria.builtin_plugins.help.models import CommandHelpInfo, PluginHelpInfo
    from apeiria.builtin_plugins.help.renderer import _format_detail_text

    info = PluginHelpInfo(
        plugin_id="p",
        module_name="m",
        name="N",
        display_name="Hello",
        description="desc",
        commands=[CommandHelpInfo(name="a", description="da")],
    )
    text = _format_detail_text(info, prefix="/", role="user")
    assert "Hello" in text
    assert "/a" in text
    assert "da" in text
