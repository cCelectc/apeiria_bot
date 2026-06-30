# Apeiria Bot

基于 [NoneBot 2](https://nonebot.dev/) 的实例化机器人框架，提供项目化管理、YAML 配置体系、插件环境隔离和 Web UI。

## 前置要求

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) 包管理器
- [playwright](https://playwright.dev/) 浏览器（htmlrender 插件需要）

## 快速开始

```bash
# 安装依赖
uv sync

# 安装 playwright 浏览器
uv run playwright install chromium

# 初始化项目环境
uv run apeiria init

# 编辑配置文件 data/config.yaml

# 启动
uv run apeiria run
```

## Docker 部署

```bash
# 构建并启动
docker compose up -d --build

# 查看日志
docker compose logs -f

# 停止
docker compose down
```

Docker 部署前，请确保 `data/config.yaml` 已正确配置。

## 配置

所有配置集中在 `data/config.yaml`，分为四块：

| 块 | 说明 |
|----|------|
| `nonebot` | NoneBot 框架配置（host/port/superusers 等） |
| `plugins` | 插件配置 |
| `adapters` | 适配器配置 |
| `apeiria` | 框架自身配置（数据库路径、Web 端口等） |

## 开发

```bash
# 代码检查
uv run ruff check .

# 类型检查
uv run pyright

# 运行测试
uv run pytest

# 生成数据库迁移
uv run alembic revision --autogenerate -m "description"

# 执行数据库迁移
uv run alembic upgrade head
```

## 许可

[MIT](LICENSE)
