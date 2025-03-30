# streamlit_app.py
import streamlit as st
import config
from embedding_utils import initialize_gemini_client
from main_search import initialize_chromadb_client
from search_app import search_videos_local as search_videos

# --- Page Configuration ---
st.set_page_config(
    page_title="Watch Later Search",
    page_icon="🎬",
    layout="wide"
)

# --- Caching Functions ---
@st.cache_resource
def load_gemini():
    print("Initializing Gemini Client...")
    client = initialize_gemini_client()
    if not client:
        st.error("Failed to initialize Gemini Client.")
    return client

@st.cache_resource
def load_chromadb():
    print("Initializing ChromaDB Client...")
    client, collection = initialize_chromadb_client()
    if not collection:
        st.error("Failed to initialize ChromaDB Collection.")
    return client, collection

# --- Main App Logic ---
st.title("🎬 YouTube Watch Later Semantic Search")
st.markdown("Enter a query to search through the videos you've saved.")

gemini_client = load_gemini()
chroma_client, chroma_collection = load_chromadb()

if not gemini_client or not chroma_collection:
    st.warning("Application cannot proceed due to client initialization errors.")
    st.stop()

db_count = chroma_collection.count()
if db_count == 0:
    st.warning(f"⚠️ Your ChromaDB collection ('{config.CHROMA_COLLECTION_NAME}') appears to be empty. "
               "Please run `python ingest_data.py` first.", icon="💾")
    st.stop()
else:
    st.sidebar.success(f"Database contains {db_count} videos.", icon="✔️")

# --- Search Interface ---
st.sidebar.header("Search Options")
num_results = st.sidebar.slider(
    "Number of results to display:", 1, 50, config.DEFAULT_SEARCH_RESULTS, 1
)

query = st.text_input("Search for:", placeholder="e.g., python tutorial, history documentary...")

if query:
    with st.spinner(f"Searching for '{query}'..."):
        search_results = search_videos(query, gemini_client, chroma_collection, n_results=num_results)

    st.divider()

    # --- Display Results ---
    if search_results and search_results.get('ids') and search_results['ids'][0]:
        st.subheader(f"Top {len(search_results['ids'][0])} Results:")

        result_ids = search_results['ids'][0]
        distances = search_results['distances'][0]
        metadatas = search_results['metadatas'][0]
        documents = search_results.get('documents', [[]])[0]

        # Calculate number of columns for a pseudo-grid (adjust as needed)
        # Let's try 2 columns for a start
        num_cols = 3
        cols = st.columns(num_cols)

        for i in range(len(result_ids)):
            with cols[i % num_cols]: # Distribute items into columns
                meta = metadatas[i]
                dist = distances[i]
                score = 1 - dist if dist is not None and dist <= 2 else 0
                video_url = meta.get('url', '#')
                video_id = meta.get('id', None) # Get video ID for thumbnail

                st.markdown(f"**[{meta.get('title', 'N/A')}]({video_url})**")
                st.caption(f"Channel: {meta.get('channel', 'N/A')}")

                # --- Display Thumbnail ---
                if video_id:
                    # Use a high-quality default thumbnail URL format
                    thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
                    # Link the thumbnail image to the video URL
                    st.markdown(f"[![{meta.get('title', 'N/A')}]({thumbnail_url})]({video_url})")
                else:
                    st.warning("Thumbnail could not be loaded (Missing Video ID).")

                # Display score below thumbnail
                st.markdown(f"Score: {score:.3f}")

                # --- Expander for Video Embed & Details ---
                with st.expander("▶️ Watch / Details", expanded=False): # Start collapsed
                    if video_url and 'youtube.com' in video_url:
                        st.video(video_url)
                    else:
                        st.warning("Video player could not be loaded (Invalid URL).")

                    st.write("---")
                    tags_str = meta.get('tags_str')
                    if tags_str:
                        st.write(f"**Tags:** {tags_str}")
                    else:
                        st.write("**Tags:** *(None)*")
                    st.write("---")
                    st.write("**Metadata:**")
                    st.json(meta) # Show raw metadata
                    st.write("---")
                    stored_text = documents[i] if i < len(documents) else "N/A"
                    st.text_area("Text Used for Embedding:", stored_text, height=100, key=f"text_{result_ids[i]}") # Slightly smaller text area

                # Add some spacing below each item within the column
                st.markdown("---") # Use markdown divider for spacing

    elif search_results:
        st.info(f"No relevant videos found in your Watch Later list matching '{query}'.")
    else:
        st.error("Search failed during query or DB lookup.")

else:
    st.info("Enter a query above to start searching.")

# --- Footer ---
st.sidebar.divider()
st.sidebar.markdown("---")
st.sidebar.markdown(f"Model: `{config.EMBEDDING_MODEL_NAME}`")
st.sidebar.markdown(f"Collection: `{config.CHROMA_COLLECTION_NAME}`")