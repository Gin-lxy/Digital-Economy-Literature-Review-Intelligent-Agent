from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Literal

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from src.arxiv_retriever import search_arxiv_documents
from src.config import Settings
from src.indexing import index_exists
from src.metadata_taxonomy import (
    enrich_document_metadata,
    normalize_journal_category,
    normalize_journal_code,
    normalize_pub_year,
    normalize_subfield,
)


DetailLevel = Literal["concise", "standard", "deep"]
SourceMode = Literal["local_only", "local_plus_arxiv", "arxiv_only"]
MIN_FILTER_YEAR = 2018
MAX_FILTER_YEAR = 2025


DETAIL_GUIDANCE: dict[DetailLevel, str] = {
    "concise": (
        "Write a compact review in about 220-320 words. "
        "Each section should be brief."
    ),
    "standard": (
        "Write a balanced review in about 380-550 words. "
        "Provide clear synthesis across multiple sources."
    ),
    "deep": (
        "Write a rich review in about 650-900 words. "
        "Compare viewpoints, methods, and evidence depth in detail."
    ),
}


PROMPT_TEMPLATE = """You are an academic writing assistant for literature review.
Task: write a structured review based only on the evidence below.

Hard rules:
1) Output in English.
2) Maintain academic style and logical clarity.
3) Every key claim must include inline citation using one or more exact citation IDs from the candidate list, in square brackets such as [source:page].
4) Do not invent facts, papers, methods, or years not present in evidence.
5) If evidence is insufficient, explicitly state limitations and missing links.
6) Synthesize sources instead of copying original wording.
7) Never cite with author-year style such as (Smith, 2024), never cite with bare source strings such as arXiv:1234.5678 or file.pdf:12, and never place citations in parentheses.
8) Never output placeholder citation text such as [source:page]; use real IDs from citation candidates.
9) Use only square-bracket citation tokens in the body text.

Detail requirement:
{detail_guidance}

Output format (Markdown):
## Background and Scope
- Define topic boundary, key constructs, and context.

## Core Findings and Mechanisms
- Synthesize at least two mechanisms/pathways and compare major findings.

## Methods and Evidence Strength
- Summarize methods, identification strategies, data limitations, and external validity.

## Debates, Gaps, and Future Directions
- Identify unresolved debates, gaps, and actionable next research steps.

Research topic:
{query}

Available citation candidates:
{citation_candidates}

Evidence:
{context}
"""

CITATION_REPAIR_PROMPT = """You must repair citations in the draft below.

Rules:
1) Keep the original meaning and structure as much as possible.
2) Replace invalid or placeholder citations with valid ones from the allowed list.
3) Keep output in English markdown.
4) Never output [source:page] or any citation not in allowed list.
5) Convert any parenthetical or bare source mention into square-bracket citation form using allowed IDs only.

Allowed citation IDs:
{valid_citation_ids}

Draft:
{draft}
"""


@dataclass
class RAGResult:
    query: str
    answer: str
    citations: list[str]
    retrieved_docs: list[Document]
    detail_level: DetailLevel
    top_k: int
    source_mode: SourceMode
    local_result_count: int
    arxiv_result_count: int
    subfields: list[str]
    journal_categories: list[str]
    journal_codes: list[str]
    year_from: int | None
    year_to: int | None


def _build_no_evidence_answer(
    source_mode: SourceMode,
    subfields: list[str],
    journal_categories: list[str],
    journal_codes: list[str],
    year_from: int | None,
    year_to: int | None,
) -> str:
    filters: list[str] = []
    if subfields:
        filters.append(f"subfields={', '.join(subfields)}")
    if journal_categories:
        filters.append(f"journal categories={', '.join(journal_categories)}")
    if journal_codes:
        filters.append(f"journal codes={', '.join(journal_codes)}")
    if year_from is not None or year_to is not None:
        filters.append(f"year={year_from or 'Any'}-{year_to or 'Any'}")

    filter_text = ", ".join(filters) if filters else "no extra metadata filters"

    return (
        "## Background and Scope\n"
        f"- No evidence matched the current query under `{source_mode}` with {filter_text}.\n\n"
        "## Core Findings and Mechanisms\n"
        "- No grounded synthesis can be produced because retrieval returned zero documents.\n\n"
        "## Methods and Evidence Strength\n"
        "- Try broadening the query or clearing restrictive filters such as journal category, journal code, or year.\n\n"
        "## Debates, Gaps, and Future Directions\n"
        "- Re-run with fewer filters or use `Select all` in the multi-select controls to restore broader coverage.\n\n"
        "## References Used\n"
        "- None"
    )


def _get_llm(settings: Settings):
    if settings.llm_provider == "ollama":
        return ChatOllama(model=settings.llm_model, temperature=0.2)
    if settings.llm_provider != "openai":
        raise ValueError(
            "Unsupported LLM_PROVIDER. Use 'openai' or 'ollama'. "
            f"Current: {settings.llm_provider}"
        )

    if not settings.openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY is missing. Create .env from .env.example and set "
            "LLM_PROVIDER=openai, LLM_MODEL, OPENAI_API_KEY."
        )

    kwargs = {"model": settings.llm_model, "temperature": 0.2}
    if settings.openai_api_key:
        kwargs["api_key"] = settings.openai_api_key
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return ChatOpenAI(**kwargs)


def _format_docs(docs: list[Document]) -> str:
    lines: list[str] = []
    for doc in docs:
        source = str(doc.metadata.get("source", "unknown"))
        page = str(doc.metadata.get("page", "NA"))
        title = str(doc.metadata.get("title", ""))
        source_type = str(doc.metadata.get("source_type", "unknown"))
        citation_id = f"{source}:{page}"
        lines.append(
            f"citation=[{citation_id}] source={source} page={page} "
            f"source_type={source_type} title={title}\n"
            f"{doc.page_content}\n"
        )
    return "\n".join(lines)


def _format_citation_candidates(docs: list[Document]) -> str:
    candidates: list[str] = []
    seen: set[str] = set()
    for doc in docs:
        source = str(doc.metadata.get("source", "unknown"))
        page = str(doc.metadata.get("page", "NA"))
        title = str(doc.metadata.get("title", "")).strip()
        cite = f"{source}:{page}"
        if cite in seen:
            continue
        seen.add(cite)
        candidates.append(f"- [{cite}] {title}")
    return "\n".join(candidates)


def _dedupe_citations(docs: list[Document]) -> list[str]:
    seen: set[str] = set()
    citations: list[str] = []
    for doc in docs:
        source = str(doc.metadata.get("source", "unknown"))
        page = str(doc.metadata.get("page", "NA"))
        cite = f"{source}:{page}"
        if cite in seen:
            continue
        seen.add(cite)
        citations.append(cite)
    return citations


def _extract_bracket_items(text: str) -> list[str]:
    return [m.strip() for m in re.findall(r"\[([^\[\]]+)\]", text) if m.strip()]


def _find_invalid_citations(answer: str, valid_citation_ids: set[str]) -> list[str]:
    invalid: list[str] = []
    for token in _extract_bracket_items(answer):
        if token in {"source:page", "real_source_file.pdf:real_page"}:
            invalid.append(token)
            continue
        if ":" not in token:
            continue
        if token.startswith("http://") or token.startswith("https://"):
            continue
        if token not in valid_citation_ids:
            invalid.append(token)
    return sorted(set(invalid))


def _load_vectorstore(index_dir: Path, embedding_model: str) -> FAISS:
    embeddings = HuggingFaceEmbeddings(model_name=embedding_model)
    return FAISS.load_local(
        str(index_dir), embeddings, allow_dangerous_deserialization=True
    )


def _normalize_subfields(subfields: list[str] | None) -> list[str]:
    if not subfields:
        return []
    normalized = [normalize_subfield(item) for item in subfields]
    return list(dict.fromkeys(item for item in normalized if item))


def _normalize_journal_categories(categories: list[str] | None) -> list[str]:
    if not categories:
        return []
    normalized = [normalize_journal_category(item) for item in categories]
    return list(dict.fromkeys(item for item in normalized if item))


def _normalize_journal_codes(codes: list[str] | None) -> list[str]:
    if not codes:
        return []
    normalized = [normalize_journal_code(item) for item in codes if str(item).strip()]
    return list(dict.fromkeys(item for item in normalized if item))


def _normalize_year_bound(name: str, year: int | None) -> int | None:
    if year is None:
        return None
    normalized = normalize_pub_year(year)
    if normalized is None:
        raise ValueError(
            f"{name} must be a valid year between {MIN_FILTER_YEAR} and {MAX_FILTER_YEAR}."
        )
    if not (MIN_FILTER_YEAR <= normalized <= MAX_FILTER_YEAR):
        raise ValueError(
            f"{name} must be between {MIN_FILTER_YEAR} and {MAX_FILTER_YEAR}."
        )
    return normalized


def _apply_metadata_filters(
    docs: list[Document],
    subfields: list[str],
    journal_categories: list[str],
    journal_codes: list[str],
    year_from: int | None,
    year_to: int | None,
) -> list[Document]:
    filtered: list[Document] = []
    for doc in docs:
        enrich_document_metadata(doc)
        doc_subfield = normalize_subfield(str(doc.metadata.get("subfield", "")))
        doc_category = normalize_journal_category(
            str(doc.metadata.get("journal_category", ""))
        )
        doc_journal_code = normalize_journal_code(str(doc.metadata.get("journal_code", "")))
        doc_pub_year = normalize_pub_year(doc.metadata.get("pub_year"))

        if subfields and doc_subfield not in subfields:
            continue
        if journal_categories and doc_category not in journal_categories:
            continue
        if journal_codes and doc_journal_code not in journal_codes:
            continue
        if year_from is not None and (doc_pub_year is None or doc_pub_year < year_from):
            continue
        if year_to is not None and (doc_pub_year is None or doc_pub_year > year_to):
            continue
        filtered.append(doc)
    return filtered


def _retrieve_local_docs(
    query: str,
    settings: Settings,
    top_k: int,
    subfields: list[str],
    journal_categories: list[str],
    journal_codes: list[str],
    year_from: int | None,
    year_to: int | None,
) -> list[Document]:
    if not index_exists(settings.index_dir):
        return []
    vectorstore = _load_vectorstore(settings.index_dir, settings.embedding_model)

    has_filters = bool(subfields or journal_categories or journal_codes or year_from or year_to)
    if not has_filters:
        docs = vectorstore.max_marginal_relevance_search(
            query,
            k=top_k,
            fetch_k=max(top_k * 4, 12),
        )
        for doc in docs:
            enrich_document_metadata(doc)
        return docs

    candidate_k = max(top_k * 40, 160)
    docs = vectorstore.similarity_search(query, k=candidate_k)
    filtered = _apply_metadata_filters(
        docs,
        subfields,
        journal_categories,
        journal_codes,
        year_from,
        year_to,
    )
    return filtered[:top_k]


def generate_review(
    query: str,
    settings: Settings,
    top_k: int | None = None,
    detail_level: DetailLevel = "standard",
    source_mode: SourceMode = "local_only",
    arxiv_max_results: int | None = None,
    subfields: list[str] | None = None,
    journal_categories: list[str] | None = None,
    journal_codes: list[str] | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
) -> RAGResult:
    effective_top_k = top_k if top_k is not None else settings.retrieve_top_k
    effective_arxiv_n = (
        arxiv_max_results if arxiv_max_results is not None else settings.arxiv_max_results
    )
    normalized_subfields = _normalize_subfields(subfields)
    normalized_categories = _normalize_journal_categories(journal_categories)
    normalized_journal_codes = _normalize_journal_codes(journal_codes)
    normalized_year_from = _normalize_year_bound("year_from", year_from)
    normalized_year_to = _normalize_year_bound("year_to", year_to)
    if (
        normalized_year_from is not None
        and normalized_year_to is not None
        and normalized_year_from > normalized_year_to
    ):
        raise ValueError("year_from cannot be greater than year_to.")

    local_docs: list[Document] = []
    arxiv_docs: list[Document] = []

    if source_mode in ("local_only", "local_plus_arxiv"):
        local_docs = _retrieve_local_docs(
            query=query,
            settings=settings,
            top_k=effective_top_k,
            subfields=normalized_subfields,
            journal_categories=normalized_categories,
            journal_codes=normalized_journal_codes,
            year_from=normalized_year_from,
            year_to=normalized_year_to,
        )
        if source_mode == "local_only" and not local_docs:
            if not index_exists(settings.index_dir):
                raise FileNotFoundError(
                    "Local FAISS index not found or empty. Build index first or switch source mode."
                )

    if source_mode in ("arxiv_only", "local_plus_arxiv"):
        arxiv_docs = search_arxiv_documents(query, max_results=effective_arxiv_n)
        arxiv_docs = _apply_metadata_filters(
            arxiv_docs,
            normalized_subfields,
            normalized_categories,
            normalized_journal_codes,
            normalized_year_from,
            normalized_year_to,
        )

    docs = local_docs + arxiv_docs
    if not docs:
        return RAGResult(
            query=query,
            answer=_build_no_evidence_answer(
                source_mode=source_mode,
                subfields=normalized_subfields,
                journal_categories=normalized_categories,
                journal_codes=normalized_journal_codes,
                year_from=normalized_year_from,
                year_to=normalized_year_to,
            ),
            citations=[],
            retrieved_docs=[],
            detail_level=detail_level,
            top_k=effective_top_k,
            source_mode=source_mode,
            local_result_count=len(local_docs),
            arxiv_result_count=len(arxiv_docs),
            subfields=normalized_subfields,
            journal_categories=normalized_categories,
            journal_codes=normalized_journal_codes,
            year_from=normalized_year_from,
            year_to=normalized_year_to,
        )

    context = _format_docs(docs)
    citation_candidates = _format_citation_candidates(docs)
    detail_guidance = DETAIL_GUIDANCE.get(detail_level, DETAIL_GUIDANCE["standard"])
    prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    llm = _get_llm(settings)
    answer = llm.invoke(
        prompt.format_messages(
            query=query,
            context=context,
            citation_candidates=citation_candidates,
            detail_guidance=detail_guidance,
        )
    ).content
    answer = str(answer)

    valid_citation_ids = {f"{d.metadata.get('source', '')}:{d.metadata.get('page', '')}" for d in docs}
    invalid_citations = _find_invalid_citations(answer, valid_citation_ids)
    if invalid_citations:
        repaired = llm.invoke(
            ChatPromptTemplate.from_template(CITATION_REPAIR_PROMPT).format_messages(
                valid_citation_ids="\n".join(f"- {cid}" for cid in sorted(valid_citation_ids)),
                draft=answer,
            )
        ).content
        answer = str(repaired)

    return RAGResult(
        query=query,
        answer=answer,
        citations=_dedupe_citations(docs),
        retrieved_docs=docs,
        detail_level=detail_level,
        top_k=effective_top_k,
        source_mode=source_mode,
        local_result_count=len(local_docs),
        arxiv_result_count=len(arxiv_docs),
        subfields=normalized_subfields,
        journal_categories=normalized_categories,
        journal_codes=normalized_journal_codes,
        year_from=normalized_year_from,
        year_to=normalized_year_to,
    )
