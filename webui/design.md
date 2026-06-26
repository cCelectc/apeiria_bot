---
version: alpha
name: Apeiria WebUI
description: Apeiria Bot 管理面板的视觉系统 —— 参照 Berry 的柔和、通透后台风格，蓝主紫辅，由 shadcn-vue + Tailwind v4 实现。
colors:
  background: "#F4F6F8"
  surface: "#FFFFFF"
  foreground: "#1F2933"
  muted: "#6B7280"
  border: "#E5E7EB"
  primary: "#2196F3"
  primary-strong: "#1565C0"
  primary-soft: "#E3F2FD"
  on-primary: "#FFFFFF"
  secondary: "#7C3AED"
  on-secondary: "#FFFFFF"
  success: "#10B981"
  success-strong: "#047857"
  warning: "#F59E0B"
  warning-strong: "#B45309"
  destructive: "#EF4444"
  destructive-strong: "#B91C1C"
  on-destructive: "#FFFFFF"
  ring: "#2196F3"
  log-debug: "#6B7280"
  log-info: "#2196F3"
  log-success: "#10B981"
  log-warning: "#F59E0B"
  log-error: "#EF4444"
  log-critical: "#D11149"
typography:
  h1:
    fontFamily: "Inter, Noto Sans SC, sans-serif"
    fontSize: 1.75rem
    fontWeight: 600
    lineHeight: 1.2
  h2:
    fontFamily: "Inter, Noto Sans SC, sans-serif"
    fontSize: 1.25rem
    fontWeight: 600
    lineHeight: 1.3
  card-title:
    fontFamily: "Inter, Noto Sans SC, sans-serif"
    fontSize: 1rem
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "Inter, Noto Sans SC, sans-serif"
    fontSize: 0.875rem
    fontWeight: 400
    lineHeight: 1.6
  caption:
    fontFamily: "Inter, Noto Sans SC, sans-serif"
    fontSize: 0.75rem
    fontWeight: 400
    lineHeight: 1.5
  metric:
    fontFamily: "Inter, Noto Sans SC, sans-serif"
    fontSize: 2rem
    fontWeight: 700
    lineHeight: 1.1
rounded:
  sm: 6px
  md: 8px
  lg: 12px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
components:
  app-background:
    backgroundColor: "{colors.background}"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.lg}"
    padding: 24px
  stat-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.lg}"
    padding: 24px
    typography: "{typography.metric}"
  text-muted:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.muted}"
    typography: "{typography.caption}"
  button-primary:
    backgroundColor: "{colors.primary-strong}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.md}"
    padding: 12px
    typography: "{typography.body}"
  button-primary-hover:
    backgroundColor: "#0D47A1"
    textColor: "{colors.on-primary}"
  button-secondary:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.on-secondary}"
    rounded: "{rounded.md}"
    padding: 12px
  button-destructive:
    backgroundColor: "{colors.destructive-strong}"
    textColor: "{colors.on-destructive}"
    rounded: "{rounded.md}"
    padding: 12px
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.md}"
    padding: 8px
  sidebar:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.foreground}"
  sidebar-item-active:
    backgroundColor: "{colors.primary-soft}"
    textColor: "{colors.primary-strong}"
    rounded: "{rounded.md}"
  topbar:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.foreground}"
    height: 64px
  icon-chip-primary:
    backgroundColor: "{colors.primary}"
  focus-ring:
    backgroundColor: "{colors.ring}"
  divider:
    backgroundColor: "{colors.border}"
  badge-info:
    backgroundColor: "{colors.primary-soft}"
    textColor: "{colors.primary-strong}"
    rounded: "{rounded.sm}"
  badge-success:
    backgroundColor: "#D1FAE5"
    textColor: "{colors.success-strong}"
    rounded: "{rounded.sm}"
  badge-warning:
    backgroundColor: "#FEF3C7"
    textColor: "{colors.warning-strong}"
    rounded: "{rounded.sm}"
  badge-destructive:
    backgroundColor: "#FEE2E2"
    textColor: "{colors.destructive-strong}"
    rounded: "{rounded.sm}"
  status-online:
    backgroundColor: "{colors.success}"
  status-degraded:
    backgroundColor: "{colors.warning}"
  status-offline:
    backgroundColor: "{colors.destructive}"
  badge-log-debug:
    backgroundColor: "{colors.log-debug}"
  badge-log-info:
    backgroundColor: "{colors.log-info}"
  badge-log-success:
    backgroundColor: "{colors.log-success}"
  badge-log-warning:
    backgroundColor: "{colors.log-warning}"
  badge-log-error:
    backgroundColor: "{colors.log-error}"
  badge-log-critical:
    backgroundColor: "{colors.log-critical}"
---

## Overview

Apeiria WebUI 是 Apeiria Bot 的管理面板，面向运维者/机器人主人。视觉参照 Berry —— 柔和、通透、留白
充足的现代 SaaS 后台：浅灰底承托白色圆角卡片，多层低透明度软阴影制造"浮起"质感，蓝为主、紫为辅。
气质偏"安静的工具"，信息密度适中、克制动效，让插件/适配器/配置/日志这些数据驱动的内容成为主角，而非
让装饰喧宾夺主。技术上完全由 shadcn-vue + Tailwind v4 复刻，不引入 Vuetify/daisyUI。

## Colors

调色板以高对比中性色为骨架，蓝色为唯一的主交互色，紫色作点缀辅助色。

- **primary (#2196F3)**：Berry 品牌蓝，用于强调、激活态指示、图标片、焦点环等"识别"场景。
  注意：它在白字上的对比度不足 WCAG AA，**不要**直接用作白字按钮底色。
- **primary-strong (#1565C0)**：可访问的深蓝，用于主按钮底（配白字）、链接文字、激活项文字。
- **primary-soft (#E3F2FD)**：浅蓝 tint，用于激活项/信息徽章的背景。
- **secondary (#7C3AED)**：紫辅色，次级强调与点缀（配白字达标）。
- **foreground (#1F2933) / muted (#6B7280)**：正文与次要文字。
- **background (#F4F6F8) / surface (#FFFFFF) / border (#E5E7EB)**：页底、卡片、分隔。
- **语义色**：success / warning / destructive 及其 `-strong` 深色变体（深色变体配浅色 tint 背景以达标）。
- **日志级别专色**（`log-debug/info/success/warning/error/critical`）：日志行与级别徽章的着色锚点。

## Typography

中文 Noto Sans SC + 拉丁 Inter，**均自托管**（woff2 随构建打包、由 FastAPI 托管，避免 CDN 在离线/内网
失效）；`font-display: swap`，权重 400/500/600/700。字体栈兜底：
`Inter, "Noto Sans SC", system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif`。

- **h1**：页面标题（28px / 600）。
- **h2**：区块标题（20px / 600）。
- **card-title**：卡片标题（16px / 600）。
- **body**：正文与表格（14px / 400）。
- **caption**：辅助文字、元信息（12px / 400，常配 `muted`）。
- **metric**：仪表盘统计卡的大数字（32px / 700）。

## Layout

整体为"左侧边栏 + 顶栏 + 内容区"的经典管理面板布局，间距以 4 的倍数为节奏（见 `spacing`）。

- **侧边栏**：默认展开 260px，可折叠为 72px 图标轨（状态持久化）；按区域分组，当前项用 `sidebar-item-active`
  胶囊高亮（浅蓝底 + 深蓝文字/图标）；窄屏转为 Sheet 抽屉。
- **顶栏**：高 64px，含面包屑/页标题、主题切换（system/light/dark）、账号菜单。
- **内容区**：`app-background` 浅灰底 + 容器栅格；列表页统一"标题 + 操作 + 搜索"页头；卡片内距 24px、
  页面边距 24–32px。

## Elevation & Depth

用柔和的多层低透明度阴影而非硬边框来分层。卡片静止态为轻柔阴影，hover 时微微抬起（`translateY` +
阴影加深）形成可交互暗示。对话框/Sheet 比卡片更高一层。避免厚重的实色投影。

## Shapes

统一圆角，呼应 Berry 的柔和感：卡片用 `rounded.lg`(12px)，按钮/输入用 `rounded.md`(8px)，徽章等小件用
`rounded.sm`(6px)。

## Components

- **button-primary / -hover**：深蓝实心 + 白字（达 AA），hover 转更深蓝；主操作用。
- **button-secondary**：紫色实心 + 白字；次级强调。
- **button-destructive**：深红实心 + 白字；卸载等破坏性操作（须配确认对话框）。
- **card / stat-card**：白底、圆角、柔影。**统计卡为纯白底 + 彩色图标片 + 大数字（metric）+ 标签，不使用
  渐变。**
- **input**：白底、`rounded.md`、内距 8px。
- **sidebar / sidebar-item-active / topbar**：见 Layout。
- **icon-chip-primary**：半透明/浅色的品牌蓝图标片，用于统计卡与列表项的图标承托。
- **badge-info / -success / -warning / -destructive**：浅色 tint 底 + 同色系深色文字（均达 AA），用于状态。
- **status-online / -degraded / -offline**：纯色状态点（绿/琥珀/红）。
- **badge-log-***：日志级别色块/徽章，对应 6 个级别。
- **focus-ring**：品牌蓝焦点环，保证键盘可达性。
- **divider**：1px 分隔线，填充 `border` 色。

## Do's and Don'ts

- **Do** 用纯白柔影统计卡 + 彩色图标片。**Don't** 用渐变统计卡。
- **Do** 把 `#2196F3` 留给品牌强调、激活态、图标片、焦点环。**Don't** 用 `#2196F3` 作白字按钮/正文文字
  （对比度不达 AA），改用 `primary-strong`。
- **Do** 语义/日志色用"浅 tint 底 + 深色文字"或纯色点来保证可读。**Don't** 用饱和色直接铺底配白字。
- **Do** 自托管 Noto Sans SC + Inter。**Don't** 依赖 CDN 字体（离线/内网会失效）。
- **Do** 保持柔和阴影 + 通透留白的 Berry 气质。**Don't** 引入 Vuetify/daisyUI 或其它组件库。
- **Do** 动效克制（折叠过渡、hover 抬升、骨架屏、toast 滑入）。**Don't** 堆砌花哨动画。
