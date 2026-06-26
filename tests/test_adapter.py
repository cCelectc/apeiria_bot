from __future__ import annotations

from pathlib import Path


def test_ensure_creates_adapters_yaml(tmp_path, monkeypatch) -> None:
    from apeiria.env.ensure import ensure_apeiria_env

    monkeypatch.chdir(tmp_path)
    base = ensure_apeiria_env()
    adapters_yaml = base / "adapters.yaml"
    assert adapters_yaml.is_file()


def test_scan_adapters_returns_builtins(tmp_path, monkeypatch) -> None:
    from apeiria.plugin.adapter_scanner import scan_adapters

    monkeypatch.chdir(tmp_path)
    _setup_builtin_toml(tmp_path)
    _setup_adapters_yaml(tmp_path, packages={}, states={})

    adapters = scan_adapters()
    names = [a.name for a in adapters]
    assert "OneBot V11" in names


def test_scan_adapters_reads_state_disabled(tmp_path, monkeypatch) -> None:
    from apeiria.plugin.adapter_scanner import scan_adapters

    monkeypatch.chdir(tmp_path)
    _setup_builtin_toml(tmp_path)
    _setup_adapters_yaml(
        tmp_path,
        packages={},
        states={"OneBot V11": {"enabled": False}},
    )

    adapters = scan_adapters()
    onebot = next(a for a in adapters if a.name == "OneBot V11")
    assert not onebot.enabled


def test_scan_adapters_reads_state_default_enabled(tmp_path, monkeypatch) -> None:
    from apeiria.plugin.adapter_scanner import scan_adapters

    monkeypatch.chdir(tmp_path)
    _setup_builtin_toml(tmp_path)
    _setup_adapters_yaml(tmp_path, packages={}, states={})

    adapters = scan_adapters()
    onebot = next(a for a in adapters if a.name == "OneBot V11")
    assert onebot.enabled


def test_scan_adapters_pypi_from_toml(tmp_path, monkeypatch) -> None:
    from apeiria.plugin.adapter_scanner import scan_adapters

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".apeiria").mkdir()
    _setup_builtin_toml(tmp_path)
    _setup_pypi_toml(
        tmp_path,
        {"MyAdapter": [{"name": "MyAdapter", "module_name": "my.module"}]},
    )
    _setup_adapters_yaml(
        tmp_path,
        packages={"MyAdapter": "my-pkg"},
        states={"MyAdapter": {"enabled": True}},
    )

    adapters = scan_adapters()
    pypi_adapters = [a for a in adapters if a.source == "pypi"]
    assert len(pypi_adapters) == 1
    assert pypi_adapters[0].name == "MyAdapter"
    assert pypi_adapters[0].module_name == "my.module"
    assert pypi_adapters[0].enabled


def test_scan_adapters_pypi_disabled(tmp_path, monkeypatch) -> None:
    from apeiria.plugin.adapter_scanner import scan_adapters

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".apeiria").mkdir()
    _setup_pypi_toml(
        tmp_path,
        {"Pkg": [{"name": "PkgAdapter", "module_name": "pkg.module"}]},
    )
    _setup_adapters_yaml(
        tmp_path,
        packages={},
        states={"PkgAdapter": {"enabled": False}},
    )

    adapters = scan_adapters()
    pypi = next(a for a in adapters if a.source == "pypi")
    assert not pypi.enabled


def test_set_adapter_state_persists(tmp_path, monkeypatch) -> None:
    from apeiria.plugin.adapter_manager import set_adapter_state
    from apeiria.plugin.adapter_scanner import scan_adapters

    monkeypatch.chdir(tmp_path)
    _setup_builtin_toml(tmp_path)
    _setup_adapters_yaml(tmp_path, packages={}, states={})

    set_adapter_state("OneBot V11", enabled=False)
    adapters = scan_adapters()
    onebot = next(a for a in adapters if a.name == "OneBot V11")
    assert not onebot.enabled


def test_toml_add_adapter(tmp_path, monkeypatch) -> None:
    from apeiria.plugin.adapter_manager import _toml_add_adapter

    monkeypatch.chdir(tmp_path)
    _setup_apeiria_toml(tmp_path)

    _toml_add_adapter("TestAdapter", "test.module")
    content = (tmp_path / ".apeiria" / "pyproject.toml").read_text("utf-8")
    assert "TestAdapter" in content
    assert "test.module" in content
    assert "[tool.nonebot.adapters]" in content


def test_toml_add_adapter_creates_section(tmp_path, monkeypatch) -> None:
    import tomllib

    from apeiria.plugin.adapter_manager import _toml_add_adapter

    monkeypatch.chdir(tmp_path)
    _setup_apeiria_toml(tmp_path)

    _toml_add_adapter("AdapterX", "adapter.x.module")
    raw = tomllib.loads((tmp_path / ".apeiria" / "pyproject.toml").read_text("utf-8"))
    entries = raw["tool"]["nonebot"]["adapters"]
    assert "AdapterX" in entries
    assert entries["AdapterX"][0]["name"] == "AdapterX"
    assert entries["AdapterX"][0]["module_name"] == "adapter.x.module"


def test_toml_remove_adapter(tmp_path, monkeypatch) -> None:
    import tomllib

    from apeiria.plugin.adapter_manager import _toml_add_adapter, _toml_remove_adapter

    monkeypatch.chdir(tmp_path)
    _setup_apeiria_toml(tmp_path)

    _toml_add_adapter("RemoveMe", "remove.module")
    _toml_remove_adapter("RemoveMe")
    raw = tomllib.loads((tmp_path / ".apeiria" / "pyproject.toml").read_text("utf-8"))
    adapters = raw.get("tool", {}).get("nonebot", {}).get("adapters", {})
    assert "RemoveMe" not in adapters


def test_toml_add_then_remove_preserves_file(tmp_path, monkeypatch) -> None:
    import tomllib

    from apeiria.plugin.adapter_manager import _toml_add_adapter, _toml_remove_adapter

    monkeypatch.chdir(tmp_path)
    _setup_apeiria_toml(tmp_path)

    _toml_add_adapter("A", "a.module")
    _toml_add_adapter("B", "b.module")
    _toml_remove_adapter("A")

    raw = tomllib.loads((tmp_path / ".apeiria" / "pyproject.toml").read_text("utf-8"))
    adapters = raw["tool"]["nonebot"]["adapters"]
    assert "A" not in adapters
    assert "B" in adapters
    assert adapters["B"][0]["module_name"] == "b.module"


def test_adapter_yaml_defaults(tmp_path, monkeypatch) -> None:
    from apeiria.plugin.adapter_manager import _read_adapters_yaml

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".apeiria").mkdir()

    data = _read_adapters_yaml()
    assert "packages" in data
    assert "states" in data
    assert data["packages"] == {}
    assert data["states"] == {}


def test_load_adapters_from_toml_state_disabled(tmp_path, monkeypatch) -> None:
    from apeiria.config.loader import load_adapters_from_toml

    monkeypatch.chdir(tmp_path)
    _setup_builtin_toml(tmp_path)

    registered = load_adapters_from_toml(
        "pyproject.toml",
        states={"OneBot V11": {"enabled": False}},
    )
    assert registered == 0


def test_load_adapters_from_toml_state_enabled(tmp_path, monkeypatch) -> None:
    from apeiria.config.loader import load_adapters_from_toml

    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        "[tool.nonebot.adapters]\n"
        "test-adapter = [\n"
        '    { name = "TestAdapter", module_name = "nonebot.adapters.onebot.v11" },\n'
        "]\n",
        encoding="utf-8",
    )

    registered = load_adapters_from_toml(
        "pyproject.toml",
        states={"TestAdapter": {"enabled": True}},
    )
    assert registered == 1


def test_load_adapters_from_toml_no_filter_without_states(
    tmp_path, monkeypatch
) -> None:
    from apeiria.config.loader import load_adapters_from_toml

    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        "[tool.nonebot.adapters]\n"
        "test-adapter = [\n"
        '    { name = "NoState", module_name = "nonebot.adapters.onebot.v11" },\n'
        "]\n",
        encoding="utf-8",
    )

    registered = load_adapters_from_toml("pyproject.toml")
    assert registered == 1


def test_state_write_then_scanner_reads_updated(tmp_path, monkeypatch) -> None:
    from apeiria.plugin.adapter_manager import set_adapter_state
    from apeiria.plugin.adapter_scanner import scan_adapters

    monkeypatch.chdir(tmp_path)
    _setup_builtin_toml(tmp_path)
    _setup_adapters_yaml(tmp_path, packages={}, states={})

    set_adapter_state("OneBot V11", enabled=False)
    adapters = scan_adapters()
    onebot = next(a for a in adapters if a.name == "OneBot V11")
    assert not onebot.enabled

    set_adapter_state("OneBot V11", enabled=True)
    adapters = scan_adapters()
    onebot = next(a for a in adapters if a.name == "OneBot V11")
    assert onebot.enabled


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _setup_builtin_toml(tmp_path: Path) -> None:
    tmp_path.joinpath("pyproject.toml").write_text(
        "[tool.nonebot.adapters]\n"
        "nonebot-adapter-onebot = [\n"
        '    { name = "OneBot V11", module_name = "nonebot.adapters.onebot.v11" },\n'
        "]\n",
        encoding="utf-8",
    )


def _setup_pypi_toml(tmp_path: Path, adapters: dict[str, list[dict[str, str]]]) -> None:
    toml_path = tmp_path / ".apeiria" / "pyproject.toml"

    lines = ["[project]", 'name = "apeiria-extensions"', 'version = "0.1.0"', ""]
    for section_key in ("tool.nonebot.adapters",):
        lines.append(f"[{section_key}]")
        for key, entries in adapters.items():
            for e in entries:
                name = e["name"]
                mod = e["module_name"]
                lines.append(
                    f'"{key}" = [{{ name = "{name}", module_name = "{mod}" }}]'
                )
    toml_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _setup_apeiria_toml(tmp_path: Path) -> None:
    (tmp_path / ".apeiria").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".apeiria" / "pyproject.toml").write_text(
        "[project]\n"
        'name = "apeiria-extensions"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.12"\n'
        "dependencies = []\n"
        "\n"
        "[tool.uv]\n"
        "package = false\n"
        "\n"
        "[tool.nonebot.plugins]\n",
        encoding="utf-8",
    )


def _setup_adapters_yaml(
    tmp_path: Path,
    packages: dict[str, str],
    states: dict[str, dict],
) -> None:
    import yaml

    (tmp_path / ".apeiria").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".apeiria" / "adapters.yaml").write_text(
        yaml.dump({"packages": packages, "states": states}),
        encoding="utf-8",
    )
