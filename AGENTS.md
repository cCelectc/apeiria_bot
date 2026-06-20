# Apeiria Bot — Repository Guidelines

## 1. Project Overview

Apeiria is a Python chatbot framework built on [NoneBot2](https://nonebot.dev/) with an AI-augmented runtime, a Vue 3 + shadcn-vue Web UI, and SQLite-backed persistence. The project is organized as the `apeiria/` package with a CLI entry point (`apeiria`) and a growing suite of AI capabilities (agent lifecycle, ACP/MCP protocols, knowledge retrieval, tool use, persona management, relationship scoring).

- **Python:** 3.10+ (CI & Docker target 3.14)
- **Package manager:** `uv` (Python) / `pnpm` (frontend)
- **Database:** SQLite via SQLAlchemy (async) + Alembic migrations
- **Runtime:** NoneBot2 with OneBot adapter + custom AI orchestration pipeline

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  Web UI (Vue 3 + shadcn-vue + Tailwind CSS)             │
│  webui/src/  pages/  components/  composables/       │
├─────────────────────────────────────────────────────────┤
│  HTTP & WebSocket Layer                                  │
│  apeiria/webui/routes/  (FastAPI endpoints)              │
│  apeiria/webchat/       (WebSocket chat gateway)         │
├─────────────────────────────────────────────────────────┤
│  Domain Services (stable, framework-agnostic)            │
│  apeiria/ai/agent/     agent lifecycle, turn loop        │
│  apeiria/ai/acp/       Agent Communication Protocol      │
│  apeiria/ai/mcp/       Model Context Protocol            │
│  apeiria/ai/embedding/ embedding computation (FAISS)     │
│  apeiria/ai/knowledge/ RAG knowledge store               │
│  apeiria/ai/memory/    long-term memory extraction       │
│  apeiria/ai/model/     model routing, adapters           │
│  apeiria/ai/tools/     tool registry, builtin tools      │
│  apeiria/ai/skills/    skill catalog and loading         │
│  apeiria/ai/persona/   persona definitions               │
│  apeiria/ai/relationship/  user-bot relationship scoring │
│  apeiria/ai/rerank/    reranking adapters                │
│  apeiria/access/       permissions, principals, groups   │
│  apeiria/conversation/ conversation state, persistence   │
├─────────────────────────────────────────────────────────┤
│  Surface / Integration Layer                             │
│  apeiria/bot/          event handling, guards, rules      │
│  apeiria/builtin_plugins/  NoneBot plugins (admin, ai)   │
│  apeiria/plugins/      plugin management, store          │
├─────────────────────────────────────────────────────────┤
│  Persistence                                            │
│  apeiria/db/          SQLAlchemy models + Alembic        │
├─────────────────────────────────────────────────────────┤
│  Infrastructure                                         │
│  apeiria/runtime/     bootstrapping, control plane       │
│  apeiria/config/      TOML config loading, mutator       │
│  apeiria/environment/ project health, extensions          │
│  apeiria/cli/         CLI commands                       │
└─────────────────────────────────────────────────────────┘
```

### Layering Rules

| Layer | What belongs | What it must NOT import |
|-------|-------------|------------------------|
| **Domain** (`ai/agent/`, `ai/acp/`, `ai/mcp/`, `ai/embedding/`, `ai/knowledge/`, `ai/memory/`, `ai/model/`, `ai/tools/`, `ai/skills/`, `ai/persona/`, `ai/relationship/`, `ai/rerank/`, `access/`, `conversation/`) | Business logic, models, repositories, handlers | NoneBot, FastAPI, WebSocket objects |
| **Surface** (`bot/`, `builtin_plugins/`, `webui/`, `webchat/`, `plugins/`) | NoneBot event handling, HTTP routes, plugin management | — (framework-aware code lives here) |
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
├── ai/                   AI domain layer
│   ├── acp/               Agent Communication Protocol client & registry
│   ├── agent/             Agent lifecycle, turn loop, events, registry
│   ├── embedding/         Embedding computation & FAISS indexing
│   ├── knowledge/         RAG knowledge store, chunking, index build
│   ├── mcp/               Model Context Protocol client & registry
│   ├── memory/            Long-term memory handler
│   ├── model/             Model adapters, routing (resolve), entry/registry
│   ├── persona/           Bot persona definitions & handler
│   ├── relationship/      User-bot relationship scoring handler
│   ├── rerank/            Reranking adapter
│   ├── skills/            Skill catalog, handler, loading
│   ├── tools/             Tool registry, builtin tools, execution
│   └── types.py           Shared domain type definitions
├── bot/                  NoneBot integration (event extraction, guards, rules)
├── builtin_plugins/      NoneBot plugins (admin, ai, message_persist, web_ui)
├── cli/                  CLI entry point & subcommands
├── config/               TOML configuration loading, mutator
├── conversation/         Conversation state, identity, persistence
├── db/                   SQLAlchemy models, Alembic migrations
├── environment/          Project health, compatibility checks
├── i18n/                 Internationalization (zh_CN, en_US)
├── plugins/              Plugin registry, installation, state management
├── runtime/              Bootstrapping, control plane, phased startup
├── utils/                Shared utilities (statistics, time, files, JSON)
├── webchat/              WebSocket chat gateway, message handling, transport
└── webui/                HTTP API routes, schemas, auth, frontend build

tests/                    pytest suite (mirrors apeiria/ layout)
webui/                    Legacy web UI (deprecated)
webui/                 Vue 3 frontend (Vite + Tailwind + shadcn-vue)
  src/api/                HTTP client layer
  src/components/         Reusable components (ui/, shell/)
  src/composables/        Vue composables (TanStack Query wrappers)
  src/pages/              Page components (overview, runtime, system, etc.)
  src/router/             Vue Router configuration
  src/stores/             Pinia stores (auth, theme, toast, restart)
  src/types/              TypeScript types (generated from OpenAPI)
  src/utils/              Shared utilities (fastapiErrors, routeRedirect)
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
| `pnpm type-check` | TypeScript type check |
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
4. **Stable vs. volatile separation** — `apeiria/ai/` and `apeiria/access/` are stable domain roots; new capabilities start there. Framework-aware code goes in `apeiria/bot/`, `apeiria/builtin_plugins/`, `apeiria/webui/`, or `apeiria/webchat/`.

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
- `feat(ai): add memory handler`
- `refactor(db): normalise session timestamps`
- `fix(webui): restore theme persistence`

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
- **Styling:** Tailwind CSS 4 + shadcn-vue component library
- **State:** Pinia stores (client-only) + TanStack Query (server state)
- **Routing:** Vue Router (`webui/src/router/`)
- **Build:** Vite 8
- **Forms:** vee-validate + Zod (declarative, Field pattern)
- **Testing:** Vitest + jsdom

### Code Style

- 2-space indentation
- Composables go in `webui/src/composables/`
- API client modules go in `webui/src/api/`
- Reusable components go in `webui/src/components/`
- Form pattern: `useForm()` + `toTypedSchema(zodSchema)` + `<Field v-slot>` — never deprecated `<Form />`

### Build Verification

```bash
cd webui
pnpm install --frozen-lockfile
pnpm type-check
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
