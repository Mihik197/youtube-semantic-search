import json
import os
import time
import math
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv
load_dotenv()
import numpy as np
from sklearn.preprocessing import normalize as l2_normalize
from sklearn.decomposition import PCA
import re  # retained only for light text cleaning in LLM prompt truncation

try:
    import hdbscan  # type: ignore
except ImportError as e:  # pragma: no cover - dependency guard
    hdbscan = None  # Allow import error to raise later when used

from src import config
from src.services.vectordb_service import VectorDBService


@dataclass
class ClusterMetrics:
    cluster_count: int
    noise_ratio: float
    validity_score: Optional[float]
    build_seconds: float
    adaptive_retry: bool = False
    warnings: List[str] = field(default_factory=list)


class TopicClusteringService:
    """Service managing topic clustering via HDBSCAN and snapshot persistence."""

    def __init__(self, vectordb: VectorDBService):
        self.vectordb = vectordb
        self.snapshot_path = getattr(config, 'TOPIC_CLUSTERING_SNAPSHOT_PATH', os.path.join(config.ROOT_DIR, 'data', 'topic_clusters.json'))
        self._lock = threading.Lock()
        self._snapshot_cache: Optional[Dict[str, Any]] = None

    # ---------------- Snapshot Handling -----------------
    def load_snapshot(self) -> Optional[Dict[str, Any]]:
        if self._snapshot_cache is not None:
            return self._snapshot_cache
        try:
            if os.path.exists(self.snapshot_path):
                with open(self.snapshot_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._snapshot_cache = data
                    return data
        except Exception as e:
            print(f"Warning: failed to load topic clustering snapshot: {e}")
        return None

    def save_snapshot_atomic(self, snapshot: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.snapshot_path), exist_ok=True)
        tmp_path = self.snapshot_path + '.tmp'
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.snapshot_path)
            self._snapshot_cache = snapshot
        finally:
            if os.path.exists(tmp_path):  # cleanup leftover on error
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def needs_rebuild(self) -> bool:
        snap = self.load_snapshot()
        if not snap:
            return True
        try:
            total_videos = self.vectordb.count()
            # Ensure both values are plain Python integers to avoid numpy array comparison issues
            snap_total = snap.get('total_videos', -1)
            if isinstance(snap_total, (list, tuple)) and len(snap_total) > 0:
                snap_total = snap_total[0]  # extract first element if it's accidentally a sequence
            snap_total = int(snap_total)
            total_videos = int(total_videos)
            if snap_total != total_videos:
                return True
        except Exception:
            return True
        return False

    # ---------------- Embedding Loading -----------------
    def load_embeddings(self) -> Tuple[List[str], np.ndarray, List[str]]:
        total = self.vectordb.count()
        if total == 0:
            return [], np.zeros((0, 0), dtype=np.float32), []
        # Chroma does not expose streaming embeddings easily via existing wrapper; pull in batches
        batch_size = getattr(config, 'CHROMA_BATCH_SIZE', 100)
        ids: List[str] = []
        embeddings: List[List[float]] = []
        texts: List[str] = []
        offset = 0
        # Use raw client for efficiency
        collection = self.vectordb.collection
        while offset < total:
            limit = min(batch_size, total - offset)
            try:
                batch = collection.get(include=['embeddings', 'metadatas', 'documents'], offset=offset, limit=limit)
            except Exception as e:
                print(f"Error retrieving embeddings batch at offset {offset}: {e}")
                break
            got_ids = batch.get('ids', [])
            # Some vector DB clients may return numpy arrays for ids; ensure list
            if isinstance(got_ids, np.ndarray):
                got_ids = got_ids.tolist()
            elif got_ids is None:
                got_ids = []
                
            embs = batch.get('embeddings', [])
            if isinstance(embs, np.ndarray):
                embs = embs.tolist()
            elif embs is None:
                embs = []
                
            metas = batch.get('metadatas', [])
            if isinstance(metas, np.ndarray):
                metas = metas.tolist()
            elif metas is None:
                metas = []
                
            docs = batch.get('documents', [])
            if isinstance(docs, np.ndarray):
                docs = docs.tolist()
            elif docs is None:
                docs = []
            for i, vid in enumerate(got_ids):
                ids.append(vid)
                if i < len(embs):
                    embeddings.append(embs[i])
                else:
                    embeddings.append([0.0])
                # Build text for labeling: title + channel + truncated description
                meta = metas[i] if i < len(metas) and isinstance(metas[i], dict) else {}
                title = (meta.get('title') or '').strip()
                channel = (meta.get('channel') or '').strip()
                description = (meta.get('description') or '')[:200].strip()
                piece_parts = []
                if title:
                    piece_parts.append(title)
                if channel:
                    piece_parts.append(channel)
                if description:
                    piece_parts.append(description)
                texts.append(' \n '.join(piece_parts))
            offset += len(got_ids)
            if len(got_ids) == 0:
                break
        X = np.asarray(embeddings, dtype=np.float32)
        return ids, X, texts

    # ---------------- Preprocessing & Params -----------------
    def preprocess_embeddings(self, X: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        if X.size == 0:
            return X, {"pca_components": 0}
        Xn = l2_normalize(X)
        pca_choice = getattr(config, 'TOPIC_CLUSTERING_DIM_REDUCTION', 'pca')
        info: Dict[str, Any] = {"pca_components": None}
        if pca_choice == 'pca' and Xn.shape[0] > 0:
            n = Xn.shape[0]
            dim = Xn.shape[1]
            if n > 3000 or dim > 384:
                max_comp = getattr(config, 'TOPIC_CLUSTERING_PCA_MAX_COMPONENTS', 50)
                target = min(max_comp, dim, max(10, int(0.1 * n)))
                var_threshold = getattr(config, 'TOPIC_CLUSTERING_PCA_VARIANCE_THRESHOLD', 0.90)
                pca = PCA(n_components=target, svd_solver='auto', random_state=42)
                Xr = pca.fit_transform(Xn)
                # Determine minimal components reaching threshold
                cumvar = np.cumsum(pca.explained_variance_ratio_)
                k = int(np.searchsorted(cumvar, var_threshold) + 1)
                if k < Xr.shape[1]:
                    Xr = Xr[:, :k]
                info['pca_components'] = Xr.shape[1]
                return Xr.astype(np.float32, copy=False), info
        info['pca_components'] = Xn.shape[1]
        return Xn.astype(np.float32, copy=False), info

    def derive_params(self, n: int) -> Dict[str, int]:
        floor_ = getattr(config, 'TOPIC_CLUSTERING_MIN_CLUSTER_SIZE_FLOOR', 5)
        cap = getattr(config, 'TOPIC_CLUSTERING_MIN_CLUSTER_SIZE_MAX', 150)
        if n <= 0:
            return {"min_cluster_size": floor_, "min_samples": floor_}
        
        # Even more aggressive parameters for better clustering discovery
        if n <= 100:
            mcs = max(floor_, int(0.08 * n))  # 8% of videos
        elif n <= 500:
            mcs = max(floor_, int(0.04 * n))  # 4% of videos
        elif n <= 1500:
            mcs = max(floor_, int(0.02 * n))  # 2% of videos
        elif n <= 3000:
            mcs = max(floor_, int(0.008 * n))  # 0.8% of videos  
        else:
            mcs = max(floor_, int(0.006 * n))  # 0.6% of videos for very large collections
            
        mcs = max(floor_, min(cap, mcs))
        ms = max(2, int(0.3 * mcs))  # Even more relaxed - 30% of cluster size
        return {"min_cluster_size": mcs, "min_samples": ms}

    # ---------------- Core Clustering -----------------
    def run_hdbscan(self, X: np.ndarray, params: Dict[str, int], selection_method: str = 'leaf') -> Tuple[np.ndarray, Optional[np.ndarray], Any]:
        if hdbscan is None:
            raise RuntimeError("hdbscan package not installed")
        if X.size == 0:
            return np.array([], dtype=int), None, None
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=params['min_cluster_size'],
            min_samples=params['min_samples'],
            metric='euclidean',
            cluster_selection_method=selection_method,
            prediction_data=True
        )
        labels = clusterer.fit_predict(X)
        probs = getattr(clusterer, 'probabilities_', None)
        return labels, probs, clusterer

    def evaluate(self, labels: np.ndarray, probs: Optional[np.ndarray], X: np.ndarray, params: Dict[str, int], start_time: float) -> ClusterMetrics:
        if labels.size == 0:
            return ClusterMetrics(cluster_count=0, noise_ratio=0.0, validity_score=None, build_seconds=0.0)
        noise_mask = labels == -1
        total = labels.size
        noise_ratio = float(np.sum(noise_mask)) / float(total) if total else 0.0
        unique = [l for l in np.unique(labels) if l != -1]
        cluster_count = len(unique)
        validity_score = None
        # Try DBCV using hdbscan validity utils
        if hdbscan is not None and cluster_count > 1:
            try:
                from hdbscan.validity import validity_index
                # Filter noise for validity - ensure proper boolean array handling
                non_noise_indices = np.where(~noise_mask)[0]
                if len(non_noise_indices) > 2:
                    core_X = X[non_noise_indices]
                    core_labels = labels[non_noise_indices]
                    if len(np.unique(core_labels)) > 1:
                        validity_score = float(validity_index(core_X, core_labels))
            except Exception:
                validity_score = None
        build_seconds = time.time() - start_time
        return ClusterMetrics(cluster_count=cluster_count, noise_ratio=noise_ratio, validity_score=validity_score, build_seconds=build_seconds)

    # ---------------- Labeling -----------------
    def _build_cluster_members(self, labels: np.ndarray, probs: Optional[np.ndarray], ids: List[str], texts: List[str]) -> Dict[int, Dict[str, Any]]:
        clusters: Dict[int, Dict[str, Any]] = {}
        for idx, label in enumerate(labels):
            # Convert numpy scalar to Python int to avoid ambiguous truth value
            label_val = int(label)
            if label_val == -1:  # skip noise for cluster stats (kept in assignments separately)
                continue
            entry = clusters.setdefault(label_val, {"members": [], "probs": [], "texts": []})
            entry["members"].append(ids[idx])
            entry["texts"].append(texts[idx])
            if probs is not None:
                entry["probs"].append(float(probs[idx]))
        # exemplar selection based on highest probability
        for cid, data in clusters.items():
            if data["members"]:
                if data["probs"]:
                    best_idx = int(np.argmax(data["probs"]))
                else:
                    best_idx = 0
                data["exemplar"] = data["members"][best_idx]
                data["mean_probability"] = float(np.mean(data["probs"])) if data["probs"] else None
            else:
                data["exemplar"] = None
                data["mean_probability"] = None
        return clusters

    def label_clusters(self, clusters: Dict[int, Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
        if not clusters:
            return {}
        max_kw = getattr(config, 'TOPIC_CLUSTERING_LABEL_MAX_KEYWORDS', 4)
        api_key = getattr(config, 'GEMINI_API_KEY', None)
        if not api_key:
            # Placeholder labels (LLM-only mode requested, no heuristic fallback)
            for cid, data in clusters.items():
                data['label'] = f"cluster_{cid}"
                data['top_keywords'] = []
            return clusters
        return self._label_clusters_with_llm_batch(clusters, max_kw)

    def _label_clusters_with_llm_batch(self, clusters: Dict[int, Dict[str, Any]], max_kw: int) -> Dict[int, Dict[str, Any]]:
        """Batch LLM labeling. Single or chunked calls; no heuristic fallback (per user request)."""
        try:
            from google import genai
            from pydantic import BaseModel, Field
            from typing import List

            class ClusterLabel(BaseModel):
                id: int = Field(..., description="Cluster id as provided")
                label: str = Field(..., description="<=4 word concise human readable topic label")
                keywords: List[str] = Field(..., description=f"Up to {max_kw} representative lowercase keywords")

            class ClusterLabelSet(BaseModel):
                clusters: List[ClusterLabel]

            client = genai.Client(api_key=config.GEMINI_API_KEY)
            model_name = getattr(config, 'TOPIC_CLUSTERING_LLM_MODEL', 'gemini-2.5-flash')

            # Split into manageable batches to control token size
            cluster_items = list(clusters.items())
            batch_size = 25
            for start in range(0, len(cluster_items), batch_size):
                batch_slice = cluster_items[start:start+batch_size]
                # Build prompt segment
                parts = [
                    "You are labeling clusters of YouTube videos. Return strict JSON only.",
                    f"Each cluster object must have: id (int), label (<=4 words), keywords (<= {max_kw}).",
                    "Guidelines: labels must be specific, no generic words like 'videos', avoid URLs, no leading/trailing quotes.",
                    "Prefer concrete topic concepts (e.g. 'python concurrency', 'retro gaming history').",
                    "Input clusters:" 
                ]
                for cid, data in batch_slice:
                    texts = data.get('texts', [])[:15]
                    sample_lines = []
                    for t in texts:
                        clean = re.sub(r'\s+', ' ', t).strip()
                        if len(clean) > 140:
                            clean = clean[:140] + '…'
                        if clean:
                            sample_lines.append(f"- {clean}")
                    if not sample_lines:
                        sample_lines.append("- (no content)")
                    parts.append(f"Cluster {cid}:\n" + "\n".join(sample_lines))
                parts.append("Respond with JSON: {\"clusters\": [ {\"id\":..., \"label\":..., \"keywords\":[...]}, ... ] }")
                prompt = "\n\n".join(parts)

                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": ClusterLabelSet,
                    }
                )

                parsed = getattr(response, 'parsed', None)
                if not parsed and getattr(response, 'text', None):
                    # Attempt manual JSON parse (strip fences if any)
                    import json as _json
                    txt = response.text.strip()
                    if txt.startswith("```"):
                        # remove markdown fences
                        txt = re.sub(r'^```[a-zA-Z]*', '', txt)
                        txt = txt.rstrip('`').strip()
                    try:
                        raw = _json.loads(txt)
                        class _Tmp(BaseModel):
                            clusters: List[ClusterLabel]
                        parsed = _Tmp(**raw)
                    except Exception:
                        parsed = None

                if not parsed:
                    if getattr(config, 'TOPIC_CLUSTERING_DEBUG', False):
                        print("[topic-cluster] LLM batch parse failed; using placeholders for this batch")
                    for cid, data in batch_slice:
                        data['label'] = f"cluster_{cid}"
                        data['top_keywords'] = []
                    continue

                # Map results
                label_map = {c.id: c for c in parsed.clusters}
                for cid, data in batch_slice:
                    cobj = label_map.get(cid)
                    if cobj:
                        data['label'] = (cobj.label or f"cluster_{cid}").strip()[:60]
                        # Normalize keywords
                        kws = [k.strip().lower() for k in (cobj.keywords or []) if k.strip()]
                        # Deduplicate preserving order
                        seen = set()
                        final_kws = []
                        for k in kws:
                            if k not in seen:
                                seen.add(k)
                                final_kws.append(k)
                            if len(final_kws) >= max_kw:
                                break
                        data['top_keywords'] = final_kws
                    else:
                        data['label'] = f"cluster_{cid}"
                        data['top_keywords'] = []
        except Exception as e:
            if getattr(config, 'TOPIC_CLUSTERING_DEBUG', False):
                print(f"[topic-cluster] LLM labeling failed globally: {e}")
            for cid, data in clusters.items():
                data['label'] = f"cluster_{cid}"
                data['top_keywords'] = []
        return clusters
                    

    # ---------------- Snapshot Build -----------------
    def build_snapshot(self, ids: List[str], labels: np.ndarray, probs: Optional[np.ndarray], metrics: ClusterMetrics, params: Dict[str, int], pca_info: Dict[str, Any], labeled_clusters: Optional[Dict[int, Dict[str, Any]]] = None) -> Dict[str, Any]:
        assignments: Dict[str, int] = {}
        for i, vid in enumerate(ids):
            # Defensive assignment to avoid numpy array truthiness issues
            try:
                if i < len(labels):
                    assignments[vid] = int(labels[i])
                else:
                    assignments[vid] = -1
            except (IndexError, ValueError):
                assignments[vid] = -1
        
        # Use provided labeled_clusters or build them
        if labeled_clusters is not None:
            clusters_raw = labeled_clusters
        else:
            clusters_raw = self._build_cluster_members(labels, probs, ids, [""] * len(ids))  # texts not needed here; labeling done earlier
        total_videos = len(ids)
        cluster_entries: List[Dict[str, Any]] = []
        # Rebuild with labels & keywords by referencing cluster labels produced earlier (we label after building members with texts)
        # The labeling adds 'label' and 'top_keywords'. We'll integrate those after labeling stage externally.
        for cid, data in clusters_raw.items():
            members = data['members']
            size = len(members)
            percent = (size / total_videos * 100.0) if total_videos else 0.0
            cluster_entries.append({
                'id': cid,
                'label': data.get('label', f'cluster_{cid}'),
                'size': size,
                'percent': round(percent, 2),
                'top_keywords': data.get('top_keywords', []),
                'exemplar_video_id': data.get('exemplar'),
                'mean_probability': data.get('mean_probability'),
                'sample_video_ids': members[:3]
            })
        snapshot = {
            'generated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'embedding_model': getattr(config, 'EMBEDDING_MODEL_NAME', 'unknown'),
            'algo': 'hdbscan',
            'params': {
                'min_cluster_size': params.get('min_cluster_size'),
                'min_samples': params.get('min_samples'),
                'pca_components': pca_info.get('pca_components')
            },
            'total_videos': total_videos,
            'cluster_count': metrics.cluster_count,
            'noise_ratio': round(metrics.noise_ratio, 4),
            'clusters': cluster_entries,
            'assignments': assignments,
            'meta': {
                'build_seconds': round(metrics.build_seconds, 3),
                'validity_score': metrics.validity_score,
                'adaptive_retry': metrics.adaptive_retry,
                'warnings': metrics.warnings,
            }
        }
        return snapshot

    # ---------------- Public Orchestrator -----------------
    def rebuild(self, force: bool = False) -> Dict[str, Any]:
        with self._lock:
            try:
                if not force and not self.needs_rebuild():
                    snap = self.load_snapshot()
                    if snap:
                        return snap
                ids, X, texts = self.load_embeddings()
                if getattr(config, 'TOPIC_CLUSTERING_DEBUG', False):
                    try:
                        print(f"[topic-cluster] loaded embeddings: n={len(ids)} shape={X.shape} texts={len(texts)}")
                    except Exception:
                        pass
                start = time.time()
                base_params = self.derive_params(len(ids))
                X_proc, pca_info = self.preprocess_embeddings(X)
                if getattr(config, 'TOPIC_CLUSTERING_DEBUG', False):
                    print(f"[topic-cluster] initial params={base_params} pca_components={pca_info.get('pca_components')} proc_shape={X_proc.shape}")

                # Adaptive multi-pass strategy
                target_min = max(15, min(80, len(ids)//120))  # dynamic acceptable cluster lower bound
                max_iters = 6
                floor_ = getattr(config, 'TOPIC_CLUSTERING_MIN_CLUSTER_SIZE_FLOOR', 5)
                best_state = None  # (metrics, labels, probs, params, selection_method)
                params = base_params.copy()
                selection_method = 'leaf'
                for it in range(max_iters):
                    labels, probs, _model = self.run_hdbscan(X_proc, params, selection_method=selection_method)
                    metrics = self.evaluate(labels, probs, X_proc, params, start)
                    if getattr(config, 'TOPIC_CLUSTERING_DEBUG', False):
                        print(f"[topic-cluster] iter={it} method={selection_method} mcs={params['min_cluster_size']} ms={params['min_samples']} clusters={metrics.cluster_count} noise={metrics.noise_ratio:.3f}")
                    # Track best: prefer more clusters; tie-break lower noise
                    if not best_state or metrics.cluster_count > best_state[0].cluster_count or (metrics.cluster_count == best_state[0].cluster_count and metrics.noise_ratio < best_state[0].noise_ratio):
                        best_state = (metrics, labels.copy(), None if probs is None else probs.copy(), params.copy(), selection_method)
                    # Early accept conditions
                    if metrics.cluster_count >= target_min and metrics.noise_ratio <= 0.65:
                        break
                    if params['min_cluster_size'] <= floor_:
                        # Try switching method if not already 'eom'
                        if selection_method == 'leaf':
                            selection_method = 'eom'
                            continue
                        break
                    # Adapt parameters for next iteration
                    params['min_cluster_size'] = max(floor_, int(params['min_cluster_size'] * 0.75))
                    params['min_samples'] = max(3, int(params['min_cluster_size'] * 0.35))
                # Use best found
                metrics, labels, probs, params, selection_method = best_state  # type: ignore
                metrics.warnings.append(f"final_selection_method={selection_method}")

                # Label clusters (LLM only)
                cluster_members = self._build_cluster_members(labels, probs, ids, texts)
                labeled_clusters = self.label_clusters(cluster_members)
                snapshot = self.build_snapshot(ids, labels, probs, metrics, params, pca_info, labeled_clusters)
                self.save_snapshot_atomic(snapshot)
                return snapshot
            except Exception as e:
                # Comprehensive error handling for numpy array truthiness and other issues
                if "ambiguous" in str(e).lower() and "truth value" in str(e).lower():
                    print(f"[topic-cluster] numpy array truthiness error detected: {e}")
                    print("[topic-cluster] this indicates a boolean evaluation of numpy arrays")
                    if getattr(config, 'TOPIC_CLUSTERING_DEBUG', False):
                        import traceback
                        traceback.print_exc()
                raise e
            # Propagate labels back into structure for snapshot
            # We create a temp mapping used for snapshot assembly with proper labels/keywords
            for cid, data in labeled_clusters.items():
                pass  # data mutated in place
            snapshot = self.build_snapshot(ids, labels, probs, metrics, params, pca_info)
            # Replace cluster entries with updated labels / keywords
            label_map = {cid: data for cid, data in labeled_clusters.items()}
            for entry in snapshot['clusters']:
                cid = entry['id']
                if cid in label_map:
                    entry['label'] = label_map[cid].get('label', entry['label'])
                    entry['top_keywords'] = label_map[cid].get('top_keywords', entry['top_keywords'])
                    entry['exemplar_video_id'] = label_map[cid].get('exemplar', entry['exemplar_video_id'])
                    entry['mean_probability'] = label_map[cid].get('mean_probability', entry['mean_probability'])
            self.save_snapshot_atomic(snapshot)
            return snapshot

    def get_topics(self, sort: str = 'size_desc', include_noise: bool = False, limit: Optional[int] = None, offset: int = 0) -> Dict[str, Any]:
        snap = self.load_snapshot()
        if not snap:
            return {'clusters': [], 'count': 0, 'total_videos': 0}
        clusters = snap.get('clusters', [])
        if not include_noise:
            assignments = snap.get('assignments', {})
            noise_ids = {vid for vid, lbl in assignments.items() if lbl == -1}
            # Filter out clusters referencing noise id; noise cluster not explicitly stored; nothing to remove.
            # (If later we add an explicit noise entry, we'd filter here.)
            pass
        if sort == 'size_asc':
            clusters.sort(key=lambda c: c.get('size', 0))
        elif sort == 'alpha':
            clusters.sort(key=lambda c: (c.get('label') or '').lower())
        elif sort == 'alpha_desc':
            clusters.sort(key=lambda c: (c.get('label') or '').lower(), reverse=True)
        else:
            clusters.sort(key=lambda c: c.get('size', 0), reverse=True)
        total = len(clusters)
        if offset:
            clusters = clusters[offset:]
        if limit is not None:
            clusters = clusters[:limit]
        return {
            'clusters': clusters,
            'count': len(clusters),
            'total': total,
            'total_videos': snap.get('total_videos'),
            'generated_at': snap.get('generated_at'),
            'noise_ratio': snap.get('noise_ratio'),
            'cluster_count': snap.get('cluster_count'),
        }

    def get_cluster(self, cluster_id: int) -> Dict[str, Any]:
        snap = self.load_snapshot()
        if not snap:
            return {'error': 'no snapshot'}
        assignments = snap.get('assignments', {})
        member_ids = [vid for vid, lbl in assignments.items() if lbl == cluster_id]
        # Pull metadata for members
        items = self.vectordb.get_items(member_ids)
        videos: List[Dict[str, Any]] = []
        for vid in member_ids:
            item = items.get(vid)
            if not item:
                continue
            meta = item.get('metadata', {}) or {}
            videos.append({
                'id': vid,
                'title': meta.get('title'),
                'channel': meta.get('channel'),
                'url': meta.get('url'),
                'published_at': meta.get('publishedAt'),
                'duration_seconds': meta.get('duration_seconds'),
                'thumbnail': f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"
            })
        cluster_entry = None
        for c in snap.get('clusters', []):
            if int(c.get('id')) == cluster_id:
                cluster_entry = c
                break
        return {
            'cluster': cluster_entry,
            'videos': videos,
            'count': len(videos),
            'cluster_id': cluster_id
        }


_topic_service_singleton: Optional[TopicClusteringService] = None


def get_topic_clustering_service() -> TopicClusteringService:
    global _topic_service_singleton
    if _topic_service_singleton is None:
        try:
            vectordb = VectorDBService(path=config.CHROMA_DB_PATH, collection_name=config.CHROMA_COLLECTION_NAME)
            _topic_service_singleton = TopicClusteringService(vectordb)
            if getattr(config, 'TOPIC_CLUSTERING_REBUILD_ON_START_IF_MISSING', True):
                try:
                    needs_rebuild_result = _topic_service_singleton.needs_rebuild()
                    if needs_rebuild_result:
                        _topic_service_singleton.rebuild(force=True)
                except Exception as e:  # pragma: no cover (startup path)
                    print(f"Warning: initial topic clustering rebuild failed: {e}")
        except Exception as e:
            print(f"Warning: topic clustering service initialization failed: {e}")
            # Create a minimal service that won't crash endpoints
            vectordb = VectorDBService(path=config.CHROMA_DB_PATH, collection_name=config.CHROMA_COLLECTION_NAME)
            _topic_service_singleton = TopicClusteringService(vectordb)
    return _topic_service_singleton
