from __future__ import annotations


def test_ensure_creates_directories(tmp_path, monkeypatch) -> None:
    from apeiria.env.ensure import ensure_apeiria_env

    monkeypatch.chdir(tmp_path)
    base = ensure_apeiria_env()
    assert base.is_dir()
    assert (base / "plugins").is_dir()
    assert (base / "pyproject.toml").is_file()
    assert (base / "plugins.yaml").is_file()


def test_ensure_idempotent(tmp_path, monkeypatch) -> None:
    from apeiria.env.ensure import ensure_apeiria_env

    monkeypatch.chdir(tmp_path)
    first = ensure_apeiria_env()
    second = ensure_apeiria_env()
    assert first == second


def test_find_uv() -> None:
    from apeiria.env.sync import _find_uv

    uv = _find_uv()
    assert uv is not None
