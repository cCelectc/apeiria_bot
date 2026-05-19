<div align="center">

# 帮助系统

_✨ Apeiria 面向用户的帮助菜单入口 ✨_

</div>

## 📖 介绍

这是 Apeiria 的内置帮助插件，用于把当前机器人已经接入的功能整理成用户菜单入口。

适合这些场景：

- 给普通用户提供统一的功能菜单入口
- 展示插件说明、命令别名与功能摘要
- 让主人快速查看某个插件的大致用途

## 💿 安装

<details open>
<summary>作为 Apeiria 内置插件使用</summary>

帮助系统为 Apeiria 内置插件，默认随框架加载，无需单独安装。

如果你关闭了此插件，可在项目插件配置中重新启用：

    apeiria.builtin_plugins.help

</details>

## ⚙️ 配置

在 Apeiria 的插件配置中，`help` 现在按分组组织，常用配置更集中：

| 配置组 | 说明 |
|:---:|:---:|
| `appearance` | 菜单标题、副标题、主色、是否展开命令 |
| `visibility` | 是否显示内建插件、隐藏哪些插件 |
| `roles` | 是否启用分身份视图、视图模式、不同身份标题、Owner 是否默认看全量 |
| `assets` | 横幅、Logo、页脚、字体相关设置 |
| `render` | 自定义模板、磁盘缓存、调试开关 |
| `plugin_overrides` | 为旧插件手动补充显示名、描述、分类标签、排序、补充命令 |

推荐直接使用分组后的结构，例如：

```yaml
help:
  appearance:
    title: 帮助菜单
    subtitle: 发送 /help <插件名> 查看详细命令
    accent_color: "#4e96f7"
  visibility:
    hidden_plugins:
      - apeiria.builtin_plugins.help
  roles:
    enabled: true
    mode: auto
    owner_sees_all: true
    admin_title: 管理菜单
  assets:
    footer_text: Apeiria
  render:
    disk_cache: true
  plugin_overrides:
    - plugin_name: nonebot_plugin_status
      display_name: 状态查看
      description: 查看机器人运行状态
      category: 系统工具
      extra_commands:
        - status|查看运行状态
```

如果某些旧式 NoneBot 插件缺少完整元数据，可以通过 `plugin_overrides`
手动补齐展示信息。推荐直接填写插件模块名，例如
`nonebot_plugin_status` 或 `apeiria.builtin_plugins.help`。

其中 `extra_commands` 的每一项格式为：

```text
命令名|描述|前缀
```

- `命令名` 必填
- `描述` 可选
- `前缀` 可选，不填时使用系统默认前缀

例如：

```yaml
plugin_overrides:
  - plugin_name: nonebot_plugin_status
    extra_commands:
      - status
      - status|查看运行状态
      - ping|检查连通性|/
```

## 🎉 使用

### 指令表

| 指令 | 权限 | 需要@ | 范围 | 说明 |
|:---:|:---:|:---:|:---:|:---:|
| `/help` | 全部用户 | 否 | 群聊 / 私聊 | 查看帮助菜单 |
| `/help <插件名>` | 全部用户 | 否 | 群聊 / 私聊 | 查看指定插件详情 |
| `/help --admin` | 管理视图可用用户 | 否 | 群聊 / 私聊 | 查看管理视图帮助 |
| `/help --all` | 主人 | 否 | 群聊 / 私聊 | 查看完整帮助 |

帮助系统会根据当前会话身份自动选择用户视图、管理视图或 Owner 视图。
如果将 `roles.mode` 设为 `manual_only`，则默认只显示普通用户视图，需要通过参数显式切换。

## 注意

- 帮助系统依赖 `apeiria.builtin_plugins.render`。
- 如果统一渲染服务不可用，帮助菜单将无法正常生成图片。
- 在项目功能尚未稳定时，可以先关闭此插件，待功能整理完成后再启用。
