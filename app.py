# app.py
from flask import Flask, render_template, request, jsonify
import config
from embedding_utils import initialize_gemini_client, initialize_chromadb_client
from search_app import search_videos_local as search_videos

app = Flask(__name__)

# Initialize clients at startup to avoid re-initialization on each request
print("Initializing Gemini Client...")
gemini_client = initialize_gemini_client()

print("Initializing ChromaDB Client...")
chroma_client, chroma_collection = initialize_chromadb_client()

@app.route('/')
def index():
    db_count = 0
    collection_name = config.CHROMA_COLLECTION_NAME
    collection_empty = True
    
    if chroma_collection:
        db_count = chroma_collection.count()
        collection_empty = db_count == 0
    
    return render_template('index.html', 
                          db_count=db_count, 
                          collection_name=collection_name,
                          collection_empty=collection_empty,
                          default_results=config.DEFAULT_SEARCH_RESULTS,
                          embedding_model=config.EMBEDDING_MODEL_NAME)

@app.route('/search', methods=['POST'])
def search():
    if not request.json:
        return jsonify({'error': 'No search parameters provided'}), 400
    
    query = request.json.get('query', '')
    n_results = int(request.json.get('num_results', config.DEFAULT_SEARCH_RESULTS))
    
    if not query:
        return jsonify({'error': 'No search query provided'}), 400
    
    if not gemini_client or not chroma_collection:
        return jsonify({'error': 'Application failed to initialize properly. Check API keys and ChromaDB.'}), 500
    
    search_results = search_videos(query, gemini_client, chroma_collection, n_results=n_results)
    
    if not search_results or not search_results.get('ids') or not search_results['ids'][0]:
        return jsonify({'results': [], 'message': 'No matching videos found'})
    
    results = []
    result_ids = search_results['ids'][0]
    distances = search_results['distances'][0]
    metadatas = search_results['metadatas'][0]
    documents = search_results.get('documents', [[]])[0]
    
    for i in range(len(result_ids)):
        meta = metadatas[i]
        dist = distances[i]
        score = 1 - dist if dist is not None and dist <= 2 else 0
        video_id = meta.get('id', None)
        
        result = {
            'id': video_id,
            'title': meta.get('title', 'N/A'),
            'channel': meta.get('channel', 'N/A'),
            'url': meta.get('url', '#'),
            'score': float(score),  # Ensure score is JSON serializable
            'thumbnail': f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg" if video_id else None,
            'tags': meta.get('tags_str', ''),
            'document': documents[i] if i < len(documents) else "N/A",
            'metadata': meta
        }
        results.append(result)
    
    return jsonify({'results': results, 'count': len(results)})

@app.route('/healthcheck')
def healthcheck():
    health = {
        'status': 'ok',
        'gemini_client': gemini_client is not None,
        'chroma_client': chroma_client is not None,
        'chroma_collection': chroma_collection is not None,
        'db_count': chroma_collection.count() if chroma_collection else 0,
        'config_valid': config.IS_CONFIG_VALID,
        'model': config.EMBEDDING_MODEL_NAME,
        'collection': config.CHROMA_COLLECTION_NAME
    }
    return jsonify(health)

if __name__ == '__main__':
    if not gemini_client or not chroma_collection:
        print("Warning: Application failed to initialize properly. Check API keys and ChromaDB setup.")
    
    app.run(debug=True, host='0.0.0.0', port=5000)