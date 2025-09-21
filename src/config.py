import os
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(ROOT_DIR, '.env'))

YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

TAKEOUT_CSV_FILE = os.path.join(ROOT_DIR, 'Watch later-videos.csv')
CHROMA_DB_PATH = os.path.join(ROOT_DIR, "chroma_watch_later_db")

EMBEDDING_MODEL_NAME = "models/text-embedding-004"
TASK_TYPE_RETRIEVAL_DOCUMENT = "RETRIEVAL_DOCUMENT"
TASK_TYPE_RETRIEVAL_QUERY = "RETRIEVAL_QUERY"

YOUTUBE_API_BATCH_SIZE = 50
YOUTUBE_API_DELAY = 0.1

EMBEDDING_BATCH_SIZE = 80
EMBEDDING_API_DELAY = 15.1

CHROMA_COLLECTION_NAME = "youtube_videos_gemini_std_v2"
CHROMA_BATCH_SIZE = 100

DEFAULT_SEARCH_RESULTS = 40

# --- LLM Re-Ranking Configuration ---
ENABLE_LLM_RERANK = 'true'
RERANK_CANDIDATES = int('50')
RERANK_MODEL_NAME = 'gemini-2.5-flash-lite'
RERANK_TIMEOUT_SECONDS = int('18')
# Truncation limits for prompt token control.
RERANK_MAX_DESCRIPTION_CHARS = int('500')
RERANK_MAX_TAGS = int('10')
RERANK_LOG_TOKEN_USAGE = 'true'

# --- Input Data Configuration ---
POSSIBLE_VIDEO_ID_COLUMNS = ['Video ID', 'videoId', 'VIDEO_ID', 'Content ID']

def validate_config():
    """Validates the essential configuration variables."""
    if not YOUTUBE_API_KEY:
        print("Validation Error: YOUTUBE_API_KEY is not set in your .env file.")
        return False
    if not GEMINI_API_KEY:
        print("Validation Error: GEMINI_API_KEY is not set in your .env file.")
        return False
    if not os.path.exists(TAKEOUT_CSV_FILE):
        print(f"Validation Error: CSV file not found at '{TAKEOUT_CSV_FILE}'.")
        print("Please ensure 'Watch later-videos.csv' is in the project root directory.")
        return False
    return True

IS_CONFIG_VALID = validate_config()
