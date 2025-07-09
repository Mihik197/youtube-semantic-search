# src/services/embedding_service.py
import time
from google import genai
from google.genai import types
from tqdm import tqdm
from src import config
from typing import List, Dict, Any, Tuple, Optional

class EmbeddingService:
    """A service class for handling text embeddings with the Gemini API."""

    def __init__(self, api_key: str, model_name: str = config.EMBEDDING_MODEL_NAME):
        """
        Initializes the EmbeddingService.

        Args:
            api_key (str): The Gemini API key.
            model_name (str): The name of the embedding model to use.

        Raises:
            ValueError: If the API key is not provided.
            Exception: For errors during Gemini client initialization.
        """
        if not api_key:
            raise ValueError("Gemini API Key not provided.")
        
        print("Initializing Gemini client...")
        try:
            self.client = genai.Client(api_key=api_key)
            self.model_name = model_name
            print("Gemini client initialized successfully.")
        except Exception as e:
            print(f"Error initializing Gemini client: {e}")
            raise

    def embed_query(self, query: str) -> Optional[List[float]]:
        """Generates an embedding for a single search query."""
        if not query:
            print("Error: Query cannot be empty.")
            return None
        try:
            result = self.client.models.embed_content(
                model=self.model_name,
                contents=[query],
                config=types.EmbedContentConfig(task_type=config.TASK_TYPE_RETRIEVAL_QUERY)
            )
            return result.embeddings[0].values
        except Exception as e:
            print(f"Error embedding query '{query}': {e}")
            return None

    def embed_documents(self, documents: List[Dict[str, Any]]) -> Tuple[List[list], List[str], List[str]]:
        """
        Generates embeddings for a list of documents.

        Args:
            documents (List[Dict[str, Any]]): A list of dicts, where each dict
                                              must have 'id' and 'text' keys.

        Returns:
            Tuple[List[list], List[str], List[str]]: A tuple containing the
            list of embeddings, list of document IDs, and list of original texts.
        """
        if not documents:
            return [], [], []

        all_embeddings, all_doc_ids, all_texts = [], [], []
        embedding_errors = 0
        
        print(f"Generating embeddings for {len(documents)} documents using model: {self.model_name}...")

        for i in tqdm(range(0, len(documents), config.EMBEDDING_BATCH_SIZE), desc="Embedding Batches"):
            batch_docs = documents[i:i + config.EMBEDDING_BATCH_SIZE]
            batch_texts = [doc['text'] for doc in batch_docs]
            batch_ids = [doc['id'] for doc in batch_docs]

            if not batch_texts:
                continue

            try:
                result = self.client.models.embed_content(
                    model=self.model_name,
                    contents=batch_texts,
                    config=types.EmbedContentConfig(task_type=config.TASK_TYPE_RETRIEVAL_DOCUMENT)
                )
                
                if len(result.embeddings) == len(batch_texts):
                    all_embeddings.extend([emb.values for emb in result.embeddings])
                    all_doc_ids.extend(batch_ids)
                    all_texts.extend(batch_texts)
                else:
                    print(f"Warning: Mismatch in embedding results for batch starting at {i}.")
                    embedding_errors += len(batch_texts)

                time.sleep(config.EMBEDDING_API_DELAY)

            except Exception as e:
                print(f"\nError processing embedding batch starting at index {i}: {e}")
                embedding_errors += len(batch_texts)
        
        print(f"Finished generating embeddings. Successful: {len(all_embeddings)}, Errors: {embedding_errors}")
        return all_embeddings, all_doc_ids, all_texts
