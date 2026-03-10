import sys
import os
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# 将 backend 目录加入路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.video_worker import VideoWorker, VideoSlice, MotionDetector
import config

async def test_filtering_logic():
    print("--- 开始智能过滤架构测试 ---")
    
    # 准备 Mock 对象
    mock_ai = AsyncMock()
    mock_ai.analyze_video.return_value = MagicMock(description="Mock Description", actions=[], objects=[])
    mock_ai.get_embedding.return_value = MagicMock(vector=[0.1]*2048, dimension=2048)
    
    mock_store = AsyncMock()
    
    worker = VideoWorker(mock_ai, mock_store)
    
    # 模拟一个视频切片 (指向项目根目录的 traffic.mp4)
    video_path = Path(__file__).parent.parent.parent / "traffic.mp4"
    if not video_path.exists():
        print(f"警告: 测试视频 {video_path} 不存在，将跳过部分测试。")
        return

    test_slice = VideoSlice(
        slice_id="test_001",
        video_id="video_test",
        start_time=0,
        end_time=5,
        duration=5,
        file_path=video_path
    )

    # 场景 1: 默认全量模式 (ENABLE_MOTION_DETECTION = False)
    config.ENABLE_MOTION_DETECTION = False
    config.ENABLE_OBJECT_DETECTION = False
    print("\n测试场景 1: 默认全量模式 (预期：不进行运动检测，直接调用 AI)")
    
    should_process = await worker._should_process_slice(test_slice)
    print(f"是否应处理: {should_process}")
    assert should_process is True, "场景1 失败: 默认全量模式应该返回 True"

    # 场景 2: 开启运动检测模式
    config.ENABLE_MOTION_DETECTION = True
    print("\n测试场景 2: 开启运动检测模式 (预期：调用 MotionDetector)")
    
    # 这里我们直接测试 MotionDetector 
    has_motion = worker.motion_detector.has_motion(test_slice.file_path)
    print(f"MotionDetector 检测结果 (是否有运动): {has_motion}")
    
    should_process_v2 = await worker._should_process_slice(test_slice)
    print(f"开启过滤后，是否应处理: {should_process_v2}")
    
    # 场景 3: 测试 process_video 流程中的计数
    print("\n测试场景 3: 模拟处理流程，验证分析调用次数")
    mock_ai.analyze_video.reset_mock()
    
    # 强制让过滤生效 (模拟无运动场景)
    worker.motion_detector.has_motion = MagicMock(return_value=False)
    
    # 运行 process_video (只测核心逻辑部分)
    # 我们直接模拟 process_single_slice 的逻辑
    async def run_simulated_process():
        if await worker._should_process_slice(test_slice):
            await mock_ai.analyze_video(video_source=test_slice.file_path, prompt="...")
            return "Processed"
        else:
            return "Skipped"

    result = await run_simulated_process()
    print(f"模拟处理结果: {result}")
    print(f"AI 调用次数: {mock_ai.analyze_video.call_count}")
    
    assert result == "Skipped", "场景3 失败: 应该跳过处理"
    assert mock_ai.analyze_video.call_count == 0, "场景3 失败: 不应该调用 AI"

    print("\n--- 所有逻辑测试通过！ ---")

if __name__ == "__main__":
    asyncio.run(test_filtering_logic())
