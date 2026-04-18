# Apeiria Agent Guide

This file is the contributor and agent navigation hub. Keep it short. Put detailed standards and procedures in `docs/*.md` or subsystem `README.md` files.

## Start here

- Project overview and quick start: [`README.md`](README.md)
- Repo navigation and first-pass workflow: [`docs/agent-quickstart.md`](docs/agent-quickstart.md)
- Architecture and ownership map: [`docs/architecture-map.md`](docs/architecture-map.md)
- Backend engineering rules: [`docs/backend-guidelines.md`](docs/backend-guidelines.md)
- Frontend engineering rules: [`docs/frontend-guidelines.md`](docs/frontend-guidelines.md)
- Quality, verification, and review expectations: [`docs/code-quality.md`](docs/code-quality.md)

## Directory map

| Path | Responsibility | Read first |
| --- | --- | --- |
| `apeiria/app/` | Application services for plugins, access, chat, dashboard | [`docs/architecture-map.md`](docs/architecture-map.md) |
| `apeiria/app/operations/` | Operations Plane services for environment, package, store, health | [`docs/architecture-map.md`](docs/architecture-map.md) |
| `apeiria/infra/` | Config, runtime bootstrap, logging, scheduler, auth, metadata | [`docs/backend-guidelines.md`](docs/backend-guidelines.md) |
| `apeiria/interfaces/` | CLI, HTTP, bot-facing entrypoints | [`docs/backend-guidelines.md`](docs/backend-guidelines.md) |
| `apeiria/builtin_plugins/` | Built-in NoneBot plugins | [`docs/architecture-map.md`](docs/architecture-map.md) |
| `web/` | Vue 3 + Vuetify Web UI | [`docs/frontend-guidelines.md`](docs/frontend-guidelines.md) |
| `docs/` | Detailed contributor and agent docs | This directory |
| `apeiria.*.toml` | Project-managed config files | [`README.md`](README.md) |
| `user_bot.py` | Local user customization hook | [`README.md`](README.md) |

## Task routing

- If you are changing runtime/bootstrap/config loading, read [`docs/architecture-map.md`](docs/architecture-map.md) and [`docs/backend-guidelines.md`](docs/backend-guidelines.md).
- If you are changing environment init, package/store operations, or health checks, read [`docs/architecture-map.md`](docs/architecture-map.md) first and start in `apeiria/app/operations/`.
- If you are changing HTTP routes, auth, or Web UI backend behavior, read [`docs/backend-guidelines.md`](docs/backend-guidelines.md) first.
- If you are changing Vue components or frontend interaction patterns, read [`docs/frontend-guidelines.md`](docs/frontend-guidelines.md) first.
- If you are changing shared standards, linting expectations, or verification steps, read [`docs/code-quality.md`](docs/code-quality.md).
- If you are documenting a builtin plugin, prefer the plugin-local `README.md` as the canonical detailed home.

## Detailed guides

- [`docs/agent-quickstart.md`](docs/agent-quickstart.md)
- [`docs/architecture-map.md`](docs/architecture-map.md)
- [`docs/backend-guidelines.md`](docs/backend-guidelines.md)
- [`docs/frontend-guidelines.md`](docs/frontend-guidelines.md)
- [`docs/code-quality.md`](docs/code-quality.md)

## Local module docs

- Web UI plugin: [`apeiria/builtin_plugins/web_ui/README.md`](apeiria/builtin_plugins/web_ui/README.md)
- Render plugin: [`apeiria/builtin_plugins/render/README.md`](apeiria/builtin_plugins/render/README.md)
- Help plugin: [`apeiria/builtin_plugins/help/README.md`](apeiria/builtin_plugins/help/README.md)
- Admin plugin: [`apeiria/builtin_plugins/admin/README.md`](apeiria/builtin_plugins/admin/README.md)
- Web component docs: [`web/src/components/README.md`](web/src/components/README.md)
- Web plugin docs: [`web/src/plugins/README.md`](web/src/plugins/README.md)
- Web style docs: [`web/src/styles/README.md`](web/src/styles/README.md)

## Maintenance rule

- `AGENTS.md` is an index, not a handbook.
- Put long-form instructions in `docs/*.md`.
- Keep one canonical home per topic and replace duplication with links.
