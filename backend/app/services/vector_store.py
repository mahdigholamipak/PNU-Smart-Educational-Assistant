from typing import Any

import chromadb

from app.config import settings
from app.services.llm_service import (
    _embed_batch_with_retry,
    get_embedding_function,
    resolve_api_keys,
    resolve_embedding_model,
)


def _get_chroma_client() -> chromadb.ClientAPI:
    """Return a persistent ChromaDB client."""
    settings.chroma_path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(settings.chroma_path))


def get_or_create_collection(course_id: int) -> Any:
    """Get (or create) the ChromaDB collection for a course."""
    client = _get_chroma_client()
    collection_name = f"course_{course_id}"
    return client.get_or_create_collection(
        name=collection_name,
        embedding_function=get_embedding_function(),
        metadata={"hnsw:space": "cosine"},
    )


def _embed_texts_with_retry(texts: list[str]) -> list[list[float]]:
    """Embed texts using the shared multi-key/backoff pipeline."""
    return _embed_batch_with_retry(
        texts=texts,
        model=resolve_embedding_model(),
        keys=resolve_api_keys(),
    )


def add_document_chunks(
    course_id: int,
    resource_id: int,
    filename: str,
    chunks: list[str],
) -> int:
    """Index document chunks into the course's ChromaDB collection.

    Chunks are embedded in configurable batches (to stay within the free-tier
    request budget) using multi-key round-robin + exponential backoff, then
    upserted into ChromaDB with precomputed embeddings. This avoids ChromaDB
    re-calling the embedding function (which would lose our retry logic) and
    prevents a large PDF from blowing the 429 rate limit on one single call.
    """
    collection = get_or_create_collection(course_id)

    ids = []
    documents = []
    metadatas = []
    all_embeddings = []

    batch_size = max(1, int(settings.embedding_batch_size))
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start:start + batch_size]
        embeddings = _embed_texts_with_retry(batch)
        for i, chunk in enumerate(batch):
            idx = start + i
            ids.append(f"res_{resource_id}_chunk_{idx}")
            documents.append(chunk)
            metadatas.append(
                {
                    "resource_id": resource_id,
                    "filename": filename,
                    "chunk_index": idx,
                }
            )
            all_embeddings.append(embeddings[i])

    if ids:
        collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=all_embeddings,
            metadatas=metadatas,
        )
    return len(ids)


def get_resource_chunks(course_id: int, resource_id: int) -> list[dict]:
    """Fetch all chunks belonging to a resource from ChromaDB (no embeddings)."""
    collection = get_or_create_collection(course_id)
    try:
        result = collection.get(
            where={"resource_id": resource_id},
            include=["documents", "metadatas"],
        )
    except Exception:
        return []

    ids = result.get("ids", []) or []
    documents = result.get("documents", []) or []
    metadatas = result.get("metadatas", []) or []

    chunks = []
    for idx, chunk_id in enumerate(ids):
        metadata = metadatas[idx] if idx < len(metadatas) else {}
        chunks.append(
            {
                "id": chunk_id,
                "chunk_index": int(metadata.get("chunk_index", idx)),
                "filename": metadata.get("filename", ""),
                "content": documents[idx] if idx < len(documents) else "",
            }
        )
    chunks.sort(key=lambda c: c["chunk_index"])
    return chunks


def update_chunk_content(
    course_id: int,
    chunk_id: str,
    new_content: str,
    embedding_fn: Any,
) -> None:
    """Update a single chunk's text and re-embed it so RAG search stays synced."""
    collection = get_or_create_collection(course_id)
    new_embeddings = _embed_texts_with_retry([new_content])
    collection.update(
        ids=[chunk_id],
        documents=[new_content],
        embeddings=[new_embeddings[0]],
    )


def delete_resource_chunks(course_id: int, resource_id: int) -> None:
    """Delete all chunks belonging to a resource from ChromaDB."""
    collection = get_or_create_collection(course_id)
    collection.delete(where={"resource_id": resource_id})


def delete_course_collection(course_id: int) -> None:
    """Delete the entire ChromaDB collection for a course."""
    client = _get_chroma_client()
    collection_name = f"course_{course_id}"
    try:
        client.delete_collection(collection_name)
    except ValueError:
        # Collection does not exist; nothing to delete
        pass


def search_course_documents(
    course_id: int,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """Search the course collection and return top-k matching chunks."""
    collection = get_or_create_collection(course_id)

    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    hits = []
    for idx, doc in enumerate(documents):
        metadata = metadatas[idx] if idx < len(metadatas) else {}
        distance = distances[idx] if idx < len(distances) else None
        hits.append(
            {
                "content": doc,
                "filename": metadata.get("filename", "ناشناخته"),
                "resource_id": metadata.get("resource_id", 0),
                "chunk_index": metadata.get("chunk_index", 0),
                "score": round(1 - float(distance), 4) if distance is not None else None,
            }
        )
    return hits