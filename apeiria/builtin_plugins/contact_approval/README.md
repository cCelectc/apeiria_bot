<div align="center">

# 关系审批

_✨ Apeiria 面向主人和群管理的关系请求审批入口 ✨_

</div>

## 📖 介绍

这是 Apeiria 的内置基础功能插件，用于把好友申请、机器人入群邀请、
群成员加群申请整理成可追踪的审批卡片。

插件关注三类场景：

- 用户申请添加机器人好友：发送给主人私聊审批
- 用户邀请机器人加入新群：发送给主人私聊审批
- 用户申请加入机器人已在的群：按群黑白名单决定是否在群内发送审批

当前 provider 面向 OneBot v11 兼容 QQ 部署。未支持的平台仍可加载本插件，
但不会执行关系审批动作。

审批票据会通过 `nonebot-plugin-localstore` 写入本插件数据目录，只保存处理审批
所需的 bounded 字段，不保存原始事件 payload。

## 💿 安装

<details open>
<summary>作为 Apeiria 内置插件使用</summary>

关系审批为 Apeiria 内置插件，默认随框架加载，无需单独安装。

如果你关闭了此插件，可在项目插件配置中重新启用：

    apeiria.builtin_plugins.contact_approval

</details>

## ⚙️ 配置

在 Apeiria 的插件配置中可调整以下配置项：

| 配置项 | 必填 | 默认值 | 说明 |
|:---:|:---:|:---:|:---:|
| `owner_targets` | 否 | `[]` | 主人私聊目标，格式如 `qq:123456`；留空时尝试从 NoneBot `superusers` 推导 QQ 号 |
| `friend_requests_enabled` | 否 | `true` | 是否处理好友申请 |
| `bot_group_invites_enabled` | 否 | `true` | 是否处理机器人入群邀请 |
| `group_join_requests_enabled` | 否 | `true` | 是否处理群成员加群申请 |
| `group_join_gate_mode` | 否 | `whitelist` | 群成员加群申请通知门禁，支持 `whitelist` / `blacklist` |
| `group_join_gate_ids` | 否 | `[]` | 门禁群号列表 |
| `suppressed_group_join_action` | 否 | `ignore` | 群成员申请被门禁静默时本地忽略或平台拒绝 |
| `suppressed_group_join_reject_reason` | 否 | 空 | 静默动作设为拒绝时传给平台的拒绝理由 |
| `ticket_expiration_minutes` | 否 | `720` | 审批票据过期分钟数 |
| `approval_prefix` | 否 | `审批` | 列出待处理审批的触发词 |
| `missing_target_reply` | 否 | 内置文案 | 未引用审批卡片且未带编号时的提示 |
| `ticket_not_found_reply` | 否 | 内置文案 | 审批编号不存在时的提示 |
| `unauthorized_reply` | 否 | 内置文案 | 无权限处理审批时的提示 |
| `platform_failed_reply` | 否 | 内置文案 | 平台审批 API 调用失败时的提示 |

示例：

```yaml
contact_approval:
  owner_targets:
    - qq:123456
  friend_requests_enabled: true
  bot_group_invites_enabled: true
  group_join_requests_enabled: true
  group_join_gate_mode: whitelist
  group_join_gate_ids:
    - "987654321"
  suppressed_group_join_action: ignore
  ticket_expiration_minutes: 720
```

默认 `whitelist + []` 表示不会向任何群发送群成员加群审批卡片，避免打扰。
黑白名单只控制“是否通知群内审批”，不代表自动同意。

## 🎉 使用

### 审批卡片

审批卡片会带短编号，例如：

```text
[好友审批 #F4K9] 待处理
申请人：小明 / 123456
验证信息：我是群友介绍来的

操作：引用本消息回复 同意 / 拒绝 原因 / 忽略 / 详情
也可发送：同意 #F4K9 / 拒绝 #F4K9 原因 / 忽略 #F4K9 / 详情 #F4K9
```

支持的操作：

### 指令表

| 指令 | 权限 | 需要@ | 范围 | 说明 |
|:---:|:---:|:---:|:---:|:---:|
| `审批` | 场景相关 | 否 | 群聊 / 私聊 | 查看当前场景待处理审批 |
| `同意 #编号` | 场景相关 | 否 | 群聊 / 私聊 | 同意指定审批 |
| `拒绝 #编号 原因` | 场景相关 | 否 | 群聊 / 私聊 | 拒绝指定审批 |
| `忽略 #编号` | 场景相关 | 否 | 群聊 / 私聊 | 本地关闭指定审批，不调用平台审批 API |
| `详情 #编号` | 场景相关 | 否 | 群聊 / 私聊 | 查看审批详情 |

也可以直接引用审批卡片发送：

```text
同意
拒绝 不认识
忽略
详情
```

没有引用审批卡片且没有带编号时，`同意` / `拒绝` / `忽略` / `详情`
不会执行，避免误批。

## 注意

- 机器人入群邀请只允许主人处理。
- 群成员加群申请可由主人、NoneBot superuser、目标群群主或管理员处理。
- 当前只支持 OneBot v11 关系请求事件和对应审批 API。
- `owner_targets` 留空时只会尝试从 `onebotv11:<QQ号>` 或纯数字格式的
  NoneBot `superusers` 推导主人 QQ 目标。
- 审批票据存储在 `nonebot-plugin-localstore` 提供的插件数据目录。
- `忽略` 只关闭本地审批票据，不调用平台同意或拒绝 API。
- 平台失败时会给出可恢复提示，不会在聊天里暴露完整异常或凭据。
