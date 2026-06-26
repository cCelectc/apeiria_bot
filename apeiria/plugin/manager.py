from __future__ import annotations

from pathlib import Path

import yaml
from nonebot.log import logger

from apeiria.env.sync import sync_apeiria_env


def _read_plugins_yaml() -> dict:
    p = Path(".apeiria/plugins.yaml")
    if not p.exists():
        return {"dirs": [], "packages": {}, "states": {}}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _write_plugins_yaml(data: dict) -> None:
    p = Path(".apeiria/plugins.yaml")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )


def install_plugin(name: str, pkg_requirement: str) -> bool:
    import shutil
    import subprocess

    uv = shutil.which("uv")
    if uv is None:
        logger.error("uv not found")
        return False

    result = subprocess.run(
        [uv, "add", "--directory", ".apeiria", pkg_requirement],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        logger.error("uv add failed: {}", result.stderr.strip())
        return False

    data = _read_plugins_yaml()
    packages = data.setdefault("packages", {})
    packages[name] = pkg_requirement
    states = data.setdefault("states", {})
    states[name] = {"enabled": True}
    _write_plugins_yaml(data)

    sync_apeiria_env()

    from apeiria.config.loader import load_adapters_from_toml

    count = load_adapters_from_toml(".apeiria/pyproject.toml")
    if count:
        logger.info("Registered {} new adapter(s) from plugin install", count)

    return True


def uninstall_plugin(name: str, *, keep_config: bool = False) -> bool:
    import shutil
    import subprocess

    data = _read_plugins_yaml()
    packages = data.get("packages") or {}
    pkg = packages.get(name, "")
    if not pkg:
        logger.warning("Plugin {} not found in plugins.yaml", name)
        return False

    uv = shutil.which("uv")
    if uv is not None:
        subprocess.run(
            [uv, "remove", "--directory", ".apeiria", pkg],
            capture_output=True,
            text=True,
            check=False,
        )

    packages.pop(name, None)
    states = data.get("states") or {}
    states.pop(name, None)
    _write_plugins_yaml(data)

    local_path = Path(f".apeiria/plugins/{name}")
    if local_path.is_dir():
        import shutil as _shutil

        _shutil.rmtree(local_path, ignore_errors=True)

    if not keep_config:
        _remove_plugin_config(name)

    sync_apeiria_env()
    return True


def set_plugin_state(name: str, enabled: bool) -> bool:  # noqa: FBT001
    data = _read_plugins_yaml()
    states = data.setdefault("states", {})
    states[name] = {"enabled": enabled}
    _write_plugins_yaml(data)
    return True


def _remove_plugin_config(name: str) -> None:
    config_path = Path("data/config.yaml")
    if not config_path.exists():
        return
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    plugins = raw.get("plugins")
    if isinstance(plugins, dict):
        plugins.pop(name, None)
        config_path.write_text(
            yaml.dump(raw, allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )
