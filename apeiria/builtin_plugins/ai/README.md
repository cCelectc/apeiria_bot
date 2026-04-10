<div align="center">

# AI 功能

_✨ Apeiria 的内置 AI 对话与配置插件 ✨_

</div>

## 📖 介绍

这是 Apeiria 的内置 AI 插件，用于承接 AI 对话运行链路，并提供配套的管理与调试入口。

它当前主要负责：

- 接收聊天事件并进入 AI 运行时
- 维护会话、人格、记忆、关系与模型选择链路
- 提供 AI 相关的 Web 管理与调试接口
- 为后续 AI 能力扩展保留统一边界

## 💿 安装

<details open>
<summary>作为 Apeiria 内置插件使用</summary>

AI 插件为 Apeiria 内置插件，默认随框架加载，无需单独安装。

如果你关闭了此插件，可在项目插件配置中重新启用：

    apeiria.builtin_plugins.ai

</details>

## ⚙️ 配置

该插件本身目前没有单独的轻量配置表；其行为主要依赖以下 AI 侧数据与配置：

- Provider 配置
- Model Profile 与 Binding
- Persona 与 Binding
- Tool Policy Binding
- 记忆与关系状态数据

日常管理建议通过 WebUI 的 AI 页面完成。

## 🎉 使用

### 基础检查

可使用以下命令检查插件是否已加载：

| 指令 | 权限 | 说明 |
|:---:|:---:|:---:|
| `/ai-status` | 超级用户 | 查看 AI 插件当前状态 |

### 运行方式

启用后，插件会在消息处理流程中接管 AI 回复路径。

如果同时启用了 WebUI，可在 AI 页面查看：

- 模型与 Provider
- Persona 与绑定
- 记忆查询
- 关系状态
- Tool Policy 与 Capability 预览
- Tool Execution 调试信息

## 注意

- 该插件当前更适合作为 AI 运行边界与管理入口，而不是独立的最终产品界面。
- 涉及模型、人格、工具策略等调整时，建议优先通过 WebUI 操作。
- 若依赖 AI 回复能力，请确保相关 Provider、Profile 与 Binding 已正确配置。
