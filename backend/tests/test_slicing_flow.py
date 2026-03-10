"""
阶段二测试：验证视频分片与存储流程
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.video_worker import VideoSlicer, VideoSlice
from services.vector_store import InMemoryVectorStore
from ai_client import create_client


async def test_video_slicing():
    """测试视频分片逻辑"""
    print("\n=== 测试视频分片 ===")

    slicer = VideoSlicer()

    # 测试分片计算
    duration = 60.0  # 60 秒视频
    slices = slicer.calculate_slices(duration, slice_duration=8, stride=5)

    print(f"视频时长: {duration}s")
    print(f"分片参数: 片段=8s, 步长=5s (重叠=3s)")
    print(f"生成片段数: {len(slices)}")

    for i, (start, end) in enumerate(slices):
        print(f"  片段 {i+1}: {start:.1f}s - {end:.1f}s (时长: {end-start:.1f}s)")

    return slices


async def test_vector_store():
    """测试向量存储"""
    print("\n=== 测试向量存储 (内存模式) ===")

    store = InMemoryVectorStore()

    # 模拟切片对象
    class MockSlice:
        def __init__(self, slice_id, video_id, start, end, desc, emb):
            self.slice_id = slice_id
            self.video_id = video_id
            self.start_time = start
            self.end_time = end
            self.duration = end - start
            self.description = desc
            self.embedding = emb
            self.metadata = {"resolution": "1920x1080"}

    # 添加测试数据
    import random
    random.seed(42)

    for i in range(5):
        # 模拟向量 (1024 维)
        embedding = [random.gauss(0, 1) for _ in range(1024)]
        slice_obj = MockSlice(
            slice_id=f"test_{i:03d}",
            video_id="test_video",
            start=i * 8,
            end=(i + 1) * 8,
            desc=f"第 {i+1} 个测试片段",
            emb=embedding,
        )
        await store.add_slice(slice_obj)

    count = await store.count_slices()
    print(f"已存储 {count} 个切片")

    # 测试搜索
    query_embedding = [random.gauss(0, 1) for _ in range(1024)]
    results = await store.search(query_embedding, n_results=3)

    print(f"\n搜索结果 (Top 3):")
    for r in results:
        print(f"  {r['slice_id']}: 相似度={r['similarity']:.4f}")

    return store


async def test_slicing_flow(video_path: str = None):
    """
    测试完整的分片流程

    需要 API Key 和测试视频
    """
    print("\n=== 测试完整分片流程 ===")

    video_path = video_path or sys.argv[1] if len(sys.argv) > 1 else None
    if not video_path:
        print("提示: 请提供视频文件路径作为参数")
        print("用法: python test_slicing_flow.py <video_path>")
        return

    path = Path(video_path)
    if not path.exists():
        print(f"错误: 文件不存在 - {video_path}")
        return

    print(f"处理视频: {path}")

    # 初始化组件
    client = await create_client()
    store = InMemoryVectorStore()
    slicer = VideoSlicer()

    from services.video_worker import VideoWorker
    worker = VideoWorker(client, store, slicer)

    # 处理视频
    def progress(current, total, slice_obj):
        print(f"  进度: {current}/{total} - {slice_obj.time_range}")

    slices = await worker.process_video(path, progress_callback=progress)

    print(f"\n处理完成:")
    print(f"  总片段数: {len(slices)}")
    for s in slices[:3]:
        print(f"  {s.slice_id}: {s.time_range}")
        print(f"    描述: {s.description[:100] if s.description else 'N/A'}...")

    # 测试搜索
    print("\n测试搜索...")
    query = "骑电动车的人"
    embedding = await client.get_embedding(query)
    results = await store.search(embedding.vector, n_results=3)

    print(f"查询: '{query}'")
    for r in results:
        print(f"  {r['slice_id']}: 相似度={r['similarity']:.4f}")


async def main():
    print("=" * 50)
    print("ShadowHunter 阶段二测试")
    print("=" * 50)

    # 测试 1: 分片逻辑
    await test_video_slicing()

    # 测试 2: 向量存储
    await test_vector_store()

    # 测试 3: 完整流程 (需要视频文件)
    try:
        await test_slicing_flow()
    except ValueError as e:
        print(f"\n跳过完整流程测试: {e}")
    except Exception as e:
        print(f"\n完整流程测试失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    asyncio.run(main())