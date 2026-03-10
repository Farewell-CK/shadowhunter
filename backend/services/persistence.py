"""
持久化存储服务
使用 JSON 文件存储任务状态和视频元信息
支持服务重启后恢复状态
"""

import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Any
import threading

logger = logging.getLogger("shadowhunter.persistence")


class PersistenceManager:
    """
    JSON 文件持久化管理器

    功能：
    1. 保存任务状态 (task_status)
    2. 保存视频元信息 (video_meta)
    3. 服务启动时自动加载
    4. 异步保存，不阻塞主流程
    """

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 文件路径
        self.task_status_file = self.data_dir / "task_status.json"
        self.video_meta_file = self.data_dir / "video_meta.json"

        # 保存锁，防止并发写入冲突
        self._lock = threading.Lock()

        # 是否有未保存的更改
        self._dirty = False

        logger.info(f"持久化管理器初始化完成，数据目录: {self.data_dir}")

    def _load_json(self, file_path: Path, default: Any = None) -> Any:
        """加载 JSON 文件"""
        if not file_path.exists():
            return default if default is not None else {}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.debug(f"加载文件: {file_path.name}")
                return data
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败 {file_path}: {e}")
            return default if default is not None else {}
        except Exception as e:
            logger.error(f"加载文件失败 {file_path}: {e}")
            return default if default is not None else {}

    def _save_json(self, file_path: Path, data: Any) -> bool:
        """保存 JSON 文件"""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
                logger.debug(f"保存文件: {file_path.name}")
                return True
        except Exception as e:
            logger.error(f"保存文件失败 {file_path}: {e}")
            return False

    # ========== 任务状态 ==========

    def load_task_status(self) -> dict:
        """
        加载所有任务状态

        Returns:
            {task_id: {status, progress, message, ...}}
        """
        data = self._load_json(self.task_status_file, {})

        # 过滤掉过期的任务（超过24小时的已完成/失败任务）
        now = datetime.now()
        valid_tasks = {}

        for task_id, task in data.items():
            created_at = task.get("created_at")
            status = task.get("status", "")

            if created_at:
                try:
                    created_time = datetime.fromisoformat(created_at)
                    age_hours = (now - created_time).total_seconds() / 3600

                    # 已完成/失败任务保留24小时，进行中任务一直保留
                    if status in ("completed", "failed") and age_hours > 24:
                        continue
                except:
                    pass

            valid_tasks[task_id] = task

        removed = len(data) - len(valid_tasks)
        if removed > 0:
            logger.info(f"清理了 {removed} 个过期任务记录")

        logger.info(f"加载了 {len(valid_tasks)} 个任务状态")
        return valid_tasks

    def save_task_status(self, task_status: dict) -> bool:
        """
        保存所有任务状态

        Args:
            task_status: 任务状态字典
        """
        with self._lock:
            return self._save_json(self.task_status_file, task_status)

    def update_task(self, task_id: str, task_data: dict) -> bool:
        """
        更新单个任务状态（增量更新）

        Args:
            task_id: 任务 ID
            task_data: 任务数据
        """
        with self._lock:
            # 加载现有数据
            data = self._load_json(self.task_status_file, {})

            # 更新任务
            data[task_id] = {
                **data.get(task_id, {}),
                **task_data,
                "updated_at": datetime.now().isoformat(),
            }

            return self._save_json(self.task_status_file, data)

    # ========== 视频元信息 ==========

    def load_video_meta(self) -> dict:
        """
        加载所有视频元信息

        Returns:
            {video_id: {total_slices, video_duration, status, ...}}
        """
        data = self._load_json(self.video_meta_file, {})
        logger.info(f"加载了 {len(data)} 个视频元信息")
        return data

    def save_video_meta(self, video_meta: dict) -> bool:
        """
        保存所有视频元信息
        """
        with self._lock:
            return self._save_json(self.video_meta_file, video_meta)

    def update_video_meta(self, video_id: str, meta_data: dict) -> bool:
        """
        更新单个视频元信息（增量更新）
        """
        with self._lock:
            data = self._load_json(self.video_meta_file, {})

            data[video_id] = {
                **data.get(video_id, {}),
                **meta_data,
                "updated_at": datetime.now().isoformat(),
            }

            return self._save_json(self.video_meta_file, data)

    # ========== 批量保存 ==========

    def save_all(self, task_status: dict, video_meta: dict) -> bool:
        """
        批量保存所有数据
        """
        success1 = self.save_task_status(task_status)
        success2 = self.save_video_meta(video_meta)
        return success1 and success2

    # ========== 清理 ==========

    def cleanup_expired_tasks(self, max_age_hours: int = 24) -> int:
        """
        清理过期的任务记录

        Args:
            max_age_hours: 最大保留时间（小时）

        Returns:
            清理的任务数量
        """
        with self._lock:
            data = self._load_json(self.task_status_file, {})

            now = datetime.now()
            to_remove = []

            for task_id, task in data.items():
                created_at = task.get("created_at")
                status = task.get("status", "")

                # 只清理已完成或失败的任务
                if status not in ("completed", "failed"):
                    continue

                if created_at:
                    try:
                        created_time = datetime.fromisoformat(created_at)
                        age_hours = (now - created_time).total_seconds() / 3600

                        if age_hours > max_age_hours:
                            to_remove.append(task_id)
                    except:
                        pass

            for task_id in to_remove:
                del data[task_id]

            if to_remove:
                self._save_json(self.task_status_file, data)
                logger.info(f"清理了 {len(to_remove)} 个过期任务")

            return len(to_remove)


# 单例实例
_persistence_manager: Optional[PersistenceManager] = None


def get_persistence(data_dir: str = "./data") -> PersistenceManager:
    """获取持久化管理器单例"""
    global _persistence_manager
    if _persistence_manager is None:
        _persistence_manager = PersistenceManager(data_dir)
    return _persistence_manager