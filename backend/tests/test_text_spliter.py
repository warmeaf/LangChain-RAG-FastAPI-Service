"""测试 1.1: Markdown 标题层级切分 (HeadingSplitter)"""

import pytest
from app.rag.text_spliter import HeadingSplitter


class TestHeadingSplitter:
    """企业级验收标准：HeadingSplitter 按 # 标题切分 + 保留路径上下文"""

    def test_splits_by_headings(self):
        """Chunk 数量 ≥ 4（两个一级标题 + 二级 + 三级）"""
        hs = HeadingSplitter(chunk_size=400)
        text = (
            "# 第一章 系统概述\n"
            "本章介绍系统的基本架构。\n\n"
            "## 1.1 核心组件\n"
            "核心组件包括 API 网关、消息队列。\n\n"
            "### 1.1.1 API 网关\n"
            "API 网关负责路由、限流、认证。\n\n"
            "# 第二章 快速开始\n"
            "按照以下步骤启动系统。\n"
        )
        chunks = hs.split_text(text)
        assert len(chunks) >= 4, f"期望 ≥4 chunks，实际 {len(chunks)}"

    def test_preserves_heading_path(self):
        """标题路径：Chunk 含 '第一章 系统概述 > 1.1 核心组件'"""
        hs = HeadingSplitter(chunk_size=400)
        text = (
            "# 第一章 系统概述\n"
            "## 1.1 核心组件\n"
            "核心组件包括 API 网关。\n"
        )
        chunks = hs.split_text(text)
        flat = "\n".join(chunks)
        assert "第一章 系统概述 > 1.1 核心组件" in flat, \
            f"缺少标题路径，chunks: {chunks}"

    def test_nested_headings(self):
        """三级嵌套：Chunk 含 '第一章 > 1.1 > 1.1.1' 三级路径"""
        hs = HeadingSplitter(chunk_size=400)
        text = (
            "# 第一章\n"
            "## 1.1 概述\n"
            "### 1.1.1 细节\n"
            "这是详细内容。\n"
        )
        chunks = hs.split_text(text)
        found = any("第一章 > 1.1 概述 > 1.1.1 细节" in c for c in chunks)
        assert found, f"未找到三级嵌套路径，chunks: {chunks}"

    def test_no_content_loss(self):
        """无内容丢失：所有原文内容在某个 chunk 中出现"""
        hs = HeadingSplitter(chunk_size=400)
        text = (
            "# 标题\n"
            "段落A内容。\n"
            "段落B内容。\n"
            "## 子标题\n"
            "段落C内容。\n"
        )
        chunks = hs.split_text(text)
        combined = "".join(chunks)
        assert "段落A内容" in combined
        assert "段落B内容" in combined
        assert "段落C内容" in combined

    def test_long_section_fallback(self):
        """超长 section 回退到段落切分"""
        hs = HeadingSplitter(chunk_size=50)
        text = "# 标题\n" + "很长的内容。" * 30
        chunks = hs.split_text(text)
        assert len(chunks) >= 2, f"超长内容应被切分，实际 {len(chunks)} chunks"

    def test_empty_or_no_heading_returns_original(self):
        """无标题文本返回原文本"""
        hs = HeadingSplitter(chunk_size=400)
        text = "这是没有标题的纯文本。"
        chunks = hs.split_text(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_split_documents_preserves_metadata(self):
        """split_documents 保留 metadata 并追加 chunk_index"""
        from langchain_core.documents import Document
        hs = HeadingSplitter(chunk_size=400)
        docs = [Document(page_content="# A\ncontent", metadata={"source": "test.md"})]
        result = hs.split_documents(docs)
        assert len(result) >= 1
        for i, doc in enumerate(result):
            assert doc.metadata["source"] == "test.md"
            assert "chunk_index" in doc.metadata
