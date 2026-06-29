"""单元测试 - Agent 图和 Prompt 系统"""

import pytest
from app.agent.graph import _build_agent_graph, DEFAULT_TOOLS
from app.agent.state import AgentState
from app.prompt.tool_xml import tools_to_xml, tools_to_json_schemas, tool_to_xml
from app.utils.prompt_loader import load_system_prompts, build_stage_prompt


def test_graph_builds_successfully():
    """测试 Agent 图可以正常构建"""
    graph = _build_agent_graph(DEFAULT_TOOLS)
    nodes = list(graph.nodes.keys())
    assert "__start__" in nodes
    assert "planning" in nodes
    assert "execution" in nodes
    assert "summarization" in nodes


def test_all_tools_have_schemas():
    """测试所有工具都有有效的 JSON Schema"""
    schemas = tools_to_json_schemas(DEFAULT_TOOLS)
    assert len(schemas) == len(DEFAULT_TOOLS)
    for schema in schemas:
        assert "name" in schema
        assert "input_schema" in schema
        assert "type" in schema["input_schema"]


def test_all_tools_have_xml():
    """测试所有工具都有 XML 描述"""
    xml = tools_to_xml(DEFAULT_TOOLS)
    for tool in DEFAULT_TOOLS:
        assert tool.name in xml


def test_tool_xml_single():
    """测试单个工具的 XML 生成"""
    from app.agent.tools.time import get_current_time
    xml = tool_to_xml(get_current_time)
    assert "get_current_time" in xml
    assert "<tool" in xml
    assert "description" in xml.lower()


def test_system_prompts_load():
    """测试系统提示词可以正常加载"""
    prompts = load_system_prompts()
    assert "base" in prompts
    assert "planning" in prompts
    assert "execution" in prompts
    assert "summarization" in prompts
    assert len(prompts["base"]) > 0


def test_build_stage_prompt_planning():
    """测试构建 Planning 阶段提示词"""
    tools_xml = "<tool name='test'><description>Test</description></tool>"
    result = build_stage_prompt("planning", tools_xml)
    assert len(result) > 0
    assert "test" in result
    assert "{tools}" not in result  # 应已被替换


def test_build_stage_prompt_summarization():
    """测试构建 Summarization 阶段提示词"""
    result = build_stage_prompt("summarization", "(无工具)")
    assert len(result) > 0
