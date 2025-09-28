# src/services/channel_service.py
from __future__ import annotations

import time
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional

from src.config import CHROMA_COLLECTION_NAME, CHROMA_DB_PATH
from src.services.duration_utils import format_watch_time
from src.services.vectordb_service import VectorDBService

_UNKNOWN = "(Unknown Channel)"


class ChannelAggregationService:
    """Build and cache aggregate channel statistics."""

    def __init__(self) -> None:
        self.vectordb = VectorDBService(path=CHROMA_DB_PATH, collection_name=CHROMA_COLLECTION_NAME)
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_total = -1
        self._lock = Lock()

    def _normalize(self, name: Optional[str]) -> str:
        if not name:
            return _UNKNOWN
        name = name.strip()
        return name or _UNKNOWN

    def _build_cache(self) -> None:
        start = time.perf_counter()
        total = self.vectordb.count()
        if self._cache and self._cache_total == total:
            return

        metadatas = self.vectordb.get_all_metadatas()
        channels: Dict[str, Dict[str, Any]] = {}
        for meta in metadatas:
            channel = self._normalize(meta.get("channel"))
            entry = channels.setdefault(
                channel,
                {
                    "channel": channel,
                    "count": 0,
                    "channel_thumbnail": meta.get("channel_thumbnail"),
                    "total_duration_seconds": 0,
                },
            )
            entry["count"] += 1
            duration = meta.get("duration_seconds")
            if isinstance(duration, (int, float)) and duration > 0:
                entry["total_duration_seconds"] += int(duration)
            elif isinstance(duration, str) and duration.isdigit():
                entry["total_duration_seconds"] += int(duration)
            if not entry.get("channel_thumbnail") and meta.get("channel_thumbnail"):
                entry["channel_thumbnail"] = meta.get("channel_thumbnail")

        channel_rows: List[Dict[str, Any]] = []
        for stats in channels.values():
            percent = (stats["count"] / total * 100) if total else 0
            stats["percent"] = round(percent, 2)
            seconds = stats.get("total_duration_seconds") or 0
            stats["watch_time"] = format_watch_time(seconds) if seconds else None
            channel_rows.append(stats)

        self._cache = {
            "total_videos": total,
            "distinct_channels": len(channel_rows),
            "channels": channel_rows,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "stale": False,
            "build_time_ms": int((time.perf_counter() - start) * 1000),
        }
        self._cache_total = total

    def get_channels(self, sort: str, limit: Optional[int], offset: int, q: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            self._build_cache()
            data = self._cache or {
                "total_videos": 0,
                "distinct_channels": 0,
                "channels": [],
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "stale": True,
                "build_time_ms": 0,
            }

        channels = data["channels"]
        if q:
            query = q.strip().lower()
            if query:
                channels = [row for row in channels if query in row["channel"].lower()]

        if sort == "count_asc":
            channels = sorted(channels, key=lambda row: row["count"])
        elif sort == "alpha":
            channels = sorted(channels, key=lambda row: row["channel"].lower())
        elif sort == "alpha_desc":
            channels = sorted(channels, key=lambda row: row["channel"].lower(), reverse=True)
        else:
            channels = sorted(channels, key=lambda row: row["count"], reverse=True)

        total_available = len(channels)
        limit = None if limit is None else max(0, limit)
        offset = max(0, offset)
        sliced = channels[offset : offset + limit] if limit is not None else channels[offset:]
        has_more = limit is not None and (offset + len(sliced)) < total_available

        return {
            "total_videos": data["total_videos"],
            "distinct_channels": data["distinct_channels"],
            "total_available": total_available,
            "returned": len(sliced),
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "sort": sort,
            "stale": data.get("stale", False),
            "q": q.strip() if q else None,
            "channels": sliced,
        }


_channel_service: ChannelAggregationService | None = None


def get_channel_aggregation_service() -> ChannelAggregationService:
    global _channel_service
    if _channel_service is None:
        _channel_service = ChannelAggregationService()
    return _channel_service
