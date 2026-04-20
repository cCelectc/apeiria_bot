# Apeiria Agent Guide

Apeiria is a project-layer on top of [NoneBot 2](https://nonebot.dev/). It adds project-managed config, runtime bootstrap, a Web UI, a host-side CLI, and a set of builtin plugins.

## Top-level layout

```
apeiria/
├── bootstrap.py              # NoneBot bootstrap: config → init → framework → user plugins
├── bot/                      # NoneBot entry + system-level hooks
├── config/                   # 4 TOML file services (project/plugins/adapters/drivers)
├── db/                       # Schema + migrations + ORM models
├── access/                   # Permissions, rules, principal, audit, webui auth
├── plugins/                  # Plugin governance (catalog/policy/install/settings/store)
├── environment/              # uv envs + health + frontend build
├── scheduler.py              # APScheduler facade
├── log.py                    # Loguru sinks + in-memory ring
├── webui/                    # FastAPI backend (auth + routes + schemas)
├── chat/                     # Web Chat platform (NoneBot Adapter implementation)
├── ai/                       # AI feature (conversation / memory / persona / tools / skills ...)
├── builtin_plugins/          # Builtin NoneBot plugins (admin / help / render / ai / web_ui)
├── cli/                      # Host CLI (env / plugin / adapter / driver / webui)
├── i18n/                     # i18n runtime (dot-path keys, {prefix} substitution)
├── utils/                    # Cross-cutting helpers (files / json / time / plugin_introspection)
├── exceptions.py             # Domain exceptions
└── _framework_loader.py, _user_loader.py   # Bootstrap helpers
```

## Principles

- **Concern-oriented, not layer-oriented.** Each top-level directory is one functional domain.
- **Do not re-wrap NoneBot.** Use `bot.send(event, text)`, `run_preprocessor`, `on_startup`, etc. directly.
- **Files ≤ 400 lines by default, 500 ceiling** (schema + migrations exempt).
- **One concern per module.** Service singletons live in the domain; helpers have role names (`registry.py`, `policy.py`, `catalog.py`), not `*_service.py` suffixes.
- **No lazy `__getattr__` exports.** Import explicitly.

## Key runtime path

1. `bot.py` → `apeiria.bot.entry.run()`
2. `apeiria.bootstrap.initialize_nonebot()`
3. `_framework_loader.load_framework()` loads framework deps + builtin plugins + runs DB schema ensure + registers bot hooks
4. `_user_loader.load_user_plugins()` loads plugins declared in `apeiria.plugins.toml`

## Verification

```bash
./.venv/bin/apeiria status
./.venv/bin/apeiria check
./.venv/bin/apeiria run

ruff check .
ruff format .
pyright
```

## Config files

Copy the `*.example.toml` templates and edit:

- `apeiria.config.toml`
- `apeiria.plugins.toml`
- `apeiria.adapters.toml`
- `apeiria.drivers.toml`
- `user_bot.py` (project-local hooks; git-ignored)
