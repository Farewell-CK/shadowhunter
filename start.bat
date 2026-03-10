#!/bin/bash

# Windows 启动脚本 (Git Bash / WSL)

# 猎影 (ShadowHunter) 启动脚本

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
DATA_DIR="$PROJECT_ROOT/data"
LOGS_DIR="$PROJECT_ROOT/logs"

mkdir -p "$DATA_DIR/chromadb" "$DATA_DIR/videos" "$LOGS_DIR"

echo "========================================"
echo "  猎影 (ShadowHunter) 视频语义检索系统"
echo "========================================"

# 检查 Python
if command -v python &> /dev/null; then
    PYTHON_CMD="python"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    echo "[ERROR] Python 未安装"
    exit 1
fi

# 安装依赖
echo "[STEP] 安装后端依赖..."
cd "$BACKEND_DIR"
$PYTHON_CMD -m pip install -r requirements.txt --quiet

echo "[STEP] 安装前端依赖..."
cd "$FRONTEND_DIR"
npm install --silent 2>/dev/null || npm install

# 启动后端
echo "[STEP] 启动后端..."
cd "$BACKEND_DIR"
$PYTHON_CMD main.py &
BACKEND_PID=$!

# 等待后端启动
sleep 3

# 启动前端
echo "[STEP] 启动前端..."
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "========================================"
echo "  服务已启动"
echo "========================================"
echo "  前端: http://localhost:3000"
echo "  后端: http://localhost:8000"
echo "  文档: http://localhost:8000/docs"
echo "========================================"
echo ""
echo "按 Ctrl+C 停止服务"

# 等待
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT
wait