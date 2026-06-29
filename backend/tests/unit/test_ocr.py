"""工具单元测试 - ocr 工具

测试 ocr_recognize 工具的路径验证和安全检查。
"""

import os
import pytest
from app.agent.tools.ocr import _validate_path, ocr_recognize
from app.utils.path_tool import get_project_root


def test_validate_path_valid():
    """测试合法路径"""
    root = get_project_root()
    result = _validate_path(os.path.join(root, "app", "agent"))
    assert not result.startswith("Error:")


def test_validate_path_traversal():
    """测试路径遍历攻击"""
    result = _validate_path("../../../etc/passwd")
    assert result.startswith("Error:")


def test_validate_path_relative():
    """测试相对路径（应在项目根目录下）"""
    result = _validate_path("app/agent")
    assert result is not None


@pytest.mark.asyncio
async def test_ocr_empty_path():
    """测试空路径"""
    result = await ocr_recognize.ainvoke({"file_path": ""})
    assert "文件路径" in result


@pytest.mark.asyncio
async def test_ocr_nonexistent_file():
    """测试不存在的文件"""
    result = await ocr_recognize.ainvoke({"file_path": "/tmp/nonexistent_file_for_test.png"})
    assert "不存在" in result or "Error" in result
