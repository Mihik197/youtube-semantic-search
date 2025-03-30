# youtube_utils.py
import time
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tqdm import tqdm
import config # Import our configuration

def fetch_youtube_details(video_ids):
    """
    Fetches video details (snippet) from the YouTube Data API v3 for a list of video IDs.

    Args:
        video_ids (list): A list of YouTube video ID strings.

    Returns:
        list: A list of dictionaries, where each dictionary contains details
              for a successfully fetched video (id, title, description, channel, tags, url).
              Returns an empty list if the API key is invalid or other critical errors occur.
    """
    # --- START DEBUGGING ---
    print("-" * 20)
    print(f"DEBUG: Attempting to use YouTube API Key: '{config.YOUTUBE_API_KEY}'")
    if config.YOUTUBE_API_KEY == 'YOUR_YOUTUBE_API_KEY_HERE':
        print("DEBUG: WARNING! The key value is still the placeholder text!")
    elif not config.YOUTUBE_API_KEY:
        print("DEBUG: ERROR! The key value is empty or None!")
    else:
        print("DEBUG: Key value appears to be set from config.")
    print("-" * 20)
    # --- END DEBUGGING ---


    if not config.YOUTUBE_API_KEY:
        print("YouTube API Key not configured in config.py or .env file.")
        return []

    try:
        # Build the YouTube service object using the key from config
        youtube = build('youtube', 'v3', developerKey=config.YOUTUBE_API_KEY)
    except Exception as e:
        print(f"Error building YouTube service object: {e}")
        return []

    all_video_details = []
    processed_count = 0
    error_count = 0

    print(f"Fetching details for {len(video_ids)} YouTube video IDs...")

    for i in tqdm(range(0, len(video_ids), config.YOUTUBE_API_BATCH_SIZE), desc="YouTube API Batches"):
        batch_ids = video_ids[i:i + config.YOUTUBE_API_BATCH_SIZE]

        try:
            request = youtube.videos().list(
                part="snippet",  # Fetches title, description, channelTitle, tags
                id=",".join(batch_ids)
            )
            response = request.execute() # <-- This is where the error happens

            for item in response.get('items', []):
                snippet = item.get('snippet', {})
                video_id = item.get('id')
                title = snippet.get('title')
                description = snippet.get('description')
                channel_title = snippet.get('channelTitle')
                tags = snippet.get('tags', []) # Get tags, default to empty list

                # Basic validation: Ensure we have an ID and title at least
                if video_id and title:
                    all_video_details.append({
                        'id': video_id,
                        'title': title,
                        'description': description or '', # Ensure description is not None
                        'channel': channel_title or '', # Ensure channel is not None
                        'tags': tags,
                        'url': f'https://www.youtube.com/watch?v={video_id}'
                    })
                    processed_count += 1
                else:
                     print(f"Warning: Skipping item with missing ID or Title in batch starting {i}. Data: {item}")
                     error_count += 1


            # Respect API rate limits/quotas
            time.sleep(config.YOUTUBE_API_DELAY)

        except HttpError as e:
            print(f"\nHTTP Error fetching batch starting at index {i}: {e}")
            # --- DEBUG: Print the key value *again* right when the error occurs ---
            print(f"DEBUG (on error): Key used was reported as: '{config.YOUTUBE_API_KEY}'")
            # --- END DEBUG ---
            if e.resp.status == 403: # Quota exceeded or key issue (though 400 is key invalid)
                 print("Likely Quota Exceeded or Invalid API Key/Permissions. Stopping YouTube fetch.")
                 break # Stop fetching if we hit quota/key issues
            # The error is 400, explicitly 'badRequest' due to invalid key here
            print("API Key seems invalid according to Google. Please double-check the key and project settings.")
            # Decide whether to stop or keep trying other batches (stopping is safer)
            print("Stopping YouTube fetch due to invalid key error.")
            break # Stop processing further batches

        except Exception as e:
            print(f"\nUnexpected Error fetching batch starting at index {i}: {e}")
            error_count += len(batch_ids)
            print("Continuing with next batch...")
            time.sleep(2)


    print(f"Finished fetching YouTube details.")
    print(f"Successfully processed: {processed_count}, Errors/Skipped: {error_count}")
    return all_video_details