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

RUN pip install uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY . .

COPY --from=webui /webui/dist ./webui/dist

EXPOSE 8080

CMD ["uv", "run", "apeiria", "run"]
