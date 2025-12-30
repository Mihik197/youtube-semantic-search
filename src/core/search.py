# src/core/search.py
from src.config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_DB_PATH,
    DEFAULT_SEARCH_RESULTS,
    EMBEDDING_MODEL_NAME,
    GEMINI_API_KEY,
)
from src.services.embedding_service import EmbeddingService
from src.services.vectordb_service import VectorDBService


def _is_deleted(meta) -> bool:
    return isinstance(meta, dict) and meta.get("is_deleted") is True


def search_videos(query: str, n_results: int = DEFAULT_SEARCH_RESULTS):
    """Perform a semantic search and return the raw Chroma response."""
    query = (query or "").strip()
    if not query:
        return None

    embedding_service = EmbeddingService(api_key=GEMINI_API_KEY, model_name=EMBEDDING_MODEL_NAME)
    vectordb_service = VectorDBService(path=CHROMA_DB_PATH, collection_name=CHROMA_COLLECTION_NAME)

    query_embedding = embedding_service.embed_query(query)
    if not query_embedding:
        return None

    n_results = max(1, int(n_results or DEFAULT_SEARCH_RESULTS))
    fetch_n = min(max(n_results * 4, n_results), 200)
    raw = vectordb_service.query(query_embedding=query_embedding, n_results=fetch_n) or {}

    ids = (raw.get("ids") or [[]])[0]
    if not ids:
        return raw

    distances = (raw.get("distances") or [[]])[0]
    metadatas = (raw.get("metadatas") or [[]])[0]
    documents = (raw.get("documents") or [[]])[0]

    keep = [idx for idx, meta in enumerate(metadatas) if not _is_deleted(meta)][:n_results]

    return {
        **raw,
        "ids": [[ids[i] for i in keep]],
        "distances": [[distances[i] for i in keep if i < len(distances)]],
        "metadatas": [[metadatas[i] for i in keep]],
        "documents": [[documents[i] for i in keep if i < len(documents)]],
    }
