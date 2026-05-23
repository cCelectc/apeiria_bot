<div align="center">

# 联系主人

_✨ Apeiria 面向用户的主人留言入口 ✨_

</div>

## 📖 介绍

这是 Apeiria 的内置基础功能插件，用于让用户通过指定前缀给主人留下留言。

适合这些场景：

- 用户遇到问题，希望给主人留下简短说明
- 群聊成员需要反馈机器人行为异常
- 主人希望公开一个低成本、低噪音的留言入口

插件只负责转发一条文本留言，不提供工单、数据库、主人回复用户或 AI 工具能力。

## 💿 安装

<details open>
<summary>作为 Apeiria 内置插件使用</summary>

联系主人为 Apeiria 内置插件，默认随框架加载，无需单独安装。

如果你关闭了此插件，可在项目插件配置中重新启用：

    apeiria.builtin_plugins.contact_owner

</details>

## ⚙️ 配置

在 Apeiria 的插件配置中可调整以下配置项：

| 配置项 | 必填 | 默认值 | 说明 |
|:---:|:---:|:---:|:---:|
| `contact_prefix` | 否 | `联系主人` | 触发联系主人的文本前缀 |
| `owner_target` | 是 | 空 | 主人目标，格式为 `scope:id`，第一版支持 `qq:QQ号` |
| `minimum_message_length` | 否 | `0` | 留言正文必须超过该字符数才转发 |
| `success_reply` | 否 | 内置文案 | 留言转发成功时回复给用户 |
| `empty_message_reply` | 否 | 内置文案 | 留言为空时回复给用户 |
| `too_short_reply` | 否 | 内置文案 | 留言过短时回复给用户 |
| `owner_unconfigured_reply` | 否 | 内置文案 | 未配置主人目标时回复给用户 |
| `invalid_owner_target_reply` | 否 | 内置文案 | 主人目标格式错误时回复给用户 |
| `unsupported_platform_reply` | 否 | 内置文案 | 当前平台或目标 scope 不支持时回复给用户 |
| `delivery_failed_reply` | 否 | 内置文案 | 平台发送失败时回复给用户 |

示例：

```yaml
contact_owner:
  contact_prefix: 联系主人
  owner_target: qq:123456
  minimum_message_length: 5
```

## 🎉 使用

### 指令表

| 指令 | 权限 | 需要@ | 范围 | 说明 |
|:---:|:---:|:---:|:---:|:---:|
| `联系主人 <留言>` | 公开 | 否 | 群聊 / 私聊 | 把留言转发给配置的主人 |

其中 `联系主人` 以当前 `contact_prefix` 配置为准。

## 注意

- `owner_target` 必须显式配置，不会从 NoneBot `superusers` 推导。
- 第一版支持 `qq:<QQ号>`，由 OneBot v11 兼容 provider 发送私聊。
- 留言正文长度必须大于 `minimum_message_length`。
- 转发给主人时会附带可安全获取的来源信息，例如用户 ID、群 ID 和消息 ID。
- 插件不转发原始事件 payload、异常堆栈或凭据。
