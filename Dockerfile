# --- Frontend build stage ---
FROM node:24-slim AS webui

WORKDIR /webui

RUN npm install -g pnpm

COPY webui/package.json webui/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY webui/ ./
RUN pnpm build

# --- Runtime stage ---
FROM python:3.12-slim

ENV PIP_NO_CACHE_DIR=1
ENV UV_COMPILE_BYTECODE=1

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

COPY --from=webui /webui/dist ./webui/dist

RUN uv run playwright install chromium --with-deps

EXPOSE 8080

CMD ["uv", "run", "apeiria", "run"]
