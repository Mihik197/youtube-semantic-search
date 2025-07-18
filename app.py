# app.py
from flask import Flask, render_template, request, jsonify
from src.config import DEFAULT_SEARCH_RESULTS, EMBEDDING_MODEL_NAME, CHROMA_COLLECTION_NAME, IS_CONFIG_VALID
from src.core.search import search_videos
from src.services.vectordb_service import VectorDBService
from src.config import CHROMA_DB_PATH, CHROMA_COLLECTION_NAME

app = Flask(__name__)

# Initialize the VectorDBService to get the collection count
try:
    vectordb_service = VectorDBService(path=CHROMA_DB_PATH, collection_name=CHROMA_COLLECTION_NAME)
    db_count = vectordb_service.count()
    collection_empty = db_count == 0
except Exception as e:
    print(f"Failed to initialize VectorDBService: {e}")
    db_count = 0
    collection_empty = True

@app.route('/')
def index():
    return render_template('index.html', 
                          db_count=db_count, 
                          collection_name=CHROMA_COLLECTION_NAME,
                          collection_empty=collection_empty,
                          default_results=DEFAULT_SEARCH_RESULTS,
                          embedding_model=EMBEDDING_MODEL_NAME)

@app.route('/search', methods=['POST'])
def search():
    if not request.json:
        return jsonify({'error': 'No search parameters provided'}), 400
    
    query = request.json.get('query', '')
    n_results = int(request.json.get('num_results', DEFAULT_SEARCH_RESULTS))
    
    if not query:
        return jsonify({'error': 'No search query provided'}), 400
    
    search_results = search_videos(query, n_results=n_results)
    
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
        'db_count': db_count,
        'config_valid': IS_CONFIG_VALID,
        'model': EMBEDDING_MODEL_NAME,
        'collection': CHROMA_COLLECTION_NAME
    }
    return jsonify(health)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
