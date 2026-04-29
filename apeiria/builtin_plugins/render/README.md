<div align="center">

# 统一渲染服务

_✨ Apeiria 的统一图片渲染基础插件 ✨_

</div>

## 📖 介绍

这是 Apeiria 的内置基础插件，负责为图片菜单、卡片、海报与页面截图提供统一渲染能力。

它主要负责：

- 把 HTML 渲染成图片
- 把模板页面渲染成图片
- 把 Markdown 渲染成图片
- 把网页截图成图片

如果你的机器人里有图片菜单、卡片消息、海报或截图功能，通常就会依赖它。

## 💿 安装

<details open>
<summary>作为 Apeiria 内置插件使用</summary>

统一渲染服务为 Apeiria 内置插件，默认随框架加载，无需单独安装。

如果你关闭了此插件，可在项目插件配置中重新启用：

    apeiria.builtin_plugins.render

</details>

## ⚙️ 配置

在 Apeiria 的插件配置中可调整以下常用选项：

| 配置项 | 必填 | 默认值 | 说明 |
|:---:|:---:|:---:|:---:|
| `headless` | 否 | `true` | 是否以无头模式启动浏览器 |
| `channel` | 否 | 空 | 浏览器通道名，如 `chrome` |
| `executable_path` | 否 | 空 | 自定义浏览器可执行文件路径 |
| `launch_args` | 否 | `[]` | 额外浏览器启动参数 |
| `browser_locale` | 否 | `zh-CN` | 渲染时的浏览器语言 |
| `user_agent` | 否 | 空 | 共享 User-Agent |
| `default_width` | 否 | `960` | 默认视口宽度 |
| `default_height` | 否 | `540` | 默认视口高度 |
| `default_device_scale_factor` | 否 | `2.0` | 默认缩放倍率 |
| `default_timeout_ms` | 否 | `15000` | 默认超时时间 |
| `max_concurrency` | 否 | `2` | 最大并发渲染数 |
| `startup_warmup` | 否 | `true` | 是否在启动时预热浏览器 |

## 🎉 使用

### 什么时候需要关心它

如果出现以下情况，优先检查这个插件：

- 帮助系统生成图片失败
- 某个插件的卡片、菜单、海报或截图功能无法工作
- 启动日志里出现 Playwright、浏览器启动失败或渲染超时相关错误

### 对开发者提供的接口

- `RenderOptions`
- `render_html(...)`
- `render_template(...)`
- `render_url(...)`
- `render_markdown(...)`
- `html_to_pic(...)`
- `template_to_pic(...)`
- `url_to_pic(...)`
- `markdown_to_pic(...)`
- `get_render_service()`
- `get_render_status()`

## 注意

- 禁用后，依赖图片渲染的插件通常也会一起不可用。
- 如果插件管理页面提示其他插件依赖渲染服务，通常应保持它启用。
