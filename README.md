# 猎影 (ShadowHunter) - 视频语义检索系统

基于智谱 AI 的全栈视频语义检索系统，专为视频侦查设计。

## 核心特性 (针对公安实战优化)

- **智能事件扫描**: 采用先扫描再切片的策略。利用 YOLO 模型快速定位目标出现区间并进行智能聚类，彻底解决固定切片导致的冗余问题。
- **三级级联过滤**: 
    1. **OpenCV 运动检测**: 毫秒级剔除 100% 静止的无效画面。
    2. **Local YOLO 初筛**: 精准拦截无目标（人/车）的画面，算力资源利用率提升 10 倍。
    3. **GLM-4.6V 深度理解**: 对高价值片段提取图侦级结构化特征。
- **语义提纯向量化**: 强制 AI 输出高浓度实词组合，极大提升复杂案情描述下的检索确凿性。
- **超大视频流式处理**: 针对 GB 级长监控视频，支持流式分块分析与断点续传。

## 功能特性

- **智能分片**: 8秒黄金窗口，5秒步长重叠分片，确保动作完整性
- **视觉理解**: GLM-4.6V 视频分析，精准识别人物、车辆、行为
- **语义检索**: 自然语言搜索，秒级定位目标视频片段
- **视觉核实**: Top-N 结果二次核验，生成专业分析报告

## 快速开始

### 1. 配置 API Key

编辑 `backend/config.py`，设置智谱 API Key：

```python
ZHIPU_API_KEY = "your_api_key_here"
```

### 2. 启动服务

**Linux/macOS:**
```bash
chmod +x start.sh
./start.sh --install
```

**Windows:**
```cmd
start_windows.bat
```

### 3. 访问系统

- 前端界面: http://localhost:3000
- API 文档: http://localhost:8000/docs

## 项目结构

```
ShadowHunter_qwen/
├── backend/                 # 后端服务 (Python/FastAPI)
│   ├── config.py           # 配置文件
│   ├── ai_client.py        # 智谱 AI 客户端
│   ├── main.py             # FastAPI 主服务
│   └── services/           # 核心服务
│       ├── video_worker.py # 视频分片
│       ├── vector_store.py # 向量存储
│       └── search_engine.py# 搜索引擎
│
├── frontend/               # 前端服务 (React/Vite)
│   └── src/
│       ├── components/     # 组件
│       ├── pages/          # 页面
│       └── services/       # API 服务
│
├── start.sh               # Linux/macOS 启动脚本
├── start_windows.bat      # Windows 启动脚本
└── README.md
```

## 使用流程

1. **上传视频**: 支持长视频上传（如 20 小时监控）
2. **自动处理**: 系统自动分片、AI 分析、向量存储
3. **语义搜索**: 输入自然语言描述，如"骑电动车戴白色头盔的人"
4. **精准定位**: 系统返回 5-10 秒视频切片及分析报告

## API 接口

| 接口 | 方法 | 描述 |
|------|------|------|
| `/api/videos/upload` | POST | 上传视频 |
| `/api/videos/process` | POST | 处理视频 |
| `/api/search` | POST | 语义搜索 |
| `/api/analyze` | POST | 深度分析 |

完整 API 文档: http://localhost:8000/docs

## 开发依赖

**后端:**
- Python 3.8+
- FastAPI
- OpenAI SDK (智谱兼容)
- ChromaDB

**前端:**
- Node.js 18+
- React 18
- Vite
- TailwindCSS

## 技术架构

```
用户查询 → GLM-4 (特征提取) → Embedding-3 (向量化)
    ↓
向量检索 (ChromaDB) → Top-K 结果
    ↓
GLM-4.6V (视觉核实) → 分析报告 + 视频片段
```

## 分片策略

采用动态重叠分片策略：

- **片段时长**: 8-10 秒（动作理解黄金窗口）
- **步长**: 5 秒（50% 重叠）
- **条件触发**: 运动侦测，静止画面稀疏采样

## 许可证

MIT License