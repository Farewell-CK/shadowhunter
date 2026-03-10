#!/bin/bash

# 猎影 (ShadowHunter) 一键启动脚本
# 用法: ./start.sh [选项]
#   --backend-only   仅启动后端
#   --frontend-only  仅启动前端
#   --install        安装依赖后启动

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
DATA_DIR="$PROJECT_ROOT/data"
LOGS_DIR="$PROJECT_ROOT/logs"

# 创建必要目录
mkdir -p "$DATA_DIR/chromadb"
mkdir -p "$DATA_DIR/videos"
mkdir -p "$LOGS_DIR"

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 检查命令是否存在
check_command() {
    if ! command -v $1 &> /dev/null; then
        log_error "$1 未安装，请先安装"
        return 1
    fi
    return 0
}

# 检查 Python 环境
check_python() {
    log_step "检查 Python 环境..."

    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        log_error "Python 未安装"
        exit 1
    fi

    log_info "使用 $PYTHON_CMD"

    # 检查 pip
    if ! $PYTHON_CMD -m pip --version &> /dev/null; then
        log_error "pip 未安装"
        exit 1
    fi
}

# 检查 Node.js 环境
check_node() {
    log_step "检查 Node.js 环境..."

    if ! check_command node; then
        log_error "Node.js 未安装，请访问 https://nodejs.org 安装"
        exit 1
    fi

    if ! check_command npm; then
        log_error "npm 未安装"
        exit 1
    fi

    NODE_VERSION=$(node -v)
    log_info "Node.js 版本: $NODE_VERSION"
}

# 安装后端依赖
install_backend() {
    log_step "安装后端依赖..."
    cd "$BACKEND_DIR"

    # 创建虚拟环境（可选）
    if [ ! -d "venv" ]; then
        log_info "创建 Python 虚拟环境..."
        $PYTHON_CMD -m venv venv
    fi

    # 激活虚拟环境
    source venv/bin/activate 2>/dev/null || true

    # 安装依赖
    pip install -r requirements.txt

    log_info "后端依赖安装完成"
}

# 安装前端依赖
install_frontend() {
    log_step "安装前端依赖..."
    cd "$FRONTEND_DIR"

    npm install

    log_info "前端依赖安装完成"
}

# 检查配置
check_config() {
    log_step "检查配置..."

    CONFIG_FILE="$BACKEND_DIR/config.py"

    if [ ! -f "$CONFIG_FILE" ]; then
        log_error "配置文件不存在: $CONFIG_FILE"
        exit 1
    fi

    # 检查 API Key 是否配置
    if grep -q 'ZHIPU_API_KEY = ""' "$CONFIG_FILE" || grep -q "ZHIPU_API_KEY = ''" "$CONFIG_FILE"; then
        log_warn "智谱 API Key 未配置"
        log_warn "请编辑 $CONFIG_FILE 设置 ZHIPU_API_KEY"
        echo ""
        read -p "是否继续启动？(y/N) " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        log_info "API Key 已配置"
    fi
}

# 启动后端
start_backend() {
    log_step "启动后端服务..."
    cd "$BACKEND_DIR"

    # 激活虚拟环境
    source venv/bin/activate 2>/dev/null || true

    # 检查端口
    if lsof -i:8000 &> /dev/null; then
        log_warn "端口 8000 已被占用"
        read -p "是否终止占用进程？(y/N) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            lsof -ti:8000 | xargs kill -9 2>/dev/null || true
        else
            log_error "无法启动后端"
            return 1
        fi
    fi

    # 启动服务
    nohup $PYTHON_CMD main.py > "$LOGS_DIR/backend.log" 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > "$LOGS_DIR/backend.pid"

    log_info "后端服务已启动 (PID: $BACKEND_PID)"
    log_info "日志文件: $LOGS_DIR/backend.log"
    log_info "API 文档: http://localhost:8000/docs"
}

# 启动前端
start_frontend() {
    log_step "启动前端服务..."
    cd "$FRONTEND_DIR"

    # 检查端口
    if lsof -i:3000 &> /dev/null; then
        log_warn "端口 3000 已被占用"
        read -p "是否终止占用进程？(y/N) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            lsof -ti:3000 | xargs kill -9 2>/dev/null || true
        else
            log_error "无法启动前端"
            return 1
        fi
    fi

    # 启动服务
    nohup npm run dev > "$LOGS_DIR/frontend.log" 2>&1 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > "$LOGS_DIR/frontend.pid"

    log_info "前端服务已启动 (PID: $FRONTEND_PID)"
    log_info "日志文件: $LOGS_DIR/frontend.log"
    log_info "访问地址: http://localhost:3000"
}

# 停止服务
stop_services() {
    log_step "停止服务..."

    # 停止后端
    if [ -f "$LOGS_DIR/backend.pid" ]; then
        PID=$(cat "$LOGS_DIR/backend.pid")
        if kill -0 $PID 2>/dev/null; then
            kill $PID
            log_info "后端服务已停止"
        fi
        rm -f "$LOGS_DIR/backend.pid"
    fi

    # 停止前端
    if [ -f "$LOGS_DIR/frontend.pid" ]; then
        PID=$(cat "$LOGS_DIR/frontend.pid")
        if kill -0 $PID 2>/dev/null; then
            kill $PID
            log_info "前端服务已停止"
        fi
        rm -f "$LOGS_DIR/frontend.pid"
    fi
}

# 查看状态
show_status() {
    echo ""
    echo "========================================"
    echo "  猎影 (ShadowHunter) 服务状态"
    echo "========================================"

    # 后端状态
    if [ -f "$LOGS_DIR/backend.pid" ]; then
        PID=$(cat "$LOGS_DIR/backend.pid")
        if kill -0 $PID 2>/dev/null; then
            echo -e "后端服务: ${GREEN}运行中${NC} (PID: $PID)"
            echo "  - API: http://localhost:8000"
            echo "  - 文档: http://localhost:8000/docs"
        else
            echo -e "后端服务: ${RED}已停止${NC}"
        fi
    else
        echo -e "后端服务: ${YELLOW}未启动${NC}"
    fi

    # 前端状态
    if [ -f "$LOGS_DIR/frontend.pid" ]; then
        PID=$(cat "$LOGS_DIR/frontend.pid")
        if kill -0 $PID 2>/dev/null; then
            echo -e "前端服务: ${GREEN}运行中${NC} (PID: $PID)"
            echo "  - 地址: http://localhost:3000"
        else
            echo -e "前端服务: ${RED}已停止${NC}"
        fi
    else
        echo -e "前端服务: ${YELLOW}未启动${NC}"
    fi

    echo "========================================"
}

# 显示帮助
show_help() {
    echo "猎影 (ShadowHunter) 启动脚本"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --help           显示帮助信息"
    echo "  --install        安装依赖并启动"
    echo "  --backend-only   仅启动后端服务"
    echo "  --frontend-only  仅启动前端服务"
    echo "  --stop           停止所有服务"
    echo "  --status         查看服务状态"
    echo ""
    echo "示例:"
    echo "  $0               # 启动所有服务"
    echo "  $0 --install     # 安装依赖后启动"
    echo "  $0 --stop        # 停止所有服务"
}

# 主函数
main() {
    echo ""
    echo "========================================"
    echo "  猎影 (ShadowHunter) 视频语义检索系统"
    echo "========================================"
    echo ""

    # 解析参数
    INSTALL_DEPS=false
    BACKEND_ONLY=false
    FRONTEND_ONLY=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            --help|-h)
                show_help
                exit 0
                ;;
            --install)
                INSTALL_DEPS=true
                shift
                ;;
            --backend-only)
                BACKEND_ONLY=true
                shift
                ;;
            --frontend-only)
                FRONTEND_ONLY=true
                shift
                ;;
            --stop)
                stop_services
                exit 0
                ;;
            --status)
                show_status
                exit 0
                ;;
            *)
                log_error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done

    # 检查环境
    check_python

    # 安装依赖
    if [ "$INSTALL_DEPS" = true ]; then
        install_backend
        check_node
        install_frontend
    fi

    # 检查配置
    check_config

    # 启动服务
    if [ "$FRONTEND_ONLY" = true ]; then
        check_node
        start_frontend
    elif [ "$BACKEND_ONLY" = true ]; then
        start_backend
    else
        start_backend
        check_node
        start_frontend
    fi

    # 显示状态
    sleep 2
    show_status

    log_info "启动完成！按 Ctrl+C 退出（服务将继续后台运行）"
    log_info "使用 '$0 --stop' 停止服务"

    # 等待用户中断
    trap 'echo ""; log_info "退出脚本（服务继续运行）"; exit 0' INT
    wait
}

# 执行主函数
main "$@"