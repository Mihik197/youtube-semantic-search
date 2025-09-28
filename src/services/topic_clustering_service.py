from __future__ import annotations

import os
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.decomposition import PCA
from sklearn.preprocessing import normalize as l2_normalize

from src import config
from src.services.io_utils import read_json, write_json_atomic
from src.services.llm_service import LLMService, summarize_usage
from src.services.prompts import build_topic_label_prompt
from src.services.vectordb_service import VectorDBService

from pydantic import BaseModel, Field

try:  # pragma: no cover - optional dependency
    import hdbscan  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    hdbscan = None


@dataclass
class ClusterMetrics:
    count: int
    noise_ratio: float
    validity: Optional[float]
    duration: float
    selection: str


class ClusterLabelPayload(BaseModel):
    id: int = Field(...)
    label: str = Field(...)
    keywords: List[str] = Field(default_factory=list)


class ClusterBatchPayload(BaseModel):
    clusters: List[ClusterLabelPayload] = Field(default_factory=list)


def _debug(message: str) -> None:
    if getattr(config, "TOPIC_CLUSTERING_DEBUG", False):
        print(f"[topic-cluster] {message}")


class TopicClusteringService:
    """Builds and serves persisted topic-clustering snapshots."""

    def __init__(self, vectordb: VectorDBService, llm: Optional[LLMService] = None) -> None:
        self.vectordb = vectordb
        self.snapshot_path = getattr(
            config,
            "TOPIC_CLUSTERING_SNAPSHOT_PATH",
            os.path.join(config.ROOT_DIR, "data", "topic_clusters.json"),
        )
        self._lock = Lock()
        self._snapshot_cache: Optional[Dict[str, Any]] = None
        self._llm_service: Optional[LLMService] = llm
        self._llm_init_failed = False

    def _ensure_llm(self) -> Optional[LLMService]:
        if self._llm_service is not None or self._llm_init_failed:
            return self._llm_service
        if not getattr(config, "TOPIC_CLUSTERING_ENABLE_LLM_LABELS", False):
            self._llm_init_failed = True
            return None
        model = getattr(config, "TOPIC_CLUSTERING_LLM_MODEL", "gemini-2.5-flash")
        temperature = getattr(config, "TOPIC_CLUSTERING_LLM_TEMPERATURE", 0.2)
        api_key = getattr(config, "GEMINI_API_KEY", "")
        try:
            self._llm_service = LLMService(api_key, model, temperature=temperature)
        except Exception as exc:  # pragma: no cover - diagnostics only
            _debug(f"failed to initialise llm service: {exc}")
            self._llm_init_failed = True
            return None
        return self._llm_service

    # ------------------------------------------------------------------
    # Snapshot persistence helpers
    # ------------------------------------------------------------------
    def load_snapshot(self) -> Optional[Dict[str, Any]]:
        if self._snapshot_cache is not None:
            return self._snapshot_cache
        try:
            data = read_json(self.snapshot_path, None)
            if isinstance(data, dict):
                self._snapshot_cache = data
                return data
        except Exception as exc:  # pragma: no cover - diagnostics only
            _debug(f"failed to load snapshot: {exc}")
        return None

    def save_snapshot(self, snapshot: Dict[str, Any]) -> None:
        write_json_atomic(self.snapshot_path, snapshot)
        self._snapshot_cache = snapshot

    def needs_rebuild(self) -> bool:
        snapshot = self.load_snapshot()
        if not snapshot:
            return True
        try:
            stored_total = int(snapshot.get("total_videos", -1))
        except (TypeError, ValueError):
            stored_total = -1
        return stored_total != self.vectordb.count()

    # ------------------------------------------------------------------
    # Embedding extraction and preprocessing
    # ------------------------------------------------------------------
    def _load_embeddings(self) -> Tuple[List[str], np.ndarray, List[str]]:
        total = self.vectordb.count()
        if total == 0:
            return [], np.zeros((0, 0), dtype=np.float32), []

        ids: List[str] = []
        vectors: List[List[float]] = []
        texts: List[str] = []
        batch_size = getattr(config, "CHROMA_BATCH_SIZE", 100)
        collection = self.vectordb.collection

        for offset in range(0, total, batch_size):
            limit = min(batch_size, total - offset)
            batch = collection.get(
                include=["embeddings", "metadatas", "documents"],
                offset=offset,
                limit=limit,
            )
            batch_ids = list(batch.get("ids") or [])
            embeddings = list(batch.get("embeddings") or [])
            metadatas = list(batch.get("metadatas") or [])

            for idx, vid in enumerate(batch_ids):
                ids.append(vid)
                vector = embeddings[idx] if idx < len(embeddings) else []
                vectors.append(vector or [0.0])
                meta = metadatas[idx] if idx < len(metadatas) and isinstance(metadatas[idx], dict) else {}
                title = (meta.get("title") or "").strip()
                channel = (meta.get("channel") or "").strip()
                description = (meta.get("description") or "")[:200].strip()
                snippet = " \n ".join(part for part in (title, channel, description) if part)
                texts.append(snippet)

        matrix = np.asarray(vectors, dtype=np.float32)
        _debug(f"loaded embeddings: {matrix.shape[0]} rows, dim={matrix.shape[1] if matrix.size else 0}")
        return ids, matrix, texts

    def _preprocess(self, matrix: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        if matrix.size == 0:
            return matrix, {"pca_components": 0}
        normalized = l2_normalize(matrix)
        if getattr(config, "TOPIC_CLUSTERING_DIM_REDUCTION", "pca") != "pca":
            return normalized.astype(np.float32, copy=False), {"pca_components": normalized.shape[1]}

        n_samples, dim = normalized.shape
        if n_samples <= 3000 and dim <= 384:
            return normalized.astype(np.float32, copy=False), {"pca_components": dim}

        max_components = getattr(config, "TOPIC_CLUSTERING_PCA_MAX_COMPONENTS", 50)
        variance = getattr(config, "TOPIC_CLUSTERING_PCA_VARIANCE_THRESHOLD", 0.90)
        target = min(max_components, dim, max(10, int(0.1 * n_samples)))
        pca = PCA(n_components=target, svd_solver="auto", random_state=42)
        reduced = pca.fit_transform(normalized)
        cumulative = np.cumsum(pca.explained_variance_ratio_)
        keep = int(np.searchsorted(cumulative, variance) + 1)
        reduced = reduced[:, :keep]
        _debug(f"pca components={keep}")
        return reduced.astype(np.float32, copy=False), {"pca_components": keep}

    def _derive_params(self, count: int) -> Dict[str, int]:
        floor = getattr(config, "TOPIC_CLUSTERING_MIN_CLUSTER_SIZE_FLOOR", 5)
        cap = getattr(config, "TOPIC_CLUSTERING_MIN_CLUSTER_SIZE_MAX", 150)
        if count <= 0:
            return {"min_cluster_size": floor, "min_samples": floor}
        if count <= 100:
            size = int(0.08 * count)
        elif count <= 500:
            size = int(0.04 * count)
        elif count <= 1500:
            size = int(0.02 * count)
        elif count <= 3000:
            size = int(0.008 * count)
        else:
            size = int(0.006 * count)
        size = max(floor, min(cap, size))
        return {"min_cluster_size": size, "min_samples": max(3, int(size * 0.35))}

    # ------------------------------------------------------------------
    # Clustering + evaluation
    # ------------------------------------------------------------------
    def _run_hdbscan(self, matrix: np.ndarray, params: Dict[str, int], selection: str) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        if hdbscan is None:
            raise RuntimeError("hdbscan package not installed")
        if matrix.size == 0:
            return np.array([], dtype=int), None
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=params["min_cluster_size"],
            min_samples=params["min_samples"],
            metric="euclidean",
            cluster_selection_method=selection,
            prediction_data=True,
        )
        labels = clusterer.fit_predict(matrix)
        probs = getattr(clusterer, "probabilities_", None)
        return labels, probs

    def _score(
        self,
        labels: np.ndarray,
        probs: Optional[np.ndarray],
        matrix: np.ndarray,
        params: Dict[str, int],
        selection: str,
        started: float,
    ) -> ClusterMetrics:
        if labels.size == 0:
            return ClusterMetrics(0, 0.0, None, 0.0, selection)
        noise_mask = labels == -1
        cluster_ids = [cid for cid in np.unique(labels) if cid != -1]
        noise_ratio = float(np.sum(noise_mask)) / labels.size if labels.size else 0.0
        validity = None
        if hdbscan is not None and len(cluster_ids) > 1:
            try:  # pragma: no cover - heavy call
                from hdbscan.validity import validity_index

                keep = np.where(~noise_mask)[0]
                if keep.size > 2:
                    core = matrix[keep]
                    current = labels[keep]
                    if len(np.unique(current)) > 1:
                        validity = float(validity_index(core, current))
            except Exception:  # pragma: no cover - diagnostics only
                validity = None
        elapsed = time.time() - started
        _debug(
            "clusters={c} noise={n:.3f} mcs={mcs} ms={ms} sel={sel}".format(
                c=len(cluster_ids),
                n=noise_ratio,
                mcs=params["min_cluster_size"],
                ms=params["min_samples"],
                sel=selection,
            )
        )
        return ClusterMetrics(len(cluster_ids), noise_ratio, validity, elapsed, selection)

    # ------------------------------------------------------------------
    # Cluster labelling + snapshot construction
    # ------------------------------------------------------------------
    def _cluster_members(
        self,
        labels: np.ndarray,
        probs: Optional[np.ndarray],
        ids: List[str],
        texts: List[str],
    ) -> Dict[int, Dict[str, Any]]:
        clusters: Dict[int, Dict[str, Any]] = {}
        for idx, label in enumerate(labels):
            label = int(label)
            if label == -1:
                continue
            bucket = clusters.setdefault(label, {"members": [], "probs": [], "texts": []})
            bucket["members"].append(ids[idx])
            bucket["texts"].append(texts[idx])
            if probs is not None:
                bucket["probs"].append(float(probs[idx]))

        for label, data in clusters.items():
            if data["members"]:
                if data["probs"]:
                    best = int(np.argmax(data["probs"]))
                    data["mean_probability"] = float(np.mean(data["probs"]))
                else:
                    best = 0
                    data["mean_probability"] = None
                data["exemplar"] = data["members"][best]
        return clusters

    def _label_clusters(self, clusters: Dict[int, Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
        if not clusters:
            return {}
        llm = self._ensure_llm()
        if not llm:
            for cid, data in clusters.items():
                data["label"] = f"cluster_{cid}"
                data["top_keywords"] = []
                data.pop("texts", None)
            return clusters

        max_keywords = getattr(config, "TOPIC_CLUSTERING_LABEL_MAX_KEYWORDS", 4)
        chunk_size = getattr(config, "TOPIC_CLUSTERING_LLM_CHUNK_SIZE", 25)
        items = list(clusters.items())

        for start in range(0, len(items), chunk_size):
            chunk = items[start : start + chunk_size]
            cluster_payload = [
                (cid, list(data.get("texts", []) or []))
                for cid, data in chunk
            ]
            prompt = build_topic_label_prompt(cluster_payload, max_keywords=max_keywords)
            prompt_tokens = llm.count_tokens(prompt)
            try:  # pragma: no cover - network call
                response, parsed = llm.generate_json(prompt, ClusterBatchPayload)
            except Exception as exc:  # pragma: no cover - diagnostics only
                _debug(f"labelling chunk failed: {exc}")
                response, parsed = None, None

            if response is not None and getattr(config, "TOPIC_CLUSTERING_DEBUG", False):
                usage = summarize_usage(response, prompt_tokens)
                usage_str = "/".join(str(val) if val is not None else "-" for val in usage)
                _debug(f"label chunk size={len(chunk)} tokens in/out/total={usage_str}")

            mapping = {entry.id: entry for entry in getattr(parsed, "clusters", [])} if parsed else {}
            for cid, data in chunk:
                entry = mapping.get(cid)
                if not entry:
                    data["label"] = f"cluster_{cid}"
                    data["top_keywords"] = []
                else:
                    label = entry.label.strip()
                    data["label"] = label[:60] if label else f"cluster_{cid}"
                    keywords: List[str] = []
                    seen: set[str] = set()
                    for keyword in entry.keywords:
                        keyword = keyword.strip().lower()
                        if keyword and keyword not in seen:
                            keywords.append(keyword)
                            seen.add(keyword)
                        if len(keywords) >= max_keywords:
                            break
                    data["top_keywords"] = keywords
                data.pop("texts", None)
        return clusters

    def _build_snapshot(
        self,
        ids: List[str],
        labels: np.ndarray,
        probs: Optional[np.ndarray],
        metrics: ClusterMetrics,
        params: Dict[str, int],
        pca_info: Dict[str, Any],
        clusters: Dict[int, Dict[str, Any]],
    ) -> Dict[str, Any]:
        assignments = {vid: int(labels[idx]) if idx < len(labels) else -1 for idx, vid in enumerate(ids)}
        total = len(ids)
        cluster_rows: List[Dict[str, Any]] = []
        for cid, data in clusters.items():
            members = data.get("members", [])
            size = len(members)
            share = round((size / total * 100.0) if total else 0.0, 2)
            cluster_rows.append(
                {
                    "id": cid,
                    "label": data.get("label", f"cluster_{cid}"),
                    "size": size,
                    "percent": share,
                    "top_keywords": data.get("top_keywords", []),
                    "exemplar_video_id": data.get("exemplar"),
                    "mean_probability": data.get("mean_probability"),
                    "sample_video_ids": members[:3],
                }
            )

        snapshot = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "embedding_model": getattr(config, "EMBEDDING_MODEL_NAME", "unknown"),
            "algo": "hdbscan",
            "params": {
                "min_cluster_size": params.get("min_cluster_size"),
                "min_samples": params.get("min_samples"),
                "pca_components": pca_info.get("pca_components"),
            },
            "total_videos": total,
            "cluster_count": metrics.count,
            "noise_ratio": round(metrics.noise_ratio, 4),
            "clusters": cluster_rows,
            "assignments": assignments,
            "meta": {
                "build_seconds": round(metrics.duration, 3),
                "validity_score": metrics.validity,
                "selection_method": metrics.selection,
            },
        }
        return snapshot

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def rebuild(self, force: bool = False) -> Dict[str, Any]:
        with self._lock:
            if not force:
                snapshot = self.load_snapshot()
                if snapshot and not self.needs_rebuild():
                    return snapshot

            ids, matrix, texts = self._load_embeddings()
            start = time.time()
            params = self._derive_params(len(ids))
            processed, pca_info = self._preprocess(matrix)

            target_clusters = max(15, min(80, len(ids) // 120 or 0))
            floor = getattr(config, "TOPIC_CLUSTERING_MIN_CLUSTER_SIZE_FLOOR", 5)
            selection = "leaf"
            best_state: Optional[Tuple[ClusterMetrics, np.ndarray, Optional[np.ndarray], Dict[str, int], str]] = None

            for _ in range(6):
                labels, probs = self._run_hdbscan(processed, params, selection)
                metrics = self._score(labels, probs, processed, params, selection, start)
                if not best_state or metrics.count > best_state[0].count or (
                    metrics.count == best_state[0].count and metrics.noise_ratio < best_state[0].noise_ratio
                ):
                    best_state = (metrics, labels.copy(), None if probs is None else probs.copy(), params.copy(), selection)
                if metrics.count >= target_clusters and metrics.noise_ratio <= 0.65:
                    break
                if params["min_cluster_size"] <= floor:
                    if selection == "leaf":
                        selection = "eom"
                        continue
                    break
                params["min_cluster_size"] = max(floor, int(params["min_cluster_size"] * 0.75))
                params["min_samples"] = max(3, int(params["min_cluster_size"] * 0.35))

            if not best_state:
                empty_metrics = ClusterMetrics(0, 0.0, None, time.time() - start, selection)
                snapshot = self._build_snapshot(ids, np.array([]), None, empty_metrics, params, pca_info, {})
                self.save_snapshot(snapshot)
                return snapshot

            metrics, labels, probs, params, selection = best_state
            metrics.selection = selection
            cluster_map = self._cluster_members(labels, probs, ids, texts)
            labeled_clusters = self._label_clusters(cluster_map)
            snapshot = self._build_snapshot(ids, labels, probs, metrics, params, pca_info, labeled_clusters)
            self.save_snapshot(snapshot)
            return snapshot

    def get_topics(
        self,
        sort: str = "size_desc",
        include_noise: bool = False,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> Dict[str, Any]:
        snapshot = self.load_snapshot()
        if not snapshot:
            return {"clusters": [], "count": 0, "total_videos": 0}
        clusters = list(snapshot.get("clusters", []))
        if not include_noise:
            clusters = [cluster for cluster in clusters if cluster.get("id", -1) != -1]

        if sort == "size_asc":
            clusters.sort(key=lambda entry: entry.get("size", 0))
        elif sort == "alpha":
            clusters.sort(key=lambda entry: (entry.get("label") or "").lower())
        elif sort == "alpha_desc":
            clusters.sort(key=lambda entry: (entry.get("label") or "").lower(), reverse=True)
        else:
            clusters.sort(key=lambda entry: entry.get("size", 0), reverse=True)

        total = len(clusters)
        clusters = clusters[offset:]
        if limit is not None:
            clusters = clusters[:limit]
        return {
            "clusters": clusters,
            "count": len(clusters),
            "total": total,
            "total_videos": snapshot.get("total_videos"),
            "generated_at": snapshot.get("generated_at"),
            "noise_ratio": snapshot.get("noise_ratio"),
            "cluster_count": snapshot.get("cluster_count"),
        }

    def get_cluster(self, cluster_id: int) -> Dict[str, Any]:
        snapshot = self.load_snapshot()
        if not snapshot:
            return {"error": "no snapshot"}
        assignments = snapshot.get("assignments", {})
        member_ids = [vid for vid, label in assignments.items() if label == cluster_id]
        items = self.vectordb.get_items(member_ids)
        videos: List[Dict[str, Any]] = []
        for vid in member_ids:
            item = items.get(vid)
            if not item:
                continue
            meta = item.get("metadata", {}) or {}
            videos.append(
                {
                    "id": vid,
                    "title": meta.get("title"),
                    "channel": meta.get("channel"),
                    "url": meta.get("url"),
                    "published_at": meta.get("publishedAt"),
                    "duration_seconds": meta.get("duration_seconds"),
                    "thumbnail": f"https://img.youtube.com/vi/{vid}/hqdefault.jpg",
                }
            )
        cluster_entry = next((c for c in snapshot.get("clusters", []) if int(c.get("id", -1)) == cluster_id), None)
        return {"cluster": cluster_entry, "videos": videos, "count": len(videos), "cluster_id": cluster_id}


_topic_service_singleton: Optional[TopicClusteringService] = None


def get_topic_clustering_service() -> TopicClusteringService:
    global _topic_service_singleton
    if _topic_service_singleton is None:
        vectordb = VectorDBService(path=config.CHROMA_DB_PATH, collection_name=config.CHROMA_COLLECTION_NAME)
        service = TopicClusteringService(vectordb)
        _topic_service_singleton = service
        if getattr(config, "TOPIC_CLUSTERING_REBUILD_ON_START_IF_MISSING", True):
            try:  # pragma: no cover - startup path
                if service.needs_rebuild():
                    service.rebuild(force=True)
            except Exception as exc:
                print(f"Warning: initial topic clustering rebuild failed: {exc}")
    return _topic_service_singleton
