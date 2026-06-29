"""Chat 路由

端点：
- POST /chat/agent/query/stream — Agent 流式 SSE 响应（Plan-then-Execute Agent Loop）
- GET /chat/agent/query — Agent 非流式响应
- POST /chat/rag/query — RAG 检索（保留兼容）
- GET/DELETE /chat/session/* — 会话管理
- GET /chat/session/{session_id}/thinking — 思考事件重放
"""

import json
import uuid
from typing import List

from fastapi.routing import APIRouter
from fastapi import Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.router.chat_service import ChatService, get_router_service
from app.schemas.models import (
    QueryRequest, RAGResponse, RAGRequest, SessionResponse,
    ReorderResponse, ReorderRequest,
)
from app.utils.auth_utils import get_current_user_id
from app.core.success_response import success_response
from app.core.rate_limit import rate_limit
from app.core.logger_handler import logger

chat_router = APIRouter(prefix="/chat", tags=["chat"])


@chat_router.post("/agent/query/stream")
async def query_stream(
    request: QueryRequest,
    user_id: str = Depends(get_current_user_id),
    _: None = Depends(rate_limit(limit=60, window=60)),
):
    """Agent 流式响应 — Plan-then-Execute Agent Loop

    SSE 事件类型：
    - plan_created: 计划制定完成 {steps: [...], total_steps: N}
    - step_start: 开始执行某步 {step_id, tool_name, reason}
    - step_done: 某步执行完成 {step_id, status: "done"|"failed"|"skipped"}
    - step_replan: 计划被修正 {reason, new_steps, new_total_steps}
    - answer_start: 开始生成最终回答 {}
    - delta: 回答文本增量 {content: str}
    - done: 流结束 {}
    - thinking: 兼容旧版思维链事件 {stage, content, details}
    - error: 错误事件 {content: str}
    """
    from app.agent.graph import run_agent_stream
    from app.services import session_manager as sm
    from langchain_core.messages import HumanMessage, AIMessage

    session_id = request.session_id or str(uuid.uuid4())

    async def event_generator():
        thinking_events = []
        final_answer = ""

        try:
            # 加载聊天历史（Anthropic content blocks 兼容格式）
            history = await sm.session_manager.get_history(session_id, user_id)
            history_messages = []
            if history:
                for user_msg, assistant_msg in history:
                    history_messages.append(HumanMessage(content=user_msg))
                    history_messages.append(AIMessage(content=assistant_msg))

            # 流式执行 Agent
            async for event in run_agent_stream(
                query=request.query,
                user_id=user_id,
                session_id=session_id,
                history_messages=history_messages,
            ):
                event_type = event.get("type", "")

                # 收集 thinking 事件
                if event_type in ("plan_created", "step_start", "step_done", "step_replan", "thinking"):
                    thinking_events.append(event)

                # 收集 delta 回答
                if event_type == "delta":
                    final_answer += event.get("content", "")

                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            # 保存到会话历史
            if final_answer:
                message_id = await sm.session_manager.add_message(
                    session_id, user_id, request.query, final_answer
                )
                if thinking_events:
                    try:
                        await sm.session_manager.save_thinking_events(
                            session_id, message_id, thinking_events
                        )
                    except Exception as e:
                        logger.error(f"保存思考事件失败: {e}")

        except Exception as e:
            logger.error(f"Agent 流式响应错误: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e), 'session_id': session_id}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@chat_router.post("/rag/query", response_model=RAGResponse)
async def query_rag(
    request: RAGRequest,
    user_id: str = Depends(get_current_user_id),
    router_service: ChatService = Depends(get_router_service),
    _: None = Depends(rate_limit(limit=60, window=60)),
):
    """RAG 检索（保留兼容，继续使用 OpenAI 协议流水线）"""
    response = await router_service.handle_rag_query(request.query, user_id)
    return success_response(data=RAGResponse(response=response))


@chat_router.get("/session/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    router_service: ChatService = Depends(get_router_service),
):
    """获取会话信息"""
    history = await router_service.handle_get_session(session_id, user_id)
    return success_response(data=SessionResponse(session_id=session_id, history=history))


@chat_router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    router_service: ChatService = Depends(get_router_service),
):
    """删除会话"""
    await router_service.handle_delete_session(session_id, user_id)
    return success_response(message=f"Session {session_id} deleted successfully")


@chat_router.get("/session/{session_id}/thinking")
async def get_session_thinking(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    router_service: ChatService = Depends(get_router_service),
):
    """获取会话的思考过程事件（支持前端刷新后重放）"""
    thinking = await router_service.handle_get_thinking(session_id, user_id)
    return success_response(data={"session_id": session_id, "thinking": thinking})


@chat_router.get("/sessions")
async def get_current_user_sessions(
    user_id: str = Depends(get_current_user_id),
    router_service: ChatService = Depends(get_router_service),
):
    """获取当前用户的所有会话"""
    sessions = await router_service.handle_get_user_sessions(user_id, user_id)
    return success_response(data={"sessions": sessions})


@chat_router.get("/sessions/{user_id}")
async def get_user_sessions(
    user_id: str,
    current_user_id: str = Depends(get_current_user_id),
    router_service: ChatService = Depends(get_router_service),
):
    """获取指定用户所有会话（需鉴权）"""
    session_ids = await router_service.handle_get_user_sessions(user_id, current_user_id)
    return success_response(data={"sessions": session_ids})


@chat_router.post("/reorder", response_model=ReorderResponse)
async def reorder_documents(
    request: ReorderRequest,
    router_service: ChatService = Depends(get_router_service),
    _: None = Depends(rate_limit(limit=60, window=60)),
):
    """文档重排序"""
    sorted_docs = await router_service.handle_reorder(request.query, request.documents)
    return success_response(data=ReorderResponse(documents=sorted_docs))
