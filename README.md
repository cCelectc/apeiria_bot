<div align="center">

# Apeiria Bot

✨ 基于 NoneBot 2 的项目化机器人框架 ✨

[NoneBot 官网](https://nonebot.dev/) · [驱动文档](https://nonebot.dev/docs/advanced/driver) · [适配器文档](https://nonebot.dev/docs/advanced/adapter) · [配置文档](https://nonebot.dev/docs/appendices/config)

</div>

## 简介

Apeiria 基于 [NoneBot 2](https://nonebot.dev/) 构建，在 NoneBot 的驱动、适配器、插件体系之上，补充了更适合长期维护的项目层能力：拆分式配置、双环境管理、内置管理插件、Web UI、插件商店接入和宿主机 CLI。

## 特色

- 项目化配置：把核心配置、插件、适配器、驱动拆分到独立 TOML 文件，降低长期维护成本
- 双环境管理：Apeiria 项目环境与扩展环境分离，减少主环境污染
- 开箱可管理：内置聊天管理命令、帮助系统、统一渲染服务和 Web UI
- 基于 NoneBot 生态：底层沿用 NoneBot 2 的驱动、适配器、插件机制，项目侧统一通过 Apeiria CLI 与 Web UI 管理
- 同时面向运维和开发：既有浏览器管理面板，也有宿主机 CLI

## 与 NoneBot 的关系

- NoneBot 2 提供事件驱动框架、驱动、适配器和插件生态
- Apeiria 提供项目组织、配置管理、运行时管理和可视化运维能力
- 驱动统一通过 `apeiria.drivers.toml` 管理
- 适配器统一通过 `apeiria.adapters.toml` 管理
- 插件统一通过 `apeiria.plugins.toml`、CLI 和 Web UI 管理
- 项目配置统一通过 `apeiria.config.toml` 管理

NoneBot 官方文档可作为本项目的基础参考：

- 官方首页：<https://nonebot.dev/>
- 驱动说明：<https://nonebot.dev/docs/advanced/driver>
- 适配器说明：<https://nonebot.dev/docs/advanced/adapter>
- 配置相关：<https://nonebot.dev/docs/appendices/config>

## 当前能力

Apeiria 提供这些核心能力：

- 基于 NoneBot 2 的机器人运行入口与项目化启动流程
- 按职责拆分的项目配置文件：核心配置、插件、适配器、驱动分别管理
- 双环境管理：Apeiria 项目环境与 `.apeiria/extensions` 扩展环境分离
- 内置插件：`apeiria.builtin_plugins.admin`、`apeiria.builtin_plugins.help`、`apeiria.builtin_plugins.render`、`apeiria.builtin_plugins.web_ui`
- Web UI：仪表盘、核心配置编辑、插件启停与配置编辑、插件商店、权限管理、日志、Web Chat、账户管理
- 宿主机 CLI：环境初始化、修复、导入导出、健康检查，驱动、适配器、插件管理，Web UI 账户恢复与注册码管理

## 项目结构

```text
.
├── apeiria/
│   ├── bootstrap.py              # NoneBot 启动编排：配置 → 框架 → 用户插件
│   ├── bot/                      # Bot 入口与系统级钩子
│   ├── config/                   # 项目 / 插件 / 适配器 / 驱动 TOML 服务
│   ├── db/                       # ORM、迁移与运行期数据库预检
│   ├── access/                   # 权限、规则、审计、Web UI 认证
│   ├── plugins/                  # 插件治理、目录、安装、配置、商店
│   ├── environment/              # `uv` 环境、健康检查、前端构建
│   ├── webui/                    # FastAPI 管理后端与 Schema
│   ├── chat/                     # Web Chat 平台适配层
│   ├── ai/                       # AI 能力域（会话 / 记忆 / 工具 / Persona）
│   ├── builtin_plugins/          # 内置 NoneBot 插件
│   ├── cli/                      # 宿主机 CLI
│   ├── i18n/                     # 国际化运行时
│   ├── utils/                    # 跨领域工具
│   ├── _framework_loader.py      # 框架层加载辅助
│   └── _user_loader.py           # 用户插件加载辅助
├── web/                          # 默认 Vue 3 + Vuetify Web UI 工作区
├── tests/                        # Python 测试
├── bot.py                        # Bot 运行入口
├── user_bot.example.py           # 本地自定义启动扩展示例
└── apeiria.*.example.toml        # 配置模板
```

## 快速开始

### 环境要求

- Python `>=3.10, <4.0`
- `uv`
- Node.js
- `pnpm`

说明：

- 后端环境初始化依赖 `uv`
- 如果仓库内没有现成的 `web/dist`，首次本地运行或前端开发需要 Node.js 和 `pnpm`
- 渲染相关功能依赖 Playwright

### 1. 准备配置文件

```bash
cp apeiria.config.example.toml apeiria.config.toml
cp apeiria.plugins.example.toml apeiria.plugins.toml
cp apeiria.adapters.example.toml apeiria.adapters.toml
cp apeiria.drivers.example.toml apeiria.drivers.toml
cp user_bot.example.py user_bot.py
```

`.env`、`.env.dev`、`.env.prod` 可为空文件，`apeiria env init` 会自动补齐。`apeiria env init` 不会创建 `apeiria.*.toml`，这些文件需要先从示例模板复制。

### 2. 初始化运行环境

```bash
uv sync
./.venv/bin/apeiria env init
```

`apeiria env init` 会同步 Apeiria 项目环境、创建 `.apeiria/extensions` 扩展环境、同步扩展环境依赖，并补齐运行期需要的 `.env` 文件。

### 3. 启动项目

```bash
./.venv/bin/apeiria run
```

需要先构建前端资源时，可执行：

```bash
./.venv/bin/apeiria run --build
```

也可以直接运行入口文件：

```bash
./.venv/bin/python bot.py
```

## Web UI

默认访问地址：

```text
http://127.0.0.1:8080/
```

首次使用前，建议在宿主机创建或恢复一个 Owner 账号：

```bash
./.venv/bin/apeiria webui recover
```

常用命令：

```bash
./.venv/bin/apeiria webui accounts list
./.venv/bin/apeiria webui accounts create
./.venv/bin/apeiria webui codes create --role owner
```

## 配置文件说明

配置文件请直接参考仓库中的示例文件：

- `apeiria.config.example.toml`
- `apeiria.plugins.example.toml`
- `apeiria.adapters.example.toml`
- `apeiria.drivers.example.toml`

### `user_bot.py`

本地项目扩展入口，仅用于用户自定义启动逻辑，适合放这些内容：

- 启动与关闭生命周期钩子
- 项目私有初始化逻辑
- 少量不适合进入项目配置面的自定义注入逻辑

不推荐把驱动、适配器、插件等项目级配置写在这里。这些内容应优先通过 Web UI 或 `apeiria.*.toml` 管理。

这个文件默认不纳入仓库版本控制，适合承载本地定制。

## Apeiria 与 NoneBot 的协作方式

Apeiria 的启动流程如下：

1. 启动前先整理 Apeiria 的项目配置、项目环境和扩展环境。
2. 用 `apeiria.config.toml` 与环境变量生成 `nonebot.init(...)` 参数。
3. 继续完成 NoneBot 初始化与框架层加载。
4. 加载框架依赖插件和 Apeiria 内置插件。
5. 执行 `user_bot.py` 中的本地自定义钩子。
6. 从 `apeiria.adapters.toml` 注册适配器。
7. 从 `apeiria.plugins.toml` 加载用户插件。

项目约定如下：

- 项目配置、插件、适配器、驱动统一通过 `apeiria.*.toml` 管理
- 安装、启停、更新、排障优先使用 Apeiria CLI 和 Web UI
- `user_bot.py` 仅用于钩子注入和其他少量自定义需求

## 常用 CLI

查看主命令：

```bash
./.venv/bin/apeiria --help
```

环境相关：

```bash
./.venv/bin/apeiria env init
./.venv/bin/apeiria env repair
./.venv/bin/apeiria env doctor
./.venv/bin/apeiria env info
./.venv/bin/apeiria check
./.venv/bin/apeiria status
```

插件、适配器、驱动：

```bash
./.venv/bin/apeiria plugin list
./.venv/bin/apeiria plugin store
./.venv/bin/apeiria plugin install --store

./.venv/bin/apeiria adapter list
./.venv/bin/apeiria adapter install --store

./.venv/bin/apeiria driver list
./.venv/bin/apeiria driver install --store
```

## Docker 运行

仓库自带 `Dockerfile` 和 `docker-compose.yml`。镜像构建阶段会先打包 `web/dist`，容器启动时不会再做前端构建；容器内执行的命令等价于：

```bash
APEIRIA_BUILD_FRONTEND_ON_START=false .venv/bin/apeiria env init --no-dev
APEIRIA_BUILD_FRONTEND_ON_START=false .venv/bin/apeiria run
```

`docker-compose.yml` 会挂载这些运行期文件：

- `./.apeiria`
- `./data`
- `./apeiria.config.toml`
- `./apeiria.plugins.toml`
- `./apeiria.adapters.toml`
- `./apeiria.drivers.toml`
- `./.env`
- `./.env.dev`
- `./.env.prod`

启动：

```bash
docker compose up -d --build
```

默认暴露端口：

```text
8080
```

`docker-compose.yml` 同时设置了 `HOST=0.0.0.0`，因此宿主机可直接访问 `http://127.0.0.1:8080/`。

## 前端开发

Web UI 使用 Vue 3 + Vuetify。

默认前端工作区为 `web/`。如需切换到其他实验性前端目录，可设置环境变量 `APEIRIA_WEBUI_FRONTEND_DIR=<目录名>`。

```bash
cd web
pnpm install
pnpm lint
pnpm type-check
pnpm build
```

## 什么不是 Apeiria

- Apeiria 不是对 NoneBot 2 的替代，而是基于 NoneBot 2 的项目封装层
- Apeiria 不是某个平台协议的具体实现，平台接入能力仍来自对应适配器
- Apeiria 不试图屏蔽 NoneBot 原生概念；驱动、适配器、插件仍然是理解项目的基础

## 开发建议

- 涉及框架基础概念时，优先参考 NoneBot 官方文档
- 新增插件或依赖时，先确认它应进入 Apeiria 项目环境还是扩展环境
- 修改核心事件处理时，避免在核心逻辑中直接依赖特定适配器类型
- 对外说明优先写在插件 README 或主 README，避免能力只存在于代码中

## 参考资料

- NoneBot 官方站点：<https://nonebot.dev/>
- NoneBot 驱动：<https://nonebot.dev/docs/advanced/driver>
- NoneBot 适配器：<https://nonebot.dev/docs/advanced/adapter>
- NoneBot 配置：<https://nonebot.dev/docs/appendices/config>

## 许可协议

[MIT](LICENSE)
