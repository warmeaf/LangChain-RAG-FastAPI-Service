# 项目学习规划

**前置条件**：熟悉 Vue3、Python，无需 LangChain 经验。

**最终目标**：能独立设计并复刻一个 RAG 智能对话系统。

**原则**：先主线后分支，以请求为线索，学架构而非 API。

---

## 阶段一：一条请求走到底（半天）

**目的**：建立全局心智模型。只看谁调谁、数据怎么流，跳过实现细节。

### 跟踪一次对话请求的完整链路

> 用户输入 → SSE 流式请求 → Agent 处理 → 流式返回 → 前端渲染

| 顺序 | 文件 | 看什么 | 关键行 |
|------|------|--------|--------|
| 1 | `front/src/views/AIChat.vue` | `fetchAIResponse` 如何构建请求体、发送 SSE 请求 | L285-310 |
| 2 | `front/src/views/AIChat.vue` | SSE 流如何解析 `data:` 事件并分发给不同 case | L310-400 |
| 3 | `backend/app/router/chat.py` | 路由如何接收请求、注入依赖、调用 Agent | L20-36 |
| 4 | `backend/app/agent/agent.py` | `get_agent_stream_response` 的整体结构：thinking_callback / run_agent / 主循环 三大块 | L254-393 |
| 5 | `backend/app/services/database_session_manager.py` | `get_session` 签名、`add_message` 签名 | L28-53, L76-133 |

### 时序图要点

```
浏览器 ──POST {session_id, query}──▶ FastAPI router
                                        │
                                        ▼
                              get_agent_stream_response()
                                        │
                              ┌─────────┼─────────┐
                              │         │         │
                         run_agent()  主循环    thinking_callback
                        (独立 Task)  (Queue轮询)   (回调入队)
                              │         │
                          get_history  yield SSE
                              │         │
                          Agent 执行   ...
                              │
                         add_message()
                              │
                         save_thinking_events()
```

### 产出

- [ ] 画出 8-10 个节点的一次对话时序图（纸笔或工具皆可）
- [ ] 能不看代码说出请求经过了哪些关键函数

---

## 阶段二：两个核心流程（1 天）

**目的**：理解项目最重要的两条链路，不是能读懂代码，是能用自己的话讲清楚。

### 链路 1：多轮对话的记忆实现

**核心问题**：为什么第二句话 Agent 知道第一句话说了什么？

```
前端只传 session_id ──▶ 后端从 DB 加载历史 ──▶ 拼成 LangChain 消息列表
──▶ 注入 Agent 的 chat_history 参数 ──▶ Agent 结束后写回 DB
```

| 步骤 | 文件 | 关键代码 |
|------|------|---------|
| 获取历史 | `database_session_manager.py` L28-53 | `get_session` 查询 `ChatMessage`，配对 user+assistant |
| 注入 Agent | `agent.py` L288-295 | 转为 `HumanMessage`/`AIMessage` 列表传入 `astream` |
| 持久化 | `agent.py` L364-369 | Agent 完成后 `add_message` 写入本轮对话 |
| ORM 模型 | `models/chat_history.py` | `ChatSession` 与 `ChatMessage` 的一对多关系 |

**关键设计点**：
- `get_history` 在 Agent 执行**前**调用，`add_message` 在**后**调用——确保本轮消息不混入历史
- `chat_history` 作为 prompt 的 `MessagesPlaceholder` 注入，LangChain 自动拼到 prompt 里
- 前端不需要传历史，后端完全自治

### 链路 2：Agent 工具调用

**核心问题**：Agent 怎么知道自己该查知识库还是调天气？

```
用户提问 ──▶ LLM 决定调用哪个工具 ──▶ 工具执行 ──▶ 结果返回 LLM ──▶ 继续推理或给出最终回答
```

| 步骤 | 文件 | 关键代码 |
|------|------|---------|
| 工厂配置 | `agent.py` L22-170 | `AgentFactory` 组装模型 + 工具 + 提示词 |
| 工具定义 | `agent/agent_tools.py` | 每个工具是一个 `@tool` 装饰的函数 |
| 中间件 | `agent/agent_middleware.py` | 请求/响应的拦截处理 |
| Agent 创建 | `agent.py` L138-170 | `create_tool_calling_agent` + `AgentExecutor` |
| 流式循环 | `agent.py` L300-315 | `agent_executor.astream` 的 `intermediate_step` 分支 |
| 思考回调 | `agent.py` L279-282 | 中间件触发 → 回调入队 → 前端实时展示 |

**关键设计点**：
- `AgentFactory` 每次 `create_agent_executor()` 都 new 新实例，避免全局状态污染
- 工厂模式让「换模型」「换工具」只需要改配置，不改业务逻辑
- 思考事件的回调机制：中间件 → callback → Queue → SSE → 前端

### 产出

- [ ] 不看代码能讲清「多轮记忆」的完整流程（前端传什么、后端怎么存/取、Agent 怎么用）
- [ ] 能解释 Agent 工具调用的 4 个参与方（LLM、工具、中间件、回调）及其协作方式

---

## 阶段三：架构决策点（半天）

**目的**：理解每个关键设计的 trade-off。到你自己的项目时，知道为什么选 A 不选 B。

### 决策矩阵

| 决策 | 本项目选择 | 替代方案 | 何时换 |
|------|-----------|---------|--------|
| **Agent 框架** | LangChain AgentExecutor + 自定义回调 | LangGraph / 自建 while 循环 | 需要复杂状态机或多 Agent 协作时换 LangGraph |
| **流式方案** | `asyncio.Queue` + `Task` + `Event` | 直接 `async for` yield | 思考事件和回答内容需要解耦时才需要 Queue |
| **会话存储** | PostgreSQL + SQLAlchemy async | Redis / 内存字典 | 需要持久化多轮对话 → PG；纯缓存 → Redis |
| **LLM 切换** | 环境变量 + if-else 工厂 | 策略模式 / 注册表 / 依赖注入 | 模型数量 < 5 时 if-else 足够；> 5 时换注册表 |
| **前后端通信** | SSE (Server-Sent Events) | WebSocket / HTTP polling | 单向流（后端推前端）→ SSE；双向 → WebSocket |
| **前端状态** | Pinia + 路由参数同步 | Vuex / provide-inject | 跨组件共享 + devtools 支持 |
| **项目结构** | 按技术分层（router/service/models） | 按领域分包（chat/rag/user） | 小型项目按层即可；多人多领域按包 |

### 架构图

```
┌──────────────────────────────────────────┐
│                  前端 (Vue3)              │
│  AIChat.vue ←── Pinia Store ──→ Router   │
│       │                                  │
│     SSE 流                                │
└───────┼──────────────────────────────────┘
        │
┌───────┼──────────────────────────────────┐
│       ▼          后端 (FastAPI)           │
│  ┌─────────┐    ┌──────────────┐         │
│  │ Router   │───▶│ ChatService  │         │
│  └─────────┘    └──────┬───────┘         │
│                        │                 │
│       ┌────────────────┼───────────┐     │
│       ▼                ▼           ▼     │
│  ┌─────────┐    ┌──────────┐ ┌───────┐  │
│  │ Agent   │    │   RAG    │ │ Auth  │  │
│  │(思考链) │    │(检索链) │ │(JWT)  │  │
│  └────┬────┘    └────┬─────┘ └───────┘  │
│       │              │                   │
│       ▼              ▼                   │
│  ┌──────────────────────────┐            │
│  │  SessionManager (DB 层)  │            │
│  └──────────┬───────────────┘            │
│             │                             │
│  ┌──────────▼───────────────┐            │
│  │   PostgreSQL              │            │
│  │   + 向量数据库 (Milvus等) │            │
│  └──────────────────────────┘            │
└──────────────────────────────────────────┘
```

### 产出

- [ ] 能解释项目中 5 个以上架构决策的 trade-off
- [ ] 能用一句话概括各模块的职责：Router 做什么、Service 做什么、SessionManager 做什么

---

## 阶段四（可选）：深入一个设计亮点

### 流式架构的异步解耦

`agent.py` 的流式架构值得细读。这是项目中最精巧的部分：

```python
# 三个并发组件 + 两条数据通路

thinking_callback(data)          # Agent 中间件触发，数据入两条路
    │
    ├──▶ thinking_queue.put()   # 通路 1：实时推送给前端
    │         │
    │         ▼
    │    主循环轮询 Queue ──▶ SSE yield
    │
    └──▶ thinking_events.append() # 通路 2：累积后持久化到 DB

run_agent()                      # 独立 asyncio.Task
    │
    ▼
Agent 执行完成后 agent_done.set() ──▶ 主循环退出 ──▶ add_message ──▶ save_thinking_events
```

**涉及的知识点**：
- `asyncio.Queue` — 生产者-消费者模式
- `asyncio.Task` — 并发执行
- `asyncio.Event` — 跨协程信号
- `asyncio.wait_for(timeout=0.1)` — 非阻塞轮询

---

## 不需要学的内容

以下内容现阶段跳过，不影响理解架构：

- LangChain/LangSmith 具体 API（版本迭代快，学思想）
- `DjangoUserService/` 内部实现（知道是独立用户系统即可）
- 前端 CSS 和 UI 细节
- `rag/` 下每个切片策略的实现（知道存在，用到深读）
- 日志封装、配置加载等基础设施代码
- RAG 服务的完整实现（阶段二只需了解工具接口）

---

## 学习节奏建议

```
Day 1 上午：阶段一，画时序图
Day 1 下午：阶段二链路 1（多轮记忆）
Day 2 上午：阶段二链路 2（Agent 工具调用）
Day 2 下午：阶段三，理解架构决策
Day 3（可选）：阶段四，深入流式解耦
```
