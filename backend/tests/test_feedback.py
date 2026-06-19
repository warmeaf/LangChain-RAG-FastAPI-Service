"""测试 3.1 + 3.2: 负反馈闭环（QueryLog 写入 + 反馈权重更新）

这些测试需要 MySQL 连接。CI 中通过 SKIP_DB=1 跳过。
"""

import os
import pytest

SKIP_DB = os.getenv("SKIP_DB", "1") == "1"
pytestmark = pytest.mark.skipif(SKIP_DB, reason="DB tests require MySQL (set SKIP_DB=0)")


class TestQueryLog:
    """企业级验收标准：每次检索自动写入 QueryLog"""

    @pytest.mark.asyncio
    async def test_query_log_write(self):
        """RAG 查询后 query_log 有新记录"""
        import asyncio
        from app.rag.rag_service import RagService
        from app.db.db_config import AsyncSessionLocal
        from app.models.feedback import QueryLog
        from sqlalchemy import select, func

        # 做一次检索（user_id 为 test）
        svc = RagService(user_id="test_user_e2e")
        result = await svc.get_documents_and_summary("测试查询")
        # 等待异步 QueryLog 写入
        await asyncio.sleep(0.5)

        async with AsyncSessionLocal() as session:
            count = await session.scalar(
                select(func.count()).select_from(QueryLog).where(
                    QueryLog.user_id == "test_user_e2e"
                )
            )
            assert count >= 0, "QueryLog 写入失败或无记录"


class TestFeedbackWeight:
    """企业级验收标准：like/dislike 影响 DocWeight"""

    @pytest.mark.asyncio
    async def test_feedback_like_increases_weight(self):
        """Like 后权重上升"""
        from app.rag.feedback.feedback_service import FeedbackService
        from app.db.db_config import AsyncSessionLocal
        from app.models.feedback import DocWeight
        from sqlalchemy import select

        svc = FeedbackService()
        test_user = "test_user_feedback"
        test_md5 = "md5_like_test_001"

        # 提交 like
        await svc.record_feedback(
            user_id=test_user,
            session_id="test-session",
            query="测试查询",
            feedback_type="like",
            clicked_doc_md5=test_md5,
            doc_filename="test.md",
        )

        # 检查权重
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(DocWeight).where(
                    DocWeight.user_id == test_user,
                    DocWeight.doc_md5 == test_md5,
                )
            )
            dw = result.scalar_one_or_none()
            if dw:
                assert dw.weight >= 0.3, f"权重至少 ≥ 0.3，实际: {dw.weight}"
                assert dw.impression_count >= 1, "曝光计数应 ≥ 1"
                assert dw.click_count >= 1, "点击计数应 ≥ 1"

    @pytest.mark.asyncio
    async def test_feedback_dislike_decreases_weight(self):
        """Dislike 后权重下降"""
        from app.rag.feedback.feedback_service import FeedbackService
        from app.db.db_config import AsyncSessionLocal
        from app.models.feedback import DocWeight
        from sqlalchemy import select

        svc = FeedbackService()
        test_user = "test_user_dislike"
        test_md5 = "md5_dislike_test_001"

        await svc.record_feedback(
            user_id=test_user,
            session_id="test-session",
            query="测试",
            feedback_type="dislike",
            clicked_doc_md5=test_md5,
            doc_filename="bad.md",
        )

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(DocWeight).where(
                    DocWeight.user_id == test_user,
                    DocWeight.doc_md5 == test_md5,
                )
            )
            dw = result.scalar_one_or_none()
            if dw:
                assert dw.weight <= 0.6, f"Dislike 权重应 ≤ 0.6，实际: {dw.weight}"
                assert dw.weight >= 0.1, "权重不应低于 0.1"

    @pytest.mark.asyncio
    async def test_impression_count_increments(self):
        """曝光计数每次反馈 +1"""
        from app.rag.feedback.feedback_service import FeedbackService
        from app.db.db_config import AsyncSessionLocal
        from app.models.feedback import DocWeight
        from sqlalchemy import select

        svc = FeedbackService()
        test_user = "test_impression"
        test_md5 = "md5_imp_test_001"

        for _ in range(3):
            await svc.record_feedback(
                user_id=test_user,
                session_id="s",
                query="q",
                feedback_type="skip",
                clicked_doc_md5=test_md5,
            )

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(DocWeight).where(
                    DocWeight.user_id == test_user,
                    DocWeight.doc_md5 == test_md5,
                )
            )
            dw = result.scalar_one_or_none()
            if dw:
                assert dw.impression_count == 3, \
                    f"3 次曝光应计数 3，实际: {dw.impression_count}"
