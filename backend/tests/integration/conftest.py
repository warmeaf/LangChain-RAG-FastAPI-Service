"""集成测试基础设施

共享 fixtures：数据准备（上传简历文件到 Milvus）、断言辅助函数。

数据上传使用与 HTTP API 相同的内部处理链路（DocumentProcessor），
Agent 查询使用 run_agent_non_stream（与 HTTP API 相同的 Agent 逻辑）。
"""

import os
import asyncio
import pytest
import tempfile
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


class _FakeUploadFile:
    """模拟 FastAPI UploadFile 的最小接口，供 DocumentProcessor.get_document() 使用

    关键：content 必须在对象构造时读取完毕（而非在 read() 中惰性读取），
    因为 get_document 会先创建 temp 文件再调用 read()，需要确保 read() 返回完整内容。
    """

    def __init__(self, filepath: str, filename: str):
        self.filename = filename
        with open(filepath, 'rb') as f:
            self._content = f.read()

    async def read(self) -> bytes:
        return self._content


async def _upload_resume_files():
    """上传简历文件到 Milvus（直接使用内部 API，与 HTTP API 同一条处理链路）

    绕过 temp 文件机制，直接使用文件路径加载、切分、存储。
    仅在 Milvus/MySQL 可用时执行。
    """
    from app.rag.milvus_store import MilvusService
    from app.agent.tools.vector_search import set_current_user_id
    from app.utils.file_handler import get_file_md5_hex

    set_current_user_id(TEST_USER_ID)
    milvus = MilvusService()

    # 先检查是否已有数据（避免重复上传）
    existing = milvus.client.query(
        collection_name=milvus.collection_name,
        filter=f'user_id == "{TEST_USER_ID}"',
        output_fields=['id'],
        limit=5,
    )
    if len(existing) > 0:
        entities = milvus.client.query(
            collection_name=milvus.collection_name,
            filter=f'user_id == "{TEST_USER_ID}"',
            output_fields=['doc_entity'],
            limit=200,
        )
        entity_set = set(r.get('doc_entity', '') for r in entities)
        print(f"  [SKIP] 已有 {len(existing)}+ 条测试数据 (entities: {len(entity_set)})，跳过上传")
        return RESUME_FILES

    uploaded = []
    for filename in RESUME_FILES:
        file_path = str(RESUME_DIR / filename)
        if not os.path.exists(file_path):
            print(f"  [SKIP] 文件不存在: {file_path}")
            continue

        try:
            # 计算 MD5
            md5_hex = await get_file_md5_hex(file_path)

            # 检查 MD5 去重
            if await milvus.md5_store.check_md5_hex(md5_hex, TEST_USER_ID):
                print(f"  [SKIP] {filename}: MD5 已存在，跳过")
                continue

            # 加载文档
            documents = await milvus.document_processor.get_file_document(
                file_path, md5_hex, TEST_USER_ID
            )
            if not documents:
                print(f"  [WARN] {filename}: 加载内容为空")
                continue

            # 切分文档
            documents = await milvus.document_processor.spliter.split_documents(documents)
            if not documents:
                print(f"  [WARN] {filename}: 切分后为空")
                continue

            # 添加用户和文件元信息
            for doc in documents:
                doc.metadata['user_id'] = TEST_USER_ID
                doc.metadata['original_filename'] = filename
                doc.metadata['md5'] = md5_hex

            # 存储向量
            await asyncio.to_thread(milvus.add_documents, documents)

            # 保存 MD5 记录
            await milvus.md5_store.save_md5_hex(md5_hex, filename, filename, TEST_USER_ID)

            # 初始化文档权重
            category = milvus.document_processor._detect_category(file_path, filename)
            quality_score = milvus.document_processor._calc_quality_score(documents)
            await milvus.document_processor._init_doc_weights(
                md5_hex, TEST_USER_ID, filename, category, quality_score
            )

            uploaded.append(filename)
            print(f"  [OK] 上传成功: {filename} ({len(documents)} chunks)")
        except Exception as e:
            print(f"  [ERROR] 上传失败: {filename}: {type(e).__name__}: {e}")

    return uploaded


async def _cleanup_test_data():
    """清理测试数据"""
    from app.rag.milvus_store import MilvusService
    from app.db.db_config import AsyncSessionLocal
    from app.models.feedback import DocWeight
    from app.models.chat_history import ChatSession, ChatMessage, ChatThinkingEvent
    from sqlalchemy import delete

    try:
        milvus = MilvusService()
        # 删除测试用户的所有向量
        milvus.client.delete(
            collection_name=milvus.collection_name,
            filter=f'user_id == "{TEST_USER_ID}"',
        )
        print(f"  [OK] 已清理 Milvus 测试数据")
    except Exception as e:
        print(f"  [WARN] Milvus 清理失败: {e}")

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(delete(DocWeight).where(DocWeight.user_id == TEST_USER_ID))
            await session.commit()
        print(f"  [OK] 已清理 MySQL DocWeight 测试数据")
    except Exception as e:
        print(f"  [WARN] MySQL 清理失败: {e}")

    try:
        # 清理 MD5 去重记录（允许下次重新上传）
        milvus.md5_store.clear_user(TEST_USER_ID)
    except Exception:
        pass


# ── Session-scoped fixtures ──

@pytest.fixture(scope="session")
def test_user_id():
    """测试用户 ID"""
    return TEST_USER_ID


@pytest.fixture(scope="session")
def resume_uploaded():
    """Session 级别：上传简历文件到 Milvus（整个测试会话共享，仅上传一次）

    Returns:
        list: 成功上传的文件名列表
    """
    print(f"\n[Setup] 上传简历文件到 Milvus (user={TEST_USER_ID})...")
    try:
        uploaded = asyncio.run(_upload_resume_files())
        print(f"[Setup] 共上传 {len(uploaded)} 个文件")
    except Exception as e:
        print(f"[Setup] 上传失败: {e}")
        uploaded = []

    yield uploaded

    print(f"\n[Teardown] 保留测试数据供后续检查")


@pytest.fixture(autouse=True)
def reset_user_context():
    """每个测试前重置 ContextVar，确保测试隔离"""
    from app.agent.tools.vector_search import set_current_user_id
    set_current_user_id(TEST_USER_ID)
    yield
    # 测试后不重置，保持 user_id 可用


async def run_agent_query(query: str) -> str:
    """运行 Agent 查询并返回回答文本

    使用与 HTTP API 相同的 run_agent_non_stream 函数。

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
        session_id=f"test_{abs(hash(query)) % 100000}",
    )

    return result.get("final_answer", "")
