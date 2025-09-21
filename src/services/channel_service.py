# src/services/channel_service.py
from __future__ import annotations
import time
from datetime import datetime, timezone
from typing import List, Dict, Any
from threading import Lock

from src.services.vectordb_service import VectorDBService
from src.services.duration_utils import format_watch_time
from src.config import CHROMA_DB_PATH, CHROMA_COLLECTION_NAME

_UNKNOWN = "(Unknown Channel)"

class ChannelAggregationService:
    """Aggregates and caches channel counts from the vector DB metadata."""

    _instance = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        # simple singleton to share cache across requests
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, '_initialized', False):
            return
        self.vectordb = VectorDBService(path=CHROMA_DB_PATH, collection_name=CHROMA_COLLECTION_NAME)
        self._cache = {}
        self._cache_total_count = None
        self._cache_timestamp = None
        self._rebuild_lock = Lock()
        self._initialized = True

    def _normalize_channel(self, name: str | None) -> str:
        if not name:
            return _UNKNOWN
        norm = name.strip()
        return norm if norm else _UNKNOWN

    def _build_cache(self):
        with self._rebuild_lock:
            start = time.time()
            try:
                metadatas = self.vectordb.get_all_metadatas()
                total = len(metadatas)
                counts: Dict[str, Dict[str, Any]] = {}
                for m in metadatas:
                    try:
                        channel = self._normalize_channel(m.get('channel'))
                        thumb = m.get('channel_thumbnail') or None
                        dur = m.get('duration_seconds')
                        try:
                            dur_int = int(dur) if dur is not None else None
                            if dur_int is not None and dur_int < 0:
                                dur_int = None
                        except (TypeError, ValueError):
                            dur_int = None
                        entry = counts.get(channel)
                        if entry is None:
                            counts[channel] = {
                                'channel': channel,
                                'count': 1,
                                'channel_thumbnail': thumb,
                                'total_duration_seconds': dur_int or 0
                            }
                        else:
                            entry['count'] += 1
                            if dur_int is not None:
                                entry['total_duration_seconds'] += dur_int
                            # If we don't yet have a thumbnail stored and this metadata has one, set it
                            if not entry.get('channel_thumbnail') and thumb:
                                entry['channel_thumbnail'] = thumb
                    except Exception as inner:
                        print(f"ChannelAggregationService warning: failed to process metadata item: {inner}")
                channels_list: List[Dict[str, Any]] = []
                if total > 0:
                    for ch_data in counts.values():
                        percent = (ch_data['count'] / total) * 100 if total else 0
                        ch_data['percent'] = round(percent, 2)
                        # Derive human readable watch time string
                        tsec = ch_data.get('total_duration_seconds')
                        if isinstance(tsec, int) and tsec > 0:
                            ch_data['watch_time'] = format_watch_time(tsec)
                        else:
                            ch_data['watch_time'] = None
                        channels_list.append(ch_data)
                self._cache = {
                    'total_videos': total,
                    'distinct_channels': len(channels_list),
                    'channels': channels_list,
                    'generated_at': datetime.now(timezone.utc).isoformat(),
                    'stale': False,
                    'build_time_ms': int((time.time() - start) * 1000)
                }
                self._cache_total_count = total
                self._cache_timestamp = time.time()
                print(f"ChannelAggregationService cache built in {self._cache['build_time_ms']} ms with {self._cache['distinct_channels']} channels.")
            except Exception as e:
                print(f"ChannelAggregationService error building cache: {e}")
                # keep previous cache if exists; else set empty
                if not self._cache:
                    self._cache = {
                        'total_videos': 0,
                        'distinct_channels': 0,
                        'channels': [],
                        'generated_at': datetime.now(timezone.utc).isoformat(),
                        'stale': True,
                        'build_time_ms': int((time.time() - start) * 1000)
                    }

    def _ensure_cache(self):
        current_total = self.vectordb.count()
        if not self._cache or self._cache_total_count != current_total:
            self._build_cache()

    def get_channels(self, sort: str, limit: int | None, offset: int, q: str | None = None) -> Dict[str, Any]:
        """Return (optionally) filtered + sorted + paginated channel list.

        q: optional case-insensitive substring filter applied to channel name BEFORE sorting/pagination.
        """
        self._ensure_cache()
        data = self._cache
        channels = data.get('channels', [])

        # Apply filter first so pagination reflects filtered dataset
        query = (q or '').strip().lower()
        if query:
            channels = [c for c in channels if query in c['channel'].lower()]

        # Sorting
        if sort == 'count_asc':
            channels_sorted = sorted(channels, key=lambda x: x['count'])
        elif sort == 'alpha':
            channels_sorted = sorted(channels, key=lambda x: x['channel'].lower())
        elif sort == 'alpha_desc':
            channels_sorted = sorted(channels, key=lambda x: x['channel'].lower(), reverse=True)
        else:  # default count_desc
            channels_sorted = sorted(channels, key=lambda x: x['count'], reverse=True)

        total_available = len(channels_sorted)
        if limit is not None:
            limit = max(0, limit)
        if offset < 0:
            offset = 0

        sliced = channels_sorted[offset: offset + limit] if limit is not None else channels_sorted[offset:]

        has_more = False
        if limit is not None:
            has_more = (offset + len(sliced)) < total_available
        response = {
            'total_videos': data['total_videos'],          # total videos in collection (unfiltered)
            'distinct_channels': data['distinct_channels'], # distinct channels in collection (unfiltered)
            'total_available': total_available,             # total channels after filtering
            'returned': len(sliced),
            'offset': offset,
            'limit': limit,
            'has_more': has_more,
            'sort': sort,
            'stale': data.get('stale', False),
            'q': query if query else None,
            'channels': sliced
        }
        return response

# Convenience accessor
_channel_service: ChannelAggregationService | None = None

def get_channel_aggregation_service() -> ChannelAggregationService:
    global _channel_service
    if _channel_service is None:
        _channel_service = ChannelAggregationService()
    return _channel_service
