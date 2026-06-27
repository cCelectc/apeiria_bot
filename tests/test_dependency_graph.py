from __future__ import annotations

from types import ModuleType
from unittest.mock import MagicMock


def _make_module(name: str, filepath: str) -> ModuleType:
    mod = ModuleType(name)
    mod.__file__ = filepath
    mod.__name__ = name
    return mod


def _make_plugin(
    name: str,
    module: ModuleType,
    metadata=None,
    sub_plugins: set | None = None,
    parent=None,
):
    from nonebot.plugin.model import Plugin

    return Plugin(
        name=name,
        module=module,
        module_name=module.__name__,
        manager=MagicMock(),
        metadata=metadata,
        sub_plugins=sub_plugins or set(),
        parent_plugin=parent,
    )


class TestBuildDependencyGraph:
    def test_require_constant_parsed(self, tmp_path) -> None:
        from apeiria.plugin.dependency_graph import build_dependency_graph

        source = """
from nonebot import require
require("nonebot_plugin_alconna")
"""
        f = tmp_path / "admin.py"
        f.write_text(source, encoding="utf-8")
        plugin = _make_plugin("admin", _make_module("admin", str(f)))

        graph = build_dependency_graph([plugin])
        assert "nonebot_plugin_alconna" in graph.graph["admin"]

    def test_require_dotted_module_normalized(self, tmp_path) -> None:
        from apeiria.plugin.dependency_graph import build_dependency_graph

        source = """
from nonebot import require
require("nonebot.plugin.alconna")
"""
        f = tmp_path / "admin.py"
        f.write_text(source, encoding="utf-8")
        plugin = _make_plugin("admin", _make_module("admin", str(f)))

        graph = build_dependency_graph([plugin])
        assert "alconna" in graph.graph["admin"]

    def test_require_variable_skipped(self, tmp_path) -> None:
        from apeiria.plugin.dependency_graph import build_dependency_graph

        source = """
from nonebot import require
dep = "some_plugin"
require(dep)
"""
        f = tmp_path / "admin.py"
        f.write_text(source, encoding="utf-8")
        plugin = _make_plugin("admin", _make_module("admin", str(f)))

        graph = build_dependency_graph([plugin])
        assert graph.graph.get("admin", set()) == set()

    def test_multiple_require_in_one_file(self, tmp_path) -> None:
        from apeiria.plugin.dependency_graph import build_dependency_graph

        source = """
from nonebot import require
require("nonebot_plugin_alconna")
require("nonebot_plugin_foo")
"""
        f = tmp_path / "admin.py"
        f.write_text(source, encoding="utf-8")
        plugin = _make_plugin("admin", _make_module("admin", str(f)))

        graph = build_dependency_graph([plugin])
        assert graph.graph["admin"] == {"nonebot_plugin_alconna", "nonebot_plugin_foo"}

    def test_no_require_no_edges(self, tmp_path) -> None:
        from apeiria.plugin.dependency_graph import build_dependency_graph

        source = "x = 1"
        f = tmp_path / "admin.py"
        f.write_text(source, encoding="utf-8")
        plugin = _make_plugin("admin", _make_module("admin", str(f)))

        graph = build_dependency_graph([plugin])
        assert graph.graph.get("admin", set()) == set()

    def test_reverse_graph_built(self, tmp_path) -> None:
        from apeiria.plugin.dependency_graph import build_dependency_graph

        a_source = """
from nonebot import require
require("dep_a")
"""
        fa = tmp_path / "plugin_a.py"
        fa.write_text(a_source, encoding="utf-8")
        fb = tmp_path / "dep_a.py"
        fb.write_text("x = 1", encoding="utf-8")
        a = _make_plugin("plugin_a", _make_module("plugin_a", str(fa)))
        b = _make_plugin("dep_a", _make_module("dep_a", str(fb)))

        graph = build_dependency_graph([a, b])
        assert graph.graph["plugin_a"] == {"dep_a"}
        assert graph.reverse["dep_a"] == {"plugin_a"}

    def test_nesting_creates_edges(self, tmp_path) -> None:
        from apeiria.plugin.dependency_graph import build_dependency_graph

        fp = tmp_path / "parent.py"
        fp.write_text("x = 1", encoding="utf-8")
        fc = tmp_path / "child.py"
        fc.write_text("y = 2", encoding="utf-8")
        child = _make_plugin("child", _make_module("parent.child", str(fc)))
        parent = _make_plugin(
            "parent", _make_module("parent", str(fp)), sub_plugins={child}
        )

        graph = build_dependency_graph([parent, child])
        assert "child" in graph.graph["parent"]
        assert "parent" in graph.reverse["child"]
        assert ("parent", "child") in graph.nesting

    def test_no_file_skips_ast(self) -> None:
        from apeiria.plugin.dependency_graph import build_dependency_graph

        mod = ModuleType("no_file_mod")
        mod.__file__ = None
        plugin = _make_plugin("no_file", mod)

        graph = build_dependency_graph([plugin])
        assert graph.graph.get("no_file", set()) == set()

    def test_non_py_file_skips_ast(self) -> None:
        from apeiria.plugin.dependency_graph import build_dependency_graph

        mod = _make_module("compiled", "/fake/path.so")
        plugin = _make_plugin("compiled", mod)

        graph = build_dependency_graph([plugin])
        assert graph.graph.get("compiled", set()) == set()
