"""
Reranking service using Gemini's structured output with Pydantic models.
"""

from __future__ import annotations

import time
import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from google import genai
from google.genai import types

from src import config
from src.services.rerank_utils import (
    SYSTEM_PROMPT,
    RankingInput,
    RankingOutput,
    VideoCandidate,
    truncate_text,
    log_token_usage,
)

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


@dataclass
class CandidateVideo:
    id: str
    title: str
    description: Optional[str] = None
    channel: Optional[str] = None
    published_at: Optional[str] = None
    duration: Optional[str] = None
    duration_seconds: Optional[int] = None
    tags: Optional[List[str]] = None
    url: Optional[str] = None
    similarity_score: Optional[float] = None


class RerankService:
    """
    RerankService using Gemini's structured output with Pydantic models.
    """

    def __init__(self, api_key: str, model_name: Optional[str] = None):
        if not api_key:
            raise ValueError("Gemini API key required for reranking.")
        self.model_name = model_name or config.RERANK_MODEL_NAME
        self.client = genai.Client(api_key=api_key)

    def _build_ranking_input(self, query: str, candidates: List[CandidateVideo]) -> RankingInput:
        """Convert CandidateVideo list to structured RankingInput."""
        video_candidates = []
        for c in candidates:
            video_candidates.append(VideoCandidate(
                id=c.id,
                title=c.title or "",
                channel=c.channel or "",
                published=c.published_at or "",
                duration_seconds=c.duration_seconds,
                tags=(c.tags or [])[:config.RERANK_MAX_TAGS],
                description=truncate_text(c.description, config.RERANK_MAX_DESCRIPTION_CHARS)
            ))
        return RankingInput(query=query, candidates=video_candidates)

    def rerank(self, query: str, candidates: List[CandidateVideo]) -> Dict[str, Any]:
        """
        Main entrypoint using Gemini's structured output:
          - Builds structured input
          - Calls model with response_schema for JSON mode
          - Processes structured output directly
          - Returns result dictionary
        """
        start = time.time()
        query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()[:8]
        original_order = [c.id for c in candidates]
        candidate_id_set = set(original_order)

        result: Dict[str, Any] = {
            "applied": False,
            "ordered_ids": original_order.copy(),
            "model": self.model_name,
            "latency_ms": 0,
            "reason": "not_run",
        }

        # Build structured input
        ranking_input = self._build_ranking_input(query, candidates)
        
        # Prepare prompt with structured data
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Query: {ranking_input.query}\n\n"
            f"Candidates to rank:\n{ranking_input.model_dump_json(indent=2)}\n\n"
            "Rank these videos by relevance to the query."
        )

        # Optional token counting
        input_token_count = None
        if getattr(config, "RERANK_LOG_TOKEN_USAGE", False):
            ct = self.client.models.count_tokens(
                model=self.model_name,
                contents=[prompt]
            )
            if hasattr(ct, "total_tokens"):
                input_token_count = ct.total_tokens

        try:
            # Use Gemini's structured output with Pydantic schema
            resp = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                    response_schema=RankingOutput
                )
            )

            # Parse the structured response
            if resp and resp.text:
                output = RankingOutput.model_validate_json(resp.text)
                
                # Filter to valid candidate IDs and build ordered list
                ranked_ids = [
                    v.id for v in output.ranked 
                    if v.id in candidate_id_set
                ]
                
                # Add any missing candidates at the end
                leftover = [cid for cid in original_order if cid not in set(ranked_ids)]
                final_ids = ranked_ids + leftover
                
                result["ordered_ids"] = final_ids
                result["applied"] = True
                result["reason"] = "success"
                
                # Include scores if present
                llm_scores = {
                    v.id: v.score for v in output.ranked 
                    if v.score is not None and v.id in candidate_id_set
                }
                if llm_scores:
                    result["llm_scores"] = llm_scores

        except Exception as e:
            logger.warning("Reranking failed: %s", str(e))
            result["reason"] = "parse_failed"

        # Log token usage
        log_token_usage(query_hash, resp if 'resp' in locals() else None, input_token_count)

        # Record latency
        result["latency_ms"] = int((time.time() - start) * 1000)
        
        logger.info(
            "RERANK query_hash=%s applied=%s reason=%s latency_ms=%s candidates=%d",
            query_hash, result["applied"], result["reason"], 
            result["latency_ms"], len(candidates)
        )
        
        return result


__all__ = ["CandidateVideo", "RerankService"]