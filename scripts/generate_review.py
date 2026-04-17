from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_settings
from src.rag_chain import generate_review


def _parse_csv_list(text: str) -> list[str]:
    return [item.strip() for item in text.split(",") if item.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate structured literature review via RAG.")
    parser.add_argument(
        "--query",
        required=True,
        help='Example: "Platform economy impacts on labor market".',
    )
    parser.add_argument(
        "--out-dir",
        default="outputs",
        help="Directory to save generation result.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=0,
        help="Override retrieval top-k. Use 0 to follow .env RETRIEVE_TOP_K.",
    )
    parser.add_argument(
        "--detail-level",
        choices=["concise", "standard", "deep"],
        default="deep",
        help="Generation richness level.",
    )
    parser.add_argument(
        "--source-mode",
        choices=["local_only", "local_plus_arxiv", "arxiv_only"],
        default="local_plus_arxiv",
        help="Evidence source combination mode.",
    )
    parser.add_argument(
        "--arxiv-max-results",
        type=int,
        default=0,
        help="Override arXiv results count. Use 0 to follow .env ARXIV_MAX_RESULTS.",
    )
    parser.add_argument(
        "--subfields",
        default="",
        help="Optional comma-separated subfield filters.",
    )
    parser.add_argument(
        "--journal-categories",
        default="",
        help="Optional comma-separated journal category filters.",
    )
    parser.add_argument(
        "--journal-codes",
        default="",
        help="Optional comma-separated journal code filters, e.g. JBE,JMIS,ARXIV.",
    )
    parser.add_argument(
        "--year-from",
        type=int,
        default=0,
        help="Optional lower bound of publication year, e.g. 2018.",
    )
    parser.add_argument(
        "--year-to",
        type=int,
        default=0,
        help="Optional upper bound of publication year, e.g. 2025.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings()
    result = generate_review(
        args.query,
        settings,
        top_k=args.top_k if args.top_k > 0 else None,
        detail_level=args.detail_level,
        source_mode=args.source_mode,
        arxiv_max_results=args.arxiv_max_results if args.arxiv_max_results > 0 else None,
        subfields=_parse_csv_list(args.subfields) or None,
        journal_categories=_parse_csv_list(args.journal_categories) or None,
        journal_codes=_parse_csv_list(args.journal_codes) or None,
        year_from=args.year_from if args.year_from > 0 else None,
        year_to=args.year_to if args.year_to > 0 else None,
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"review_{ts}.json"

    payload = {
        "query": result.query,
        "detail_level": result.detail_level,
        "top_k": result.top_k,
        "source_mode": result.source_mode,
        "subfields": result.subfields,
        "journal_categories": result.journal_categories,
        "journal_codes": result.journal_codes,
        "year_from": result.year_from,
        "year_to": result.year_to,
        "local_result_count": result.local_result_count,
        "arxiv_result_count": result.arxiv_result_count,
        "answer": result.answer,
        "citations": result.citations,
        "retrieved_docs": [
            {
                "source": d.metadata.get("source", ""),
                "title": d.metadata.get("title", ""),
                "page": d.metadata.get("page", 0),
                "source_type": d.metadata.get("source_type", ""),
                "journal_code": d.metadata.get("journal_code", ""),
                "journal_category": d.metadata.get("journal_category", ""),
                "subfield": d.metadata.get("subfield", ""),
                "url": d.metadata.get("url", ""),
                "published": d.metadata.get("published", ""),
                "pub_year": d.metadata.get("pub_year", None),
                "text": d.page_content,
            }
            for d in result.retrieved_docs
        ],
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(result.answer)
    print(f"\nSaved to: {out_path}")


if __name__ == "__main__":
    main()
