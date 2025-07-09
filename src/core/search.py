# src/core/search.py
from src.services.embedding_service import EmbeddingService
from src.services.vectordb_service import VectorDBService
from src.config import DEFAULT_SEARCH_RESULTS, EMBEDDING_MODEL_NAME, TASK_TYPE_RETRIEVAL_QUERY, GEMINI_API_KEY, CHROMA_DB_PATH, CHROMA_COLLECTION_NAME

def search_videos(query: str, n_results: int = DEFAULT_SEARCH_RESULTS):
    """Performs semantic search using Gemini query embedding and ChromaDB."""
    if not query:
        print("Please provide a search query.")
        return None

    try:
        embedding_service = EmbeddingService(api_key=GEMINI_API_KEY, model_name=EMBEDDING_MODEL_NAME)
        vectordb_service = VectorDBService(path=CHROMA_DB_PATH, collection_name=CHROMA_COLLECTION_NAME)

        print(f"Embedding query: '{query}'...")
        query_embedding = embedding_service.embed_query(query)

        if not query_embedding:
            print("Error: Could not extract embedding vector from query response.")
            return None

        print(f"Querying ChromaDB for top {n_results} results...")
        results = vectordb_service.query(
            query_embedding=query_embedding,
            n_results=n_results
        )
        return results

    except Exception as e:
        print(f"Error during search for query '{query}': {e}")
        return None
