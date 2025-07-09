# cli_app.py
from src.config import IS_CONFIG_VALID
from src.core.search import search_videos
from src.services.vectordb_service import VectorDBService
from src.config import CHROMA_DB_PATH, CHROMA_COLLECTION_NAME

def run_search_cli():
    """Runs the interactive command-line search interface."""
    print("--- YouTube Watch Later Semantic Search (CLI) ---")

    if not IS_CONFIG_VALID:
        print("Error: Configuration is not valid. Please check your .env file and file paths.")
        return

    try:
        vectordb_service = VectorDBService(path=CHROMA_DB_PATH, collection_name=CHROMA_COLLECTION_NAME)
        db_count = vectordb_service.count()
        print(f"Database contains {db_count} items.")
        if db_count == 0:
            print("Warning: The database is empty. Run `python ingest_data.py` first.")
    except Exception as e:
        print(f"Failed to initialize VectorDBService: {e}")
        return

    print("\n--- Search Interface ---")
    try:
        while True:
            user_query = input("Enter your search query (or type 'quit' to exit): ")
            if user_query.lower() == 'quit':
                break
            if not user_query.strip():
                continue

            search_results = search_videos(user_query)

            if search_results and search_results.get('ids') and search_results['ids'][0]:
                print(f"\n--- Top {len(search_results['ids'][0])} Results for: '{user_query}' ---")
                result_ids = search_results['ids'][0]
                distances = search_results['distances'][0]
                metadatas = search_results['metadatas'][0]

                for i in range(len(result_ids)):
                    meta = metadatas[i]
                    dist = distances[i]
                    score = 1 - dist if dist is not None and dist <= 2 else 0
                    print(f"\n{i+1}. (Score: {score:.4f}) {meta.get('title', 'N/A')}")
                    print(f"   Channel: {meta.get('channel', 'N/A')}")
                    print(f"   URL: {meta.get('url', 'N/A')}")
            elif search_results:
                print("No relevant videos found for that query.")
            else:
                print("Search failed. Please check logs or try again.")

    except KeyboardInterrupt:
        print("\nExiting search.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    run_search_cli()
    print("\n--- Search Application Closed ---")
