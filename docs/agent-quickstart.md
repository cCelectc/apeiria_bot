# Agent Quickstart

Back to the index: [`../AGENTS.md`](../AGENTS.md)

## Purpose

Use this guide when you need a fast path into the repo before making a change.

## First-pass reading order

1. Read [`../README.md`](../README.md) for product scope, startup flow, and config model.
2. Read [`architecture-map.md`](architecture-map.md) to find the right subsystem.
3. Read the area-specific guide:
   - backend work → [`backend-guidelines.md`](backend-guidelines.md)
   - frontend work → [`frontend-guidelines.md`](frontend-guidelines.md)
   - repo-wide verification or standards → [`code-quality.md`](code-quality.md)

## When to read what

- Runtime, config, plugin loading, or CLI changes: start from `apeiria/infra/` and `apeiria/interfaces/`.
- Environment/package/store/health surface changes: check `apeiria/app/operations/` before editing CLI or HTTP entrypoints.
- Builtin plugin changes: check `apeiria/builtin_plugins/*/README.md` before editing code.
- Web UI changes: read `web/` plus the frontend guide before touching views or stores.
- Docs changes: update the canonical detailed doc, then keep `AGENTS.md` as a summary.

## Fast repo landmarks

- `bot.py` — bot runtime entrypoint
- `apeiria/infra/runtime/bootstrap.py` — NoneBot bootstrap and project-managed startup
- `apeiria/infra/runtime/framework_loader.py` — framework and builtin plugin loading
- `apeiria/interfaces/http/routes/router.py` — API router aggregation
- `apeiria/interfaces/cli/main.py` — CLI entrypoint
- `apeiria/app/plugins/service.py` — plugin catalog and management service layer
- `apeiria/app/operations/` — Operations Plane facades for environment, package, store, and health
- `web/src/api/` — frontend HTTP client layer
- `web/src/` — frontend application source

## Working rule

Prefer small, targeted edits. Before introducing new structure, check whether an existing service, route group, plugin README, or frontend pattern already covers the problem.
