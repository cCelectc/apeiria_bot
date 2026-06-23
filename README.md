<div align="center">

# Apeiria Bot

基于 NoneBot 2 的项目化机器人框架。

</div>

## 快速开始

```bash
uv run apeiria run
```

热重载：

```bash
uv run apeiria run --reload
```

> 也可以手动分步执行：`uv run apeiria env init` → `uv run apeiria run`

## 数据库维护

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
