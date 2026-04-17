import sys
sys.path.append('.')
import os
from dotenv import load_dotenv
from src.config import load_settings
from pathlib import Path

print('Current dir:', os.getcwd())
print('Env file exists:', os.path.exists('.env'))

load_dotenv()
print('OPENAI_API_KEY loaded:', bool(os.getenv('OPENAI_API_KEY')))

try:
    settings = load_settings()
    print('Settings loaded successfully')

    # 模拟backend.py中的逻辑
    index_path = settings.index_dir / "index.faiss"
    chunks_path = settings.processed_chunks_path

    print(f'Index path: {index_path}')
    print(f'Chunks path: {chunks_path}')
    print(f'Index exists: {index_path.exists()}')
    print(f'Chunks exists: {chunks_path.exists()}')

    status = {
        "index_exists": index_path.exists(),
        "chunks_exists": chunks_path.exists(),
        "index_size_mb": 0,
        "chunks_count": 0,
    }

    if status["index_exists"]:
        status["index_size_mb"] = round(index_path.stat().st_size / (1024 * 1024), 2)
        print(f'Index size: {status["index_size_mb"]} MB')

    if status["chunks_exists"]:
        print('Reading chunks file...')
        with open(chunks_path, "r", encoding="utf-8") as f:
            status["chunks_count"] = sum(1 for _ in f)
        print(f'Chunks count: {status["chunks_count"]}')

    print(f'Final status: {status}')

except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()