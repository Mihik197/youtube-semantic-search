"""
Utility helpers for reranking service.

Contains:
 - Pydantic models for structured input/output
 - truncate_text helper
 - log_token_usage: centralized token-usage extraction / logging helper
"""

from __future__ import annotations
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from src import config

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class RankedVideo(BaseModel):
    """Single ranked video result."""
    id: str = Field(description="Video ID from candidates")
    score: Optional[float] = Field(None, description="Relevance score 0-1")

class RankingOutput(BaseModel):
    """Expected output schema for ranking."""
    ranked: List[RankedVideo] = Field(description="Videos ordered by relevance")

class VideoCandidate(BaseModel):
    """Input schema for a video candidate."""
    id: str
    title: str
    channel: str = ""
    published: str = ""
    duration_seconds: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    description: str = ""

class RankingInput(BaseModel):
    """Input schema for ranking request."""
    query: str = Field(description="User search query")
    candidates: List[VideoCandidate] = Field(description="Videos to rank")

# System prompt
SYSTEM_PROMPT = """
    You are a strict relevance ranking module. Given a user query and YouTube video metadata, rank videos by relevance to the query. Return only the requested JSON structure.
"""

def truncate_text(text: Optional[str], limit: int) -> str:
    """Return text truncated to `limit` characters with an ellipsis when necessary."""
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"

def log_token_usage(query_hash: str, resp: any, input_token_count: Optional[int] = None):
    """
    Extract token usage statistics (best-effort) and log a single-line info entry.
    If RERANK_LOG_TOKEN_USAGE is not enabled in config, this is a no-op.
    """
    if not getattr(config, "RERANK_LOG_TOKEN_USAGE", False):
        return

    usage_in = input_token_count
    usage_out = None
    usage_total = None

    if hasattr(resp, "usage_metadata"):
        um = getattr(resp, "usage_metadata")
        if um:
            if hasattr(um, "prompt_token_count"):
                usage_in = getattr(um, "prompt_token_count") or usage_in
            if hasattr(um, "candidates_token_count"):
                usage_out = getattr(um, "candidates_token_count")
            if hasattr(um, "total_token_count"):
                usage_total = getattr(um, "total_token_count")

    if usage_total is None and usage_in is not None and usage_out is not None:
        usage_total = usage_in + usage_out

    logger.info(
        "RERANK_TOKENS query_hash=%s input_tokens=%s output_tokens=%s total_tokens=%s",
        query_hash, usage_in, usage_out, usage_total
    )