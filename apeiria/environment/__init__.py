"""Operations-plane application services."""

from apeiria.app.plugins.store.service import StoreService, store_service
from apeiria.environment.health import HealthService, health_service
from apeiria.environment.manager import (
    EnvironmentService,
    environment_service,
)
from apeiria.environment.models import (
    EnvironmentRepairPlan,
    EnvironmentSnapshot,
    FrontendBuildRunResult,
    FrontendBuildSnapshot,
    FrontendBuildStreamEvent,
    HealthCheck,
    HealthSnapshot,
    PackageOperationRequest,
    PackageOperationResult,
)
from apeiria.plugins.install import (
    PackageService,
    StoreInstallError,
    package_service,
)

__all__ = [
    "EnvironmentRepairPlan",
    "EnvironmentService",
    "EnvironmentSnapshot",
    "FrontendBuildRunResult",
    "FrontendBuildSnapshot",
    "FrontendBuildStreamEvent",
    "HealthCheck",
    "HealthService",
    "HealthSnapshot",
    "PackageOperationRequest",
    "PackageOperationResult",
    "PackageService",
    "StoreInstallError",
    "StoreService",
    "environment_service",
    "health_service",
    "package_service",
    "store_service",
]
