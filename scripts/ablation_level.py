from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import re
import statistics
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_settings
from src.evaluation import eval_to_dict, evaluate_generation
from src.rag_chain import generate_review


VALID_LEVELS = ("concise", "standard", "deep")
HIGHER_BETTER_METRICS = (
    "rouge_l_f1_mean",
    "citation_count_mean",
    "citation_coverage_mean",
    "context_overlap_mean",
    "citation_id_precision_mean",
)
LOWER_BETTER_METRICS = (
    "placeholder_citation_count_mean",
    "invalid_id_like_count_mean",
    "latency_s_mean",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run detail-level ablation experiments by fixing retrieval settings "
            "and comparing concise/standard/deep generation quality."
        )
    )
    parser.add_argument(
        "--queries",
        nargs="*",
        default=[],
        help="Inline query list. Example: --queries \"q1\" \"q2\"",
    )
    parser.add_argument(
        "--queries-file",
        default="",
        help="Optional text file with one query per line.",
    )
    parser.add_argument(
        "--levels",
        default="concise,standard,deep",
        help="Comma-separated levels from concise,standard,deep.",
    )
    parser.add_argument(
        "--baseline-level",
        default="standard",
        choices=VALID_LEVELS,
        help="Baseline level for improvement comparison.",
    )
    parser.add_argument(
        "--source-mode",
        choices=["local_only", "local_plus_arxiv", "arxiv_only"],
        default="local_plus_arxiv",
        help="Evidence source combination mode.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=0,
        help="Override retrieval top-k. Use 0 to follow .env RETRIEVE_TOP_K.",
    )
    parser.add_argument(
        "--arxiv-max-results",
        type=int,
        default=0,
        help="Override arXiv results count. Use 0 to follow .env ARXIV_MAX_RESULTS.",
    )
    parser.add_argument(
        "--reference-json",
        default="",
        help=(
            "Optional reference mapping JSON for ROUGE-L. "
            "Supports {\"query\":\"reference\"} or "
            "[{\"query\":\"...\",\"reference\":\"...\"}]."
        ),
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.0,
        help="Optional sleep between runs to reduce API rate pressure.",
    )
    parser.add_argument(
        "--max-queries",
        type=int,
        default=0,
        help="Run only first N queries after loading. 0 means all.",
    )
    parser.add_argument(
        "--out-dir",
        default="outputs/ablation",
        help="Directory to save run details and summaries.",
    )
    return parser.parse_args()


def _parse_levels(raw_levels: str) -> list[str]:
    levels = [item.strip().lower() for item in raw_levels.split(",") if item.strip()]
    if not levels:
        raise ValueError("No detail levels provided.")
    for level in levels:
        if level not in VALID_LEVELS:
            raise ValueError(
                f"Invalid level '{level}'. Allowed values: {', '.join(VALID_LEVELS)}"
            )
    deduped = list(dict.fromkeys(levels))
    return deduped


def _load_queries(inline_queries: list[str], queries_file: str) -> list[str]:
    queries = [q.strip() for q in inline_queries if q.strip()]
    if queries_file:
        file_path = Path(queries_file)
        if not file_path.exists():
            raise FileNotFoundError(f"Queries file not found: {queries_file}")
        for line in file_path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            queries.append(text)

    deduped = list(dict.fromkeys(queries))
    if not deduped:
        raise ValueError("No query provided. Use --queries or --queries-file.")
    return deduped


def _load_reference_map(reference_json: str) -> dict[str, str]:
    if not reference_json:
        return {}

    ref_path = Path(reference_json)
    if not ref_path.exists():
        raise FileNotFoundError(f"Reference JSON not found: {reference_json}")

    payload = json.loads(ref_path.read_text(encoding="utf-8"))
    ref_map: dict[str, str] = {}

    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(key, str) and isinstance(value, str):
                ref_map[key.strip()] = value
        return ref_map

    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            query = str(item.get("query", "")).strip()
            reference = str(item.get("reference", "")).strip()
            if query and reference:
                ref_map[query] = reference
        return ref_map

    raise ValueError("Unsupported reference JSON schema.")


def _extract_bracket_items(text: str) -> list[str]:
    return [token.strip() for token in re.findall(r"\[([^\[\]]+)\]", text) if token.strip()]


def _count_word_like_tokens(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9_]+", text))


def _analyze_citations(answer: str, valid_citation_ids: set[str]) -> dict[str, Any]:
    items = _extract_bracket_items(answer)
    placeholder_citation_count = 0
    id_like: list[str] = []

    for token in items:
        lower = token.lower()
        if lower == "source:page":
            placeholder_citation_count += 1
        if ":" not in token:
            continue
        if lower.startswith("http://") or lower.startswith("https://"):
            continue
        id_like.append(token)

    valid_id_like_count = sum(1 for token in id_like if token in valid_citation_ids)
    invalid_id_like_items = sorted(
        {token for token in id_like if token not in valid_citation_ids and token.lower() != "source:page"}
    )
    invalid_id_like_count = len(invalid_id_like_items)
    citation_id_precision = (
        valid_id_like_count / len(id_like) if id_like else 0.0
    )

    return {
        "bracket_item_count": len(items),
        "id_like_citation_count": len(id_like),
        "valid_id_like_count": valid_id_like_count,
        "invalid_id_like_count": invalid_id_like_count,
        "invalid_id_like_items": invalid_id_like_items,
        "placeholder_citation_count": placeholder_citation_count,
        "citation_id_precision": round(citation_id_precision, 4),
    }


def _serialize_docs(retrieved_docs: list[Any]) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for doc in retrieved_docs:
        docs.append(
            {
                "source": doc.metadata.get("source", ""),
                "title": doc.metadata.get("title", ""),
                "page": doc.metadata.get("page", ""),
                "source_type": doc.metadata.get("source_type", ""),
                "journal_code": doc.metadata.get("journal_code", ""),
                "journal_category": doc.metadata.get("journal_category", ""),
                "subfield": doc.metadata.get("subfield", ""),
                "url": doc.metadata.get("url", ""),
                "published": doc.metadata.get("published", ""),
                "text": doc.page_content,
            }
        )
    return docs


def _mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return round(statistics.mean(values), 4)


def _aggregate_by_level(rows: list[dict[str, Any]], levels: list[str]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for level in levels:
        level_rows = [row for row in rows if row["detail_level"] == level]
        success_rows = [row for row in level_rows if row["success"]]
        summary.append(
            {
                "detail_level": level,
                "runs_total": len(level_rows),
                "success_count": len(success_rows),
                "error_count": len(level_rows) - len(success_rows),
                "rouge_l_f1_mean": _mean_or_none([row["rouge_l_f1"] for row in success_rows]),
                "citation_count_mean": _mean_or_none([row["citation_count"] for row in success_rows]),
                "citation_coverage_mean": _mean_or_none([row["citation_coverage"] for row in success_rows]),
                "context_overlap_mean": _mean_or_none([row["context_overlap"] for row in success_rows]),
                "citation_id_precision_mean": _mean_or_none([row["citation_id_precision"] for row in success_rows]),
                "placeholder_citation_count_mean": _mean_or_none(
                    [row["placeholder_citation_count"] for row in success_rows]
                ),
                "invalid_id_like_count_mean": _mean_or_none(
                    [row["invalid_id_like_count"] for row in success_rows]
                ),
                "latency_s_mean": _mean_or_none([row["latency_s"] for row in success_rows]),
                "answer_word_tokens_mean": _mean_or_none(
                    [row["answer_word_tokens"] for row in success_rows]
                ),
                "answer_chars_mean": _mean_or_none([row["answer_chars"] for row in success_rows]),
            }
        )
    return summary


def _relative_improvement(
    baseline_value: float | None,
    current_value: float | None,
    higher_is_better: bool,
) -> float | None:
    if baseline_value is None or current_value is None:
        return None
    if baseline_value == 0:
        if current_value == 0:
            return 0.0
        return None
    if higher_is_better:
        return round((current_value - baseline_value) / abs(baseline_value) * 100, 2)
    return round((baseline_value - current_value) / abs(baseline_value) * 100, 2)


def _build_improvements_vs_baseline(
    level_summary: list[dict[str, Any]],
    baseline_level: str,
) -> dict[str, Any]:
    by_level = {item["detail_level"]: item for item in level_summary}
    baseline = by_level.get(baseline_level)
    if not baseline:
        return {"baseline_level": baseline_level, "comparisons": {}}

    comparisons: dict[str, Any] = {}
    for level, row in by_level.items():
        if level == baseline_level:
            continue
        metric_compare: dict[str, Any] = {}
        for metric in HIGHER_BETTER_METRICS:
            metric_compare[metric] = {
                "delta": None
                if baseline.get(metric) is None or row.get(metric) is None
                else round(row[metric] - baseline[metric], 4),
                "relative_improvement_pct": _relative_improvement(
                    baseline.get(metric), row.get(metric), higher_is_better=True
                ),
                "direction": "higher_is_better",
            }
        for metric in LOWER_BETTER_METRICS:
            metric_compare[metric] = {
                "delta": None
                if baseline.get(metric) is None or row.get(metric) is None
                else round(row[metric] - baseline[metric], 4),
                "relative_improvement_pct": _relative_improvement(
                    baseline.get(metric), row.get(metric), higher_is_better=False
                ),
                "direction": "lower_is_better",
            }
        comparisons[level] = metric_compare
    return {"baseline_level": baseline_level, "comparisons": comparisons}


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _print_summary(summary_rows: list[dict[str, Any]], improvements: dict[str, Any]) -> None:
    print("\n=== Ablation Summary (by detail_level) ===")
    for row in summary_rows:
        print(
            f"- {row['detail_level']}: "
            f"success={row['success_count']}/{row['runs_total']}, "
            f"context_overlap_mean={row['context_overlap_mean']}, "
            f"citation_precision_mean={row['citation_id_precision_mean']}, "
            f"placeholder_mean={row['placeholder_citation_count_mean']}, "
            f"latency_s_mean={row['latency_s_mean']}"
        )

    baseline_level = improvements.get("baseline_level", "")
    print(f"\n=== Relative Improvement vs baseline='{baseline_level}' ===")
    comparisons = improvements.get("comparisons", {})
    if not comparisons:
        print("No comparison available (missing baseline or no successful runs).")
        return
    for level, metrics in comparisons.items():
        overlap = metrics.get("context_overlap_mean", {}).get("relative_improvement_pct")
        precision = metrics.get("citation_id_precision_mean", {}).get("relative_improvement_pct")
        placeholder = metrics.get("placeholder_citation_count_mean", {}).get("relative_improvement_pct")
        print(
            f"- {level}: context_overlap={overlap}%, "
            f"citation_precision={precision}%, "
            f"placeholder_count={placeholder}%"
        )


def main() -> None:
    args = parse_args()
    settings = load_settings()

    levels = _parse_levels(args.levels)
    if args.baseline_level not in levels:
        levels.append(args.baseline_level)

    queries = _load_queries(args.queries, args.queries_file)
    if args.max_queries > 0:
        queries = queries[: args.max_queries]
    reference_map = _load_reference_map(args.reference_json)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir) / f"ablation_level_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    effective_top_k = args.top_k if args.top_k > 0 else settings.retrieve_top_k
    effective_arxiv_max = (
        args.arxiv_max_results if args.arxiv_max_results > 0 else settings.arxiv_max_results
    )

    all_rows: list[dict[str, Any]] = []
    total_runs = len(queries) * len(levels)
    run_index = 0
    for query in queries:
        for level in levels:
            run_index += 1
            print(f"[{run_index}/{total_runs}] Running level='{level}' query='{query}'")
            started = time.perf_counter()
            try:
                result = generate_review(
                    query=query,
                    settings=settings,
                    top_k=effective_top_k,
                    detail_level=level,
                    source_mode=args.source_mode,
                    arxiv_max_results=effective_arxiv_max,
                )
                elapsed = round(time.perf_counter() - started, 4)

                eval_result = eval_to_dict(
                    evaluate_generation(
                        generated_text=result.answer,
                        citations=result.citations,
                        retrieved_contexts=[doc.page_content for doc in result.retrieved_docs],
                        reference_text=reference_map.get(query, ""),
                    )
                )
                citation_analysis = _analyze_citations(result.answer, set(result.citations))

                row: dict[str, Any] = {
                    "success": True,
                    "error": "",
                    "query": query,
                    "detail_level": level,
                    "source_mode": args.source_mode,
                    "top_k": result.top_k,
                    "arxiv_max_results": effective_arxiv_max,
                    "local_result_count": result.local_result_count,
                    "arxiv_result_count": result.arxiv_result_count,
                    "latency_s": elapsed,
                    "answer_chars": len(result.answer),
                    "answer_word_tokens": _count_word_like_tokens(result.answer),
                    **eval_result,
                    **citation_analysis,
                    "answer": result.answer,
                    "citations": result.citations,
                    "retrieved_docs": _serialize_docs(result.retrieved_docs),
                }
                all_rows.append(row)
            except Exception as exc:
                elapsed = round(time.perf_counter() - started, 4)
                all_rows.append(
                    {
                        "success": False,
                        "error": f"{type(exc).__name__}: {exc}",
                        "query": query,
                        "detail_level": level,
                        "source_mode": args.source_mode,
                        "top_k": effective_top_k,
                        "arxiv_max_results": effective_arxiv_max,
                        "local_result_count": 0,
                        "arxiv_result_count": 0,
                        "latency_s": elapsed,
                        "answer_chars": 0,
                        "answer_word_tokens": 0,
                        "rouge_l_f1": 0.0,
                        "citation_count": 0,
                        "citation_coverage": 0.0,
                        "context_overlap": 0.0,
                        "bracket_item_count": 0,
                        "id_like_citation_count": 0,
                        "valid_id_like_count": 0,
                        "invalid_id_like_count": 0,
                        "invalid_id_like_items": [],
                        "placeholder_citation_count": 0,
                        "citation_id_precision": 0.0,
                        "answer": "",
                        "citations": [],
                        "retrieved_docs": [],
                    }
                )
            if args.sleep_seconds > 0:
                time.sleep(args.sleep_seconds)

    level_summary = _aggregate_by_level(all_rows, levels)
    improvements = _build_improvements_vs_baseline(level_summary, args.baseline_level)

    run_details_path = out_dir / "run_details.jsonl"
    run_summary_path = out_dir / "summary_by_level.csv"
    improvements_path = out_dir / "improvements_vs_baseline.json"
    config_path = out_dir / "experiment_config.json"

    _write_jsonl(run_details_path, all_rows)
    _write_csv(run_summary_path, level_summary)
    improvements_path.write_text(
        json.dumps(improvements, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    config_path.write_text(
        json.dumps(
            {
                "timestamp": ts,
                "queries_count": len(queries),
                "levels": levels,
                "baseline_level": args.baseline_level,
                "source_mode": args.source_mode,
                "top_k": effective_top_k,
                "arxiv_max_results": effective_arxiv_max,
                "reference_json": args.reference_json,
                "sleep_seconds": args.sleep_seconds,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    _print_summary(level_summary, improvements)
    print("\nSaved files:")
    print(f"- {run_details_path}")
    print(f"- {run_summary_path}")
    print(f"- {improvements_path}")
    print(f"- {config_path}")


if __name__ == "__main__":
    main()
