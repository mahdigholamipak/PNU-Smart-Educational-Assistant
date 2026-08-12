from typing import Any

import chromadb

from app.config import settings
from app.services.llm_service import get_embedding_function


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
    """Index document chunks into the course's ChromaDB collection."""
    collection = get_or_create_collection(course_id)

    ids = [f"res_{resource_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "resource_id": resource_id,
            "filename": filename,
            "chunk_index": i,
        }
        for i in range(len(chunks))
    ]

    collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)
    return len(chunks)


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