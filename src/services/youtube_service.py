# src/services/youtube_service.py
import time
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tqdm import tqdm
from src import config

class YouTubeService:
    """A service class for interacting with the YouTube Data API v3."""

    def __init__(self, api_key: str):
        """
        Initializes the YouTubeService.

        Args:
            api_key (str): The YouTube Data API v3 key.

        Raises:
            ValueError: If the API key is not provided.
            Exception: For errors during the YouTube service object build.
        """
        if not api_key:
            raise ValueError("YouTube API Key not provided.")
        
        print("Building YouTube service object...")
        try:
            self.youtube = build('youtube', 'v3', developerKey=api_key)
            print("YouTube service object built successfully.")
        except Exception as e:
            print(f"Error building YouTube service object: {e}")
            raise

    def fetch_video_details(self, video_ids: list[str]) -> list[dict]:
        """
        Fetches video details (snippet) for a list of video IDs.

        Args:
            video_ids (list[str]): A list of YouTube video ID strings.

        Returns:
            list[dict]: A list of dictionaries with details for each video.
        """
        if not video_ids:
            return []

        all_video_details = []
        processed_count = 0
        error_count = 0
        requested_id_set = set(video_ids)
        self.last_missing_ids = []  # will populate at end for external diagnostics

        print(f"Fetching details for {len(video_ids)} YouTube video IDs...")

        channel_ids: set[str] = set()

        for i in tqdm(range(0, len(video_ids), config.YOUTUBE_API_BATCH_SIZE), desc="YouTube API Batches"):
            batch_ids = video_ids[i:i + config.YOUTUBE_API_BATCH_SIZE]

            try:
                request = self.youtube.videos().list(
                    part="snippet,contentDetails",
                    id=",".join(batch_ids)
                )
                response = request.execute()

                returned_ids_in_batch = set()
                for item in response.get('items', []):
                    snippet = item.get('snippet', {})
                    content_details = item.get('contentDetails', {})
                    video_id = item.get('id')
                    channel_id = snippet.get('channelId') or None
                    
                    if video_id and snippet.get('title'):
                        returned_ids_in_batch.add(video_id)
                        if channel_id:
                            channel_ids.add(channel_id)
                        all_video_details.append({
                            'id': video_id,
                            'title': snippet.get('title'),
                            'description': snippet.get('description', ''),
                            'channel': snippet.get('channelTitle', ''),
                            'channel_id': channel_id,
                            'tags': snippet.get('tags', []),
                            'publishedAt': snippet.get('publishedAt'),
                            'duration': content_details.get('duration'),  # ISO 8601 duration
                            'url': f'https://www.youtube.com/watch?v={video_id}'
                        })
                        processed_count += 1
                    else:
                        print(f"Warning: Skipping item with missing ID or Title. Data: {item}")
                        error_count += 1

                # Detect IDs that were requested but not returned (private, deleted, invalid, region blocked, etc.)
                missing_from_batch = set(batch_ids) - returned_ids_in_batch
                if missing_from_batch:
                    sample_list = list(missing_from_batch)[:5]
                    print(f"Info: {len(missing_from_batch)} IDs in this batch not returned by API (possibly private/deleted/unavailable). Sample: {sample_list}")
                
                time.sleep(config.YOUTUBE_API_DELAY)

            except HttpError as e:
                print(f"\nHTTP Error fetching batch: {e}")
                if e.resp.status in [403, 404]:
                    print("Critical API Error (likely quota, invalid key, or permissions). Stopping YouTube fetch.")
                    break 
                error_count += len(batch_ids)

            except Exception as e:
                print(f"\nUnexpected Error fetching batch: {e}")
                error_count += len(batch_ids)
        
        # Compute missing IDs overall (those not returned at all)
        returned_overall = {d['id'] for d in all_video_details}
        total_missing = len(requested_id_set - returned_overall)
        if total_missing > 0:
            self.last_missing_ids = sorted(list(requested_id_set - returned_overall))
            print(f"Summary: {total_missing} of {len(requested_id_set)} requested IDs not returned by API.")
        else:
            self.last_missing_ids = []
        # Enrich with channel thumbnails (batch fetch)
        try:
            if channel_ids:
                channel_thumb_map = self.fetch_channel_thumbnails(list(channel_ids))
                for v in all_video_details:
                    cid = v.get('channel_id')
                    if cid and cid in channel_thumb_map:
                        v['channel_thumbnail'] = channel_thumb_map[cid]
        except Exception as enrich_e:
            print(f"Warning: Failed to enrich channel thumbnails: {enrich_e}")

        print(f"Finished fetching YouTube details. Processed: {processed_count}, Errors/Skipped: {error_count}")
        return all_video_details

    def fetch_channel_thumbnails(self, channel_ids: list[str]) -> dict[str, str]:
        """Fetch channel thumbnails for a list of channel IDs.

        Uses channels.list (part=snippet). Returns mapping channelId -> thumbnail URL (prefers high > medium > default).
        """
        if not channel_ids:
            return {}
        result: dict[str, str] = {}
        # Deduplicate & batch
        unique_ids = list(dict.fromkeys([cid for cid in channel_ids if cid]))
        for i in range(0, len(unique_ids), config.YOUTUBE_API_BATCH_SIZE):
            batch = unique_ids[i:i + config.YOUTUBE_API_BATCH_SIZE]
            try:
                request = self.youtube.channels().list(part="snippet", id=",".join(batch))
                response = request.execute()
                for item in response.get('items', []):
                    cid = item.get('id')
                    snippet = item.get('snippet', {})
                    thumbs = (snippet.get('thumbnails') or {}) if isinstance(snippet, dict) else {}
                    # Preferred order: high, medium, default
                    thumb_url = None
                    for key in ('high', 'medium', 'default'):
                        if key in thumbs and isinstance(thumbs[key], dict):
                            thumb_url = thumbs[key].get('url')
                            if thumb_url:
                                break
                    if cid and thumb_url:
                        result[cid] = thumb_url
                time.sleep(config.YOUTUBE_API_DELAY)
            except HttpError as e:
                print(f"Channel thumbnails HTTP error: {e}")
            except Exception as e:
                print(f"Unexpected error fetching channel thumbnails: {e}")
        return result
