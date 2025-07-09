# src/core/pipeline.py
import pandas as pd
from src.services.youtube_service import YouTubeService
from src.services.embedding_service import EmbeddingService
from src.services.vectordb_service import VectorDBService
from src.config import (
    YOUTUBE_API_KEY,
    GEMINI_API_KEY,
    EMBEDDING_MODEL_NAME,
    CHROMA_DB_PATH,
    CHROMA_COLLECTION_NAME,
    TAKEOUT_CSV_FILE,
    POSSIBLE_VIDEO_ID_COLUMNS,
)

class DataIngestionPipeline:
    def __init__(self):
        self.youtube_service = YouTubeService(api_key=YOUTUBE_API_KEY)
        self.embedding_service = EmbeddingService(api_key=GEMINI_API_KEY, model_name=EMBEDDING_MODEL_NAME)
        self.vectordb_service = VectorDBService(path=CHROMA_DB_PATH, collection_name=CHROMA_COLLECTION_NAME)

    def run(self):
        print("--- Running Data Ingestion Pipeline ---")

        # Phase 1: Load video IDs from CSV
        print("\n--- Phase 1: Loading Video IDs ---")
        csv_video_ids = self._load_video_ids_from_csv(TAKEOUT_CSV_FILE)
        if not csv_video_ids:
            print("No video IDs found in the CSV file. Aborting.")
            return False
        print(f"Found {len(csv_video_ids)} unique video IDs in the CSV file.")

        # Phase 2: Get existing IDs from ChromaDB
        print("\n--- Phase 2: Getting Existing IDs from ChromaDB ---")
        existing_ids = set(self.vectordb_service.get_all_ids())
        print(f"Found {len(existing_ids)} existing video IDs in the database.")

        # Phase 3: Calculate differences
        print("\n--- Phase 3: Calculating Differences ---")
        new_video_ids = list(csv_video_ids - existing_ids)
        removed_video_ids = list(existing_ids - csv_video_ids)
        print(f"Found {len(new_video_ids)} new videos to add.")
        print(f"Found {len(removed_video_ids)} videos to remove.")

        # Phase 4: Processing new videos
        if new_video_ids:
            print("\n--- Phase 4: Processing New Videos ---")
            video_details = self.youtube_service.fetch_video_details(new_video_ids)
            if video_details:
                documents_to_embed = self._prepare_text_documents(video_details)
                if documents_to_embed:
                    embeddings, doc_ids, texts = self.embedding_service.embed_documents(documents_to_embed)
                    if embeddings:
                        metadata_map = {doc['id']: doc['metadata'] for doc in documents_to_embed}
                        metadata_for_storage = [metadata_map[id] for id in doc_ids if id in metadata_map]
                        
                        processed_metadatas_for_chroma = []
                        for meta_item in metadata_for_storage:
                            processed_item = meta_item.copy()
                            tags_list = processed_item.get('tags')
                            if isinstance(tags_list, list):
                                processed_item['tags_str'] = ", ".join(tags_list) if tags_list else ""
                            elif tags_list is not None:
                                processed_item['tags_str'] = str(tags_list)
                            if 'tags' in processed_item:
                                del processed_item['tags']
                            processed_metadatas_for_chroma.append(processed_item)

                        if (len(embeddings) == len(doc_ids) == len(texts) == len(processed_metadatas_for_chroma)):
                            self.vectordb_service.upsert_documents(
                                embeddings, doc_ids, processed_metadatas_for_chroma, texts
                            )
                        else:
                            print("Error: Mismatch in lengths of data to be stored. Skipping storage of new videos.")
        else:
            print("\n--- Phase 4: No new videos to process. ---")

        # Phase 5: Removing old videos
        if removed_video_ids:
            print("\n--- Phase 5: Removing Old Videos ---")
            self.vectordb_service.delete(ids=removed_video_ids)
            print(f"Removed {len(removed_video_ids)} old videos from the database.")
        else:
            print("\n--- Phase 5: No old videos to remove. ---")

        print("\n--- Ingestion process finished. ---")
        print(f"Total videos in database: {self.vectordb_service.count()}")
        return True

    def _load_video_ids_from_csv(self, filepath):
        try:
            df = pd.read_csv(filepath)
            id_column = None
            for col in POSSIBLE_VIDEO_ID_COLUMNS:
                if col in df.columns:
                    id_column = col
                    break

            if id_column is None:
                 print(f"Error: Could not find a suitable Video ID column in '{filepath}'.")
                 print(f"Looked for: {POSSIBLE_VIDEO_ID_COLUMNS}")
                 print(f"Available columns: {df.columns.tolist()}")
                 return None

            video_ids = df[id_column].dropna().unique().tolist()
            print(f"Loaded {len(video_ids)} unique video IDs from column '{id_column}' in '{filepath}'.")
            return set(video_ids)

        except FileNotFoundError:
            print(f"Error: CSV file not found at '{filepath}'")
            return None
        except Exception as e:
            print(f"Error reading CSV file '{filepath}': {e}")
            return None

    def _prepare_text_documents(self, video_details_list):
        processed_docs = []
        print("Preparing text documents for embedding (including titles)...")
        for video in video_details_list:
            doc_id = video.get('id')
            if not doc_id:
                print(f"Warning: Skipping video detail with missing ID: {video}")
                continue

            title = video.get('title', '').strip()
            channel = video.get('channel', '').strip()
            description = video.get('description', '').strip()

            text_parts = []
            if title:
                 text_parts.append(f"Title: {title}")
            if channel:
                 text_parts.append(f"Channel: {channel}")
            if description:
                 text_parts.append(f"Description: {description}")

            text_to_embed = "\n".join(text_parts)
            text_to_embed = text_to_embed.replace('\r', '\n').replace('\n\n', '\n')

            processed_docs.append({
                'id': doc_id,
                'text': text_to_embed.strip(),
                'metadata': video
            })
        print(f"Prepared {len(processed_docs)} documents with titles included in text.")
        return processed_docs
