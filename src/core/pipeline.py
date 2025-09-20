# src/core/pipeline.py
import pandas as pd
from src.services.youtube_service import YouTubeService
from src.services.embedding_service import EmbeddingService
from src.services.vectordb_service import VectorDBService
from src.services.deleted_videos_archive import archive_deleted_videos
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
            # Diagnostic: report missing IDs not returned by API
            missing_ids = getattr(self.youtube_service, 'last_missing_ids', [])
            if missing_ids:
                print(f"Diagnostic: {len(missing_ids)} of {len(new_video_ids)} new IDs not returned by YouTube API.")
                sample_missing = missing_ids[:10]
                print(f"Missing IDs sample (up to 10): {sample_missing}")
                # Optionally write to a file for later inspection
                try:
                    import os, json, time as _time
                    diagnostics_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'data')
                    diagnostics_path = os.path.abspath(diagnostics_path)
                    os.makedirs(diagnostics_path, exist_ok=True)
                    out_file = os.path.join(diagnostics_path, f'missing_youtube_ids_{int(_time.time())}.json')
                    with open(out_file, 'w', encoding='utf-8') as f:
                        json.dump({
                            'requested_new_ids': new_video_ids,
                            'missing_ids': missing_ids,
                            'missing_count': len(missing_ids)
                        }, f, indent=2)
                    print(f"Diagnostic: Missing ID list written to {out_file}")
                except Exception as diag_e:
                    print(f"Warning: Failed to write missing ID diagnostics file: {diag_e}")
                # Attempt archival of deleted/private videos if we still have historical details
                try:
                    # Load existing intermediate details if present for archival
                    import json, os
                    intermediate_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'intermediate_youtube_details.json')
                    intermediate_path = os.path.abspath(intermediate_path)
                    historical_details = []
                    if os.path.exists(intermediate_path):
                        with open(intermediate_path, 'r', encoding='utf-8') as f:
                            try:
                                historical_details = json.load(f)
                            except json.JSONDecodeError:
                                print("Warning: Could not parse intermediate_youtube_details.json for archival.")
                    if isinstance(historical_details, list) and historical_details:
                        archive_summary = archive_deleted_videos(
                            missing_ids,
                            historical_details,
                            source_reason='ingestion_missing',
                            run_context={'new_video_ids_requested': len(new_video_ids)}
                        )
                        print("Archive: Archived {archived_new_records} new / {missing_input_count} missing IDs (already archived: {already_archived}).".format(**archive_summary))
                    else:
                        print("Archive: No historical details available to archive missing videos.")
                except Exception as arch_e:
                    print(f"Archive Warning: Failed to archive missing videos: {arch_e}")
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

            raw_ids = df[id_column].dropna().astype(str).tolist()
            cleaned_ids = []
            invalid_ids = []
            seen = set()

            # YouTube video IDs are typically 11 chars (alphanumeric, -, _). We won't strictly enforce length
            # (shorts or future changes) but we'll log irregular lengths.
            import re
            pattern = re.compile(r'^[A-Za-z0-9_-]{5,}$')  # relaxed lower bound to 5 to avoid over-filtering

            for vid in raw_ids:
                cleaned = vid.strip().strip('"').strip("'")
                if not cleaned:
                    continue
                if cleaned in seen:
                    continue
                seen.add(cleaned)
                if not pattern.match(cleaned):
                    invalid_ids.append(cleaned)
                cleaned_ids.append(cleaned)

            if invalid_ids:
                print(f"Note: {len(invalid_ids)} video IDs have unexpected characters/length and were still included. Sample: {invalid_ids[:5]}")

            print(f"Loaded {len(cleaned_ids)} unique (cleaned) video IDs from column '{id_column}' in '{filepath}'.")
            # Return as set for downstream set operations
            return set(cleaned_ids)

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
