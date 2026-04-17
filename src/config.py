from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    llm_model: str
    openai_api_key: str
    openai_base_url: str
    embedding_model: str
    retrieve_top_k: int
    arxiv_max_results: int
    raw_pdf_dir: Path
    processed_chunks_path: Path
    index_dir: Path


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        llm_provider=os.getenv("LLM_PROVIDER", "openai").strip().lower(),
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "").strip(),
        embedding_model=os.getenv(
            "EMBEDDING_MODEL",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        ).strip(),
        retrieve_top_k=int(os.getenv("RETRIEVE_TOP_K", "6")),
        arxiv_max_results=int(os.getenv("ARXIV_MAX_RESULTS", "3")),
        raw_pdf_dir=Path(os.getenv("RAW_PDF_DIR", "data/raw_pdfs")),
        processed_chunks_path=Path(
            os.getenv("PROCESSED_CHUNKS_PATH", "data/processed/chunks.jsonl")
        ),
        index_dir=Path(os.getenv("INDEX_DIR", "data/index/faiss")),
    )
