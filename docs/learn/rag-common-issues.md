# RAG 检索常见问题与解决方案

> 基于本项目的实际踩坑记录，涵盖跨文档混淆、chunk 上下文断裂等问题及修复方案。

---

## Q1：问 A 的信息，为什么回答里混入了 B 的内容？

**场景**：上传了两份简历（胡平和汪国辉），问「胡平擅长什么？」，AI 回答「前端开发：掌握 Vue2/Vue3/Vuex/Pinia...」——但这是汪国辉的技能。

**原因**：Milvus 向量检索按语义相似度召回 chunk，不分文档归属。两份简历都包含「技术」「项目经验」等关键词，向量空间里它们的 chunk 会混杂在一起。LLM 拿到的是混合片段，无法分辨哪个 chunk 属于哪份简历。

**解决方案：元数据注入（Metadata Prefix Injection）**

入库时，每个 chunk 嵌入前拼接文档来源标识：

```
原: "掌握 Vue2/Vue3、Vuex、Pinia..."
改: "[文档: 汪国辉_简历.pdf] 掌握 Vue2/Vue3、Vuex、Pinia..."
```

改动涉及文件：`backend/app/rag/milvus_store.py` → `add_documents()` 方法。

**效果对比**：

| | 修复前 | 修复后 |
|------|--------|--------|
| 重排序 Top-2 | 两份简历混合 | 全为胡平的 chunk |
| 误归因 | 汪国辉技能 → 胡平 | 无 |
| 跨文档最高分 | 0.30 | 0.22 |

**业内相关方案**：
- **CHOP**（2025）：自动为每个 chunk 生成 `[类别-名-模型]` 元数据标签
- **SPD-RAG**（2025）：每个文档一个独立 Agent，彻底隔离
- **ConvSelect-RAG**（2025）：文档级预过滤后再 chunk 级检索

---

## Q2：为什么每次只回答一部分工作经历，漏掉了其他公司？

**场景**：韩梓阳的简历有 9 个 chunk，工作经历跨 chunk 0-1-2。问「工作经历」时，chunk 0 因含姓名得分最高被取走，但 ABC 科技的完整描述在 chunk 1，LLM 只看到 chunk 0 的不完整内容。

**原因**：文本切分是机械的，一份简历被切成多个 chunk 后，相关信息分散在不同 chunk 中。向量检索按 chunk 粒度召回，不能保证关联 chunk 同时被选中。

**chunk 切断示例**：
```
chunk 0: "...负责推荐算法的优化，通过改进协同过滤和深度学习模型，将用户点击"
chunk 1: "率提升25% - 设计并实现基于Transformer 的文本分类系统..."
chunk 2: "...ABC 科技后续 + XYZ 互联网公司 + DEF 人工智能实验室"
```

**解决方案：相邻 Chunk 扩展（Adjacent Chunk Expansion）**

检索到某个 chunk 后，自动补充其相邻的 chunk（chunk_index ± 1），确保上下文完整。

改动涉及文件：
- `backend/app/rag/milvus_store.py` → `get_adjacent_chunks()` 方法
- `backend/app/rag/rag_service.py` → `_expand_adjacent_chunks()` 方法

**流程**：
```
多因素排序 → 收集每个 doc 的 (source, chunk_index)
    → 计算邻居索引 (index ± 1)
    → 从 Milvus 批量查询邻居 chunk
    → 追加到最终文档列表 → 喂给 LLM
```

**业内相关方案**：
- **Contextual Retrieval**（Anthropic, 2024）：LLM 预写 chunk 上下文摘要，拼在 chunk 前再嵌入
- **Late Chunking**（Jina, 2024）：先全文档嵌入，再切块，embedding 层面保留跨 chunk 关系
- **SAKI-RAG**（EMNLP 2025）：用注意力分数计算 chunk 间关系，按关系扩展候选集
- **MacRAG**（2025）：多层粒度检索 + h-hop 邻居合并

---

## Q3：为什么 DOCX/MD 文件被切成几十个微小 chunk？

**场景**：上传一份 DOCX 简历，竟被切成 67 个 chunk；上传一份 MD 简历，被切成 88 个 chunk。每个 chunk 只有一行或十几字，如「姓名：韩小团」「工作经历」「教育背景」各成一个 chunk。检索返回大量碎片，顺序也乱了。

**原因**：`unstructured` 库将 DOCX/MD 拆成逐段落/标题的元素，`preserve_format()` 为每个元素创建一个 LangChain Document。每个元素只有几十字，远小于 400 字的 `chunk_size`，切分器不需要再分但也从不合并它们。结果就是几十个微小 chunk。

**解决方案：入库前先聚合**

新建 `aggregate_by_length()` 函数，将连续的元素按 `chunk_size`（400 字）合并。类似 PPTX 已有的 `aggregate_by_slide()`（按幻灯片聚合）。

```
旧: 67 个元素 → 67 个 Document → 67 个微小 chunk
新: 67 个元素 → aggregate_by_length → 5-8 个 Document → 5-8 个合理 chunk
```

改动涉及文件：
- `backend/app/rag/document_handler/format_preserver.py` → `aggregate_by_length()` 新函数
- `backend/app/rag/document_handler/processor.py` → DOCX 分支改为调用 `aggregate_by_length`
- `backend/app/utils/file_handler.py` → `word_loader`、`word_loader_sync`、`markdown_loader`、`markdown_loader_sync`、`ppt_loader`、`ppt_loader_sync` 全部改为调用对应的聚合函数

---

## Q4：为什么检索结果里显示的是临时路径而非文件名？

**场景**：上传了「李大乐个人简历.pptx」，但检索时每个 chunk 的前缀是 `[文档: /var/folders/.../tmpXXXX.pptx]`，LLM 看不到真实文件名，无法把人名和文档对上号。

**原因**：元数据前缀拼接时优先取了 `doc.metadata.get("source")`，而 unstructured 流程中 `source` 存的是系统临时路径。真正的原始文件名在 `doc.metadata.original_filename` 里，但没被用到。

**解决方案：前缀优先取原始文件名**

```python
# 旧
source = doc.metadata.get("source", doc.metadata.get("filename", ""))

# 新
source = doc.metadata.get("original_filename") \
      or doc.metadata.get("source") \
      or doc.metadata.get("filename", "")
```

改动涉及文件：`backend/app/rag/milvus_store.py` → `add_documents()`。

**效果**：chunk 前缀从 `[文档: /var/folders/.../tmpXXXX.pptx]` 变为 `[文档: 李大乐个人简历.pptx]`，LLM 能正确识别人名与文档的关联。

---

---

## Q5：DOCX 浮动文本框加载为空（文件加载为空）

**场景**：上传由 Aspose.Words 等自动化工具生成的 DOCX 简历（如「李哆啦.docx」「余涵.docx」），SSE 上传处理后报「文件加载为空」。同一批 PDF 正常，传统手动创建的 DOCX（如「韩小团个人简历.docx」）也正常。

**日志特征**：
```
【SSE上传】切片文件 李哆啦.docx 失败: 文件加载为空
```
但日志中**没有**【WORD文件加载(同步)】失败的异常记录——不是抛出异常，而是静默返回空列表。

**原因**：这些 DOCX 由 Aspose.Words for .NET 等工具生成，使用**绝对定位文本框（wps:wsp via wp:anchor）**进行排版，而非传统 Word 段落文本流。`unstructured.partition.docx.partition_docx` 的 XPath 只处理了 `wp:inline`（嵌入形状），没有处理 `wp:anchor`（浮动形状），所以返回 0 个元素 → `aggregate_by_length` 返回 `[]` → 报加载为空。

**文件结构差异**：

| 维度 | 传统 DOCX（韩小团） | Aspose 生成（余涵等 5 份） |
|------|-------------------|------------------------|
| `<w:p>` 段落数 | 67 个独立段落 | 仅 1 个段落 |
| 文本框（`<w:drawing>`） | 0 个 | 18~44 个 |
| 文字位置 | 标准 `<w:r><w:t>` 文本流 | `<wps:wsp>` 浮动文本框内 |
| `partition_docx` 结果 | 67 个元素 | **0 个元素** |
| `python-docx` 读到的段落 | 67 个，`text` 正常 | 1 个，`text` 为空字符串 |

**解决方案：回退提取浮动文本框内容**

```python
# 新增 _extract_textbox_docx 回退函数
# 逻辑：当 partition_docx 返回空时，使用 python-docx + lxml
# 直接遍历 <w:txbxContent> 提取所有文本框中的文字
# 复用 aggregate_by_length 进行聚合
```

改动涉及文件：`backend/app/utils/file_handler.py`

| 函数 | 改动 |
|------|------|
| `word_loader_sync` | `partition_docx` 返回空时调用回退函数 |
| `_extract_textbox_docx` | **新增**。手动提取 `w:txbxContent` 文本 |

**效果**：

| 文件 | 修复前 | 修复后 |
|------|--------|--------|
| 余涵.docx | 加载为空 | 6 docs，2078 字 |
| 张全峰.docx | 加载为空 | 5 docs，1911 字 |
| 李哆啦.docx | 加载为空 | 6 docs，2196 字 |
| 林宇萧.docx | 加载为空 | 5 docs，1887 字 |
| 陈林.docx | 加载为空 | 5 docs，1637 字 |
| 韩小团.docx（回归） | 正常（走 `unstructured`） | 不变 |

**代价**：回退路径丢失 unstructured 的 Title/Header/ListItem 等 Markdown 分类标记，但文本内容完整。

---

## Q6：计数/列举类问题 RAG 永远回答不全

**场景**：知识库中有 13 份简历，问「目前一共有多少个简历？」，AI 回答「4 份」。明明有 13 份，但永远数不全。

**原因**：`rag.yaml` 中 `max_documents: 8` 限制了最终送入 LLM 的文档块数量。多因素排序后只有得分最高的 8 个块被保留。这 8 个块恰好来自 4 份简历（张全峰、陈林、韩梓阳、余涵），LLM 只看到这 4 份。

**从 thinking 数据验证**：
```
重排序 Top-8 分布：
  张全峰.docx × 4 个块（得分 1.0 / 0.70 / 0.56 / 0.54）
  陈林.docx    × 2 个块（得分 0.66 / 0.64）
  韩梓阳.pdf   × 1 个块（得分 0.55）
  余涵.docx    × 1 个块（得分 0.53）
  → 只有 4 份简历可见，其他 9 份被截断
```

**解决方案：新增只读 SQL 查询工具**

不是增强 RAG，而是让 AI agent 有另一条路——直接查询 `doc_weights` 表的元数据。

```
Agent 收到"一共有多少简历？"
  → 判断：这是元数据查询问题，不是语义理解问题
  → 调用 execute_readonly_sql
  → SQL: SELECT COUNT(*) FROM doc_weights
  → 返回 13（精确计数，不受 max_documents 限制）
```

改动涉及文件：

| 文件 | 改动 |
|------|------|
| `backend/app/agent/agent_tools.py` | 新增 `execute_readonly_sql` 工具 + `_inject_user_filter` 安全层 |
| `backend/app/agent/agent.py` | 导入并注册到 `DEFAULT_TOOLS` |

**安全设计**：工具自动在 SQL 中注入 `WHERE user_id = '{当前用户}'`，即使 LLM 没写用户条件，也确保数据隔离。

```
LLM 写：  SELECT COUNT(*) FROM doc_weights
            ↓ _inject_user_filter 自动注入
实际执行：SELECT COUNT(*) FROM doc_weights
         WHERE user_id = 'DMGCo2HLV3gNGvbEFBWkyQ'
```

**安全校验矩阵**：

| 输入 | 行为 |
|------|------|
| `SELECT COUNT(*) FROM doc_weights` | ✅ 自动注入 `WHERE user_id = '...'` |
| `SELECT * FROM doc_weights WHERE category = 'default'` | ✅ 追加 `AND user_id = '...'` |
| `DELETE FROM doc_weights` | ❌ 拒绝（非 SELECT） |
| `SELECT 1; DROP TABLE doc_weights` | ❌ 拒绝（黑名单命中 `DROP`） |

**Agent 路由策略**：

| 工具 | 适用场景 |
|------|---------|
| `execute_readonly_sql` | 计数、列举、按文件名搜索、按类型筛选 |
| `rag_summary_tools` | 理解文档语义内容 |

---

## Q7：doc_weights 表数据缺失

**场景**：`execute_readonly_sql` 工具查询 `SELECT COUNT(*) FROM doc_weights` 返回 0，但知识库里明明有文档。

**原因**：`doc_weights` 表只在**异步批量上传**路径（`processor.py:get_document`）写入，**SSE 流式上传**路径（`knowledge_service.py:_process_slice_results`）没有写入。而用户的所有文档都是通过 SSE 上传的。

**两条上传路径对比**：

```
异步批量上传（get_document）         SSE 流式上传（_process_slice_results）
────────────────────────────          ────────────────────────────────
store.add_documents                   store.add_documents
_init_doc_weights        ← 有       ← 没有！
md5_store.save_md5_hex               md5_store.save_md5_hex
```

**解决方案：补全 SSE 路径 + 回填历史数据**

改动涉及文件：

| 文件 | 改动 |
|------|------|
| `backend/app/router/knowledge_service.py` | 新增 `_init_doc_weight` 方法，在 SSE 成功路径调用 |
| `backend/scripts/backfill_doc_weights.py` | **新增**。一次性回填脚本，从 MD5 存储读取历史记录补写到 `doc_weights` |

回填脚本运行方法：
```bash
cd backend
LLM_TYPE=OLLAMA python scripts/backfill_doc_weights.py
```

回填参数：
- `--user-id <id>`：只处理指定用户（不传则处理所有用户）

**效果**：回填后 `SELECT COUNT(*) FROM doc_weights WHERE user_id = '...'` 返回正确的文档数（如 13 份）。

---

## 关键文件索引

| 问题 | 文件 | 方法/位置 |
|------|------|----------|
| 跨文档混淆 | `backend/app/rag/milvus_store.py` | `add_documents()` |
| chunk 上下文断裂 | `backend/app/rag/milvus_store.py` | `get_adjacent_chunks()` |
| chunk 上下文断裂 | `backend/app/rag/rag_service.py` | `_expand_adjacent_chunks()` |
| DOCX/MD 碎片化 | `backend/app/rag/document_handler/format_preserver.py` | `aggregate_by_length()` |
| DOCX/MD 碎片化 | `backend/app/utils/file_handler.py` | `word_loader`、`markdown_loader` 等 |
| 临时路径前缀 | `backend/app/rag/milvus_store.py` | `add_documents()` |
| DOCX 浮动文本框加载为空 | `backend/app/utils/file_handler.py` | `word_loader_sync`、`_extract_textbox_docx` |
| 计数/列举不全 | `backend/app/agent/agent_tools.py` | `execute_readonly_sql`、`_inject_user_filter` |
| 计数/列举不全 | `backend/app/agent/agent.py` | `DEFAULT_TOOLS` |
| doc_weights 表数据缺失 | `backend/app/router/knowledge_service.py` | `_init_doc_weight`、`_process_slice_results` |
| doc_weights 表数据缺失 | `backend/scripts/backfill_doc_weights.py` | 一次性回填脚本 |
