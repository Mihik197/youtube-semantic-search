# YouTube Watch Later Semantic Search

A semantic search engine for your YouTube 'Watch Later' list. This project uses Google's Gemini embedding model to understand the meaning behind your search queries and finds relevant videos from your saved list stored in a ChromaDB vector database.

![Search Interface](images/image.png?)
![Search Results](images/image-1.png?)
![Video Details](images/image-2.png?)

## Features

-   **Semantic Search:** Goes beyond keyword matching to understand the intent and context of your search queries.
-   **Google Gemini Embeddings:** Uses the `models/text-embedding-004` model for generating high-quality vector embeddings of video metadata.
-   **ChromaDB Integration:** Stores and efficiently searches through video embeddings.
-   **YouTube Data API:** Fetches detailed video information (titles, descriptions, tags, channel).
-   **Incremental Data Ingestion:** Processes your YouTube 'Watch Later' list from a CSV export, only adding new videos and removing ones that are no longer on the list.
-   **Web & CLI Interfaces:** Provides both a user-friendly web interface (via Flask) and a command-line interface for searching.

## Architecture

The project is organized into a `src` directory containing the core application logic, and a root directory containing the entry points for the application.

```
.
├── src/
│   ├── core/
│   │   ├── pipeline.py       # The main data ingestion pipeline
│   │   └── search.py         # The core search logic
│   ├── services/
│   │   ├── embedding_service.py # Service for generating Gemini embeddings
│   │   ├── vectordb_service.py  # Service for interacting with ChromaDB
│   │   └── youtube_service.py   # Service for interacting with the YouTube API
│   └── config.py             # Configuration settings
├── app.py                  # Entry point for the Flask web application
├── cli_app.py              # Entry point for the command-line interface
├── ingest_data.py          # Entry point for the data ingestion pipeline
├── requirements.txt        # Python dependencies
├── Watch later-videos.csv  # Your YouTube 'Watch Later' export (example)
├── chroma_watch_later_db/  # ChromaDB vector store
├── images/                 # Screenshots for README
├── static/                 # Static assets for web interface (CSS, JS)
└── templates/              # HTML templates for web interface
```

## Setup and Installation

1.  **Clone the repository:**

    ```bash
    git clone <repository-url>
    cd youtube-semantic-search
    ```

2.  **Create a virtual environment and activate it:**

    ```bash
    python -m venv venv
    # On Windows
    .\venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up API Keys:**

    -   Create a `.env` file in the root directory.
    -   Add your API keys to the `.env` file:
        ```env
        YOUTUBE_API_KEY="YOUR_YOUTUBE_API_KEY"
        GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
        ```
    -   You can obtain a YouTube API key from the [Google Cloud Console](https://console.cloud.google.com/).
    -   You can obtain a Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey).

5.  **Prepare your YouTube Data:**
    -   Export your 'Watch Later' list from YouTube. Typically, this can be done via [Google Takeout](https://takeout.google.com/). Ensure you get a CSV file.
    -   Place the CSV file in the root directory and make sure the filename matches the `TAKEOUT_CSV_FILE` variable in `src/config.py`.

## Usage

1.  **Ingest Data:**
    Run the ingestion script to process your YouTube data, fetch details, generate embeddings, and store them in ChromaDB. This script performs an incremental update, so it will only process new or removed videos on subsequent runs.

    ```bash
    python ingest_data.py
    ```

2.  **Run the Search Application:**
    You can search your videos using either the web interface or the command-line tool.

    **Option A: Web Interface**
    Launch the Flask web application:

    ```bash
    python app.py
    ```
    This will start a local server, and you can access the search interface in your web browser at `http://127.0.0.1:5000`.

    **Option B: Command-Line Interface (CLI)**
    Run the CLI application for a terminal-based search experience:
    ```bash
    python cli_app.py
    ```

3.  **Search Your Videos:**
    -   Enter your search query.
    -   The application will display relevant videos from your 'Watch Later' list, along with their thumbnails, titles, channels, and a relevance score.

## Configuration

Key configuration options can be found in `src/config.py`:

-   `YOUTUBE_API_KEY`, `GEMINI_API_KEY`: Your API keys (preferably set via `.env`).
-   `TAKEOUT_CSV_FILE`: Path to your YouTube 'Watch Later' CSV.
-   `CHROMA_DB_PATH`: Directory to store the ChromaDB database.
-   `EMBEDDING_MODEL_NAME`: The Gemini embedding model to use.
-   `CHROMA_COLLECTION_NAME`: Name of the collection in ChromaDB.
-   `DEFAULT_SEARCH_RESULTS`: Default number of search results to display.

## Dependencies

The main dependencies are listed in `requirements.txt`:

-   `flask`: For the web application interface.
-   `pandas`: For data manipulation, especially reading the CSV.
-   `google-api-python-client`: For interacting with the YouTube Data API.
-   `google-genai`: For using the Google Gemini embedding models.
-   `chromadb`: The vector database for storing and searching embeddings.
-   `tqdm`: For displaying progress bars during data ingestion.
-   `python-dotenv`: For managing environment variables (API keys).

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue.

## License

This project is licensed under the MIT License.

## Deleted / Removed Video Archival

Ingestion automatically logs missing (likely deleted/private) video IDs and archives any previously cached metadata to `data/deleted_videos_archive.jsonl` with a lightweight index (`deleted_videos_index.json`) for historical reference.
