# src/core/pipeline.py
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

import pandas as pd

from src.config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_DB_PATH,
    EMBEDDING_MODEL_NAME,
    GEMINI_API_KEY,
    POSSIBLE_VIDEO_ID_COLUMNS,
    TAKEOUT_CSV_FILE,
    YOUTUBE_API_KEY,
)
from src.services.deleted_videos_archive import archive_deleted_videos
from src.services.duration_utils import parse_iso8601_duration
from src.services.embedding_service import EmbeddingService
from src.services.vectordb_service import VectorDBService
from src.services.youtube_service import YouTubeService


class DataIngestionPipeline:
    """End-to-end loader for the "Watch later" dataset."""

    def __init__(self) -> None:
        self.youtube_service = YouTubeService(api_key=YOUTUBE_API_KEY)
        self.embedding_service = EmbeddingService(api_key=GEMINI_API_KEY, model_name=EMBEDDING_MODEL_NAME)
        self.vectordb_service = VectorDBService(path=CHROMA_DB_PATH, collection_name=CHROMA_COLLECTION_NAME)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self) -> bool:
        print("--- Running Data Ingestion Pipeline ---")

        csv_ids = self._load_video_ids_from_csv(TAKEOUT_CSV_FILE)
        if not csv_ids:
            print("No video IDs found in the CSV file. Aborting.")
            return False
        print(f"Found {len(csv_ids)} unique video IDs in the CSV file.")

        existing_ids = set(self.vectordb_service.get_all_ids())
        print(f"Found {len(existing_ids)} existing video IDs in the database.")

        new_ids = sorted(csv_ids - existing_ids)
        removed_ids = sorted(existing_ids - csv_ids)
        print(f"Found {len(new_ids)} new videos to add.")
        print(f"Found {len(removed_ids)} videos to remove.")

        if new_ids:
            self._ingest_new_videos(new_ids)
        else:
            print("No new videos to process.")

        if removed_ids:
            self._remove_videos(removed_ids)
        else:
            print("No old videos to remove.")

        total = self.vectordb_service.count()
        print("\n--- Ingestion process finished. ---")
        print(f"Total videos in database: {total}")
        return True

    # ------------------------------------------------------------------
    # Load + clean IDs
    # ------------------------------------------------------------------
    def _load_video_ids_from_csv(self, filepath: str) -> Set[str]:
        try:
            df = pd.read_csv(filepath)
        except FileNotFoundError:
            print(f"Error: CSV file not found at '{filepath}'")
            return set()
        except Exception as exc:
            print(f"Error reading CSV file '{filepath}': {exc}")
            return set()

        id_column = next((col for col in POSSIBLE_VIDEO_ID_COLUMNS if col in df.columns), None)
        if id_column is None:
            print(f"Error: Could not find a suitable Video ID column in '{filepath}'.")
            print(f"Looked for: {POSSIBLE_VIDEO_ID_COLUMNS}")
            print(f"Available columns: {df.columns.tolist()}")
            return set()

        series = (
            df[id_column]
            .dropna()
            .astype(str)
            .str.strip()
            .str.strip('"')
            .str.strip("'")
        )
        cleaned = {vid for vid in series if self._is_valid_video_id(vid)}
        print(f"Loaded {len(cleaned)} unique (cleaned) video IDs from column '{id_column}'.")
        return cleaned

    @staticmethod
    def _is_valid_video_id(value: str) -> bool:
        return bool(value) and len(value) >= 5

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------
    def _ingest_new_videos(self, video_ids: Sequence[str]) -> None:
        print("\n--- Phase: Processing new videos ---")
        details = self.youtube_service.fetch_video_details(video_ids)
        missing = list(getattr(self.youtube_service, "last_missing_ids", []) or [])
        if missing:
            print(f"Diagnostic: {len(missing)} of {len(video_ids)} new IDs not returned by YouTube API.")
            self._record_missing_ids(video_ids, missing)

        if not details:
            print("No details returned; nothing to embed.")
            return

        documents = self._prepare_documents(details)
        if not documents:
            print("No documents constructed for embedding.")
            return

        embeddings, doc_ids, texts = self.embedding_service.embed_documents(documents)
        if not embeddings:
            print("Embedding step returned no vectors; aborting upsert.")
            return

        metadata_lookup = {doc["id"]: self._prepare_metadata(doc["metadata"]) for doc in documents}
        ordered_metadatas = [metadata_lookup[doc_id] for doc_id in doc_ids if doc_id in metadata_lookup]
        if len(ordered_metadatas) != len(doc_ids):
            print("Warning: Metadata mismatch; skipping storage.")
            return

        self.vectordb_service.upsert_documents(embeddings, list(doc_ids), ordered_metadatas, list(texts))

    def _record_missing_ids(self, requested: Sequence[str], missing: Sequence[str]) -> None:
        sample = list(missing)[:10]
        print(f"Missing IDs sample (up to 10): {sample}")
        diagnostics_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data")
        os.makedirs(diagnostics_dir, exist_ok=True)
        out_path = os.path.join(diagnostics_dir, f"missing_youtube_ids_{int(time.time())}.json")
        payload = {
            "requested_new_ids": list(requested),
            "missing_ids": list(missing),
            "missing_count": len(missing),
        }
        with open(os.path.abspath(out_path), "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        print(f"Diagnostic: Missing ID list written to {os.path.abspath(out_path)}")
        self._archive_missing_videos(missing, len(requested))

    def _archive_missing_videos(self, missing: Sequence[str], requested_total: int) -> None:
        details_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "intermediate_youtube_details.json")
        details_path = os.path.abspath(details_path)
        if not os.path.exists(details_path):
            print("Archive: No historical details available to archive missing videos.")
            return
        try:
            with open(details_path, "r", encoding="utf-8") as handle:
                historical_details = json.load(handle)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"Archive warning: failed to load historical details ({exc}).")
            return
        if not isinstance(historical_details, list) or not historical_details:
            print("Archive: Historical details file was empty.")
            return
        summary = archive_deleted_videos(
            missing,
            historical_details,
            source_reason="ingestion_missing",
            run_context={"new_video_ids_requested": requested_total},
        )
        print(
            "Archive: Archived {archived_new_records} new / {missing_input_count} missing IDs (already archived: {already_archived}).".format(
                **summary
            )
        )

    def _prepare_documents(self, video_details: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        documents: List[Dict[str, Any]] = []
        for video in video_details:
            doc_id = video.get("id")
            if not doc_id:
                continue
            title = (video.get("title") or "").strip()
            channel = (video.get("channel") or "").strip()
            description = (video.get("description") or "").strip()
            parts = [part for part in (title, channel, description) if part]
            if not parts:
                continue
            documents.append(
                {
                    "id": doc_id,
                    "text": "\n".join(parts),
                    "metadata": video,
                }
            )
        print(f"Prepared {len(documents)} documents with titles included in text.")
        return documents

    def _prepare_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        meta = dict(metadata)
        duration = parse_iso8601_duration(meta.get("duration"))
        if duration is not None:
            meta["duration_seconds"] = int(duration)
        tags = meta.get("tags")
        if isinstance(tags, list):
            meta["tags_str"] = ", ".join(tags)
        elif tags is not None:
            meta["tags_str"] = str(tags)
        meta.pop("tags", None)
        return meta

    # ------------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------------
    def _remove_videos(self, video_ids: Sequence[str]) -> None:
        print("\n--- Phase: Removing old videos ---")
        self.vectordb_service.delete(ids=list(video_ids))
        print(f"Removed {len(video_ids)} old videos from the database.")
