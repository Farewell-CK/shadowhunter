"""
阶段一测试：验证智谱 AI 视频输入功能
测试 glm-4.6v 对视频片段的识别能力
"""

import asyncio
import sys
from pathlib import Path

# 添加后端目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_client import ZhipuManager, create_client


async def test_text_chat():
    """测试文本对话功能"""
    print("\n=== 测试文本对话 (glm-4) ===")

    client = await create_client()

    # 测试查询解析
    response = await client.chat(
        message="从以下描述中提取视觉特征：一个骑电动车、戴白色头盔、穿绿色上衣的人",
        system_prompt="你是一个专业的视觉特征提取助手，请从文本中提取关键视觉特征。",
    )

    print(f"查询解析结果: {response}")
    return response


async def test_video_analysis(video_path: str = None):
    """
    测试视频分析功能

    Args:
        video_path: 测试视频路径，如未提供则使用默认测试视频
    """
    print("\n=== 测试视频分析 (glm-4.6v) ===")

    client = await create_client()

    if video_path:
        path = Path(video_path)
        if not path.exists():
            print(f"错误: 视频文件不存在 - {video_path}")
            return None
    else:
        # 检查默认测试视频
        default_path = Path(__file__).parent.parent.parent / "assets" / "test_videos" / "test_riding.mp4"
        if not default_path.exists():
            print(f"提示: 未找到测试视频，请提供视频路径")
            print(f"预期路径: {default_path}")
            return None
        path = default_path

    print(f"分析视频: {path}")

    # 分析视频
    result = await client.analyze_video(
        video_source=path,
        prompt="""请详细分析这个视频片段，回答以下问题：
1. 视频中有哪些人物？他们的穿着特征是什么？
2. 人物在进行什么动作？
3. 有哪些交通工具或物品？
4. 请用一句话概括视频内容。""",
    )

    print(f"\n分析结果:")
    print(f"  描述: {result.description[:200]}...")
    print(f"  检测到的动作: {result.actions}")
    print(f"  检测到的对象: {result.objects}")
    print(f"  置信度: {result.confidence}")

    return result


async def test_embedding():
    """测试向量生成功能"""
    print("\n=== 测试向量生成 (embedding-3) ===")

    client = await create_client()

    text = "一个骑电动车的人戴着白色头盔，穿着绿色上衣"
    result = await client.get_embedding(text)

    print(f"向量维度: {result.dimension}")
    print(f"向量前 10 个值: {result.vector[:10]}")

    return result


async def test_concurrent_requests():
    """测试并发控制 (验证 QPS=3 限制)"""
    print("\n=== 测试并发控制 ===")

    client = await create_client()

    # 发送 5 个并发请求
    tasks = [
        client.chat(f"请说一句话，包含数字 {i}")
        for i in range(5)
    ]

    import time
    start_time = time.time()
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start_time

    print(f"发送 5 个请求，总耗时: {elapsed:.2f}秒")
    print(f"预期最小耗时: 约 2 秒 (5 请求 / 3 QPS ≈ 1.67秒)")

    for i, result in enumerate(results):
        print(f"  请求 {i}: {result[:50]}...")

    return results


async def main():
    """主测试流程"""
    print("=" * 50)
    print("ShadowHunter 阶段一测试")
    print("=" * 50)

    try:
        # 测试 1: 文本对话
        await test_text_chat()

        # 测试 2: 向量生成
        await test_embedding()

        # 测试 3: 视频分析 (需要测试视频)
        video_path = sys.argv[1] if len(sys.argv) > 1 else None
        await test_video_analysis(video_path)

        # 测试 4: 并发控制
        await test_concurrent_requests()

        print("\n=== 测试完成 ===")

    except ValueError as e:
        print(f"\n配置错误: {e}")
        print("请在 backend/config.py 中设置 ZHIPU_API_KEY")
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())