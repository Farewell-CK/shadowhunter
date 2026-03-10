"""
智谱 AI 客户端封装
支持 glm-4 (文本)、glm-4.6v (视频/图像)、embedding-3 (向量)
"""

import asyncio
import base64
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Union
from dataclasses import dataclass

import httpx
from openai import AsyncOpenAI

from config import (
    ZHIPU_API_KEY,
    ZHIPU_BASE_URL,
    MODEL_CHAT,
    MODEL_VISION,
    MODEL_EMBEDDING,
    MAX_CONCURRENT_REQUESTS,
)


@dataclass
class VideoAnalysisResult:
    """视频分析结果"""
    description: str  # 语义描述
    actions: list[str]  # 动作列表
    objects: list[str]  # 检测到的对象
    confidence: float  # 置信度


@dataclass
class EmbeddingResult:
    """向量生成结果"""
    vector: list[float]
    dimension: int


class ZhipuManager:
    """
    智谱 AI 客户端管理器
    封装文本对话、视频理解、向量生成接口
    严格遵守并发限制 (QPS=3)
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or ZHIPU_API_KEY
        if not self.api_key:
            raise ValueError("需要提供智谱 API Key")

        # 初始化 OpenAI 兼容客户端
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=ZHIPU_BASE_URL,
        )

        # 并发控制信号量
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        # 请求时间记录 (用于滑动窗口限速)
        self._request_times: list[float] = []
        self._lock = asyncio.Lock()  # 保护 _request_times 的并发访问

    @asynccontextmanager
    async def _rate_limit(self):
        """
        限速控制 - 使用滑动窗口算法

        确保在任意 1 秒内不超过 MAX_CONCURRENT_REQUESTS 个请求
        """
        async with self._semaphore:
            async with self._lock:
                now = time.time()
                # 清理 1 秒前的请求记录
                self._request_times = [t for t in self._request_times if now - t < 1.0]

                # 如果 1 秒内请求数已达上限，等待
                if len(self._request_times) >= MAX_CONCURRENT_REQUESTS:
                    wait_time = 1.0 - (now - self._request_times[0])
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)
                    # 清理过期的记录
                    self._request_times = [t for t in self._request_times if time.time() - t < 1.0]

                self._request_times.append(time.time())

            yield

    async def chat(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """
        文本对话接口 (glm-4)
        用于查询解析、特征提取
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})

        async with self._rate_limit():
            response = await self.client.chat.completions.create(
                model=MODEL_CHAT,
                messages=messages,
                temperature=temperature,
            )
            return response.choices[0].message.content

    async def analyze_video(
        self,
        video_source: Union[str, Path, bytes],
        prompt: str = "请详细描述这个视频片段中发生的事情，包括人物动作、穿着、携带物品等。",
        video_type: str = "mp4",
    ) -> VideoAnalysisResult:
        """
        视频分析接口 (glm-4.6v)

        Args:
            video_source: 视频文件路径、URL 或二进制数据
            prompt: 分析提示词
            video_type: 视频格式 (mp4, webm 等)

        Returns:
            VideoAnalysisResult: 包含描述、动作、对象、置信度
        """
        # 准备视频内容
        video_content = await self._prepare_video_content(video_source, video_type)

        # 使用 OpenAI 兼容格式
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "video_url",
                        "video_url": video_content
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]

        async with self._rate_limit():
            response = await self.client.chat.completions.create(
                model=MODEL_VISION,
                messages=messages,
            )
            result_text = response.choices[0].message.content

        # 解析结果
        return self._parse_video_analysis(result_text)

    async def analyze_image(
        self,
        image_source: Union[str, Path, bytes],
        prompt: str = "请描述这张图片的内容。",
        image_type: str = "jpeg",
    ) -> str:
        """
        图像分析接口 (glm-4.6v)
        """
        image_content = await self._prepare_image_content(image_source, image_type)

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_content}},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        async with self._rate_limit():
            response = await self.client.chat.completions.create(
                model=MODEL_VISION,
                messages=messages,
            )
            return response.choices[0].message.content

    async def get_embedding(self, text: str) -> EmbeddingResult:
        """
        向量生成接口 (embedding-3)
        """
        async with self._rate_limit():
            response = await self.client.embeddings.create(
                model=MODEL_EMBEDDING,
                input=text,
            )
            vector = response.data[0].embedding
            return EmbeddingResult(
                vector=vector,
                dimension=len(vector),
            )

    async def _prepare_video_content(
        self,
        source: Union[str, Path, bytes],
        video_type: str = "mp4",
    ) -> dict:
        """
        准备视频内容 (非阻塞版本)
        使用线程池处理磁盘 IO 和 Base64 编码，防止阻塞事件循环
        """
        # URL 直接返回
        if isinstance(source, str) and source.startswith(("http://", "https://")):
            return {"url": source}

        def _read_and_encode():
            if isinstance(source, (str, Path)):
                path = Path(source)
                if not path.exists():
                    raise FileNotFoundError(f"视频文件不存在: {path}")
                video_bytes = path.read_bytes()
            else:
                video_bytes = source
            
            return base64.b64encode(video_bytes).decode("utf-8")

        # 将 CPU/IO 密集型操作移至线程池
        base64_video = await asyncio.to_thread(_read_and_encode)
        return {"url": f"data:video/{video_type};base64,{base64_video}"}

    async def _prepare_image_content(
        self,
        source: Union[str, Path, bytes],
        image_type: str = "jpeg",
    ) -> str:
        """
        准备图像内容供 API 调用
        """
        if isinstance(source, str) and source.startswith(("http://", "https://")):
            return source

        if isinstance(source, (str, Path)):
            path = Path(source)
            if not path.exists():
                raise FileNotFoundError(f"图像文件不存在: {path}")
            image_bytes = path.read_bytes()
        else:
            image_bytes = source

        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:image/{image_type};base64,{base64_image}"

    def _parse_video_analysis(self, result_text: str) -> VideoAnalysisResult:
        """
        解析视频分析结果
        提取描述、动作、对象等信息
        """
        # 基础解析 (可根据实际返回格式优化)
        description = result_text.strip()

        # 提取动作关键词
        action_keywords = ["走", "跑", "骑", "开", "停", "拿", "放", "看", "说", "坐", "站"]
        actions = [kw for kw in action_keywords if kw in description]

        # 提取对象关键词
        object_keywords = ["人", "车", "头盔", "包", "手机", "衣服", "帽子", "眼镜"]
        objects = [kw for kw in object_keywords if kw in description]

        return VideoAnalysisResult(
            description=description,
            actions=actions,
            objects=objects,
            confidence=0.85,  # 基础置信度
        )


# 便捷函数
async def create_client(api_key: Optional[str] = None) -> ZhipuManager:
    """创建智谱 AI 客户端"""
    return ZhipuManager(api_key)