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

## 关键文件索引

| 问题 | 文件 | 方法/位置 |
|------|------|----------|
| 跨文档混淆 | `backend/app/rag/milvus_store.py` | `add_documents()` |
| chunk 上下文断裂 | `backend/app/rag/milvus_store.py` | `get_adjacent_chunks()` |
| chunk 上下文断裂 | `backend/app/rag/rag_service.py` | `_expand_adjacent_chunks()` |
| DOCX/MD 碎片化 | `backend/app/rag/document_handler/format_preserver.py` | `aggregate_by_length()` |
| DOCX/MD 碎片化 | `backend/app/utils/file_handler.py` | `word_loader`、`markdown_loader` 等 |
| 临时路径前缀 | `backend/app/rag/milvus_store.py` | `add_documents()` |
