from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Optional

from app.rag.feedback.feedback_service import FeedbackService
from app.utils.auth_utils import get_current_user_id

feedback_router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    session_id: str
    query: str
    feedback_type: str = Field(..., pattern="^(like|dislike|skip)$")
    rating: Optional[int] = Field(None, ge=1, le=5)
    dwell_time_ms: Optional[int] = None
    clicked_doc_md5: Optional[str] = None
    clicked_doc_filename: Optional[str] = None


@feedback_router.post("")
async def submit_feedback(
    req: FeedbackRequest,
    user_id: str = Depends(get_current_user_id),
):
    service = FeedbackService()
    await service.record_feedback(
        user_id=user_id,
        session_id=req.session_id,
        query=req.query,
        feedback_type=req.feedback_type,
        rating=req.rating,
        dwell_time_ms=req.dwell_time_ms,
        clicked_doc_md5=req.clicked_doc_md5,
        doc_filename=req.clicked_doc_filename,
    )
    return {"success": True}


@feedback_router.get("/stats")
async def get_feedback_stats(
    user_id: str = Depends(get_current_user_id),
):
    service = FeedbackService()
    stats = await service.get_stats(user_id)
    return stats
