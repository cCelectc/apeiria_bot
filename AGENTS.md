# Repository Guidelines

## Project Structure & Module Organization

`apeiria/` is the main Python package. Keep work organized by concern: `access/`, `ai/`, `bot/`, `cli/`, `config/`, `db/`, `environment/`, `plugins/`, `runtime/`, and `webui/` each own a functional domain. `bootstrap.py` remains the compatibility entrypoint, but new project-level startup and orchestration logic should prefer `apeiria/runtime/*`. Put project entry normalization in `apeiria/runtime/entries.py`. For management-facing behavior, prefer `ApeiriaControlPlane` over route-local service wiring when that behavior is already represented as runtime-level coordination; current usage is especially on read-side paths. `webui/` contains the primary Vue + Tailwind/shadcn-vue Web UI, and `tests/` holds pytest coverage. Root-level `apeiria.*.example.toml` and `user_bot.example.py` are the templates contributors should copy for local setup.

## Build, Test, and Development Commands

Use `uv` for backend setup and `pnpm` for the frontend.

- `uv sync --group dev`: install backend and dev dependencies into `.venv`.
- `./.venv/bin/apeiria env init`: create runtime files and the extension environment.
- `./.venv/bin/apeiria run` or `./.venv/bin/python bot.py`: start the bot locally.
- `./.venv/bin/apeiria check` and `./.venv/bin/apeiria status`: project health checks.
- `uv run ruff check .` and `uv run ruff format . --check`: backend lint and format validation.
- `uv run pyright`: advisory static type check.
- `uv run pytest`: run the Python test suite.
- `cd webui && pnpm install && pnpm build`: install and build the primary Web UI.

## Coding Style & Naming Conventions

Target Python 3.10+, 4-space indentation, and Ruff’s 88-character line length. Prefer explicit imports; do not add lazy `__getattr__` exports. Follow the repo’s concern-oriented structure and keep one concern per module. New helper modules should use descriptive role names such as `registry.py`, `policy.py`, or `catalog.py`, not generic `*_service.py`. For Vue and TypeScript in `webui/`, match the existing 2-space indentation and keep composables in `webui/src/composables/`.

## Testing Guidelines

Place backend tests under `tests/` using `test_*.py` names. Current suites cover `cli/`, `db/`, and `runtime/`; extend nearby files when possible. Use targeted runs like `uv run pytest tests/db/test_runtime_preflight.py -q` during development, then finish with `uv run pytest`, `uv run ruff check .`, and `uv run pyright`.

## Commit & Pull Request Guidelines

Recent history follows Conventional Commit style such as `feat(webui): ...`, `refactor(db): ...`, and `chore: ...`. Keep subjects imperative and scoped when the area is clear. PRs should summarize behavior changes, note config or migration impact, list the verification commands you ran, and include screenshots for `webui/` UI changes.

## Security & Configuration Tips

Do not commit local secrets or machine-specific overrides. Start from `apeiria.config.example.toml`, `apeiria.plugins.example.toml`, `apeiria.adapters.example.toml`, `apeiria.drivers.example.toml`, and `user_bot.example.py`, then keep real values in local copies and `.env*` files.
