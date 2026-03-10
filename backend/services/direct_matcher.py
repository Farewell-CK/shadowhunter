"""
直接视频匹配服务
将视频切片 + query 一起发给大模型判断，实现精确匹配
适用于公安场景的精确查找需求
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from services.video_worker import VideoSlicer, VideoSlice
from services.vector_store import VectorStore
from ai_client import ZhipuManager

logger = logging.getLogger("shadowhunter.direct_match")


@dataclass
class MatchResult:
    """匹配结果"""
    slice_id: str
    video_id: str
    start_time: float
    end_time: float
    is_matched: bool  # 是否匹配
    confidence: float  # 置信度 0-100
    reason: str  # 匹配理由
    description: str  # 视频内容摘要
    file_path: Optional[Path] = None  # 切片文件路径
    embedding: Optional[list[float]] = None  # 向量


class DirectMatcher:
    """
    直接视频匹配器

    核心流程:
    1. 视频分片 (复用 VideoSlicer)
    2. 每个切片 + query 发给 GLM-4.6V 判断
    3. 大模型返回结构化匹配结果
    4. 匹配结果存入向量库
    5. 返回 Top-K 结果
    """

    MATCH_PROMPT = """你是一名专业的视频侦查分析师，正在协助公安侦查工作。

请分析这段视频片段，判断是否包含以下目标：

**目标描述**: {query}

请严格按照以下 JSON 格式输出分析结果：
{{
    "is_matched": true或false,
    "confidence": 0-100的数字,
    "reason": "匹配或不匹配的理由，具体说明视频中看到了什么",
    "description": "视频内容的客观描述，包括人物、车辆、动作、场景等"
}}

分析要点：
1. 仔细观察视频中的人物特征（衣着、体态、携带物品）
2. 注意车辆类型、颜色、牌照等特征
3. 关注人物动作和行为
4. 只有确实看到符合目标描述的内容时才判断为匹配
5. 如果不确定，置信度应该较低"""

    def __init__(
        self,
        ai_client: ZhipuManager,
        vector_store: VectorStore,
        slicer: Optional[VideoSlicer] = None,
    ):
        self.ai_client = ai_client
        self.vector_store = vector_store
        self.slicer = slicer or VideoSlicer()

    async def match_videos(
        self,
        video_paths: list[str],
        query: str,
        top_k: int = 10,
        store_results: bool = True,
        progress_callback=None,
    ) -> list[MatchResult]:
        """
        直接匹配多个视频

        Args:
            video_paths: 视频文件路径列表
            query: 查询描述
            top_k: 返回结果数量
            store_results: 是否存储到向量库
            progress_callback: 进度回调函数 (current, total, message)

        Returns:
            匹配结果列表（按置信度排序）
        """
        all_results = []
        total_videos = len(video_paths)

        for video_idx, video_path in enumerate(video_paths):
            path = Path(video_path)
            if not path.exists():
                logger.warning(f"视频文件不存在: {video_path}")
                continue

            if progress_callback:
                progress_callback(
                    video_idx, total_videos,
                    f"正在处理: {path.name}"
                )

            # 处理单个视频
            results = await self._match_single_video(
                video_path=path,
                query=query,
                store_results=store_results,
                progress_callback=progress_callback,
            )
            all_results.extend(results)

        # 按置信度排序，返回 Top-K
        all_results.sort(key=lambda x: x.confidence, reverse=True)
        return all_results[:top_k]

    async def _match_single_video(
        self,
        video_path: Path,
        query: str,
        store_results: bool = True,
        progress_callback=None,
    ) -> list[MatchResult]:
        """
        匹配单个视频的所有切片
        """
        # 生成视频 ID
        video_id = self.slicer._generate_video_id(video_path)

        # 获取视频信息
        try:
            video_info = self.slicer.get_video_info(video_path)
            total_slices = len(self.slicer.calculate_slices(video_info.duration))
            logger.info(f"视频 {video_path.name}: 时长 {video_info.duration:.1f}s, 预计 {total_slices} 个切片")
        except Exception as e:
            logger.error(f"获取视频信息失败: {e}")
            return []

        results = []
        processed_count = 0

        async def process_slice(slice_obj: VideoSlice) -> Optional[MatchResult]:
            nonlocal processed_count

            try:
                # 调用大模型判断匹配 (ai_client 内部已有并发控制)
                match_result = await self._match_slice(slice_obj, query)

                if match_result and match_result.is_matched:
                    results.append(match_result)

                    # 存储到向量库
                    if store_results and match_result.embedding:
                        slice_obj.description = match_result.description
                        slice_obj.embedding = match_result.embedding
                        slice_obj.metadata["match_confidence"] = match_result.confidence
                        slice_obj.metadata["match_reason"] = match_result.reason
                        slice_obj.metadata["query"] = query
                        await self.vector_store.add_slice(slice_obj)

                # 清理临时文件
                self.slicer.cleanup_slice(slice_obj)

            except Exception as e:
                logger.error(f"切片处理失败 {slice_obj.slice_id}: {e}")
            finally:
                processed_count += 1
                if progress_callback:
                    progress_callback(
                        processed_count, total_slices,
                        f"已分析 {processed_count}/{total_slices} 个片段"
                    )

        # 流水线处理：边切片边匹配
        tasks = []
        async for slice_obj in self.slicer.slice_video_async(video_path, video_id):
            task = asyncio.create_task(process_slice(slice_obj))
            tasks.append(task)

        # 等待所有任务完成
        if tasks:
            await asyncio.gather(*tasks)

        logger.info(f"视频 {video_path.name} 处理完成，匹配 {len(results)} 个片段")
        return results

    async def _match_slice(
        self,
        slice_obj: VideoSlice,
        query: str,
    ) -> Optional[MatchResult]:
        """
        对单个切片进行匹配判断
        """
        try:
            # 验证切片文件有效性
            if not slice_obj.file_path or not slice_obj.file_path.exists():
                logger.warning(f"切片文件不存在: {slice_obj.slice_id}")
                return None

            file_size = slice_obj.file_path.stat().st_size
            if file_size < 1000:  # 小于 1KB 认为是无效文件
                logger.warning(f"切片文件过小，可能损坏: {slice_obj.slice_id} ({file_size} bytes)")
                return None

            # 调用大模型
            prompt = self.MATCH_PROMPT.format(query=query)
            analysis = await self.ai_client.analyze_video(
                video_source=slice_obj.file_path,
                prompt=prompt,
            )

            # 解析结果
            result = self._parse_match_result(analysis.description, slice_obj)

            # 如果匹配，生成向量
            if result and result.is_matched and result.description:
                embedding_result = await self.ai_client.get_embedding(result.description)
                result.embedding = embedding_result.vector

            return result

        except Exception as e:
            logger.error(f"切片匹配失败 {slice_obj.slice_id}: {e}")
            return None

    def _parse_match_result(
        self,
        response_text: str,
        slice_obj: VideoSlice,
    ) -> Optional[MatchResult]:
        """
        解析大模型返回的匹配结果
        """
        try:
            # 尝试提取 JSON
            json_str = response_text.strip()

            # 处理 markdown 代码块
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            # 解析 JSON
            data = json.loads(json_str.strip())

            return MatchResult(
                slice_id=slice_obj.slice_id,
                video_id=slice_obj.video_id,
                start_time=slice_obj.start_time,
                end_time=slice_obj.end_time,
                is_matched=bool(data.get("is_matched", False)),
                confidence=float(data.get("confidence", 0)),
                reason=str(data.get("reason", "")),
                description=str(data.get("description", "")),
                file_path=slice_obj.file_path,
            )

        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败: {e}, 原始响应: {response_text[:200]}")
            # 尝试简单判断
            is_matched = "是" in response_text or "匹配" in response_text or "符合" in response_text
            return MatchResult(
                slice_id=slice_obj.slice_id,
                video_id=slice_obj.video_id,
                start_time=slice_obj.start_time,
                end_time=slice_obj.end_time,
                is_matched=is_matched,
                confidence=50.0 if is_matched else 0.0,
                reason="无法解析结构化结果",
                description=response_text[:500],
                file_path=slice_obj.file_path,
            )
        except Exception as e:
            logger.error(f"解析匹配结果失败: {e}")
            return None