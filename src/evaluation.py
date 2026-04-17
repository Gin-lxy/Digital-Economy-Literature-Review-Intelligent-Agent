from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Iterable

try:
    import jieba
except Exception:  # pragma: no cover
    jieba = None


@dataclass
class EvalResult:
    rouge_l_f1: float
    citation_count: int
    citation_coverage: float
    context_overlap: float


def _split_multilingual(text: str) -> list[str]:
    """
    Tokenize mixed Chinese/English text:
    - Chinese blocks: segmented by jieba if available; fallback to char-level.
    - English/number blocks: kept as lowercase word tokens.
    """
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    blocks = re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9_]+", text)
    tokens: list[str] = []
    for block in blocks:
        if re.fullmatch(r"[\u4e00-\u9fff]+", block):
            if jieba is not None:
                tokens.extend([tok.strip() for tok in jieba.lcut(block) if tok.strip()])
            else:
                tokens.extend(list(block))
        else:
            tokens.append(block.lower())
    return tokens


def _tokenize_set(text: str) -> set[str]:
    return set(_split_multilingual(text))


def _lcs_length(a: list[str], b: list[str]) -> int:
    if not a or not b:
        return 0
    dp = [0] * (len(b) + 1)
    for token_a in a:
        prev = 0
        for j, token_b in enumerate(b, start=1):
            tmp = dp[j]
            if token_a == token_b:
                dp[j] = prev + 1
            else:
                dp[j] = max(dp[j], dp[j - 1])
            prev = tmp
    return dp[-1]


def _rouge_l_f1(reference_text: str, generated_text: str) -> float:
    ref = _split_multilingual(reference_text)
    hyp = _split_multilingual(generated_text)
    if not ref or not hyp:
        return 0.0

    lcs = _lcs_length(ref, hyp)
    if lcs == 0:
        return 0.0

    precision = lcs / len(hyp)
    recall = lcs / len(ref)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _context_overlap(answer: str, contexts: Iterable[str]) -> float:
    context_tokens: set[str] = set()
    for ctx in contexts:
        context_tokens |= _tokenize_set(ctx)

    answer_tokens = _tokenize_set(answer)
    if not answer_tokens:
        return 0.0
    shared = answer_tokens & context_tokens
    return len(shared) / len(answer_tokens)


def evaluate_generation(
    generated_text: str,
    citations: list[str],
    retrieved_contexts: list[str],
    reference_text: str = "",
    expected_min_citations: int = 3,
) -> EvalResult:
    rouge_l = 0.0
    if reference_text.strip():
        rouge_l = _rouge_l_f1(reference_text, generated_text)

    citation_count = len(citations)
    citation_coverage = min(citation_count / max(expected_min_citations, 1), 1.0)
    overlap = _context_overlap(generated_text, retrieved_contexts)

    return EvalResult(
        rouge_l_f1=round(rouge_l, 4),
        citation_count=citation_count,
        citation_coverage=round(citation_coverage, 4),
        context_overlap=round(overlap, 4),
    )


def eval_to_dict(result: EvalResult) -> dict:
    return asdict(result)
