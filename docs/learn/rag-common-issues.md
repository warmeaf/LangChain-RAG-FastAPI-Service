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

## 关键文件索引

| 问题 | 文件 | 方法/位置 |
|------|------|----------|
| 跨文档混淆 | `backend/app/rag/milvus_store.py` | `add_documents()` |
| chunk 上下文断裂 | `backend/app/rag/milvus_store.py` | `get_adjacent_chunks()` |
| chunk 上下文断裂 | `backend/app/rag/rag_service.py` | `_expand_adjacent_chunks()` |
