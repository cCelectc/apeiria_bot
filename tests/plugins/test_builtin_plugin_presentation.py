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
    "apeiria.builtin_plugins.contact_approval",
    "apeiria.builtin_plugins.contact_owner",
    "apeiria.builtin_plugins.help",
    "apeiria.builtin_plugins.qq_tools",
    "apeiria.builtin_plugins.render",
    "apeiria.builtin_plugins.repeater",
    "apeiria.builtin_plugins.self_revoke",
    "apeiria.builtin_plugins.trigger_reply",
    "apeiria.builtin_plugins.web_ui",
)


def test_builtin_plugin_set_includes_contact_approval_role() -> None:
    assert iter_builtin_plugin_modules() == BUILTIN_PLUGIN_MODULES


def test_web_ui_is_the_protected_builtin_control_panel() -> None:
    assert is_protected_plugin_module("apeiria.builtin_plugins.web_ui")
    assert get_plugin_kind("apeiria.builtin_plugins.web_ui") == "core"
    assert get_default_protection_mode("apeiria.builtin_plugins.web_ui") == "required"
