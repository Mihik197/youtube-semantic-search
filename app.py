# app.py
"""
Flask application - simplified and less defensive.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request, send_from_directory

from src.config import (
    DEFAULT_SEARCH_RESULTS,
    EMBEDDING_MODEL_NAME,
    CHROMA_COLLECTION_NAME,
    IS_CONFIG_VALID,
    ENABLE_LLM_RERANK,
    RERANK_CANDIDATES,
    GEMINI_API_KEY,
    CHROMA_DB_PATH,
)
from src.core.search import search_videos
from src.services.rerank_service import CandidateVideo, RerankService
from src.services.vectordb_service import VectorDBService
from src.services.channel_service import get_channel_aggregation_service
from src.services.topic_clustering_service import get_topic_clustering_service

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

REACT_BUILD_DIR = os.path.join(app.static_folder, "react")


def parse_int(value: Any, default: int, *, minimum: Optional[int] = None, maximum: Optional[int] = None) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def cosine_distance_to_similarity(distance: Optional[float]) -> float:
    if distance is None:
        return 0.0
    return max(0.0, min(1.0, 1.0 - distance))


# Initialize VectorDBService at startup — let any genuine errors surface early.
vectordb_service = VectorDBService(path=CHROMA_DB_PATH, collection_name=CHROMA_COLLECTION_NAME)
db_count = vectordb_service.count()
collection_empty = (db_count == 0)


def build_candidate_response(index: int, vid: str, meta: Dict[str, Any], distance: Optional[float], doc_text: str) -> Dict[str, Any]:
    sim = cosine_distance_to_similarity(distance)
    thumbnail = f"https://img.youtube.com/vi/{vid}/hqdefault.jpg" if vid else None
    return {
        "id": vid,
        "title": meta.get("title", "N/A"),
        "channel": meta.get("channel", "N/A"),
        "channel_id": meta.get("channel_id"),
        "url": meta.get("url", "#"),
        "score": float(sim),
        "thumbnail": thumbnail,
        "channel_thumbnail": meta.get("channel_thumbnail"),
        "tags": meta.get("tags_str", ""),
        "document": doc_text,
        "metadata": meta,
        "original_rank": index + 1,
    }


def build_candidate_video(index: int, vid: str, meta: Dict[str, Any], distance: Optional[float], doc_text: str) -> CandidateVideo:
    tags_list = (meta.get("tags_str") or "")
    tags = tags_list.split(", ") if tags_list else None
    return CandidateVideo(
        id=vid,
        title=meta.get("title", ""),
        description=meta.get("description", ""),
        channel=meta.get("channel"),
        published_at=meta.get("publishedAt"),
        duration=meta.get("duration"),
        duration_seconds=meta.get("duration_seconds"),
        tags=tags,
        url=meta.get("url"),
        similarity_score=cosine_distance_to_similarity(distance),
    )


@app.route("/")
def index():
    index_path = os.path.join(REACT_BUILD_DIR, "index.html")
    if not os.path.exists(index_path):
        return jsonify({"error": "Frontend build not found. Run 'npm run build' inside the frontend directory."}), 500
    return send_from_directory(REACT_BUILD_DIR, "index.html")


@app.route("/app-config", methods=["GET"])
def app_config():
    return jsonify(
        {
            "db_count": db_count,
            "collection_name": CHROMA_COLLECTION_NAME,
            "collection_empty": collection_empty,
            "default_results": DEFAULT_SEARCH_RESULTS,
            "embedding_model": EMBEDDING_MODEL_NAME,
        }
    )


@app.route("/search", methods=["POST"])
def search():
    payload = request.get_json(silent=True) or {}
    query = (payload.get("query") or "").strip()
    if not query:
        return jsonify({"error": "No search query provided"}), 400

    display_n = parse_int(payload.get("num_results"), DEFAULT_SEARCH_RESULTS, minimum=1)
    retrieve_n = max(display_n, RERANK_CANDIDATES if ENABLE_LLM_RERANK else display_n)
    search_results = search_videos(query, n_results=retrieve_n) or {}

    ids = (search_results.get("ids") or [[]])[0]
    if not ids:
        return jsonify({"results": [], "message": "No matching videos found"})

    distances = (search_results.get("distances") or [[]])[0]
    metadatas = (search_results.get("metadatas") or [[]])[0]
    documents = (search_results.get("documents") or [[]])[0]

    candidates: List[Dict[str, Any]] = []
    candidate_video_objs: List[CandidateVideo] = []
    for idx, result_id in enumerate(ids):
        meta = metadatas[idx]
        doc = documents[idx] if idx < len(documents) else ""
        distance = distances[idx] if idx < len(distances) else None
        video_id = meta.get("id") or result_id
        candidates.append(build_candidate_response(idx, video_id, meta, distance, doc))
        candidate_video_objs.append(build_candidate_video(idx, video_id, meta, distance, doc))

    rerank_info: Dict[str, Any] = {"enabled": bool(ENABLE_LLM_RERANK), "applied": False}

    if ENABLE_LLM_RERANK and GEMINI_API_KEY:
        service = RerankService(api_key=GEMINI_API_KEY)
        rr = service.rerank(query, candidate_video_objs)
        rerank_info.update(
            {
                "applied": rr.get("applied", False),
                "model": rr.get("model"),
                "latency_ms": rr.get("latency_ms"),
                "reason": rr.get("reason"),
                "candidate_count": len(candidates),
            }
        )
        order_index = {vid: pos for pos, vid in enumerate(rr.get("ordered_ids", []))}
        if rr.get("applied"):
            candidates.sort(key=lambda item: order_index.get(item["id"], 10**9))
        llm_scores = rr.get("llm_scores") or {}
        for pos, candidate in enumerate(candidates, start=1):
            candidate["rerank_position"] = pos if rr.get("applied") else candidate["original_rank"]
            if candidate["id"] in llm_scores:
                candidate["llm_score"] = llm_scores[candidate["id"]]
    else:
        for candidate in candidates:
            candidate["rerank_position"] = candidate["original_rank"]

    final_results = candidates[:display_n]
    return jsonify({"results": final_results, "count": len(final_results), "rerank": rerank_info})


@app.route("/healthcheck")
def healthcheck():
    return jsonify({
        "status": "ok",
        "db_count": db_count,
        "config_valid": IS_CONFIG_VALID,
        "model": EMBEDDING_MODEL_NAME,
        "collection": CHROMA_COLLECTION_NAME,
    })


@app.route("/channels", methods=["GET"])
def channels():
    sort = request.args.get("sort", "count_desc")
    if sort not in {"count_desc", "count_asc", "alpha", "alpha_desc"}:
        sort = "count_desc"

    q = request.args.get("q", None)

    limit_arg = request.args.get("limit")
    limit: Optional[int] = None if limit_arg is None else parse_int(limit_arg, 0, minimum=0, maximum=500)
    offset = parse_int(request.args.get("offset", 0), 0, minimum=0)

    svc = get_channel_aggregation_service()
    data = svc.get_channels(sort=sort, limit=limit, offset=offset, q=q)
    return jsonify(data)


@app.route("/channel_videos", methods=["GET"])
def channel_videos():
    channel = (request.args.get("channel") or "").strip()
    if not channel:
        return jsonify({"error": "channel parameter required"}), 400

    videos = vectordb_service.get_videos_by_channel(channel)

    shaped = []
    for meta in videos:
        vid = meta.get("id") or meta.get("video_id")
        shaped.append(
            {
                "id": vid,
                "title": meta.get("title", "N/A"),
                "channel": meta.get("channel", channel),
                "channel_id": meta.get("channel_id"),
                "url": meta.get("url") or (f"https://www.youtube.com/watch?v={vid}" if vid else "#"),
                "score": 0.0,
                "thumbnail": f"https://img.youtube.com/vi/{vid}/hqdefault.jpg" if vid else None,
                "channel_thumbnail": meta.get("channel_thumbnail"),
                "tags": meta.get("tags_str", ""),
                "document": meta.get("document", ""),
                "metadata": meta,
            }
        )
    return jsonify({"results": shaped, "count": len(shaped), "channel": channel})


@app.route("/topics", methods=["GET"])
def topics():
    svc = get_topic_clustering_service()
    sort = request.args.get('sort', 'size_desc')
    include_noise = request.args.get('include_noise', 'false').lower() == 'true'
    limit_arg = request.args.get('limit')
    limit_int = None if limit_arg is None else parse_int(limit_arg, 0, minimum=0)
    offset_int = parse_int(request.args.get('offset', 0), 0, minimum=0)
    data = svc.get_topics(sort=sort, include_noise=include_noise, limit=limit_int, offset=offset_int)
    return jsonify(data)


@app.route("/topics/<int:cluster_id>", methods=["GET"])
def topic_detail(cluster_id: int):
    svc = get_topic_clustering_service()
    data = svc.get_cluster(cluster_id)
    if 'error' in data:
        return jsonify(data), 404
    return jsonify(data)


@app.route("/topics/rebuild", methods=["POST"])
def topics_rebuild():
    svc = get_topic_clustering_service()
    force = request.args.get('force', 'false').lower() == 'true'
    try:
        snap = svc.rebuild(force=force)
        return jsonify({"status": "ok", "snapshot": {
            "generated_at": snap.get('generated_at'),
            "cluster_count": snap.get('cluster_count'),
            "noise_ratio": snap.get('noise_ratio'),
            "total_videos": snap.get('total_videos')
        }})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=5000)
