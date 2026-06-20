import os
import hashlib
import aiofiles
import asyncio
import sys
from typing import List

from langchain_core.documents import Document

from app.core.logger_handler import logger
from app.utils.path_tool import get_abstract_path


class FontBBoxStreamFilter:
    def __init__(self, stream):
        self.stream = stream
        
    def write(self, data):
        if isinstance(data, bytes):
            if b'FontBBox from font descriptor' not in data:
                self.stream.write(data)
        else:
            if 'FontBBox from font descriptor' not in data:
                self.stream.write(data)
            
    def flush(self):
        self.stream.flush()

sys.stderr = FontBBoxStreamFilter(sys.stderr)


# ── MD5 计算 ──

async def get_file_md5_hex(file_path: str) -> str:
    """获取文件的md5值"""
    abs_file_path = get_abstract_path(file_path) if not os.path.isabs(file_path) else file_path
    if not os.path.exists(abs_file_path):
        logger.error(f"【md5计算】文件路径 {abs_file_path} 不存在")
        return ""
    if not os.path.isfile(abs_file_path):
        logger.error(f"【md5计算】文件路径 {abs_file_path} 不是文件")
        return ""
    md5_object = hashlib.md5()
    chunk_size = 1024
    try:
        async with aiofiles.open(abs_file_path, "rb") as f:
            while chunk := await f.read(chunk_size):
                md5_object.update(chunk)
    except Exception as e:
        logger.error(f"【md5计算】读取文件 {abs_file_path} 时出错: {e}")
        return ""
    return md5_object.hexdigest()

def get_file_md5_hex_sync(file_path: str) -> str:
    """同步获取文件的md5值（用于多线程场景）"""
    abs_file_path = get_abstract_path(file_path) if not os.path.isabs(file_path) else file_path
    if not os.path.exists(abs_file_path):
        logger.error(f"【md5计算】文件路径 {abs_file_path} 不存在")
        return ""
    if not os.path.isfile(abs_file_path):
        logger.error(f"【md5计算】文件路径 {abs_file_path} 不是文件")
        return ""
    md5_object = hashlib.md5()
    chunk_size = 1024
    try:
        with open(abs_file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                md5_object.update(chunk)
    except Exception as e:
        logger.error(f"【md5计算】读取文件 {abs_file_path} 时出错: {e}")
        return ""
    return md5_object.hexdigest()


# ── 目录遍历 ──

async def listdir_allowed_type(path: str, allowed_types: tuple[str]) -> tuple:
    """获取指定目录下所有允许的文件类型"""
    abs_path = get_abstract_path(path) if not os.path.isabs(path) else path
    if not os.path.exists(abs_path):
        logger.error(f"【文件列表】目录路径 {abs_path} 不存在")
        return ()
    if not os.path.isdir(abs_path):
        logger.error(f"【文件列表】目录路径 {abs_path} 不是目录")
        return ()
    file_list = []
    for f in await asyncio.to_thread(os.listdir, abs_path):
        if f.endswith(allowed_types):
            file_path = os.path.join(abs_path, f)
            file_list.append(file_path)
    return tuple(file_list)


# ── 文档加载器 ──

async def pdf_loader(file_path: str, password: str = None) -> List[Document]:
    """PDF 加载器：先尝试 unstructured，失败回退 pypdf"""
    abs_file_path = get_abstract_path(file_path) if not os.path.isabs(file_path) else file_path
    
    if password:
        import pypdf
        reader = pypdf.PdfReader(abs_file_path)
        if reader.is_encrypted:
            reader.decrypt(password)
        docs = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            docs.append(Document(page_content=text, metadata={"page": i + 1, "source": abs_file_path}))
        return docs
    
    # 优先尝试 unstructured
    try:
        from unstructured.partition.pdf import partition_pdf
        elements = partition_pdf(filename=abs_file_path, strategy="auto")
        if elements:
            docs = []
            for el in elements:
                page_number = getattr(el.metadata, 'page_number', None) if el.metadata else None
                metadata = {"source": abs_file_path}
                if page_number:
                    metadata["page"] = page_number
                text = str(el) if hasattr(el, '__str__') else getattr(el, 'text', "")
                if text.strip():
                    docs.append(Document(page_content=text, metadata=metadata))
            if docs:
                return docs
    except Exception as e:
        logger.warning(f"【PDF加载】unstructured 失败，尝试 pypdf: {e}")
    
    # 回退到 pypdf
    import pypdf
    reader = pypdf.PdfReader(abs_file_path)
    docs = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        docs.append(Document(page_content=text, metadata={"page": i + 1, "source": abs_file_path}))
    return docs


async def txt_loader(file_path: str) -> List[Document]:
    """TXT 加载器"""
    abs_file_path = get_abstract_path(file_path) if not os.path.isabs(file_path) else file_path
    encodings = ['utf-8', 'gbk']
    for encoding in encodings:
        try:
            async with aiofiles.open(abs_file_path, 'r', encoding=encoding) as f:
                content = await f.read()
            return [Document(page_content=content, metadata={"source": abs_file_path})]
        except Exception as e:
            logger.warning(f"【文本文件加载】使用编码 {encoding} 失败: {e}")
            continue
    return []


async def word_loader(file_path: str) -> List[Document]:
    """DOCX 加载器"""
    abs_file_path = get_abstract_path(file_path) if not os.path.isabs(file_path) else file_path
    try:
        from unstructured.partition.docx import partition_docx
        from app.rag.document_handler.format_preserver import aggregate_by_length
        elements = partition_docx(filename=abs_file_path)
        return aggregate_by_length(elements, abs_file_path)
    except Exception as e:
        logger.error(f"【WORD文件加载】失败: {e}")
        return []


async def markdown_loader(file_path: str) -> List[Document]:
    """Markdown 加载器"""
    abs_file_path = get_abstract_path(file_path) if not os.path.isabs(file_path) else file_path
    try:
        from unstructured.partition.md import partition_md
        elements = partition_md(filename=abs_file_path)
        docs = []
        for el in elements:
            text = str(el) if hasattr(el, '__str__') else getattr(el, 'text', "")
            if text.strip():
                docs.append(Document(page_content=text, metadata={"source": abs_file_path}))
        return docs
    except Exception as e:
        logger.error(f"【Markdown文件加载】失败: {e}")
        return []


async def ppt_loader(file_path: str) -> List[Document]:
    """PPTX 加载器"""
    abs_file_path = get_abstract_path(file_path) if not os.path.isabs(file_path) else file_path
    try:
        from unstructured.partition.pptx import partition_pptx
        elements = partition_pptx(filename=abs_file_path)
        docs = []
        for el in elements:
            text = str(el) if hasattr(el, '__str__') else getattr(el, 'text', "")
            if text.strip():
                docs.append(Document(page_content=text, metadata={"source": abs_file_path}))
        return docs
    except Exception as e:
        logger.error(f"【PPT文件加载】失败: {e}")
        return []


# ── 同步版本（用于多线程场景）──

def pdf_loader_sync(file_path: str, password: str = None) -> List[Document]:
    """同步加载PDF文件内容"""
    abs_file_path = get_abstract_path(file_path) if not os.path.isabs(file_path) else file_path
    
    if password:
        import pypdf
        reader = pypdf.PdfReader(abs_file_path)
        if reader.is_encrypted:
            reader.decrypt(password)
        docs = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            docs.append(Document(page_content=text, metadata={"page": i + 1, "source": abs_file_path}))
        return docs
    
    try:
        from unstructured.partition.pdf import partition_pdf
        elements = partition_pdf(filename=abs_file_path, strategy="auto")
        if elements:
            docs = []
            for el in elements:
                page_number = getattr(el.metadata, 'page_number', None) if el.metadata else None
                metadata = {"source": abs_file_path}
                if page_number:
                    metadata["page"] = page_number
                text = str(el) if hasattr(el, '__str__') else getattr(el, 'text', "")
                if text.strip():
                    docs.append(Document(page_content=text, metadata=metadata))
            if docs:
                return docs
    except Exception as e:
        logger.warning(f"【PDF加载(同步)】unstructured 失败，尝试 pypdf: {e}")
    
    import pypdf
    reader = pypdf.PdfReader(abs_file_path)
    docs = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        docs.append(Document(page_content=text, metadata={"page": i + 1, "source": abs_file_path}))
    return docs


def txt_loader_sync(file_path: str) -> List[Document]:
    """同步加载TXT文件内容"""
    abs_file_path = get_abstract_path(file_path) if not os.path.isabs(file_path) else file_path
    encodings = ['utf-8', 'gbk']
    for encoding in encodings:
        try:
            with open(abs_file_path, 'r', encoding=encoding) as f:
                content = f.read()
            return [Document(page_content=content, metadata={"source": abs_file_path})]
        except Exception:
            continue
    return []


def word_loader_sync(file_path: str) -> List[Document]:
    """同步加载DOCX文件内容"""
    abs_file_path = get_abstract_path(file_path) if not os.path.isabs(file_path) else file_path
    try:
        from unstructured.partition.docx import partition_docx
        from app.rag.document_handler.format_preserver import aggregate_by_length
        elements = partition_docx(filename=abs_file_path)
        return aggregate_by_length(elements, abs_file_path)
    except Exception as e:
        logger.error(f"【WORD文件加载(同步)】失败: {e}")
        return []


def markdown_loader_sync(file_path: str) -> List[Document]:
    """同步加载Markdown文件内容"""
    abs_file_path = get_abstract_path(file_path) if not os.path.isabs(file_path) else file_path
    try:
        from unstructured.partition.md import partition_md
        elements = partition_md(filename=abs_file_path)
        docs = []
        for el in elements:
            text = str(el) if hasattr(el, '__str__') else getattr(el, 'text', "")
            if text.strip():
                docs.append(Document(page_content=text, metadata={"source": abs_file_path}))
        return docs
    except Exception as e:
        logger.error(f"【Markdown文件加载(同步)】失败: {e}")
        return []


def ppt_loader_sync(file_path: str) -> List[Document]:
    """同步加载PPTX文件内容"""
    abs_file_path = get_abstract_path(file_path) if not os.path.isabs(file_path) else file_path
    try:
        from unstructured.partition.pptx import partition_pptx
        elements = partition_pptx(filename=abs_file_path)
        docs = []
        for el in elements:
            text = str(el) if hasattr(el, '__str__') else getattr(el, 'text', "")
            if text.strip():
                docs.append(Document(page_content=text, metadata={"source": abs_file_path}))
        return docs
    except Exception as e:
        logger.error(f"【PPT文件加载(同步)】失败: {e}")
        return []
