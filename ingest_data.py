# ingest_data.py
import sys
import config
import pandas as pd
import os # Needed for checking file existence
import json # Needed for saving/loading intermediate data

from youtube_utils import fetch_youtube_details
from embedding_utils import (
    initialize_gemini_client,
    generate_embeddings,
    store_embeddings_in_chroma
)
# Assuming shared functions are still in main_search or moved to common_utils
from main_search import (
    initialize_chromadb_client,
    load_video_ids_from_csv,
    prepare_text_documents
)

# Helper function to save data to JSON
def save_to_json(data, filename):
    print(f"Saving intermediate data to {filename}...")
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Successfully saved {filename}.")
    except Exception as e:
        print(f"Error saving data to {filename}: {e}")

# Helper function to load data from JSON
def load_from_json(filename):
    print(f"Attempting to load intermediate data from {filename}...")
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"Successfully loaded data from {filename}.")
            return data
        except Exception as e:
            print(f"Error loading data from {filename}: {e}. Will proceed without loading.")
            return None
    else:
        print(f"File {filename} not found. Will proceed without loading.")
        return None

# --- Main Ingestion Logic ---
def run_ingestion():
    """Handles the full data ingestion pipeline with intermediate saving/loading."""
    print("--- Running Data Ingestion Pipeline (with Intermediate Saving) ---")

    # 1. Validate Configuration
    if not config.IS_CONFIG_VALID:
        print("Configuration is invalid. Please check settings and file paths.")
        return False

    # --- Initialize required clients ---
    # Gemini client needed for embedding phase
    gemini_client = None
    # Chroma client needed for storage phase
    chroma_client = None
    chroma_collection = None

    # --- Phase 1: Loading Video IDs ---
    print("\n--- Phase 1: Loading Video IDs ---")
    video_ids_from_csv = load_video_ids_from_csv(config.TAKEOUT_CSV_FILE)
    if video_ids_from_csv is None:
        print("Failed to load video IDs. Aborting ingestion.")
        return False
    print(f"Total unique video IDs found in CSV: {len(video_ids_from_csv)}")


    # --- Phase 2: Fetching/Loading YouTube Details ---
    print("\n--- Phase 2: Fetching/Loading YouTube Details ---")
    video_details = load_from_json(config.YOUTUBE_DETAILS_FILE)

    if video_details:
        print("Using previously fetched YouTube details.")
        # Optional: Filter details to only include IDs present in the current CSV if needed
        # current_csv_ids = set(video_ids_from_csv)
        # video_details = [vd for vd in video_details if vd.get('id') in current_csv_ids]
        # print(f"Filtered details to {len(video_details)} matching current CSV.")
    else:
        print("No existing details file found or failed to load. Fetching from YouTube API...")
        # We'll fetch details for ALL IDs in the CSV for simplicity here.
        # Filtering for only new IDs before fetching requires ChromaDB access first.
        video_details = fetch_youtube_details(video_ids_from_csv)
        if not video_details:
            print("No video details were fetched. Cannot proceed with embedding.")
            return False # Stop if fetching fails completely
        # Save the newly fetched details
        save_to_json(video_details, config.YOUTUBE_DETAILS_FILE)

    if not video_details:
         print("No video details available to process after fetch/load attempt. Exiting.")
         return False


    # --- Phase 3: Preparing Documents for Embedding ---
    # This step is relatively fast, so we usually run it every time based on loaded/fetched details
    print("\n--- Phase 3: Preparing Documents for Embedding ---")
    documents_to_embed = prepare_text_documents(video_details)
    if not documents_to_embed:
        print("No documents prepared for embedding. Exiting.")
        return False
    # Create metadata map for later use (associates ID with original full metadata)
    metadata_map = {doc['id']: doc['metadata'] for doc in documents_to_embed}


    # --- Phase 4: Generating/Loading Embeddings ---
    print("\n--- Phase 4: Generating/Loading Embeddings ---")
    embeddings_data = load_from_json(config.EMBEDDINGS_DATA_FILE)
    embeddings = None
    doc_ids = None
    texts = None
    metadata_for_storage = None # Metadata corresponding to loaded embeddings

    if embeddings_data and all(k in embeddings_data for k in ['embeddings', 'doc_ids', 'texts', 'metadata']):
        print("Using previously generated embeddings and associated data.")
        embeddings = embeddings_data['embeddings']
        doc_ids = embeddings_data['doc_ids']
        texts = embeddings_data['texts']
        metadata_for_storage = embeddings_data['metadata'] # Load original metadata linked to embeddings

        # Optional: Consistency check
        if not (len(embeddings) == len(doc_ids) == len(texts) == len(metadata_for_storage)):
             print("Warning: Inconsistency found in loaded embeddings data file. Discarding and regenerating.")
             embeddings = doc_ids = texts = metadata_for_storage = None # Force regeneration
        else:
             print(f"Loaded {len(embeddings)} embeddings.")

    if embeddings is None: # Regenerate if not loaded or if load failed consistency check
        print("No existing embeddings file found or data invalid. Generating embeddings...")
        if not gemini_client: # Initialize only if needed
             gemini_client = initialize_gemini_client()
             if not gemini_client:
                  print("Failed to initialize Gemini client. Cannot generate embeddings.")
                  return False

        # Generate embeddings based on the prepared documents from Phase 3
        embeddings, doc_ids, texts = generate_embeddings(gemini_client, documents_to_embed)

        if not embeddings: # Check if embedding generation failed
            print("Embedding generation failed or produced no results. Cannot store data.")
            return False

        # Prepare corresponding original metadata for saving with embeddings
        # Use the map created in Phase 3, ensure order matches generated embeddings
        metadata_for_saving = [metadata_map[id] for id in doc_ids if id in metadata_map]

        # Double-check consistency before saving
        if len(embeddings) == len(doc_ids) == len(texts) == len(metadata_for_saving):
            # Save the newly generated embeddings and associated data
            data_to_save = {
                'embeddings': embeddings,
                'doc_ids': doc_ids,
                'texts': texts,
                'metadata': metadata_for_saving # Save original metadata linked to embeddings
            }
            save_to_json(data_to_save, config.EMBEDDINGS_DATA_FILE)
            metadata_for_storage = metadata_for_saving # Use this for the next step
        else:
            print("Error: Mismatch after embedding generation. Cannot save or store.")
            return False

    if not embeddings or not doc_ids or not texts or not metadata_for_storage:
         print("Essential data missing after embedding phase. Cannot proceed to storage.")
         return False


    # --- Phase 5: Preparing Metadata and Storing in Vector DB ---
    print("\n--- Phase 5: Preparing Metadata and Storing in Vector DB ---")

    # ** CRITICAL STEP: Pre-process metadata for ChromaDB **
    # Convert 'tags' list to comma-separated string for each item
    print("Preprocessing metadata for ChromaDB compatibility (converting tags list to string)...")
    processed_metadatas_for_chroma = []
    items_processed_count = 0
    items_error_count = 0
    for meta_item in metadata_for_storage:
        # Create a copy to avoid modifying the original loaded/saved data
        processed_item = meta_item.copy()
        try:
            tags_list = processed_item.get('tags')
            if isinstance(tags_list, list):
                # Join list into a comma-separated string, handle empty list
                processed_item['tags_str'] = ", ".join(tags_list) if tags_list else ""
            elif tags_list is not None:
                # If tags exist but aren't a list, convert to string defensively
                processed_item['tags_str'] = str(tags_list)

            # Remove the original 'tags' list key as it's not allowed by Chroma
            if 'tags' in processed_item:
                del processed_item['tags']

            # Optional: Check other fields if necessary (ensure no other lists/dicts)
            # for key, value in processed_item.items():
            #    if isinstance(value, (list, dict)):
            #        print(f"Warning: Found non-primitive type for key '{key}' in metadata ID {processed_item.get('id')}. Value: {value}")
            #        # Decide how to handle - convert, remove, or error out

            processed_metadatas_for_chroma.append(processed_item)
            items_processed_count += 1

        except Exception as meta_e:
             items_error_count += 1
             print(f"Error processing metadata for item ID {meta_item.get('id', 'UNKNOWN')}: {meta_e}")
             # Option: append None or skip item to avoid ChromaDB error later
             # For now, let's just report and continue, ChromaDB will catch if needed

    print(f"Metadata preprocessing complete. Processed: {items_processed_count}, Errors: {items_error_count}")
    if not processed_metadatas_for_chroma:
         print("No metadata available after preprocessing. Cannot store in ChromaDB.")
         return False

    # Initialize ChromaDB client only if needed for storage
    if not chroma_client:
        chroma_client, chroma_collection = initialize_chromadb_client()
        if not chroma_collection:
            print("Failed to initialize ChromaDB. Cannot store data.")
            return False

    # Check consistency one last time before storing
    if not (len(embeddings) == len(doc_ids) == len(texts) == len(processed_metadatas_for_chroma)):
        print("Error: Mismatch between embeddings/IDs/texts and preprocessed metadata before storage.")
        print(f"Lengths - Embeddings: {len(embeddings)}, IDs: {len(doc_ids)}, Texts: {len(texts)}, Processed Metadata: {len(processed_metadatas_for_chroma)}")
        return False

    # Store in ChromaDB using the pre-processed metadata
    added_count, skipped_count = store_embeddings_in_chroma(
        chroma_collection, embeddings, doc_ids, processed_metadatas_for_chroma, texts
    )
    print(f"Ingestion process finished. ChromaDB Add/Update: {added_count}, Skipped: {skipped_count}")

    # Optional: Clean up intermediate files after successful completion?
    # Consider adding flags to control this behavior. For now, keep them.
    # if added_count > 0 and skipped_count == 0:
    #     try: os.remove(config.YOUTUBE_DETAILS_FILE) except OSError: pass
    #     try: os.remove(config.EMBEDDINGS_DATA_FILE) except OSError: pass

    return added_count > 0 or skipped_count == 0 # Return True if something was processed or no errors


if __name__ == "__main__":
    if run_ingestion():
        print("\n--- Ingestion completed successfully (or no new data needed). ---")
        sys.exit(0) # Exit with success code
    else:
        print("\n--- Ingestion process failed or encountered errors. ---")
        sys.exit(1) # Exit with failure code