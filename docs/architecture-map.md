# Architecture Map

Back to the index: [`../AGENTS.md`](../AGENTS.md)

## Project shape

Apeiria is a project layer on top of NoneBot 2. It adds project-managed config, runtime/bootstrap logic, builtin management plugins, a Web UI, and a host-side CLI.

## High-level ownership

### Backend

- `apeiria/app/` — application services and use-case orchestration
- `apeiria/app/operations/` — Operations Plane services for environment, package, store, and health facades
- `apeiria/infra/` — config, runtime bootstrap, logging, scheduler, auth, metadata, and other infrastructure
- `apeiria/interfaces/` — external entrypoints for CLI, HTTP, and bot hooks
- `apeiria/shared/` — shared helpers, types, and cross-cutting utilities

### Builtin plugins

- `apeiria/builtin_plugins/admin/` — management commands and admin-facing bot capabilities
- `apeiria/builtin_plugins/help/` — help generation and presentation
- `apeiria/builtin_plugins/render/` — shared rendering service and browser-backed image generation
- `apeiria/builtin_plugins/web_ui/` — Web UI backend integration and static asset serving

See plugin-local READMEs for details:

- [`../apeiria/builtin_plugins/admin/README.md`](../apeiria/builtin_plugins/admin/README.md)
- [`../apeiria/builtin_plugins/help/README.md`](../apeiria/builtin_plugins/help/README.md)
- [`../apeiria/builtin_plugins/render/README.md`](../apeiria/builtin_plugins/render/README.md)
- [`../apeiria/builtin_plugins/web_ui/README.md`](../apeiria/builtin_plugins/web_ui/README.md)

### Frontend

- `web/src/components/` — reusable UI components
- `web/src/views/` — page-level views
- `web/src/composables/` — reusable Composition API logic
- `web/src/stores/` — client-side state
- `web/src/router/` — route definitions
- `web/src/api/` — frontend API client wrappers
- `web/src/styles/` — frontend style setup

## Key runtime path

When you need to understand startup and ownership, read in this order:

1. `bot.py`
2. `apeiria/interfaces/bot/main.py`
3. `apeiria/infra/runtime/bootstrap.py`
4. `apeiria/infra/runtime/framework_loader.py`
5. `apeiria/interfaces/http/routes/router.py` or `apeiria/interfaces/cli/main.py`, depending on the entrypoint you are changing

## Where to change what

- NoneBot startup, plugin loading, runtime environment: `apeiria/infra/runtime/`
- Environment, package/store operations, and health facades: `apeiria/app/operations/`
- Project config reading/writing: `apeiria/infra/config/`
- Plugin catalog, config, install/uninstall, policy: `apeiria/app/plugins/`
- HTTP auth and API routes: `apeiria/interfaces/http/`
- CLI commands: `apeiria/interfaces/cli/`
- Frontend pages and interaction: `web/src/`
- Builtin plugin behavior: `apeiria/builtin_plugins/<plugin_name>/`

## Config model

Project-level config is intentionally split across multiple TOML files rather than hidden in `user_bot.py`:

- `apeiria.config.toml`
- `apeiria.plugins.toml`
- `apeiria.adapters.toml`
- `apeiria.drivers.toml`

Use the README as the primary operator-facing explanation of these files.
