import asyncio
import os
import tempfile
from typing import TYPE_CHECKING

from langchain_core.documents import Document

from app.rag.text_spliter import AsyncTextSplitter
from app.utils.config import rag_config
from app.utils.factory import embed_model
from app.utils.file_handler import pdf_loader, txt_loader, listdir_allowed_type, get_file_md5_hex, markdown_loader, \
    ppt_loader, word_loader, pdf_loader_sync, txt_loader_sync, markdown_loader_sync, ppt_loader_sync, word_loader_sync
from app.utils.pdf_multimodal_loader import pdf_multimodal_loader, pdf_multimodal_loader_sync
from app.core.logger_handler import logger


class DocumentProcessor:
    """文档处理器"""

    def __init__(self, vectors_store, md5_store):
        self.vectors_store = vectors_store
        self.md5_store = md5_store
        chunk_cfg = rag_config.get("chunking", {}).get("default", {})
        self.spliter = AsyncTextSplitter(
            chunk_size=chunk_cfg.get('chunk_size', 400),
            chunk_overlap=chunk_cfg.get('chunk_overlap', 40),
            separators=rag_config.get('chunking', {}).get('separators', ["\n\n", "\n", "。", "！", "？", "!", "?", " ", ""]),
            embedding_model=embed_model
        )

    async def get_file_document(self, read_path: str, md5: str = None, user_id: str = None) -> list[Document]:
        """异步加载文件（集成类型路由器）"""
        from .type_router import DocumentTypeRouter

        strategy = DocumentTypeRouter.get_strategy(read_path)

        # Excel 处理
        if strategy == "excel":
            from .excel_processor import ExcelProcessor
            docs = await ExcelProcessor().process(read_path)
            if docs:
                return docs

        # 代码文件处理
        if strategy == "code":
            from .code_processor import CodeProcessor
            docs = await CodeProcessor().process(read_path)
            if docs:
                return docs

        # Markdown 标题层级切分
        if strategy == "markdown":
            from app.rag.text_spliter import HeadingSplitter
            chunk_cfg = rag_config.get("chunking", {}).get("default", {})
            heading_splitter = HeadingSplitter(
                chunk_size=chunk_cfg.get('chunk_size', 400),
                chunk_overlap=chunk_cfg.get('chunk_overlap', 40),
            )
            raw_docs = await markdown_loader(read_path)
            if raw_docs:
                split_docs = heading_splitter.split_documents(raw_docs)
                return split_docs
            return raw_docs

        # 默认文件类型
        if read_path.endswith('.txt'):
            return await txt_loader(read_path)
        elif read_path.endswith('.pdf'):
            # OCR 先行尝试
            from .ocr_processor import OCRProcessor
            ocr_docs = await OCRProcessor().process(read_path)
            if ocr_docs and len(ocr_docs) > 0 and len(ocr_docs[0].page_content) > 50:
                return ocr_docs
            if md5 and user_id:
                return await pdf_multimodal_loader(read_path, md5, user_id)
            return await pdf_loader(read_path)
        elif read_path.endswith('.md'):
            return await markdown_loader(read_path)
        elif read_path.endswith('.pptx'):
            from .format_preserver import aggregate_by_slide
            from unstructured.partition.pptx import partition_pptx
            elements = partition_pptx(filename=read_path)
            return aggregate_by_slide(elements, read_path)
        elif read_path.endswith('.docx'):
            from .format_preserver import aggregate_by_length
            from unstructured.partition.docx import partition_docx
            elements = partition_docx(filename=read_path)
            chunk_cfg = rag_config.get("chunking", {}).get("default", {})
            chunk_size = chunk_cfg.get("chunk_size", 400)
            return aggregate_by_length(elements, read_path, chunk_size)
        else:
            return []

    def get_file_document_sync(self, read_path: str, md5: str = None, user_id: str = None) -> list[Document]:
        """同步加载文件（用于多线程场景）"""
        if read_path.endswith('.txt'):
            return txt_loader_sync(read_path)
        elif read_path.endswith('.pdf'):
            if md5 and user_id:
                return pdf_multimodal_loader_sync(read_path, md5, user_id)
            return pdf_loader_sync(read_path)
        elif read_path.endswith('.md'):
            return markdown_loader_sync(read_path)
        elif read_path.endswith('.pptx'):
            return ppt_loader_sync(read_path)
        elif read_path.endswith('.docx'):
            return word_loader_sync(read_path)
        else:
            return []

    def split_documents_sync(self, documents: list[Document]) -> list[Document]:
        """同步分割文档（用于多线程场景）"""
        return self.spliter.split_documents_sync(documents)

    async def get_document(self, files: list = None, user_id: str = None, progress_callback=None):
        """
        处理文档并将其转为向量存入向量数据库
        :param files: 上传的文件列表，如果为None则从数据文件夹读取
        :param user_id: 用户ID，用于标记文档的所有者
        :param progress_callback: 进度回调函数，用于实时返回处理进度
        """
        file_paths = []
        file_names = {}

        if files:
            for file in files:
                temp_file_path = await asyncio.to_thread(
                    tempfile.NamedTemporaryFile,
                    delete=False,
                    suffix=os.path.splitext(file.filename)[1]
                )
                content = await file.read()
                await asyncio.to_thread(temp_file_path.write, content)
                file_paths.append(temp_file_path.name)
                file_names[temp_file_path.name] = file.filename
        else:
            allowed_file_path: tuple[str] = await listdir_allowed_type(
                rag_config['data_path'],
                tuple(rag_config['allow_file_types'])
            )
            file_paths = list(allowed_file_path)

        for idx, file_path in enumerate(file_paths):
            filename = file_names.get(file_path, os.path.basename(file_path))

            md5_hex = await get_file_md5_hex(file_path)
            if await self.md5_store.check_md5_hex(md5_hex, user_id):
                if progress_callback:
                    await progress_callback({
                        'step': 'skipping',
                        'filename': filename,
                        'message': f'文件 {filename} 已存在，跳过'
                    })
                logger.info(f"【向量数据库】文件 {file_path} 的md5值 {md5_hex} 已存在，跳过")
                if files:
                    try:
                        os.unlink(file_path)
                    except:
                        pass
                continue

            try:
                if progress_callback:
                    await progress_callback({
                        'step': 'loading',
                        'filename': filename,
                        'message': f'正在加载文档 {filename}...'
                    })
                logger.info(f"【向量数据库】开始加载文档: {filename}")

                # 传入 md5_hex 和 user_id 以支持多模态PDF加载（图片提取和存储路径定位）
                document: list[Document] = await self.get_file_document(file_path, md5_hex, user_id)
                if not document:
                    if progress_callback:
                        await progress_callback({
                            'step': 'error',
                            'filename': filename,
                            'message': f'文件 {filename} 加载内容为空，跳过',
                            'error_message': '文件内容为空'
                        })
                    logger.error(f"【向量数据库】文件 {file_path} 加载内容为空，跳过")
                    if files:
                        try:
                            os.unlink(file_path)
                        except Exception as e:
                            pass
                    continue

                if progress_callback:
                    await progress_callback({
                        'step': 'splitting',
                        'filename': filename,
                        'message': f'正在切分文档 {filename}...'
                    })
                logger.info(f"【向量数据库】开始切分文档: {filename}")

                document: list[Document] = await self.spliter.split_documents(document)
                if not document:
                    if progress_callback:
                        await progress_callback({
                            'step': 'error',
                            'filename': filename,
                            'message': f'文件 {filename} 切分内容为空，跳过',
                            'error_message': '文档切分后为空'
                        })
                    logger.error(f"【向量数据库】文件 {file_path} 切分内容为空，跳过")
                    if files:
                        try:
                            os.unlink(file_path)
                        except:
                            pass
                    continue

                if progress_callback:
                    await progress_callback({
                        'step': 'storing',
                        'filename': filename,
                        'message': f'正在存储向量 {filename}...'
                    })
                logger.info(f"【向量数据库】开始存储向量: {filename}，文档数量: {len(document)}")

                if user_id:
                    for doc in document:
                        doc.metadata['user_id'] = user_id

                for doc in document:
                    doc.metadata['original_filename'] = filename
                    doc.metadata['md5'] = md5_hex
                    # 语言检测：用于后续 Embedding 模型自动选择
                    from app.utils.language_detector import detect_language
                    doc.metadata['language'] = detect_language(doc.page_content)

                await asyncio.to_thread(self.vectors_store.add_documents, document)

                # 类别识别与初始权重写入
                if user_id:
                    category = self._detect_category(file_path, filename)
                    quality_score = self._calc_quality_score(document)
                    await self._init_doc_weights(
                        md5_hex, user_id, filename, category, quality_score
                    )
                    # 存储图片视觉向量 (CLIP)
                    await self._store_image_vectors(md5_hex, file_path, user_id)

                original_filename = file_names.get(file_path, filename) if files else filename
                await self.md5_store.save_md5_hex(md5_hex, filename, original_filename, user_id)

                if progress_callback:
                    await progress_callback({
                        'step': 'completed',
                        'filename': filename,
                        'message': f'文件 {filename} 处理完成'
                    })
                logger.info(f"【向量数据库】文件 {file_path} 的md5值 {md5_hex} 已保存")

                if files:
                    try:
                        os.unlink(file_path)
                    except:
                        pass

            except Exception as e:
                if progress_callback:
                    await progress_callback({
                        'step': 'error',
                        'filename': filename,
                        'message': f'文件 {filename} 处理失败',
                        'error_message': str(e)
                    })
                logger.error(f"【向量数据库】文件 {file_path} 处理时出错: {e}")
                if files:
                    try:
                        os.unlink(file_path)
                    except:
                        pass
                continue

    def _detect_category(self, file_path: str, filename: str) -> str:
        """基于文件名和路径检测文档类别"""
        name_lower = (filename + file_path).lower()
        category_keywords = {
            "政策制度": ["政策", "制度", "规定", "办法", "条例", "章程"],
            "技术文档": ["技术", "架构", "api", "接口", "代码", "开发", "部署", "运维"],
            "产品手册": ["产品", "手册", "指南", "用户", "帮助", "使用说明"],
            "周报日报": ["周报", "日报", "月报", "季度", "年终总结"],
            "会议纪要": ["会议", "纪要", "记录", "讨论"],
        }
        for cat, keywords in category_keywords.items():
            for kw in keywords:
                if kw in name_lower:
                    return cat
        return "default"

    def _calc_quality_score(self, documents: list) -> float:
        """基于 chunk 数和平均长度评估文档完整度"""
        if not documents:
            return 0.5
        total_length = sum(len(doc.page_content) for doc in documents)
        avg_length = total_length / len(documents)
        chunk_bonus = min(1.0, len(documents) / 20)
        length_bonus = min(1.0, avg_length / 300)
        return round(0.4 * chunk_bonus + 0.6 * length_bonus, 2)

    async def _init_doc_weights(
        self, md5_hex: str, user_id: str, filename: str,
        category: str, quality_score: float
    ):
        """初始化文档权重记录"""
        from app.models.feedback import DocWeight
        from app.db.db_config import AsyncSessionLocal
        from sqlalchemy import select

        category_weights = rag_config.get("doc_category_weights", {})
        category_weight = category_weights.get(category, category_weights.get("default", 0.7))

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(DocWeight).where(
                    DocWeight.user_id == user_id,
                    DocWeight.doc_md5 == md5_hex,
                )
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                dw = DocWeight(
                    user_id=user_id,
                    doc_md5=md5_hex,
                    doc_filename=filename,
                    category=category,
                    weight=category_weight,
                    quality_score=quality_score,
                )
                session.add(dw)
                await session.commit()

    async def _store_image_vectors(self, md5_hex: str, file_path: str, user_id: str):
        """提取并存储 PDF 中的图片视觉向量 (CLIP)"""
        if not file_path.lower().endswith('.pdf'):
            return

        try:
            from app.rag.image_embedder import image_embedder
            from app.utils.path_tool import get_data_path
            from PIL import Image

            image_dir = os.path.join(get_data_path(), 'extracted_images', user_id, md5_hex)
            if not os.path.isdir(image_dir):
                return

            image_data = []
            for img_file in sorted(os.listdir(image_dir)):
                img_path = os.path.join(image_dir, img_file)
                if not os.path.isfile(img_path):
                    continue
                try:
                    pil_image = Image.open(img_path).convert("RGB")
                    visual_emb = await image_embedder.encode_image(pil_image)

                    image_data.append({
                        "image_md5": img_file,
                        "visual_embedding": visual_emb,
                        "user_id": user_id,
                        "parent_doc_md5": md5_hex,
                        "ocr_text": "",
                        "description": "",
                        "metadata": {"source": file_path},
                    })
                except Exception as e:
                    logger.warning(f"CLIP encoding failed for {img_file}: {e}")

            if image_data:
                await asyncio.to_thread(self.vectors_store.add_image_vectors, image_data)
                logger.info(f"Stored {len(image_data)} image vectors for doc {md5_hex}")
        except Exception as e:
            logger.warning(f"Image vector storage failed: {e}")