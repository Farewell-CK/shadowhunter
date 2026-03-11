import asyncio
import httpx
import time
from pathlib import Path
import json

API_BASE = "http://localhost:8000/api"
TEST_VIDEO = "/root/workspace/zp/ShadowHunter_qwen/NVR_ch14_main_20251220000000_20251220010006.mp4"

async def test_video_processing_pipeline():
    print("=== 开始端到端视频处理测试 ===")
    
    if not Path(TEST_VIDEO).exists():
        print(f"错误: 找不到测试视频 {TEST_VIDEO}")
        return

    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. 获取配置
        print("\n[1] 获取系统配置...")
        res = await client.get(f"{API_BASE}/config")
        config = res.json()
        print(f"当前配置: 运动检测={config['enable_motion_detection']}, 目标检测={config['enable_object_detection']}")
        
        # 2. 模拟上传并触发处理
        print("\n[2] 触发视频处理任务...")
        # 为了测试效果，我们只放行包含 'person' 的片段，看看过滤率
        params = {
            "video_path": TEST_VIDEO,
            "video_id": "test_smart_scan_" + str(int(time.time())),
            "custom_required_objects": "person",
            "enable_motion_detection": True,
            "enable_object_detection": True,
            "smart_scan_mode": True
        }
        res = await client.post(f"{API_BASE}/videos/process", params=params)
        
        if res.status_code != 200:
            print(f"任务创建失败: {res.text}")
            return
            
        task_data = res.json()
        task_id = task_data["task_id"]
        print(f"任务创建成功，Task ID: {task_id}")
        
        # 3. 轮询状态并打印明细日志
        print("\n[3] 轮询任务进度日志 (每 5 秒)...")
        for i in range(100):
            res = await client.get(f"{API_BASE}/videos/tasks/{task_id}")
            if res.status_code != 200:
                print("获取状态失败")
                break
                
            status = res.json()
            
            # 打印高度结构化的监控面板
            print(f"[{time.strftime('%H:%M:%S')}] 状态: {status['status']} | 总体进度: {status.get('progress', 0)*100:.1f}%")
            print(f"  > 宏观消息: {status.get('message', '')}")
            
            if 'current_action' in status:
                print(f"  > 细粒度动作: {status['current_action']}")
                
            if 'total_slices' in status:
                processed = status.get('processed_slices', 0)
                filtered = status.get('filtered_slices', 0)
                print(f"  > 数据漏斗: 总量 {status['total_slices']} | 已处理(入库) {processed} | 被过滤(拦截) {filtered}")
                if 'filtered_by_opencv' in status:
                    print(f"      - OpenCV 拦截: {status.get('filtered_by_opencv', 0)}")
                if 'filtered_by_yolo' in status:
                    print(f"      - YOLO 拦截: {status.get('filtered_by_yolo', 0)}")
                    
                # 如果已经开始有实质性进展，就不必等全完了
                if processed > 0 or filtered > 0:
                    if i > 5 and (processed + filtered) > 10:
                        print("\n[成功] 已经观察到系统正在处理和过滤数据！为了节省时间，提前结束日志观察。")
                        break
            
            print("-" * 50)
            
            if status['status'] in ['completed', 'failed']:
                break
                
            await asyncio.sleep(5)

        print("\n=== 观察结束。任务仍在后台运行中... ===")

if __name__ == "__main__":
    asyncio.run(test_video_processing_pipeline())
