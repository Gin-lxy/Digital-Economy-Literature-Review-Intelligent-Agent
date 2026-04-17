from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from tqdm import tqdm

from src.metadata_taxonomy import enrich_metadata


def _embedding_model(embedding_model: str) -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=embedding_model,
        encode_kwargs={"batch_size": 64, "normalize_embeddings": True},
    )


def index_exists(index_dir: Path) -> bool:
    return (index_dir / "index.faiss").exists() and (index_dir / "index.pkl").exists()


def _row_to_document(row: dict) -> Document:
    return Document(
        page_content=row["text"],
        metadata=enrich_metadata(
            {
                "chunk_id": row.get("chunk_id", ""),
                "source": row.get("source", ""),
                "title": row.get("title", ""),
                "page": row.get("page", 0),
                "source_type": row.get("source_type", "local_pdf"),
                "published": row.get("published", ""),
                "pub_year": row.get("pub_year"),
                "journal_code": row.get("journal_code", ""),
                "journal_category": row.get("journal_category", ""),
                "subfield": row.get("subfield", ""),
            },
            text=row.get("text", ""),
        ),
    )


def _count_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def iter_chunks_jsonl(chunks_path: Path) -> Iterator[Document]:
    if not chunks_path.exists():
        raise FileNotFoundError(f"Chunk file not found: {chunks_path.resolve()}")

    with chunks_path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON at line {line_num} in {chunks_path.resolve()}"
                ) from exc
            try:
                yield _row_to_document(row)
            except KeyError as exc:
                raise KeyError(
                    f"Missing required field {exc} at line {line_num} in "
                    f"{chunks_path.resolve()}"
                ) from exc


def load_chunks_jsonl(chunks_path: Path) -> list[Document]:
    return list(iter_chunks_jsonl(chunks_path))


def load_faiss_index(index_dir: Path, embedding_model: str) -> FAISS:
    embeddings = _embedding_model(embedding_model)
    return FAISS.load_local(
        str(index_dir), embeddings, allow_dangerous_deserialization=True
    )


def build_faiss_index(
    chunks_path: Path,
    index_dir: Path,
    embedding_model: str,
    batch_size: int = 256,
    max_chunks: int | None = None,
) -> int:
    if batch_size <= 0:
        raise ValueError("batch_size must be a positive integer.")

    total_chunks = _count_lines(chunks_path)
    if total_chunks == 0:
        raise ValueError("No chunk documents found to index.")
    if max_chunks is not None:
        if max_chunks <= 0:
            raise ValueError("max_chunks must be a positive integer when provided.")
        total_chunks = min(total_chunks, max_chunks)

    embeddings = _embedding_model(embedding_model)
    vectorstore: FAISS | None = None
    batch: list[Document] = []
    indexed = 0
    selected = 0

    with tqdm(total=total_chunks, desc="Building FAISS index", unit="chunk") as progress:
        for doc in iter_chunks_jsonl(chunks_path):
            if max_chunks is not None and selected >= max_chunks:
                break
            batch.append(doc)
            selected += 1
            if len(batch) < batch_size:
                continue

            if vectorstore is None:
                vectorstore = FAISS.from_documents(batch, embeddings)
            else:
                vectorstore.add_documents(batch)
            indexed += len(batch)
            progress.update(len(batch))
            batch = []

        if batch:
            if vectorstore is None:
                vectorstore = FAISS.from_documents(batch, embeddings)
            else:
                vectorstore.add_documents(batch)
            indexed += len(batch)
            progress.update(len(batch))

    if vectorstore is None:
        raise ValueError("No chunk documents found to index.")

    index_dir.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(index_dir))
    return indexed


def upsert_faiss_index(
    docs: list[Document],
    index_dir: Path,
    embedding_model: str,
) -> int:
    if not docs:
        return 0
    embeddings = _embedding_model(embedding_model)

    if index_exists(index_dir):
        vectorstore = FAISS.load_local(
            str(index_dir), embeddings, allow_dangerous_deserialization=True
        )
        vectorstore.add_documents(docs)
    else:
        vectorstore = FAISS.from_documents(docs, embeddings)

    index_dir.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(index_dir))
    return len(docs)
