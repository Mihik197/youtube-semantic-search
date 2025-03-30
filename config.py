# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys ---
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# --- File Paths ---
TAKEOUT_CSV_FILE = 'Watch later-videos.csv' # Match your actual filename
CHROMA_DB_PATH = "./chroma_watch_later_db"
# --- Intermediate Results Filenames ---
YOUTUBE_DETAILS_FILE = "intermediate_youtube_details.json"
EMBEDDINGS_DATA_FILE = "intermediate_embeddings_data.json"

# --- Model Configuration ---
EMBEDDING_MODEL_NAME = "models/text-embedding-004"
TASK_TYPE_RETRIEVAL_DOCUMENT = "RETRIEVAL_DOCUMENT"
TASK_TYPE_RETRIEVAL_QUERY = "RETRIEVAL_QUERY"

# --- YouTube API Settings ---
YOUTUBE_API_BATCH_SIZE = 50
YOUTUBE_API_DELAY = 0.1

# --- Embedding Settings ---
EMBEDDING_BATCH_SIZE = 80
EMBEDDING_API_DELAY = 15.1 # Adjusted to avoid rate limits

# --- ChromaDB Settings ---
# Using a distinct name for this successful model/config run
CHROMA_COLLECTION_NAME = "youtube_videos_gemini_std_v2"
CHROMA_BATCH_SIZE = 100

# --- Search Settings ---
DEFAULT_SEARCH_RESULTS = 10

# --- Input Data Configuration ---
POSSIBLE_VIDEO_ID_COLUMNS = ['Video ID', 'videoId', 'VIDEO_ID', 'Content ID']

# --- Validation ---
def validate_config():
    if not YOUTUBE_API_KEY:
         print("Validation Error: YOUTUBE_API_KEY missing.")
         return False
    if not GEMINI_API_KEY:
         print("Validation Error: GEMINI_API_KEY missing.")
         return False
    if not os.path.exists(TAKEOUT_CSV_FILE):
         print(f"Validation Error: CSV file not found at '{TAKEOUT_CSV_FILE}'. Check filename in config.py.")
         return False
    return True
IS_CONFIG_VALID = validate_config()