FROM node:24-bookworm-slim AS web-builder

WORKDIR /frontend

RUN apt-get update \
    && apt-get install -y --no-install-recommends python-is-python3 \
    && npm install -g pnpm \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /root/.npm

COPY webui/package.json webui/pnpm-lock.yaml webui/pnpm-workspace.yaml ./webui/
COPY scripts ./scripts
COPY apeiria ./apeiria
WORKDIR /frontend/webui
RUN pnpm install --frozen-lockfile

COPY webui/ ./
RUN pnpm run build


FROM python:3.14.3-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        fontconfig \
        git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md bot.py ./
COPY apeiria ./apeiria
COPY --from=web-builder /frontend/webui/dist ./webui/dist

RUN uv sync --locked --no-dev
RUN .venv/bin/python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/.apeiria /app/data

EXPOSE 8080

CMD ["/bin/sh", "-lc", "APEIRIA_BUILD_FRONTEND_ON_START=false .venv/bin/apeiria env init --no-dev && exec env APEIRIA_BUILD_FRONTEND_ON_START=false .venv/bin/apeiria run"]
