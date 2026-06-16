<div align="center">

# Apeiria Bot

✨ 基于 NoneBot 2 的项目化机器人框架，内置 WebUI。 ✨

</div>

## 快速开始

首次运行会自动初始化环境、建库、构建前端：

```bash
uv run apeiria run
```

热重载：

```bash
uv run apeiria run --reload
```

> 也可以手动分步执行：`uv run apeiria env init` → `uv run apeiria run --build`

## 使用

Web UI 默认 `http://127.0.0.1:8080`，首次使用创建 Owner 账号：

```bash
uv run apeiria webui recover
```

数据库维护：

```bash
uv run apeiria db check
uv run apeiria db repair
```

## Docker

```bash
docker compose up -d --build
```

## 许可

[MIT](LICENSE)
