#!/bin/bash
# 启动 RAG 前端开发服务器（无等待消息）

cd "$(dirname "$0")"

echo "========================================"
echo "Starting RAG Frontend Development Server"
echo "========================================"
echo ""

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js not found or not in PATH"
    exit 1
fi

# 启动开发服务器
echo "Starting on http://localhost:5173"
echo "Press Ctrl+C to stop"
echo ""

npm run dev
