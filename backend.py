from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.config import load_settings
from src.metadata_taxonomy import (
    journal_category_label,
    list_supported_journal_categories,
    list_supported_journal_codes,
    list_supported_subfields,
    subfield_label,
)
from src.rag_chain import MAX_FILTER_YEAR, MIN_FILTER_YEAR, generate_review


app = FastAPI(
    title="RAG Scholar Agent API",
    description="Production API for the RAG Scholar literature review agent.",
    version="2.0.0",
)

# CORS for local frontend development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LiteratureQuery(BaseModel):
    """Request payload for literature review generation."""

    query: str = Field(
        ...,
        description="Research question or keyword query",
        min_length=2,
        max_length=500,
    )
    detail_level: str = Field(
        "standard",
        description="Output detail level",
        pattern="^(concise|standard|deep)$",
    )
    source_mode: str = Field(
        "local_plus_arxiv",
        description="Evidence source mode",
        pattern="^(local_only|arxiv_only|local_plus_arxiv)$",
    )
    top_k: Optional[int] = Field(None, description="Local retrieval result count")
    arxiv_max_results: Optional[int] = Field(None, description="Maximum arXiv results")
    subfields: Optional[list[str]] = Field(None, description="Subfield filters")
    journal_categories: Optional[list[str]] = Field(None, description="Journal category filters")
    journal_codes: Optional[list[str]] = Field(None, description="Journal code filters")
    year_from: Optional[int] = Field(None, description="Publication year lower bound")
    year_to: Optional[int] = Field(None, description="Publication year upper bound")


class LiteratureResponse(BaseModel):
    """Response payload for review generation."""

    query: str
    review: str
    metadata: dict
    sources: list[dict]
    status: str = "success"


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    message: str
    llm_configured: bool


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check API and backend health."""

    try:
        settings = load_settings()
        return {
            "status": "healthy",
            "message": "RAG API is running normally",
            "llm_configured": bool(
                settings.openai_api_key or settings.llm_provider != "openai"
            ),
        }
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Health check failed: {exc}")


@app.post("/api/generate-review", response_model=LiteratureResponse)
async def generate_literature_review(request: LiteratureQuery):
    """Generate a literature review from user query and retrieval settings."""

    try:
        settings = load_settings()

        result = generate_review(
            query=request.query,
            settings=settings,
            top_k=request.top_k,
            detail_level=request.detail_level,
            source_mode=request.source_mode,
            arxiv_max_results=request.arxiv_max_results,
            subfields=request.subfields,
            journal_categories=request.journal_categories,
            journal_codes=request.journal_codes,
            year_from=request.year_from,
            year_to=request.year_to,
        )

        return {
            "query": request.query,
            "review": result.answer,
            "metadata": {
                "detail_level": request.detail_level,
                "source_mode": request.source_mode,
                "top_k": result.top_k,
                "local_documents_count": result.local_result_count,
                "arxiv_documents_count": result.arxiv_result_count,
                "subfields": result.subfields,
                "journal_categories": result.journal_categories,
                "journal_codes": result.journal_codes,
                "year_from": result.year_from,
                "year_to": result.year_to,
                "total_tokens": 0,
            },
            "sources": [
                {
                    "id": doc.metadata.get("source", "unknown"),
                    "title": doc.metadata.get("title", "Untitled"),
                    "source_type": doc.metadata.get("source_type", "local"),
                    "page": doc.metadata.get("page", 0),
                    "journal_code": doc.metadata.get("journal_code", "UNKNOWN"),
                    "journal_category": doc.metadata.get("journal_category", "other"),
                    "pub_year": doc.metadata.get("pub_year"),
                }
                for doc in result.retrieved_docs
            ],
        }
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=(
                "Index or processed data file not found: "
                f"{exc}. Please run scripts/build_corpus.py and scripts/build_index.py first."
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid request parameter: {exc}")
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Review generation failed: {exc}")


@app.get("/api/config")
async def get_config():
    """Return non-sensitive runtime configuration."""

    try:
        settings = load_settings()
        return {
            "app_name": "RAG Scholar Agent",
            "llm_model": settings.llm_model,
            "llm_provider": settings.llm_provider,
            "retrieve_top_k": settings.retrieve_top_k,
            "arxiv_max_results": settings.arxiv_max_results,
            "embedding_model": settings.embedding_model,
            "supported_journal_codes": list_supported_journal_codes(),
            "journal_code_options": [
                {"value": code, "label": code}
                for code in list_supported_journal_codes()
            ],
            "subfield_options": [
                {"value": item, "label": subfield_label(item)}
                for item in list_supported_subfields()
            ],
            "journal_category_options": [
                {"value": item, "label": journal_category_label(item)}
                for item in list_supported_journal_categories()
            ],
            "year_filter_min": MIN_FILTER_YEAR,
            "year_filter_max": MAX_FILTER_YEAR,
        }
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Failed to load config: {exc}")


@app.get("/api/index-status")
async def get_index_status():
    """Return FAISS index and chunk file status."""

    try:
        settings = load_settings()
        index_path = settings.index_dir / "index.faiss"
        chunks_path = settings.processed_chunks_path

        status = {
            "index_exists": index_path.exists(),
            "chunks_exists": chunks_path.exists(),
            "index_size_mb": 0,
            "chunks_count": 0,
        }

        if status["index_exists"]:
            status["index_size_mb"] = round(index_path.stat().st_size / (1024 * 1024), 2)

        if status["chunks_exists"]:
            with open(chunks_path, "r", encoding="utf-8") as file:
                status["chunks_count"] = sum(1 for _ in file)

        return status
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Failed to get index status: {exc}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
