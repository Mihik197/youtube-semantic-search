# main_search.py
# Holds shared utility functions used by ingest_data.py and search_app.py

import pandas as pd
import chromadb
import config # Import our configuration settings
import sys

def load_video_ids_from_csv(filepath):
    """Loads unique video IDs from the specified CSV file."""
    try:
        df = pd.read_csv(filepath)
        # Find the correct Video ID column based on possible names in config
        id_column = None
        for col in config.POSSIBLE_VIDEO_ID_COLUMNS:
            if col in df.columns:
                id_column = col
                break

        if id_column is None:
             print(f"Error: Could not find a suitable Video ID column in '{filepath}'.")
             print(f"Looked for: {config.POSSIBLE_VIDEO_ID_COLUMNS}")
             print(f"Available columns: {df.columns.tolist()}")
             return None

        video_ids = df[id_column].dropna().unique().tolist()
        print(f"Loaded {len(video_ids)} unique video IDs from column '{id_column}' in '{filepath}'.")
        return video_ids

    except FileNotFoundError:
        print(f"Error: CSV file not found at '{filepath}'")
        return None
    except Exception as e:
        print(f"Error reading CSV file '{filepath}': {e}")
        return None

def prepare_text_documents(video_details_list):
    """
    Prepares documents for embedding from fetched video details.
    **Crucially includes the title directly in the text_to_embed.**
    """
    processed_docs = []
    print("Preparing text documents for embedding (including titles)...")
    for video in video_details_list:
        doc_id = video.get('id')
        if not doc_id:
            print(f"Warning: Skipping video detail with missing ID: {video}")
            continue

        title = video.get('title', '').strip() # Get title, remove leading/trailing whitespace
        channel = video.get('channel', '').strip()
        description = video.get('description', '').strip()

        # --- Prepend title to the text ---
        # This ensures title information is part of the embedded content
        text_parts = []
        if title: # Only add title prefix if title exists
             text_parts.append(f"Title: {title}")
        if channel:
             text_parts.append(f"Channel: {channel}")
        if description:
             text_parts.append(f"Description: {description}")
        # Optional: Add tags if desired
        # tags = video.get('tags')
        # if tags:
        #     text_parts.append(f"Tags: {', '.join(tags)}")

        text_to_embed = "\n".join(text_parts) # Join non-empty parts

        # Basic cleaning (can be expanded)
        text_to_embed = text_to_embed.replace('\r', '\n').replace('\n\n', '\n') # Normalize newlines
        # Consider removing URLs or other boilerplate if needed

        processed_docs.append({
            'id': doc_id,
            'text': text_to_embed.strip(), # Final text to be embedded
            'metadata': video # Store the original fetched metadata structure
        })
    print(f"Prepared {len(processed_docs)} documents with titles included in text.")
    return processed_docs

def initialize_chromadb_client():
    """Initializes and returns the ChromaDB persistent client and collection."""
    try:
        print(f"Initializing ChromaDB client at: {config.CHROMA_DB_PATH}")
        chroma_client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)

        print(f"Getting or creating ChromaDB collection: '{config.CHROMA_COLLECTION_NAME}'")
        # Ensure cosine distance is used, which is generally best for semantic similarity
        collection = chroma_client.get_or_create_collection(
            name=config.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"} # Explicitly set cosine distance
        )
        # Verify the metric (optional check)
        collection_metadata = collection.metadata
        if collection_metadata and collection_metadata.get("hnsw:space") != "cosine":
            print(f"Warning: Collection existed but used distance '{collection_metadata.get('hnsw:space')}'. Consider recreating for 'cosine'.")
        else:
            print(f"Collection '{config.CHROMA_COLLECTION_NAME}' ready. Distance metric: cosine. Current item count: {collection.count()}")

        return chroma_client, collection
    except Exception as e:
        print(f"Fatal Error initializing ChromaDB: {e}")
        print("Check permissions and ChromaDB setup.")
        return None, None

# NOTE: The `if __name__ == "__main__":` block remains removed.
# Execution logic is in ingest_data.py and search_app.py