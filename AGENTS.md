# Apeiria Bot — Repository Guidelines

## 1. Project Overview

Apeiria is a Python chatbot framework built on [NoneBot2](https://nonebot.dev/) with an AI-augmented runtime, a Vue 3 + shadcn-vue Web UI, and SQLite-backed persistence. The project is organized as the `apeiria/` package with a CLI entry point (`apeiria`) and a growing suite of AI capabilities (memory, knowledge retrieval, tool use, persona management, relationship scoring).

- **Python:** 3.10+ (CI & Docker target 3.14)
- **Package manager:** `uv` (Python) / `pnpm` (frontend)
- **Database:** SQLite via SQLAlchemy (async) + Alembic migrations
- **Runtime:** NoneBot2 with OneBot adapter + custom AI orchestration pipeline

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  Web UI (Vue 3 + shadcn-vue + Tailwind CSS)             │
│  webui/src/  pages/  components/  composables/          │
├─────────────────────────────────────────────────────────┤
│  HTTP & WebSocket Layer                                  │
│  apeiria/webui/routes/  (FastAPI endpoints)              │
│  apeiria/app/chat/      (WebSocket gateway)              │
├─────────────────────────────────────────────────────────┤
│  AI Runtime Orchestrator                                 │
│  apeiria/app/ai/runtime/   (planning, execution, commit) │
│  apeiria/app/ai/reply_strategy/  (initiative, wake)     │
├─────────────────────────────────────────────────────────┤
│  Domain Services (stable, framework-agnostic)            │
│  apeiria/ai/          memory, knowledge, skills, tools   │
│  apeiria/access/      permissions, principals, groups    │
│  apeiria/conversation/  conversation state & history     │
├─────────────────────────────────────────────────────────┤
│  Persistence                                            │
│  apeiria/db/          SQLAlchemy models + Alembic        │
├─────────────────────────────────────────────────────────┤
│  Bot Integration Layer (NoneBot-aware code only)         │
│  apeiria/bot/         event handling, guards, rules      │
│  apeiria/builtin_plugins/  NoneBot plugins               │
├─────────────────────────────────────────────────────────┤
│  Infrastructure                                         │
│  apeiria/runtime/     bootstrapping, control plane       │
│  apeiria/config/      TOML config loading                │
│  apeiria/environment/ project health & compatibility     │
│  apeiria/cli/         CLI commands                       │
└─────────────────────────────────────────────────────────┘
```

### Layering Rules

| Layer | What belongs | What it must NOT import |
|-------|-------------|------------------------|
| **Domain** (`ai/`, `access/`, `conversation/`) | Business logic, models, repositories, services | NoneBot, FastAPI, WebSocket objects |
| **Application** (`app/`) | Orchestration, wiring, runtime pipelines | — (wires domain + framework layers) |
| **Bot** (`bot/`, `builtin_plugins/`) | NoneBot event extraction, guards, hooks, commands | — (NoneBot-aware code only here) |
| **WebUI** (`webui/`) | HTTP routes, schemas, auth | Domain services are fine; bot internals should not leak |
| **Infrastructure** (`runtime/`, `config/`, `db/`, `environment/`, `cli/`) | Cross-cutting concerns | — |

---

## 3. Development Setup

```bash
# 1. Install Python dependencies
uv sync --group dev

# 2. Initialize runtime files and extension environment
./.venv/bin/apeiria env init

# 3. Copy and customize config templates as needed
#    apeiria.config.example.toml      → apeiria.config.toml
#    apeiria.plugins.example.toml     → apeiria.plugins.toml
#    apeiria.adapters.example.toml    → apeiria.adapters.toml
#    apeiria.drivers.example.toml     → apeiria.drivers.toml
#    user_bot.example.py              → user_bot.py

# 4. Install frontend dependencies (optional, for Web UI development)
cd webui && pnpm install

# 5. Run the bot
./.venv/bin/apeiria run     # or: ./.venv/bin/python bot.py
```

---

## 4. Directory Map

```
apeiria/
├── access/               Permission & access control (principals, groups, audit)
├── ai/                   AI domain layer — knowledge, memory, skills, tools, personas
│   ├── knowledge/         Embedding-based knowledge store
│   ├── memory/            Long-term memory extraction & retrieval
│   ├── model/             Model adapters, catalog, routing, runtime clients
│   ├── persona/           Bot persona definitions & resolution
│   ├── profile/           User profiles
│   ├── prompting/         Prompt templates & rendering
│   ├── relationship/      User-bot relationship scoring
│   ├── retrieval/         Dense/sparse retrieval + rerank
│   ├── skills/            Skill catalog, loading, selection
│   └── tools/             Tool contracts, execution, function-calling schema
├── app/                  Application orchestration layer
│   ├── ai/runtime/        AI turn pipeline (planning → execution → commit)
│   ├── ai/reply_strategy/  Initiative detection, wake gate, social judgment
│   ├── ai/builtin_tools/  Built-in tool implementations (memory, knowledge, etc.)
│   ├── ai/future_tasks/   Scheduled task execution
│   ├── chat/              WebSocket chat gateway, message handling
│   ├── access/            Web UI auth, account management
│   └── plugins/           Plugin management, store integration
├── bot/                  NoneBot integration (event extraction, guards, hooks, rules)
├── builtin_plugins/      NoneBot plugins (admin, help, contact_approval, etc.)
├── cli/                  CLI entry point & subcommands
├── config/               TOML configuration loading
├── conversation/         Conversation state, identity, persistence
├── db/                   SQLAlchemy models, Alembic migrations
├── environment/          Project health, compatibility checks
├── i18n/                 Internationalization (zh_CN, en_US)
├── plugins/              Plugin registry, installation, state management
├── runtime/              Bootstrapping, control plane, phased startup
├── utils/                Shared utilities (statistics, time, files, JSON)
└── webui/                HTTP API routes, schemas, auth, frontend build

tests/                    pytest suite (mirrors apeiria/ layout)
webui/                    Vue 3 frontend (Vite + Tailwind + shadcn-vue)
  src/api/                HTTP client layer
  src/components/         Reusable components
  src/composables/        Vue composables
  src/pages/              Page components
  src/stores/             Pinia stores
  src/types/              TypeScript types
```

---

## 5. Build, Test, and Quality Commands

### Python

| Command | Purpose |
|---------|---------|
| `uv sync --group dev` | Install all dependencies |
| `./.venv/bin/apeiria run` | Start the bot |
| `./.venv/bin/python bot.py` | Start via compatibility entrypoint |
| `./.venv/bin/apeiria check` | Project health check |
| `./.venv/bin/apeiria status` | Runtime status |
| `uv run ruff check .` | Lint; run `--fix` to auto-fix |
| `uv run ruff format . --check` | Format validation; drop `--check` to apply |
| `uv run pyright` | Static type check (advisory) |
| `uv run pytest` | Full test suite |
| `uv run pytest tests/<path> -q` | Targeted test run |
| `uv run pre-commit run --all-files` | Run pre-commit hooks manually |

### Frontend

| Command | Purpose |
|---------|---------|
| `pnpm install` | Install dependencies (in `webui/`) |
| `pnpm dev` | Dev server with HMR |
| `pnpm build` | Production build |
| `pnpm lint` | ESLint |

### CI (GitHub Actions)

CI enforces `ruff check`, `ruff format --check`, and `pnpm build` on every push and PR. Pyright runs but does not block (advisory).

---

## 6. Python Coding Standards

### General Style

- **Target:** Python 3.10+ (do not use 3.11+ syntax unless guarded)
- **Indentation:** 4 spaces
- **Line length:** 88 characters (matching ruff config)
- **Quotes:** Double quotes preferred (enforced by ruff Q rule)
- **Line endings:** LF (enforced by ruff format)
- **No dead code:** Ruff `ERA` is disabled but the principle holds — remove, don't comment out

### Lint Rules

The project uses an extensive Ruff ruleset covering: Pyflakes (F), pycodestyle (E/W), isort (I), pep8-naming (N), pylint (PL), pyupgrade (UP), flake8-annotations (ANN), flake8-bugbear (B), flake8-comprehensions (C4), flake8-import-conventions (ICN), flake8-simplify (SIM), tryceratops (TRY), refurb (FURB), FastAPI (FAST), Perflint (PERF), and more.

**Explicit ignores** (do not fight these):
- `E402` — NoneBot `require()` pattern requires top-level imports after plugin declarations
- `B008` — NoneBot `Depends()` without `Annotated`
- `ANN202` — Private function return annotations are optional

### Naming Conventions

- Modules: `snake_case`, one concern per file
- Helper modules: descriptive role names (`registry.py`, `policy.py`, `catalog.py`, `repository.py`) — avoid generic `*_service.py` suffixes for new modules
- Classes: `PascalCase`
- Functions/methods/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private members: prefix with single underscore `_`

### Imports

- Use explicit imports; do not add lazy `__getattr__` exports in `__init__.py`
- Organize: stdlib → third-party → first-party (enforced by isort via ruff)
- Use `from apeiria.xxx import yyy` for internal imports; avoid relative imports across domain boundaries
- Prefer importing from concrete modules rather than package-root compatibility re-exports

### Type Annotations

- Public functions and methods must have type annotations (enforced by ruff ANN rules)
- Use `| None` syntax (Python 3.10+); do not use `Optional[...]`
- Use `list[T]`, `dict[K, V]` (not `List`, `Dict` from `typing`) — enforced by pyupgrade
- Type-check with `uv run pyright`; the config uses `typeCheckingMode = "standard"`

---

## 7. Module Organization Rules

### When creating new modules:

1. **Identify the domain** — Is it AI logic, access control, bot integration, or infrastructure?
2. **Keep one concern per file** — If a file does two things, split it
3. **Match neighboring conventions** — Look at existing modules in the same directory for patterns
4. **Stable vs. volatile separation** — `apeiria/ai/` and `apeiria/access/` are relatively stable domain roots; new capabilities start there. Application wiring, orchestration, and NoneBot integration go in `apeiria/app/` and `apeiria/bot/` respectively.

### Module size guidelines:
- Prefer many small, focused modules over a few large ones
- If a module exceeds ~500 lines, consider whether it can be split into a sub-package

---

## 8. Testing Guidelines

### Structure

- Place tests in `tests/` mirroring the `apeiria/` package layout
- Name test files `test_*.py` and test functions `test_*`
- Use `tests/conftest.py` for shared fixtures
- Helper files like `tests/db_helpers.py` and `tests/plugins/nonebot_helpers.py` provide test utilities — extend these rather than duplicating

### Running Tests

```bash
uv run pytest                          # Full suite
uv run pytest tests/db/ -q             # Specific directory
uv run pytest tests/db/test_schema.py -q  # Single file
uv run pytest -k "test_name_pattern"   # By name pattern
```

### Writing Tests

- Use pytest fixtures for setup; avoid class-based tests unless grouping is essential
- Test business logic against domain services, not against framework objects
- For NoneBot plugin tests, use `nonebug` (already a dev dependency)
- Mock external API calls; tests should not require network access
- Database tests use SQLite in-memory or temp files

### Pre-commit & CI

- Run `uv run ruff check . && uv run ruff format . --check && uv run pyright` before pushing
- All tests must pass in CI; pyright is advisory (failures do not block)

---

## 9. Version Control

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <imperative summary>
```

Types: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`, `perf`, `ci`, `build`

Common scopes: `webui`, `db`, `ai`, `bot`, `runtime`, `cli`, `plugins`, `config`

Examples:
- `feat(ai): add memory extraction governance policy`
- `refactor(db): normalise session timestamp columns`
- `fix(webui): restore theme persistence across page reloads`

### Pull Requests

- Summarize behavior changes and reasoning
- Note any config or migration impact
- List the verification commands you ran (`uv run pytest`, `uv run ruff check .`, `uv run pyright`)
- Include screenshots or screen recordings for Web UI changes
- Keep PRs focused; prefer multiple small PRs over monolithic ones

### What NOT to Commit

- **Never commit secrets, tokens, or API keys** — use `.env*` files (gitignored)
- **Never commit local config files** (`apeiria.*.toml` without `.example`, `user_bot.py`)
- **Never commit generated files** (`.apeiria/`, `data/`, `dist/`, `__pycache__`)
- Run `git status` before committing and review the diff

---

## 10. Configuration & Secrets

### Config File Flow

| Example Template | Local Copy (gitignored) | Purpose |
|-----------------|------------------------|---------|
| `apeiria.config.example.toml` | `apeiria.config.toml` | Main bot configuration |
| `apeiria.plugins.example.toml` | `apeiria.plugins.toml` | Plugin declarations |
| `apeiria.adapters.example.toml` | `apeiria.adapters.toml` | Adapter declarations |
| `apeiria.drivers.example.toml` | `apeiria.drivers.toml` | Driver declarations |
| `user_bot.example.py` | `user_bot.py` | Local startup hooks |

- When adding new config options, update the relevant `.example.toml` template
- Use `.env` for sensitive values; `.env.dev` and `.env.prod` provide environment-specific defaults

---

## 11. WebUI (Frontend) Conventions

### Tech Stack

- **Framework:** Vue 3 (Composition API with `<script setup lang="ts">`)
- **Language:** TypeScript (strict)
- **Styling:** Tailwind CSS + shadcn-vue component library
- **State:** Pinia stores (`webui/src/stores/`)
- **Routing:** Vue Router (`webui/src/router/`)
- **Build:** Vite

### Code Style

- 2-space indentation
- Composables go in `webui/src/composables/`
- API client modules go in `webui/src/api/`
- Reusable components go in `webui/src/components/`

### Build Verification

```bash
cd webui
pnpm install --frozen-lockfile
pnpm build
```

---

## 12. Pre-commit Hooks

The project uses `pre-commit` with [ruff-pre-commit](https://github.com/astral-sh/ruff-pre-commit):

- `ruff-check` — lint with auto-fix
- `ruff-format` — format enforcement

Install: `uv run pre-commit install`

---

## 13. Docker

Build and run via Docker Compose:

```bash
docker compose up --build    # Build and start (port 8080)
```

The multi-stage `Dockerfile` builds the frontend (Node 24) and packages it with the Python runtime (3.14.3-slim). See `docker-compose.yml` for service configuration.
