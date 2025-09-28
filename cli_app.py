# cli_app.py
from __future__ import annotations

from src.config import CHROMA_COLLECTION_NAME, CHROMA_DB_PATH, IS_CONFIG_VALID
from src.core.search import search_videos
from src.services.vectordb_service import VectorDBService

def run_search_cli() -> None:
    print("--- YouTube Watch Later Semantic Search (CLI) ---")
    if not IS_CONFIG_VALID:
        print("Configuration is not valid. Check your .env file and paths.")
        return

    vectordb = VectorDBService(path=CHROMA_DB_PATH, collection_name=CHROMA_COLLECTION_NAME)
    db_count = vectordb.count()
    print(f"Database contains {db_count} items.")
    if db_count == 0:
        print("Warning: The database is empty. Run `python ingest_data.py` first.")

    print("\nType search queries (or 'quit' to exit).\n")
    while True:
        try:
            query = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting search.")
            break
        if not query:
            continue
        if query.lower() == "quit":
            break

        results = search_videos(query)
        hits = (results or {}).get("ids") or []
        if not hits or not hits[0]:
            print("No relevant videos found.")
            continue

        ids = results["ids"][0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        print(f"\n--- Top {len(ids)} results for '{query}' ---")
        for idx, video_id in enumerate(ids):
            meta = metadatas[idx]
            distance = distances[idx] if idx < len(distances) else None
            score = 1 - distance if distance is not None else 0
            print(f"\n{idx + 1}. (Score: {score:.4f}) {meta.get('title', 'N/A')}")
            print(f"   Channel: {meta.get('channel', 'N/A')}")
            print(f"   URL: {meta.get('url', 'N/A')}")

if __name__ == "__main__":
    run_search_cli()
    print("\n--- Search Application Closed ---")
