# Anthropic Messages API 规范参考

> 本文档面向本项目的升级实施，融合 Anthropic 官方 Messages API 规范 + DeepSeek Anthropic 端点兼容性细节 + 项目具体架构决策。
>
> 来源：
> - [Anthropic Messages API](https://platform.claude.com/docs/en/build-with-claude/working-with-messages)
> - [Anthropic Tool Use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)
> - [Anthropic API Reference](https://platform.claude.com/docs/en/api/messages)
> - [DeepSeek Anthropic API](https://api-docs.deepseek.com/zh-cn/guides/anthropic_api)
> - [升级计划](../版本升级规划/升级计划.md)

---

## 一、基础概念

### 1.1 Messages API vs OpenAI Chat Completions

Anthropic Messages API 与 OpenAI Chat Completions API **结构上不兼容**，核心差异：

| 维度 | OpenAI | Anthropic |
|------|--------|-----------|
| 端点 | `POST /v1/chat/completions` | `POST /v1/messages` |
| 消息格式 | `messages: [{role, content}]` | `messages: [{role, content}]` |
| content 类型 | 纯字符串 | **content blocks 数组** |
| 系统提示词 | `messages[0]` (role=system) | 顶层 `system` 参数（字符串或数组） |
| 工具调用 | `tool_calls` 字段在 message 上 | `tool_use` **嵌在 content 数组里** |
| 工具结果 | `ToolMessage` (role=tool) | `tool_result` **嵌在 content 数组里** |
| 流式 | `delta` 逐 token | 逐 content block 事件（更丰富的结构） |

### 1.2 Content Blocks

Anthropic 的 `content` 不是字符串，是 **content block 数组**。每个 block 有 `type` 字段：

```json
// 纯文本
{"type": "text", "text": "Hello, how can I help?"}

// 工具调用
{"type": "tool_use", "id": "toolu_01A09q90...", "name": "vector_search", "input": {"query": "..."}}

// 工具结果
{"type": "tool_result", "tool_use_id": "toolu_01A09q90...", "content": "检索结果：..."}

// 思考（DeepSeek 支持）
{"type": "thinking", "thinking": "我需要先..."}
```

**关键**：一条 assistant message 可以同时包含 `text` + `tool_use` 多个 block，按数组顺序排列。

---

## 二、请求格式

### 2.1 端点与认证

```
POST https://api.deepseek.com/anthropic/v1/messages
```

**Headers**：

| Header | 值 | 说明 |
|--------|---|------|
| `x-api-key` | `sk-...` | DeepSeek API key |
| `anthropic-version` | 任意值 | DeepSeek 忽略此 header |
| `anthropic-beta` | 任意值 | DeepSeek 忽略此 header |
| `Content-Type` | `application/json` | 固定 |

### 2.2 请求体结构

```json
{
  "model": "deepseek-v4-flash",
  "max_tokens": 4096,
  "system": "你是一个智能助手...",
  "messages": [
    {"role": "user", "content": "用户问题"}
  ],
  "tools": [
    {
      "name": "vector_search",
      "description": "在向量数据库中检索文档",
      "input_schema": {
        "type": "object",
        "properties": {
          "query": {"type": "string", "description": "检索查询"}
        },
        "required": ["query"]
      }
    }
  ],
  "stream": true
}
```

### 2.3 参数说明

| 参数 | 类型 | 必需 | DeepSeek 支持 | 说明 |
|------|------|------|--------------|------|
| `model` | string | ✅ | ✅ | `deepseek-v4-flash` |
| `max_tokens` | integer | ✅ | ✅ | 最大输出 token 数 |
| `messages` | array | ✅ | ✅ | 对话历史 |
| `system` | string/array | ❌ | ✅ | 系统提示词（顶层参数） |
| `tools` | array | ❌ | ✅ | 工具定义列表 |
| `tool_choice` | object/string | ❌ | ✅ | `auto`/`any`/`tool`/`none` |
| `stream` | boolean | ❌ | ✅ | 是否流式输出 |
| `temperature` | float | ❌ | ✅ | 0.0–2.0 |
| `top_p` | float | ❌ | ✅ | nucleus sampling |
| `stop_sequences` | array | ❌ | ✅ | 停止序列 |
| `thinking` | object | ❌ | ✅ | `{"type": "enabled"}`（`budget_tokens` 忽略） |
| `metadata` | object | ❌ | 仅 `user_id` | 用于限流隔离 |

### 2.4 DeepSeek 不支持/忽略的参数

| 参数 | 行为 |
|------|------|
| `top_k` | 忽略 |
| `cache_control` | 忽略（不支持 prompt caching） |
| `service_tier` | 忽略 |
| `disable_parallel_tool_use` | **忽略**——模型可能一次返回多个 tool_use |
| `image` content block | **不支持** |
| `document` content block | **不支持** |
| `search_result` content block | **不支持** |

---

## 三、消息格式

### 3.1 User Message

```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "王小明的邮箱是什么？"}
  ]
}
```

也可以简写为字符串：
```json
{"role": "user", "content": "王小明的邮箱是什么？"}
```

**注意**：DeepSeek **不支持** `image` 和 `document` content type，所以 user message 只能用 `text`。

### 3.2 Assistant Message（模型返回）

Assistant message 的 content 是 content blocks 数组：

```json
{
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "让我调用向量检索来查找相关信息。"
    },
    {
      "type": "tool_use",
      "id": "toolu_01AbCdEfGh",
      "name": "vector_search",
      "input": {
        "query": "王小明 邮箱"
      }
    }
  ]
}
```

**注意顺序**：`text` block 在 `tool_use` block 之前（模型先思考再调工具）。

### 3.3 Tool Result Message（用户侧传入）

工具执行完后，以 user role 将结果传回：

```json
{
  "role": "user",
  "content": [
    {
      "type": "tool_result",
      "tool_use_id": "toolu_01AbCdEfGh",
      "content": "检索到文档：...[来源: 王小明的个人简历.md, 相关度: 0.95]...\n邮箱: wangxiaoming@email.com\nGitHub: github.com/wangxiaoming"
    }
  ]
}
```

**关键**：
- `is_error` 字段在 DeepSeek 上**被忽略**——工具报错时，将错误信息直接放入 `content` 文本，格式如 `"Error: 连接Milvus超时"`
- 多个 `tool_result` 可以在同一个 user message 里（对应一次 assistant message 中的多个 `tool_use`）

### 3.4 完整多轮对话示例

```
# Round 1
user:      "王小明的邮箱是什么？"
assistant: text("让我检索...") + tool_use("vector_search", {query: "王小明 邮箱"})

# Round 2
user:      tool_result("检索到：邮箱 wangxiaoming@email.com")
assistant: text("王小明的邮箱是 wangxiaoming@email.com")
```

---

## 四、工具定义 (Tools)

### 4.1 格式

```json
{
  "name": "vector_search",
  "description": "在向量数据库中语义检索文档。返回相关 chunk 的拼接文本，每个 chunk 带来源和相似度标注。用于查找语义相关的文档内容。",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "检索查询语句，自然语言"
      }
    },
    "required": ["query"]
  }
}
```

### 4.2 本项目工具清单

| 工具名 | 用途 | 关键参数 |
|--------|------|---------|
| `vector_search` | 向量语义检索 | `query` |
| `keyword_search` | BM25 关键词检索 | `query` |
| `sql_query` | 只读 SQL 查询（MySQL 元数据） | `query` (自然语言，内部转 SQL) |
| `metadata_filter_milvus` | Milvus 标量字段过滤 | `condition` (自然语言条件) |
| `get_weather` | 和风天气查询 | `city` |
| `get_current_time` | 获取当前时间 | 无 |
| `ocr_recognize` | OCR 识别文件内容 | `file_path` |

**注意**：`user_id` 不在工具参数中暴露——由系统从 ContextVar 自动注入。

### 4.3 元工具（控制 Agent Loop）

| 工具名 | 用途 | 在哪个节点使用 |
|--------|------|---------------|
| `create_plan` | 提交检索计划 | Planning |
| `evaluate_step_result` | 审视步骤结果，输出决策 | Execution |

### 4.4 tool_choice

| 值 | 含义 | 本项目使用场景 |
|----|------|--------------|
| `"auto"` | 模型自行决定是否调工具（默认） | Execution 审视（可能 continue 不调工具） |
| `"any"` | 必须调至少一个工具 | Planning（必须输出 create_plan） |
| `"tool"` | 必须调指定工具 | 可用于强制调用某个工具 |
| `"none"` | 禁止调工具 | Summarization（不走工具，纯文本回答） |

---

## 五、流式输出 (Streaming)

### 5.1 SSE 事件流

当 `stream: true` 时，API 返回 SSE（Server-Sent Events）流：

```
event: message_start
data: {"type": "message_start", "message": {...}}

event: content_block_start
data: {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}

event: content_block_delta
data: {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "王"}}

event: content_block_delta
data: {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "小明"}}

...

event: content_block_stop
data: {"type": "content_block_stop", "index": 0}

event: content_block_start
data: {"type": "content_block_start", "index": 1, "content_block": {"type": "tool_use", "id": "toolu_...", "name": "vector_search", "input": {}}}

event: content_block_delta
data: {"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": "{\"query\": \"王小"}}

...

event: content_block_stop
data: {"type": "content_block_stop", "index": 1}

event: message_delta
data: {"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {...}}

event: message_stop
data: {"type": "message_stop"}

### 5.2 事件类型总结

| 事件 | 含义 | 本项目处理 |
|------|------|-----------|
| `message_start` | 消息开始 | 可选记录 |
| `content_block_start` | 一个 content block 开始 | 判断是 text 还是 tool_use |
| `content_block_delta` | content block 的增量 | text_delta→推送 SSE delta；input_json_delta→累积工具参数 |
| `content_block_stop` | 一个 content block 结束 | tool_use block 结束时，得到完整 tool_use |
| `message_delta` | 消息级增量 | 获取 `stop_reason` (`end_turn`/`tool_use`) |
| `message_stop` | 消息结束 | 判断是否需要执行工具 |

### 5.3 本项目 SSE 事件转换

Anthropic 原生流 → 本项目自定义 SSE 事件（面向前端）：

| Anthropic 原生 | 本项目 SSE |
|---------------|-----------|
| `content_block_start` (tool_use, name="create_plan") | `plan_created` |
| `content_block_start` (tool_use, name="vector_search" 等) | `step_start` |
| `message_delta` (stop_reason="tool_use") 或多个 tool_use 执行完毕 | `step_done` |
| `content_block_start` (tool_use, name="evaluate_step_result", decision="replan") | `step_replan` |
| `content_block_start` (text, 在 Summarization 节点) | `answer_start` |
| `content_block_delta` (text_delta, 在 Summarization 节点) | `delta` |
| `message_stop` | `done` |

### 5.4 Streaming 实现注意

- LangGraph 中通过 `get_stream_writer()` 在节点内推送自定义 SSE
- Summarization 节点的文本流：使用 ChatAnthropic 的 `astream()`，逐 token 推送 `delta`
- Planning/Execution 节点：不需要推送 token 流，推送结构化事件（`plan_created`、`step_start` 等）

---

## 六、消息角色 (Roles)

Anthropic Messages API 只有三种 role：

| Role | 含义 | 说明 |
|------|------|------|
| `user` | 用户消息 | 包括 `tool_result` content blocks |
| `assistant` | 模型回复 | 包括 `text` + `tool_use` content blocks |
| `system` | 系统提示词 | **顶层参数**，不在 messages 数组里 |

**注意**：没有独立的 `tool` role，`tool_result` 放在 **user** role 的 content 里。

---

## 七、stop_reason

每条 assistant message 结束后通过 `stop_reason` 表明终止原因：

| stop_reason | 含义 | 本项目处理 |
|-------------|------|-----------|
| `end_turn` | 模型正常结束（不再调工具） | 进入 Summarization 或 END |
| `tool_use` | 模型调用了工具，等待结果 | 执行工具，将 tool_result 传回 |
| `max_tokens` | 达到 max_tokens 上限 | 记录警告，可能重试 |
| `stop_sequence` | 触发了 stop_sequences | 正常结束 |

---

## 八、langchain_anthropic 集成要点

### 8.1 ChatAnthropic 初始化

```python
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(
    model="deepseek-v4-flash",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/anthropic",
    temperature=0.2,       # Planning/Execution 用低温度
    max_tokens=4096,
    streaming=True,
)
```

**关键**：
- `base_url` 设为 `https://api.deepseek.com/anthropic`（不包含 `/v1`，langchain_anthropic 会自动拼接 `/v1/messages`）
- `api_key` 会通过 `x-api-key` header 发送
- DeepSeek 忽略 `anthropic-version` header，所以无需额外配置

### 8.2 工具绑定

```python
from langchain_core.tools import tool

@tool
def vector_search(query: str) -> str:
    """在向量数据库中语义检索文档。"""
    # 实现...
    return result

tools = [vector_search, keyword_search, ...]
llm_with_tools = llm.bind_tools(tools)
```

ChatAnthropic 的 `bind_tools()` 会自动将 LangChain 工具转为 Anthropic 的 `tools` JSON Schema 格式。

### 8.3 流式调用

```python
# 方式1：astream() 逐 content block 流式
async for chunk in llm_with_tools.astream(messages):
    # chunk 是 AIMessageChunk，content 是 content blocks 列表
    ...

# 方式2：astream_events() 更细粒度
async for event in llm_with_tools.astream_events(messages, version="v2"):
    if event["event"] == "on_chat_model_stream":
        data = event["data"]["chunk"]
        ...
```

### 8.4 在 LangGraph 中使用

```python
# 节点函数
async def llm_call(state: AgentState):
    system_prompt = load_prompt("planning")
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = await llm_with_tools.ainvoke(messages)
    return {"messages": [response]}
```

ChatAnthropic 返回的 `AIMessage` 中，content 会被解析为 content blocks 列表。
`tool_calls` 属性也能正常填充（langchain_anthropic 做了兼容处理）。

---

## 九、与 OpenAI 协议的差异备忘

本项目同时使用两种协议（Agent → Anthropic，RAG 流水线 → OpenAI），开发时注意以下差异：

| 关注点 | Anthropic | OpenAI |
|--------|-----------|--------|
| 系统提示词 | 顶层 `system` 参数 | `messages[0]`, role=system |
| 消息追加方式 | `[user, assistant, user, assistant, ...]` | 同（但 tool message 是独立 role） |
| tool_result 的 role | **user** | **tool** |
| 多轮中如何引用之前的工具结果 | 通过 `tool_result` content block，在 user message 中 | 通过 `ToolMessage`, role=tool |
| 流式 chunk 结构 | 逐 content block | 逐 token delta |
| 最大 context | 1,000,000 token | 视模型而定 |

---

## 十、本项目 Agent Loop 消息序列示例

完整的 Plan-then-Execute 流程在 Anthropic Messages 格式下的序列：

```
### Planning 阶段 ###
user:      "王小明的邮箱和GitHub是什么？"
assistant: text("我需要制定检索计划...") + tool_use("create_plan", {
             steps: [
               {id:"step1", tool_name:"vector_search", args:{query:"王小明 邮箱 GitHub"}, ...},
               {id:"step2", tool_name:"keyword_search", args:{query:"王小明 联系方式"}, ...}
             ]
           })
user:      tool_result("计划已创建，共 2 步")

### Execution: Step 1 ###
assistant: tool_use("vector_search", {query: "王小明 邮箱 GitHub"})
user:      tool_result("检索到：[来源: 王小明的个人简历.md, 相关度: 0.95]\n邮箱: wangxiaoming@email.com\nGitHub: github.com/wangxiaoming")

### Execution: 审视 Step 1 ###
assistant: text("Step 1 结果包含了邮箱和GitHub，信息充足。") + tool_use("evaluate_step_result", {
             decision: "continue",
             reason: "已获取到目标信息，可以跳过 Step 2 或继续验证"
           })

### Execution: Step 2 (基于审视决定跳过) ###
evaluate_step_result 的 decision="continue" 且已满足需求 → 跳过剩余 step

### Summarization ###
assistant: text("王小明的邮箱是 wangxiaoming@email.com，GitHub 是 github.com/wangxiaoming。这些信息来自他的个人简历。")
```

---

## 附：DeepSeek Anthropic 端点兼容性速查表

| 特性 | DeepSeek 支持？ | 备注 |
|------|:---:|------|
| Messages API | ✅ | base_url: `https://api.deepseek.com/anthropic` |
| `tool_use` content block | ✅ | id, input, name 全支持 |
| `tool_result` content block | ✅ | tool_use_id, content 支持；`is_error` 忽略 |
| `thinking` content block | ✅ | `budget_tokens` 忽略 |
| `disable_parallel_tool_use` | ❌ | 被忽略，需应用层处理 |
| `image` content block | ❌ | |
| `document` content block | ❌ | |
| `cache_control` | ❌ | |
| `text` content | ✅ | |
| SSE streaming | ✅ | 完整事件流支持 |
| `temperature` | ✅ | 0.0 ~ 2.0 |
| `top_p` | ✅ | |
| `stop_sequences` | ✅ | |
| `max_tokens` | ✅ | 必须传 |
| `tool_choice` | ✅ | auto/any/tool/none |
| context window | 1,000,000 token | |
