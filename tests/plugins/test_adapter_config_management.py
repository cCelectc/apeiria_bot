from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.plugins.registry import PluginRegistrationConfigService

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def test_update_adapter_config_normalizes_modules_and_prunes_bindings(
    monkeypatch: MonkeyPatch,
) -> None:
    service = PluginRegistrationConfigService()
    written: dict[str, object] = {}

    monkeypatch.setattr(
        "apeiria.plugins.registry.adapter_config_service.read_project_adapter_config",
        lambda: {
            "modules": [
                "nonebot.adapters.one",
                "nonebot.adapters.two",
            ],
            "packages": {
                "nonebot-adapter-one": ["nonebot.adapters.one"],
                "nonebot-adapter-two": ["nonebot.adapters.two"],
            },
        },
    )

    def fake_write(config, config_path=None):  # noqa: ANN001,ARG001
        written["config"] = config

    monkeypatch.setattr(
        "apeiria.plugins.registry.adapter_config_service.write_project_adapter_config",
        fake_write,
    )
    monkeypatch.setattr(
        service,
        "_build_adapter_config_items",
        lambda modules: [],  # noqa: ARG005
    )

    service.update_adapter_config(
        [" nonebot.adapters.two ", "", "nonebot.adapters.two"],
    )

    assert written["config"] == {
        "modules": ["nonebot.adapters.two"],
        "packages": {
            "nonebot-adapter-two": ["nonebot.adapters.two"],
        },
    }
