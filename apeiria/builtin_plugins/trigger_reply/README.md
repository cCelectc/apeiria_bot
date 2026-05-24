<div align="center">

# 触发回复

_Apeiria 面向特征信息和戳一戳的规则回复插件_

</div>

## 介绍

触发回复是 Apeiria 内置基础功能插件，用于按独立 TOML 规则文件响应特定
消息文本和 OneBot v11 戳一戳通知，不接入 AI 层。

规则文件通过 `nonebot-plugin-localstore` 保存在本插件配置目录。规则文件不
存在时插件仍可加载，只是不响应任何规则。

## 配置

在 Apeiria 的插件配置中可调整以下全局配置：

| 配置项 | 必填 | 默认值 | 说明 |
|:---:|:---:|:---:|:---:|
| `enabled` | 否 | `true` | 是否启用触发回复 |
| `priority` | 否 | `12` | NoneBot matcher 优先级，修改后需重启生效 |
| `stop_propagation_on_match` | 否 | `true` | 成功发送至少一条回复后是否阻止后续插件处理同一事件 |
| `rules_file` | 否 | `rules.toml` | 本插件 localstore 配置目录下的规则文件相对路径 |
| `debug` | 否 | `false` | 启用后记录规则加载与事件跳过原因 |

示例：

```yaml
trigger_reply:
  enabled: true
  priority: 12
  stop_propagation_on_match: true
  rules_file: rules.toml
  debug: false
```

## 使用

| 行为 | 权限 | 需要@ | 范围 | 说明 |
|:---:|:---:|:---:|:---:|:---:|
| 配置消息命中 | 公开 | 配置决定 | 群聊 / 私聊 | 按规则文件中的文本或正则匹配发送文本回复 |
| OneBot v11 戳一戳命中 | 公开 | 否 | 群聊 / 私聊 | 按 `event = "qq.poke"` 发送文本回复 |
| `/重载回复` | NoneBot superuser | 否 | 群聊 / 私聊 | 重新读取规则文件并替换当前缓存 |
| `/tr` | NoneBot superuser | 否 | 群聊 / 私聊 | `/重载回复` 的英文别名 |

热重载只重载规则 TOML，不重载插件代码；重载后会清空内存 cooldown。如果新
规则文件是无效 TOML，插件会保留上一份可用规则。

规则文件写法见同目录的 `rules.example.toml`。示例以可复制 TOML 为主，注释
中说明了 match、event、reply、chance、scenes、groups、users、cooldown 和
变量的用法。
