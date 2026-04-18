"""Runtime Kernel observation layer.

The runtime module owns the formal ingress normalization objects,
`DispatchRequest`, `ExecutionReport`, and the unified runtime diagnostics
recorder. It does not replace NoneBot's matcher — it shells matcher
execution so that every incoming interaction can be observed as a formal
runtime event without altering the existing handler path.
"""

from apeiria.app.runtime.diagnostics import (
    RuntimeDiagnostic,
    RuntimeDiagnosticKind,
    RuntimeDiagnosticRecorder,
    runtime_diagnostic_recorder,
)
from apeiria.app.runtime.models import (
    DeliveryTarget,
    DispatchRequest,
    ExecutionReport,
    IngressKind,
    InvocationDisposition,
    MessageContent,
    MessageEvent,
    PrincipalRef,
    PrincipalRefKind,
    RuntimeFrame,
    SceneKind,
    SceneRef,
    SessionRef,
    SubjectKind,
)
from apeiria.app.runtime.normalize import (
    RuntimeIngressNormalizer,
    runtime_ingress_normalizer,
)
from apeiria.app.runtime.observer import (
    MatcherObservation,
    runtime_matcher_observer,
)

__all__ = [
    "DeliveryTarget",
    "DispatchRequest",
    "ExecutionReport",
    "IngressKind",
    "InvocationDisposition",
    "MatcherObservation",
    "MessageContent",
    "MessageEvent",
    "PrincipalRef",
    "PrincipalRefKind",
    "RuntimeDiagnostic",
    "RuntimeDiagnosticKind",
    "RuntimeDiagnosticRecorder",
    "RuntimeFrame",
    "RuntimeIngressNormalizer",
    "SceneKind",
    "SceneRef",
    "SessionRef",
    "SubjectKind",
    "runtime_diagnostic_recorder",
    "runtime_ingress_normalizer",
    "runtime_matcher_observer",
]
