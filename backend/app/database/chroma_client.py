"""Chroma persistent collection for paper chunks."""

import chromadb

from app.config import settings

chroma_client = chromadb.PersistentClient(path=settings.chroma_dir)

collection = chroma_client.get_or_create_collection(
    name="paper_chunks",
    metadata={"hnsw:space": "cosine"},
)


def split_into_chunks(text: str, max_chars: int = 500) -> list[str]:
    """Split text by paragraphs while keeping chunks under max_chars where possible."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chars:
            current = f"{current}\n\n{para}" if current else para
            continue

        if current:
            chunks.append(current)

        if len(para) <= max_chars:
            current = para
        else:
            for start in range(0, len(para), max_chars):
                part = para[start:start + max_chars].strip()
                if part:
                    chunks.append(part)
            current = ""

    if current:
        chunks.append(current)

    return chunks


def index_paper_chunks(paper_id: str, text: str, max_chars: int = 500) -> int:
    """Upsert paper chunks into Chroma and return chunk count."""
    chunks = split_into_chunks(text, max_chars=max_chars)
    if not chunks:
        return 0

    ids = [f"{paper_id}:chunk:{i}" for i in range(len(chunks))]
    metadatas = [{"paper_id": paper_id, "chunk_index": i} for i in range(len(chunks))]

    collection.upsert(
        ids=ids,
        documents=chunks,
        metadatas=metadatas,
    )
    return len(chunks)
