from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from pypdf.errors import DependencyError
from tqdm import tqdm

from src.metadata_taxonomy import enrich_metadata


@dataclass
class ChunkRecord:
    chunk_id: str
    text: str
    source: str
    title: str
    page: int
    source_type: str
    published: str
    pub_year: int | None
    journal_code: str
    journal_category: str
    subfield: str


def _aes_dependency_error(pdf_path: Path) -> RuntimeError:
    return RuntimeError(
        f"Failed to parse '{pdf_path.name}': AES-encrypted PDFs require "
        "the 'cryptography>=3.1' package. Install dependencies with "
        "'pip install -r requirements.txt' and rerun."
    )


def _clean_text(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            lines.append("")
            continue
        if re.fullmatch(r"\d{1,4}", line):
            continue
        if len(line) <= 2:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _guess_title(first_page_text: str, fallback: str) -> str:
    for line in first_page_text.splitlines():
        stripped = line.strip()
        if 4 <= len(stripped) <= 200:
            return stripped
    return fallback


def parse_pdf_to_documents(pdf_path: Path) -> list[Document]:
    try:
        reader = PdfReader(str(pdf_path))
    except DependencyError as exc:
        raise _aes_dependency_error(pdf_path) from exc
    if reader.is_encrypted:
        try:
            decrypted = reader.decrypt("")
        except DependencyError as exc:
            raise _aes_dependency_error(pdf_path) from exc
        if not decrypted:
            raise RuntimeError(
                f"Failed to parse '{pdf_path.name}': this PDF is password-protected "
                "and cannot be parsed automatically."
            )

    page_texts: list[str] = []
    try:
        for page in reader.pages:
            page_texts.append(_clean_text(page.extract_text() or ""))
    except DependencyError as exc:
        raise _aes_dependency_error(pdf_path) from exc

    non_empty = [txt for txt in page_texts if txt.strip()]
    title = _guess_title(non_empty[0], pdf_path.stem) if non_empty else pdf_path.stem

    docs: list[Document] = []
    base_metadata = enrich_metadata(
        {
            "source": pdf_path.name,
            "title": title,
            "source_type": "local_pdf",
        }
    )
    for page_idx, text in enumerate(page_texts, start=1):
        if not text.strip():
            continue
        metadata = dict(base_metadata)
        metadata["page"] = page_idx
        docs.append(
            Document(
                page_content=text,
                metadata=metadata,
            )
        )
    return docs


def chunk_documents(
    docs: Iterable[Document],
    chunk_size: int = 800,
    chunk_overlap: int = 120,
    start_index: int = 0,
) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", ".", " ", ""],
    )
    chunks = splitter.split_documents(list(docs))
    for i, chunk in enumerate(chunks, start=start_index):
        chunk.metadata = enrich_metadata(chunk.metadata, text=chunk.page_content)
        chunk.metadata["chunk_id"] = f"chunk_{i:06d}"
        chunk.metadata["source_type"] = str(
            chunk.metadata.get("source_type", "local_pdf")
        )
    return chunks


def _write_chunks_jsonl(
    chunks: Iterable[Document],
    output_path: Path,
    mode: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open(mode, encoding="utf-8") as f:
        for chunk in chunks:
            metadata = enrich_metadata(chunk.metadata, text=chunk.page_content)
            chunk.metadata = metadata
            record = ChunkRecord(
                chunk_id=metadata["chunk_id"],
                text=chunk.page_content,
                source=str(metadata.get("source", "")),
                title=str(metadata.get("title", "")),
                page=int(metadata.get("page", 0)),
                source_type=str(metadata.get("source_type", "local_pdf")),
                published=str(metadata.get("published", "")),
                pub_year=metadata.get("pub_year"),
                journal_code=str(metadata.get("journal_code", "UNKNOWN")),
                journal_category=str(metadata.get("journal_category", "other")),
                subfield=str(metadata.get("subfield", "other")),
            )
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def write_chunks_jsonl(chunks: Iterable[Document], output_path: Path) -> None:
    _write_chunks_jsonl(chunks, output_path, mode="w")


def append_chunks_jsonl(chunks: Iterable[Document], output_path: Path) -> None:
    _write_chunks_jsonl(chunks, output_path, mode="a")


def read_next_chunk_index(chunks_path: Path) -> int:
    if not chunks_path.exists():
        return 0
    max_idx = -1
    with chunks_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            chunk_id = str(row.get("chunk_id", ""))
            match = re.match(r"chunk_(\d+)$", chunk_id)
            if not match:
                continue
            max_idx = max(max_idx, int(match.group(1)))
    return max_idx + 1


def parse_and_chunk_pdfs(
    pdf_paths: list[Path],
    chunk_size: int = 800,
    chunk_overlap: int = 120,
    start_index: int = 0,
) -> list[Document]:
    page_docs: list[Document] = []
    for pdf_path in pdf_paths:
        page_docs.extend(parse_pdf_to_documents(pdf_path))
    return chunk_documents(
        page_docs,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        start_index=start_index,
    )


def build_corpus(
    raw_pdf_dir: Path,
    output_chunks_path: Path,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> tuple[int, int]:
    pdf_files = sorted(raw_pdf_dir.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(
            f"No PDF files found in {raw_pdf_dir.resolve()}."
            " Add your papers and rerun."
        )

    page_docs: list[Document] = []
    for pdf_file in tqdm(pdf_files, desc="Parsing PDFs"):
        page_docs.extend(parse_pdf_to_documents(pdf_file))

    chunks = chunk_documents(page_docs, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    write_chunks_jsonl(chunks, output_chunks_path)
    return len(pdf_files), len(chunks)
