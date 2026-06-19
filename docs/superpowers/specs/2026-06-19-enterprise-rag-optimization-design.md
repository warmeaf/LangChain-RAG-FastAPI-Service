# 企业级 RAG 深度优化设计文档

**日期**: 2026-06-19  
**基线评分**: 80/100 (B+)  
**目标评分**: 92-94/100 (A)  
**分支**: feature/enterprise-rag  
**排除**: 邮件/聊天处理

---

## 1. 背景

基于「企业级 RAG」标准文档 (Miles.Ma, 2026-05-12) 的深度分析，当前实现在检索流水线、模型选型、工程架构方面表现优秀 (85-88 分)，但在以下领域存在明显差距：

- 负反馈闭环 (38%)：反馈数据收集完备但未驱动检索优化
- 代码 AST 切分 (60%)：仅 Python 支持，JS/TS/Java/Go 退化
- 混合检索动态权重 (40%)：RRF 固定融合
- 文档权重机制 (70%)：缺类别预设权重
- Excel 增强 (70%)：未处理合并单元格/多级表头
- 图片召回 (65%)：仅多模态描述单通路
- 切分策略 (75%)：缺标题层级切分

---

## 2. 优化模块设计

### 2.1 负反馈闭环 (38% → 85%)

**当前状态**：
- `FeedbackService` 收集 like/dislike/skip + rating + dwell_time + clicked_doc_md5
- `DocWeight` 表存储权重，feedback 触发 ±0.05 微调
- `MultiFactorRanker` 只读 metadata.doc_weight（初始值 1.0），从未查询 DocWeight 表
- `QueryLog` 表定义存在但检索时未写入

**设计变更**：

1. **MultiFactorRanker 改造**：增加 `user_id` 参数，在计算最终得分时查询 `DocWeight` 表获取实际权重。关联键：`metadata.md5 ↔ DocWeight.doc_md5`。权重合并公式：`effective_weight = doc_weight(metadata) * category_weight(config) + feedback_adjustment(db)`。

2. **QueryLog 写入**：在 `RagService.retrieve_documents_batch()` 返回结果后，异步写入 QueryLog 记录（query + retrieved doc IDs + session_id）。

3. **CTR 加权**：`FeedbackService._update_weight()` 从简单 ±0.05 改为基于点击率的贝叶斯平滑：
   - 记录的权重因子：点击次数 / 曝光次数（同 query 或相似 query 下）
   - 冷启动文档默认权重 0.5，随着反馈数据积累逐步调整
   - 相似 query 匹配：基于 query embedding 的余弦相似度（> 0.8）

4. **新增 API**：`POST /feedback/batch` 批量提交反馈（前端一次性上报多个文档的浏览/跳过快照）

**涉及文件**：
- `backend/app/rag/multi_factor_ranker.py` — 读取 DocWeight，合并权重
- `backend/app/rag/feedback/feedback_service.py` — CTR 贝叶斯加权
- `backend/app/rag/rag_service.py` — 传入 user_id，写入 QueryLog
- `backend/app/router/feedback_router.py` — 新增批量反馈接口
- `backend/app/models/feedback.py` — QueryLog 增加字段

**数据流**：
```
检索 → 曝光(写QueryLog) → 用户行为 → Feedback API → DocWeight更新
                                                          ↓
下次检索 → MultiFactorRanker读取DocWeight → 加权排序
```

---

### 2.2 代码 AST 切分 (60% → 90%)

**当前状态**：
- `CodeProcessor._process_python()` 使用 `ast` 模块解析，按 FunctionDef/ClassDef 切分
- `_process_generic()` 对 JS/TS/Java/Go 简单按空行 (`\n\n`) 分块
- `_build_context()` 尝试为 Python 函数添加上下文但实现有 bug（遍历整个 AST 而非直接查找父节点）

**设计变更**：

1. **引入 tree-sitter**：统一处理 Python/JS/TS/Java/Go 五种语言。
   - Python: `tree-sitter-python`
   - JavaScript: `tree-sitter-javascript`
   - TypeScript: `tree-sitter-typescript`
   - Java: `tree-sitter-java`
   - Go: `tree-sitter-go`

2. **切分粒度**：按 function/method/class 边界切分。每个 chunk 包含：
   - 父级上下文注释（如 `// class: UserService, method: login`）
   - 完整代码段源码

3. **fallback**：如果 tree-sitter 解析失败（语法错误或语言不支持），回退到空行分块。

4. **Python 也迁移**：移除自定义 `ast` 实现，统一使用 tree-sitter。

**涉及文件**：
- `backend/app/rag/document_handler/code_processor.py` — 重写
- `backend/requirements.txt` — 添加 tree-sitter 依赖

---

### 2.3 混合检索动态权重 (40% → 85%)

**当前状态**：
- `RRFRetriever` 固定 k=60，均匀融合
- `get_dynamic_weights()` 返回固定 [0.5, 0.5]

**设计变更**：

1. **查询类型分类器**（轻量级，基于规则）：
   - 检测精确匹配特征：数字编号(`\b[A-Z]?\d{3,}\b`)、日期、邮箱、URL、中文专有名词
   - 包含 ≥1 精确特征 → 类型 "precise"
   - 纯自然语言 → 类型 "semantic"
   - 默认 → "balanced"

2. **加权 RRF**：修改 `RRFRetriever` 支持 weighted reciprocal rank fusion：
   ```
   weighted_rrf = Σ (weight_i / (k + rank_i + 1))
   ```
   - precise: BM25=0.65, vector=0.35
   - semantic: BM25=0.30, vector=0.70
   - balanced: BM25=0.50, vector=0.50

3. **实现位置**：`MilvusService.get_dynamic_weights()` 内实现分类逻辑，返回权重数组。`RRFRetriever` 接收 weights 参数。

**涉及文件**：
- `backend/app/rag/milvus_store.py` — 实现分类逻辑
- `backend/app/rag/retrievers/hybrid_retriever.py` — 加权 RRF

---

### 2.4 文档权重机制 (70% → 90%)

**当前状态**：
- 所有文档权重默认 1.0
- 反馈可 ±0.05 微调
- 无类别预设、无质量评分

**设计变更**：

1. **类别预设权重**（config 驱动）：
   ```yaml
   # rag.yaml 新增
   doc_category_weights:
     政策制度: 1.0
     技术文档: 0.9
     产品手册: 0.85
     周报日报: 0.4
     会议纪要: 0.3
     default: 0.7
   ```

2. **类别自动识别**：在 `DocumentProcessor.get_document()` 中，基于文件路径关键词匹配类别（如路径包含 "政策"→政策制度，"技术"→技术文档），匹配不到则用 default。

3. **质量评分**：在 ingest 时计算简单质量分：
   - 高 chunk 数 + 长平均文本 → 完整度高分 (0.9-1.0)
   - 低 chunk 数 + 短文本 → 可能是碎片 (0.5-0.7)
   - 质量分存入 `DocWeight.quality_score`

4. **权重合并**（在 `MultiFactorRanker` 中）：
   ```
   effective = category_preset * 0.4 + feedback_weight * 0.4 + quality_score * 0.2
   ```
   - 初始 ingest 后写入 DocWeight（category + quality），后续反馈微调

**涉及文件**：
- `backend/app/config/rag.yaml` — 新增配置项
- `backend/app/rag/document_handler/processor.py` — 类别识别 + 质量评分
- `backend/app/rag/multi_factor_ranker.py` — 权重合并公式
- `backend/app/models/feedback.py` — DocWeight 新增字段

---

### 2.5 Excel 增强 (70% → 90%)

**当前状态**：
- `ExcelProcessor.process()` 用 openpyxl 读取
- 第一行作为表头，逐行拼接为 "表头值" 格式
- 多 sheet 支持（sheet 名作前缀）
- 未处理合并单元格、多级表头

**设计变更**：

1. **合并单元格处理**：
   - 使用 `ws.merged_cells.ranges` 获取所有合并区域
   - 构建 `merged_value_map`: {(min_row, min_col) → cell_value}
   - 读取时如果单元格属于合并区域，使用合并区域左上角的值

2. **多级表头检测**：
   - 启发式检测：扫描前 N 行（N≤5），如果某行 ≥50% 的单元格与相邻行单元格形成层级模式 → 识别为多级表头
   - 多级表头合并：`"一级表头 > 二级表头"` 格式
   - 非表头行用单行表头处理

3. **自然语言转换增强**：
   - 保持现有 `"表头值"` 格式
   - 多级表头下格式为 `"一级>二级值"`
   - 数字格式保留原始精度

**涉及文件**：
- `backend/app/rag/document_handler/excel_processor.py` — 重写

---

### 2.6 图片三路召回 (65% → 90%)

**当前状态**：
- OCR: PaddleOCR 提取扫描 PDF → 按页生成 Document
- 多模态: Vision Model 生成图片描述 → 文本 Embedding
- 不存在视觉 Embedding 独立通路
- OCR 和多模态描述混在同一个 collection 中，未区分

**设计变更**：

1. **通路 1 - OCR 文字**：现有 PaddleOCR 结果作为独立 chunk 存入 Milvus（metadata 增加 `chunk_type: "image_ocr"`, `image_index`）

2. **通路 2 - 多模态描述**：现有 Vision Model 描述作为独立 chunk 存入（metadata 增加 `chunk_type: "image_desc"`）

3. **通路 3 - 视觉 Embedding（新增）**：
   - 模型：`openai/clip-vit-base-patch32`（通过 `sentence_transformers` 或 `transformers` 加载）
   - 在 PDF 多模态加载时对每张提取的图片生成 CLIP embedding (512维)
   - 使用独立的 Milvus collection（`rag_image_collection`）或在现有 collection 中增加 float_vector 字段
   - **方案选择**：使用独立 collection，schema: `(id, image_md5, visual_embedding(512), user_id, parent_doc_md5, created_at)`
   - 查询文本也通过 CLIP 编码，与视觉 embedding 计算相似度

4. **检索融合**：
   - 文本检索（文本 chunk 粗排）→ Top-N1
   - 图片检索三路并行（OCR 文本 + 多模态描述 + 视觉 embedding）→ 分别 Top-N2 → RRF 融合 → Top-N3
   - 合并文本 Top-N1 + 图片 Top-N3 → 去重 → 精排 (Reranker)

**涉及文件**：
- 新建 `backend/app/rag/image_embedder.py` — CLIP 视觉 Embedding
- `backend/app/rag/milvus_store.py` — 图片 collection 管理 + 多路检索
- `backend/app/rag/document_handler/ocr_processor.py` — OCR chunk type 标记
- `backend/app/utils/pdf_multimodal_loader.py` — 调用 CLIP 生成视觉 embedding
- `backend/app/rag/rag_service.py` — 集成图片检索通路
- `backend/app/utils/factory.py` — clip_model 工厂函数

---

### 2.7 标题层级切分 (75% → 90%)

**当前状态**：
- `RecursiveTextSplitter` 统一处理所有文档
- 分隔符包含 `\n\n`, `\n`, `。`, `！`, `？` 等中文感知分隔符
- `AsyncTextSplitter` 在此基础上增加了 embedding 相似度合并优化
- 未识别 Markdown 标题层级

**设计变更**：

1. **新增 HeadingSplitter**（`text_spliter.py` 中）：
   - 识别 Markdown ATX 标题（`#`, `##`, `###`, `####`, `#####`, `######`）
   - 按标题切分：每个标题及其后续内容（直到同级或更高级标题）作为一个 section
   - 每个 chunk 保留标题路径作为上下文前缀（如 `# 第三章 > ## 3.1 概述 > `）
   - 如果标题下内容超长（> chunk_size × 2），递归应用 `RecursiveTextSplitter`

2. **集成**：
   - `DocumentTypeRouter` 为 `.md` 文件返回 `"markdown"` 策略
   - `DocumentProcessor.get_file_document()` 对 markdown 策略使用 `HeadingSplitter` + `RecursiveTextSplitter` 组合
   - 其他文件类型不变

**涉及文件**：
- `backend/app/rag/text_spliter.py` — 新增 HeadingSplitter
- `backend/app/rag/document_handler/type_router.py` — 增加 markdown 路由
- `backend/app/rag/document_handler/processor.py` — 集成

---

## 3. 配置变更汇总

### rag.yaml 新增配置

```yaml
# 文档类别预设权重
doc_category_weights:
  政策制度: 1.0
  技术文档: 0.9
  产品手册: 0.85
  周报日报: 0.4
  会议纪要: 0.3
  default: 0.7

# 混合检索动态权重
hybrid_search:
  weights:
    balanced: [0.5, 0.5]    # [bm25, vector]
    precise: [0.65, 0.35]
    semantic: [0.3, 0.7]

# 图片召回
image_retrieval:
  enabled: true
  clip_model: "openai/clip-vit-base-patch32"
  visual_collection: "rag_image_collection"
  max_image_chunks: 5

# 标题切分
heading_splitting:
  enabled: true
```

### requirements.txt 新增依赖

```
tree-sitter==0.21.3
tree-sitter-python==0.21.0
tree-sitter-javascript==0.21.0
tree-sitter-typescript==0.21.0
tree-sitter-java==0.21.0
tree-sitter-go==0.21.0
```

CLIP 通过现有的 `sentence_transformers` / `transformers` 库支持，不需要额外依赖。

---

## 4. 数据库变更

### DocWeight 表新增字段

```sql
ALTER TABLE doc_weights ADD COLUMN category VARCHAR(128);
ALTER TABLE doc_weights ADD COLUMN quality_score FLOAT DEFAULT 0.7;
ALTER TABLE doc_weights ADD COLUMN impression_count INT DEFAULT 0;
ALTER TABLE doc_weights ADD COLUMN click_count INT DEFAULT 0;
```

### QueryLog 表新增字段

```sql
ALTER TABLE query_log ADD COLUMN query_embedding JSON;  -- 用于相似 query 匹配
ALTER TABLE query_log ADD COLUMN feedback_applied BOOLEAN DEFAULT FALSE;
```

---

## 5. 实现顺序

按依赖关系和风险排序：

| 顺序 | 模块 | 依赖 | 风险 |
|------|------|------|------|
| 1 | 标题层级切分 | 无 | 低 |
| 2 | Excel 增强 | 无 | 低 |
| 3 | 代码 AST 切分 | 无 | 中 (tree-sitter 集成) |
| 4 | 文档权重机制 | 无 | 低 |
| 5 | 混合检索动态权重 | 无 | 低 |
| 6 | 负反馈闭环 | 模块 4 (DocWeight 表) | 中 |
| 7 | 图片三路召回 | 模块 6 (检索融合逻辑) | 中-高 |

---

## 6. 验证标准

每个模块完成后需通过：

1. **功能正确性**：现有测试（如有）通过，新逻辑手动回归测试
2. **配置兼容性**：新配置项有默认值，不配置时不影响原有行为
3. **性能影响**：关键路径延迟不超过原有 1.2 倍（tree-sitter 和 CLIP 首次加载除外）
4. **评分验证**：全部完成后重新运行企业级标准评估，确认 ≥ 90 分
