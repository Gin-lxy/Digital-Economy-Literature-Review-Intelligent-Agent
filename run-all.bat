@echo off
REM Start the main agent product: FastAPI backend + Vite frontend.

echo ========================================
echo RAG Scholar Agent
echo ========================================
echo.

setlocal enabledelayedexpansion
for %%I in ("%~dp0.") do set "PROJECT_ROOT=%%~fI"

echo [1/4] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    exit /b 1
)

echo [2/4] Checking Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js is not installed or not in PATH.
    exit /b 1
)

echo [3/4] Starting backend on port 8000...
start "RAG-Scholar-API" cmd /k "cd /d %PROJECT_ROOT% && python -m uvicorn backend:app --reload --host 0.0.0.0 --port 8000"

echo [4/4] Starting frontend on port 5173...
start "RAG-Scholar-Web" cmd /k "cd /d %PROJECT_ROOT%\web && npm run dev"

echo.
echo ========================================
echo Services started
echo ========================================
echo Frontend: http://localhost:5173
echo Backend:  http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo ========================================
