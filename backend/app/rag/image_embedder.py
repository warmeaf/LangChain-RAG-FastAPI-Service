"""CLIP 视觉 Embedding 模型，用于图片到图片的相似度检索"""
import asyncio
import os
from typing import List


class CLIPImageEmbedder:
    """CLIP 视觉嵌入模型 (ViT-B/32)"""

    def __init__(self, model_name: str = None):
        self.model_name = model_name or os.getenv("IMAGE_EMBED_MODEL_NAME", "openai/clip-vit-base-patch32")
        self._model = None
        self._processor = None

    def _load_sync(self):
        from transformers import CLIPModel, CLIPProcessor
        self._model = CLIPModel.from_pretrained(self.model_name)
        self._processor = CLIPProcessor.from_pretrained(self.model_name)
        return self._model, self._processor

    async def _ensure_loaded(self):
        if self._model is None:
            await asyncio.to_thread(self._load_sync)

    async def encode_image(self, image) -> List[float]:
        """编码图片为 512 维向量"""
        import torch
        await self._ensure_loaded()
        inputs = self._processor(images=image, return_tensors="pt")
        with torch.no_grad():
            features = self._model.get_image_features(**inputs)
            features = features.pooler_output
            features = features / features.norm(dim=-1, keepdim=True)
        return features.squeeze().tolist()

    def encode_image_sync(self, image) -> List[float]:
        """同步编码图片"""
        import torch
        self._load_sync()
        inputs = self._processor(images=image, return_tensors="pt")
        with torch.no_grad():
            features = self._model.get_image_features(**inputs)
            features = features.pooler_output
            features = features / features.norm(dim=-1, keepdim=True)
        return features.squeeze().tolist()

    async def encode_text(self, text: str) -> List[float]:
        """编码文本为 CLIP 空间向量"""
        import torch
        await self._ensure_loaded()
        inputs = self._processor(text=[text], return_tensors="pt", padding=True)
        with torch.no_grad():
            features = self._model.get_text_features(**inputs)
            features = features.pooler_output
            features = features / features.norm(dim=-1, keepdim=True)
        return features.squeeze().tolist()


# 全局单例
image_embedder = CLIPImageEmbedder()
