<div align="center">

# QQ Tools

_✨ Apeiria 面向 AI 的 QQ 聊天动作工具包 ✨_

</div>

## 📖 介绍

这是 Apeiria 的内置 AI 能力插件，用于把少量 QQ 聊天动作以安全边界暴露给 AI 工具系统。

适合这些场景：

- AI 需要用轻量方式回应当前聊天参与者
- AI 需要对当前消息做一个简短表情回应
- 主人希望显式授权 AI 使用少量 QQ 平台侧动作

插件只提供当前会话相关的受限动作，不注册聊天命令，也不会把任意 QQ 或 OneBot API 暴露给 AI。

当前内置提供：

- `qq.poke`：戳一戳当前消息发送者
- `qq.react_to_message`：对当前或来源消息添加受限表情回应
- `qq-tools` AI skill：提示 AI 何时可以克制地使用这些工具

## 💿 安装

<details open>
<summary>作为 Apeiria 内置插件使用</summary>

QQ Tools 为 Apeiria 内置插件，默认随框架加载，无需单独安装。

如果你关闭了此插件，可在项目插件配置中重新启用：

    apeiria.builtin_plugins.qq_tools

</details>

## ⚙️ 配置

该插件目前无独立配置项。

工具是否会暴露给 AI，由现有 AI 工具策略控制。`qq.poke` 与
`qq.react_to_message` 都需要至少 `write` 级工具权限；默认群聊场景不会自动开放。

## 🎉 使用

### AI 工具表

| 工具 | 权限 | 需要 live 消息上下文 | 范围 | 说明 |
|:---:|:---:|:---:|:---:|:---:|
| `qq.poke` | `write` | 是 | 当前 QQ 会话 | 戳一戳当前消息发送者 |
| `qq.react_to_message` | `write` | 是 | 当前 QQ 会话 | 对当前或来源消息添加受限表情回应 |

### AI Skill

| Skill | 模式 | 关联工具 | 说明 |
|:---:|:---:|:---:|:---:|
| `qq-tools` | `prompt_only` | `qq.poke`, `qq.react_to_message` | 提醒 AI 仅在动作确实有价值时使用 QQ 工具 |

当前 provider 以 OneBot v11 兼容 QQ 部署为目标。平台不支持、缺少当前消息上下文、缺少目标数据或 API 调用失败时，工具会返回受限的 AI tool observation，不会额外发送聊天错误消息。

## 注意

- 这是 AI 工具插件，不提供用户可直接发送的聊天命令。
- `qq.poke` 不接受任意目标 ID，只作用于当前消息发送者。
- `qq.react_to_message` 不接受任意消息 ID，只作用于当前或来源消息。
- 插件不提供 `qq.call_api`、`onebot.call_api` 或其他泛用平台 API 桥。
- 如需新增 QQ 动作，应为每个动作单独设计工具 schema、权限级别、provider 方法和测试。
