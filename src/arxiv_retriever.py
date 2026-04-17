from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.documents import Document

from src.metadata_taxonomy import enrich_metadata


@dataclass
class ArxivPaper:
    paper_id: str
    title: str
    summary: str
    published: str
    url: str


def _extract_arxiv_id(entry: Any) -> str:
    if hasattr(entry, "entry_id") and isinstance(entry.entry_id, str):
        return entry.entry_id.rsplit("/", 1)[-1]
    if hasattr(entry, "get_short_id"):
        try:
            return str(entry.get_short_id())
        except Exception:
            pass
    return "unknown"


def search_arxiv_papers(query: str, max_results: int = 3) -> list[ArxivPaper]:
    try:
        import arxiv
    except ImportError as exc:
        raise RuntimeError("Missing dependency: arxiv. Run `pip install arxiv`.") from exc

    client = arxiv.Client(page_size=max_results, delay_seconds=0.2, num_retries=2)
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
    )

    papers: list[ArxivPaper] = []
    for result in client.results(search):
        paper_id = _extract_arxiv_id(result)
        published = ""
        try:
            published = result.published.strftime("%Y-%m-%d")
        except Exception:
            published = ""

        papers.append(
            ArxivPaper(
                paper_id=paper_id,
                title=str(getattr(result, "title", "")).strip(),
                summary=str(getattr(result, "summary", "")).strip(),
                published=published,
                url=str(getattr(result, "entry_id", "")).strip(),
            )
        )
    return papers


def search_arxiv_documents(query: str, max_results: int = 3) -> list[Document]:
    papers = search_arxiv_papers(query=query, max_results=max_results)
    docs: list[Document] = []
    for idx, paper in enumerate(papers, start=1):
        content = (
            f"Title: {paper.title}\n"
            f"Published: {paper.published}\n"
            f"URL: {paper.url}\n"
            f"Abstract: {paper.summary}"
        )
        metadata = enrich_metadata(
            {
                "chunk_id": f"arxiv_{idx:04d}",
                "source": f"arXiv:{paper.paper_id}",
                "title": paper.title,
                "page": "abs",
                "source_type": "arxiv",
                "url": paper.url,
                "published": paper.published,
                "journal_code": "ARXIV",
                "journal_category": "preprint",
            },
            text=paper.summary,
        )
        docs.append(
            Document(
                page_content=content,
                metadata=metadata,
            )
        )
    return docs
