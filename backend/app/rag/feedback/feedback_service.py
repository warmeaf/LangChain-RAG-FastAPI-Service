from typing import Optional
from sqlalchemy import select, func
from app.db.db_config import AsyncSessionLocal
from app.models.feedback import UserFeedback, DocWeight
from app.core.logger_handler import logger


class FeedbackService:
    """用户反馈服务"""

    async def record_feedback(
        self,
        user_id: str,
        session_id: str,
        query: str,
        feedback_type: str,
        rating: Optional[int] = None,
        dwell_time_ms: Optional[int] = None,
        clicked_doc_md5: Optional[str] = None,
        doc_filename: Optional[str] = None,
    ):
        async with AsyncSessionLocal() as session:
            fb = UserFeedback(
                user_id=user_id,
                session_id=session_id,
                query=query,
                feedback_type=feedback_type,
                rating=rating,
                dwell_time_ms=dwell_time_ms,
                clicked=True if clicked_doc_md5 else False,
                doc_md5=clicked_doc_md5,
                doc_filename=doc_filename,
            )
            session.add(fb)

            if clicked_doc_md5:
                await self._update_weight(
                    session, user_id, clicked_doc_md5, doc_filename, feedback_type
                )

            await session.commit()

    async def _update_weight(self, session, user_id, doc_md5, filename, feedback_type):
        result = await session.execute(
            select(DocWeight).where(
                DocWeight.user_id == user_id,
                DocWeight.doc_md5 == doc_md5,
            )
        )
        dw = result.scalar_one_or_none()

        if dw is None:
            dw = DocWeight(
                user_id=user_id,
                doc_md5=doc_md5,
                doc_filename=filename,
                weight=0.5,
                impression_count=0,
                click_count=0,
                quality_score=0.7,
            )
            session.add(dw)

        # 更新曝光和点击计数
        dw.impression_count = (dw.impression_count or 0) + 1
        if feedback_type == "like":
            dw.click_count = (dw.click_count or 0) + 1

        # 贝叶斯平滑 CTR: (clicks + prior_click) / (impressions + prior_impression)
        prior_click = 1.0
        prior_impression = 2.0
        smoothed_ctr = (dw.click_count + prior_click) / (dw.impression_count + prior_impression)

        # 反馈即时调整
        if feedback_type == "like":
            feedback_bonus = 0.05
        elif feedback_type in ("dislike", "skip"):
            feedback_bonus = -0.05
        else:
            feedback_bonus = 0.0

        # 新权重 = 贝叶斯CTR (0.6) + 历史权重 (0.2) + 即时反馈 (0.2)
        dw.weight = round(
            smoothed_ctr * 0.6 +
            (dw.weight or 0.5) * 0.2 +
            (0.5 + feedback_bonus) * 0.2,
            3
        )
        dw.weight = max(0.1, min(1.0, dw.weight))

    async def get_stats(self, user_id: str):
        async with AsyncSessionLocal() as session:
            total = await session.scalar(
                select(func.count()).select_from(UserFeedback).where(
                    UserFeedback.user_id == user_id
                )
            )
            likes = await session.scalar(
                select(func.count()).select_from(UserFeedback).where(
                    UserFeedback.user_id == user_id,
                    UserFeedback.feedback_type == "like",
                )
            )
            return {
                "total_feedback": total or 0,
                "like_rate": (likes / total) if total else 0,
            }
