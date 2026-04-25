from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace

from pytest import MonkeyPatch, raises

from apeiria.db.runtime import ApeiriaDatabase
from apeiria.runtime import ApeiriaRuntime
from apeiria.runtime.bootstrapper import ApeiriaBootstrapper
from apeiria.runtime.context import get_current_runtime, set_current_runtime


def test_runtime_skeleton_exposes_core_handles(tmp_path: Path) -> None:
    config = object()
    environment = object()
    database = object()
    plugins = object()
    access = object()
    ai = object()
    control_plane = None

    runtime = ApeiriaRuntime(
        project_root=tmp_path,
        config=config,
        environment=environment,
        database=database,
        plugins=plugins,
        access=access,
        ai=ai,
        control_plane=control_plane,
    )

    assert runtime.project_root == tmp_path
    assert runtime.config is config
    assert runtime.environment is environment
    assert runtime.database is database
    assert runtime.plugins is plugins
    assert runtime.access is access
    assert runtime.ai is ai
    assert runtime.control_plane is control_plane
    assert tuple(field.name for field in fields(ApeiriaRuntime)) == (
        "project_root",
        "config",
        "environment",
        "database",
        "plugins",
        "access",
        "ai",
        "control_plane",
    )


def test_current_runtime_can_be_installed_and_retrieved(tmp_path: Path) -> None:
    runtime = ApeiriaRuntime(
        project_root=tmp_path,
        config=object(),
        environment=object(),
        database=object(),
        plugins=object(),
        access=object(),
        ai=object(),
        control_plane=None,
    )
    previous = get_current_runtime()

    try:
        set_current_runtime(runtime)

        assert get_current_runtime() is runtime
    finally:
        set_current_runtime(previous)


def test_build_runtime_uses_existing_project_services(
    monkeypatch: MonkeyPatch,
) -> None:
    from apeiria.runtime.phases import runtime as runtime_phase

    project_root = Path("/tmp/test-project")
    project_config_service = object()
    environment_service = type(
        "EnvironmentServiceStub",
        (),
        {"project_root": project_root},
    )()
    database_service = ApeiriaDatabase(project_root=project_root)
    plugin_governance_service = object()
    access_service = object()
    ai_runtime_service = object()

    monkeypatch.setattr(
        runtime_phase,
        "_get_runtime_services",
        lambda: (
            project_config_service,
            environment_service,
            database_service,
            plugin_governance_service,
            access_service,
            ai_runtime_service,
        ),
    )

    runtime = runtime_phase.build_runtime()

    assert runtime == ApeiriaRuntime(
        project_root=project_root,
        config=project_config_service,
        environment=environment_service,
        database=database_service,
        plugins=plugin_governance_service,
        access=access_service,
        ai=ai_runtime_service,
        control_plane=None,
    )


def test_bootstrapper_runtime_phase_builds_and_installs_runtime(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = ApeiriaRuntime(
        project_root=tmp_path,
        config=object(),
        environment=object(),
        database=None,
        plugins=object(),
        access=object(),
        ai=object(),
        control_plane=None,
    )
    bootstrapper = ApeiriaBootstrapper()
    previous = get_current_runtime()
    attached_control_planes: list[object] = []

    monkeypatch.setattr(
        "apeiria.runtime.phases.runtime.build_runtime",
        lambda: runtime,
    )
    monkeypatch.setattr(
        "apeiria.runtime.control_plane.ApeiriaControlPlane",
        lambda attached_runtime: attached_control_planes.append(attached_runtime)
        or SimpleNamespace(runtime=attached_runtime),
    )

    try:
        bootstrapper._run_runtime_phase()

        assert bootstrapper.runtime is runtime
        assert runtime.control_plane == SimpleNamespace(runtime=runtime)
        assert attached_control_planes == [runtime]
        assert get_current_runtime() is runtime
    finally:
        set_current_runtime(previous)


def test_initialize_nonebot_rolls_back_runtime_when_user_plugins_phase_fails(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    previous_runtime = ApeiriaRuntime(
        project_root=tmp_path / "previous",
        config=object(),
        environment=object(),
        database=None,
        plugins=object(),
        access=object(),
        ai=object(),
        control_plane=None,
    )
    installed_runtime = ApeiriaRuntime(
        project_root=tmp_path / "installed",
        config=object(),
        environment=object(),
        database=None,
        plugins=object(),
        access=object(),
        ai=object(),
        control_plane=None,
    )
    bootstrapper = ApeiriaBootstrapper()
    expected_error = RuntimeError("user plugin load failed")
    original_runtime = get_current_runtime()

    monkeypatch.setattr(bootstrapper, "_run_environment_phase", lambda: None)
    monkeypatch.setattr(bootstrapper, "_run_config_phase", lambda: None)
    monkeypatch.setattr(bootstrapper, "_run_user_extensions_phase", lambda: None)
    monkeypatch.setattr(bootstrapper, "_run_framework_phase", lambda: None)

    def install_runtime() -> None:
        bootstrapper.runtime = installed_runtime
        set_current_runtime(installed_runtime)

    monkeypatch.setattr(bootstrapper, "_run_runtime_phase", install_runtime)
    monkeypatch.setattr(
        bootstrapper,
        "_run_user_plugins_phase",
        lambda: (_ for _ in ()).throw(expected_error),
    )

    try:
        set_current_runtime(previous_runtime)

        with raises(RuntimeError) as exc_info:
            bootstrapper.initialize_nonebot()

        assert exc_info.value is expected_error
        assert get_current_runtime() is previous_runtime
        assert bootstrapper.runtime is None
    finally:
        set_current_runtime(original_runtime)
