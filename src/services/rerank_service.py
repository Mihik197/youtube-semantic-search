"""
Reranking service using Gemini's structured output with Pydantic models.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field

from src import config
from src.services.llm_service import LLMService, log_usage, summarize_usage
from src.services.prompts import build_rerank_prompt


class RankedVideo(BaseModel):
    id: str = Field(description="Video ID from candidates")
    score: Optional[float] = Field(default=None, description="Relevance score 0-1")


class RankingOutput(BaseModel):
    ranked: List[RankedVideo] = Field(description="Videos ordered by relevance")


class VideoCandidate(BaseModel):
    id: str
    title: str
    channel: str = ""
    published: str = ""
    duration_seconds: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    description: str = ""


class RankingInput(BaseModel):
    query: str = Field(description="User search query")
    candidates: List[VideoCandidate] = Field(description="Videos to rank")


def truncate_text(text: Optional[str], limit: int) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"

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
        self.temperature = getattr(config, "RERANK_TEMPERATURE", 0.2)
        self.llm = LLMService(api_key, self.model_name, temperature=self.temperature)

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
        ranking_json = ranking_input.model_dump_json(indent=2)
        prompt = build_rerank_prompt(ranking_input.query, ranking_json)

        # Optional token counting
        input_token_count = None
        if getattr(config, "RERANK_LOG_TOKEN_USAGE", False):
            input_token_count = self.llm.count_tokens(prompt)

        response = None
        parsed: Optional[RankingOutput] = None
        try:
            response, parsed = self.llm.generate_json(prompt, RankingOutput)
        except Exception as exc:
            logger.warning("Reranking failed: %s", exc)
            result["reason"] = "llm_error"
        else:
            if parsed:
                ranked_ids = [vid.id for vid in parsed.ranked if vid.id in candidate_id_set]
                leftover_set: Set[str] = set(ranked_ids)
                leftover = [cid for cid in original_order if cid not in leftover_set]
                final_ids = ranked_ids + leftover

                result["ordered_ids"] = final_ids
                result["applied"] = True
                result["reason"] = "success"

                llm_scores = {vid.id: vid.score for vid in parsed.ranked if vid.score is not None and vid.id in candidate_id_set}
                if llm_scores:
                    result["llm_scores"] = llm_scores
            else:
                result["reason"] = "parse_failed"

        # Token usage logging + optional metrics on response
        log_usage(
            f"RERANK_TOKENS query_hash={query_hash}",
            response=response,
            prompt_tokens=input_token_count,
            logger=logger,
            enabled=getattr(config, "RERANK_LOG_TOKEN_USAGE", False),
        )
        if response is not None:
            usage = summarize_usage(response, input_token_count)
            if any(val is not None for val in usage):
                result["token_usage"] = {
                    "input": usage[0],
                    "output": usage[1],
                    "total": usage[2],
                }

        # Record latency
        result["latency_ms"] = int((time.time() - start) * 1000)
        
        logger.info(
            "RERANK query_hash=%s applied=%s reason=%s latency_ms=%s candidates=%d",
            query_hash, result["applied"], result["reason"], 
            result["latency_ms"], len(candidates)
        )
        
        return result


__all__ = ["CandidateVideo", "RerankService"]