from __future__ import annotations

import pytest


@pytest.fixture(scope="module", autouse=True)
def _require_help_deps(after_nonebot_init: None) -> None:  # noqa: ARG001
    from nonebot import require

    require("nonebot_plugin_alconna")
    require("nonebot_plugin_htmlrender")


def test_help_command_item_defaults() -> None:
    from apeiria.builtin_plugins.help.models import HelpCommandItem

    cmd = HelpCommandItem(name="test")
    assert cmd.name == "test"
    assert cmd.aliases == []
    assert cmd.description == ""
    assert cmd.usage == ""
    assert cmd.admin_only is False


def test_help_plugin_item_properties() -> None:
    from apeiria.builtin_plugins.help.models import HelpCommandItem, HelpPluginItem

    p = HelpPluginItem(
        plugin_id="p",
        module_name="m",
        name="TestPlugin",
        source="builtin",
        commands=[
            HelpCommandItem(name="a"),
            HelpCommandItem(name="b"),
            HelpCommandItem(name="c"),
        ],
    )
    assert p.command_count == 3
    assert p.is_builtin is True

    other = HelpPluginItem(plugin_id="q", module_name="m2", name="Q", source="user")
    assert other.is_builtin is False
    assert other.command_count == 0


def test_format_detail_text() -> None:
    from apeiria.builtin_plugins.help.models import HelpCommandItem, HelpPluginItem
    from apeiria.builtin_plugins.help.renderer import _format_detail_text

    plugin = HelpPluginItem(
        plugin_id="p",
        module_name="m",
        name="Hello",
        description="A test plugin",
        usage="Use /hello to greet",
        commands=[
            HelpCommandItem(name="hello", description="Say hello", usage="/hello"),
            HelpCommandItem(
                name="admin", usage="/admin", admin_only=True, aliases=["a"]
            ),
        ],
    )
    text = _format_detail_text(plugin, prefix="/")
    assert "Hello" in text
    assert "hello" in text
    assert "Say hello" in text
    assert "/admin" in text
    assert "仅超管" in text
    assert "a" in text
    assert "Use /hello to greet" in text


def test_format_menu_text() -> None:
    from apeiria.builtin_plugins.help.config import HelpConfig
    from apeiria.builtin_plugins.help.models import HelpCommandItem, HelpPluginItem
    from apeiria.builtin_plugins.help.renderer import _format_menu_text

    config = HelpConfig(title="Menu")
    plugins = [
        HelpPluginItem(
            plugin_id="p",
            module_name="m",
            name="Plugin",
            description="desc",
            commands=[
                HelpCommandItem(name="cmd1", admin_only=True),
                HelpCommandItem(name="cmd2"),
            ],
        )
    ]

    text = _format_menu_text(plugins, prefix="/", config=config)
    assert "Menu" in text
    assert "Plugin" in text
    assert "cmd1" in text
    assert "cmd2" in text

    text_expanded = _format_menu_text(
        plugins,
        prefix="/",
        config=HelpConfig(title="Menu", expand_commands=True),
    )
    assert "仅超管" in text_expanded


def test_build_detail_data() -> None:
    from apeiria.builtin_plugins.help.config import HelpConfig
    from apeiria.builtin_plugins.help.models import HelpCommandItem, HelpPluginItem
    from apeiria.builtin_plugins.help.renderer import _build_detail_data

    config = HelpConfig(accent_color="#ff0000")
    plugin = HelpPluginItem(
        plugin_id="p",
        module_name="m",
        name="N",
        description="D",
        usage="U",
        commands=[HelpCommandItem(name="c", description="cd", aliases=["x"])],
    )
    data = _build_detail_data(plugin, prefix="/", config=config)
    assert data["plugin"]["name"] == "N"
    assert data["plugin"]["description"] == "D"
    assert data["usage"] == "U"
    assert data["commands"][0]["name"] == "c"
    assert data["commands"][0]["description"] == "cd"
    assert "x" in data["commands"][0]["aliases"]


def test_build_menu_data_groups() -> None:
    from apeiria.builtin_plugins.help.config import HelpConfig
    from apeiria.builtin_plugins.help.models import HelpCommandItem, HelpPluginItem
    from apeiria.builtin_plugins.help.renderer import _build_menu_data

    config = HelpConfig(expand_commands=False)
    plugins = [
        HelpPluginItem(
            plugin_id="a",
            module_name="ma",
            name="App",
            source="user",
            commands=[HelpCommandItem(name="x")],
        ),
        HelpPluginItem(
            plugin_id="b",
            module_name="mb",
            name="Builtin",
            source="builtin",
            commands=[HelpCommandItem(name="y")],
        ),
    ]
    data = _build_menu_data(plugins, prefix="/", config=config, is_superuser=True)
    assert len(data["groups"]) == 2  # application + builtin
    app_group = next(g for g in data["groups"] if g["label"] == "功能")
    builtin_group = next(g for g in data["groups"] if g["label"] == "内置")
    assert len(app_group["plugins"]) == 1
    assert len(builtin_group["plugins"]) == 1


def test_build_menu_data_hides_builtin_for_normal_user() -> None:
    from apeiria.builtin_plugins.help.config import HelpConfig
    from apeiria.builtin_plugins.help.models import HelpCommandItem, HelpPluginItem
    from apeiria.builtin_plugins.help.renderer import _build_menu_data

    config = HelpConfig()
    plugins = [
        HelpPluginItem(
            plugin_id="a",
            module_name="ma",
            name="App",
            source="user",
            commands=[HelpCommandItem(name="x")],
        ),
        HelpPluginItem(
            plugin_id="b",
            module_name="mb",
            name="Builtin",
            source="builtin",
            commands=[HelpCommandItem(name="y")],
        ),
    ]
    data = _build_menu_data(plugins, prefix="/", config=config, is_superuser=False)
    assert len(data["groups"]) == 1
    assert data["groups"][0]["label"] == "功能"


def test_apply_admin_filter_superuser_passthrough() -> None:
    from apeiria.builtin_plugins.help.models import HelpCommandItem
    from apeiria.builtin_plugins.help.probe import _apply_admin_filter

    cmds = [
        HelpCommandItem(name="admin", admin_only=True),
        HelpCommandItem(name="normal"),
    ]
    result = _apply_admin_filter(cmds, is_superuser=True)
    assert result == cmds
    assert any(c.admin_only for c in result)


def test_apply_admin_filter_hides_admin_for_normal() -> None:
    from apeiria.builtin_plugins.help.models import HelpCommandItem
    from apeiria.builtin_plugins.help.probe import _apply_admin_filter

    cmds = [
        HelpCommandItem(name="admin", admin_only=True),
        HelpCommandItem(name="normal"),
    ]
    result = _apply_admin_filter(cmds, is_superuser=False)
    assert result is not None
    assert len(result) == 1
    assert result[0].name == "normal"
    assert not any(c.admin_only for c in result)


def test_apply_admin_filter_all_admin_returns_none() -> None:
    from apeiria.builtin_plugins.help.models import HelpCommandItem
    from apeiria.builtin_plugins.help.probe import _apply_admin_filter

    cmds = [
        HelpCommandItem(name="a", admin_only=True),
        HelpCommandItem(name="b", admin_only=True),
    ]
    assert _apply_admin_filter(cmds, is_superuser=False) is None


def test_apply_admin_filter_empty_returns_empty() -> None:
    from apeiria.builtin_plugins.help.probe import _apply_admin_filter

    assert _apply_admin_filter([], is_superuser=False) == []
