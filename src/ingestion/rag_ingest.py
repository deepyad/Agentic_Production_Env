"""
RAG ingestion: load PDFs → chunk text → write to Weaviate.

Run from project root:
  python -m src.ingestion --input-dir ./docs [--weaviate-url URL] [--index NAME] [--chunk-size 500] [--overlap 50] [--recreate]
  or: python -m src.ingestion.rag_ingest --input-dir ./docs ...
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

from ..config import config


# --- PDF extraction ---

def extract_text_from_pdf(path: str | Path) -> str:
    """Extract raw text from a PDF file. Requires pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise RuntimeError("PDF support requires pypdf. Install: pip install pypdf") from e

    path = Path(path)
    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise ValueError(f"Not a PDF file: {path}")

    reader = PdfReader(str(path))
    parts = []
    for page in reader.pages:
        try:
            text = page.extract_text()
            if text:
                parts.append(text)
        except Exception:
            continue
    return "\n\n".join(parts)


def list_pdfs(directory: str | Path) -> list[Path]:
    """List all PDF files under directory (non-recursive by default)."""
    directory = Path(directory)
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*.pdf"))


# --- Chunking ---

def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
    min_chunk_size: int = 20,
) -> Iterator[str]:
    """
    Split text into overlapping chunks by character count.
    Tries to break at sentence or word boundaries when possible.
    """
    text = (text or "").strip()
    if not text or len(text) < min_chunk_size:
        return

    # Prefer splitting on paragraph, then sentence, then space
    def split_points(s: str) -> list[int]:
        points = [0]
        for m in re.finditer(r"\n\n+|\n|[.!?]\s+|\s+", s):
            points.append(m.end())
        points.append(len(s))
        return sorted(set(points))

    points = split_points(text)
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end - start < min_chunk_size and start > 0:
            break
        # Snap end to nearest split point if we're not at the very end
        if end < len(text):
            best = start
            for p in points:
                if start < p <= end:
                    best = p
                elif p > end:
                    break
            if best > start:
                end = best
        chunk = text[start:end].strip()
        if chunk:
            yield chunk
        start = end - overlap
        if start >= len(text):
            break


# --- Weaviate write ---

def get_weaviate_client(url: str):
    """Return a connected Weaviate client (v4). Weaviate server needs OPENAI_APIKEY for text2vec-openai vectorizer."""
    import weaviate

    parsed = urlparse(url or "http://localhost:8080")
    host = parsed.hostname or "localhost"
    port = parsed.port or 8080
    secure = parsed.scheme == "https"

    if host in ("localhost", "127.0.0.1"):
        client = weaviate.connect_to_local(host=host, port=port, grpc_port=50051)
    else:
        client = weaviate.connect_to_custom(
            http_host=host,
            http_port=port,
            http_secure=secure,
        )
    return client


def ensure_collection(client, index_name: str, recreate: bool = False) -> None:
    """Create Weaviate collection with text2vec-openai if it does not exist (or recreate)."""
    from weaviate.classes.config import Configure, DataType, Property

    if recreate and client.collections.exists(index_name):
        client.collections.delete(index_name)

    if client.collections.exists(index_name):
        return

    client.collections.create(
        name=index_name,
        vectorizer_config=Configure.Vectors.text2vec_openai(),
        properties=[
            Property(name="content", data_type=DataType.TEXT),
            Property(name="source", data_type=DataType.TEXT),
        ],
    )


def insert_chunks_weaviate(
    client,
    index_name: str,
    chunks: list[tuple[str, str]],
) -> int:
    """Insert (content, source) chunks into Weaviate. Returns count inserted."""
    collection = client.collections.get(index_name)
    inserted = 0
    for content, source in chunks:
        if not (content or "").strip():
            continue
        collection.data.insert_one(properties={"content": content.strip(), "source": source or ""})
        inserted += 1
    return inserted


# --- Pipeline ---

def ingest_pdfs(
    input_dir: str | Path,
    weaviate_url: str = "",
    index_name: str = "RAGChunks",
    chunk_size: int = 500,
    overlap: int = 50,
    recreate: bool = False,
) -> tuple[int, int]:
    """
    Load all PDFs from input_dir, chunk text, and write to Weaviate.
    Returns (num_files_processed, num_chunks_inserted).
    """
    weaviate_url = weaviate_url or config.weaviate_url
    if not weaviate_url.strip():
        raise ValueError("WEAVIATE_URL is required for ingestion. Set it in .env or pass --weaviate-url")

    pdf_paths = list_pdfs(input_dir)
    if not pdf_paths:
        return 0, 0

    client = get_weaviate_client(weaviate_url)
    try:
        ensure_collection(client, index_name, recreate=recreate)
        all_chunks: list[tuple[str, str]] = []
        for path in pdf_paths:
            text = extract_text_from_pdf(path)
            source_label = path.name
            for chunk in chunk_text(text, chunk_size=chunk_size, overlap=overlap):
                all_chunks.append((chunk, source_label))
        inserted = insert_chunks_weaviate(client, index_name, all_chunks)
        return len(pdf_paths), inserted
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest PDF files into Weaviate for RAG. Requires WEAVIATE_URL and OPENAI_API_KEY (for vectorizer).",
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default="docs",
        help="Directory containing PDF files (default: docs)",
    )
    parser.add_argument(
        "--weaviate-url",
        type=str,
        default="",
        help="Weaviate URL (default: WEAVIATE_URL from env)",
    )
    parser.add_argument(
        "--index",
        type=str,
        default="",
        help="Weaviate collection name (default: WEAVIATE_INDEX or RAGChunks)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Target chunk size in characters (default: 500)",
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=50,
        help="Overlap between chunks in characters (default: 50)",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and recreate the collection before ingesting (destructive)",
    )
    args = parser.parse_args()

    index_name = (args.index or os.getenv("WEAVIATE_INDEX") or config.weaviate_index).strip() or "RAGChunks"
    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        print(f"Input directory not found: {input_dir}")
        return

    try:
        num_files, num_chunks = ingest_pdfs(
            input_dir=input_dir,
            weaviate_url=args.weaviate_url or None,
            index_name=index_name,
            chunk_size=args.chunk_size,
            overlap=args.overlap,
            recreate=args.recreate,
        )
        print(f"Ingested {num_files} PDF(s) → {num_chunks} chunks in Weaviate collection '{index_name}'.")
    except Exception as e:
        print(f"Ingestion failed: {e}")
        raise


if __name__ == "__main__":
    main()
