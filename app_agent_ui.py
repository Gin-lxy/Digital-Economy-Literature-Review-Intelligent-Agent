from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import Settings, load_settings
from src.evaluation import eval_to_dict, evaluate_generation
from src.indexing import index_exists, upsert_faiss_index
from src.metadata_taxonomy import (
    journal_category_label,
    list_supported_journal_codes,
    list_supported_journal_categories,
    list_supported_subfields,
    subfield_label,
)
from src.pdf_pipeline import (
    append_chunks_jsonl,
    chunk_documents,
    parse_pdf_to_documents,
    read_next_chunk_index,
)
from src.rag_chain import generate_review

st.set_page_config(
    page_title="RAG Scholar Ops Console",
    layout="wide",
)


def inject_styles() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

:root {
  --color-primary: #0F172A;
  --color-on-primary: #FFFFFF;
  --color-secondary: #334155;
  --color-accent: #0369A1;
  --color-background: #F8FAFC;
  --color-foreground: #020617;
  --color-muted: #E8ECF1;
  --color-border: #E2E8F0;
  --color-ring: #0F172A;
  --color-muted-text: #475569;
}

[data-testid="stAppViewContainer"] {
  background: var(--color-background);
}

.block-container {
  max-width: 1220px;
  padding-top: 1rem;
  padding-bottom: 2rem;
}

html, body, p, div, span, label, li {
  font-family: "Plus Jakarta Sans", "Segoe UI", sans-serif !important;
  color: var(--color-foreground);
}

h1, h2, h3, h4 {
  font-family: "Plus Jakarta Sans", "Segoe UI", sans-serif !important;
  letter-spacing: -0.01em;
}

[data-testid="stSidebar"] {
  border-right: 1px solid var(--color-border);
  background: #ffffff;
}

.app-hero {
  border: 1px solid var(--color-border);
  background: #ffffff;
  border-radius: 14px;
  padding: 16px 18px;
  margin-bottom: 12px;
}

.app-hero h1 {
  margin: 0;
  color: var(--color-primary);
  font-size: 1.28rem;
  font-weight: 800;
}

.app-hero p {
  margin: 8px 0 0 0;
  color: var(--color-muted-text);
  line-height: 1.7;
}

.kpi-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.kpi-item {
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: #ffffff;
  padding: 10px 12px;
}

.kpi-label {
  color: var(--color-muted-text);
  font-size: 0.78rem;
  margin-bottom: 4px;
}

.kpi-value {
  color: var(--color-primary);
  font-weight: 700;
  font-size: 1rem;
  word-break: break-word;
}

.panel {
  border: 1px solid var(--color-border);
  border-radius: 14px;
  background: #ffffff;
  padding: 14px;
}

.panel-title {
  color: var(--color-primary);
  font-size: 0.96rem;
  font-weight: 700;
  margin-bottom: 8px;
}

.hint {
  color: var(--color-muted-text);
  font-size: 0.84rem;
  line-height: 1.6;
}

.chip-row {
  margin: 2px 0 10px 0;
}

.chip {
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: #fff;
  color: var(--color-secondary);
  font-size: 0.78rem;
  padding: 4px 10px;
  margin-right: 8px;
  margin-bottom: 8px;
}

.review-box {
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: #ffffff;
  padding: 14px 16px;
}

.review-box p, .review-box li, .review-box h1, .review-box h2, .review-box h3 {
  line-height: 1.75;
}

[data-testid="stButton"] button {
  border-radius: 10px !important;
  transition: background-color 180ms ease, color 180ms ease, border-color 180ms ease;
}

[data-testid="stButton"] button[kind="primary"] {
  background: var(--color-accent) !important;
  border: 1px solid var(--color-accent) !important;
  color: var(--color-on-primary) !important;
}

[data-testid="stButton"] button[kind="primary"]:hover {
  background: #075985 !important;
  border-color: #075985 !important;
}

[data-baseweb="tab-list"] button {
  background: #f1f5f9;
  border-radius: 8px 8px 0 0;
}

[data-baseweb="tab-list"] button[aria-selected="true"] {
  background: #e2e8f0;
  color: #0f172a;
}

@media (max-width: 1024px) {
  .kpi-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .kpi-strip {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  * {
    transition: none !important;
  }
}
</style>
        """,
        unsafe_allow_html=True,
    )


def calc_word_count(text: str) -> int:
    return len([tok for tok in text.replace("\n", " ").split(" ") if tok.strip()])


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def sanitize_filename(name: str) -> str:
    clean = re.sub(r"[^\w.\- ]+", "_", Path(name).name)
    return clean[:180] if len(clean) > 180 else clean


def save_uploaded_files(uploaded_files: list, raw_pdf_dir: Path) -> list[Path]:
    raw_pdf_dir.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []
    for file in uploaded_files:
        base_name = sanitize_filename(file.name)
        target = raw_pdf_dir / base_name
        if target.exists():
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            target = raw_pdf_dir / f"{target.stem}_{ts}{target.suffix}"
        target.write_bytes(file.getvalue())
        saved_paths.append(target)
    return saved_paths


def ingest_uploaded_pdfs(uploaded_files: list, settings: Settings) -> dict:
    if not uploaded_files:
        return {"ok": False, "message": "No PDF files uploaded."}

    saved_paths = save_uploaded_files(uploaded_files, settings.raw_pdf_dir)
    next_idx = read_next_chunk_index(settings.processed_chunks_path)
    all_chunks = []
    failed_files: list[str] = []

    for pdf_path in saved_paths:
        try:
            docs = parse_pdf_to_documents(pdf_path)
            if not docs:
                failed_files.append(f"{pdf_path.name} (empty text)")
                continue
            chunks = chunk_documents(docs, start_index=next_idx)
            next_idx += len(chunks)
            all_chunks.extend(chunks)
        except Exception as exc:
            failed_files.append(f"{pdf_path.name} ({exc})")

    if not all_chunks:
        return {
            "ok": False,
            "message": "No valid chunks parsed from uploaded files.",
            "failed_files": failed_files,
        }

    append_chunks_jsonl(all_chunks, settings.processed_chunks_path)
    indexed = upsert_faiss_index(all_chunks, settings.index_dir, settings.embedding_model)
    return {
        "ok": True,
        "message": f"Ingestion completed. New chunks: {len(all_chunks)}, indexed: {indexed}.",
        "saved_count": len(saved_paths),
        "failed_files": failed_files,
    }


def init_state() -> None:
    st.session_state.setdefault("ui_history", [])
    st.session_state.setdefault("ui_last_result", None)
    st.session_state.setdefault("ui_last_reference", "")
    st.session_state.setdefault("ui_ingest_report", None)
    st.session_state.setdefault("ui_error", "")


inject_styles()
init_state()
settings = load_settings()
subfield_options = list_supported_subfields()
journal_category_options = list_supported_journal_categories()
journal_code_options = list_supported_journal_codes()

local_pdf_count = len(list(settings.raw_pdf_dir.glob("*.pdf")))
chunk_count = count_lines(settings.processed_chunks_path)
has_index = index_exists(settings.index_dir)

st.markdown(
    """
<div class="app-hero">
  <h1>RAG Scholar Ops Console</h1>
  <p>
    Internal workspace for corpus ingestion, evidence inspection, review generation,
    evaluation, and export. This console connects directly to the local pipeline,
    FAISS index, and runtime configuration used by the main agent product.
  </p>
</div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
<div class="kpi-strip">
  <div class="kpi-item">
    <div class="kpi-label">Local PDFs</div>
    <div class="kpi-value">{local_pdf_count}</div>
  </div>
  <div class="kpi-item">
    <div class="kpi-label">Chunk Records</div>
    <div class="kpi-value">{chunk_count}</div>
  </div>
  <div class="kpi-item">
    <div class="kpi-label">FAISS Index</div>
    <div class="kpi-value">{"Ready" if has_index else "Missing"}</div>
  </div>
  <div class="kpi-item">
    <div class="kpi-label">Model</div>
    <div class="kpi-value">{settings.llm_provider} / {settings.llm_model}</div>
  </div>
</div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### Data Ingestion")
    uploaded = st.file_uploader(
        "Upload PDF files",
        type=["pdf"],
        accept_multiple_files=True,
    )
    if st.button("Parse and Update Index", use_container_width=True):
        with st.spinner("Parsing PDFs and updating index..."):
            report = ingest_uploaded_pdfs(uploaded, settings)
        st.session_state["ui_ingest_report"] = report

    report = st.session_state.get("ui_ingest_report")
    if report:
        if report.get("ok"):
            st.success(report["message"])
        else:
            st.error(report["message"])
        for item in report.get("failed_files", []):
            st.caption(f"- {item}")

    st.divider()
    st.markdown("### Environment")
    st.caption(f"Raw dir: `{settings.raw_pdf_dir}`")
    st.caption(f"Index dir: `{settings.index_dir}`")
    st.caption(f"Embedding: `{settings.embedding_model}`")

    st.divider()
    if st.button("Reset Session", use_container_width=True):
        st.session_state["ui_history"] = []
        st.session_state["ui_last_result"] = None
        st.session_state["ui_last_reference"] = ""
        st.session_state["ui_error"] = ""
        st.rerun()

left, right = st.columns([2.15, 1], gap="large")

with left:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">Research Topic</div>', unsafe_allow_html=True)
    query = st.text_area(
        "Research Topic",
        value="How digital economy driven industrial restructuring affects regional employment quality",
        height=115,
        label_visibility="collapsed",
    )
    reference_text = st.text_area(
        "Optional reference review (for ROUGE-L)",
        value=st.session_state.get("ui_last_reference", ""),
        height=120,
    )
    st.markdown(
        '<div class="hint">Leave reference empty if you only need generation, not ROUGE-L comparison.</div>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">Generation Controls</div>', unsafe_allow_html=True)
    source_mode = st.selectbox(
        "Evidence source",
        options=["local_plus_arxiv", "local_only", "arxiv_only"],
        index=0,
    )
    detail_level = st.selectbox(
        "Detail level",
        options=["concise", "standard", "deep"],
        index=2,
    )
    top_k = st.slider(
        "Local top-k",
        min_value=3,
        max_value=12,
        value=max(3, min(12, settings.retrieve_top_k)),
        step=1,
    )
    arxiv_n = st.slider(
        "arXiv results",
        min_value=1,
        max_value=10,
        value=max(1, min(10, settings.arxiv_max_results)),
        step=1,
    )
    selected_subfields = st.multiselect(
        "Subfield filter",
        options=subfield_options,
        default=[],
        format_func=subfield_label,
    )
    selected_journal_categories = st.multiselect(
        "Journal category filter",
        options=journal_category_options,
        default=[],
        format_func=journal_category_label,
    )
    selected_journal_codes = st.multiselect(
        "Journal code filter",
        options=journal_code_options,
        default=[],
    )
    enable_year_filter = st.checkbox("Enable publication year filter", value=False)
    year_from = None
    year_to = None
    if enable_year_filter:
        year_from, year_to = st.slider(
            "Publication year range",
            min_value=2018,
            max_value=2025,
            value=(2018, 2025),
            step=1,
        )
    st.markdown("</div>", unsafe_allow_html=True)

run_col, _ = st.columns([1, 2.2])
with run_col:
    run_clicked = st.button("Generate Review", type="primary", use_container_width=True)

if run_clicked:
    st.session_state["ui_error"] = ""
    with st.spinner("Retrieving evidence and generating review..."):
        started = datetime.now()
        try:
            result = generate_review(
                query=query,
                settings=settings,
                top_k=top_k,
                detail_level=detail_level,
                source_mode=source_mode,
                arxiv_max_results=arxiv_n,
                subfields=selected_subfields or None,
                journal_categories=selected_journal_categories or None,
                journal_codes=selected_journal_codes or None,
                year_from=year_from,
                year_to=year_to,
            )
            elapsed = (datetime.now() - started).total_seconds()
            st.session_state["ui_last_result"] = result
            st.session_state["ui_last_reference"] = reference_text
            st.session_state["ui_history"].insert(
                0,
                {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "query": query,
                    "source_mode": source_mode,
                    "detail_level": detail_level,
                    "subfields": ", ".join(result.subfields) if result.subfields else "all",
                    "journal_categories": ", ".join(result.journal_categories)
                    if result.journal_categories
                    else "all",
                    "journal_codes": ", ".join(result.journal_codes)
                    if result.journal_codes
                    else "all",
                    "year_range": (
                        f"{result.year_from}-{result.year_to}"
                        if result.year_from is not None or result.year_to is not None
                        else "all"
                    ),
                    "local_results": result.local_result_count,
                    "arxiv_results": result.arxiv_result_count,
                    "latency_sec": round(elapsed, 2),
                },
            )
        except Exception as exc:
            st.session_state["ui_error"] = str(exc)
            st.session_state["ui_last_result"] = None

if st.session_state.get("ui_error"):
    st.error(f"Generation failed: {st.session_state['ui_error']}")

history = st.session_state["ui_history"]
if history:
    with st.expander("Run History", expanded=False):
        history_df = pd.DataFrame(history)[
            [
                "time",
                "query",
                "source_mode",
                "detail_level",
                "subfields",
                "journal_categories",
                "journal_codes",
                "year_range",
                "local_results",
                "arxiv_results",
                "latency_sec",
            ]
        ]
        st.dataframe(history_df, hide_index=True, use_container_width=True)

if st.session_state.get("ui_last_result") is not None:
    result = st.session_state["ui_last_result"]
    reference_text = st.session_state.get("ui_last_reference", "")

    metrics = evaluate_generation(
        generated_text=result.answer,
        citations=result.citations,
        retrieved_contexts=[doc.page_content for doc in result.retrieved_docs],
        reference_text=reference_text,
    )
    metric_dict = eval_to_dict(metrics)

    source_counts = {"local_pdf": 0, "arxiv": 0, "other": 0}
    for doc in result.retrieved_docs:
        source_type = str(doc.metadata.get("source_type", "other"))
        if source_type in source_counts:
            source_counts[source_type] += 1
        else:
            source_counts["other"] += 1

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Characters", len(result.answer))
    m2.metric("Words", calc_word_count(result.answer))
    m3.metric("Citations", len(result.citations))
    m4.metric("Local Chunks", source_counts["local_pdf"])
    m5.metric("arXiv Chunks", source_counts["arxiv"])
    m6.metric("ROUGE-L F1", metric_dict["rouge_l_f1"])

    subfield_text = ", ".join(subfield_label(v) for v in result.subfields) if result.subfields else "All"
    journal_text = (
        ", ".join(journal_category_label(v) for v in result.journal_categories)
        if result.journal_categories
        else "All"
    )
    journal_code_text = ", ".join(result.journal_codes) if result.journal_codes else "All"
    year_text = (
        f"{result.year_from or 'Any'} - {result.year_to or 'Any'}"
        if result.year_from is not None or result.year_to is not None
        else "All"
    )
    st.markdown(
        f"""
<div class="chip-row">
  <span class="chip">Subfields: {subfield_text}</span>
  <span class="chip">Journal categories: {journal_text}</span>
  <span class="chip">Journal codes: {journal_code_text}</span>
  <span class="chip">Publication year: {year_text}</span>
</div>
        """,
        unsafe_allow_html=True,
    )

    tab_review, tab_evidence, tab_quality, tab_export = st.tabs(
        ["Generated Review", "Evidence", "Quality", "Export"]
    )

    with tab_review:
        st.markdown('<div class="review-box">', unsafe_allow_html=True)
        st.markdown(result.answer)
        st.markdown("</div>", unsafe_allow_html=True)
        st.download_button(
            "Download Review (.md)",
            data=result.answer,
            file_name=f"review_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            mime="text/markdown",
        )

    with tab_evidence:
        st.subheader("Citation List")
        if result.citations:
            for cite in result.citations:
                st.write(f"- `{cite}`")
        else:
            st.info("No citations extracted from retrieved evidence.")

        st.subheader("Retrieved Evidence Overview")
        table = pd.DataFrame(
            [
                {
                    "source_type": d.metadata.get("source_type", ""),
                    "source": d.metadata.get("source", ""),
                    "title": d.metadata.get("title", ""),
                    "journal_code": d.metadata.get("journal_code", ""),
                    "journal_category": d.metadata.get("journal_category", ""),
                    "subfield": d.metadata.get("subfield", ""),
                    "pub_year": d.metadata.get("pub_year", ""),
                    "page": d.metadata.get("page", ""),
                    "url": d.metadata.get("url", ""),
                    "text_preview": d.page_content[:220],
                }
                for d in result.retrieved_docs
            ]
        )
        st.dataframe(table, use_container_width=True, hide_index=True)

        st.subheader("Evidence Details")
        for i, doc in enumerate(result.retrieved_docs, start=1):
            src = doc.metadata.get("source", "unknown")
            page = doc.metadata.get("page", "NA")
            title = doc.metadata.get("title", "")
            source_type = doc.metadata.get("source_type", "unknown")
            subfield = doc.metadata.get("subfield", "other")
            journal_category = doc.metadata.get("journal_category", "other")
            journal_code = doc.metadata.get("journal_code", "UNKNOWN")
            pub_year = doc.metadata.get("pub_year", "")
            with st.expander(f"[{i}] {source_type} | {src}:{page} | {title}", expanded=False):
                st.caption(
                    f"Subfield: {subfield_label(str(subfield))} | "
                    f"Journal Category: {journal_category_label(str(journal_category))} | "
                    f"Journal Code: {journal_code} | "
                    f"Year: {pub_year or 'NA'}"
                )
                st.write(doc.page_content)
                if doc.metadata.get("url"):
                    st.caption(f"URL: {doc.metadata['url']}")

    with tab_quality:
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("ROUGE-L F1", metric_dict["rouge_l_f1"])
        q2.metric("Citation Coverage", metric_dict["citation_coverage"])
        q3.metric("Context Overlap", metric_dict["context_overlap"])
        q4.metric("Citation Count", metric_dict["citation_count"])
        if not reference_text.strip():
            st.info("Reference text is empty, so ROUGE-L is not comparable yet.")
        st.json(metric_dict)

    with tab_export:
        export_payload = {
            "generated_at": datetime.now().isoformat(),
            "query": result.query,
            "detail_level": result.detail_level,
            "source_mode": result.source_mode,
            "top_k": result.top_k,
            "subfields": result.subfields,
            "journal_categories": result.journal_categories,
            "journal_codes": result.journal_codes,
            "year_from": result.year_from,
            "year_to": result.year_to,
            "local_result_count": result.local_result_count,
            "arxiv_result_count": result.arxiv_result_count,
            "answer": result.answer,
            "citations": result.citations,
            "metrics": metric_dict,
            "retrieved_docs": [
                {
                    "source_type": d.metadata.get("source_type", ""),
                    "source": d.metadata.get("source", ""),
                    "title": d.metadata.get("title", ""),
                    "page": d.metadata.get("page", ""),
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
        json_data = json.dumps(export_payload, ensure_ascii=False, indent=2)
        st.download_button(
            "Download Full Result (.json)",
            data=json_data,
            file_name=f"review_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
        )
        st.code(
            json_data[:3000] + ("\n..." if len(json_data) > 3000 else ""),
            language="json",
        )
