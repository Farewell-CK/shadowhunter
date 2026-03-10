"""
阶段三测试：验证智能查询与视觉核验
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.vector_store import InMemoryVectorStore
from services.search_engine import SearchEngine
from ai_client import create_client


async def setup_test_data(store):
    """创建测试数据"""
    import random
    random.seed(42)

    class MockSlice:
        def __init__(self, slice_id, video_id, start, end, desc, emb):
            self.slice_id = slice_id
            self.video_id = video_id
            self.start_time = start
            self.end_time = end
            self.duration = end - start
            self.description = desc
            self.embedding = emb
            self.metadata = {"resolution": "1920x1080", "original_file": "test.mp4"}

    test_descriptions = [
        "视频中有一个穿着绿色上衣的男子骑着黑色电动车，他戴着白色头盔，正在路口等待红灯。",
        "画面中显示一辆白色小轿车正在道路上行驶，车内有两个人。",
        "一个穿红色外套的女子正在步行道上行走，她手里拿着手机在看。",
        "摩托车骑手穿着黑色皮衣，戴着墨镜，正在高速公路上行驶。",
        "视频片段显示一个人骑着共享单车穿过人行横道。",
    ]

    for i, desc in enumerate(test_descriptions):
        # 模拟向量
        embedding = [random.gauss(0, 1) for _ in range(1024)]
        slice_obj = MockSlice(
            slice_id=f"test_slice_{i:03d}",
            video_id="test_video_001",
            start=i * 8,
            end=(i + 1) * 8,
            desc=desc,
            emb=embedding,
        )
        await store.add_slice(slice_obj)
        print(f"添加测试数据: {slice_obj.slice_id}")


async def test_query_parsing():
    """测试查询解析"""
    print("\n=== 测试查询解析 ===")

    client = await create_client()
    store = InMemoryVectorStore()
    engine = SearchEngine(client, store)

    test_queries = [
        "找一个骑电动车、戴白色头盔、穿绿色上衣的人",
        "搜索穿红色衣服的行人",
        "查找白色轿车的画面",
    ]

    for query in test_queries:
        parsed = await engine._parse_query(query)
        print(f"\n查询: {query}")
        print(f"  特征: {parsed.features}")
        print(f"  过滤: {parsed.filters}")


async def test_semantic_search():
    """测试语义搜索"""
    print("\n=== 测试语义搜索 ===")

    client = await create_client()
    store = InMemoryVectorStore()
    await setup_test_data(store)

    engine = SearchEngine(client, store)

    query = "骑电动车戴白色头盔的人"
    print(f"\n搜索查询: {query}")

    results = await engine.search(
        query_text=query,
        top_k=3,
        verify_top_n=0,  # 暂不进行视觉核实
    )

    print(f"找到 {len(results)} 个结果:")
    for r in results:
        print(f"\n  [{r.slice_id}] 相似度: {r.similarity:.4f}")
        print(f"  时间: {r.start_time:.1f}s - {r.end_time:.1f}s")
        print(f"  描述: {r.description[:80]}...")


async def test_visual_verification():
    """测试视觉核实"""
    print("\n=== 测试视觉核实 ===")

    client = await create_client()
    store = InMemoryVectorStore()
    await setup_test_data(store)

    engine = SearchEngine(client, store)

    query = "骑电动车戴白色头盔穿绿色上衣"
    print(f"\n搜索并核实: {query}")

    results = await engine.search(
        query_text=query,
        top_k=3,
        verify_top_n=2,  # 对 Top 2 进行视觉核实
    )

    print(f"\n搜索结果 (含视觉核实):")
    for r in results:
        print(f"\n  [{r.slice_id}] 相似度: {r.similarity:.4f}")
        print(f"  时间: {r.start_time:.1f}s - {r.end_time:.1f}s")
        if r.visual_verification:
            print(f"  核实报告: {r.visual_verification[:200]}...")


async def test_feature_search():
    """测试特征搜索"""
    print("\n=== 测试特征搜索 ===")

    client = await create_client()
    store = InMemoryVectorStore()
    await setup_test_data(store)

    engine = SearchEngine(client, store)

    features = ["电动车", "白色头盔", "绿色上衣"]
    print(f"\n特征搜索: {features}")

    results = await engine.search_by_features(features=features, top_k=3)

    print(f"找到 {len(results)} 个结果:")
    for r in results:
        print(f"  {r.slice_id}: 相似度={r.similarity:.4f}")


async def test_suspect_analysis():
    """测试嫌疑分析"""
    print("\n=== 测试嫌疑分析 ===")

    client = await create_client()
    store = InMemoryVectorStore()
    await setup_test_data(store)

    engine = SearchEngine(client, store)

    # 分析第一个切片
    analysis = await engine.analyze_suspect(
        slice_id="test_slice_000",
        focus_features=["电动车", "白色头盔", "绿色上衣"],
    )

    print(f"\n嫌疑分析报告:")
    print(f"  切片: {analysis.get('slice_id')}")
    print(f"  分析: {analysis.get('analysis', 'N/A')[:300]}...")


async def main():
    print("=" * 50)
    print("ShadowHunter 阶段三测试")
    print("=" * 50)

    try:
        # 测试 1: 查询解析
        await test_query_parsing()

        # 测试 2: 语义搜索
        await test_semantic_search()

        # 测试 3: 特征搜索
        await test_feature_search()

        # 测试 4: 视觉核实
        await test_visual_verification()

        # 测试 5: 嫌疑分析
        await test_suspect_analysis()

    except ValueError as e:
        print(f"\n配置错误: {e}")
        print("请在 backend/config.py 中设置 ZHIPU_API_KEY")
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    asyncio.run(main())