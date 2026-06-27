from __future__ import annotations


def test_step_load_pypi_loads_enabled_packages_by_module(tmp_path, monkeypatch) -> None:
    import nonebot

    from apeiria.bootstrap import steps

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".apeiria").mkdir()
    (tmp_path / ".apeiria" / "plugins.yaml").write_text(
        "dirs: []\n"
        "packages:\n"
        "  服务器状态查看: nonebot-plugin-status>=0.9.0\n"
        "  关闭项: nonebot-plugin-foo\n"
        "states:\n"
        "  关闭项:\n"
        "    enabled: false\n",
        encoding="utf-8",
    )

    loaded: list[str] = []

    def _fake_load_plugin(module: str) -> None:
        loaded.append(module)

    monkeypatch.setattr(nonebot, "load_plugin", _fake_load_plugin)

    steps.step_load_pypi()

    assert loaded == ["nonebot_plugin_status"]
