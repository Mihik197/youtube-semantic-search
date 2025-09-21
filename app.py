# app.py
"""
Flask application - simplified and less defensive.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, render_template, request

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

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)


def cosine_distance_to_similarity(distance: Optional[float]) -> float:
    if distance is None:
        return 0.0
    if distance < 0 or distance > 2:
        return 0.0
    return 1.0 - distance


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
    return render_template(
        "index.html",
        db_count=db_count,
        collection_name=CHROMA_COLLECTION_NAME,
        collection_empty=collection_empty,
        default_results=DEFAULT_SEARCH_RESULTS,
        embedding_model=EMBEDDING_MODEL_NAME,
    )


@app.route("/search", methods=["POST"])
def search():
    if not request.json:
        return jsonify({"error": "No search parameters provided"}), 400

    query = (request.json.get("query") or "").strip()
    try:
        display_n = int(request.json.get("num_results", DEFAULT_SEARCH_RESULTS))
    except (TypeError, ValueError):
        display_n = DEFAULT_SEARCH_RESULTS
    display_n = max(display_n, 1)

    if not query:
        return jsonify({"error": "No search query provided"}), 400

    retrieve_n = max(display_n, RERANK_CANDIDATES if ENABLE_LLM_RERANK else display_n)
    search_results = search_videos(query, n_results=retrieve_n)

    if not search_results or not search_results.get("ids") or not search_results["ids"][0]:
        return jsonify({"results": [], "message": "No matching videos found"})

    result_ids = search_results["ids"][0]
    distances = search_results["distances"][0]
    metadatas = search_results["metadatas"][0]
    documents = search_results.get("documents", [[]])[0]

    candidates: List[Dict[str, Any]] = []
    candidate_video_objs: List[CandidateVideo] = []

    for i, rid in enumerate(result_ids):
        meta = metadatas[i]
        dist = distances[i]
        doc_text = documents[i] if i < len(documents) else ""
        vid = meta.get("id") or rid
        candidates.append(build_candidate_response(i, vid, meta, dist, doc_text))
        candidate_video_objs.append(build_candidate_video(i, vid, meta, dist, doc_text))

    rerank_info: Dict[str, Any] = {"enabled": bool(ENABLE_LLM_RERANK), "applied": False}

    if ENABLE_LLM_RERANK and GEMINI_API_KEY:
        service = RerankService(api_key=GEMINI_API_KEY)
        rr = service.rerank(query, candidate_video_objs)
        rerank_info.update({
            "applied": rr.get("applied", False),
            "model": rr.get("model"),
            "latency_ms": rr.get("latency_ms"),
            "reason": rr.get("reason"),
            "candidate_count": len(candidates),
        })
        order = rr.get("ordered_ids", [])
        order_index = {vid: idx for idx, vid in enumerate(order)}
        if rr.get("applied"):
            candidates.sort(key=lambda c: order_index.get(c["id"], 10 ** 9))
            for idx, c in enumerate(candidates):
                c["rerank_position"] = idx + 1
        else:
            for c in candidates:
                c["rerank_position"] = c["original_rank"]

        llm_scores = rr.get("llm_scores") or {}
        if llm_scores:
            for c in candidates:
                if c["id"] in llm_scores:
                    c["llm_score"] = llm_scores[c["id"]]
    else:
        for c in candidates:
            c["rerank_position"] = c["original_rank"]

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

    limit_param = request.args.get("limit")
    limit: Optional[int] = None
    if limit_param is not None:
        try:
            limit = int(limit_param)
        except (TypeError, ValueError):
            limit = None
    if limit is not None:
        limit = min(max(limit, 0), 500)

    try:
        offset = int(request.args.get("offset", "0"))
    except (TypeError, ValueError):
        offset = 0
    offset = max(offset, 0)

    svc = get_channel_aggregation_service()
    data = svc.get_channels(sort=sort, limit=limit, offset=offset, q=q)
    return jsonify(data)


@app.route("/channel_videos", methods=["GET"])
def channel_videos():
    channel = (request.args.get("channel") or "").strip()
    if not channel:
        return jsonify({"error": "channel parameter required"}), 400

    vectordb = VectorDBService(path=CHROMA_DB_PATH, collection_name=CHROMA_COLLECTION_NAME)
    videos = vectordb.get_videos_by_channel(channel)

    shaped: List[Dict[str, Any]] = []
    for v in videos:
        vid = v.get("id") or v.get("video_id")
        shaped.append({
            "id": vid,
            "title": v.get("title", "N/A"),
            "channel": v.get("channel", channel),
            "channel_id": v.get("channel_id"),
            "url": v.get("url", f"https://www.youtube.com/watch?v={vid}" if vid else "#"),
            "score": 0.0,
            "thumbnail": f"https://img.youtube.com/vi/{vid}/hqdefault.jpg" if vid else None,
            "channel_thumbnail": v.get("channel_thumbnail"),
            "tags": v.get("tags_str", ""),
            "document": v.get("document", ""),
            "metadata": v,
        })
    return jsonify({"results": shaped, "count": len(shaped), "channel": channel})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
