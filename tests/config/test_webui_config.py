from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.config.webui_config import WebUIConfig, get_web_ui_config

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def test_webui_config_ignores_retired_global_token_expiry_key(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "apeiria.config.webui_config.project_config_service.read_project_plugin_config",
        lambda _section: {},
    )
    monkeypatch.setattr(
        "apeiria.config.webui_config.project_config_service.read_project_config",
        lambda: {"web_ui_token_expire_days": 30},
    )

    assert get_web_ui_config().token_expire_days == WebUIConfig().token_expire_days
