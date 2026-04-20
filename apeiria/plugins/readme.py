"""Plugin README resolution helpers."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import distributions
from pathlib import Path

from apeiria.plugins.metadata.module_cache import resolve_module_spec
from apeiria.utils.plugin_introspection import find_loaded_plugin


@dataclass(frozen=True)
class PluginReadme:
    """Resolved plugin README document."""

    module_name: str
    filename: str
    content: str


class PluginReadmeService:
    """Resolve plugin README documents and assets."""

    _README_FILENAMES = (
        "README.md",
        "README_zh-CN.md",
        "README.zh-CN.md",
        "README.rst",
        "README.txt",
    )
    _README_MAX_BYTES = 256 * 1024

    def get_plugin_readme(self, module_name: str) -> PluginReadme:
        candidate = self.resolve_plugin_readme_path(module_name)
        if candidate is None:
            raise FileNotFoundError(module_name)

        try:
            raw = candidate.read_bytes()
        except OSError as exc:
            msg = "failed to read plugin readme"
            raise RuntimeError(msg) from exc

        if len(raw) > self._README_MAX_BYTES:
            msg = "plugin readme is too large"
            raise RuntimeError(msg)

        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            content = raw.decode("utf-8", errors="replace")

        return PluginReadme(
            module_name=module_name,
            filename=candidate.name,
            content=content,
        )

    def get_plugin_readme_asset_path(
        self,
        module_name: str,
        relative_path: str,
    ) -> Path:
        readme_path = self.resolve_plugin_readme_path(module_name)
        if readme_path is None:
            raise FileNotFoundError(module_name)

        normalized_path = relative_path.strip()
        if not normalized_path or "\\" in normalized_path:
            msg = "invalid plugin readme path"
            raise ValueError(msg)

        base_dir = readme_path.parent
        try:
            resolved = (base_dir / normalized_path).resolve()
        except OSError as exc:
            msg = "invalid plugin readme path"
            raise ValueError(msg) from exc

        if not resolved.is_relative_to(base_dir):
            raise PermissionError(normalized_path)
        if not resolved.is_file():
            raise FileNotFoundError(normalized_path)
        return resolved

    def resolve_plugin_readme_path(
        self,
        module_name: str,
        *,
        plugin: object | None = None,
    ) -> Path | None:
        seen: set[Path] = set()

        for candidate in self._iter_module_readme_candidates(
            module_name,
            plugin=plugin,
        ):
            resolved = self._safe_resolve(candidate)
            if resolved is None or resolved in seen:
                continue
            seen.add(resolved)
            if resolved.is_file():
                return resolved

        for candidate in self._iter_distribution_readme_candidates(module_name):
            resolved = self._safe_resolve(candidate)
            if resolved is None or resolved in seen:
                continue
            seen.add(resolved)
            if resolved.is_file():
                return resolved

        return None

    def _iter_module_readme_candidates(
        self,
        module_name: str,
        *,
        plugin: object | None = None,
    ) -> list[Path]:
        plugin = plugin or find_loaded_plugin(module_name)
        module = getattr(plugin, "module", None)
        module_file = getattr(module, "__file__", None)

        roots: list[Path] = []
        if isinstance(module_file, str) and module_file:
            resolved = self._safe_resolve(Path(module_file))
            if resolved is not None:
                roots.extend(self._module_search_roots_from_path(resolved))
        else:
            roots.extend(self._module_search_roots_from_spec(module_name))

        candidates: list[Path] = []
        for root in roots:
            candidates.extend(root / filename for filename in self._README_FILENAMES)
        return candidates

    def _module_search_roots_from_spec(self, module_name: str) -> list[Path]:
        spec = resolve_module_spec(module_name)
        if spec is None:
            return []

        roots: list[Path] = []
        if spec.origin:
            resolved = self._safe_resolve(Path(spec.origin))
            if resolved is not None:
                roots.extend(self._module_search_roots_from_path(resolved))
        for location in spec.submodule_search_locations or ():
            resolved = self._safe_resolve(Path(location))
            if resolved is not None:
                roots.extend(self._ascend_module_roots(resolved))
        return roots

    def _module_search_roots_from_path(self, path: Path) -> list[Path]:
        root = path.parent
        if path.name == "__init__.py":
            root = path.parent
        return self._ascend_module_roots(root)

    def _ascend_module_roots(self, root: Path) -> list[Path]:
        roots: list[Path] = []
        current = root
        while True:
            if current in roots:
                break
            roots.append(current)
            if not (current / "__init__.py").is_file():
                break
            parent = current.parent
            if parent == current:
                break
            current = parent
        return roots

    def _iter_distribution_readme_candidates(self, module_name: str) -> list[Path]:
        top_level = module_name.split(".", 1)[0]
        candidates: list[Path] = []
        for dist in distributions():
            top_level_text = dist.read_text("top_level.txt") or ""
            top_levels = {
                line.strip() for line in top_level_text.splitlines() if line.strip()
            }
            if top_level not in top_levels:
                continue

            readme_files: list[tuple[int, Path]] = []
            for file in dist.files or ():
                if Path(file).name not in self._README_FILENAMES:
                    continue
                try:
                    located = Path(str(dist.locate_file(file)))
                except OSError:
                    continue
                readme_files.append((len(Path(file).parts), located))

            readme_files.sort(key=lambda item: item[0])
            candidates.extend(path for _, path in readme_files)
        return candidates

    def _safe_resolve(self, path: Path) -> Path | None:
        try:
            return path.resolve()
        except OSError:
            return None


plugin_readme_service = PluginReadmeService()
