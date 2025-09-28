# src/services/vectordb_service.py
from __future__ import annotations

from typing import Any, Dict, Iterable, List

import chromadb

from src import config


_BATCH_SIZE = max(1, getattr(config, "CHROMA_BATCH_SIZE", 100))


class VectorDBService:
    """Lightweight wrapper around a Chroma persistent collection."""

    def __init__(self, path: str, collection_name: str):
        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_documents(
        self,
        embeddings: List[List[float]],
        ids: List[str],
        metadatas: List[Dict[str, Any]],
        documents: List[str],
    ) -> tuple[int, int]:
        if not embeddings or not ids:
            return 0, 0
        lengths = {len(embeddings), len(ids), len(metadatas), len(documents)}
        if len(lengths) != 1:
            raise ValueError("embeddings, ids, metadatas, and documents must be the same length")

        added = 0
        for start in range(0, len(ids), _BATCH_SIZE):
            end = min(start + _BATCH_SIZE, len(ids))
            self.collection.upsert(
                ids=ids[start:end],
                embeddings=embeddings[start:end],
                metadatas=metadatas[start:end],
                documents=documents[start:end],
            )
            added += end - start
        return added, 0

    def delete(self, ids: Iterable[str]) -> None:
        ids = list(ids)
        if ids:
            self.collection.delete(ids=ids)

    def query(self, query_embedding: List[float], n_results: int) -> Dict[str, Any]:
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["metadatas", "distances", "documents"],
        )

    def get_all_ids(self) -> List[str]:
        return self.collection.get(include=[]).get("ids", []) or []

    def count(self) -> int:
        return int(self.collection.count())

    def get_all_metadatas(self, batch_size: int = 1000, include_ids: bool = True) -> List[Dict[str, Any]]:
        total = self.count()
        if total == 0:
            return []
        batch_size = max(1, batch_size)
        collected: List[Dict[str, Any]] = []
        offset = 0
        while offset < total:
            limit = min(batch_size, total - offset)
            include = ["metadatas"] + (["ids"] if include_ids else [])
            batch = self.collection.get(include=include, offset=offset, limit=limit)
            metadatas = batch.get("metadatas") or []
            ids = batch.get("ids") or []
            for idx, meta in enumerate(metadatas):
                if not isinstance(meta, dict):
                    continue
                record = dict(meta)
                if include_ids and idx < len(ids):
                    record.setdefault("id", ids[idx])
                collected.append(record)
            if not metadatas:
                break
            offset += len(metadatas)
        return collected

    def get_videos_by_channel(self, channel: str, limit: int = 500) -> List[Dict[str, Any]]:
        if not channel:
            return []
        try:
            batch = self.collection.get(
                where={"channel": channel},
                include=["metadatas", "ids", "documents"],
                limit=max(1, limit),
            )
        except Exception:
            # fall back to manual filtering when the backend does not support "where" filters
            return [m for m in self.get_all_metadatas(include_ids=True) if m.get("channel") == channel][:limit]

        metadatas = batch.get("metadatas") or []
        ids = batch.get("ids") or []
        docs = batch.get("documents") or []
        videos: List[Dict[str, Any]] = []
        for idx, meta in enumerate(metadatas):
            if not isinstance(meta, dict):
                continue
            record = dict(meta)
            if idx < len(ids):
                record.setdefault("id", ids[idx])
            if idx < len(docs):
                record.setdefault("document", docs[idx])
            videos.append(record)
        return videos

    def get_items(self, ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        ids = list(ids)
        if not ids:
            return {}
        found: Dict[str, Dict[str, Any]] = {}
        for start in range(0, len(ids), _BATCH_SIZE):
            subset = ids[start:start + _BATCH_SIZE]
            batch = self.collection.get(
                ids=subset,
                include=["embeddings", "metadatas", "documents"],
            )
            got_ids = batch.get("ids") or []
            embeddings = batch.get("embeddings") or []
            metadatas = batch.get("metadatas") or []
            documents = batch.get("documents") or []
            for idx, vid in enumerate(got_ids):
                found[vid] = {
                    "embedding": embeddings[idx] if idx < len(embeddings) else None,
                    "metadata": metadatas[idx] if idx < len(metadatas) else {},
                    "document": documents[idx] if idx < len(documents) else "",
                }
        return found
