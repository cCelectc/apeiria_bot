from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml
from nonebot.log import logger

from apeiria.env.sync import sync_apeiria_env

_ADAPTERS_TOML = Path(".apeiria/pyproject.toml")
_ADAPTERS_SECTION = "[tool.nonebot.adapters]"


def _read_adapters_yaml() -> dict:
    p = Path(".apeiria/adapters.yaml")
    if not p.exists():
        return {"packages": {}, "states": {}}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _write_adapters_yaml(data: dict) -> None:
    p = Path(".apeiria/adapters.yaml")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )


def _toml_add_adapter(name: str, module_name: str) -> None:
    lines = _ADAPTERS_TOML.read_text(encoding="utf-8").splitlines()

    section_idx = None
    for i, line in enumerate(lines):
        if line.strip() == _ADAPTERS_SECTION:
            section_idx = i
            break

    entry = f'"{name}" = [{{ name = "{name}", module_name = "{module_name}" }}]'

    if section_idx is not None:
        lines[section_idx + 1 : section_idx + 1] = [entry]
    else:
        if lines and lines[-1] != "":
            lines.append("")
        lines.append(_ADAPTERS_SECTION)
        lines.append(entry)

    _ADAPTERS_TOML.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _toml_remove_adapter(name: str) -> None:
    if not _ADAPTERS_TOML.exists():
        return
    lines = _ADAPTERS_TOML.read_text(encoding="utf-8").splitlines()
    prefix = f'"{name}" = '
    filtered = [line for line in lines if not line.strip().startswith(prefix)]
    _ADAPTERS_TOML.write_text("\n".join(filtered) + "\n", encoding="utf-8")


def install_adapter(
    name: str, pkg_requirement: str, module_name: str
) -> tuple[bool, str]:
    uv = shutil.which("uv")
    if uv is None:
        return False, "uv not found"

    try:
        result = subprocess.run(
            [uv, "add", "--directory", ".apeiria", pkg_requirement],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return False, "安装超时（120s），请检查网络或包大小"
    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip()
        logger.error("uv add failed: {}", err)
        return False, err

    _toml_add_adapter(name, module_name)

    data = _read_adapters_yaml()
    packages = data.setdefault("packages", {})
    packages[name] = pkg_requirement
    states = data.setdefault("states", {})
    states[name] = {"enabled": True}
    _write_adapters_yaml(data)

    sync_apeiria_env()
    return True, "安装成功"


def uninstall_adapter(name: str, *, keep_config: bool = False) -> bool:
    data = _read_adapters_yaml()
    packages = data.get("packages") or {}
    pkg = packages.get(name, "")
    if not pkg:
        logger.warning("Adapter {} not found in adapters.yaml", name)
        return False

    uv = shutil.which("uv")
    if uv is not None:
        subprocess.run(
            [uv, "remove", "--directory", ".apeiria", pkg],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )

    _toml_remove_adapter(name)

    packages.pop(name, None)
    states = data.get("states") or {}
    states.pop(name, None)
    _write_adapters_yaml(data)

    if not keep_config:
        _remove_adapter_config(name)

    sync_apeiria_env()
    return True


def set_adapter_state(name: str, enabled: bool) -> bool:  # noqa: FBT001
    data = _read_adapters_yaml()
    states = data.setdefault("states", {})
    states[name] = {"enabled": enabled}
    _write_adapters_yaml(data)
    return True


def _remove_adapter_config(name: str) -> None:
    config_path = Path("data/config.yaml")
    if not config_path.exists():
        return
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    adapters = raw.get("adapters")
    if isinstance(adapters, dict):
        adapters.pop(name, None)
        config_path.write_text(
            yaml.dump(raw, allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )
