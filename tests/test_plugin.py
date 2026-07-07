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


def test_resolve_pypi_module_prefers_config_module() -> None:
    from apeiria.plugin.scanner import resolve_pypi_module

    assert (
        resolve_pypi_module("nonebot-plugin-genshinuid", config_module="GenshinUID")
        == "GenshinUID"
    )


def _write_distinfo(
    site_packages, dist_name: str, *, top_level: str | None, record: str | None
) -> None:
    dist_dir = site_packages / f"{dist_name.replace('-', '_')}-1.0.dist-info"
    dist_dir.mkdir(parents=True)
    (dist_dir / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {dist_name}\nVersion: 1.0\n",
        encoding="utf-8",
    )
    if top_level is not None:
        (dist_dir / "top_level.txt").write_text(top_level, encoding="utf-8")
    if record is not None:
        (dist_dir / "RECORD").write_text(record, encoding="utf-8")


def test_resolve_pypi_module_from_distinfo(tmp_path) -> None:
    from apeiria.plugin.scanner import resolve_pypi_module

    _write_distinfo(tmp_path, "demo-pkg", top_level="RealModule\n", record=None)
    assert (
        resolve_pypi_module("demo-pkg>=1.0", venv_site_packages=tmp_path)
        == "RealModule"
    )


def test_resolve_pypi_module_fallback(tmp_path) -> None:
    from apeiria.plugin.scanner import resolve_pypi_module

    assert (
        resolve_pypi_module("nonebot-plugin-status", venv_site_packages=tmp_path)
        == "nonebot_plugin_status"
    )


def test_resolve_pypi_module_distinfo_empty_toplevel(tmp_path) -> None:
    from apeiria.plugin.scanner import resolve_pypi_module

    record = (
        "GenshinUID/__init__.py,sha256=abc,100\n"
        "GenshinUID/client.py,sha256=def,200\n"
        "nonebot_plugin_genshinuid-1.0.dist-info/METADATA,,\n"
        "nonebot_plugin_genshinuid-1.0.dist-info/RECORD,,\n"
    )
    _write_distinfo(
        tmp_path,
        "nonebot-plugin-genshinuid",
        top_level="",
        record=record,
    )
    assert (
        resolve_pypi_module(
            "nonebot-plugin-genshinuid>=5.0.0", venv_site_packages=tmp_path
        )
        == "GenshinUID"
    )
