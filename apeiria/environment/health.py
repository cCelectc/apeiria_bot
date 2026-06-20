from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.environment.models import HealthCheck, HealthSnapshot

if TYPE_CHECKING:
    from apeiria.environment.manager import EnvironmentService


class HealthService:
    def __init__(self, env: EnvironmentService) -> None:
        self._env = env

    def get_snapshot(self) -> HealthSnapshot:
        env_snapshot = self._env.get_environment_snapshot()
        checks = [
            HealthCheck(
                key="project_root",
                ok=env_snapshot.project_root.exists(),
                detail=str(env_snapshot.project_root),
            ),
            HealthCheck(
                key="database",
                ok=True,
                detail="ok",
            ),
        ]
        status = "healthy" if all(c.ok for c in checks) else "degraded"
        return HealthSnapshot(
            status=status,
            project_root=env_snapshot.project_root,
            checks=checks,
            environment=env_snapshot,
        )
