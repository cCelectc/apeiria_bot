from __future__ import annotations


class AIModelError(Exception):
    pass


class AIModelRateLimitError(AIModelError):
    pass


class AIModelAuthError(AIModelError):
    pass


class AIModelOverloadedError(AIModelError):
    pass


class AIModelConnectionError(AIModelError):
    pass


class AIModelContextLengthError(AIModelError):
    pass


class AIModelProviderNotFoundError(AIModelError):
    def __init__(self, adapter: str) -> None:
        super().__init__(f"No provider registered for adapter: {adapter}")
        self.adapter = adapter


class AIModelCapabilityError(AIModelError):
    def __init__(self, adapter: str, capability: str) -> None:
        super().__init__(
            f"Provider '{adapter}' does not support capability: {capability}"
        )
        self.adapter = adapter
        self.capability = capability


class AIModelNotFoundError(AIModelError):
    def __init__(self, model_id: str) -> None:
        super().__init__(f"Model not found or disabled: {model_id}")
        self.model_id = model_id


class AIModelSourceNotFoundError(AIModelError):
    def __init__(self, source_id: str) -> None:
        super().__init__(f"Source not found or disabled: {source_id}")
        self.source_id = source_id


class AIModelStreamTimeoutError(AIModelError):
    pass
