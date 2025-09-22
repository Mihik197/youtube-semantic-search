# src/services/vectordb_service.py
import chromadb
from tqdm import tqdm
from src import config
from typing import List, Dict, Any, Optional

class VectorDBService:
    """A service class for interacting with a ChromaDB vector database."""

    def __init__(self, path: str, collection_name: str):
        print(f"Initializing ChromaDB client at: {path}")
        try:
            self.client = chromadb.PersistentClient(path=path)
            print(f"Getting or creating ChromaDB collection: '{collection_name}'")
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"} 
            )
            print(f"Collection '{collection_name}' ready. Item count: {self.count()}")
        except Exception as e:
            print(f"Fatal Error initializing ChromaDB: {e}")
            raise

    def upsert_documents(self, embeddings: List[list], ids: List[str], metadatas: List[dict], documents: List[str]) -> tuple[int, int]:
        """
        Upserts (inserts or updates) documents into the ChromaDB collection.

        Args:
            embeddings (List[list]): List of embedding vectors.
            ids (List[str]): List of corresponding document IDs.
            metadatas (List[dict]): List of corresponding metadata dictionaries.
            documents (List[str]): List of corresponding source text documents.

        Returns:
            tuple[int, int]: A tuple of (added_count, skipped_count).
        """
        # Defensive length checks to avoid numpy array ambiguous truth values
        if (len(embeddings) == 0 or len(ids) == 0 or 
            len(metadatas) == 0 or len(documents) == 0):
            print("Warning: Empty lists provided for ChromaDB storage. Skipping.")
            return 0, 0

        if not (len(embeddings) == len(ids) == len(metadatas) == len(documents)):
            print("Error: Mismatch in list lengths for ChromaDB storage. Aborting.")
            return 0, len(ids)

        added_count, skipped_count = 0, 0
        for i in tqdm(range(0, len(ids), config.CHROMA_BATCH_SIZE), desc="ChromaDB Batches"):
            batch_end = min(i + config.CHROMA_BATCH_SIZE, len(ids))
            try:
                self.collection.upsert(
                    ids=ids[i:batch_end],
                    embeddings=embeddings[i:batch_end],
                    metadatas=metadatas[i:batch_end],
                    documents=documents[i:batch_end]
                )
                added_count += len(ids[i:batch_end])
            except Exception as e:
                print(f"\nError adding batch to ChromaDB: {e}")
                skipped_count += len(ids[i:batch_end])
        
        print(f"Finished upserting to ChromaDB. Added/Updated: {added_count}, Skipped: {skipped_count}")
        return added_count, skipped_count

    def query(self, query_embedding: List[float], n_results: int) -> Optional[Dict[str, Any]]:
        """Performs a similarity search against the collection."""
        try:
            return self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                include=['metadatas', 'distances', 'documents']
            )
        except Exception as e:
            print(f"Error querying ChromaDB: {e}")
            return None

    def delete(self, ids: List[str]):
        """Deletes documents from the collection by their IDs."""
        if not ids:
            return
        try:
            self.collection.delete(ids=ids)
            print(f"Deleted {len(ids)} items from ChromaDB.")
        except Exception as e:
            print(f"Error deleting items from ChromaDB: {e}")

    def get_all_ids(self) -> List[str]:
        """Retrieves all document IDs from the collection."""
        try:
            return self.collection.get(include=[])['ids']
        except Exception as e:
            print(f"Error getting all IDs from ChromaDB: {e}")
            return []

    def count(self) -> int:
        """Returns the total number of items in the collection."""
        try:
            return self.collection.count()
        except Exception as e:
            print(f"Error counting items in ChromaDB: {e}")
            return 0

    def get_all_metadatas(self, batch_size: int = 1000, include_ids: bool = True) -> list[dict]:
        """Retrieve all metadatas (and optionally IDs) from the collection.

        Chroma's collection.get may limit results; this performs batched retrieval.

        Args:
            batch_size: Number of records to pull per batch.
            include_ids: If True, include the id in each metadata dict under key 'id'.

        Returns:
            List of metadata dictionaries.
        """
        metadatas: list[dict] = []
        try:
            total = self.count()
            if total == 0:
                return metadatas
            offset = 0
            while offset < total:
                try:
                    batch = self.collection.get(
                        include=["metadatas"],
                        offset=offset,
                        limit=min(batch_size, total - offset)
                    )
                    batch_metas = batch.get('metadatas', [])
                    if batch_metas is None:
                        batch_metas = []
                    if include_ids:
                        batch_ids = batch.get('ids', [])
                        if batch_ids is None:
                            batch_ids = []
                        for i, m in enumerate(batch_metas):
                            if isinstance(m, dict):
                                m = m.copy()
                                if i < len(batch_ids):
                                    m['id'] = batch_ids[i]
                                metadatas.append(m)
                    else:
                        metadatas.extend([m for m in batch_metas if isinstance(m, dict)])
                    if not batch_metas:
                        break  # defensive break to avoid infinite loop
                    offset += len(batch_metas)
                except Exception as inner_e:
                    print(f"Warning: Failed to retrieve metadatas batch at offset {offset}: {inner_e}")
                    break
        except Exception as e:
            print(f"Error retrieving all metadatas: {e}")
        return metadatas

    def get_videos_by_channel(self, channel: str, limit: int = 500) -> list[dict]:
        """Return a list of video metadata dicts for a specific channel.

        Args:
            channel: Channel name to match exactly (case-sensitive as stored).
            limit: Max number of videos to return (safety cap).
        Returns:
            List of dictionaries with keys: id, title, channel, url, (and others present in metadata).
        """
        if not channel:
            return []
        try:
            # Attempt simple where filter; if unsupported, fallback to manual filter
            raw = self.collection.get(
                where={'channel': channel},
                include=['metadatas', 'ids', 'documents'],
                limit=limit
            )
            metadatas = raw.get('metadatas', [])
            if metadatas is None:
                metadatas = []
            ids = raw.get('ids', [])
            if ids is None:
                ids = []
            docs = raw.get('documents', [])
            if docs is None:
                docs = []
            videos = []
            for i, m in enumerate(metadatas):
                if not isinstance(m, dict):
                    continue
                vid = m.copy()
                if i < len(ids):
                    vid['id'] = ids[i]
                if i < len(docs):
                    vid['document'] = docs[i]
                videos.append(vid)
            return videos
        except Exception as e:
            print(f"Warning: direct channel query failed ({e}); falling back to full scan.")
            # Fallback full scan limited by limit
            result = []
            for m in self.get_all_metadatas():
                if m.get('channel') == channel:
                    result.append(m)
                    if len(result) >= limit:
                        break
            return result

    # --- Enrichment / Maintenance Helpers ---
    def get_items(self, ids: List[str]) -> dict[str, dict]:
        """Retrieve existing items (embeddings, metadatas, documents) for given IDs.

        Batches requests to avoid underlying client edge cases. Returns mapping id ->
        { 'embedding': [...], 'metadata': {...}, 'document': str }
        Missing IDs are skipped.
        """
        if not ids:
            return {}
        out: dict[str, dict] = {}
        try:
            batch_size = getattr(config, 'CHROMA_BATCH_SIZE', 100) if 'config' in globals() else 100
        except Exception:
            batch_size = 100
        for i in range(0, len(ids), batch_size):
            subset = ids[i:i+batch_size]
            try:
                batch = self.collection.get(ids=subset, include=['embeddings', 'metadatas', 'documents'])
                got_ids = batch.get('ids', [])
                if got_ids is None:
                    got_ids = []
                mets = batch.get('metadatas', [])
                if mets is None:
                    mets = []
                embs = batch.get('embeddings', [])
                if embs is None:
                    embs = []
                docs = batch.get('documents', [])
                if docs is None:
                    docs = []
                for j, vid in enumerate(got_ids):
                    out[vid] = {
                        'embedding': embs[j] if j < len(embs) else None,
                        'metadata': mets[j] if j < len(mets) else {},
                        'document': docs[j] if j < len(docs) else ''
                    }
            except Exception as e:
                print(f"Warning: failed to retrieve batch of items ({len(subset)} ids) - {e}")
        return out

    def update_metadatas(self, updates: dict[str, dict]) -> tuple[int, int]:
        """Merge and update metadata for existing IDs.

        Args:
            updates: mapping id -> partial metadata to merge into existing.
        Returns:
            (updated_count, skipped_missing)
        """
        if not updates:
            return 0, 0
        ids = list(updates.keys())
        existing = self.get_items(ids)
        to_upsert_ids: list[str] = []
        to_upsert_embeddings: list[list] = []
        to_upsert_metadatas: list[dict] = []
        to_upsert_documents: list[str] = []
        skipped = 0
        for vid in ids:
            item = existing.get(vid)
            if not item:
                skipped += 1
                continue
            merged_meta = item['metadata'].copy() if isinstance(item['metadata'], dict) else {}
            patch = updates[vid] or {}
            merged_meta.update({k: v for k, v in patch.items() if v is not None})
            to_upsert_ids.append(vid)
            to_upsert_embeddings.append(item['embedding'])
            to_upsert_metadatas.append(merged_meta)
            to_upsert_documents.append(item['document'])
        if to_upsert_ids:
            try:
                self.collection.upsert(
                    ids=to_upsert_ids,
                    embeddings=to_upsert_embeddings,
                    metadatas=to_upsert_metadatas,
                    documents=to_upsert_documents
                )
            except Exception as e:
                print(f"Error during metadata update upsert: {e}")
                return 0, len(ids)
        return len(to_upsert_ids), skipped

    def bulk_update_metadatas(self, updates: dict[str, dict], batch_size: int | None = None) -> tuple[int, int]:
        """Efficiently apply metadata patches by scanning collection once.

        This avoids repeated per-ID get calls (which caused ambiguous truth value errors
        with some underlying client array types). We stream through all records in batches,
        merging only those in the updates dict. Embeddings and documents are preserved.

        Args:
            updates: mapping id -> partial metadata patch
            batch_size: override batch size (defaults to CHROMA_BATCH_SIZE or 100)
        Returns:
            (updated, skipped_missing)
        """
        if not updates:
            return 0, 0
        try:
            if batch_size is None:
                batch_size = getattr(config, 'CHROMA_BATCH_SIZE', 100)
        except Exception:
            batch_size = 100
        total = self.count()
        if total == 0:
            return 0, 0
        updated = 0
        skipped_missing = 0
        offset = 0
        while offset < total:
            try:
                batch = self.collection.get(
                    include=['metadatas', 'embeddings', 'documents'],
                    offset=offset,
                    limit=min(batch_size, total - offset)
                )
            except Exception as e:
                print(f"Error retrieving batch at offset {offset}: {e}")
                break
            ids = batch.get('ids', [])
            if ids is None:
                ids = []
            mets = batch.get('metadatas', [])
            if mets is None:
                mets = []
            embs = batch.get('embeddings', [])
            if embs is None:
                embs = []
            docs = batch.get('documents', [])
            if docs is None:
                docs = []
            if not ids:
                break
            to_update_ids = []
            to_update_embs = []
            to_update_metas = []
            to_update_docs = []
            for i, vid in enumerate(ids):
                if vid in updates:
                    base_meta = mets[i] if i < len(mets) and isinstance(mets[i], dict) else {}
                    patch = updates[vid] or {}
                    merged = base_meta.copy()
                    merged.update({k: v for k, v in patch.items() if v is not None})
                    to_update_ids.append(vid)
                    to_update_embs.append(embs[i] if i < len(embs) else None)
                    to_update_metas.append(merged)
                    to_update_docs.append(docs[i] if i < len(docs) else '')
            if to_update_ids:
                try:
                    self.collection.upsert(
                        ids=to_update_ids,
                        embeddings=to_update_embs,
                        metadatas=to_update_metas,
                        documents=to_update_docs
                    )
                    updated += len(to_update_ids)
                except Exception as e:
                    print(f"Error upserting metadata batch (offset {offset}): {e}")
            offset += len(ids)
        # Compute skipped_missing as those update keys never encountered
        skipped_missing = len([k for k in updates.keys() if k not in self.collection.get(ids=list(updates.keys()), include=[]).get('ids', [])])
        return updated, skipped_missing

    def patch_metadatas(self, updates: dict[str, dict], batch_size: int | None = None) -> tuple[int, int]:
        """Merge patches into existing metadatas using collection.update (no embedding fetch).

        This avoids retrieving embeddings (source of ambiguous truth value errors) and is
        sufficient when only adding new metadata keys.
        """
        if not updates:
            return 0, 0
        try:
            if batch_size is None:
                batch_size = getattr(config, 'CHROMA_BATCH_SIZE', 100)
        except Exception:
            batch_size = 100
        ids_all = list(updates.keys())
        updated = 0
        skipped_missing = 0
        for i in range(0, len(ids_all), batch_size):
            subset = ids_all[i:i+batch_size]
            try:
                existing = self.collection.get(ids=subset, include=['metadatas'])
            except Exception as e:
                print(f"Warning: failed to fetch metadata batch for update ({len(subset)} ids): {e}")
                skipped_missing += len(subset)
                continue
            got_ids = existing.get('ids', [])
            if got_ids is None:
                got_ids = []
            existing_mets = existing.get('metadatas', [])
            if existing_mets is None:
                existing_mets = []
            existing_map = {}
            for j, vid in enumerate(got_ids):
                base = existing_mets[j] if j < len(existing_mets) and isinstance(existing_mets[j], dict) else {}
                existing_map[vid] = base
            patch_ids = []
            patch_metas = []
            for vid in subset:
                patch = updates.get(vid) or {}
                if vid not in existing_map:
                    skipped_missing += 1
                    continue
                merged = existing_map[vid].copy()
                merged.update({k: v for k, v in patch.items() if v is not None})
                patch_ids.append(vid)
                patch_metas.append(merged)
            if patch_ids:
                try:
                    self.collection.update(ids=patch_ids, metadatas=patch_metas)
                    updated += len(patch_ids)
                except Exception as e:
                    print(f"Error applying metadata patch batch (size {len(patch_ids)}): {e}")
        return updated, skipped_missing
