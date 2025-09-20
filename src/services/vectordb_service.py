# src/services/vectordb_service.py
import chromadb
from tqdm import tqdm
from src import config
from typing import List, Dict, Any, Optional

class VectorDBService:
    """A service class for interacting with a ChromaDB vector database."""

    def __init__(self, path: str, collection_name: str):
        """
        Initializes the VectorDBService.

        Args:
            path (str): The path to the ChromaDB persistent storage.
            collection_name (str): The name of the collection to use.
        
        Raises:
            Exception: For errors during ChromaDB client or collection initialization.
        """
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
        if not all([embeddings, ids, metadatas, documents]):
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
                    batch_metas = batch.get('metadatas', []) or []
                    if include_ids:
                        batch_ids = batch.get('ids', []) or []
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
            metadatas = raw.get('metadatas', []) or []
            ids = raw.get('ids', []) or []
            docs = raw.get('documents', []) or []
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
