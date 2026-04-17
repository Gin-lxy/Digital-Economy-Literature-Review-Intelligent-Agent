from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_settings
from src.pdf_pipeline import build_corpus


def parse_args() -> argparse.Namespace:
    settings = load_settings()
    parser = argparse.ArgumentParser(
        description="Parse PDFs, clean text, and create chunk JSONL."
    )
    parser.add_argument(
        "--raw-dir",
        default=str(settings.raw_pdf_dir),
        help="Directory containing PDF papers.",
    )
    parser.add_argument(
        "--out",
        default=str(settings.processed_chunks_path),
        help="Output JSONL path for text chunks.",
    )
    parser.add_argument("--chunk-size", type=int, default=800)
    parser.add_argument("--chunk-overlap", type=int, default=120)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pdf_count, chunk_count = build_corpus(
        raw_pdf_dir=Path(args.raw_dir),
        output_chunks_path=Path(args.out),
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    print(f"Completed. PDFs: {pdf_count}, chunks: {chunk_count}, output: {args.out}")


if __name__ == "__main__":
    main()
