# AI 架构指南

本文档面向需要在 `apeiria/ai/` 与 `apeiria/app/ai/` 中调试、扩展或重构的人。
目的不是把所有细节写进来，而是给一份**地图**：让你知道一个概念归在哪一层、
一条消息从哪儿进来、出问题时去哪个文件查。

> 范围：本文只涉及 AI 子系统。NoneBot 事件抽取、Web UI 路由、插件目录与会话
> 域请参考 `AGENTS.md` 与各域目录下的代码。

---

## 1. 一句话定位

Apeiria 的 AI 子系统不是"调一下 OpenAI"，而是一套**可路由、可降级、可观测、
带工具循环、带记忆/技能/人格**的对话运行时。它把一次"消息进来 → 回复出去"
建模成一条**显式的、分阶段的 pipeline**，每个阶段都有典型输入/输出契约。

---

## 2. 顶层结构：双层边界

```
┌──────────────────────────────────────────────────────────┐
│  apeiria/app/ai/   应用层（边界 / 编排 / 生命周期）       │
│  - application / lifecycle / runtime/                    │
│  - reply_strategy / agent_turn / conversation_context    │
│  - sessions / skills / future_tasks / operations         │
│  - diagnostics / tooling / usage_recording               │
└──────────────────────┬───────────────────────────────────┘
                       │ 只调用 / 不被调用
                       ▼
┌──────────────────────────────────────────────────────────┐
│  apeiria/ai/        域层（纯领域能力栈）                  │
│  - model/           provider 调用、模型路由               │
│  - prompting/       prompt 模板与拼装                     │
│  - tools/           工具定义、执行、循环                  │
│  - skills/          文件型 SKILL.md prompt 技能           │
│  - memory/ / knowledge/ / retrieval/                     │
│  - persona/ / profile/ / relationship/                   │
│  - retention / turn_records / contributions              │
└──────────────────────────────────────────────────────────┘
```

**纪律线**：

- `apeiria/ai/` 只接受**原语 / 域类型**；不允许出现 NoneBot/FastAPI/Bot/Event。
- `apeiria/app/ai/` 是 NoneBot 与域之间的**防腐层**，负责把 Event 翻译成
  `RuntimeTurnInput`、把域结果翻译回 NoneBot 可投递的回复。
- 不要从 `apeiria.ai` 包根 import 任何东西。`__init__.py` 故意为空。
- 生产组合入口看 `apeiria/app/ai/wiring.py` 与
  `apeiria/app/ai/model_wiring.py`。应用层拿共享 AI 域服务时，优先通过
  `ai_wiring` / `ai_wiring.model`，而不是依赖域层里的模块级单例。
- 域层 `apeiria/ai/` 不得反向 import `apeiria/app/ai/wiring.py`；域内协作要靠
  构造注入或域内显式装配。

---

## 3. 一条消息的完整链路

下面是一条 NoneBot 消息从入口到回复的实际路径。读懂这张图等于读懂一半。

```
NoneBot Event
   │
   ▼
apeiria/builtin_plugins/ai.py            ← 注册 matcher
   │
   ▼
DefaultAILiveRuntimeEntry.handle_message ← apeiria/app/ai/runtime/live.py
   │
   ├─ ensure_ai_runtime_support_initialized()
   │      │（首次触发时初始化工具/技能/记忆等支撑组件）
   │      ▼
   │  ai_lifecycle_coordinator.startup()
   │
   ├─ build_wake_context() / evaluate_wake()
   │      （唤醒判断；不需要回复就提前返回）
   │
   ├─ ai_retention_service.maybe_schedule_cleanup()
   │      （节流的后台清理任务）
   │
   ├─ build_ingested_chat_event() + chat_session_service.append_message()
   │      （把 NoneBot Event 归一化为 ChatMessage 并落库）
   │
   ├─ session_runtime.record_event_if_new()
   │      （事件去重，防止重复处理同一条消息）
   │
   ├─ extract_runtime_media() + speech_input_preparer.prepare()
   │      （提取媒体段、按需走 STT）
   │
   ▼
AIRuntimeCoordinator.run(ReplyRuntimeRequest)   ← orchestrator.py
   │
   ▼
ReplyPath._run_reply_path                       ← orchestrator.py
   │
   │  以下是 7 个显式 stage，每个 stage 实现一个 Protocol：
   │
   ├─ policy_stage.evaluate          硬规则（不应回复就停在这里）
   ├─ observation_stage.apply*       观测副作用（写记忆/落非回复轮）
   ├─ context_stage.assemble         拉对话窗 / 记忆 / persona / RAG
   ├─ policy_stage.decide_reply      社交策略（要不要说话）
   ├─ planning_stage.plan            选模型 / 拼 prompt / 选工具
   ├─ execution_stage.execute        调模型；进入 tool loop
   ├─ commit_stage.commit            写库 + 投递回复
   └─ trace_stage.project            落 TurnTrace 摘要
   │
   ▼
AIRuntimeResult (outcome, commit, stage_reports)
   │
   ▼
str | None  → NoneBot 投递
```

**关键事实**：

- `ReplyPath` 的 7 个 stage 是 **typed protocol**，定义在 `runtime/stages.py`。
  每个 stage 输入/输出是 frozen dataclass，跨 stage 不共享可变状态。
- `AIRuntimeResult.outcome` 有 9 种终态（`hard_rule_skipped` / `social_no_reply` /
  `no_plan` / `no_model` / `empty_response` / `execution_failed` /
  `commit_failed` / `committed` / `observed`），调试时第一眼看这个字段。
- `composition.py` 仍然是 runtime path 的 stage 装配根。
- AI 域服务的生产组合根则是 `apeiria/app/ai/wiring.py` /
  `apeiria/app/ai/model_wiring.py`。前者管工具、技能、记忆、知识、画像、关系、
  retention 等跨边界域服务，后者管 model source/catalog/routing/runtime 子系统。

---

## 4. `apeiria/app/ai/runtime/` 七阶段详解

这是整个 AI 子系统中**最容易迷路**的一块。下面给每个阶段一句话职责 + 关键文件。

```
runtime/
├── ingress/              输入归一化（live.py 里完成大部分）
├── orchestrator.py       AIRuntimeCoordinator / ReplyPath 总编排
├── stages.py             所有 stage 的 Protocol + 数据契约
├── composition.py        装配根：把所有 stage 接到 ReplyPath 上
├── live.py               DefaultAILiveRuntimeEntry：NoneBot 接入点
├── factory.py            LazyAIRuntimeEntry：懒装配
├── contracts.py          RuntimeTraceContext / FutureTaskRuntimeResult 等
│
├── policy.py             ① 硬规则 + 社交决策 stage 实现
├── observation.py        ② 观测副作用 stage 实现
├── context/              ③ 上下文装配 stage 与 provider
├── planning/             ④ 选模型 / 拼 prompt / 选工具
├── execution/            ⑤ 直接执行 / 工具循环 stage
├── commit/               ⑥ 持久化与投递 stage
├── session/              ⑦（横切）会话级运行时（去重、串行化）
└── trace/                ⑧（横切）TurnTrace 摘要落库
```

| 阶段           | 文件                                | 关键产物                                   |
| -------------- | ----------------------------------- | ------------------------------------------ |
| ① 硬规则       | `policy.py`                         | `RuntimePolicyOutcome`                     |
| ② 观测         | `observation.py`                    | 副作用，无显式输出                         |
| ③ 上下文装配   | `context/stage.py` + 多 provider    | `RuntimeContextBundle`                     |
| ④ 社交策略     | `policy.py`（同 stage 第二个方法）  | `ReplyStrategyDecision`                    |
| ⑤ Planning     | `planning/stage.py`                 | `RuntimeTurnPlan` + `RuntimePlanningReport`|
| ⑥ Execution    | `execution/stage.py` + `tool_loop`  | `RuntimeExecutionOutcome`                  |
| ⑦ Commit       | `commit/persistence.py` + `delivery`| `RuntimeCommitResult`                      |
| ⑧ Trace        | `trace/`                            | `TurnTrace`                                |

---

### 4.1 上下文装配（context/）

`context/` 是 stage 实现里**最分散**的一块，因为它本身就是个聚合器：

```
context/
├── stage.py             ← RuntimeContextAssemblyStage
├── materials.py         ← gather_reply_inputs() 编排所有 provider
├── adapter.py           ← 把 RuntimeContextMaterials → TurnContext
├── projection.py        ← 给 trace / planning 用的投影
│
├── context_window.py    ← 对话窗口截取
├── personas.py          ← persona 装配
├── memories.py          ← 记忆召回
├── memory_extraction.py ← 深度观测/记忆提取
├── observations.py      ← 观测副作用助手
├── profiles.py          ← 用户画像
└── relationships.py     ← 关系信号
```

读 `materials.py::gather_reply_inputs` 一遍就能知道**这一轮回复用到了哪些
上下文**。

---

### 4.2 Planning（planning/）

```
planning/
├── stage.py            ← RuntimeTurnPlanningStage（顶层入口）
├── reply_decision.py   ← 是否进入回复路径
├── hard_rules.py       ← 硬规则评估
├── wake.py             ← 唤醒判断（也含 fallback wake context）
├── social.py           ← 社交策略
├── model_selection.py  ← 选模型（衔接 model/routing）
├── prompts.py          ← 拼 prompt 消息
├── tool_exposure.py    ← 决定本轮暴露哪些工具
├── tool_intents.py     ← 工具意图解析
├── tool_policy.py      ← 工具调用策略
├── skills.py           ← 技能选择
├── reasoning.py        ← reasoning 选项装配
├── turn.py             ← AgentTurn 装配
└── diagnostics.py      ← Planning 阶段诊断收集
```

Planning 阶段的产物 `RuntimeTurnPlan` 同时承载：
- 选定模型 + fallback 模型链
- prompt 消息序列
- 工具暴露计划 (`ToolExposurePlan`)
- pre/post tool task class（决定调模型时走哪类路由）
- 技能激活、超时、模式

---

### 4.3 Execution & Tool Loop（execution/）

```
execution/
├── stage.py             ← RuntimeTurnExecutionStage
├── runner.py            ← 直接调用 ModelInvoker
└── tool_loop.py         ← 工具循环主体
```

工具循环的核心状态在 `apeiria/ai/tools/loop/state.py::ToolLoopState`：

| 字段                                  | 含义                                       |
| ------------------------------------- | ------------------------------------------ |
| `round_count`                         | 工具循环跑了几轮                           |
| `model_attempt_count`                 | 本轮调用模型几次                           |
| `model_retry_count`                   | 模型重试次数                               |
| `context_recovery_attempted`          | 是否触发了上下文恢复（截断/压缩）          |
| `chain_repair_placeholders/orphans`   | 工具调用链断裂修补统计                     |
| `consecutive_tool_error_rounds`       | 连续工具错误轮数（截断阈值）               |
| `finalization_attempted/succeeded`    | 终止流程是否走完                           |
| `capability_degradations`             | 能力降级记录（来自 `model/runtime/planning`）|
| `repeated_tool_counts`                | 工具被重复调用的计数                       |

排查"机器人没回复"或"机器人卡在工具调用里"时，先看这个对象的快照
（会被并入 assistant message 的 meta，名字以 `tool_loop_*` 开头）。

---

## 5. 模型子系统：`apeiria/ai/model/`

模型层是整个 AI 子系统中**最严密**的部分。它本身又被分成 4 层：

```
model/
├── sources/      ← provider 接入（OpenAI 兼容 / Anthropic / Gemini / Ollama）
├── catalog/      ← 已配置的具体模型（chat / embedding / rerank / stt / tts）
├── routing/      ← 选模型规则（profile / route / binding / capability_selection）
├── runtime/      ← 实际调用与能力规划
└── adapters/     ← provider 协议适配器
```

### 5.1 一次模型调用的子链路

```
ModelInvoker.generate_text(selected, messages, tools, ...)
   │
   ├─ ai_source_service.get_source_api_key()
   │
   ├─ plan_model_call()                       ← runtime/planning.py
   │     ├─ 检查 capability：streaming / tool / modality
   │     ├─ 若不支持，要么 reject，要么生成 degradations
   │     └─ 输出 AIModelAttemptPlan (messages, tools, options, degradations)
   │
   ├─ build_source_adapter()                  ← runtime/factory.py
   │
   ├─ ai_model_client.generate_text(request)  ← runtime/client.py
   │     └─ adapter.generate_text(...)        ← adapters/*.py
   │
   └─ 把 degradations 注入 response.provider_data["apeiria_degradations"]
```

### 5.2 路由是声明式的

`routing/` 让"reply 用 GPT-4o，summary 用 Haiku，rerank 用本地模型"这种调度
变成配置而非代码：

- `AIModelTaskClass`：任务分类（reply / summary / extraction / rerank / ...）
- `AIModelProfileDefinition`：一个 profile 是一组 task class → 模型的映射
- `AIModelRouteDefinition`：路由规则（algorithm + scope + members）
- `AIModelRouteScopeType`：路由作用域（全局 / 会话 / 用户）

需要追"为什么这次选了这个模型"时，看 `routing/capability_selection.py` +
`AIRuntimeResult.diagnostics["model_routing"]`。

---

## 6. 工具 vs 技能（容易混淆）

| 维度       | Tool（代码型）                          | Skill（文件型）                        |
| ---------- | --------------------------------------- | -------------------------------------- |
| **形态**   | Python 函数                             | `SKILL.md` 文本                        |
| **声明**   | `@ai_tool` 装饰器（`apeiria.ai.plugin_api`）| `register_ai_skill_source(path)`     |
| **存放**   | 插件源码                                | 插件目录 / `builtin_plugins/qq_tools/skills/*/SKILL.md` |
| **运行**   | 工具循环里被模型调用，可执行           | Planning 阶段被选中后注入 prompt       |
| **作用**   | 提供"事实/动作"能力（查天气、发图）    | 提供"语境/工作流"指引（怎么处理某种话题）|
| **服务**   | `apeiria.ai.tools.service.ai_tool_service` | `apeiria.ai.skills.service.ai_skill_service` |
| **持久化** | 执行被审计到 `ai_tool_execution` 表    | 仅元数据；prompt 在内存里              |
| **政策**   | `AIToolLevel` + `AIToolPolicy` 分级    | 当前不分级                             |

> 经验法则：**"模型自己决定要不要做一件事"用 tool；"我们决定模型在某种语境下
> 怎么说话"用 skill。**

---

## 7. 插件贡献：注册时序

插件向 AI 注册工具/技能用的是**冷数据 + 启动时快照**模式：

```
1. 插件 import 期：
   @ai_tool(...) def my_tool(...): ...
        └→ 写入 apeiria.ai.contributions.ai_contributions（全局注册表）

2. 启动 lifecycle：
   ai_lifecycle_coordinator.startup()
        └→ ai_contributions.snapshot()           ← 取一份不可变快照
        └→ 把快照里的工具注册进 ai_tool_service.registry
        └→ 把快照里的 skill 路径喂给 ai_skill_service

3. 运行时：
   工具/技能从 service 读，不再回头找 contributions
```

**为什么这样**：
- 插件 import 期不触发 runtime 单例的初始化（启动顺序解耦）
- snapshot 是 deterministic ordered tuple，对快照测试友好
- `live_platform_context()` 提供 NoneBot 上下文给工具实现，工具仍然只感知
  "live context"接口，而不是 NoneBot 类型

---

## 8. 应用层 Entry Pattern

`apeiria/app/ai/application.py` 的 `AIApplication` 是一个组合根，包含 6 个 entry：

```python
AIApplication(
    runtime,        # LiveRuntimeEntry：handle_message / handle_future_task
    sessions,       # 会话查询/管理
    future_tasks,   # 定时跟进任务
    skills,         # 技能查询/重载
    operations,     # CRUD 给 Web UI 用（personas / profiles / memories / ...）
    diagnostics,    # 诊断快照
)
```

每个 entry 都被 `LazyApplicationEntry` 包了一层——**首次调用才装配**。这是为
启动速度做的权衡，代价是读代码时多穿一层雾。

要替换其中任一个，构造 `AIApplication(runtime=my_runtime, ...)` 即可，参数
都有默认工厂函数。

---

## 9. 全局单例清单

按"读代码时最容易卡住"的优先级排：

| 单例                                        | 文件                                    | 你会在哪里碰到 |
| ------------------------------------------- | --------------------------------------- | -------------- |
| `model_invoker`                             | `model/runtime/service.py`              | 任何模型调用   |
| `ai_model_client`                           | `model/runtime/client.py`               | 同上的下一层   |
| `ai_tool_service`                           | `tools/service.py`                      | 工具相关       |
| `ai_skill_service`                          | `skills/service.py`                     | 技能相关       |
| `ai_contributions`                          | `contributions.py`                      | 插件注册的工具/技能落点 |
| `ai_retention_service`                      | `retention.py`                          | 后台清理       |
| `ai_runtime_settings_service`               | `runtime_settings.py`                   | 各种参数读取   |
| `ai_source_service` / `ai_chat_model_service` 等 | `model/sources/service.py`、`model/catalog/*` | 配置型查询     |
| `ai_model_route_service` / `ai_model_profile_service` | `model/routing/*` | 路由配置       |
| `chat_session_service`                      | `apeiria.conversation.service`          | 会话域（不在 ai/ 下，但会经常一起用）|

它们都来自模块底部的 `xxx = XxxService()`，不是从 DI 容器拿。
**单元测试时**：用 monkeypatch 替换属性，或构造一个新实例传给上层 entry。

---

## 10. 词汇表

| 术语                       | 含义 |
| -------------------------- | ---- |
| `RuntimeTurnInput`         | 一轮回复的归一化输入（identity + source + sender + future_task + sentiment + stream_sink） |
| `RuntimeTurnSource`        | turn 的来源细节（消息文本、是否私聊、媒体段、speech 诊断…） |
| `TurnContext`              | execution 阶段消费的上下文打包 |
| `RuntimeContextMaterials`  | context stage 装配的"原材料"（窗口 / 记忆 / persona / RAG / profile / relationship） |
| `RuntimeTurnPlan`          | planning 的产物：选定模型 + prompt + tool 暴露 + 任务分类 |
| `AgentTurnResult`          | 模型一次完整 agent 流程的结果（response + 工具循环细节 + 诊断） |
| `ToolLoopState`            | 工具循环的可变状态（轮数、重试、上下文恢复、降级…） |
| `ModelAttempt` / `ToolAttempt` | 跨 model/tools 边界的中性记录原语（含 redact） |
| `PromptSafeObservation`    | 工具产物经过截断后的"模型可见"内容 |
| `AIRuntimeResult`          | 一次 runtime 调度的最终结果（outcome + commit + stage_reports + diagnostics） |
| `AIRuntimeCoordinator`     | 选 path 并执行；唯一外部入口 |
| `RuntimePath`              | 命名路径（目前只有 `reply`，未来可能扩展） |
| `RuntimeStageReport`       | 单 stage 的对外摘要（status + diagnostics） |
| `TurnTrace`                | 终态摘要：模型引用 / 工具暴露 / 召回数 / 降级 / outcome |
| `degradation`              | 能力规划阶段的"无法严格满足要求但仍可继续"的降级记录 |

---

## 11. 调试入口（按症状）

| 症状 | 第一眼看 |
| ---- | -------- |
| 机器人对消息没反应 | `evaluate_wake()` 在 `live.py` 的早返回；`policy.evaluate` 的 `should_continue` |
| 进入处理但没回复 | `AIRuntimeResult.outcome`：`social_no_reply` / `no_plan` / `empty_response` |
| 工具调用循环没停 | assistant message meta 里的 `tool_loop_*` 字段；`max_consecutive_tool_error_rounds` |
| 模型选择不对 | `AIRuntimeResult.diagnostics["model_routing"]`；`routing/capability_selection.py` |
| 工具未暴露 | `RuntimePlanningReport.tool_exposure_summary`；`planning/tool_exposure.py` |
| 回复没投递 | `RuntimeCommitResult.delivery_result`；`commit/delivery.py` |
| 启动后 AI 不响应 | `AILifecycleSnapshot.components`；`lifecycle.py` 的 `initialization_source` |
| 记忆没召回 | `RuntimeContextBundle.diagnostics`；`context/memories.py` |

---

## 12. 不在本文档范围

- 非 reply 的 runtime path（目前未实装；预留在 `RuntimeCoordinator.paths`）
- 多 agent 协作 / 子 agent 调度（明确 out of scope，见 `runtime/README.md`）
- 外部向量数据库（当前是 SQLite + embedding store）
- TurnTrace 之外的回放与可视化

如果将来引入这些能力，应当：
- 新增一个 `RuntimePath` 实现而非在 `ReplyPath` 里分支
- 不要把 NoneBot 类型泄漏到 `apeiria/ai/`
- 保持 stage 之间的 dataclass 契约：跨 stage 不共享可变状态
