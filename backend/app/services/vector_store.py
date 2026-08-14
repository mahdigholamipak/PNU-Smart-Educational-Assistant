from typing import Any

import chromadb

from app.config import settings
from app.services.embedding_manager import embed_batches_managed, key_manager
from app.services.llm_service import (
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


def add_document_chunks(
    course_id: int,
    resource_id: int,
    filename: str,
    chunks: list[str],
) -> int:
    """Index document chunks into the course's ChromaDB collection.

    Fully decoupled embedding pipeline:
      1. All chunks are embedded manually by :func:`embed_batches_managed`
         (raw Gemini REST ``batchEmbedContents``, proactive key rotation,
         per-key cooldown, granular 429 retry at the batch level).
      2. The pre-computed embeddings are passed directly to ChromaDB's
         ``upsert``, bypassing Chroma's internal embedding-function call
         entirely (so ChromaDB never triggers Gemini API calls during upload).
    """
    collection = get_or_create_collection(course_id)

    if not chunks:
        return 0

    # Manual, decoupled embedding of ALL chunks via the smart key manager.
    keys = resolve_api_keys()
    key_manager.configure(keys)
    all_embeddings = embed_batches_managed(
        chunks=chunks,
        model=resolve_embedding_model(),
    )

    ids = [f"res_{resource_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "resource_id": resource_id,
            "filename": filename,
            "chunk_index": i,
        }
        for i in range(len(chunks))
    ]

    collection.upsert(
        ids=ids,
        documents=chunks,
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
    # Embed through the same decoupled manager (raw REST, smart key rotation).
    keys = resolve_api_keys()
    key_manager.configure(keys)
    new_embeddings = embed_batches_managed([new_content], resolve_embedding_model())
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