# ShadowHunter (猎影) - Project Documentation

## Project Overview
ShadowHunter is a full-stack video semantic search system specifically designed for video investigation and surveillance analysis. It leverages advanced AI models from Zhipu AI (GLM-4, GLM-4.6V, and Embedding-3) to provide deep visual understanding and natural language search capabilities over large-scale video data.

### Key Features
- **Intelligent Slicing**: Dynamic video segmentation (8s fragments with 50% overlap) to maintain action continuity.
- **Semantic Search**: Natural language querying (e.g., "person in a white helmet on a black electric bike").
- **Visual Verification**: Secondary AI verification of top search results for high precision.
- **Deep Analysis**: Suspect behavior analysis and detailed reporting.

### Tech Stack
- **Backend**: Python 3.8+, FastAPI, Zhipu AI SDK, ChromaDB (Vector Store), FFmpeg (Video Processing).
- **Frontend**: React 18, Vite, TailwindCSS, Lucide React (Icons).
- **AI Models**: 
  - `glm-5`: Query parsing and feature extraction.
  - `glm-4.6v`: Video analysis and visual verification.
  - `embedding-3`: Vector generation for semantic search.

---

## Directory Structure
```
ShadowHunter_qwen/
├── backend/                # FastAPI backend service
│   ├── config.py           # Central configuration (API keys, model selection)
│   ├── main.py             # FastAPI entry point and API routes
│   ├── ai_client.py        # Zhipu AI integration manager
│   ├── services/           # Core business logic
│   │   ├── video_worker.py # Slicing and AI analysis orchestration
│   │   ├── search_engine.py# Semantic search and verification logic
│   │   ├── vector_store.py # ChromaDB integration
│   │   └── persistence.py  # Task and metadata persistence
│   └── data/               # Persistent storage (SQLite, ChromaDB files)
├── frontend/               # React frontend service
│   ├── src/
│   │   ├── pages/          # Application views (Upload, Search, Analytics)
│   │   ├── components/     # UI components
│   │   └── services/       # Frontend API clients
│   └── package.json        # Frontend dependencies and scripts
├── start.sh                # Linux/macOS orchestration script
├── start_windows.bat       # Windows orchestration script
└── README.md               # User-facing documentation
```

---

## Building and Running

### Prerequisites
- Python 3.8+
- Node.js 18+
- FFmpeg (installed and available in PATH)

### Quick Start (Recommended)
**Linux/macOS:**
```bash
chmod +x start.sh
./start.sh --install
```

**Windows:**
```cmd
start_windows.bat
```

### Manual Setup
**Backend:**
1. Navigate to `backend/`.
2. Install dependencies: `pip install -r requirements.txt`.
3. Configure `ZHIPU_API_KEY` in `config.py`.
4. Run: `python main.py` (Default: http://localhost:8000).

**Frontend:**
1. Navigate to `frontend/`.
2. Install dependencies: `npm install`.
3. Run: `npm run dev` (Default: http://localhost:3000).

---

## Core Workflows

### 1. Video Processing Pipeline
- **Upload**: Video is saved to `backend/temp/slices/videos`.
- **Slicing**: FFmpeg cuts video into 8-second slices with a 5-second stride.
- **Analysis**: Each slice is processed by `glm-4.6v` for visual description.
- **Vectorization**: Descriptions are converted to 2048-dimensional vectors via `embedding-3`.
- **Storage**: Vectors and metadata are stored in ChromaDB.

### 2. Search Pipeline
- **Query Parsing**: `glm-5` extracts visual features from the user's natural language query.
- **Vector Retrieval**: Semantic search in ChromaDB finds the most similar slices.
- **Verification**: Top results are re-evaluated by `glm-4.6v` against the extracted features to ensure accuracy.

---

## Development Conventions
- **Configuration**: All system-wide settings (models, ports, slicing logic) MUST be managed in `backend/config.py`.
- **API Documentation**: Interactive docs are available at `/docs` (Swagger) when the backend is running.
- **Persistence**: Task states and video metadata are persisted in `backend/data/task_status.json` and `video_meta.json`.
- **Error Handling**: Use the `task_status` dictionary in `main.py` to track long-running async background tasks.
- **Styling**: Frontend uses TailwindCSS for responsive and modern UI components.

---

## TODO / Future Enhancements
- [ ] Implement OpenCV-based motion detection to skip static video segments.
- [ ] Add support for real-time RTSP stream analysis.
- [ ] Enhance visual verification with frame-level bounding box detection.
