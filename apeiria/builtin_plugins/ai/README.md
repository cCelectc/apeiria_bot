# AI Plugin

This builtin plugin is the NoneBot-facing shell for the Apeiria AI rewrite.

Current boundary-freeze phase provides:

- plugin metadata
- startup wiring
- a minimal superuser command for smoke testing
- a thin NoneBot-facing shell over the AI runtime

The runtime now also exposes explicit phase-1 boundaries for:

- reply decision
- skill compatibility
- admin/debug compatibility

It does not yet provide a full product implementation for:

- conversation context management
- persona switching
- long-term memory
- skill-first management UI
- WebUI management routes
