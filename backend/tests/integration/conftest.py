"""集成测试基础设施

共享 fixtures：数据准备（上传简历文件到 Milvus）、断言辅助函数。
"""

import os
import asyncio
import pytest
from pathlib import Path
from typing import List


# 测试用户 ID
TEST_USER_ID = "integration_test_user"

# 简历文件目录
RESUME_DIR = Path(__file__).parent.parent.parent.parent / "docs" / "简历合集"

# 11 个简历文件
RESUME_FILES = [
    "王小明的个人简历.md",
    "赵明轩-软件开发.pdf",
    "李大乐 - 销售总监个人简历.pptx",
    "汪小辉 - 产品运营简历.pdf",
    "韩小团个人简历.docx",
    "余涵.docx",
    "张全峰.docx",
    "李哆啦.docx",
    "林宇萧.docx",
    "陈林.docx",
]


def check_answer(answer: str, must_contain: List[str] = None, must_not_contain: List[str] = None,
                 must_match: str = None) -> dict:
    """断言辅助函数：检查回答是否满足规则

    Args:
        answer: Agent 返回的回答文本
        must_contain: 必须包含的关键词/实体列表
        must_not_contain: 不得包含的内容列表
        must_match: 精确正则匹配（可选）

    Returns:
        {"passed": bool, "failures": list[str]}
    """
    failures = []

    if must_contain:
        for item in must_contain:
            if item.lower() not in answer.lower():
                failures.append(f"must_contain: '{item}' not found in answer")

    if must_not_contain:
        for item in must_not_contain:
            if item.lower() in answer.lower():
                failures.append(f"must_not_contain: '{item}' found in answer")

    if must_match:
        import re
        if not re.search(must_match, answer, re.IGNORECASE):
            failures.append(f"must_match: pattern '{must_match}' not matched")

    return {
        "passed": len(failures) == 0,
        "failures": failures,
    }


async def _upload_resume_files():
    """上传简历文件到 Milvus（直接使用内部 API）

    使用 DocumentProcessor 上传文件，与 HTTP API 上传效果一致。
    仅在 Milvus/MySQL 可用时执行。
    """
    from app.rag.milvus_store import MilvusService
    from app.agent.tools.vector_search import set_current_user_id

    set_current_user_id(TEST_USER_ID)
    milvus = MilvusService()

    uploaded = []
    for filename in RESUME_FILES:
        file_path = RESUME_DIR / filename
        if not file_path.exists():
            print(f"  [SKIP] 文件不存在: {file_path}")
            continue

        try:
            # 使用 document_processor 上传
            doc_ids = await milvus.document_processor.load_and_store(
                str(file_path), TEST_USER_ID
            )
            uploaded.append(filename)
            print(f"  [OK] 上传成功: {filename} ({len(doc_ids)} chunks)")
        except Exception as e:
            print(f"  [ERROR] 上传失败: {filename}: {e}")

    return uploaded


async def _cleanup_test_data():
    """清理测试数据"""
    from app.rag.milvus_store import MilvusService
    try:
        milvus = MilvusService()
        # 删除测试用户的所有向量
        milvus.client.delete(
            collection_name=milvus.collection_name,
            filter=f'user_id == "{TEST_USER_ID}"',
        )
        print(f"  [OK] 已清理测试用户 {TEST_USER_ID} 的数据")
    except Exception as e:
        print(f"  [WARN] 清理失败: {e}")


# ── Module-scoped fixtures 用于各测试文件 ──

@pytest.fixture(scope="module")
def test_user_id():
    """测试用户 ID"""
    return TEST_USER_ID


@pytest.fixture(scope="module")
def resume_uploaded():
    """Module 级别：上传简历文件到 Milvus（共享数据，仅上传一次）"""
    print(f"\n[Setup] 上传简历文件到 Milvus (user={TEST_USER_ID})...")
    try:
        uploaded = asyncio.run(_upload_resume_files())
        print(f"[Setup] 共上传 {len(uploaded)} 个文件")
    except Exception as e:
        print(f"[Setup] 上传失败（可能 Milvus 未运行）: {e}")
        uploaded = []

    yield uploaded

    # Teardown: 清理测试数据
    print(f"\n[Teardown] 清理测试数据...")
    try:
        asyncio.run(_cleanup_test_data())
    except Exception as e:
        print(f"[Teardown] 清理失败: {e}")


async def run_agent_query(query: str) -> str:
    """运行 Agent 查询并返回回答文本

    Args:
        query: 用户问题

    Returns:
        Agent 的 final_answer 文本
    """
    from app.agent.graph import run_agent_non_stream
    from app.agent.tools.vector_search import set_current_user_id

    set_current_user_id(TEST_USER_ID)

    result = await run_agent_non_stream(
        query=query,
        user_id=TEST_USER_ID,
        session_id=f"test_{hash(query) % 10000}",
    )

    return result.get("final_answer", "")
