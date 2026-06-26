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
