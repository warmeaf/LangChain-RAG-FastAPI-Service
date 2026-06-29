"""工具 XML 描述生成器

从工具函数签名 + docstring 生成 Anthropic 风格的 XML 工具描述（用于系统提示词），
同时生成 OpenAI/Anthropic JSON Schema（用于 API 请求中的 tools 参数）。

两份定义从同一源生成，保持一致性。
"""

from typing import List, Callable, Any
import json


def tool_to_json_schema(tool_func: Callable) -> dict:
    """从 LangChain @tool 函数生成 Anthropic-compatible JSON Schema

    优先使用 args_schema（Pydantic 模型），否则从函数签名推断。
    """
    name = getattr(tool_func, 'name', None) or getattr(tool_func, '__name__', 'unknown')
    description = getattr(tool_func, 'description', '') or (tool_func.__doc__ or '').strip()

    # 尝试从 args_schema 获取参数定义
    if hasattr(tool_func, 'args_schema') and tool_func.args_schema:
        try:
            schema = tool_func.args_schema.model_json_schema()
            return {
                "name": name,
                "description": description,
                "input_schema": {
                    "type": "object",
                    "properties": schema.get("properties", {}),
                    "required": schema.get("required", []),
                },
            }
        except Exception:
            pass

    # 降级：从函数签名推断简单 schema
    import inspect
    sig = inspect.signature(tool_func)
    properties = {}
    required = []
    for param_name, param in sig.parameters.items():
        if param_name in ('self', 'cls', 'return'):
            continue
        param_type = "string"
        if param.annotation != inspect.Parameter.empty:
            ann = param.annotation
            if ann is str:
                param_type = "string"
            elif ann is int:
                param_type = "integer"
            elif ann is float:
                param_type = "number"
            elif ann is bool:
                param_type = "boolean"
            elif ann is dict:
                param_type = "object"

        properties[param_name] = {"type": param_type, "description": f"{param_name} 参数"}
        if param.default == inspect.Parameter.empty:
            required.append(param_name)

    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


def tool_to_xml(tool_func: Callable, indent: int = 0) -> str:
    """从工具函数生成 Anthropic 风格的 XML 工具描述

    用于注入系统提示词，让 LLM 理解工具用途和参数。

    输出格式：
    <tool name="vector_search">
      <description>在向量数据库中语义检索文档...</description>
      <parameters>
        <parameter name="query" type="string" required="true">检索查询语句</parameter>
      </parameters>
    </tool>
    """
    name = getattr(tool_func, 'name', None) or getattr(tool_func, '__name__', 'unknown')
    description = getattr(tool_func, 'description', '') or (tool_func.__doc__ or '').strip()

    # 获取参数信息
    if hasattr(tool_func, 'args_schema') and tool_func.args_schema:
        try:
            schema = tool_func.args_schema.model_json_schema()
            props = schema.get("properties", {})
            required_list = schema.get("required", [])
        except Exception:
            props, required_list = _infer_params_from_signature(tool_func)
    else:
        props, required_list = _infer_params_from_signature(tool_func)

    prefix = " " * indent
    lines = [f"{prefix}<tool name=\"{name}\">"]
    lines.append(f"{prefix}  <description>{description}</description>")
    lines.append(f"{prefix}  <parameters>")

    for param_name, param_info in props.items():
        if param_name in ('user_id',):
            continue  # user_id 不在工具描述中暴露
        ptype = param_info.get("type", "string")
        pdesc = param_info.get("description", "")
        required = "true" if param_name in required_list else "false"
        lines.append(f'{prefix}    <parameter name="{param_name}" type="{ptype}" required="{required}">{pdesc}</parameter>')

    lines.append(f"{prefix}  </parameters>")
    lines.append(f"{prefix}</tool>")

    return "\n".join(lines)


def tools_to_xml(tools: List[Callable], indent: int = 0) -> str:
    """将多个工具转为 XML 字符串（用空行分隔）"""
    return "\n\n".join(tool_to_xml(t, indent) for t in tools)


def tools_to_json_schemas(tools: List[Callable]) -> List[dict]:
    """将多个工具转为 Anthropic-compatible JSON Schema 列表"""
    return [tool_to_json_schema(t) for t in tools]


def _infer_params_from_signature(tool_func: Callable) -> tuple:
    """从函数签名推断参数信息"""
    import inspect
    sig = inspect.signature(tool_func)
    props = {}
    required = []
    for param_name, param in sig.parameters.items():
        if param_name in ('self', 'cls', 'return'):
            continue
        param_type = "string"
        if param.annotation != inspect.Parameter.empty:
            ann = param.annotation
            if ann is str:
                param_type = "string"
            elif ann is int:
                param_type = "integer"
            elif ann is float:
                param_type = "number"
            elif ann is bool:
                param_type = "boolean"
        props[param_name] = {"type": param_type, "description": ""}
        if param.default == inspect.Parameter.empty:
            required.append(param_name)
    return props, required
