from sqlalchemy import (
    Column, BigInteger, String, Text, Boolean, Integer,
    Float, TIMESTAMP, JSON, Enum as SAEnum, UniqueConstraint, Index
)
from sqlalchemy.sql import func

from app.db.db_config import Base


class UserFeedback(Base):
    __tablename__ = "user_feedback"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False)
    session_id = Column(String(64), nullable=False)
    query = Column(Text, nullable=False)
    doc_md5 = Column(String(64))
    doc_filename = Column(String(512))
    feedback_type = Column(SAEnum("like", "dislike", "skip", name="feedback_type_enum"))
    rating = Column(Integer)
    dwell_time_ms = Column(Integer)
    clicked = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index("idx_user_query", "user_id", "query"),
    )


class DocWeight(Base):
    __tablename__ = "doc_weights"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False)
    doc_md5 = Column(String(64), nullable=False)
    doc_filename = Column(String(512))
    category = Column(String(128))
    weight = Column(Float, default=1.0)
    quality_score = Column(Float, default=0.7)
    impression_count = Column(Integer, default=0)
    click_count = Column(Integer, default=0)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "doc_md5", name="uk_user_md5"),
    )


class QueryLog(Base):
    __tablename__ = "query_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(64))
    query = Column(Text, nullable=False)
    retrieved_docs = Column(JSON)
    clicked_doc_md5 = Column(String(64))
    session_id = Column(String(64))
    created_at = Column(TIMESTAMP, server_default=func.now())
