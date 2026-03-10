"""
向量存储服务
使用 ChromaDB 存储视频片段的语义向量
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
import json

from config import VECTOR_DB_PATH, EMBEDDING_DIMENSION


@dataclass
class SliceRecord:
    """切片记录"""
    slice_id: str
    video_id: str
    start_time: float
    end_time: float
    description: str
    embedding: list[float]
    metadata: dict = field(default_factory=dict)

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    def to_dict(self) -> dict:
        return {
            "slice_id": self.slice_id,
            "video_id": self.video_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "description": self.description,
            "metadata": self.metadata,
        }


class VectorStore:
    """
    向量存储管理器
    基于 ChromaDB 实现向量检索
    """

    def __init__(self, db_path: Optional[str] = None, collection_name: str = "video_slices"):
        self.db_path = Path(db_path or VECTOR_DB_PATH)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self._client = None
        self._collection = None

    def _get_client(self):
        """懒加载 ChromaDB 客户端"""
        if self._client is None:
            import chromadb
            self._client = chromadb.PersistentClient(path=str(self.db_path))
        return self._client

    def _get_collection(self):
        """获取或创建集合"""
        if self._collection is None:
            client = self._get_client()
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},  # 使用余弦距离
            )
        return self._collection

    async def add_slice(self, slice_obj) -> str:
        """
        添加视频切片到向量库

        Args:
            slice_obj: VideoSlice 对象

        Returns:
            切片 ID
        """
        collection = self._get_collection()
        
        # 确保所有的 metadata 值都是基本类型 (ChromaDB 限制)
        safe_metadata = {}
        for k, v in slice_obj.metadata.items():
            if isinstance(v, (str, int, float, bool)):
                safe_metadata[k] = v
            else:
                safe_metadata[k] = json.dumps(v, ensure_ascii=False)

        # 准备元数据
        metadata = {
            "video_id": slice_obj.video_id,
            "start_time": slice_obj.start_time,
            "end_time": slice_obj.end_time,
            "duration": slice_obj.duration,
            "created_at": datetime.now().isoformat(),
            **safe_metadata,
        }

        # 添加到集合
        collection.add(
            ids=[slice_obj.slice_id],
            embeddings=[slice_obj.embedding],
            documents=[slice_obj.description],
            metadatas=[metadata],
        )

        return slice_obj.slice_id

    async def add_slices_batch(self, slice_objs: list) -> list[str]:
        """
        批量添加视频切片到向量库（性能优化）

        相比逐个添加，批量添加可以：
        1. 减少数据库连接开销
        2. 批量写入索引，效率更高
        3. 减少事务次数

        Args:
            slice_objs: VideoSlice 对象列表

        Returns:
            成功添加的切片 ID 列表
        """
        if not slice_objs:
            return []

        collection = self._get_collection()

        # 批量准备数据
        ids = []
        embeddings = []
        documents = []
        metadatas = []

        for slice_obj in slice_objs:
            if not slice_obj.embedding or not slice_obj.description:
                continue

            metadata = {
                "video_id": slice_obj.video_id,
                "start_time": slice_obj.start_time,
                "end_time": slice_obj.end_time,
                "duration": slice_obj.duration,
                "created_at": datetime.now().isoformat(),
                **{k: str(v) for k, v in slice_obj.metadata.items()},
            }

            ids.append(slice_obj.slice_id)
            embeddings.append(slice_obj.embedding)
            documents.append(slice_obj.description)
            metadatas.append(metadata)

        if not ids:
            return []

        # 批量添加到集合
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

        return ids

    async def search(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        video_id: Optional[str] = None,
        min_similarity: float = 0.0,
    ) -> list[dict]:
        """
        向量相似度搜索

        Args:
            query_embedding: 查询向量
            n_results: 返回结果数量
            video_id: 限定视频 ID (可选)
            min_similarity: 最小相似度阈值

        Returns:
            匹配结果列表
        """
        collection = self._get_collection()

        # 构建过滤条件
        where_filter = None
        if video_id:
            where_filter = {"video_id": video_id}

        # 执行搜索
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        # 格式化结果
        matches = []
        if results["ids"] and results["ids"][0]:
            for i, slice_id in enumerate(results["ids"][0]):
                # ChromaDB 返回的是距离，转换为相似度
                distance = results["distances"][0][i]
                similarity = 1 - distance  # 余弦距离转相似度

                if similarity < min_similarity:
                    continue

                matches.append({
                    "slice_id": slice_id,
                    "description": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "similarity": similarity,
                    "start_time": results["metadatas"][0][i].get("start_time", 0),
                    "end_time": results["metadatas"][0][i].get("end_time", 0),
                    "video_id": results["metadatas"][0][i].get("video_id", ""),
                })

        return matches

    async def delete_slice(self, slice_id: str):
        """删除切片"""
        collection = self._get_collection()
        collection.delete(ids=[slice_id])

    async def delete_video(self, video_id: str):
        """删除视频的所有切片"""
        collection = self._get_collection()
        collection.delete(where={"video_id": video_id})

    async def get_slice(self, slice_id: str) -> Optional[dict]:
        """获取单个切片"""
        collection = self._get_collection()
        results = collection.get(
            ids=[slice_id],
            include=["documents", "metadatas", "embeddings"],
        )

        if not results["ids"]:
            return None

        # 安全获取 embedding
        embeddings_data = results.get("embeddings")
        embedding = embeddings_data[0] if embeddings_data is not None and len(embeddings_data) > 0 else None

        return {
            "slice_id": slice_id,
            "description": results["documents"][0],
            "metadata": results["metadatas"][0],
            "embedding": embedding,
        }

    async def list_videos(self) -> list[str]:
        """列出所有视频 ID"""
        collection = self._get_collection()
        results = collection.get(include=["metadatas"])

        video_ids = set()
        for metadata in results["metadatas"]:
            if "video_id" in metadata:
                video_ids.add(metadata["video_id"])

        return list(video_ids)

    async def count_slices(self, video_id: Optional[str] = None) -> int:
        """统计切片数量"""
        collection = self._get_collection()

        if video_id:
            results = collection.get(where={"video_id": video_id})
            return len(results["ids"])
        else:
            return collection.count()

    async def get_slices_by_video(self, video_id: str) -> list[dict]:
        """获取指定视频的所有切片（含向量数据库详情）"""
        collection = self._get_collection()
        results = collection.get(
            where={"video_id": video_id},
            include=["documents", "metadatas", "embeddings"],
        )

        slices = []
        if results["ids"]:
            embeddings_data = results.get("embeddings")
            for i, slice_id in enumerate(results["ids"]):
                # 安全获取 embedding (避免数组布尔判断错误)
                embedding = None
                if embeddings_data is not None and i < len(embeddings_data):
                    embedding = embeddings_data[i]

                embedding_dim = len(embedding) if embedding is not None else 0
                embedding_preview = list(embedding[:10]) if embedding is not None else []

                slice_data = {
                    "slice_id": slice_id,
                    "video_id": video_id,
                    "description": results["documents"][i] if results["documents"] else "",
                    "metadata": results["metadatas"][i] if results["metadatas"] else {},
                    "embedding_dimension": embedding_dim,
                    "embedding_preview": embedding_preview,
                }
                # 从 metadata 中提取时间信息
                metadata = results["metadatas"][i] if results["metadatas"] else {}
                slice_data["start_time"] = metadata.get("start_time", 0)
                slice_data["end_time"] = metadata.get("end_time", 0)
                slice_data["duration"] = metadata.get("duration", 0)
                slice_data["created_at"] = metadata.get("created_at", "")
                slices.append(slice_data)

        # 按开始时间排序
        slices.sort(key=lambda x: x.get("start_time", 0))
        return slices

    async def list_all_slices(self, limit: int = 1000) -> list[dict]:
        """列出所有切片"""
        collection = self._get_collection()
        results = collection.get(
            limit=limit,
            include=["documents", "metadatas", "embeddings"],
        )

        slices = []
        if results["ids"]:
            embeddings_data = results.get("embeddings")
            for i, slice_id in enumerate(results["ids"]):
                metadata = results["metadatas"][i] if results["metadatas"] else {}

                # 安全获取 embedding (避免数组布尔判断错误)
                embedding = None
                if embeddings_data is not None and i < len(embeddings_data):
                    embedding = embeddings_data[i]

                slice_data = {
                    "slice_id": slice_id,
                    "video_id": metadata.get("video_id", ""),
                    "description": results["documents"][i] if results["documents"] else "",
                    "metadata": metadata,
                    "start_time": metadata.get("start_time", 0),
                    "end_time": metadata.get("end_time", 0),
                    "duration": metadata.get("duration", 0),
                    "embedding_dimension": len(embedding) if embedding is not None else 0,
                }
                slices.append(slice_data)

        return slices


class InMemoryVectorStore(VectorStore):
    """
    内存向量存储 (用于测试)
    不依赖 ChromaDB
    """

    def __init__(self):
        self.slices: dict[str, SliceRecord] = {}

    def _get_collection(self):
        raise NotImplementedError("InMemoryVectorStore 不使用 ChromaDB")

    async def add_slice(self, slice_obj) -> str:
        record = SliceRecord(
            slice_id=slice_obj.slice_id,
            video_id=slice_obj.video_id,
            start_time=slice_obj.start_time,
            end_time=slice_obj.end_time,
            description=slice_obj.description or "",
            embedding=slice_obj.embedding or [],
            metadata=slice_obj.metadata,
        )
        self.slices[slice_obj.slice_id] = record
        return slice_obj.slice_id

    async def add_slices_batch(self, slice_objs: list) -> list[str]:
        """批量添加视频切片"""
        ids = []
        for slice_obj in slice_objs:
            record = SliceRecord(
                slice_id=slice_obj.slice_id,
                video_id=slice_obj.video_id,
                start_time=slice_obj.start_time,
                end_time=slice_obj.end_time,
                description=slice_obj.description or "",
                embedding=slice_obj.embedding or [],
                metadata=slice_obj.metadata,
            )
            self.slices[slice_obj.slice_id] = record
            ids.append(slice_obj.slice_id)
        return ids

    async def search(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        video_id: Optional[str] = None,
        min_similarity: float = 0.0,
    ) -> list[dict]:
        import numpy as np

        query_vec = np.array(query_embedding)
        matches = []

        for record in self.slices.values():
            if video_id and record.video_id != video_id:
                continue

            if not record.embedding:
                continue

            # 计算余弦相似度
            record_vec = np.array(record.embedding)
            similarity = np.dot(query_vec, record_vec) / (
                np.linalg.norm(query_vec) * np.linalg.norm(record_vec)
            )

            if similarity >= min_similarity:
                matches.append({
                    "slice_id": record.slice_id,
                    "description": record.description,
                    "metadata": record.metadata,
                    "similarity": float(similarity),
                    "start_time": record.start_time,
                    "end_time": record.end_time,
                    "video_id": record.video_id,
                })

        # 按相似度排序
        matches.sort(key=lambda x: x["similarity"], reverse=True)
        return matches[:n_results]

    async def delete_slice(self, slice_id: str):
        if slice_id in self.slices:
            del self.slices[slice_id]

    async def delete_video(self, video_id: str):
        to_delete = [sid for sid, s in self.slices.items() if s.video_id == video_id]
        for sid in to_delete:
            del self.slices[sid]

    async def get_slice(self, slice_id: str) -> Optional[dict]:
        record = self.slices.get(slice_id)
        if not record:
            return None
        return {
            "slice_id": slice_id,
            "description": record.description,
            "metadata": record.metadata,
            "embedding": record.embedding,
        }

    async def list_videos(self) -> list[str]:
        return list(set(s.video_id for s in self.slices.values()))

    async def count_slices(self, video_id: Optional[str] = None) -> int:
        if video_id:
            return sum(1 for s in self.slices.values() if s.video_id == video_id)
        return len(self.slices)

    async def get_slices_by_video(self, video_id: str) -> list[dict]:
        """获取指定视频的所有切片"""
        slices = []
        for record in self.slices.values():
            if record.video_id == video_id:
                slices.append({
                    "slice_id": record.slice_id,
                    "video_id": record.video_id,
                    "description": record.description,
                    "metadata": record.metadata,
                    "start_time": record.start_time,
                    "end_time": record.end_time,
                    "duration": record.duration,
                    "embedding_dimension": len(record.embedding) if record.embedding else 0,
                    "embedding_preview": record.embedding[:10] if record.embedding else [],
                })
        slices.sort(key=lambda x: x.get("start_time", 0))
        return slices

    async def list_all_slices(self, limit: int = 1000) -> list[dict]:
        """列出所有切片"""
        slices = []
        for record in list(self.slices.values())[:limit]:
            slices.append({
                "slice_id": record.slice_id,
                "video_id": record.video_id,
                "description": record.description,
                "metadata": record.metadata,
                "start_time": record.start_time,
                "end_time": record.end_time,
                "duration": record.duration,
                "embedding_dimension": len(record.embedding) if record.embedding else 0,
            })
        return slices