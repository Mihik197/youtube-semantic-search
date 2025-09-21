# app.py
from flask import Flask, render_template, request, jsonify
from src.config import (
    DEFAULT_SEARCH_RESULTS,
    EMBEDDING_MODEL_NAME,
    CHROMA_COLLECTION_NAME,
    IS_CONFIG_VALID,
    ENABLE_LLM_RERANK,
    RERANK_CANDIDATES,
    GEMINI_API_KEY,
)
from src.core.search import search_videos
from src.services.rerank_service import RerankService, CandidateVideo
from src.services.vectordb_service import VectorDBService
from src.config import CHROMA_DB_PATH, CHROMA_COLLECTION_NAME
from src.services.channel_service import get_channel_aggregation_service
from src.services.vectordb_service import VectorDBService

app = Flask(__name__)

def distance_to_similarity(dist: float | None) -> float:
    if dist is None:
        return 0.0
    try:
        # distances from cosine in Chroma are usually 0..2; clamp defensively
        if dist < 0:
            return 0.0
        if dist > 2:
            return 0.0
        return 1 - dist
    except Exception:
        return 0.0

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
    query = request.json.get('query', '').strip()
    display_n = int(request.json.get('num_results', DEFAULT_SEARCH_RESULTS))
    if display_n <= 0:
        display_n = DEFAULT_SEARCH_RESULTS
    if not query:
        return jsonify({'error': 'No search query provided'}), 400

    # Determine retrieval size (may exceed display size for reranking headroom)
    retrieve_n = max(display_n, RERANK_CANDIDATES if ENABLE_LLM_RERANK else display_n)

    search_results = search_videos(query, n_results=retrieve_n)
    if not search_results or not search_results.get('ids') or not search_results['ids'][0]:
        return jsonify({'results': [], 'message': 'No matching videos found'})

    result_ids = search_results['ids'][0]
    distances = search_results['distances'][0]
    metadatas = search_results['metadatas'][0]
    documents = search_results.get('documents', [[]])[0]

    candidates: list[dict] = []
    candidate_video_objs: list[CandidateVideo] = []
    for i in range(len(result_ids)):
        meta = metadatas[i]
        dist = distances[i]
        sim_score = distance_to_similarity(dist)
        video_id = meta.get('id') or result_ids[i]
        doc_text = documents[i] if i < len(documents) else ""
        candidates.append({
            'id': video_id,
            'title': meta.get('title', 'N/A'),
            'channel': meta.get('channel', 'N/A'),
            'channel_id': meta.get('channel_id'),
            'url': meta.get('url', '#'),
            'score': float(sim_score),
            'thumbnail': f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg" if video_id else None,
            'channel_thumbnail': meta.get('channel_thumbnail'),
            'tags': meta.get('tags_str', ''),
            'document': doc_text,
            'metadata': meta,
            'original_rank': i + 1
        })
        candidate_video_objs.append(CandidateVideo(
            id=video_id,
            title=meta.get('title', ''),
            description=meta.get('description', ''),
            channel=meta.get('channel'),
            published_at=meta.get('publishedAt'),
            duration=meta.get('duration'),
            duration_seconds=meta.get('duration_seconds'),
            tags=(meta.get('tags_str', '') or '').split(', ') if meta.get('tags_str') else None,
            url=meta.get('url'),
            similarity_score=sim_score
        ))

    rerank_info = {
        'enabled': bool(ENABLE_LLM_RERANK),
        'applied': False
    }
    if ENABLE_LLM_RERANK and GEMINI_API_KEY:
        try:
            service = RerankService(api_key=GEMINI_API_KEY)
            rr = service.rerank(query, candidate_video_objs)
            rerank_info.update({
                'applied': rr.get('applied', False),
                'model': rr.get('model'),
                'latency_ms': rr.get('latency_ms'),
                'reason': rr.get('reason'),
                'candidate_count': len(candidates)
            })
            order = rr.get('ordered_ids', [])
            order_index = {vid: idx for idx, vid in enumerate(order)}
            # Sort candidates by reranked order if applied
            if rr.get('applied'):
                candidates.sort(key=lambda c: order_index.get(c['id'], 10**9))
                for idx, c in enumerate(candidates):
                    c['rerank_position'] = idx + 1
            else:
                for c in candidates:
                    c['rerank_position'] = c['original_rank']
            # Attach optional llm scores
            llm_scores = rr.get('llm_scores') or {}
            if llm_scores:
                for c in candidates:
                    if c['id'] in llm_scores:
                        c['llm_score'] = llm_scores[c['id']]
        except Exception as e:
            rerank_info['reason'] = f'error:{e.__class__.__name__}'
            for c in candidates:
                c['rerank_position'] = c['original_rank']
    else:
        # No rerank executed
        for c in candidates:
            c['rerank_position'] = c['original_rank']

    # Slice to display_n
    final_results = candidates[:display_n]
    return jsonify({'results': final_results, 'count': len(final_results), 'rerank': rerank_info})

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
        q = request.args.get('q', None)
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
        data = svc.get_channels(sort=sort, limit=limit, offset=offset, q=q)
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
                'channel_id': v.get('channel_id'),
                'url': v.get('url', f'https://www.youtube.com/watch?v={vid}' if vid else '#'),
                'score': 0.0,
                'thumbnail': f"https://img.youtube.com/vi/{vid}/hqdefault.jpg" if vid else None,
                'channel_thumbnail': v.get('channel_thumbnail'),
                'tags': v.get('tags_str', ''),
                'document': v.get('document', ''),
                'metadata': v
            })
        return jsonify({'results': shaped, 'count': len(shaped), 'channel': channel})
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve channel videos', 'detail': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
