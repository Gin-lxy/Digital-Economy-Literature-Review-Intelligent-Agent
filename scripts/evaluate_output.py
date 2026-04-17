from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluation import eval_to_dict, evaluate_generation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate generated review output.")
    parser.add_argument("--input", required=True, help="Path to review_*.json")
    parser.add_argument(
        "--reference",
        default="",
        help="Optional human-written review text for ROUGE-L.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    payload = json.loads(input_path.read_text(encoding="utf-8"))

    eval_result = evaluate_generation(
        generated_text=payload.get("answer", ""),
        citations=payload.get("citations", []),
        retrieved_contexts=[d.get("text", "") for d in payload.get("retrieved_docs", [])],
        reference_text=args.reference,
    )
    result_dict = eval_to_dict(eval_result)
    print(json.dumps(result_dict, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
