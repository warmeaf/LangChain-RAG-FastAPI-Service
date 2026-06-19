"""测试 1.3: 代码 AST 切分（tree-sitter 多语言）"""

import pytest
import tempfile
import os
from app.rag.document_handler.code_processor import CodeProcessor


def _write_temp(content, suffix):
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False)
    tmp.write(content)
    tmp.close()
    return tmp.name


PY_CODE = """
class UserService:
    \"\"\"用户服务\"\"\"
    def login(self, user, pwd):
        return True

    def logout(self, user):
        pass

def main():
    print('hello')
"""

JS_CODE = """
class UserService {
    login(user, pwd) {
        return true;
    }
    logout(user) {
        return false;
    }
}
function main() {
    console.log('start');
}
"""


class TestCodeProcessor:
    """企业级验收标准：Python/JS 均按函数/类切分，保留上下文"""

    @pytest.mark.asyncio
    async def test_python_splits_into_chunks(self):
        """Python: ≥ 3 chunks（class + 方法 + 顶层函数）"""
        path = _write_temp(PY_CODE, ".py")
        try:
            docs = await CodeProcessor().process(path)
            assert len(docs) >= 3, f"Python 期望 ≥3 chunks，实际 {len(docs)}"
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_python_has_class_context(self):
        """Python: chunk 含 'class: UserService' 上下文"""
        path = _write_temp(PY_CODE, ".py")
        try:
            docs = await CodeProcessor().process(path)
            method_docs = [d for d in docs if d.metadata.get("node_type") == "function_definition"]
            found = any("class: UserService" in d.page_content for d in method_docs)
            assert found, f"方法 chunk 应含类上下文"
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_python_has_function_names(self):
        """Python: chunk 含 'def: login' 和 'def: main'"""
        path = _write_temp(PY_CODE, ".py")
        try:
            docs = await CodeProcessor().process(path)
            flat = "\n".join(d.page_content for d in docs)
            assert "def: login" in flat, f"缺少 def: login"
            assert "def: main" in flat, f"缺少 def: main"
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_javascript_splits_into_chunks(self):
        """JS: ≥ 2 chunks"""
        path = _write_temp(JS_CODE, ".js")
        try:
            docs = await CodeProcessor().process(path)
            assert len(docs) >= 2, f"JS 期望 ≥2 chunks，实际 {len(docs)}"
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_javascript_has_context(self):
        """JS: chunk 含 'class: UserService' 上下文"""
        path = _write_temp(JS_CODE, ".js")
        try:
            docs = await CodeProcessor().process(path)
            flat = "\n".join(d.page_content for d in docs)
            has_context = "class: UserService" in flat
            has_func = "def: main" in flat or "function_declaration: main" in flat
            assert has_context or has_func, f"JS 应保留上下文"
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_fallback_on_invalid_syntax(self):
        """语法错误退化为空行分块，不崩溃"""
        path = _write_temp("this is not valid python {{{", ".py")
        try:
            docs = await CodeProcessor().process(path)
            assert len(docs) >= 0  # 不崩溃
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_unknown_extension_returns_empty(self):
        """不支持的文件类型返回空"""
        path = _write_temp("some text", ".txt")
        try:
            docs = await CodeProcessor().process(path)
            assert docs == []
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_metadata_has_language_and_node_type(self):
        """metadata 含 language 和 node_type"""
        path = _write_temp(PY_CODE, ".py")
        try:
            docs = await CodeProcessor().process(path)
            for d in docs:
                assert "language" in d.metadata
                assert d.metadata["language"] == "python"
                assert "node_type" in d.metadata
        finally:
            os.unlink(path)
