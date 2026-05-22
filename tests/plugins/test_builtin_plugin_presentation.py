from __future__ import annotations

from apeiria._framework_loader import iter_builtin_plugin_modules
from apeiria.plugins.protection import (
    get_default_protection_mode,
    get_plugin_kind,
    is_protected_plugin_module,
)

BUILTIN_PLUGIN_MODULES = (
    "apeiria.builtin_plugins.admin",
    "apeiria.builtin_plugins.ai",
    "apeiria.builtin_plugins.help",
    "apeiria.builtin_plugins.render",
    "apeiria.builtin_plugins.self_revoke",
    "apeiria.builtin_plugins.web_ui",
)


def test_builtin_plugin_set_stays_six_role_modules() -> None:
    assert iter_builtin_plugin_modules() == BUILTIN_PLUGIN_MODULES


def test_web_ui_is_the_protected_builtin_control_panel() -> None:
    assert is_protected_plugin_module("apeiria.builtin_plugins.web_ui")
    assert get_plugin_kind("apeiria.builtin_plugins.web_ui") == "core"
    assert get_default_protection_mode("apeiria.builtin_plugins.web_ui") == "required"


def test_ai_render_and_self_revoke_remain_separate_user_controls() -> None:
    for module_name in (
        "apeiria.builtin_plugins.ai",
        "apeiria.builtin_plugins.render",
        "apeiria.builtin_plugins.self_revoke",
    ):
        assert module_name in iter_builtin_plugin_modules()
        assert not is_protected_plugin_module(module_name)
        assert get_plugin_kind(module_name) == "plugin"
        assert get_default_protection_mode(module_name) == "normal"
