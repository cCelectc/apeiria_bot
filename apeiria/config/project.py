from __future__ import annotations

from pathlib import Path
from typing import Any

import tomlkit
import tomlkit.items
from nonebot.log import logger

from apeiria.utils.files import atomic_write_text, load_toml_dict
from apeiria.utils.project_context import current_project_root

PROJECT_NONEBOT_DEFAULTS: dict[str, Any] = {
    "localstore_use_cwd": True,
}


class InvalidProjectConfigError(ValueError):
    """Raised when a project TOML file cannot be parsed safely for mutation."""


class ProjectConfigService:
    """Read and mutate project-level TOML configuration."""

    def _project_root(self) -> Path:
        return current_project_root()

    def default_config_path(self) -> Path:
        return self._project_root() / "apeiria.config.toml"

    def read_project_config(self, config_path: Path | None = None) -> dict[str, Any]:
        target = config_path or self.default_config_path()
        return self._read_effective_nonebot_config(target)

    def read_env_config(self) -> dict[str, Any]:
        return self._read_env_nonebot_config()

    def get_project_config_kwargs(
        self,
        config_path: Path | None = None,
    ) -> dict[str, Any]:
        """Return effective NoneBot init kwargs derived from project config files."""
        target = config_path or self.default_config_path()
        return self._read_nonebot_overrides(target)

    def read_raw_project_config(
        self,
        config_path: Path | None = None,
    ) -> dict[str, Any]:
        target = config_path or self.default_config_path()
        return self._load_config(target)

    def read_pyproject_nonebot_config(
        self,
        config_path: Path | None = None,
    ) -> dict[str, list[str]]:
        target = config_path or (self._project_root() / "pyproject.toml")
        data = self._load_config(target)
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
        nonebot_section = self._load_config(target).get("nonebot")
        if isinstance(nonebot_section, dict):
            return dict(nonebot_section)
        return {}

    def read_project_plugin_section_names(
        self,
        config_path: Path | None = None,
    ) -> list[str]:
        target = config_path or self.default_config_path()
        plugins = self._load_config(target).get("plugins")
        if not isinstance(plugins, dict):
            return []
        return [name for name in plugins if isinstance(name, str) and name.strip()]

    def read_project_plugin_module_map(
        self,
        config_path: Path | None = None,
    ) -> dict[str, str]:
        target = config_path or self.default_config_path()
        mappings = self._load_config(target).get("plugin_modules")
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

    def _parse_int(self, value: object, default: int) -> int:
        if isinstance(value, bool):
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                return default
            try:
                return int(normalized)
            except ValueError:
                return default
        return default

    def read_plugin_store_sources_config(
        self,
        config_path: Path | None = None,
    ) -> list[dict[str, object]]:
        """Read configured plugin store sources from project config."""
        target = config_path or self.default_config_path()
        data = self._load_config(target)
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
                    "priority": self._parse_int(
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
        document = self._load_toml_document(target)
        self._set_plugin_module_mapping(document, updates)
        atomic_write_text(target, tomlkit.dumps(document))
        return target

    def read_project_plugin_config(
        self,
        plugin_name: str,
        config_path: Path | None = None,
    ) -> dict[str, Any]:
        target = config_path or self.default_config_path()
        return self._read_plugin_table(self._load_config(target), plugin_name)

    def read_project_nonebot_section_toml(
        self,
        config_path: Path | None = None,
    ) -> str:
        """Render only the `[nonebot]` section for raw-editor style workflows."""
        target = config_path or self.default_config_path()
        section_data = self.read_project_nonebot_section_config(target)
        document = tomlkit.document()
        document["nonebot"] = self._build_table_from_mapping(section_data)
        return tomlkit.dumps(document)

    def write_project_nonebot_section_toml(
        self,
        text: str,
        config_path: Path | None = None,
    ) -> Path:
        """Replace only the `[nonebot]` section while preserving the rest of TOML."""
        target = config_path or self.default_config_path()
        document = self._load_toml_document(target)
        parsed = self._parse_toml_text(text)

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
        parsed = self._parse_toml_text(text)
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
            iter(self._plugin_name_candidates(plugin_name)),
            plugin_name,
        )
        section_data = self.read_project_plugin_config(section_name, target)
        document = tomlkit.document()
        plugins = tomlkit.table()
        plugins[section_name] = self._build_table_from_mapping(section_data)
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
        document = self._load_toml_document(target)
        parsed = self._parse_toml_text(text)
        section_name = next(
            iter(self._plugin_name_candidates(plugin_name)),
            plugin_name,
        )

        section = self._validate_plugin_section_toml(parsed, section_name)

        plugins = document.get("plugins")
        if not isinstance(plugins, tomlkit.items.Table):  # type: ignore[attr-defined]
            plugins = tomlkit.table()
            document["plugins"] = plugins

        if section is None or len(section) == 0:
            if section_name in plugins:
                del plugins[section_name]
            if len(plugins) == 0 and "plugins" in document:
                del document["plugins"]
            self._set_plugin_module_mapping(document, {section_name: None})
            atomic_write_text(target, tomlkit.dumps(document))
            return target

        plugins[section_name] = section
        if module_name is not None:
            self._set_plugin_module_mapping(document, {section_name: module_name})
        atomic_write_text(target, tomlkit.dumps(document))
        return target

    def validate_project_plugin_section_toml(
        self,
        plugin_name: str,
        text: str,
    ) -> None:
        """Validate raw TOML for a single `[plugins.<section>]` block."""
        section_name = next(
            iter(self._plugin_name_candidates(plugin_name)),
            plugin_name,
        )
        parsed = self._parse_toml_text(text)
        self._validate_plugin_section_toml(parsed, section_name)

    def write_project_plugin_section_config(
        self,
        plugin_name: str,
        values: dict[str, object | None],
        config_path: Path | None = None,
        *,
        module_name: str | None = None,
    ) -> Path:
        target = config_path or self.default_config_path()
        document = self._load_toml_document(target)

        plugins = document.get("plugins")
        if not isinstance(plugins, tomlkit.items.Table):  # type: ignore[attr-defined]
            plugins = tomlkit.table()
            document["plugins"] = plugins

        section_name = next(
            iter(self._plugin_name_candidates(plugin_name)),
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
            section[key] = self._dump_toml_value(value)

        if len(section) == 0:
            del plugins[section_name]
            clear_module_mapping = True
        if len(plugins) == 0:
            del document["plugins"]

        if clear_module_mapping:
            self._set_plugin_module_mapping(document, {section_name: None})
        elif len(section) > 0 and module_name is not None:
            self._set_plugin_module_mapping(document, {section_name: module_name})
        atomic_write_text(target, tomlkit.dumps(document))
        return target

    def remove_project_plugin_section(
        self,
        plugin_name: str,
        config_path: Path | None = None,
    ) -> Path:
        """Remove one `[plugins.<section>]` block and related module mapping."""
        target = config_path or self.default_config_path()
        document = self._load_toml_document(target)

        plugins = document.get("plugins")
        if isinstance(plugins, tomlkit.items.Table):  # type: ignore[attr-defined]
            for candidate in self._plugin_name_candidates(plugin_name):
                if candidate in plugins:
                    del plugins[candidate]
            if len(plugins) == 0 and "plugins" in document:
                del document["plugins"]

        self._set_plugin_module_mapping(
            document,
            dict.fromkeys(self._plugin_name_candidates(plugin_name), None),
        )
        atomic_write_text(target, tomlkit.dumps(document))
        return target

    def write_project_nonebot_config(
        self,
        values: dict[str, object | None],
        config_path: Path | None = None,
    ) -> Path:
        target = config_path or self.default_config_path()
        document = self._load_toml_document(target)

        section = document.get("nonebot")
        if not isinstance(section, tomlkit.items.Table):  # type: ignore[attr-defined]
            section = tomlkit.table()
            document["nonebot"] = section

        for key, value in values.items():
            if value is None:
                if key in section:
                    del section[key]
                continue
            section[key] = self._dump_toml_value(value)

        if len(section) == 0:
            del document["nonebot"]

        atomic_write_text(target, tomlkit.dumps(document))
        return target

    def _load_config(self, config_path: Path) -> dict[str, Any]:
        return load_toml_dict(
            config_path,
            logger=logger,
            missing_dependency_message=(
                f"Skip loading {config_path.name}: tomllib/tomli is unavailable"
            ),
        )

    def _normalize_config(self, data: dict[str, Any]) -> dict[str, Any]:
        nonebot_config = data.get("nonebot")
        if isinstance(nonebot_config, dict):
            return dict(nonebot_config)
        return data

    def _read_nonebot_overrides(self, config_path: Path) -> dict[str, Any]:
        data = self._load_config(config_path)
        config = dict(PROJECT_NONEBOT_DEFAULTS)
        config.update(self._normalize_config(data))
        return config

    def _read_effective_nonebot_config(self, config_path: Path) -> dict[str, Any]:
        from nonebot.compat import model_dump
        from nonebot.config import Config, Env

        env = Env()
        env_file = f".env.{env.environment}"
        config = Config(
            **self._read_nonebot_overrides(config_path),
            _env_file=(".env", env_file),
        )
        return dict(model_dump(config))

    def _read_env_nonebot_config(self) -> dict[str, Any]:
        from nonebot.compat import model_dump
        from nonebot.config import Config, Env

        env = Env()
        env_file = f".env.{env.environment}"
        config = Config(_env_file=(".env", env_file))
        return dict(model_dump(config))

    def _plugin_name_candidates(self, plugin_name: str) -> tuple[str, ...]:
        stripped = plugin_name.strip()
        if not stripped:
            return ()

        candidates = [stripped]
        normalized = stripped.replace("-", "_")
        if normalized not in candidates:
            candidates.append(normalized)
        dashed = stripped.replace("_", "-")
        if dashed not in candidates:
            candidates.append(dashed)
        return tuple(candidates)

    def _read_plugin_table(
        self,
        data: dict[str, Any],
        plugin_name: str,
    ) -> dict[str, Any]:
        plugins = data.get("plugins")
        if not isinstance(plugins, dict):
            return {}

        for candidate in self._plugin_name_candidates(plugin_name):
            plugin_config = plugins.get(candidate)
            if isinstance(plugin_config, dict):
                return dict(plugin_config)
        return {}

    def _load_toml_document(self, config_path: Path) -> tomlkit.TOMLDocument:
        if not config_path.is_file():
            return tomlkit.document()
        try:
            return tomlkit.parse(config_path.read_text(encoding="utf-8"))
        except OSError as exc:
            msg = f"cannot read {config_path.name}: {exc}"
            raise InvalidProjectConfigError(msg) from exc
        except Exception as exc:
            msg = f"{config_path.name} contains invalid TOML: {exc}"
            raise InvalidProjectConfigError(msg) from exc

    def _dump_toml_value(self, value: object) -> tomlkit.items.Item:  # type: ignore[attr-defined]
        return tomlkit.item(self._normalize_toml_value(value))  # type: ignore[call-overload]

    def _normalize_toml_value(self, value: object) -> object:
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, set):
            return [self._normalize_toml_value(item) for item in sorted(value)]
        if isinstance(value, list | tuple):
            return [self._normalize_toml_value(item) for item in value]
        if isinstance(value, dict):
            return {
                str(key): self._normalize_toml_value(item)
                for key, item in value.items()
            }
        return value

    def _build_table_from_mapping(
        self,
        values: dict[str, Any],
    ) -> tomlkit.items.Table:  # type: ignore[attr-defined]
        table = tomlkit.table()
        for key, value in values.items():
            table[str(key)] = self._dump_toml_value(value)
        return table

    def _parse_toml_text(self, text: str) -> tomlkit.TOMLDocument:
        normalized = text.strip()
        if not normalized:
            return tomlkit.document()
        if not normalized.endswith("\n"):
            normalized = f"{normalized}\n"
        return tomlkit.parse(normalized)

    def _validate_plugin_section_toml(
        self,
        parsed: dict[str, object],
        section_name: str,
    ) -> tomlkit.items.Table | None:  # type: ignore[attr-defined]
        if any(key != "plugins" for key in parsed):
            msg = "raw editor only accepts the [plugins.<section>] section"
            raise ValueError(msg)

        plugins_section = parsed.get("plugins")
        if plugins_section is None:
            return None
        if not isinstance(plugins_section, tomlkit.items.Table):  # type: ignore[attr-defined]
            msg = "raw editor expects a [plugins.<section>] table"
            raise TypeError(msg)

        if any(key != section_name for key in plugins_section):
            msg = f"raw editor only accepts the [plugins.{section_name}] section"
            raise ValueError(msg)
        section = plugins_section.get(section_name)
        if section is not None and not isinstance(section, tomlkit.items.Table):  # type: ignore[attr-defined]
            msg = f"raw editor expects [plugins.{section_name}] to be a table"
            raise ValueError(msg)
        return section

    def _set_plugin_module_mapping(
        self,
        document: tomlkit.TOMLDocument,
        updates: dict[str, str | None],
    ) -> None:
        plugin_modules = document.get("plugin_modules")
        if not isinstance(plugin_modules, tomlkit.items.Table):  # type: ignore[attr-defined]
            plugin_modules = tomlkit.table()
            document["plugin_modules"] = plugin_modules

        for section, module_name in updates.items():
            normalized_section = next(
                iter(self._plugin_name_candidates(section)),
                section,
            )
            if not normalized_section:
                continue
            normalized_module = (
                module_name.strip() if isinstance(module_name, str) else ""
            )
            if normalized_module:
                plugin_modules[normalized_section] = normalized_module
            elif normalized_section in plugin_modules:
                del plugin_modules[normalized_section]

        if len(plugin_modules) == 0 and "plugin_modules" in document:
            del document["plugin_modules"]


project_config_service = ProjectConfigService()
