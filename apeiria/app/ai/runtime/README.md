# Lightweight AI Runtime Boundaries

The live AI path stays stage-oriented. A turn moves through policy, observation,
context assembly, planning, execution, commit, and trace projection under
`apeiria.app.ai.runtime`; new AI behavior should fit one of those boundaries
before adding a new coordinator.

Context gathering is intentionally split into small providers for conversation
window, persona/model target, tool policy, memory, relationship/person profile,
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

Out of scope for this runtime layer:

- Generic Agent SDK or workflow-engine adoption.
- Multi-agent orchestration, swarm execution, or autonomous sub-agent planning.
- Codex-like patch/edit workflows, broad shell execution approvals, or OS-level
  sandboxing.
- Mandatory vector database, process supervisor, or external memory service.
