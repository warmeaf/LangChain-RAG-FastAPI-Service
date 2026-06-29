"""Chat 服务层

处理 Agent / RAG 查询的业务逻辑。
Agent 使用新的 Plan-then-Execute 图（Anthropic 协议），
RAG 继续使用 OpenAI 兼容协议。
"""

from typing import List, Optional, Tuple, Dict, Any
import uuid

from fastapi import HTTPException

from app.core.logger_handler import logger
from app.rag.rag_service import RagService
from app.rag.reorder_service import reorder_service
from app.services import session_manager as sm


class ChatService:
    """路由服务层，处理业务逻辑"""

    async def handle_agent_query(
        self, query: str, session_id: Optional[str], user_id: str
    ) -> Tuple[str, str, dict]:
        """处理 Agent 查询（非流式，使用新 Plan-then-Execute 图）

        Returns:
            (session_id, response_text, steps_info)
        """
        from app.agent.graph import run_agent_non_stream
        from langchain_core.messages import HumanMessage, AIMessage

        session_id = session_id or str(uuid.uuid4())

        # 加载历史
        history = await sm.session_manager.get_history(session_id, user_id)
        history_messages = []
        if history:
            for user_msg, assistant_msg in history:
                history_messages.append(HumanMessage(content=user_msg))
                history_messages.append(AIMessage(content=assistant_msg))

        # 执行 Agent
        result = await run_agent_non_stream(
            query=query,
            user_id=user_id,
            session_id=session_id,
            history_messages=history_messages,
        )

        response_text = result.get("final_answer", "抱歉，无法回答这个问题。")
        plan = result.get("plan", [])
        tool_results = result.get("tool_results", {})

        # 保存到会话历史
        await sm.session_manager.add_message(session_id, user_id, query, response_text)

        # 构建 steps 信息
        steps_info = {
            "plan": [
                {
                    "id": s["id"],
                    "tool_name": s["tool_name"],
                    "reason": s["reason"],
                    "status": s["status"],
                }
                for s in plan
            ],
            "tool_results": tool_results,
        }

        return session_id, response_text, steps_info

    async def handle_rag_query(self, query: str, user_id: str) -> str:
        """处理 RAG 查询（保留 OpenAI 协议流水线）"""
        rag_service = RagService(user_id)
        response = await rag_service.rag_summary(query)
        return response

    async def handle_get_session(
        self, session_id: str, user_id: str
    ) -> List[Tuple[str, str]]:
        """获取会话历史"""
        history = await sm.session_manager.get_history(session_id, user_id)
        return history

    async def handle_get_thinking(
        self, session_id: str, user_id: str
    ):
        """获取会话的思考过程事件"""
        # 验证会话属于当前用户
        await sm.session_manager.get_session(session_id, user_id)
        return await sm.session_manager.get_thinking_events(session_id)

    async def handle_delete_session(
        self, session_id: str, user_id: str
    ) -> None:
        """删除会话"""
        await sm.session_manager.clear_session(session_id, user_id)

    async def handle_get_user_sessions(
        self, user_id: str, current_user_id: str
    ) -> List[Dict]:
        """获取用户会话列表"""
        if user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        sessions = await sm.session_manager.get_user_sessions(user_id)
        return sessions

    async def handle_reorder(
        self, query: str, documents: List[str]
    ) -> List[Dict[str, Any]]:
        """文档重排序"""
        try:
            result = await reorder_service.reorder_documents(query, documents)
            if result["success"]:
                logger.info(f"重排序完成: {len(result['documents'])} 个文档")
                return result["documents"]
            else:
                logger.warning(f"重排序失败: {result['error']}")
                return [{"document": doc, "similarity": 0.0} for doc in documents]
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"重排序出错: {str(e)}")


def get_router_service() -> ChatService:
    """获取路由服务实例（用于 FastAPI 依赖注入）"""
    return ChatService()
