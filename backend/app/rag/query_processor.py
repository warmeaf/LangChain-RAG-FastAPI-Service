from typing import List
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.utils.factory import chat_model
from app.utils.config import rag_config
from app.core.logger_handler import logger


COMPRESS_PROMPT = PromptTemplate.from_template(
    "以下是一段长文本，请将其压缩为 {max_length} 字以内的摘要，保留所有关键信息：\n\n{query}\n\n压缩后的摘要："
)

DECOMPOSE_PROMPT = PromptTemplate.from_template(
    "以下问题可能包含多个子问题。请将其拆分为多个独立的问题，每行一个，最多 {max_queries} 个。"
    "如果问题只有一个，直接返回原问题。\n\n问题：{query}\n\n拆分结果："
)

EXPAND_PROMPT = PromptTemplate.from_template(
    "为以下查询生成 {max_expansions} 个语义相同但表达方式不同的变体，每行一个：\n\n{query}\n\n变体："
)


class QueryProcessor:
    """查询预处理器：压缩 + 拆解 + 扩展"""

    def __init__(self):
        qp_cfg = rag_config.get("query_processing", {})
        self.max_length = qp_cfg.get("max_length", 400)
        self.max_sub_queries = qp_cfg.get("max_sub_queries", 5)
        self.max_expansions = qp_cfg.get("max_expansions", 3)
        self.llm = chat_model

    async def process(self, query: str) -> List[str]:
        """返回 1~N 个查询变体"""
        processed = query

        # Step 1: 压缩
        if len(query) > self.max_length:
            processed = await self._compress(query)

        # Step 2: 拆分子问题
        sub_queries = await self._decompose(processed)

        # Step 3: 查询扩展
        all_variants = []
        for q in sub_queries:
            expanded = await self._expand(q)
            all_variants.extend(expanded)

        # 去重保持顺序
        seen = set()
        result = []
        for v in all_variants:
            if v not in seen:
                seen.add(v)
                result.append(v)

        logger.info(f"查询预处理: 原始长度={len(query)} → {len(result)}个变体")
        return result

    async def _compress(self, query: str) -> str:
        try:
            chain = COMPRESS_PROMPT | self.llm | StrOutputParser()
            result = await chain.ainvoke({"query": query, "max_length": self.max_length})
            return result.strip() if result else query
        except Exception as e:
            logger.warning(f"查询压缩失败: {e}")
            return query

    async def _decompose(self, query: str) -> List[str]:
        try:
            chain = DECOMPOSE_PROMPT | self.llm | StrOutputParser()
            result = await chain.ainvoke({"query": query, "max_queries": self.max_sub_queries})
            if result:
                lines = [line.strip() for line in result.strip().split("\n") if line.strip()]
                if lines:
                    return lines
        except Exception as e:
            logger.warning(f"查询拆解失败: {e}")
        return [query]

    async def _expand(self, query: str) -> List[str]:
        try:
            chain = EXPAND_PROMPT | self.llm | StrOutputParser()
            result = await chain.ainvoke({"query": query, "max_expansions": self.max_expansions})
            if result:
                lines = [line.strip() for line in result.strip().split("\n") if line.strip()]
                if lines:
                    return [query] + lines[:self.max_expansions]
        except Exception as e:
            logger.warning(f"查询扩展失败: {e}")
        return [query]
