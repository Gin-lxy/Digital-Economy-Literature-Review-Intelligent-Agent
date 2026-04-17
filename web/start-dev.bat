@echo off
REM 启动 RAG 前端开发服务器（无等待消息）

cd /d "%~dp0"

echo ========================================
echo Starting RAG Frontend Development Server
echo ========================================
echo.

REM 检查 Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js not found or not in PATH
    exit /b 1
)

REM 启动开发服务器
echo Starting on http://localhost:5173
echo Press Ctrl+C to stop
echo.

REM 使用 --no-stdin 标志运行 npm dev（如果支持）
npm run dev

exit /b %ERRORLEVEL%
