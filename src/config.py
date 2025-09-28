from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

TAKEOUT_CSV_FILE = ROOT_DIR / "Watch later-videos.csv"
CHROMA_DB_PATH = ROOT_DIR / "chroma_watch_later_db"

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
ENABLE_LLM_RERANK = True
RERANK_CANDIDATES = 50
RERANK_MODEL_NAME = "gemini-flash-lite-latest"
RERANK_TIMEOUT_SECONDS = 18
RERANK_MAX_DESCRIPTION_CHARS = 500
RERANK_MAX_TAGS = 10
RERANK_LOG_TOKEN_USAGE = True

# --- Input Data Configuration ---
POSSIBLE_VIDEO_ID_COLUMNS = ["Video ID", "videoId", "VIDEO_ID", "Content ID"]


def validate_config() -> bool:
    """Basic runtime checks for critical configuration values."""

    ok = True
    if not YOUTUBE_API_KEY:
        print("Validation Error: YOUTUBE_API_KEY is not set in your .env file.")
        ok = False
    if not GEMINI_API_KEY:
        print("Validation Error: GEMINI_API_KEY is not set in your .env file.")
        ok = False
    if not TAKEOUT_CSV_FILE.exists():
        print(f"Validation Error: CSV file not found at '{TAKEOUT_CSV_FILE}'.")
        print("Please ensure 'Watch later-videos.csv' is in the project root directory.")
        ok = False
    return ok


IS_CONFIG_VALID = validate_config()

# --- Topic Clustering Configuration (HDBSCAN) ---
ENABLE_TOPIC_CLUSTERING = True
TOPIC_CLUSTERING_MIN_CLUSTER_SIZE_FLOOR = 5
TOPIC_CLUSTERING_MIN_CLUSTER_SIZE_MAX = 150
TOPIC_CLUSTERING_SAMPLE_VALIDITY_MAX = 1000
TOPIC_CLUSTERING_LABEL_MAX_KEYWORDS = 4
TOPIC_CLUSTERING_SNAPSHOT_PATH = ROOT_DIR / "data" / "topic_clusters.json"
TOPIC_CLUSTERING_ENABLE_LLM_LABELS = False
TOPIC_CLUSTERING_DEBUG = True
TOPIC_CLUSTERING_LLM_MODEL = "gemini-flash-lite-latest"
TOPIC_CLUSTERING_DIM_REDUCTION = "pca"
TOPIC_CLUSTERING_PCA_MAX_COMPONENTS = 50
TOPIC_CLUSTERING_PCA_VARIANCE_THRESHOLD = 0.90
TOPIC_CLUSTERING_SHOW_NOISE = False
TOPIC_CLUSTERING_MAX_EXEMPLAR_TITLE_CHARS = 140
TOPIC_CLUSTERING_REBUILD_ON_START_IF_MISSING = True
TOPIC_CLUSTERING_MAX_MICRO_CLUSTER_SIZE = 2
TOPIC_CLUSTERING_NOISE_RATIO_RETRY_THRESHOLD = 0.40
TOPIC_CLUSTERING_LOW_CLUSTER_COUNT_RETRY_THRESHOLD = 2
TOPIC_CLUSTERING_ADAPTIVE_MIN_SAMPLES_FACTOR = 0.75
