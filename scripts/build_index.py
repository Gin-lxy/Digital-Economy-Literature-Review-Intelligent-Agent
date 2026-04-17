from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_settings
from src.indexing import build_faiss_index


def parse_args() -> argparse.Namespace:
    settings = load_settings()
    parser = argparse.ArgumentParser(description="Build FAISS index from chunk JSONL.")
    parser.add_argument(
        "--chunks",
        default=str(settings.processed_chunks_path),
        help="Input chunk JSONL path.",
    )
    parser.add_argument(
        "--index-dir",
        default=str(settings.index_dir),
        help="Output FAISS index directory.",
    )
    parser.add_argument(
        "--embedding-model",
        default=settings.embedding_model,
        help="Sentence transformer model name.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=256,
        help="How many chunks to embed per batch when building FAISS.",
    )
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=None,
        help="Optional: only index the first N chunks for debugging.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    count = build_faiss_index(
        chunks_path=Path(args.chunks),
        index_dir=Path(args.index_dir),
        embedding_model=args.embedding_model,
        batch_size=args.batch_size,
        max_chunks=args.max_chunks,
    )
    print(f"Completed. Indexed chunks: {count}, index_dir: {args.index_dir}")


if __name__ == "__main__":
    main()
