"""Configuration bootstrap phase for NoneBot init and TOML loading."""

from typing import Any, cast

import nonebot

from apeiria.config import driver_config_service, project_config_service


def resolve_driver_kwargs(config_kwargs: dict[str, object]) -> dict[str, object]:
    """Resolve driver kwargs with the runtime precedence used by the project.

    Project-managed driver config wins over values loaded from config files.
    If the project does not pin a driver, fall back to env-derived config so
    existing NoneBot behavior remains intact.
    """
    project_driver_kwargs = driver_config_service.get_project_driver_kwargs()

    if project_driver_kwargs.get("driver"):
        config_kwargs.pop("driver", None)
        return cast("dict[str, object]", project_driver_kwargs)
    if "driver" in config_kwargs:
        return {}

    env_config = project_config_service.read_env_config()
    env_driver = env_config.get("driver")
    if isinstance(env_driver, str) and env_driver:
        return {"driver": env_driver}
    return {}


def run_config_phase() -> None:
    config_kwargs = project_config_service.get_project_config_kwargs()
    driver_kwargs = resolve_driver_kwargs(config_kwargs)

    nonebot.init(
        **cast("dict[str, Any]", config_kwargs),
        **cast("dict[str, Any]", driver_kwargs),
    )
    nonebot.load_from_toml(
        str(project_config_service.default_config_path().with_name("pyproject.toml"))
    )
