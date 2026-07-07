from __future__ import annotations

from types import SimpleNamespace

import pytest


def _fake_request(*, auth_header=None):
    headers = {"Authorization": auth_header} if auth_header is not None else {}
    return SimpleNamespace(headers=headers, cookies={}, query_params={})


def _patch_secret(monkeypatch, secret):
    from apeiria.web import auth

    async def _fake() -> str:
        return secret

    monkeypatch.setattr(auth, "_require_jwt_secret", _fake)


# --------------------------------------------------------------------------
# paginate
# --------------------------------------------------------------------------


def test_paginate() -> None:
    from apeiria.web.store import paginate

    items = list(range(10))
    page, total = paginate(items, offset=0, limit=3)
    assert page == [0, 1, 2]
    assert total == 10

    page, total = paginate(items, offset=8, limit=5)
    assert page == [8, 9]

    page, total = paginate(items, offset=2, limit=0)
    assert page == items[2:]
    assert total == 10


# --------------------------------------------------------------------------
# merge_plugin_metadata
# --------------------------------------------------------------------------


def test_merge_plugin_metadata() -> None:
    from apeiria.plugin.scanner import PluginManifest
    from apeiria.web.plugin_metadata import merge_plugin_metadata

    builtin = PluginManifest(
        name="foo",
        path_or_module="apeiria.builtin_plugins.foo",
        enabled=True,
        source="builtin",
    )
    pypi = PluginManifest(
        name="bar", path_or_module="bar-pkg", enabled=False, source="pypi"
    )
    metadata_map = {"foo": {"name": "Foo", "description": "d", "type": "application"}}
    rows = merge_plugin_metadata(
        [builtin, pypi],
        metadata_map,
        dep_graph={"foo": {"bar"}},
        dep_reverse={"bar": {"foo"}},
    )
    by = {r["name"]: r for r in rows}

    assert by["foo"]["can_disable"] is True
    assert by["foo"]["can_uninstall"] is False
    assert by["foo"]["display_name"] == "Foo"
    assert by["foo"]["module"] == "foo"
    assert by["foo"]["depends_on"] == ["bar"]

    assert by["bar"]["can_uninstall"] is True
    assert by["bar"]["module"] == "bar_pkg"
    assert by["bar"]["enabled"] is False
    assert by["bar"]["depended_by"] == ["foo"]


# --------------------------------------------------------------------------
# verify_token
# --------------------------------------------------------------------------


async def test_verify_token_valid(monkeypatch) -> None:
    import jwt

    from apeiria.web import auth

    _patch_secret(monkeypatch, "test-secret-key-32-bytes-minimum-aaaa")
    token = jwt.encode(
        {"sub": "admin"}, "test-secret-key-32-bytes-minimum-aaaa", algorithm="HS256"
    )
    assert await auth.verify_token(_fake_request(auth_header=f"Bearer {token}")) == (
        "admin"
    )


async def test_verify_token_missing() -> None:
    from fastapi import HTTPException

    from apeiria.web import auth

    with pytest.raises(HTTPException) as exc:
        await auth.verify_token(_fake_request())
    assert exc.value.status_code == 401


async def test_verify_token_invalid(monkeypatch) -> None:
    from fastapi import HTTPException

    from apeiria.web import auth

    _patch_secret(monkeypatch, "test-secret-key-32-bytes-minimum-aaaa")
    with pytest.raises(HTTPException) as exc:
        await auth.verify_token(_fake_request(auth_header="Bearer garbage"))
    assert exc.value.status_code == 401


async def test_verify_token_expired(monkeypatch) -> None:
    from datetime import UTC, datetime, timedelta

    import jwt
    from fastapi import HTTPException

    from apeiria.web import auth

    _patch_secret(monkeypatch, "test-secret-key-32-bytes-minimum-aaaa")
    expired = datetime.now(UTC) - timedelta(days=1)
    token = jwt.encode(
        {"sub": "admin", "exp": expired},
        "test-secret-key-32-bytes-minimum-aaaa",
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc:
        await auth.verify_token(_fake_request(auth_header=f"Bearer {token}"))
    assert exc.value.status_code == 401


# --------------------------------------------------------------------------
# _patch_config
# --------------------------------------------------------------------------


def test_patch_config_merges_existing_dict(tmp_path, monkeypatch) -> None:
    import yaml

    from apeiria.web.routes import _patch_config

    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    cfg = tmp_path / "data" / "config.yaml"
    cfg.write_text(yaml.dump({"plugins": {"a": 1}}), encoding="utf-8")

    _patch_config("plugins", {"b": 2})
    raw = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert raw["plugins"] == {"a": 1, "b": 2}


def test_patch_config_replaces_non_dict_section(tmp_path, monkeypatch) -> None:
    import yaml

    from apeiria.web.routes import _patch_config

    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    cfg = tmp_path / "data" / "config.yaml"
    cfg.write_text(yaml.dump({"nonebot": "scalar"}), encoding="utf-8")

    _patch_config("nonebot", {"host": "x"})
    raw = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert raw["nonebot"] == {"host": "x"}


# --------------------------------------------------------------------------
# api_config_nonebot driver protection
# --------------------------------------------------------------------------


async def test_config_nonebot_driver_unchanged_ok(tmp_path, monkeypatch) -> None:
    import yaml

    from apeiria.web.routes import api_config_nonebot

    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    cfg = tmp_path / "data" / "config.yaml"
    driver = "~fastapi+~httpx+~websockets"
    cfg.write_text(
        yaml.dump({"nonebot": {"driver": driver, "host": "127.0.0.1"}}),
        encoding="utf-8",
    )

    resp = await api_config_nonebot({"driver": driver, "host": "0.0.0.0"})
    assert resp.status_code == 200
    raw = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert raw["nonebot"]["host"] == "0.0.0.0"
    assert raw["nonebot"]["driver"] == driver


async def test_config_nonebot_driver_changed_blocked(tmp_path, monkeypatch) -> None:
    import yaml
    from fastapi import HTTPException

    from apeiria.web.routes import api_config_nonebot

    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    cfg = tmp_path / "data" / "config.yaml"
    cfg.write_text(
        yaml.dump({"nonebot": {"driver": "~fastapi+~httpx+~websockets"}}),
        encoding="utf-8",
    )

    with pytest.raises(HTTPException) as exc:
        await api_config_nonebot({"driver": "~aiohttp"})
    assert exc.value.status_code == 422
    assert "driver" in exc.value.detail


# --------------------------------------------------------------------------
# _scanned_name_to_module
# --------------------------------------------------------------------------


def test_scanned_name_to_module_maps_display_name(tmp_path, monkeypatch) -> None:
    import yaml

    from apeiria.web.routes import _scanned_name_to_module

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".apeiria").mkdir()
    (tmp_path / ".apeiria" / "plugins.yaml").write_text(
        yaml.dump(
            {
                "dirs": [],
                "packages": {"链接分享解析 Alconna 版": "nonebot-plugin-parser"},
                "states": {},
            }
        ),
        encoding="utf-8",
    )

    assert _scanned_name_to_module("链接分享解析 Alconna 版") == "nonebot_plugin_parser"
    assert _scanned_name_to_module("不存在的插件") is None
