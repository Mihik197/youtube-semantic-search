# src/services/embedding_service.py
from __future__ import annotations

import time
from typing import Any, Dict, List, Tuple

from google import genai
from google.genai import types

from src import config


class EmbeddingService:
    """Minimal Gemini embedding helper."""

    def __init__(self, api_key: str, model_name: str = config.EMBEDDING_MODEL_NAME):
        if not api_key:
            raise ValueError("Gemini API key is required")
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def embed_query(self, query: str) -> List[float] | None:
        query = (query or "").strip()
        if not query:
            return None
        result = self.client.models.embed_content(
            model=self.model_name,
            contents=[query],
            config=types.EmbedContentConfig(task_type=config.TASK_TYPE_RETRIEVAL_QUERY),
        )
        if not result.embeddings:
            return None
        return result.embeddings[0].values

    def embed_documents(self, documents: List[Dict[str, Any]]) -> Tuple[List[List[float]], List[str], List[str]]:
        if not documents:
            return [], [], []

        embeddings: List[List[float]] = []
        doc_ids: List[str] = []
        texts: List[str] = []
        batch_size = getattr(config, "EMBEDDING_BATCH_SIZE", 80)

        for start in range(0, len(documents), batch_size):
            batch = documents[start:start + batch_size]
            payload = [(doc.get("id"), doc.get("text")) for doc in batch]
            payload = [(doc_id, text) for doc_id, text in payload if doc_id and text]
            if not payload:
                continue
            batch_ids, batch_texts = zip(*payload)

            response = self.client.models.embed_content(
                model=self.model_name,
                contents=batch_texts,
                config=types.EmbedContentConfig(task_type=config.TASK_TYPE_RETRIEVAL_DOCUMENT),
            )
            embeddings.extend([emb.values for emb in response.embeddings])
            doc_ids.extend(batch_ids)
            texts.extend(batch_texts)
            time.sleep(getattr(config, "EMBEDDING_API_DELAY", 0))

        return embeddings, doc_ids, texts
