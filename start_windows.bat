@echo off
chcp 65001 >nul
title ShadowHunter - 视频语义检索系统

echo ========================================
echo   猎影 (ShadowHunter) 视频语义检索系统
echo ========================================
echo.

:: 检查 Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 未安装，请先安装 Python 3.8+
    pause
    exit /b 1
)

:: 检查 Node.js
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js 未安装，请先安装 Node.js 18+
    pause
    exit /b 1
)

:: 创建目录
if not exist "data\chromadb" mkdir data\chromadb
if not exist "data\videos" mkdir data\videos
if not exist "logs" mkdir logs

:: 安装后端依赖
echo [STEP] 安装后端依赖...
cd backend
python -m pip install -r requirements.txt -q

:: 安装前端依赖
echo [STEP] 安装前端依赖...
cd ..\frontend
call npm install --silent

:: 启动后端
echo [STEP] 启动后端服务...
cd ..\backend
start /b python main.py

:: 等待后端启动
timeout /t 3 /nobreak >nul

:: 启动前端
echo [STEP] 启动前端服务...
cd ..\frontend
start /b npm run dev

echo.
echo ========================================
echo   服务已启动
echo ========================================
echo   前端: http://localhost:3000
echo   后端: http://localhost:8000
echo   文档: http://localhost:8000/docs
echo ========================================
echo.
echo 按任意键停止服务...
pause >nul

:: 停止服务
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im node.exe >nul 2>&1

echo 服务已停止