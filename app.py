# app.py
from flask import Flask, render_template, request, jsonify
from src.config import DEFAULT_SEARCH_RESULTS, EMBEDDING_MODEL_NAME, CHROMA_COLLECTION_NAME, IS_CONFIG_VALID
from src.core.search import search_videos
from src.services.vectordb_service import VectorDBService
from src.config import CHROMA_DB_PATH, CHROMA_COLLECTION_NAME
from src.services.channel_service import get_channel_aggregation_service
from src.services.vectordb_service import VectorDBService

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

@app.route('/channels', methods=['GET'])
def channels():
    try:
        sort = request.args.get('sort', 'count_desc')
        if sort not in {'count_desc', 'count_asc', 'alpha', 'alpha_desc'}:
            sort = 'count_desc'
        # Limit safeguards
        limit_param = request.args.get('limit')
        try:
            limit = int(limit_param) if limit_param is not None else None
        except ValueError:
            limit = None
        if limit is not None:
            # enforce reasonable cap
            limit = min(max(limit, 0), 500)
        offset_param = request.args.get('offset', '0')
        try:
            offset = int(offset_param)
        except ValueError:
            offset = 0
        if offset < 0:
            offset = 0
        svc = get_channel_aggregation_service()
        data = svc.get_channels(sort=sort, limit=limit, offset=offset)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve channels', 'detail': str(e)}), 500

@app.route('/channel_videos', methods=['GET'])
def channel_videos():
    channel = request.args.get('channel', '').strip()
    if not channel:
        return jsonify({'error': 'channel parameter required'}), 400
    try:
        vectordb = VectorDBService(path=CHROMA_DB_PATH, collection_name=CHROMA_COLLECTION_NAME)
        videos = vectordb.get_videos_by_channel(channel)
        # Shape response similar to search results minimal subset
        shaped = []
        for v in videos:
            vid = v.get('id') or v.get('video_id')
            shaped.append({
                'id': vid,
                'title': v.get('title', 'N/A'),
                'channel': v.get('channel', channel),
                'url': v.get('url', f'https://www.youtube.com/watch?v={vid}' if vid else '#'),
                'score': 0.0,
                'thumbnail': f"https://img.youtube.com/vi/{vid}/hqdefault.jpg" if vid else None,
                'tags': v.get('tags_str', ''),
                'document': v.get('document', ''),
                'metadata': v
            })
        return jsonify({'results': shaped, 'count': len(shaped), 'channel': channel})
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve channel videos', 'detail': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
