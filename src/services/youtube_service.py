from __future__ import annotations

import logging
import time
from typing import Dict, Iterable, Iterator, List, Sequence

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src import config


logger = logging.getLogger(__name__)


def _chunk(sequence: Sequence[str], size: int) -> Iterator[List[str]]:
    for start in range(0, len(sequence), size):
        yield list(sequence[start : start + size])


class YouTubeService:
    """Thin wrapper around the YouTube Data API v3."""

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("YouTube API key is required")
        self.youtube = build("youtube", "v3", developerKey=api_key)
        self.last_missing_ids: List[str] = []

    # ------------------------------------------------------------------
    # Video metadata
    # ------------------------------------------------------------------
    def fetch_video_details(self, video_ids: Sequence[str]) -> List[Dict]:
        if not video_ids:
            self.last_missing_ids = []
            return []

        batch_size = getattr(config, "YOUTUBE_API_BATCH_SIZE", 50)
        delay = getattr(config, "YOUTUBE_API_DELAY", 0)

        requested_ids = [vid for vid in video_ids if vid]
        requested_set = set(requested_ids)
        details: List[Dict] = []
        channel_ids: set[str] = set()

        for batch in _chunk(requested_ids, batch_size):
            try:
                response = (
                    self.youtube.videos()
                    .list(part="snippet,contentDetails", id=",".join(batch))
                    .execute()
                )
            except HttpError as error:
                logger.warning("YouTube videos.list failed: %s", error)
                if getattr(error, "resp", None) and getattr(error.resp, "status", None) in {403, 404}:
                    break
                continue
            except Exception as error:  # pragma: no cover - network failures
                logger.warning("Unexpected YouTube client error: %s", error)
                continue

            returned = set()
            for item in response.get("items", []):
                snippet = item.get("snippet", {})
                content_details = item.get("contentDetails", {})
                video_id = item.get("id")
                title = snippet.get("title")
                if not video_id or not title:
                    logger.debug("Skipping malformed API item: %s", item)
                    continue

                returned.add(video_id)
                channel_id = snippet.get("channelId")
                if channel_id:
                    channel_ids.add(channel_id)

                details.append(
                    {
                        "id": video_id,
                        "title": title,
                        "description": snippet.get("description", ""),
                        "channel": snippet.get("channelTitle", ""),
                        "channel_id": channel_id,
                        "tags": snippet.get("tags", []),
                        "publishedAt": snippet.get("publishedAt"),
                        "duration": content_details.get("duration"),
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                    }
                )

            missing = set(batch) - returned
            if missing:
                logger.debug("%d IDs missing from batch", len(missing))

            if delay:
                time.sleep(delay)

        returned_ids = {video["id"] for video in details}
        self.last_missing_ids = sorted(requested_set - returned_ids)

        if channel_ids:
            thumbnails = self.fetch_channel_thumbnails(channel_ids)
            for video in details:
                channel_id = video.get("channel_id")
                if channel_id and channel_id in thumbnails:
                    video["channel_thumbnail"] = thumbnails[channel_id]

        return details

    # ------------------------------------------------------------------
    # Channel helpers
    # ------------------------------------------------------------------
    def fetch_channel_thumbnails(self, channel_ids: Iterable[str]) -> Dict[str, str]:
        ids = [cid for cid in dict.fromkeys(channel_ids) if cid]
        if not ids:
            return {}

        batch_size = getattr(config, "YOUTUBE_API_BATCH_SIZE", 50)
        delay = getattr(config, "YOUTUBE_API_DELAY", 0)

        thumbnails: Dict[str, str] = {}
        for batch in _chunk(ids, batch_size):
            try:
                response = (
                    self.youtube.channels()
                    .list(part="snippet", id=",".join(batch))
                    .execute()
                )
            except HttpError as error:
                logger.warning("YouTube channels.list failed: %s", error)
                continue
            except Exception as error:  # pragma: no cover - network failures
                logger.warning("Unexpected YouTube channel error: %s", error)
                continue

            for item in response.get("items", []):
                channel_id = item.get("id")
                if not channel_id:
                    continue
                thumbs = (item.get("snippet", {}) or {}).get("thumbnails", {})
                for quality in ("high", "medium", "default"):
                    candidate = thumbs.get(quality, {})
                    url = candidate.get("url") if isinstance(candidate, dict) else None
                    if url:
                        thumbnails[channel_id] = url
                        break

            if delay:
                time.sleep(delay)

        return thumbnails
