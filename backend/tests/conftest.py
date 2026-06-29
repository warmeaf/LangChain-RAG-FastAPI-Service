"""测试基础设施 - 共享 fixtures 和配置"""

import os
import sys
import pytest
import asyncio
from pathlib import Path

# 确保 backend 目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("LLM_TYPE", "DEEPSEEK")
os.environ.setdefault("DEEPSEEK_API_KEY", os.getenv("DEEPSEEK_API_KEY", "sk-test"))
os.environ.setdefault("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
os.environ.setdefault("DEEPSEEK_MODEL_NAME", "deepseek-v4-flash")


@pytest.fixture(scope="session")
def event_loop():
    """为整个测试会话提供事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_user_id():
    """测试用户 ID"""
    return "test_user_agent_upgrade"


@pytest.fixture(scope="session")
def test_session_id():
    """测试会话 ID"""
    return "test_session_agent_upgrade"


@pytest.fixture
def sample_query():
    """示例查询"""
    return "王小明是谁？"


@pytest.fixture
def sample_resume_queries():
    """简历相关的测试查询集合"""
    return {
        "Q1": "王小明的邮箱和GitHub地址是什么？",
        "Q2": "李大乐在哪家上市公司担任销售总监？他管理多少人的团队？",
        "Q3": "赵明轩期望的薪资范围是多少？他使用什么开发框架？",
        "Q4": "余涵的求职意向是什么？她的最高学历和专业是什么？",
        "Q5": "韩小团获得了哪些专业认证？他毕业于哪所大学？",
    }


def pytest_configure(config):
    """Pytest 配置"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "smoke: marks tests as smoke tests"
    )
