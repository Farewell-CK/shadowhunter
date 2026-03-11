"""
视频处理服务
实现动态分片逻辑 (8s 片段, 5s 步长)
"""

import asyncio
import json
import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Iterator, AsyncIterator
import hashlib

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None

from config import (
    SLICE_DURATION,
    SLICE_STRIDE,
    SLICE_MIN_DURATION,
    SLICE_MAX_DURATION,
    TEMP_DIR,
    CLEANUP_AFTER_PROCESS,
)

# 配置日志
logger = logging.getLogger("shadowhunter.video")


@dataclass
class VideoSlice:
    """视频片段元数据"""
    slice_id: str  # 唯一标识
    video_id: str  # 原视频 ID
    start_time: float  # 开始时间 (秒)
    end_time: float  # 结束时间 (秒)
    duration: float  # 时长 (秒)
    file_path: Optional[Path] = None  # 临时文件路径
    description: Optional[str] = None  # AI 生成的描述
    embedding: Optional[list[float]] = None  # 向量
    metadata: dict = field(default_factory=dict)  # 额外元数据

    @property
    def time_range(self) -> str:
        """返回时间范围字符串"""
        return f"{self.start_time:.1f}s - {self.end_time:.1f}s"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "slice_id": self.slice_id,
            "video_id": self.video_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "description": self.description,
            "metadata": self.metadata,
        }


@dataclass
class VideoInfo:
    """视频文件信息"""
    file_path: Path
    duration: float  # 总时长 (秒)
    width: int
    height: int
    fps: float
    codec: str
    file_size: int  # 字节数


class VideoSlicer:
    """
    视频分片器
    使用 FFmpeg 进行视频切割
    支持动态重叠分片策略
    """

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = Path(output_dir or TEMP_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_video_info(self, video_path: Path) -> VideoInfo:
        """
        获取视频文件信息
        使用 ffprobe 提取元数据
        """
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe 失败: {result.stderr}")

        data = json.loads(result.stdout)

        # 提取视频流信息
        video_stream = None
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                video_stream = stream
                break

        if not video_stream:
            raise ValueError(f"未找到视频流: {video_path}")

        # 解析帧率
        fps_str = video_stream.get("r_frame_rate", "30/1")
        if "/" in fps_str:
            num, den = fps_str.split("/")
            fps = float(num) / float(den) if float(den) > 0 else 30.0
        else:
            fps = float(fps_str)

        return VideoInfo(
            file_path=video_path,
            duration=float(data["format"].get("duration", 0)),
            width=int(video_stream.get("width", 0)),
            height=int(video_stream.get("height", 0)),
            fps=fps,
            codec=video_stream.get("codec_name", "unknown"),
            file_size=int(data["format"].get("size", 0)),
        )

    def calculate_slices(
        self,
        video_duration: float,
        slice_duration: float = SLICE_DURATION,
        stride: float = SLICE_STRIDE,
    ) -> list[tuple[float, float]]:
        """
        计算分片时间点

        Args:
            video_duration: 视频总时长 (秒)
            slice_duration: 每个片段时长 (秒)
            stride: 步长 (秒)

        Returns:
            [(start_time, end_time), ...] 片段时间列表
        """
        slices = []
        start = 0.0

        while start < video_duration:
            end = min(start + slice_duration, video_duration)

            # 确保片段时长不小于最小值
            if end - start >= SLICE_MIN_DURATION:
                slices.append((start, end))

            # 最后一个片段
            if end >= video_duration:
                break

            start += stride

        return slices

    def slice_video(
        self,
        video_path: Path,
        video_id: Optional[str] = None,
        slice_duration: float = SLICE_DURATION,
        stride: float = SLICE_STRIDE,
    ) -> Iterator[VideoSlice]:
        """
        切割视频为多个片段

        Args:
            video_path: 视频文件路径
            video_id: 视频唯一标识 (可选)
            slice_duration: 片段时长 (秒)
            stride: 步长 (秒)

        Yields:
            VideoSlice: 视频片段元数据
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        # 获取视频信息
        info = self.get_video_info(video_path)
        logger.info(f"视频信息: 时长={info.duration:.1f}s, 分辨率={info.width}x{info.height}, 编码={info.codec}")

        # 生成视频 ID
        if not video_id:
            video_id = self._generate_video_id(video_path)

        # 计算分片
        slice_times = self.calculate_slices(info.duration, slice_duration, stride)
        logger.info(f"计划切割 {len(slice_times)} 个片段")

        # 切割每个片段
        for idx, (start, end) in enumerate(slice_times):
            slice_id = f"{video_id}_{idx:04d}"
            output_file = self.output_dir / f"{slice_id}.mp4"

            # 使用 FFmpeg 切割
            self._extract_segment(video_path, start, end, output_file)

            slice_obj = VideoSlice(
                slice_id=slice_id,
                video_id=video_id,
                start_time=start,
                end_time=end,
                duration=end - start,
                file_path=output_file,
                metadata={
                    "original_file": str(video_path),
                    "resolution": f"{info.width}x{info.height}",
                    "fps": info.fps,
                    "index": idx,
                },
            )

            yield slice_obj

    async def _extract_segment(
        self,
        video_path: Path,
        start: float,
        end: float,
        output_path: Path,
        fast_mode: bool = True,
    ):
        """
        提取视频片段 (异步版本)
        """
        duration = end - start

        # 方案1: 无损切割 (极速)
        if fast_mode:
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start),
                "-i", str(video_path),
                "-t", str(duration),
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                "-loglevel", "error",
                str(output_path),
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            
            if process.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
                return

        # 方案2: 重新编码 (兜底)
        cmd_encode = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", str(video_path),
            "-t", str(duration),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "superfast",
            "-loglevel", "error",
            str(output_path),
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd_encode,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()

    async def slice_video_async(
        self,
        video_path: Path,
        video_id: str,
        slice_duration: float = SLICE_DURATION,
        stride: float = SLICE_STRIDE,
    ) -> AsyncIterator[VideoSlice]:
        """
        异步切割视频，通过 yield 实现流水线输出
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        info = self.get_video_info(video_path)
        slice_times = self.calculate_slices(info.duration, slice_duration, stride)
        
        logger.info(f"开始异步切割视频: {video_id}, 共 {len(slice_times)} 个片段")

        for idx, (start, end) in enumerate(slice_times):
            slice_id = f"{video_id}_{idx:04d}"
            output_file = self.output_dir / f"{slice_id}.mp4"

            # 异步执行 FFmpeg
            await self._extract_segment(video_path, start, end, output_file)

            slice_obj = VideoSlice(
                slice_id=slice_id,
                video_id=video_id,
                start_time=start,
                end_time=end,
                duration=end - start,
                file_path=output_file,
                metadata={
                    "original_file": str(video_path),
                    "resolution": f"{info.width}x{info.height}",
                    "fps": info.fps,
                    "index": idx,
                },
            )
            yield slice_obj

    def _generate_video_id(self, video_path: Path) -> str:
        """生成视频唯一标识"""
        hash_input = f"{video_path.name}_{video_path.stat().st_size}_{datetime.now().isoformat()}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:12]

    def cleanup_slice(self, slice_obj: VideoSlice):
        """清理临时切片文件"""
        if slice_obj.file_path and slice_obj.file_path.exists():
            slice_obj.file_path.unlink()
            logger.debug(f"已清理临时文件: {slice_obj.file_path}")


class MotionDetector:
    """
    运动检测器
    使用 OpenCV 的混合高斯建模 (MOG2) 或 帧差法
    """

    def __init__(self, threshold_ratio: float = 0.01):
        """
        Args:
            threshold_ratio: 默认运动面积占比阈值 (0-1)
        """
        self.default_threshold = threshold_ratio

    def has_motion(self, video_path: Path, threshold_override: Optional[float] = None) -> bool:
        """检测视频片段中是否有显著运动"""
        if cv2 is None:
            return True  # 没安装 cv2，默认全通过

        threshold = threshold_override if threshold_override is not None else self.default_threshold

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return True

        fgbg = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=True)
        
        motion_detected = False
        frame_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            # 每 5 帧采样一次，提高速度
            if frame_count % 5 != 0:
                continue

            # 缩小尺寸加快处理
            small_frame = cv2.resize(frame, (640, 360))
            fgmask = fgbg.apply(small_frame)
            
            # 计算非零像素比例 (运动区域)
            non_zero = cv2.countNonZero(fgmask)
            total_pixels = small_frame.shape[0] * small_frame.shape[1]
            
            if (non_zero / total_pixels) > threshold:
                motion_detected = True
                break
        
        cap.release()
        return motion_detected


class YoloDetector:
    """
    YOLO 目标检测器接口 (真实接入)
    """

    def __init__(self, model_path: Optional[str] = "/root/workspace/zp/ShadowHunter_qwen/yolov8n.pt"):
        self.model = None
        self.is_ready = False
        try:
            from ultralytics import YOLO
            import os
            # 确保模型文件存在
            if model_path and os.path.exists(model_path):
                logger.info(f"正在加载 YOLO 模型: {model_path}")
                self.model = YOLO(model_path)
                self.is_ready = True
            else:
                logger.warning(f"YOLO 模型不存在: {model_path}，目标检测将默认放行。")
        except ImportError:
            logger.warning("未安装 ultralytics 库，无法使用 YOLO，目标检测将默认放行。")

    def detect_objects(self, video_path: Path) -> list:
        """
        检测视频中的目标
        返回包含的目标标签列表 (如 'person', 'car')
        """
        if not self.is_ready or not self.model:
            return []
        
        try:
            # 读取视频
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                return []

            detected_labels = set()
            frame_count = 0

            # 抽几帧进行检测即可，没必要逐帧检测
            while cap.isOpened() and frame_count < 30: # 最多看前30帧
                ret, frame = cap.read()
                if not ret:
                    break
                
                frame_count += 1
                
                # 每 5 帧检测一次以加快速度
                if frame_count % 5 == 0:
                    results = self.model.predict(frame, verbose=False)
                    for r in results:
                        classes = r.boxes.cls.cpu().numpy()
                        names = r.names
                        for c in classes:
                            detected_labels.add(names[int(c)])
            
            cap.release()
            return list(detected_labels)

        except Exception as e:
            logger.error(f"YOLO 检测过程出错: {e}")
            return []

    def has_required_objects(self, video_path: Path, required_labels: list) -> bool:
        """
        判断视频中是否包含感兴趣的目标
        """
        if not self.is_ready:
            return True # 没加载模型时，默认通过

        found_labels = self.detect_objects(video_path)
        logger.debug(f"[{video_path.name}] YOLO 发现目标: {found_labels}")
        
        for label in required_labels:
            if label in found_labels:
                return True
        return False


class VideoScanner:
    """
    智能视频扫描器
    不再固定切片，而是先扫描全视频找出目标出现的时段
    """
    def __init__(self, yolo_detector: 'YoloDetector'):
        self.yolo_detector = yolo_detector

    async def scan_for_events(
        self, 
        video_path: Path, 
        target_labels: list, 
        fps_limit: float = 1.0,
        status_callback = None
    ) -> list[tuple[float, float]]:
        """
        全片快速扫描目标
        """
        return await asyncio.to_thread(self._scan_blocking, video_path, target_labels, fps_limit, status_callback)

    def _scan_blocking(self, video_path, target_labels, fps_limit, status_callback):
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened(): return []
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_interval = max(1, int(fps / fps_limit))
        
        active_timestamps = []
        frame_idx = 0
        
        while True:
            ret, frame = cap.read()
            if not ret: break
            
            if frame_idx % frame_interval == 0:
                current_time = frame_idx / fps
                if status_callback:
                    status_callback(f"正在全片扫描目标... {current_time:.1f}s / {total_frames/fps:.1f}s")
                
                # 运行 YOLO 快速检测
                results = self.yolo_detector.model.predict(frame, verbose=False)
                found = False
                for r in results:
                    classes = r.boxes.cls.cpu().numpy()
                    names = r.names
                    for c in classes:
                        if names[int(c)] in target_labels:
                            found = True
                            break
                    if found: break
                
                if found:
                    active_timestamps.append(current_time)
            
            frame_idx += 1
        
        cap.release()
        
        # 将散点聚类为区间 (合并 5 秒以内的目标)
        return self._cluster_timestamps(active_timestamps, merge_gap=5.0)

    def _cluster_timestamps(self, timestamps: list[float], merge_gap: float) -> list[tuple[float, float]]:
        if not timestamps: return []
        
        events = []
        start = timestamps[0]
        prev = timestamps[0]
        
        for i in range(1, len(timestamps)):
            curr = timestamps[i]
            if curr - prev > merge_gap:
                # 结束当前区间，开始新区间
                events.append((max(0, start - 2.0), prev + 2.0)) # 前后各扩 2 秒
                start = curr
            prev = curr
        
        events.append((max(0, start - 2.0), prev + 2.0))
        return events

    async def extract_target_keyframes(
        self, 
        video_path: Path, 
        target_labels: list, 
        max_frames: int = 3
    ) -> list[Path]:
        """
        [核心修复] 以目标为中心的智能抽帧
        从视频片段中，利用 YOLO 找出包含目标、且目标面积最大的几张帧
        彻底解决“片段中有7.5秒没人，只有0.5秒有人”导致大模型失焦的问题。
        """
        def _extract():
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened(): return []
            
            frame_scores = [] # (score, frame)
            frame_idx = 0
            
            while True:
                ret, frame = cap.read()
                if not ret: break
                
                # 每 3 帧抽一次，寻找最佳
                if frame_idx % 3 == 0:
                    results = self.yolo_detector.model.predict(frame, verbose=False)
                    max_area = 0
                    
                    for r in results:
                        boxes = r.boxes
                        for box in boxes:
                            cls_id = int(box.cls[0].item())
                            label = r.names[cls_id]
                            
                            if label in target_labels:
                                # 计算边界框面积作为“清晰度/重要性”得分
                                x1, y1, x2, y2 = box.xyxy[0].tolist()
                                area = (x2 - x1) * (y2 - y1)
                                if area > max_area:
                                    max_area = area
                    
                    if max_area > 0:
                        frame_scores.append((max_area, frame))
                        
                frame_idx += 1
            
            cap.release()
            
            # 按面积从大到小排序，选出最具代表性的前 max_frames 张
            frame_scores.sort(key=lambda x: x[0], reverse=True)
            top_frames = [f[1] for f in frame_scores[:max_frames]]
            
            # 将这些优质帧保存为临时文件
            saved_paths = []
            for idx, f in enumerate(top_frames):
                tmp_path = Path(tempfile.gettempdir()) / f"keyframe_{uuid.uuid4().hex}_{idx}.jpg"
                cv2.imwrite(str(tmp_path), f)
                saved_paths.append(tmp_path)
                
            return saved_paths

        return await asyncio.to_thread(_extract)

class VideoWorker:
    """
    视频处理工作器
    协调分片、智能过滤、AI 分析、向量存储
    """

    def __init__(self, ai_client, vector_store, slicer: Optional[VideoSlicer] = None):
        self.ai_client = ai_client
        self.vector_store = vector_store
        self.slicer = slicer or VideoSlicer()
        self.motion_detector = MotionDetector()
        self.yolo_detector = YoloDetector()
        self.scanner = VideoScanner(self.yolo_detector) # 引入扫描器

    async def extract_visual_features(self, slice_obj: VideoSlice) -> list[float]:
        """
        提取切片的视觉特征向量 (CLIP 逻辑)
        """
        if not slice_obj.file_path or not slice_obj.file_path.exists():
            return []

        # 1. 抽取中间帧作为代表
        cap = cv2.VideoCapture(str(slice_obj.file_path))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            return []

        # 2. 临时保存并获取视觉向量
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            cv2.imwrite(str(tmp_path), frame)
            
            emb_res = await self.ai_client.get_visual_embedding(tmp_path)
            tmp_path.unlink()
            
            return emb_res.vector if emb_res else []

    async def _should_process_slice(
        self, 
        slice_obj: VideoSlice, 
        custom_required_objects: list = None, 
        status_callback=None,
        enable_motion_detection: Optional[bool] = None,
        enable_object_detection: Optional[bool] = None,
        motion_threshold: Optional[float] = None
    ) -> bool:
        """
        判断一个切片是否值得进行 AI 深度分析
        实现漏斗级联过滤逻辑
        """
        import config
        
        req_objs = custom_required_objects if custom_required_objects is not None else config.REQUIRED_OBJECTS
        use_motion = enable_motion_detection if enable_motion_detection is not None else config.ENABLE_MOTION_DETECTION
        use_object = enable_object_detection if enable_object_detection is not None else config.ENABLE_OBJECT_DETECTION

        # 1. 如果都没开启，默认全量分析 (保持原有逻辑兼容性)
        if not use_motion and not use_object:
            if status_callback: status_callback("GLM-4.6V 深度分析中...")
            return True

        # 2. 运动检测过滤 (第一级漏斗)
        if use_motion:
            if status_callback: status_callback(f"OpenCV 运动检测中(阈值:{motion_threshold or '默认'})...")
            if not self.motion_detector.has_motion(slice_obj.file_path, motion_threshold):
                logger.info(f"  [跳过] 无运动特征: {slice_obj.slice_id}")
                slice_obj.metadata["filter_reason"] = "opencv"
                return False

        # 3. 目标检测过滤 (第二级漏斗)
        if use_object:
            if status_callback: status_callback("YOLO 目标初筛中...")
            if not self.yolo_detector.has_required_objects(slice_obj.file_path, req_objs):
                logger.info(f"  [跳过] 未检测到感兴趣目标: {slice_obj.slice_id}")
                slice_obj.metadata["filter_reason"] = "yolo"
                return False

        if status_callback: status_callback("GLM-4.6V 深度分析中...")
        return True

    async def process_video(
        self,
        video_path: Path,
        video_id: Optional[str] = None,
        progress_callback=None,
        max_concurrent: int = 30,
    ) -> list[VideoSlice]:
        """
        处理完整视频流程 (支持并行处理)

        1. 视频分片
        2. AI 分析每个片段 (并行，最多 max_concurrent 个)
        3. 生成向量并存储

        Args:
            video_path: 视频文件路径
            video_id: 视频唯一标识
            progress_callback: 进度回调函数
            max_concurrent: 最大并发数 (默认30)

        Returns:
            处理完成的所有片段
        """
        import time
        from ai_client import ZhipuManager

        video_path = Path(video_path)
        slices = list(self.slicer.slice_video(video_path, video_id))

        results = []
        total = len(slices)
        processed_count = 0

        # 并行处理切片
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_single_slice(slice_obj, idx):
            nonlocal processed_count
            start_time = time.time()

            async with semaphore:
                try:
                    # 智能过滤：判断是否需要 AI 深度分析
                    if await self._should_process_slice(slice_obj):
                        # AI 分析 (公安图侦专用 Prompt)
                        analysis = await self.ai_client.analyze_video(
                            video_source=slice_obj.file_path,
                            prompt="""你是一个专业的公安图侦与视频分析专家。
请审查这段视频切片，极其简练地提取可用于刑侦检索的核心特征。
请直接输出一段高浓度的特征描述（用逗号分隔，不要有任何多余的寒暄和解释词）。

重点关注以下维度（若画面中没有，则严格忽略，绝对不要凭空捏造）：
1. 人物体貌：性别/大致年龄段/体型（胖瘦）
2. 衣着伪装：上/下衣颜色与款式/是否戴帽子、头盔、口罩、墨镜
3. 携带物品：背包/手提袋/雨伞/手持可疑物
4. 车辆特征：车型（轿车/SUV/两轮电动车等）/颜色/显著特征
5. 行为轨迹：正常行走/奔跑/徘徊/左顾右盼/翻越

示例输出："男性, 青壮年, 黑上衣, 蓝牛仔裤, 戴白色头盔, 骑行红色两轮电动车, 正在左顾右盼" """,
                        )
                        slice_obj.description = analysis.description
                        slice_obj.metadata["actions"] = analysis.actions
                        slice_obj.metadata["objects"] = analysis.objects
                    else:
                        slice_obj.description = "无显著目标 (已过滤)"
                        slice_obj.metadata["skipped"] = True

                except Exception as e:
                    logger.warning(f"AI 分析失败 [{slice_obj.slice_id}]: {e}")
                    slice_obj.description = "分析失败"

                # 生成向量 (仅对未过滤且分析成功的切片)
                if slice_obj.description and slice_obj.description not in ["分析失败", "无显著目标 (已过滤)"]:
                    try:
                        embedding_result = await self.ai_client.get_embedding(slice_obj.description)
                        slice_obj.embedding = embedding_result.vector
                        slice_obj.metadata["embedding_dimension"] = embedding_result.dimension
                    except Exception as e:
                        logger.warning(f"向量生成失败 [{slice_obj.slice_id}]: {e}")
                elif slice_obj.metadata.get("skipped"):
                     # 如果被过滤，可以存一个空向量或不存入向量库
                     pass

                # 存储到向量库
                if slice_obj.embedding:
                    await self.vector_store.add_slice(slice_obj)

                elapsed = time.time() - start_time
                processed_count += 1

                # 清理临时文件
                if self.slicer:
                    self.slicer.cleanup_slice(slice_obj)

                # 回调进度
                if progress_callback:
                    progress_callback(processed_count, total, slice_obj, elapsed)

                return slice_obj

        # 并行执行所有任务
        tasks = [process_single_slice(slice_obj, idx) for idx, slice_obj in enumerate(slices)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 过滤成功的结果
        successful_results = [r for r in results if isinstance(r, VideoSlice)]

        return successful_results

    async def process_video_slices(
        self,
        slices: list,
        progress_callback=None,
        max_concurrent: int = 30,
    ) -> list:
        """
        处理指定的切片列表 (支持并行处理和断点续传)

        Args:
            slices: VideoSlice 对象列表
            progress_callback: 进度回调函数
            max_concurrent: 最大并发数

        Returns:
            处理完成的切片列表
        """
        import time

        results = []
        total = len(slices)
        processed_count = 0

        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_single_slice(slice_obj, idx):
            nonlocal processed_count
            start_time = time.time()

            async with semaphore:
                try:
                    # 智能过滤：判断是否需要 AI 深度分析
                    if await self._should_process_slice(slice_obj):
                        # AI 分析 (公安图侦专用 Prompt)
                        analysis = await self.ai_client.analyze_video(
                            video_source=slice_obj.file_path,
                            prompt="""你是一个专业的公安图侦与视频分析专家。
请审查这段视频切片，极其简练地提取可用于刑侦检索的核心特征。
请直接输出一段高浓度的特征描述（用逗号分隔，不要有任何多余的寒暄和解释词）。

重点关注以下维度（若画面中没有，则严格忽略，绝对不要凭空捏造）：
1. 人物体貌：性别/大致年龄段/体型（胖瘦）
2. 衣着伪装：上/下衣颜色与款式/是否戴帽子、头盔、口罩、墨镜
3. 携带物品：背包/手提袋/雨伞/手持可疑物
4. 车辆特征：车型（轿车/SUV/两轮电动车等）/颜色/显著特征
5. 行为轨迹：正常行走/奔跑/徘徊/左顾右盼/翻越

示例输出："男性, 青壮年, 黑上衣, 蓝牛仔裤, 戴白色头盔, 骑行红色两轮电动车, 正在左顾右盼" """,
                        )
                        slice_obj.description = analysis.description
                        slice_obj.metadata["actions"] = analysis.actions
                        slice_obj.metadata["objects"] = analysis.objects
                    else:
                        slice_obj.description = "无显著目标 (已过滤)"
                        slice_obj.metadata["skipped"] = True

                except Exception as e:
                    print(f"  AI 分析失败: {e}")
                    slice_obj.description = "分析失败"

                # 生成向量 (仅对未过滤且分析成功的切片)
                if slice_obj.description and slice_obj.description not in ["分析失败", "无显著目标 (已过滤)"]:
                    try:
                        embedding_result = await self.ai_client.get_embedding(slice_obj.description)
                        slice_obj.embedding = embedding_result.vector
                        slice_obj.metadata["embedding_dimension"] = embedding_result.dimension
                    except Exception as e:
                        print(f"  向量生成失败: {e}")
                elif slice_obj.metadata.get("skipped"):
                     pass

                # 存储到向量库
                if slice_obj.embedding:
                    await self.vector_store.add_slice(slice_obj)

                elapsed = time.time() - start_time
                processed_count += 1

                # 清理临时文件
                if self.slicer:
                    self.slicer.cleanup_slice(slice_obj)

                # 回调进度
                if progress_callback:
                    progress_callback(processed_count, total, slice_obj, elapsed)

                return slice_obj

        # 并行执行所有任务
        tasks = [process_single_slice(slice_obj, idx) for idx, slice_obj in enumerate(slices)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 过滤成功的结果
        successful_results = [r for r in results if isinstance(r, VideoSlice)]

        return successful_results


# 便捷函数
def create_slicer(output_dir: Optional[str] = None) -> VideoSlicer:
    """创建视频分片器"""
    return VideoSlicer(Path(output_dir) if output_dir else None)