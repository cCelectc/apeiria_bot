from __future__ import annotations


def test_scanner_returns_builtins(tmp_path, monkeypatch) -> None:
    from apeiria.plugin.scanner import scan_plugins

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".apeiria").mkdir()
    (tmp_path / ".apeiria" / "plugins.yaml").write_text(
        "dirs: []\npackages: {}\nstates: {}\n"
    )

    plugins = scan_plugins()
    names = [p.name for p in plugins]
    assert "admin" in names
    assert "help" in names


def test_set_plugin_state(tmp_path, monkeypatch) -> None:
    from apeiria.plugin.manager import set_plugin_state
    from apeiria.plugin.scanner import scan_plugins

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".apeiria").mkdir()
    yaml_path = tmp_path / ".apeiria" / "plugins.yaml"
    yaml_path.write_text("dirs: []\npackages: {}\nstates: {}\n")

    set_plugin_state("admin", enabled=False)
    plugins = scan_plugins()
    admin = next(p for p in plugins if p.name == "admin")
    assert not admin.enabled


def test_scan_returns_sorted(tmp_path, monkeypatch) -> None:
    from apeiria.plugin.scanner import scan_plugins

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".apeiria").mkdir()
    (tmp_path / ".apeiria" / "plugins.yaml").write_text(
        "dirs: []\npackages: {}\nstates: {}\n"
    )

    plugins = scan_plugins()
    assert len(plugins) >= 5


def test_requirement_to_module_strips_version() -> None:
    from apeiria.plugin.scanner import requirement_to_module

    assert requirement_to_module("nonebot-plugin-status") == "nonebot_plugin_status"
    assert (
        requirement_to_module("nonebot-plugin-status>=0.9.0") == "nonebot_plugin_status"
    )
    assert (
        requirement_to_module("nonebot-plugin-foo[extra]>=1.0") == "nonebot_plugin_foo"
    )
    assert requirement_to_module("nonebot_plugin_foo") == "nonebot_plugin_foo"


def test_manifest_module_candidate_by_source() -> None:
    from apeiria.plugin.scanner import PluginManifest, manifest_module_candidate

    pypi = PluginManifest(
        name="服务器状态查看",
        path_or_module="nonebot-plugin-status>=0.9.0",
        enabled=True,
        source="pypi",
    )
    assert manifest_module_candidate(pypi) == "nonebot_plugin_status"

    builtin = PluginManifest(
        name="admin",
        path_or_module="apeiria.builtin_plugins.admin",
        enabled=True,
        source="builtin",
    )
    assert manifest_module_candidate(builtin) == "admin"

    local = PluginManifest(
        name="myplugin",
        path_or_module="/abs/path/myplugin",
        enabled=True,
        source="local",
    )
    assert manifest_module_candidate(local) == "myplugin"
