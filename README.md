<div align="center">

# Apeiria Bot

✨ 基于 NoneBot 2 的项目化机器人框架 ✨

</div>

## 特点

- 多文件项目配置：核心配置、插件、适配器、驱动分别通过独立 TOML 文件管理
- 内置 Web UI：提供插件管理、权限管理、日志查看与 Web Chat 等浏览器管理界面
- 项目数据本地保存：Apeiria 自身状态写入 `data/db/apeiria.sqlite3`

## 快速开始

### 1. 初始化环境

```bash
uv sync
./.venv/bin/apeiria env init
```

### 2. 启动项目

```bash
./.venv/bin/apeiria run
```

开发时可以指定入口文件或启用重载：

```bash
./.venv/bin/apeiria run --entry user_bot.py --reload
```

也可以直接运行：

```bash
./.venv/bin/python bot.py
```

## CLI 运维

宿主机侧命令可以用 `--cwd` 指定 Apeiria 项目根目录，并在检查类命令中用
`--json` 输出机器可读结果：

```bash
./.venv/bin/apeiria --cwd /path/to/project status --json
./.venv/bin/apeiria env info --json
./.venv/bin/apeiria env doctor --json
```

数据库状态可以直接检查或修复：

```bash
./.venv/bin/apeiria db status
./.venv/bin/apeiria db check --json
./.venv/bin/apeiria db repair
```

## Web UI

默认访问地址：

```text
http://127.0.0.1:8080/
```

首次使用前，建议先恢复或创建一个 Owner 账号：

```bash
./.venv/bin/apeiria webui recover
```

## Docker

启动：

```bash
docker compose up -d --build
```

默认端口：

```text
8080
```

## 许可协议

[MIT](LICENSE)
