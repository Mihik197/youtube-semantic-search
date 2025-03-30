# search_app.py
import sys
import config
from embedding_utils import initialize_gemini_client
from google.genai import types
# Assuming shared functions are still in main_search or moved to common_utils
from main_search import (
    initialize_chromadb_client,
    # search_videos # Remove this if defined below
)

# Define search_videos locally or import if kept elsewhere
def search_videos_local(query, gemini_client, chroma_collection, n_results=config.DEFAULT_SEARCH_RESULTS):
    """Performs semantic search using Gemini query embedding and ChromaDB."""
    # ... (embedding logic remains the same) ...
    if not query:
        print("Please provide a search query.")
        return None
    if not gemini_client or not chroma_collection:
        print("Error: Gemini client or ChromaDB collection not initialized.")
        return None
    try:
        print(f"Embedding query: '{query}'...")
        query_embedding_result = gemini_client.models.embed_content(
            model=config.EMBEDDING_MODEL_NAME,
            contents=[query],
            config=types.EmbedContentConfig(
                 task_type=config.TASK_TYPE_RETRIEVAL_QUERY
            )
        )
        query_embedding = None
        if hasattr(query_embedding_result, 'embeddings') and isinstance(query_embedding_result.embeddings, list) and query_embedding_result.embeddings:
            first_embedding = query_embedding_result.embeddings[0]
            if hasattr(first_embedding, 'values') and first_embedding.values is not None:
                query_embedding = first_embedding.values
        elif hasattr(query_embedding_result, 'embedding') and hasattr(query_embedding_result.embedding, 'values'):
             query_embedding = query_embedding_result.embedding.values

        if not query_embedding:
            response_repr = repr(query_embedding_result)[:200]
            print(f"Error: Could not extract embedding vector from query response: {response_repr}")
            return None

        print(f"Querying ChromaDB for top {n_results} results...")
        results = chroma_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=['metadatas', 'distances', 'documents']
        )
        return results

    except Exception as e:
        print(f"Error during search for query '{query}': {e}")
        if "task type" in str(e).lower() and "not supported" in str(e).lower():
             print(f"Model {config.EMBEDDING_MODEL_NAME} might not support task_type.")
        return None

# --- Main Search Application Logic ---
def run_search_app():
    """Runs the interactive search application."""
    print("--- YouTube Watch Later Semantic Search ---")

    if not config.GEMINI_API_KEY:
         print("Error: GEMINI_API_KEY missing.")
         return

    gemini_client = initialize_gemini_client()
    chroma_client, chroma_collection = initialize_chromadb_client()

    if not gemini_client or not chroma_collection:
        print("Failed to initialize required clients for search. Exiting.")
        return

    db_count = chroma_collection.count()
    print(f"Database contains {db_count} items.")
    if db_count == 0:
        print("Warning: The database is empty. Run the ingestion script first (`python ingest_data.py`).")

    print("\n--- Search Interface ---")
    while True:
        try:
            user_query = input("Enter your search query (or type 'quit' to exit): ")
            if user_query.lower() == 'quit':
                break
            if not user_query:
                continue

            search_results = search_videos_local(user_query, gemini_client, chroma_collection)

            if search_results and search_results.get('ids') and search_results['ids'][0]:
                print(f"\n--- Top {len(search_results['ids'][0])} Results for: '{user_query}' ---")

                result_ids = search_results['ids'][0]
                distances = search_results['distances'][0]
                metadatas = search_results['metadatas'][0]

                for i in range(len(result_ids)):
                    meta = metadatas[i]
                    dist = distances[i]
                    # Assuming cosine distance from collection setup
                    score = 1 - dist if dist is not None and dist <= 2 else 0

                    print(f"\n{i+1}. (Score: {score:.4f}) {meta.get('title', 'N/A')}")
                    print(f"   Channel: {meta.get('channel', 'N/A')}")
                    print(f"   URL: {meta.get('url', 'N/A')}")
                    # Optionally display the processed tags string
                    # tags_str = meta.get('tags_str')
                    # if tags_str:
                    #    print(f"   Tags: {tags_str}")

            elif search_results:
                print("No relevant videos found in your Watch Later list for that query.")
            else:
                print("Search failed. Please check logs or try again.")

        except KeyboardInterrupt:
            print("\nExiting search.")
            break
        except Exception as e:
            print(f"\nAn unexpected error occurred during the search loop: {e}")
            import time
            time.sleep(1)

if __name__ == "__main__":
    run_search_app()
    print("\n--- Search Application Closed ---")