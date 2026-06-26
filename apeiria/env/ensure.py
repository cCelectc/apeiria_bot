from __future__ import annotations

from pathlib import Path

from nonebot.log import logger

_TEMPLATE_PYPROJECT = """[project]
name = "apeiria-extensions"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[tool.uv]
package = false

[tool.nonebot.plugins]
"""

_TEMPLATE_PLUGINS_YAML = """dirs:
  - ".apeiria/plugins"
packages: {}
states: {}
"""


def ensure_apeiria_env() -> Path:
    base = Path(".apeiria")
    base.mkdir(parents=True, exist_ok=True)

    plugins_dir = base / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)

    pyproject_path = base / "pyproject.toml"
    if not pyproject_path.exists():
        pyproject_path.write_text(_TEMPLATE_PYPROJECT, encoding="utf-8")
        logger.info("Created {}", pyproject_path)

    plugins_yaml_path = base / "plugins.yaml"
    if not plugins_yaml_path.exists():
        plugins_yaml_path.write_text(_TEMPLATE_PLUGINS_YAML, encoding="utf-8")
        logger.info("Created {}", plugins_yaml_path)

    return base
