# embedding_utils.py
import time
from google import genai
from google.genai import types
from tqdm import tqdm
import config

# --- initialize_gemini_client (no changes) ---
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

# --- generate_embeddings (no changes needed from last working version) ---
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