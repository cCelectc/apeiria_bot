"""Error types raised by the AI admin service layer."""

from __future__ import annotations


class AIAdminModelNotFoundError(ValueError):
    """Raised when one requested source-backed model cannot be found."""


class AISourceModelFetchConfigError(ValueError):
    """Raised when source model discovery lacks required runtime config."""

    MISSING_PRESET = "请先选择接入方式。"
    MISSING_API_BASE = "请先填写接口地址。"
    MISSING_API_KEY = "未找到可用的 API 密钥。"

    def __init__(self, detail: str = MISSING_API_KEY) -> None:
        super().__init__(detail)


class AISourceModelFetchUpstreamError(RuntimeError):
    """Raised when upstream source discovery fails."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)


class AISourceModelTestConfigError(ValueError):
    """Raised when source model test lacks required runtime config."""

    MISSING_MODEL_IDENTIFIER = "请先选择需要测试的模型。"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)


class AISourceModelTestUpstreamError(RuntimeError):
    """Raised when upstream source model test fails."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)


class AISourceDeleteBlockedError(ValueError):
    """Raised when deleting one source would leave dependent rows behind."""

    def __init__(
        self,
        *,
        model_count: int,
        model_labels: tuple[str, ...] = (),
    ) -> None:
        suffix = f"：{', '.join(model_labels)}" if model_labels else ""
        super().__init__(
            f"当前接入仍绑定 {model_count} 个模型，请先删除相关模型{suffix}。"
        )


class AISourceModelDeleteBlockedError(ValueError):
    """Raised when deleting one source model would leave profiles behind."""

    def __init__(
        self,
        *,
        profile_count: int,
        profile_labels: tuple[str, ...] = (),
    ) -> None:
        suffix = f"：{', '.join(profile_labels)}" if profile_labels else ""
        super().__init__(
            f"当前模型仍被 {profile_count} 个模型档案引用，请先调整模型档案{suffix}。"
        )


__all__ = [
    "AIAdminModelNotFoundError",
    "AISourceDeleteBlockedError",
    "AISourceModelDeleteBlockedError",
    "AISourceModelFetchConfigError",
    "AISourceModelFetchUpstreamError",
    "AISourceModelTestConfigError",
    "AISourceModelTestUpstreamError",
]
