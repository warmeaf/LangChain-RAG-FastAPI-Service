import asyncio
from typing import List, Dict, Any
import torch
import os
from dotenv import load_dotenv
from sentence_transformers import CrossEncoder
from modelscope import snapshot_download
from tqdm import tqdm
from app.core.logger_handler import logger

# 加载环境变量
load_dotenv()


def find_model_path(base_path: str) -> str:
    if os.path.exists(os.path.join(base_path, 'config.json')):
        return base_path

    for root, dirs, files in os.walk(base_path):
        if 'config.json' in files:
            return root

    logger.info(f"✅ 模型路径：{base_path}")
    logger.info(f"✅ 模型路径：{root}")
    return base_path


def check_and_download_reranker_model() -> None:
    """检查并重排序模型，在FastAPI启动时执行"""
    LOCAL_MODEL_PATH = os.getenv("RERANKER_MODEL_PATH", r"D:\Hugging_Face\models\Qwen3-Reranker-0.6B")
    MODELSCOPE_MODEL_NAME = "Qwen/Qwen3-Reranker-0.6B"

    try:
        if os.path.exists(LOCAL_MODEL_PATH) and os.path.isdir(LOCAL_MODEL_PATH) and os.path.exists(os.path.join(LOCAL_MODEL_PATH, "config.json")):
            logger.info(f"✅ 检测到本地重排序模型：{LOCAL_MODEL_PATH}")
        else:
            logger.warning(f"⚠️  本地模型未找到：{LOCAL_MODEL_PATH}")
            logger.info(f"🔄 开始从魔搭社区下载模型：{MODELSCOPE_MODEL_NAME}")

            os.makedirs(LOCAL_MODEL_PATH, exist_ok=True)

            with tqdm(total=100, desc='下载模型', leave=True, bar_format='{l_bar}{bar}| {n_fmt}%') as pbar:
                pbar.update(10)
                snapshot_download(
                    model_id=MODELSCOPE_MODEL_NAME,
                    cache_dir=LOCAL_MODEL_PATH,
                    revision='master'
                )
                pbar.update(90)

            logger.info(f"✅ 模型下载完成，保存路径：{LOCAL_MODEL_PATH}")

    except Exception as e:
        logger.error(f"❌ 模型检查失败: {str(e)}")
        raise RuntimeError(f"重排序模型检查失败: {str(e)}")


class ReorderService:
    """文档重排序服务"""

    def __init__(self):
        self.LOCAL_MODEL_PATH = os.getenv("RERANKER_MODEL_PATH", r"D:\Hugging_Face\models\Qwen3-Reranker-0.6B")
        self.MODELSCOPE_MODEL_NAME = "Qwen/Qwen3-Reranker-0.6B"
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = None

    def _load_model_sync(self, model_path: str):
        """在独立线程中加载 CrossEncoder，避免阻塞事件循环"""
        model = CrossEncoder(
            model_path,
            max_length=512,
            device=self.device,
            local_files_only=True
        )
        model.eval()
        return model

    def _predict_sync(self, model, pairs):
        """在独立线程中执行 predict，避免阻塞事件循环"""
        with torch.no_grad():
            return model.predict(pairs, batch_size=1)

    async def _get_model(self):
        if self._model is None:
            actual_model_path = find_model_path(self.LOCAL_MODEL_PATH)
            logger.info(f"✅ 加载重排序模型：{actual_model_path}")
            self._model = await asyncio.to_thread(self._load_model_sync, actual_model_path)
            logger.info(f"✅ 模型加载成功，使用设备：{self.device}")
        return self._model

    @property
    async def model(self):
        return await self._get_model()

    async def reorder_documents(self, query: str, documents: List[str], thinking_callback=None) -> Dict[str, Any]:
        try:
            if not documents:
                return {
                    "success": True,
                    "documents": [],
                    "error": ""
                }

            if thinking_callback:
                await thinking_callback({
                    "type": "thinking",
                    "stage": "reorder",
                    "content": f"正在计算 {len(documents)} 个文档的相关性分数..."
                })

            pairs = [(query, doc) for doc in documents]

            model = await self.model
            scores = await asyncio.to_thread(self._predict_sync, model, pairs)

            scored_documents = []
            for doc, score in zip(documents, scores):
                scored_documents.append({
                    "document": doc,
                    "similarity": float(score)
                })
                logger.info(f"【重排序服务】文档相似度分数: {score:.4f}")

            if thinking_callback:
                score_details = []
                for i, (doc, score) in enumerate(zip(documents, scores), 1):
                    score_details.append({
                        "index": i,
                        "score": round(float(score), 4),
                        "preview": doc[:100] + "..." if len(doc) > 100 else doc
                    })
                await thinking_callback({
                    "type": "thinking",
                    "stage": "reorder",
                    "content": f"已计算完成 {len(documents)} 个文档的相关性分数，按分数降序排序",
                    "details": {
                        "scores": score_details
                    }
                })

            sorted_docs = sorted(scored_documents, key=lambda x: x["similarity"], reverse=True)
            logger.info(f"【重排序服务】文档重排序成功，返回 {len(sorted_docs)} 个文档")

            return {
                "success": True,
                "documents": sorted_docs,
                "error": ""
            }
        except Exception as e:
            error_msg = str(e)
            logger.error(f"【重排序服务】重排序失败: {error_msg}")
            return {
                "success": False,
                "documents": [],
                "error": error_msg
            }

    @staticmethod
    async def format_reorder_result(sorted_docs: List[Dict]) -> str:
        """
        格式化重排序结果
        :param sorted_docs: 重排序后的文档列表
        :return: 格式化后的字符串
        """
        formatted_result = "重排序后的文档列表：\n"
        for i, doc in enumerate(sorted_docs, 1):
            formatted_result += f"{i}. 相似度: {doc.get('similarity', 0):.4f}\n"
            formatted_result += f"   内容: {doc.get('document', '')}\n\n"
        return formatted_result


# 全局重排序服务实例
reorder_service = ReorderService()