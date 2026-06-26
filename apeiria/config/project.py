from __future__ import annotations

from typing import TYPE_CHECKING, Any

import tomlkit
import tomlkit.items

if TYPE_CHECKING:
    from pathlib import Path

from apeiria.config.project_sections import (
    InvalidProjectConfigError,  # noqa: F401  # re-exported for __init__.py
    _build_table_from_mapping,
    _dump_toml_value,
    _load_config,
    _load_toml_document,
    _parse_int,
    _parse_toml_text,
    _plugin_name_candidates,
    _read_effective_nonebot_config,
    _read_env_nonebot_config,
    _read_plugin_table,
    _set_plugin_module_mapping,
    _validate_plugin_section_toml,
)
from apeiria.utils.files import atomic_write_text
from apeiria.utils.project_context import current_project_root

PROJECT_NONEBOT_DEFAULTS: dict[str, Any] = {
    "localstore_use_cwd": True,
}


class ProjectConfigService:
    """Read and mutate project-level TOML configuration."""

    def _project_root(self) -> Path:
        return current_project_root()

    def default_config_path(self) -> Path:
        return self._project_root() / "apeiria.config.toml"

    def read_project_config(self, config_path: Path | None = None) -> dict[str, Any]:
        target = config_path or self.default_config_path()
        return _read_effective_nonebot_config(target, PROJECT_NONEBOT_DEFAULTS)

    def read_env_config(self) -> dict[str, Any]:
        return _read_env_nonebot_config()

    def get_project_config_kwargs(
        self,
        config_path: Path | None = None,
    ) -> dict[str, Any]:
        """Return effective NoneBot init kwargs derived from project config files."""
        target = config_path or self.default_config_path()
        from apeiria.config.project_sections import _read_nonebot_overrides

        return _read_nonebot_overrides(target, PROJECT_NONEBOT_DEFAULTS)

    def read_raw_project_config(
        self,
        config_path: Path | None = None,
    ) -> dict[str, Any]:
        target = config_path or self.default_config_path()
        return _load_config(target)

    def read_pyproject_nonebot_config(
        self,
        config_path: Path | None = None,
    ) -> dict[str, list[str]]:
        target = config_path or (self._project_root() / "pyproject.toml")
        data = _load_config(target)
        nonebot_config = data.get("tool", {}).get("nonebot", {})
        if not isinstance(nonebot_config, dict):
            return {"plugins": [], "plugin_dirs": []}

        raw_plugins = nonebot_config.get("plugins", {})
        plugins: list[str]
        if isinstance(raw_plugins, list):
            plugins = [item for item in raw_plugins if isinstance(item, str)]
        elif isinstance(raw_plugins, dict):
            plugins = [
                item
                for item in dict.values(raw_plugins)
                if isinstance(item, list)
                for item in item
                if isinstance(item, str)
            ]
        else:
            plugins = []

        raw_plugin_dirs = nonebot_config.get("plugin_dirs", [])
        plugin_dirs = (
            [item for item in raw_plugin_dirs if isinstance(item, str)]
            if isinstance(raw_plugin_dirs, list)
            else []
        )
        return {"plugins": plugins, "plugin_dirs": plugin_dirs}

    def read_project_nonebot_section_config(
        self,
        config_path: Path | None = None,
    ) -> dict[str, Any]:
        target = config_path or self.default_config_path()
        nonebot_section = _load_config(target).get("nonebot")
        if isinstance(nonebot_section, dict):
            return dict(nonebot_section)
        return {}

    def read_project_plugin_section_names(
        self,
        config_path: Path | None = None,
    ) -> list[str]:
        target = config_path or self.default_config_path()
        plugins = _load_config(target).get("plugins")
        if not isinstance(plugins, dict):
            return []
        return [name for name in plugins if isinstance(name, str) and name.strip()]

    def read_project_plugin_module_map(
        self,
        config_path: Path | None = None,
    ) -> dict[str, str]:
        target = config_path or self.default_config_path()
        mappings = _load_config(target).get("plugin_modules")
        if not isinstance(mappings, dict):
            return {}
        return {
            section: module_name
            for section, module_name in mappings.items()
            if isinstance(section, str)
            and section.strip()
            and isinstance(module_name, str)
            and module_name.strip()
        }

    def read_plugin_store_sources_config(
        self,
        config_path: Path | None = None,
    ) -> list[dict[str, object]]:
        """Read configured plugin store sources from project config."""
        target = config_path or self.default_config_path()
        data = _load_config(target)
        plugin_store = data.get("plugin_store")
        if not isinstance(plugin_store, dict):
            return []
        raw_sources = plugin_store.get("sources")
        if not isinstance(raw_sources, dict):
            return []

        sources: list[dict[str, object]] = []
        for source_id, raw_source in raw_sources.items():
            if not isinstance(source_id, str) or not source_id.strip():
                continue
            if not isinstance(raw_source, dict):
                continue
            sources.append(
                {
                    "source_id": source_id.strip(),
                    "kind": raw_source.get("kind", ""),
                    "label": raw_source.get("label", source_id.strip()),
                    "base_url": raw_source.get("base_url", ""),
                    "enabled": raw_source.get("enabled", True),
                    "priority": _parse_int(
                        raw_source.get("priority", 100),
                        100,
                    ),
                }
            )
        return sources

    def write_project_plugin_module_map(
        self,
        updates: dict[str, str | None],
        config_path: Path | None = None,
    ) -> Path:
        target = config_path or self.default_config_path()
        document = _load_toml_document(target)
        _set_plugin_module_mapping(document, updates)
        atomic_write_text(target, tomlkit.dumps(document))
        return target

    def read_project_plugin_config(
        self,
        plugin_name: str,
        config_path: Path | None = None,
    ) -> dict[str, Any]:
        target = config_path or self.default_config_path()
        return _read_plugin_table(_load_config(target), plugin_name)

    def read_project_nonebot_section_toml(
        self,
        config_path: Path | None = None,
    ) -> str:
        """Render only the `[nonebot]` section for raw-editor style workflows."""
        target = config_path or self.default_config_path()
        section_data = self.read_project_nonebot_section_config(target)
        document = tomlkit.document()
        document["nonebot"] = _build_table_from_mapping(section_data)
        return tomlkit.dumps(document)

    def write_project_nonebot_section_toml(
        self,
        text: str,
        config_path: Path | None = None,
    ) -> Path:
        """Replace only the `[nonebot]` section while preserving the rest of TOML."""
        target = config_path or self.default_config_path()
        document = _load_toml_document(target)
        parsed = _parse_toml_text(text)

        if any(key != "nonebot" for key in parsed):
            msg = "raw editor only accepts the [nonebot] section"
            raise ValueError(msg)

        section = parsed.get("nonebot")
        if section is None:
            if "nonebot" in document:
                del document["nonebot"]
        elif not isinstance(section, tomlkit.items.Table):  # type: ignore[attr-defined]
            msg = "raw editor expects a [nonebot] table"
            raise ValueError(msg)
        elif len(section) == 0:
            if "nonebot" in document:
                del document["nonebot"]
        else:
            document["nonebot"] = section

        atomic_write_text(target, tomlkit.dumps(document))
        return target

    def validate_project_nonebot_section_toml(self, text: str) -> None:
        """Validate raw TOML for the `[nonebot]` section without writing."""
        parsed = _parse_toml_text(text)
        if any(key != "nonebot" for key in parsed):
            msg = "raw editor only accepts the [nonebot] section"
            raise ValueError(msg)

        section = parsed.get("nonebot")
        if section is None:
            return
        if not isinstance(section, tomlkit.items.Table):  # type: ignore[attr-defined]
            msg = "raw editor expects a [nonebot] table"
            raise TypeError(msg)

    def read_project_plugin_section_toml(
        self,
        plugin_name: str,
        config_path: Path | None = None,
    ) -> str:
        target = config_path or self.default_config_path()
        section_name = next(
            iter(_plugin_name_candidates(plugin_name)),
            plugin_name,
        )
        section_data = self.read_project_plugin_config(section_name, target)
        document = tomlkit.document()
        plugins = tomlkit.table()
        plugins[section_name] = _build_table_from_mapping(section_data)
        document["plugins"] = plugins
        return tomlkit.dumps(document)

    def write_project_plugin_section_toml(
        self,
        plugin_name: str,
        text: str,
        config_path: Path | None = None,
        *,
        module_name: str | None = None,
    ) -> Path:
        """Replace one `[plugins.<section>]` block without rewriting unrelated TOML."""
        target = config_path or self.default_config_path()
        document = _load_toml_document(target)
        parsed = _parse_toml_text(text)
        section_name = next(
            iter(_plugin_name_candidates(plugin_name)),
            plugin_name,
        )

        section = _validate_plugin_section_toml(parsed, section_name)

        plugins = document.get("plugins")
        if not isinstance(plugins, tomlkit.items.Table):  # type: ignore[attr-defined]
            plugins = tomlkit.table()
            document["plugins"] = plugins

        if section is None or len(section) == 0:
            if section_name in plugins:
                del plugins[section_name]
            if len(plugins) == 0 and "plugins" in document:
                del document["plugins"]
            _set_plugin_module_mapping(document, {section_name: None})
            atomic_write_text(target, tomlkit.dumps(document))
            return target

        plugins[section_name] = section
        if module_name is not None:
            _set_plugin_module_mapping(document, {section_name: module_name})
        atomic_write_text(target, tomlkit.dumps(document))
        return target

    def validate_project_plugin_section_toml(
        self,
        plugin_name: str,
        text: str,
    ) -> None:
        """Validate raw TOML for a single `[plugins.<section>]` block."""
        section_name = next(
            iter(_plugin_name_candidates(plugin_name)),
            plugin_name,
        )
        parsed = _parse_toml_text(text)
        _validate_plugin_section_toml(parsed, section_name)

    def write_project_plugin_section_config(
        self,
        plugin_name: str,
        values: dict[str, object | None],
        config_path: Path | None = None,
        *,
        module_name: str | None = None,
    ) -> Path:
        target = config_path or self.default_config_path()
        document = _load_toml_document(target)

        plugins = document.get("plugins")
        if not isinstance(plugins, tomlkit.items.Table):  # type: ignore[attr-defined]
            plugins = tomlkit.table()
            document["plugins"] = plugins

        section_name = next(
            iter(_plugin_name_candidates(plugin_name)),
            plugin_name,
        )
        section = plugins.get(section_name)
        if not isinstance(section, tomlkit.items.Table):  # type: ignore[attr-defined]
            section = tomlkit.table()
            plugins[section_name] = section

        clear_module_mapping = False
        for key, value in values.items():
            if value is None:
                if key in section:
                    del section[key]
                continue
            section[key] = _dump_toml_value(value)

        if len(section) == 0:
            del plugins[section_name]
            clear_module_mapping = True
        if len(plugins) == 0:
            del document["plugins"]

        if clear_module_mapping:
            _set_plugin_module_mapping(document, {section_name: None})
        elif len(section) > 0 and module_name is not None:
            _set_plugin_module_mapping(document, {section_name: module_name})
        atomic_write_text(target, tomlkit.dumps(document))
        return target

    def remove_project_plugin_section(
        self,
        plugin_name: str,
        config_path: Path | None = None,
    ) -> Path:
        """Remove one `[plugins.<section>]` block and related module mapping."""
        target = config_path or self.default_config_path()
        document = _load_toml_document(target)

        plugins = document.get("plugins")
        if isinstance(plugins, tomlkit.items.Table):  # type: ignore[attr-defined]
            for candidate in _plugin_name_candidates(plugin_name):
                if candidate in plugins:
                    del plugins[candidate]
            if len(plugins) == 0 and "plugins" in document:
                del document["plugins"]

        _set_plugin_module_mapping(
            document,
            dict.fromkeys(_plugin_name_candidates(plugin_name), None),
        )
        atomic_write_text(target, tomlkit.dumps(document))
        return target

    def write_project_nonebot_config(
        self,
        values: dict[str, object | None],
        config_path: Path | None = None,
    ) -> Path:
        target = config_path or self.default_config_path()
        document = _load_toml_document(target)

        section = document.get("nonebot")
        if not isinstance(section, tomlkit.items.Table):  # type: ignore[attr-defined]
            section = tomlkit.table()
            document["nonebot"] = section

        for key, value in values.items():
            if value is None:
                if key in section:
                    del section[key]
                continue
            section[key] = _dump_toml_value(value)

        if len(section) == 0:
            del document["nonebot"]

        atomic_write_text(target, tomlkit.dumps(document))
        return target


project_config_service = ProjectConfigService()
