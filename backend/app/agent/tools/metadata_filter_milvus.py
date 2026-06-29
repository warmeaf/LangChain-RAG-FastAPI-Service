"""Milvus 标量字段过滤工具

全新工具：将自然语言过滤条件转为 Milvus expr 表达式，在 Milvus 层做标量过滤。
可用标量字段：id, text, user_id, doc_entity, doc_weight, created_at, metadata(JSON)
"""

from typing import Optional
from contextvars import ContextVar

from langchain_core.tools import tool

from app.core.logger_handler import logger
from app.rag.milvus_store import MilvusService

current_user_id_var: ContextVar[str] = ContextVar('current_user_id', default=None)

# Milvus 可用标量字段说明
FILTERABLE_FIELDS = """
可用过滤字段：
  - doc_entity: 文档主体标识（如人名、公司名），精确匹配，类型 VARCHAR
  - doc_weight: 文档权重，范围比较，类型 FLOAT
  - created_at: 创建时间戳（Unix 秒），范围比较，类型 INT64
  - metadata: JSON 字段，可用 metadata["key"] 访问嵌套字段，类型 JSON
  - id: 文档唯一标识，精确匹配，类型 VARCHAR
  - text: 文档文本内容，支持 LIKE 模糊匹配，类型 VARCHAR

支持的操作符：
  - == 等于
  - != 不等于
  - >, >=, <, <= 大小比较
  - && AND 逻辑与
  - || OR 逻辑或
  - like 文本模糊匹配
  - in 包含于列表

示例：
  - doc_entity == "王小明"
  - doc_weight > 0.8
  - created_at > 1704038400
  - doc_entity like "张%"
  - doc_entity in ["王小明", "赵明轩"]
"""


@tool
async def metadata_filter_milvus(condition: str, user_id: Optional[str] = None) -> str:
    """在 Milvus 向量数据库中按标量字段过滤文档。

    工具内部将自然语言条件转为 Milvus expr 表达式，返回匹配文档的计数和统计摘要。
    适合按文档主体（人/公司）、权重、时间范围等结构化条件筛选文档。

    Args:
        condition: 自然语言过滤条件描述（如"doc_entity 是王小明"、"权重高于0.8的文档"、"2024年之后创建的"）
        user_id: 用户ID（系统自动注入，无需手动传入）
    """
    from app.agent.tools.vector_search import get_current_user_id
    effective_user_id = user_id or get_current_user_id()
    if not effective_user_id:
        return "错误: 无法确定用户身份"

    milvus = MilvusService()

    try:
        # 将自然语言条件转为 Milvus expr
        expr = await _nl_to_milvus_expr(condition)
        if not expr:
            return f"无法解析过滤条件: {condition}\n\n{FILTERABLE_FIELDS}"

        # 合并 user_id 过滤
        full_expr = f'user_id == "{effective_user_id}" && ({expr})'
        logger.info(f"Milvus 过滤: {full_expr}")

        # 执行查询
        results = milvus.client.query(
            collection_name=milvus.collection_name,
            filter=full_expr,
            output_fields=["id", "doc_entity", "doc_weight", "created_at", "metadata"],
            limit=100,
        )

        if not results:
            return f"过滤条件 '{condition}' 未匹配到任何文档。\n\n{FILTERABLE_FIELDS}"

        # 生成统计摘要
        total = len(results)
        entities = set()
        weights = []
        for r in results:
            if r.get("doc_entity"):
                entities.add(r["doc_entity"])
            if r.get("doc_weight"):
                weights.append(r["doc_weight"])

        lines = [f"Metadata 过滤结果（匹配 {total} 条文档）:"]
        lines.append(f"- 涉及实体: {', '.join(sorted(entities)[:10])}")
        if weights:
            lines.append(f"- 权重范围: {min(weights):.2f} ~ {max(weights):.2f}")
        lines.append(f"\n匹配文档 ID 列表:")
        for i, r in enumerate(results[:20], 1):
            entity = r.get("doc_entity", "N/A")
            weight = r.get("doc_weight", "N/A")
            lines.append(f"  [{i}] {r['id']} | entity={entity} | weight={weight}")

        if len(results) > 20:
            lines.append(f"  ... 还有 {len(results) - 20} 条结果")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Milvus 过滤失败: {e}", exc_info=True)
        return f"Metadata 过滤出错: {str(e)}\n\n{FILTERABLE_FIELDS}"


async def _nl_to_milvus_expr(natural_condition: str) -> str:
    """将自然语言条件转为 Milvus expr 表达式（使用 LLM 转换）"""
    from app.utils.factory import create_chat_model

    prompt = f"""{FILTERABLE_FIELDS}

请将以下自然语言过滤条件转换为 Milvus expr 表达式。只输出表达式，不要任何解释。

注意：
1. 字符串值必须用双引号包裹，如 doc_entity == "王小明"
2. 时间戳是 Unix 秒，2024-01-01 = 1704038400
3. 只输出一行表达式

自然语言条件：{natural_condition}
"""
    try:
        llm = create_chat_model(streaming=False, temperature=0.1)
        result = await llm.ainvoke(prompt)
        expr = result.content.strip() if hasattr(result, 'content') else str(result).strip()
        # 清理输出
        if expr.startswith("```"):
            expr = expr.split("\n", 1)[-1] if "\n" in expr else expr
            expr = expr.replace("```", "").strip()
        # 基本验证
        if any(op in expr for op in ['==', '!=', '>', '<', 'like', 'in']):
            logger.info(f"NL→Milvus expr: {natural_condition[:50]} → {expr}")
            return expr
    except Exception as e:
        logger.warning(f"NL→Milvus expr 转换失败: {e}")

    # 降级：尝试简单规则转换
    return _simple_rule_based_expr(natural_condition)


def _simple_rule_based_expr(condition: str) -> Optional[str]:
    """简单规则转换：处理常见的过滤模式"""
    import re

    # 模式：entity/文档主体 是/为 X
    m = re.search(r'(?:entity|文档主体|doc_entity).*?[是为是](.+?)(?:[，的]|$)', condition)
    if m:
        entity = m.group(1).strip()
        return f'doc_entity == "{entity}"'

    # 模式：权重 >/>=/</<= N (包括中文"高于/低于/大于/小于")
    m = re.search(r'(?:权重|doc_weight)\s*(>=?|<=?|==?|高于|低于|大于|小于)\s*([\d.]+)', condition)
    if m:
        op_str = m.group(1)
        val = float(m.group(2))
        # 中文操作符转符号
        op_map = {"高于": ">", "低于": "<", "大于": ">", "小于": "<"}
        op = op_map.get(op_str, op_str)
        return f"doc_weight {op} {val}"

    # 模式：包含/含有关键词 X
    m = re.search(r'(?:包含|含有|文件名.*?)(.+?)(?:[，的]|$)', condition)
    if m:
        keyword = m.group(1).strip()
        return f'doc_entity like "%{keyword}%"'

    return None
