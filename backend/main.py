"""
FastAPI 后端服务
提供视频处理、搜索、流媒体等 API
"""

import logging
import sys
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import asyncio
import uuid
from pathlib import Path
import shutil
import time
from datetime import datetime

from config import API_HOST, API_PORT, TEMP_DIR, MAX_CONCURRENT_REQUESTS
from ai_client import ZhipuManager, create_client
from services.video_worker import VideoSlicer, VideoWorker, VideoSlice
from services.vector_store import VectorStore
from services.search_engine import SearchEngine
from services.persistence import get_persistence, PersistenceManager
from services.direct_matcher import DirectMatcher


# 配置日志系统
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("shadowhunter")


# 创建 FastAPI 应用
app = FastAPI(
    title="ShadowHunter API",
    description="视频语义检索系统后端 API",
    version="1.0.0",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局实例
ai_client: Optional[ZhipuManager] = None
vector_store: Optional[VectorStore] = None
search_engine: Optional[SearchEngine] = None
video_slicer: Optional[VideoSlicer] = None
persistence: Optional[PersistenceManager] = None
direct_matcher: Optional[DirectMatcher] = None

# 任务状态存储
task_status: dict[str, dict] = {}

# 视频元信息存储 (video_id -> {total_slices, video_duration})
video_meta: dict[str, dict] = {}

# 任务过期时间 (秒)
TASK_EXPIRE_SECONDS = 3600  # 1小时后过期


def _cleanup_expired_tasks():
    """清理过期的任务状态，防止内存泄漏"""
    now = time.time()
    expired = [
        task_id for task_id, status in task_status.items()
        if status.get("created_at", 0) < now - TASK_EXPIRE_SECONDS
    ]
    for task_id in expired:
        del task_status[task_id]
        logger.info(f"过期任务已移除: {task_id}")


# Pydantic 模型
class SearchRequest(BaseModel):
    query: str
    video_id: Optional[str] = None
    top_k: int = 10
    verify_top_n: int = 3


class FeatureSearchRequest(BaseModel):
    features: list[str]
    video_id: Optional[str] = None
    top_k: int = 10


class AnalyzeRequest(BaseModel):
    slice_id: str
    focus_features: list[str]


class TaskStatus(BaseModel):
    task_id: str
    status: str
    progress: float
    message: str
    result: Optional[dict] = None


class DirectMatchRequest(BaseModel):
    """直接匹配请求"""
    video_paths: list[str]  # 视频文件路径列表
    query: str              # 查询描述
    top_k: int = 10         # 返回结果数量
    store_results: bool = True  # 是否存储到向量库


class DirectMatchUploadRequest(BaseModel):
    """直接匹配上传请求（前端上传后调用）"""
    query: str
    top_k: int = 10
    store_results: bool = True


# 启动事件
@app.on_event("startup")
async def startup_event():
    global ai_client, vector_store, search_engine, video_slicer, persistence, task_status, video_meta, direct_matcher

    # 初始化持久化存储
    persistence = get_persistence("./data")

    # 从持久化存储加载状态
    task_status = persistence.load_task_status()
    video_meta = persistence.load_video_meta()

    # 初始化其他服务
    ai_client = await create_client()
    vector_store = VectorStore()
    search_engine = SearchEngine(ai_client, vector_store)
    video_slicer = VideoSlicer()
    direct_matcher = DirectMatcher(ai_client, vector_store, video_slicer)

    # 确保临时目录存在
    Path(TEMP_DIR).mkdir(parents=True, exist_ok=True)

    logger.info("ShadowHunter API 启动完成")
    logger.info(f"已加载 {len(task_status)} 个任务状态, {len(video_meta)} 个视频元信息")


# 关闭事件 - 保存状态
@app.on_event("shutdown")
async def shutdown_event():
    """服务关闭时保存所有状态"""
    global persistence, task_status, video_meta

    if persistence:
        persistence.save_all(task_status, video_meta)
        logger.info("已保存所有状态到持久化存储")

    logger.info("ShadowHunter API 已关闭")


# 健康检查
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "services": {
            "ai_client": ai_client is not None,
            "vector_store": vector_store is not None,
            "search_engine": search_engine is not None,
        }
    }


# 视频上传与处理
@app.post("/api/videos/upload")
async def upload_video(file: UploadFile = File(...)):
    """
    上传视频文件
    """
    # 生成视频 ID
    video_id = uuid.uuid4().hex[:12]

    # 保存文件
    video_dir = Path(TEMP_DIR) / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)

    file_ext = Path(file.filename).suffix or ".mp4"
    video_path = video_dir / f"{video_id}{file_ext}"

    with open(video_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {
        "video_id": video_id,
        "filename": file.filename,
        "file_path": str(video_path),
        "message": "上传成功，请调用 /api/videos/process 开始处理",
    }


@app.get("/api/config")
async def get_config():
    """获取系统配置，包括过滤器选项"""
    from config import ENABLE_MOTION_DETECTION, ENABLE_OBJECT_DETECTION, REQUIRED_OBJECTS, DETECTION_THRESHOLD, SMART_SCAN_MODE
    
    # 预设的完整类别列表 (用于前端显示供用户选择)
    all_available_objects = [
        "person", "car", "bus", "truck", "motorcycle", "bicycle", 
        "dog", "cat", "backpack", "umbrella", "handbag", "suitcase"
    ]
    
    # 如果 REQUIRED_OBJECTS 中有新增的自定义类别，合并到可用列表中
    for obj in REQUIRED_OBJECTS:
        if obj not in all_available_objects:
            all_available_objects.append(obj)

    return {
        "enable_motion_detection": ENABLE_MOTION_DETECTION,
        "enable_object_detection": ENABLE_OBJECT_DETECTION,
        "smart_scan_mode": SMART_SCAN_MODE,
        "required_objects": REQUIRED_OBJECTS,
        "available_objects": all_available_objects,
        "motion_threshold": 0.01  # 默认 1% 的面积变化
    }


@app.post("/api/videos/process")
async def process_video(
    video_path: str,
    video_id: Optional[str] = None,
    resume: bool = True,  # 启用断点续传
    custom_required_objects: Optional[str] = Query(None, description="逗号分隔的所需目标列表"),
    enable_motion_detection: Optional[bool] = Query(None, description="是否启用运动检测"),
    enable_object_detection: Optional[bool] = Query(None, description="是否启用目标检测"),
    motion_threshold: Optional[float] = Query(None, description="运动面积变化阈值 (0-1)"),
):
    """
    处理视频 (分片 + AI 分析 + 向量存储)
    """
    global ai_client, vector_store, video_slicer

    path = Path(video_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="视频文件不存在")
        
    req_objs_list = None
    if custom_required_objects:
        req_objs_list = [obj.strip() for obj in custom_required_objects.split(",") if obj.strip()]

    # 创建任务 ID
    task_id = uuid.uuid4().hex[:12]
    task_status[task_id] = {
        "status": "pending",
        "progress": 0.0,
        "message": "任务已创建，正在初始化...",
        "resume_mode": resume,
        "created_at": time.time(),
        "video_path": str(video_path),
    }

    # 持久化保存
    if persistence:
        persistence.update_task(task_id, task_status[task_id])

    logger.info(f"任务创建: task_id={task_id}, video_path={video_path}, resume={resume}, custom_objects={req_objs_list}, motion={enable_motion_detection}, threshold={motion_threshold}")

    # 清理过期任务
    _cleanup_expired_tasks()

    # 异步处理
    asyncio.create_task(_process_video_task(
        task_id, path, video_id, ai_client, vector_store, video_slicer, resume, req_objs_list,
        enable_motion_detection, enable_object_detection, motion_threshold
    ))

    return {"task_id": task_id, "message": "处理任务已启动", "resume": resume}


async def _process_video_task(
    task_id: str,
    video_path: Path,
    video_id: Optional[str],
    ai_client: ZhipuManager,
    vector_store: VectorStore,
    slicer: VideoSlicer,
    resume: bool = True,
    custom_required_objects: list = None,
    enable_motion_detection: Optional[bool] = None,
    enable_object_detection: Optional[bool] = None,
    motion_threshold: Optional[float] = None,
):
    """视频处理后台任务 (流水线并行版本)"""

    try:
        from config import SMART_SCAN_MODE
        start_time = time.time()
        task_status[task_id]["status"] = "processing"
        
        # 实例化 worker
        worker = VideoWorker(ai_client, vector_store, slicer)
        
        logger.info(f"[{task_id}] 开始处理视频: {video_path}")

        # 获取视频元数据
        video_info = slicer.get_video_info(video_path)
        
        # --- 智能扫描模式逻辑 ---
        if SMART_SCAN_MODE:
            task_status[task_id]["stage"] = "scanning"
            task_status[task_id]["message"] = "智能扫描模式：正在全视频定位目标..."
            
            # 使用 YOLO 快速扫描出目标出现的区间
            targets = custom_required_objects or ["person", "car"]
            events = await worker.scanner.scan_for_events(
                video_path, 
                targets, 
                fps_limit=1.0, 
                status_callback=lambda msg: (task_status[task_id].update({"current_action": msg}))
            )
            
            logger.info(f"[{task_id}] 智能扫描完成，发现 {len(events)} 个关键事件区间")
            task_status[task_id]["total_slices"] = len(events)
            
            if not events:
                task_status[task_id]["status"] = "completed"
                task_status[task_id]["progress"] = 1.0
                task_status[task_id]["message"] = "扫描完毕，全视频未发现指定目标。"
                return

            # 根据事件区间生成 VideoSlice 对象
            slices_to_process = []
            for idx, (start, end) in enumerate(events):
                slice_id = f"{video_id}_event_{idx:03d}"
                output_file = slicer.output_dir / f"{slice_id}.mp4"
                
                # 动态切割事件片段
                await slicer._extract_segment(video_path, start, end, output_file)
                
                slices_to_process.append(VideoSlice(
                    slice_id=slice_id,
                    video_id=video_id,
                    start_time=start,
                    end_time=end,
                    duration=end - start,
                    file_path=output_file
                ))
            
            total_slices = len(slices_to_process)
        else:
            # --- 传统切片模式逻辑 ---
            task_status[task_id]["stage"] = "pipeline"
            task_status[task_id]["message"] = "传统模式：正在启动流水线切片..."
            # (原有逻辑：边切片边分析)
            # 为了保持兼容性，我们先手动获取所有切片
            slices_to_process = list(slicer.slice_video(video_path, video_id))
            total_slices = len(slices_to_process)

        # 后续分析逻辑 (对上面生成的切片进行分析)
        task_status[task_id]["total_slices"] = total_slices
        task_status[task_id]["processed_slices"] = 0
        task_status[task_id]["filtered_slices"] = 0
        task_status[task_id]["stage"] = "analyzing"

        # 分析池并发控制
        analysis_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        analysis_tasks = []

        async def _analyze_and_store(slice_obj):
            async with analysis_semaphore:
                try:
                    def update_status(action_msg):
                        task_status[task_id]["current_action"] = f"[{slice_obj.slice_id}] {action_msg}"
                        task_status[task_id]["_updated"] = time.time()

                    # 在智能模式下，因为已经确定有人，所以不再进行二次 _should_process_slice 过滤
                    # 1. 优先提取视觉向量 (CLIP)，以便立即搜索
                    from config import ENABLE_CLIP_RECALL
                    if ENABLE_CLIP_RECALL:
                        update_status("正在提取视觉向量特征 (CLIP/Recall)...")
                        visual_vector = await worker.extract_visual_features(slice_obj)
                        if visual_vector:
                            slice_obj.embedding = visual_vector
                            # 存入向量库 (此时只有视觉特征，没有文字描述)
                            await vector_store.add_slice(slice_obj)

                    # 2. 调用大模型进行深度特征提取 (精排层)
                    update_status("正在进行大模型深度特征分析 (Rerank)...")
                    
                    analysis_prompt = """你是一个专业的公安图侦与视频分析专家。
请审查提供的画面，极其简练地提取可用于刑侦检索的核心特征。
请直接输出一段高浓度的特征描述（用逗号分隔，不要有任何多余的寒暄和解释词）。

重点关注以下维度：
1. 人物体貌：性别/体型
2. 衣着伪装：上下衣颜色与款式/是否戴帽子头盔口罩
3. 携带物品：背包手提袋
4. 车辆特征：车型颜色
5. 行为轨迹：正常/鬼祟/奔跑

示例输出："男性, 青壮年, 黑上衣, 蓝牛仔裤, 戴白色头盔, 骑行红色两轮电动车" """

                    if SMART_SCAN_MODE:
                        # 智能模式核心：不给大模型看可能包含大量空镜的完整视频
                        # 而是用 YOLO 把有目标的、最清晰的 3 张关键帧喂给它
                        update_status("智能抽帧：提取目标最大最清晰的关键帧...")
                        targets = custom_required_objects or ["person", "car"]
                        keyframes = await worker.scanner.extract_target_keyframes(slice_obj.file_path, targets, max_frames=3)
                        
                        if not keyframes:
                            slice_obj.description = "无显著目标 (已过滤)"
                            slice_obj.metadata["skipped"] = True
                            task_status[task_id]["filtered_slices"] += 1
                        else:
                            update_status("多帧联合分析中...")
                            analysis = await ai_client.analyze_images(
                                image_sources=keyframes,
                                prompt=analysis_prompt,
                            )
                            slice_obj.description = analysis.description
                            
                            # 清理抽帧生成的临时图片
                            for kf in keyframes:
                                if kf.exists(): kf.unlink()
                    else:
                        # 传统模式，喂给整个视频
                        analysis = await ai_client.analyze_video(
                            video_source=slice_obj.file_path,
                            prompt=analysis_prompt,
                        )
                        slice_obj.description = analysis.description
                    
                    # 向量化与存储
                    if slice_obj.description and slice_obj.description not in ["分析失败", "无显著目标 (已过滤)"]:
                        embedding_result = await ai_client.get_embedding(slice_obj.description)
                        slice_obj.embedding = embedding_result.vector
                        await vector_store.add_slice(slice_obj)
                    
                    task_status[task_id]["processed_slices"] += 1
                    task_status[task_id]["progress"] = task_status[task_id]["processed_slices"] / total_slices
                    slicer.cleanup_slice(slice_obj)
                except Exception as e:
                    logger.error(f"分析失败 {slice_obj.slice_id}: {e}")

        # 启动分析
        analysis_tasks = [_analyze_and_store(s) for s in slices_to_process]
        await asyncio.gather(*analysis_tasks)

        # 结束处理
        end_time = time.time()
        total_time = end_time - start_time
        task_status[task_id]["status"] = "completed"
        task_status[task_id]["message"] = f"处理完成！智能发现 {total_slices} 个关键事件，总耗时 {total_time/60:.1f} 分钟"
        
        if persistence:
            persistence.save_all(task_status, video_meta)

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        task_status[task_id]["status"] = "failed"
        task_status[task_id]["message"] = f"处理失败: {str(e)}"
        logger.error(f"[{task_id}] 任务异常: {error_detail}")
        if persistence:
            persistence.update_task(task_id, task_status[task_id])


@app.get("/api/videos/tasks/{task_id}")
async def get_task_status(task_id: str):
    """获取任务状态"""
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="任务不存在")

    return task_status[task_id]


@app.get("/api/videos")
async def list_videos():
    """列出所有已处理的视频"""
    video_ids = await vector_store.list_videos()
    counts = {vid: await vector_store.count_slices(vid) for vid in video_ids}

    return {
        "videos": [
            {"video_id": vid, "slice_count": counts[vid]}
            for vid in video_ids
        ]
    }


@app.get("/api/videos/{video_id}/slices")
async def get_video_slices(video_id: str):
    """获取视频的所有切片信息（含向量数据库详情）"""
    # 获取该视频的所有切片
    slices = await vector_store.get_slices_by_video(video_id)

    if not slices:
        raise HTTPException(status_code=404, detail="视频不存在或未处理")

    return {
        "video_id": video_id,
        "slice_count": len(slices),
        "slices": slices
    }


@app.get("/api/slices")
async def list_all_slices(video_id: Optional[str] = None, limit: int = 100, offset: int = 0):
    """列出所有切片（支持分页和视频过滤）"""
    if video_id:
        slices = await vector_store.get_slices_by_video(video_id)
    else:
        slices = await vector_store.list_all_slices()

    # 分页
    total = len(slices)
    slices = slices[offset:offset + limit]

    return {
        "total": total,
        "count": len(slices),
        "slices": slices
    }


@app.delete("/api/videos/{video_id}")
async def delete_video(video_id: str):
    """删除视频及其所有切片"""
    await vector_store.delete_video(video_id)
    return {"message": f"视频 {video_id} 已删除"}


# ========== 直接匹配 API (新增功能) ==========

@app.post("/api/direct-match")
async def direct_match(request: DirectMatchRequest):
    """
    直接匹配模式：视频切片 + query 一起发给大模型判断

    适用场景：公安精确查找，如"找偷电瓶的人"

    流程：
    1. 遍历所有视频，分片
    2. 每个切片 + query 发给 GLM-4.6V 判断是否匹配
    3. 返回匹配结果（按置信度排序）
    4. 可选存储到向量库
    """
    global direct_matcher

    if not direct_matcher:
        raise HTTPException(status_code=500, detail="服务未初始化")

    # 验证视频文件存在
    valid_paths = []
    for path in request.video_paths:
        if Path(path).exists():
            valid_paths.append(path)
        else:
            logger.warning(f"视频文件不存在: {path}")

    if not valid_paths:
        raise HTTPException(status_code=400, detail="没有有效的视频文件")

    # 执行匹配
    results = await direct_matcher.match_videos(
        video_paths=valid_paths,
        query=request.query,
        top_k=request.top_k,
        store_results=request.store_results,
    )

    return {
        "query": request.query,
        "total_videos": len(valid_paths),
        "count": len(results),
        "results": [
            {
                "slice_id": r.slice_id,
                "video_id": r.video_id,
                "start_time": r.start_time,
                "end_time": r.end_time,
                "is_matched": r.is_matched,
                "confidence": r.confidence,
                "reason": r.reason,
                "description": r.description,
            }
            for r in results
        ]
    }


@app.post("/api/direct-match/upload")
async def direct_match_upload(
    files: list[UploadFile] = File(...),
    query: str = Query(..., description="查询描述"),
    top_k: int = Query(10, description="返回结果数量"),
    store_results: bool = Query(True, description="是否存储到向量库"),
):
    """
    直接匹配模式（上传文件版本）

    支持批量上传视频文件进行直接匹配
    """
    global direct_matcher

    if not direct_matcher:
        raise HTTPException(status_code=500, detail="服务未初始化")

    # 保存上传的文件
    video_dir = Path(TEMP_DIR) / "direct_match"
    video_dir.mkdir(parents=True, exist_ok=True)

    video_paths = []
    for file in files:
        file_ext = Path(file.filename).suffix or ".mp4"
        temp_path = video_dir / f"{uuid.uuid4().hex[:12]}{file_ext}"

        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        video_paths.append(str(temp_path))
        logger.info(f"已保存上传文件: {temp_path}")

    # 执行匹配
    results = await direct_matcher.match_videos(
        video_paths=video_paths,
        query=query,
        top_k=top_k,
        store_results=store_results,
    )

    return {
        "query": query,
        "total_videos": len(video_paths),
        "count": len(results),
        "results": [
            {
                "slice_id": r.slice_id,
                "video_id": r.video_id,
                "start_time": r.start_time,
                "end_time": r.end_time,
                "is_matched": r.is_matched,
                "confidence": r.confidence,
                "reason": r.reason,
                "description": r.description,
            }
            for r in results
        ]
    }


@app.post("/api/direct-match/async")
async def direct_match_async(request: DirectMatchRequest):
    """
    直接匹配模式（异步版本）

    返回任务 ID，通过 /api/videos/tasks/{task_id} 查询进度
    """
    global direct_matcher

    if not direct_matcher:
        raise HTTPException(status_code=500, detail="服务未初始化")

    # 验证视频文件存在
    valid_paths = []
    for path in request.video_paths:
        if Path(path).exists():
            valid_paths.append(path)

    if not valid_paths:
        raise HTTPException(status_code=400, detail="没有有效的视频文件")

    # 创建任务
    task_id = uuid.uuid4().hex[:12]
    task_status[task_id] = {
        "status": "pending",
        "progress": 0.0,
        "message": "任务已创建，正在初始化...",
        "created_at": time.time(),
        "query": request.query,
        "video_count": len(valid_paths),
        "type": "direct_match",
    }

    # 持久化保存
    if persistence:
        persistence.update_task(task_id, task_status[task_id])

    # 异步执行
    asyncio.create_task(_direct_match_task(
        task_id, valid_paths, request.query, request.top_k, request.store_results
    ))

    return {"task_id": task_id, "message": "直接匹配任务已启动"}


async def _direct_match_task(
    task_id: str,
    video_paths: list[str],
    query: str,
    top_k: int,
    store_results: bool,
):
    """直接匹配后台任务"""
    global direct_matcher

    try:
        task_status[task_id]["status"] = "processing"
        task_status[task_id]["message"] = "正在分析视频..."

        def progress_callback(current, total, message):
            task_status[task_id]["progress"] = current / total if total > 0 else 0
            task_status[task_id]["message"] = message

        results = await direct_matcher.match_videos(
            video_paths=video_paths,
            query=query,
            top_k=top_k,
            store_results=store_results,
            progress_callback=progress_callback,
        )

        task_status[task_id]["status"] = "completed"
        task_status[task_id]["progress"] = 1.0
        task_status[task_id]["message"] = f"匹配完成，找到 {len(results)} 个结果"
        task_status[task_id]["result"] = {
            "query": query,
            "count": len(results),
            "results": [
                {
                    "slice_id": r.slice_id,
                    "video_id": r.video_id,
                    "start_time": r.start_time,
                    "end_time": r.end_time,
                    "confidence": r.confidence,
                    "reason": r.reason,
                    "description": r.description,
                }
                for r in results
            ]
        }

        if persistence:
            persistence.update_task(task_id, task_status[task_id])

        logger.info(f"[{task_id}] 直接匹配完成，找到 {len(results)} 个结果")

    except Exception as e:
        import traceback
        task_status[task_id]["status"] = "failed"
        task_status[task_id]["message"] = f"匹配失败: {str(e)}"
        logger.error(f"[{task_id}] 直接匹配失败: {traceback.format_exc()}")
        if persistence:
            persistence.update_task(task_id, task_status[task_id])


# 搜索接口
@app.post("/api/search")
async def search(request: SearchRequest):
    """
    语义搜索视频片段

    流程:
    1. glm-4 解析查询
    2. embedding-3 生成向量
    3. 向量库检索
    4. glm-4.6v 视觉核实 (Top-N)
    """
    results = await search_engine.search(
        query_text=request.query,
        top_k=request.top_k,
        verify_top_n=request.verify_top_n,
        video_id=request.video_id,
    )

    return {
        "query": request.query,
        "count": len(results),
        "results": [
            {
                "slice_id": r.slice_id,
                "video_id": r.video_id,
                "start_time": r.start_time,
                "end_time": r.end_time,
                "description": r.description,
                "similarity": r.similarity,
                "visual_verification": r.visual_verification,
            }
            for r in results
        ]
    }


@app.post("/api/search/features")
async def search_by_features(request: FeatureSearchRequest):
    """直接使用特征列表搜索"""
    results = await search_engine.search_by_features(
        features=request.features,
        top_k=request.top_k,
        video_id=request.video_id,
    )

    return {
        "features": request.features,
        "count": len(results),
        "results": [
            {
                "slice_id": r.slice_id,
                "video_id": r.video_id,
                "start_time": r.start_time,
                "end_time": r.end_time,
                "description": r.description,
                "similarity": r.similarity,
            }
            for r in results
        ]
    }


# 分析接口
@app.post("/api/analyze")
async def analyze_slice(request: AnalyzeRequest):
    """
    对特定片段进行深度嫌疑分析
    """
    analysis = await search_engine.analyze_suspect(
        slice_id=request.slice_id,
        focus_features=request.focus_features,
    )
    return analysis


# 切片管理
@app.get("/api/slices/{slice_id}")
async def get_slice(slice_id: str):
    """获取切片详情"""
    slice_info = await vector_store.get_slice(slice_id)
    if not slice_info:
        raise HTTPException(status_code=404, detail="切片不存在")
    return slice_info


# 视频流服务
@app.get("/api/stream/{video_id}")
async def stream_video(
    video_id: str,
    start: float = Query(0, description="开始时间 (秒)"),
    end: Optional[float] = Query(None, description="结束时间 (秒)"),
):
    """
    流式播放视频片段

    支持通过 start/end 参数定位到特定时间段
    """
    # 查找视频文件
    video_dir = Path(TEMP_DIR) / "videos"
    video_files = list(video_dir.glob(f"{video_id}.*"))

    if not video_files:
        raise HTTPException(status_code=404, detail="视频不存在")

    video_path = video_files[0]

    # 如果指定了时间范围，切割视频片段
    if start > 0 or end:
        from services.video_worker import VideoSlicer
        slicer = VideoSlicer()

        end = end or (start + 10)  # 默认 10 秒
        output_path = Path(TEMP_DIR) / "streams" / f"{video_id}_{start}_{end}.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 检查是否已有缓存的片段
        if output_path.exists():
            return FileResponse(output_path, media_type="video/mp4")

        # 异步提取片段
        await slicer._extract_segment(video_path, start, end, output_path)

        if output_path.exists():
            return FileResponse(output_path, media_type="video/mp4")
        else:
            raise HTTPException(status_code=500, detail="视频片段提取失败")

    return FileResponse(video_path, media_type="video/mp4")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT)