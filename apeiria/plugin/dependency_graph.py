from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from nonebot.log import logger

if TYPE_CHECKING:
    from nonebot.plugin.model import Plugin


@dataclass
class DepGraph:
    graph: dict[str, set[str]] = field(default_factory=dict)
    reverse: dict[str, set[str]] = field(default_factory=dict)
    nesting: set[tuple[str, str]] = field(default_factory=set)


class _Cache:
    value: DepGraph | None = None


def _normalize_name(name: str) -> str:
    return name.rsplit(".", 1)[-1]


def _parse_require_calls(source: str) -> set[str]:
    result: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return result

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id == "require"):
            continue
        if not node.args:
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            result.add(_normalize_name(arg.value))
        else:
            logger.warning(
                "Skipping dynamic require() call — argument is not a string literal"
            )
    return result


def build_dependency_graph(plugins: list["Plugin"]) -> DepGraph:
    graph: dict[str, set[str]] = {}
    nesting: set[tuple[str, str]] = set()

    for plugin in plugins:
        graph.setdefault(plugin.name, set())

        module_file = getattr(plugin.module, "__file__", None)
        if module_file and module_file.endswith(".py"):
            try:
                with Path(module_file).open(encoding="utf-8") as f:
                    source = f.read()
            except OSError:
                pass
            else:
                for dep in _parse_require_calls(source):
                    graph[plugin.name].add(dep)

        for sub in plugin.sub_plugins:
            graph.setdefault(plugin.name, set()).add(sub.name)
            nesting.add((plugin.name, sub.name))

    reverse: dict[str, set[str]] = {}
    for node, deps in graph.items():
        reverse.setdefault(node, set())
        for dep in deps:
            reverse.setdefault(dep, set()).add(node)

    return DepGraph(graph=graph, reverse=reverse, nesting=nesting)


def get_cached_graph(plugins: list["Plugin"]) -> DepGraph:
    if _Cache.value is None:
        _Cache.value = build_dependency_graph(plugins)
    return _Cache.value
