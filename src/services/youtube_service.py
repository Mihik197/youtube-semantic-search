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
        
        print(f"Fetching details for {len(video_ids)} YouTube video IDs...")

        for i in tqdm(range(0, len(video_ids), config.YOUTUBE_API_BATCH_SIZE), desc="YouTube API Batches"):
            batch_ids = video_ids[i:i + config.YOUTUBE_API_BATCH_SIZE]

            try:
                request = self.youtube.videos().list(
                    part="snippet",
                    id=",".join(batch_ids)
                )
                response = request.execute()

                for item in response.get('items', []):
                    snippet = item.get('snippet', {})
                    video_id = item.get('id')
                    
                    if video_id and snippet.get('title'):
                        all_video_details.append({
                            'id': video_id,
                            'title': snippet.get('title'),
                            'description': snippet.get('description', ''),
                            'channel': snippet.get('channelTitle', ''),
                            'tags': snippet.get('tags', []),
                            'url': f'https://www.youtube.com/watch?v={video_id}'
                        })
                        processed_count += 1
                    else:
                        print(f"Warning: Skipping item with missing ID or Title. Data: {item}")
                        error_count += 1
                
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
        
        print(f"Finished fetching YouTube details. Processed: {processed_count}, Errors/Skipped: {error_count}")
        return all_video_details
