# 企业级 RAG 系统重构设计文档

> 基准：《企业级 RAG.md》by Miles.Ma  
> 日期：2026-06-19  
> 分支策略：从 `feature/langgraph-migration` 新建 `feature/enterprise-rag` 分支实施

---

## 一、重构目标

将当前系统（企业级程度约 42/100）提升至 ~85/100 企业级水平。覆盖以下差距：

| 优先级 | 项目 | 状态 |
|--------|------|------|
| P0 | 粗排 k: 10 → 100 | 改造 |
| P0 | 多因素排序（时间衰减 + 文档权重） | 新增 |
| P0 | 长问题处理（压缩 + 拆分子问题） | 新增 |
| P0 | 查询扩展（LLM 多表达生成） | 新增 |
| P0 | 文件类型感知切分（Excel/代码/格式保留/OCR） | 新增/改造 |
| P1 | 负反馈采集 + 权重影响 | 新增 |
| P1 | 动态混合检索权重 | 改造 |
| P1 | Word/PPT 格式保留（Markdown） | 改造 |
| P1 | 扫描 PDF OCR 支持 | 新增 |
| 架构 | ChromaDB → Milvus (Docker) | 替换 |
| 模型 | qwen3-embedding → bge-large-zh | 替换 |
| 模型 | Qwen3-Reranker → bge-reranker-large | 替换 |
| 前端 | 全面重构 (Naive UI) | 重写 |

---

## 二、整体架构

```
                         ┌─────────────────────────────┐
                         │     Vue 3 前端 (Naive UI)     │
                         │     Pinia + Vue Router       │
                         └─────────────┬───────────────┘
                                       │ SSE / REST
                         ┌─────────────▼───────────────┐
                         │   FastAPI 后端 (uv 管理)      │
                         │                              │
  ┌──────────────────┐   │  ┌───────────────────────┐  │
  │ LangGraph Agent  │   │  │  企业级 RAG Pipeline   │  │
  │  · 工具调用      │   │  │  ① QueryProcessor      │  │
  │  · SSE 流式      │   │  │  ② 粗排 Top-100        │  │
  │  · 思考链可见    │   │  │  ③ 精排 Reranker       │  │
  └──────────────────┘   │  │  ④ MultiFactorRanker   │  │
                         │  │  ⑤ 分批总结             │  │
                         │  └───────────────────────┘  │
                         │                              │
                         │  ┌───────────────────────┐  │
                         │  │  DocumentTypeRouter    │  │
                         │  │  · ExcelProcessor      │  │
                         │  │  · ScannedPDFProcessor │  │
                         │  │  · CodeProcessor       │  │
                         │  │  · Word/PPT Preserver  │  │
                         │  └───────────────────────┘  │
                         │                              │
                         │  ┌───────────────────────┐  │
                         │  │  FeedbackService       │  │
                         │  │  · like/dislike/rating │  │
                         │  │  · dwell time tracking │  │
                         │  │  · weight auto-update  │  │
                         │  └───────────────────────┘  │
                         └──────────┬──────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
    ┌─────────▼────────┐  ┌────────▼────────┐  ┌─────────▼────────┐
    │  Milvus (Docker) │  │  MySQL (本地)   │  │  Redis (本地)    │
    │                  │  │                 │  │                  │
    │  · bge-large-zh  │  │  · chat_sessions│  │  · rate limit    │
    │  · 1024维向量    │  │  · chat_messages│  │  · user cache    │
    │  · IVF_FLAT 索引  │  │  · user_feedback│  │  · query cache   │
    │  · Partition Key  │  │  · doc_weights  │  │                  │
    │    (user_id)      │  │  · query_log    │  │                  │
    └──────────────────┘  └────────────────┘  └──────────────────┘
```

---

## 三、基础设施变更

### 3.1 部署策略

**仅 Milvus 使用 Docker**（Milvus 依赖 etcd + MinIO，Docker 是官方推荐的唯一方式）。MySQL 和 Redis 保持本地手动部署（已在当前系统中配置运行）。

```bash
# Mac 安装 Colima (轻量 Docker 运行时，无需 Docker Desktop)
brew install colima docker docker-compose
colima start --cpu 4 --memory 8

# 仅启动 Milvus 相关服务
docker compose -f docker-compose.milvus.yml up -d
```

`docker-compose.milvus.yml` 包含三个容器：
- `etcd`（Milvus 元数据存储）
- `minio`（Milvus 向量数据存储）  
- `milvus-standalone`（端口 19530、9091）

MySQL/Redis 沿用现有本地服务，无需改动。

### 3.2 模型切换

| 组件 | 旧 | 新 | 加载方式 |
|------|----|----|----------|
| Embedding | qwen3-embedding:0.6b (Ollama) | `BAAI/bge-large-zh` (1024维) | `SentenceTransformer` 本地加载，HF 自动下载 |
| Reranker | Qwen3-Reranker-0.6B (ModelScope) | `BAAI/bge-reranker-large` | `CrossEncoder` 本地加载，HF 自动下载 |
| LLM | 不变 (DeepSeek/Ollama/阿里云) | 不变 | 不变 |

模型首次运行时从 HuggingFace 下载到 `~/.cache/huggingface/hub/`。

### 3.3 Milvus Collection Schema

```python
from pymilvus import Collection, DataType, FieldSchema, CollectionSchema

schema = CollectionSchema([
    FieldSchema("id", DataType.VARCHAR, max_length=128, is_primary=True),
    FieldSchema("text", DataType.VARCHAR, max_length=65535),
    FieldSchema("embedding", DataType.FLOAT_VECTOR, dim=1024),
    FieldSchema("user_id", DataType.VARCHAR, max_length=64, is_partition_key=True),
    FieldSchema("doc_weight", DataType.FLOAT, default=1.0),
    FieldSchema("created_at", DataType.INT64),
    FieldSchema("metadata", DataType.JSON),
])

collection.create_index("embedding", {
    "index_type": "IVF_FLAT",
    "metric_type": "COSINE",
    "params": {"nlist": 128}
})
```

`user_id` 作为 Partition Key，实现原生多租户隔离。

### 3.4 新增 MySQL 表

由于 Embedding 模型从 `qwen3-embedding`（维度未知）切换到 `bge-large-zh`（1024维），**所有文档必须重新向量化**。迁移策略：

**方案：通过现有 API 重新上传**

```bash
# 1. 导出当前 ChromaDB 中的原始文件名列表（MD5 store 已有）
# 2. 用户通过 /knowledge/add/multiple 重新上传文件
# 3. bge-large-zh 重新向量化 → 写入 Milvus
# 4. 旧的 ChromaDB data/ 目录保留作为备份
```

**ChromaDB 数据保留**：
- 旧 `data/chromadb/` 目录不删除，保留到确认 Milvus 正常后再清理
- `data/md5_hex_store/` 保留兼容（MD5 去重仍依赖它）

**无需迁移的内容**：
- MySQL 的 `chat_sessions`、`chat_messages`、`chat_thinking_events` 不受影响
- Redis 缓存不受影响
- JWT 认证逻辑不受影响

```sql
-- 用户反馈表
CREATE TABLE user_feedback (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    session_id VARCHAR(64) NOT NULL,
    query TEXT NOT NULL,
    doc_md5 VARCHAR(64),
    doc_filename VARCHAR(512),
    feedback_type ENUM('like', 'dislike', 'skip'),
    rating TINYINT,
    dwell_time_ms INT,
    clicked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_query (user_id, query(100))
);

-- 文档权重表
CREATE TABLE doc_weights (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    doc_md5 VARCHAR(64) NOT NULL,
    doc_filename VARCHAR(512),
    category VARCHAR(128),
    weight FLOAT DEFAULT 1.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_md5 (user_id, doc_md5)
);

-- 查询日志表
CREATE TABLE query_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(64),
    query TEXT NOT NULL,
    retrieved_docs JSON,
    clicked_doc_md5 VARCHAR(64),
    session_id VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 四、检索策略层

### 4.1 完整 Pipeline

```
用户查询 (任意长度)
    │
    ▼
┌─────────────────────────────┐
│ ① QueryProcessor (新增)      │
│                              │
│ 1. 长度检测 & LLM 压缩        │
│    if len(query) > 400 char:  │
│      → compress to ~300 char  │
│                              │
│ 2. 子问题拆解                 │
│    → LLM decompose to list    │
│                              │
│ 3. 查询扩展                   │
│    → LLM generate synonyms    │
│    → 每个变体独立检索          │
│                              │
│ 输出: List[str] (1~N 变体)    │
└─────────────┬───────────────┘
              │ 并行 asyncio.gather
              ▼
┌─────────────────────────────┐
│ ② 粗排: Top-100              │
│                              │
│ Milvus 向量检索 → Top-100    │
│ BM25 关键词检索 → Top-100    │
│ → RRF 融合 (k=60)            │
│ → 去重，返回 Top-100         │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ ③ 精排: bge-reranker-large   │
│                              │
│ CrossEncoder(query, doc)     │
│ 对 100 条逐对打分             │
│ 归一化到 [0,1]               │
│ → Top-20                     │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ ④ MultiFactorRanker (新增)   │
│                              │
│ score =                      │
│   relevance  × 0.5 +        │
│   time_decay × 0.3 +        │
│   doc_weight × 0.2          │
│                              │
│ time_decay = e^(-1.0 × yrs)  │
│   今天=1.0, 1年前≈0.37      │
│                              │
│ doc_weight: 从 DB 读取       │
│   政策类=1.0, 会议纪要=0.3   │
│                              │
│ → 取 Top-5 (max_documents)   │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ ⑤ 分批总结 (保留现有逻辑)     │
│   per-doc summarize          │
│   → merge → final summary    │
└─────────────────────────────┘
```

### 4.2 新增/改造的源码文件

```
backend/app/rag/
├── query_processor.py        # 新增：QueryProcessor 类
├── multi_factor_ranker.py    # 新增：MultiFactorRanker 类
├── milvus_store.py           # 重写：MilvusService 替代 VectorStoreService
├── rag_service.py            # 改造：编排新流程
├── reorder_service.py        # 改造：bge-reranker-large 替换
├── retrievers/
│   ├── milvus_retriever.py   # 新增：Milvus 向量检索
│   ├── bm25_retriever.py     # 保留增强
│   └── rrf_retriever.py      # 保留增强
│   └── hybrid_retriever.py   # 保留改造
```

### 4.3 QueryProcessor 核心接口

```python
class QueryProcessor:
    async def process(self, query: str) -> List[str]:
        """返回 1~N 个查询变体，每个独立检索"""
        # 1. 长度检测 & 压缩
        # 2. 子问题拆解
        # 3. 查询扩展
        # 返回去重后的变体列表
```

### 4.4 MultiFactorRanker 核心接口

```python
class MultiFactorRanker:
    async def rank(self, query: str, docs: List[Document]) -> List[Document]:
        """多因素排序：相关性 + 时间衰减 + 文档权重"""
```

### 4.5 HyDE 策略变更

保留 HyDE，但调整其位置：
- **旧**：HyDE 在检索前执行，生成的假设答案完全替代原始 query 用于检索
- **新**：HyDE 作为查询扩展的一个额外变体，与原始 query + 其他扩展变体并行检索，所有结果经过 RRF 合并去重。这样既受益于 HyDE 的语义丰富性，又不丢失原始 query 的精确匹配能力

检索变体来源：
1. 原始 query（始终保留）
2. 查询扩展生成的同义词变体（如"请假"→"休假申请"）
3. HyDE 生成的假设答案变体（如"请假是指员工因私人原因..."）

---

## 五、文档处理层

### 5.1 类型路由器

```
backend/app/rag/document_handler/
├── processor.py         # 改造：DocumentProcessor 集成路由器
├── type_router.py       # 新增：DocumentTypeRouter
├── excel_processor.py   # 新增：行→自然语言，支持合并单元格/多级表头
├── code_processor.py    # 新增：tree-sitter AST 切分 (函数/类/方法)
├── ocr_processor.py     # 新增：PaddleOCR 扫描 PDF
├── format_preserver.py  # 新增：Word/PPT Markdown 格式保留
└── pdf_multimodal_loader.py  # 保留增强
```

### 5.2 各处理器策略

| 文件类型 | 旧策略 | 新策略 |
|----------|--------|--------|
| `.xlsx/.xls` | ❌ 不支持 | 行→自然语言，sheet 名作上下文 |
| `.pdf` (文字) | PyMuPDF → 统一切分 | 标题层级识别 → 按 section 切分 + 段落保留 |
| `.pdf` (扫描) | ❌ 无 OCR | PaddleOCR → 文字提取 → 按 section 切分 |
| `.docx` | unstructured → str(el) | 格式→Markdown (bold→`**`, heading→`#`) |
| `.pptx` | unstructured → str(el) | 幻灯片为单元，保留页码 + 格式 |
| `.py/.js/.ts/.java/.go` | ❌ 不支持 | tree-sitter AST → 按函数/类/方法切分 |
| `.md/.txt` | 统一切分 | 保持，切分粒度调整到 400 char |

### 5.3 切分配置 (rag.yaml)

```yaml
chunking:
  default:
    chunk_size: 400
    chunk_overlap: 40
  by_type:
    policy_doc:
      chunk_size: 600
    technical_doc:
      chunk_size: 300
    code:
      strategy: ast
    excel:
      strategy: row_to_nl
```

---

## 六、负反馈系统

### 6.1 数据流

```
用户操作 (点赞/点踩/评分/点击)
    │
    ▼
POST /feedback → feedback_service.py → MySQL user_feedback
    │
    ▼ (批处理 / 实时)
doc_weight 更新 → doc_weights 表
    │
    ▼
下次检索时 MultiFactorRanker 读取最新权重
```

### 6.2 API

```python
# POST /feedback
{
    "session_id": "uuid",
    "query": "怎么申请报销",
    "feedback_type": "like",       # like | dislike | skip
    "rating": 4,                    # 1-5 (可选)
    "dwell_time_ms": 12500,         # 停留时长 (可选)
    "clicked_doc_md5": "abc123"     # 点击的文档 (可选)
}

# GET /feedback/stats?user_id=xxx
{
    "total_feedback": 150,
    "like_rate": 0.72,
    "avg_rating": 3.8,
    "top_queries": [...],
    "top_docs": [...]
}
```

### 6.3 权重自动调整规则

| 反馈类型 | 权重调整 |
|----------|----------|
| like | `weight += 0.05` (上限 1.0) |
| dislike | `weight -= 0.05` (下限 0.1) |
| skip (检索到但未点击) | `weight -= 0.02` (下限 0.1) |

### 6.4 目录结构

```
backend/app/rag/feedback/
└── feedback_service.py   # 新增：FeedbackService
backend/app/router/
└── feedback_router.py     # 新增：POST /feedback, GET /feedback/stats
backend/app/models/
└── feedback.py            # 新增：ORM (UserFeedback, DocWeight, QueryLog)
```

---

## 七、前端重构

### 7.1 技术栈

| 组件 | 当前 | 重构后 | 变更原因 |
|------|------|--------|----------|
| 框架 | Vue 3 + TypeScript | 保持 | - |
| UI 库 | **Vant** (移动端) | **Naive UI** (桌面端) | Vant 面向移动端 H5，不适用企业级桌面后台；Naive UI 专为企业级管理面板设计 |
| 状态管理 | Pinia | 保持 | - |
| 路由 | Vue Router | 保持 | - |
| 构建 | Vite + pnpm | 保持 | - |
| HTTP | axios | 保持 | - |
| Markdown | marked + highlight.js | 保持 | - |
| 国际化 | vue-i18n | 保持 | - |
| XSS 防护 | DOMPurify | 保持 | - |

### 7.2 页面结构

```
front/src/
├── views/
│   ├── ChatView.vue          # 对话页：RAG pipeline 可视化 + 反馈
│   ├── KnowledgeView.vue     # 知识库：文件管理 + 类型标签 + 权重设置
│   ├── AnalyticsView.vue     # 新增：反馈统计 + 高频查询 + 效果仪表板
│   └── LoginView.vue         # 保留
├── components/
│   ├── chat/
│   │   ├── MessageBubble.vue     # 改造：消息气泡 + 反馈条
│   │   ├── RAGPipelineCard.vue   # 新增：检索过程可视化
│   │   └── FeedbackBar.vue       # 新增：点赞/点踩/评分
│   ├── knowledge/
│   │   ├── FileTypeTag.vue       # 新增：文件类型彩色标签
│   │   └── DocWeightEditor.vue   # 新增：权重滑条编辑器
│   └── common/
│       └── ...
├── api/
│   ├── chat.ts
│   ├── knowledge.ts
│   └── feedback.ts
└── stores/
    ├── chat.ts
    ├── knowledge.ts
    └── feedback.ts
```

### 7.3 RAG Pipeline 可视化组件

在对话消息中展示 RAG 检索过程（替代后台 thinking events 的纯文本展示）：

```
┌─────────────────────────────────────────┐
│ 🔍 RAG 检索过程                         │
│                                         │
│ ① 查询预处理                            │
│    原始: "怎么请假"                      │
│    扩展: ["请假流程", "休假申请"]  ✓     │
│                                         │
│ ② 粗排检索 (Top-100)                    │
│    向量检索: 100 条   │ BM25: 86 条      │
│    RRF 融合后: 100 条                    │
│                                         │
│ ③ 精排重排 (bge-reranker)               │
│    Top-1: 得分 0.95                      │
│    Top-2: 得分 0.87    ...              │
│                                         │
│ ④ 多因素排序                            │
│    相关性: 0.95 × 0.5 = 0.475           │
│    时间衰: 0.82 × 0.3 = 0.246           │
│    权重:   1.00 × 0.2 = 0.200           │
│    ─────────────────────────            │
│    最终: 0.921                          │
│                                         │
│ ⑤ 分批总结 (5 篇文档)                   │
│    已完成 ✓                              │
└─────────────────────────────────────────┘
```

---

## 八、配置管理

### 8.1 YAML 配置统一为 `rag.yaml`

```yaml
# backend/app/config/rag.yaml

retrieval:
  coarse_k: 100          # 粗排召回数
  max_documents: 5       # 最终总结文档数
  
reranker:
  model: "BAAI/bge-reranker-large"
  max_length: 512

ranking:
  w_relevance: 0.5
  w_time: 0.3
  w_weight: 0.2
  time_decay_lambda: 1.0   # 指数衰减系数

query_processing:
  max_length: 400          # 超此长度触发压缩
  max_sub_queries: 5       # 子问题最大数量
  max_expansions: 3        # 查询扩展最大数量

chunking:
  default:
    chunk_size: 400
    chunk_overlap: 40
  separators: ["\n\n", "\n", "。", "！", "？", "!", "?", " ", ""]

milvus:
  host: "localhost"
  port: 19530
  collection_name: "rag_collection"
  index_type: "IVF_FLAT"
  metric_type: "COSINE"
  nlist: 128

allow_file_types: ["txt", "pdf", "md", "pptx", "docx", "xlsx", "xls", "py", "js", "ts", "java", "go"]

ocr:
  enabled: true
  language: "ch"
```

### 8.2 环境变量新增

```bash
# .env 新增
MILVUS_HOST=localhost
MILVUS_PORT=19530
EMBED_MODEL_NAME=BAAI/bge-large-zh
RERANKER_MODEL_NAME=BAAI/bge-reranker-large
```

---

## 九、实施顺序（渐进式）

> 实施分支：`feature/enterprise-rag`（从 `feature/langgraph-migration` 创建）

### 阶段 1：基础设施替换
1. 创建分支：`git checkout -b feature/enterprise-rag`
2. 安装 Colima + Docker，编写 `docker-compose.milvus.yml`，启动 Milvus
3. 编写 `milvus_store.py`（MilvusService 类），替换 `vector_store.py`
4. 改造 `factory.py`：`bge-large-zh` + `bge-reranker-large` HF 加载
5. 改造 `reorder_service.py`：适配 bge-reranker-large
6. 新增 MySQL 表：`user_feedback`、`doc_weights`、`query_log`
7. 文档通过 API 重新上传，bge-large-zh 重新向量化→写入 Milvus
8. 配置文件：`chroma.yaml` → `rag.yaml`，新增 `.env` 变量

### 阶段 2：检索策略增强
7. 新增 `query_processor.py`（压缩 + 拆解 + 扩展）
8. 新增 `multi_factor_ranker.py`（时间衰减 + 文档权重）
9. 改造 `rag_service.py`：集成新 pipeline
10. 粗排 k 调至 100

### 阶段 3：文档处理升级
11. 新增 `type_router.py` + 各处理器（Excel/Code/OCR/格式保留）
12. 改造 `processor.py`：集成类型路由器
13. 新增 `rag.yaml` 配置

### 阶段 4：反馈闭环 + 前端
14. 新增 `feedback_service.py` + `feedback_router.py` + ORM
15. 前端全面重构（Naive UI + RAG pipeline 可视化 + 反馈）
16. 端到端集成测试

---

## 十、回滚与兼容

- 每个阶段在独立 git 分支上开发，完成后合并到 `feature/enterprise-rag`
- 阶段 1 完成后，旧的 ChromaDB 代码保留在 `feature/langgraph-migration` 分支，可随时回退
- 数据迁移脚本同时生成 ChromaDB 导出文件，确保可恢复
- `docker-compose.yml` 中服务端口与现有服务错开，不冲突
