# AI Runtime Boundaries

The live AI runtime has one direct orchestration entry:
`AIRuntimeCoordinator`. Runtime entrypoints normalize ingress data into an
`AIRuntimeRequest`, the coordinator selects a named `RuntimePath`, and the path
runs the existing stage interfaces before returning an `AIRuntimeResult`.

The first production path is `ReplyPath`. It moves a turn through policy,
observation, context assembly, social policy, planning, execution, commit, and
trace projection. Future runtime variants should add a request/path pair when
their sequencing differs, rather than branching inside the live entry or
reintroducing a session-turn-engine facade.

`AIRuntimeResult` carries the terminal `RuntimeOutcome`, optional commit result,
compact stage reports, and diagnostics. Outcomes distinguish hard-rule skips,
social no-reply, no-plan/no-model paths, empty responses, commit failures, and
successful commits without overloading `RuntimeCommitResult`.

Context gathering is intentionally split into small providers for conversation
window, persona/model target, tool policy, memory, relationship/profile,
initiative bias, and optional RAG. These providers feed the existing
`RuntimeContextMaterials` shape instead of a configurable pipeline framework.

Tool contracts expose only operational metadata needed by policy, diagnostics,
and management reads: read-only status, derived mutation status, risk level,
optional timeout, and explicit operator-approval requirement. The metadata does
not imply an interactive approval queue, shell policy system, or OS sandbox.

Memory and knowledge retrieval remain bounded to the current memory layers,
relationship/persona context, and optional default knowledge RAG. Retrieval
diagnostics should report counts, layers, ranking/degradation status, and other
compact facts without requiring graph memory, multi-agent shared memory, or an
external memory-brain service.

Trace projection stores compact stage summaries, selected model references,
tool exposure summaries, retrieval counts, degradation reasons, and final
outcomes where available. Traces should not persist raw prompts, provider
payloads, API keys, full retrieved documents, full message histories, or tool
observation bodies by default.

The coordinator is intentionally small. It owns request dispatch,
same-session serialization, and top-level path execution. It does not own model
routing, prompt construction, tool-loop behavior, memory retrieval, delivery, or
trace storage policy; those responsibilities remain behind the stage
collaborators.

Out of scope for this runtime layer:

- Generic Agent SDK or workflow-engine adoption.
- DAGs, graph DSLs, replay engines, or flow visualization systems.
- Multi-agent orchestration, swarm execution, or autonomous sub-agent planning.
- Plugin-defined arbitrary runtime paths.
- Codex-like patch/edit workflows, broad shell execution approvals, or OS-level
  sandboxing.
- Mandatory vector database, process supervisor, or external memory service.
