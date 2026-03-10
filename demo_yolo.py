import cv2
from ultralytics import YOLO
import sys

def run_yolo_demo(video_path):
    print("正在加载 YOLOv8n 基模 (如果本地没有会自动下载)...")
    model = YOLO("yolov8n.pt")  # 加载预训练的轻量级模型
    
    print(f"开始分析视频: {video_path}")
    
    # 我们只抽取几帧来模拟系统的“抽帧分析”过程
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"无法打开视频文件: {video_path}")
        return
        
    frame_count = 0
    detected_classes = set()
    
    while cap.isOpened() and frame_count < 30: # 抽前30帧测试
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_count += 1
        
        # 每 10 帧检测一次
        if frame_count % 10 == 0:
            print(f"\n--- 正在分析第 {frame_count} 帧 ---")
            
            # 运行推理
            results = model.predict(frame, verbose=False)
            
            # 解析结果
            for r in results:
                # 获取检测到的类别索引
                classes = r.boxes.cls.cpu().numpy()
                names = r.names
                
                frame_labels = set([names[int(c)] for c in classes])
                detected_classes.update(frame_labels)
                
                print(f"本帧检测到的目标: {', '.join(frame_labels) if frame_labels else '无'}")
                
    cap.release()
    print("\n------------------------------")
    print(f"Demo 运行完毕。")
    print(f"在这个视频片段中，YOLO 累计发现了以下目标类型: {', '.join(detected_classes) if detected_classes else '无'}")

if __name__ == "__main__":
    test_video = "traffic.mp4"
    run_yolo_demo(test_video)
