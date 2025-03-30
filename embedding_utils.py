# embedding_utils.py
import time
from google import genai
from google.genai import types
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tqdm import tqdm
import config
import pandas as pd
import chromadb

def initialize_gemini_client():
    """Initializes and returns the Gemini API client using the new SDK pattern."""
    if not config.GEMINI_API_KEY:
        print("Gemini API Key not configured in config.py or .env file.")
        return None
    try:
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        print("Gemini client initialized successfully.")
        return client
    except Exception as e:
        print(f"Error initializing Gemini client: {e}")
        return None

def generate_embeddings(client, documents_to_embed):
    """
    Generates embeddings for a list of text documents using the configured Gemini model,
    utilizing batching. Title information is expected to be prepended in the 'text' field.
    TaskType is passed via the config object.
    """
    if not client:
        print("Gemini client is not initialized.")
        return [], [], []
    if not documents_to_embed:
        print("No documents provided for embedding.")
        return [], [], []

    all_embeddings = []
    all_doc_ids = []
    all_texts = []
    embedding_errors = 0
    total_docs = len(documents_to_embed)

    print(f"Generating embeddings for {total_docs} documents using model: {config.EMBEDDING_MODEL_NAME} in batches of {config.EMBEDDING_BATCH_SIZE}...")

    for i in tqdm(range(0, total_docs, config.EMBEDDING_BATCH_SIZE), desc="Embedding Batches"):
        batch_end = min(i + config.EMBEDDING_BATCH_SIZE, total_docs)
        current_batch_docs = documents_to_embed[i:batch_end]

        batch_texts = [doc.get('text', '') for doc in current_batch_docs]
        batch_ids = [doc.get('id') for doc in current_batch_docs]

        if len(batch_texts) != len(batch_ids):
             print(f"Warning: Mismatch between texts and IDs in batch starting {i}. Check document preparation.")
             embedding_errors += len(current_batch_docs)
             continue

        if not batch_texts:
            print(f"Skipping empty batch at index {i}")
            continue

        try:
            result = client.models.embed_content(
                model=config.EMBEDDING_MODEL_NAME,
                contents=batch_texts,
                config=types.EmbedContentConfig(
                    task_type=config.TASK_TYPE_RETRIEVAL_DOCUMENT
                )
            )

            if hasattr(result, 'embeddings') and isinstance(result.embeddings, list) and len(result.embeddings) == len(batch_texts):
                batch_embeddings_data = result.embeddings
                batch_embeddings_values = [emb.values for emb in batch_embeddings_data if hasattr(emb, 'values') and emb.values is not None]

                if len(batch_embeddings_values) == len(batch_texts):
                     successful_indices = list(range(len(batch_texts)))
                     all_embeddings.extend(batch_embeddings_values)
                     all_doc_ids.extend([batch_ids[idx] for idx in successful_indices])
                     all_texts.extend([batch_texts[idx] for idx in successful_indices])
                else:
                     valid_mapping = {idx: emb for idx, emb in enumerate(batch_embeddings_values) if emb is not None}
                     successful_indices = list(valid_mapping.keys())
                     all_embeddings.extend(valid_mapping.values())
                     all_doc_ids.extend([batch_ids[idx] for idx in successful_indices])
                     all_texts.extend([batch_texts[idx] for idx in successful_indices])
                     failed_count = len(batch_texts) - len(successful_indices)
                     embedding_errors += failed_count
                     print(f"\nWarning: {failed_count} items in batch starting {i} failed to embed or had missing values.")
            else:
                response_repr = repr(result)[:200]
                print(f"\nError: Unexpected response structure or embedding count mismatch for batch starting {i}. Response snippet: {response_repr}")
                embedding_errors += len(batch_texts)

            time.sleep(config.EMBEDDING_API_DELAY)

        except Exception as e:
            print(f"\nError processing embedding batch starting at index {i}: {e}")
            if "task type" in str(e).lower() and "not supported" in str(e).lower():
                 print(f"Model {config.EMBEDDING_MODEL_NAME} might not support task_type. Consider using a different model or removing task_type.")
            embedding_errors += len(batch_texts)
            print("Pausing longer before next batch...")
            time.sleep(min(config.EMBEDDING_API_DELAY * 2, 60))

    print(f"Finished generating embeddings.")
    print(f"Successfully generated {len(all_embeddings)} embeddings.")
    print(f"Encountered {embedding_errors} errors during embedding.")
    return all_embeddings, all_doc_ids, all_texts


def store_embeddings_in_chroma(chroma_collection, embeddings, ids, metadatas, documents):
    """
    Stores embeddings, metadata, and source documents in the ChromaDB collection.
    EXPECTS that the 'tags' field within each dictionary in 'metadatas'
    has already been converted to a string (e.g., comma-separated) or removed
    by the calling function (ingest_data.py).

    Args:
        chroma_collection: An initialized ChromaDB collection object.
        embeddings (list): List of embedding vectors.
        ids (list): List of corresponding document IDs.
        metadatas (list): List of corresponding metadata dictionaries (pre-processed).
        documents (list): List of corresponding source text documents (including title prefix).

    Returns:
        tuple: (added_count, skipped_count)
    """
    if not all([embeddings, ids, metadatas, documents]):
        print("Warning: Empty lists provided for ChromaDB storage. Skipping.")
        return 0, 0

    # Verify lists have the same length
    if not (len(embeddings) == len(ids) == len(metadatas) == len(documents)):
        print("Error: Mismatch in list lengths for ChromaDB storage. Aborting.")
        print(f"Embeddings: {len(embeddings)}, IDs: {len(ids)}, Metadatas: {len(metadatas)}, Documents: {len(documents)}")
        return 0, len(ids)

    added_count = 0
    skipped_count = 0
    total_items = len(ids)

    print(f"Adding/Updating {total_items} items in ChromaDB collection '{chroma_collection.name}'...")

    for i in tqdm(range(0, total_items, config.CHROMA_BATCH_SIZE), desc="ChromaDB Batches"):
        batch_end = min(i + config.CHROMA_BATCH_SIZE, total_items)

        current_ids = ids[i:batch_end]
        current_embeddings = embeddings[i:batch_end]
        current_metadatas = metadatas[i:batch_end] # Already pre-processed
        current_documents = documents[i:batch_end]

        try:
            chroma_collection.upsert(
                ids=current_ids,
                embeddings=current_embeddings,
                metadatas=current_metadatas, # Store pre-processed metadata
                documents=current_documents
            )
            added_count += len(current_ids)
        except Exception as e:
            # Catch potential ChromaDB errors (e.g., data validation errors if pre-processing missed something)
            print(f"\nError adding batch starting at index {i} to ChromaDB: {e}")
            # Provide more context if possible
            if len(current_ids) > 0:
                 print(f"Example Metadata causing error (ID: {current_ids[0]}): {current_metadatas[0]}")
            skipped_count += len(current_ids)

    print(f"Finished adding data to ChromaDB.")
    print(f"Items processed/upserted: {added_count}. Items skipped due to errors: {skipped_count}")
    print(f"Total items now in collection: {chroma_collection.count()}")
    return added_count, skipped_count

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
    
def fetch_youtube_details(video_ids):
    """
    Fetches video details (snippet) from the YouTube Data API v3 for a list of video IDs.

    Args:
        video_ids (list): A list of YouTube video ID strings.

    Returns:
        list: A list of dictionaries, where each dictionary contains details
              for a successfully fetched video (id, title, description, channel, tags, url).
              Returns an empty list if the API key is invalid or other critical errors occur.
    """
    print("-" * 20)
    print(f"DEBUG: Attempting to use YouTube API Key: '{config.YOUTUBE_API_KEY}'")
    if config.YOUTUBE_API_KEY == 'YOUR_YOUTUBE_API_KEY_HERE':
        print("DEBUG: WARNING! The key value is still the placeholder text!")
    elif not config.YOUTUBE_API_KEY:
        print("DEBUG: ERROR! The key value is empty or None!")
    else:
        print("DEBUG: Key value appears to be set from config.")
    print("-" * 20)
    # --- END DEBUGGING ---


    if not config.YOUTUBE_API_KEY:
        print("YouTube API Key not configured in config.py or .env file.")
        return []

    try:
        # Build the YouTube service object using the key from config
        youtube = build('youtube', 'v3', developerKey=config.YOUTUBE_API_KEY)
    except Exception as e:
        print(f"Error building YouTube service object: {e}")
        return []

    all_video_details = []
    processed_count = 0
    error_count = 0

    print(f"Fetching details for {len(video_ids)} YouTube video IDs...")

    for i in tqdm(range(0, len(video_ids), config.YOUTUBE_API_BATCH_SIZE), desc="YouTube API Batches"):
        batch_ids = video_ids[i:i + config.YOUTUBE_API_BATCH_SIZE]

        try:
            request = youtube.videos().list(
                part="snippet",  # Fetches title, description, channelTitle, tags
                id=",".join(batch_ids)
            )
            response = request.execute() # <-- This is where the error happens

            for item in response.get('items', []):
                snippet = item.get('snippet', {})
                video_id = item.get('id')
                title = snippet.get('title')
                description = snippet.get('description')
                channel_title = snippet.get('channelTitle')
                tags = snippet.get('tags', []) # Get tags, default to empty list

                # Basic validation: Ensure we have an ID and title at least
                if video_id and title:
                    all_video_details.append({
                        'id': video_id,
                        'title': title,
                        'description': description or '', # Ensure description is not None
                        'channel': channel_title or '', # Ensure channel is not None
                        'tags': tags,
                        'url': f'https://www.youtube.com/watch?v={video_id}'
                    })
                    processed_count += 1
                else:
                     print(f"Warning: Skipping item with missing ID or Title in batch starting {i}. Data: {item}")
                     error_count += 1


            # Respect API rate limits/quotas
            time.sleep(config.YOUTUBE_API_DELAY)

        except HttpError as e:
            print(f"\nHTTP Error fetching batch starting at index {i}: {e}")
            print(f"DEBUG (on error): Key used was reported as: '{config.YOUTUBE_API_KEY}'")
            # --- END DEBUG ---
            if e.resp.status == 403:
                 print("Likely Quota Exceeded or Invalid API Key/Permissions. Stopping YouTube fetch.")
                 break
            print("API Key seems invalid according to Google. Please double-check the key and project settings.")
            print("Stopping YouTube fetch due to invalid key error.")
            break

        except Exception as e:
            print(f"\nUnexpected Error fetching batch starting at index {i}: {e}")
            error_count += len(batch_ids)
            print("Continuing with next batch...")
            time.sleep(2)


    print(f"Finished fetching YouTube details.")
    print(f"Successfully processed: {processed_count}, Errors/Skipped: {error_count}")
    return all_video_details