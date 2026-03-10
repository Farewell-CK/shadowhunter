"""
搜索引擎服务
实现语义检索与视觉核实流程
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional
import json

from ai_client import ZhipuManager


@dataclass
class SearchQuery:
    """搜索查询"""
    text: str  # 原始查询文本
    features: list[str] = field(default_factory=list)  # 提取的特征词
    filters: dict = field(default_factory=dict)  # 过滤条件


@dataclass
class SearchResult:
    """搜索结果"""
    slice_id: str
    video_id: str
    start_time: float
    end_time: float
    description: str
    similarity: float
    visual_verification: Optional[str] = None  # 视觉核实报告
    matched_features: list[str] = field(default_factory=list)  # 匹配的特征


class SearchEngine:
    """
    视频语义搜索引擎

    搜索流程:
    1. glm-4 解析用户查询，提取视觉特征
    2. embedding-3 生成查询向量
    3. 向量库检索相似片段
    4. glm-4.6v 对 Top-N 结果进行视觉核实 (并行处理)
    """

    FEATURE_EXTRACTION_PROMPT = """你是一个专业的公安图侦查询解析助手。
从用户的查询中提取用于刑侦检索的核心视觉特征，以便与数据库中的特征向量进行比对。

用户查询: {query}

请按以下格式输出提取的特征（JSON 数组格式）:
{{
    "features": ["特征1", "特征2", ...],
    "filters": {{
        "gender": "男/女/未知",
        "vehicle": "两轮电动车/汽车/摩托车/步行/未知",
        "action": "正常行走/奔跑/徘徊/左顾右盼/其他"
    }}
}}

注意：
1. features 数组中的特征必须极其精简，如 "男性", "黑上衣", "白色头盔", "红色电动车"。
2. 丢弃所有非视觉描述（如时间、地点、"帮我找一下"等口语）。
3. 只输出 JSON，不要有任何额外解释文字。"""

    def __init__(self, ai_client: ZhipuManager, vector_store):
        self.ai_client = ai_client
        self.vector_store = vector_store

    async def search(
        self,
        query_text: str,
        top_k: int = 10,
        verify_top_n: int = 3,
        video_id: Optional[str] = None,
    ) -> list[SearchResult]:
        """
        执行语义搜索 (并行核实版本)
        """
        # 1. 解析查询，提取特征
        query = await self._parse_query(query_text)

        # 2. 生成查询向量
        query_text_for_embedding = ", ".join(query.features)
        
        # 兜底：如果没提取出特征，使用原始查询
        if not query_text_for_embedding.strip():
            query_text_for_embedding = query_text

        embedding_result = await self.ai_client.get_embedding(query_text_for_embedding)

        # 3. 向量检索
        matches = await self.vector_store.search(
            query_embedding=embedding_result.vector,
            n_results=top_k,
            video_id=video_id,
        )

        if not matches:
            return []

        # 4. 转换为 SearchResult 对象
        results = [
            SearchResult(
                slice_id=m["slice_id"],
                video_id=m["video_id"],
                start_time=m["start_time"],
                end_time=m["end_time"],
                description=m["description"],
                similarity=m["similarity"],
            )
            for m in matches
        ]

        # 5. 并行化视觉核实
        if verify_top_n > 0:
            results_to_verify = results[:verify_top_n]
            
            # 创建并发任务
            async def _verify_task(res):
                res.visual_verification = await self._visual_verify(res, query.features)

            verify_tasks = [_verify_task(r) for r in results_to_verify]
            await asyncio.gather(*verify_tasks)

        return results

    async def _parse_query(self, query_text: str) -> SearchQuery:
        """
        使用 glm-4 解析查询，提取视觉特征
        """
        try:
            response = await self.ai_client.chat(
                message=self.FEATURE_EXTRACTION_PROMPT.format(query=query_text),
                temperature=0.3,
            )

            # 解析 JSON 响应
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]

            data = json.loads(json_str.strip())

            return SearchQuery(
                text=query_text,
                features=data.get("features", []),
                filters=data.get("filters", {}),
            )

        except Exception as e:
            return SearchQuery(text=query_text, features=[query_text])

    async def _visual_verify(
        self,
        result: SearchResult,
        features: list[str],
    ) -> str:
        """
        视觉核实逻辑
        """
        prompt = f"""基于以下视频片段描述，判断是否包含目标特征。

视频描述:
{result.description}

目标特征:
{', '.join(features)}

请简要分析匹配程度，指出哪些特征匹配、哪些不匹配。"""

        try:
            verification = await self.ai_client.chat(
                message=prompt,
                temperature=0.3,
            )
            return verification
        except Exception as e:
            return f"视觉核实中途出错: {e}"

    async def search_by_features(
        self,
        features: list[str],
        top_k: int = 10,
        video_id: Optional[str] = None,
    ) -> list[SearchResult]:
        """
        直接使用特征列表搜索
        """
        query_text = ", ".join(features)
        embedding_result = await self.ai_client.get_embedding(query_text)

        matches = await self.vector_store.search(
            query_embedding=embedding_result.vector,
            n_results=top_k,
            video_id=video_id,
        )

        return [
            SearchResult(
                slice_id=m["slice_id"],
                video_id=m["video_id"],
                start_time=m["start_time"],
                end_time=m["end_time"],
                description=m["description"],
                similarity=m["similarity"],
            )
            for m in matches
        ]

    async def analyze_suspect(
        self,
        slice_id: str,
        focus_features: list[str],
    ) -> dict:
        """
        深度嫌疑分析
        """
        slice_info = await self.vector_store.get_slice(slice_id)
        if not slice_info:
            return {"error": "切片不存在"}

        prompt = f"""分析视频片段嫌疑特征。

视频描述:
{slice_info['description']}

重点分析特征:
{', '.join(focus_features)}

请输出匹配分析、行为意图推测、可疑度评估及建议。"""

        analysis = await self.ai_client.chat(message=prompt, temperature=0.5)

        return {
            "slice_id": slice_id,
            "video_id": slice_info["metadata"].get("video_id", ""),
            "start_time": slice_info["metadata"].get("start_time", 0),
            "end_time": slice_info["metadata"].get("end_time", 0),
            "analysis": analysis,
            "focus_features": focus_features,
        }