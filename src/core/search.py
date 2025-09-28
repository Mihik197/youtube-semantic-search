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

    return vectordb_service.query(query_embedding=query_embedding, n_results=n_results)
