<div align="center">

# 自助撤回

_✨ Apeiria 面向用户的机器人消息自助撤回入口 ✨_

</div>

## 📖 介绍

这是 Apeiria 的内置基础功能插件，用于让用户通过回复消息清理机器人自己发出的内容。

适合这些场景：

- 用户发现机器人回复有误，需要快速移除
- 群聊里机器人消息过长或过期，需要减少干扰
- 主人希望把撤回机器人消息的能力默认开放给普通用户

插件只会撤回平台能力提供者确认由当前机器人发送的消息。无法确认目标归属、平台不支持撤回或平台调用失败时，默认保持静默。

当前内置支持：

- OneBot v11
- OneBot v12
- Telegram
- Discord
- Feishu
- Satori（仅限回复目标包含作者元信息的消息）
- QQ 频道 / 公域消息

未列出的适配器仍可安装并正常启动；只是不会由本插件执行撤回。QQ C2C、QQ 群开放平台消息、Console、DoDo、Ding、Kaiheila 暂不撤回，因为当前核查到的可用事件模型不足以同时稳定提供回复目标、目标作者、当前机器人身份和撤回操作。

## 💿 安装

<details open>
<summary>作为 Apeiria 内置插件使用</summary>

自助撤回为 Apeiria 内置插件，默认随框架加载，无需单独安装。

如果你关闭了此插件，可在项目插件配置中重新启用：

    apeiria.builtin_plugins.self_revoke

</details>

## ⚙️ 配置

在 Apeiria 的插件配置中可调整以下配置项：

| 配置项 | 必填 | 默认值 | 说明 |
|:---:|:---:|:---:|:---:|
| `permission` | 否 | `public` | 使用权限，可选 `public` 或 `superuser` |
| `revoke_trigger_message` | 否 | `false` | 目标消息撤回成功后，是否尽力撤回用户发送的触发消息 |
| `feedback` | 否 | `silent` | 反馈方式，可选 `silent` 或 `reaction` |

示例：

```yaml
self_revoke:
  permission: public
  revoke_trigger_message: false
  feedback: silent
```

## 🎉 使用

### 指令表

| 指令 | 权限 | 需要@ | 范围 | 说明 |
|:---:|:---:|:---:|:---:|:---:|
| `撤回` | 配置决定 | 否 | 群聊 / 私聊 | 回复机器人消息，撤回该机器人消息 |
| `revoke` | 配置决定 | 否 | 群聊 / 私聊 | 回复机器人消息，撤回该机器人消息 |
| `/撤回` | 配置决定 | 否 | 群聊 / 私聊 | 使用命令前缀触发同一撤回流程 |
| `/revoke` | 配置决定 | 否 | 群聊 / 私聊 | 使用命令前缀触发同一撤回流程 |

其中 `/` 以当前项目配置的命令前缀为准。

## 注意

- 默认所有用户都可以撤回机器人自己发送的消息。
- 只会撤回确认由当前机器人发送的回复目标，不会默认撤回用户消息。
- 未回复消息时发送 `撤回` / `revoke` 不会静默消费，可继续交给其他处理器或 AI 说明用法。
- `revoke_trigger_message` 只在目标消息撤回成功后尽力撤回用户的触发消息。
- 同时启用 `feedback: reaction` 与 `revoke_trigger_message` 时，目标撤回成功后会优先撤回触发消息，不再对这条触发消息添加成功表情。
- `feedback: reaction` 依赖平台能力；当前仅 OneBot v11 提供尽力表情回应，失败表情使用 QQ 表情 `424`。
- 插件不接触 AI 层、对话记录或生成回复统计。
