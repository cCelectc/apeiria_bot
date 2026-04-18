"""Runtime Kernel observation and control layer.

The runtime module owns the formal ingress normalization objects,
`DispatchRequest`, `ExecutionReport`, the unified runtime diagnostics
recorder, and the `Effect` pipeline. It does not replace NoneBot's matcher
— it shells matcher execution so that every incoming interaction can be
observed as a formal runtime event and every outbound side effect flows
through a structured gateway.
"""

from apeiria.app.runtime.diagnostics import (
    RuntimeDiagnostic,
    RuntimeDiagnosticKind,
    RuntimeDiagnosticRecorder,
    runtime_diagnostic_recorder,
)
from apeiria.app.runtime.effect import (
    Effect,
    EffectBucket,
    EffectKind,
    EffectQueue,
    EffectStatus,
    bind_effect_queue,
    current_effect_queue,
    new_effect,
    reset_effect_queue,
)
from apeiria.app.runtime.handler_registry import (
    HandlerRegistry,
    handler_registry,
)
from apeiria.app.runtime.models import (
    DeliveryChannel,
    DeliveryTarget,
    DispatchRequest,
    ExecutionReport,
    IngressKind,
    InvocationDisposition,
    InvocationResult,
    MessageContent,
    MessageEvent,
    ModelRequest,
    ModelResponse,
    PrincipalRef,
    PrincipalRefKind,
    RuntimeFrame,
    SceneKind,
    SceneRef,
    SendResult,
    SessionRef,
    SubjectKind,
    ToolCall,
    ToolResult,
)
from apeiria.app.runtime.normalize import (
    RuntimeIngressNormalizer,
    runtime_ingress_normalizer,
)
from apeiria.app.runtime.observer import (
    MatcherObservation,
    current_frame,
    current_request_id,
    runtime_matcher_observer,
)
from apeiria.app.runtime.plugin_state_store import (
    PluginRuntimeStateStore,
    plugin_runtime_state_store,
)

__all__ = [
    "DeliveryChannel",
    "DeliveryTarget",
    "DispatchRequest",
    "Effect",
    "EffectBucket",
    "EffectKind",
    "EffectQueue",
    "EffectStatus",
    "ExecutionReport",
    "HandlerRegistry",
    "IngressKind",
    "InvocationDisposition",
    "InvocationResult",
    "MatcherObservation",
    "MessageContent",
    "MessageEvent",
    "ModelRequest",
    "ModelResponse",
    "PluginRuntimeStateStore",
    "PrincipalRef",
    "PrincipalRefKind",
    "RuntimeDiagnostic",
    "RuntimeDiagnosticKind",
    "RuntimeDiagnosticRecorder",
    "RuntimeFrame",
    "RuntimeIngressNormalizer",
    "SceneKind",
    "SceneRef",
    "SendResult",
    "SessionRef",
    "SubjectKind",
    "ToolCall",
    "ToolResult",
    "bind_effect_queue",
    "current_effect_queue",
    "current_frame",
    "current_request_id",
    "handler_registry",
    "new_effect",
    "plugin_runtime_state_store",
    "reset_effect_queue",
    "runtime_diagnostic_recorder",
    "runtime_ingress_normalizer",
    "runtime_matcher_observer",
]
