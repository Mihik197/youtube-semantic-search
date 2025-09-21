# src/services/rerank_service.py
import json
import time
import hashlib
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from google import genai
from google.genai import types

from src import config

@dataclass
class CandidateVideo:
    id: str
    title: str
    description: str | None
    channel: str | None
    published_at: str | None
    duration: str | None
    duration_seconds: int | None
    tags: List[str] | None
    url: str | None
    similarity_score: float | None = None  # retained for potential hybrid use

class RerankService:
    """Handles LLM-based reranking of candidate videos."""

    def __init__(self, api_key: str, model_name: str | None = None):
        if not api_key:
            raise ValueError("Gemini API key required for reranking.")
        self.model_name = model_name or config.RERANK_MODEL_NAME
        self.client = genai.Client(api_key=api_key)

    @staticmethod
    def _truncate(text: Optional[str], limit: int) -> str:
        if not text:
            return ""
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "…"

    def build_payload(self, query: str, candidates: List[CandidateVideo]) -> Dict[str, Any]:
        payload_candidates: List[Dict[str, Any]] = []
        for c in candidates:
            payload_candidates.append({
                "id": c.id,
                "title": c.title or "",
                "channel": c.channel or "",
                "published": c.published_at or "",
                "duration_seconds": c.duration_seconds,
                "tags": (c.tags or [])[: config.RERANK_MAX_TAGS],
                "description": self._truncate(c.description, config.RERANK_MAX_DESCRIPTION_CHARS)
            })
        return {
            "query": query,
            "instruction": "You are a ranking engine. Rank candidate YouTube videos strictly by their relevance to the user query. Return JSON only.",
            "candidates": payload_candidates,
            "output_schema": {"ranked": [{"id": "video_id", "score": 0}]}
        }

    def _system_message(self) -> str:
        return (
            "You are a strict relevance ranking module. Given a user query and up to 50 YouTube video metadata records, "
            "output ONLY JSON with key 'ranked' whose value is an array of objects each having at minimum 'id' in most relevant to least relevant order. "
            "Do NOT include commentary. Do NOT add fields not requested. Use only provided IDs."
        )

    def _parse_ranked(self, raw_text: str, candidate_ids: set[str]) -> List[Dict[str, Any]]:
        # Strip common fence wrappers
        cleaned = raw_text.strip()
        if cleaned.startswith('```'):
            # remove leading fence line
            parts = cleaned.split('\n')
            # drop first and possible last fence
            if parts and parts[0].startswith('```'):
                parts = parts[1:]
            if parts and parts[-1].startswith('```'):
                parts = parts[:-1]
            cleaned = '\n'.join(parts).strip()
        # Attempt JSON parse
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, dict):
            return []
        ranked = data.get('ranked')
        if not isinstance(ranked, list):
            return []
        seen = set()
        output: List[Dict[str, Any]] = []
        for item in ranked:
            if not isinstance(item, dict):
                continue
            vid = item.get('id')
            if not isinstance(vid, str):
                continue
            if vid not in candidate_ids:
                continue
            if vid in seen:
                continue
            seen.add(vid)
            score = item.get('score')
            if isinstance(score, (int, float)):
                output.append({'id': vid, 'score': float(score)})
            else:
                output.append({'id': vid})
        return output

    def rerank(self, query: str, candidates: List[CandidateVideo]) -> Dict[str, Any]:
        start = time.time()
        query_hash = hashlib.sha256(query.encode('utf-8')).hexdigest()[:8]
        payload = self.build_payload(query, candidates)
        system_message = self._system_message()
        candidate_ids = {c.id for c in candidates}
        result: Dict[str, Any] = {
            'applied': False,
            'ordered_ids': [c.id for c in candidates],  # default original order fallback
            'model': self.model_name,
            'latency_ms': 0,
            'reason': 'not_run'
        }
        try:
            # Build content per google-genai text generation API
            # According to docs: client.models.generate_content(model=..., contents=[...])
            user_payload_json = json.dumps(payload, ensure_ascii=False)
            combined = (
                system_message + "\n---\n" +
                "JSON INPUT:" + "\n" + user_payload_json + "\n" +
                "Return ONLY valid JSON with key 'ranked'."
            )
            input_token_count = None
            if getattr(config, 'RERANK_LOG_TOKEN_USAGE', False):
                try:
                    # Gemini count tokens endpoint; fallback silent if unsupported
                    ct = self.client.models.count_tokens(model=self.model_name, contents=[combined])
                    # Attribute names may differ (usage_metadata vs total_tokens). Use best-effort.
                    if ct and hasattr(ct, 'total_tokens'):
                        input_token_count = getattr(ct, 'total_tokens')
                    elif ct and hasattr(ct, 'usage_metadata'):
                        um = getattr(ct, 'usage_metadata')
                        if um and hasattr(um, 'total_token_count'):
                            input_token_count = getattr(um, 'total_token_count')
                except Exception:
                    pass
            resp = self.client.models.generate_content(
                model=self.model_name,
                contents=[combined],
                config=types.GenerateContentConfig(temperature=0.2)
            )
            # Aggregate text output (library may expose output_text convenience attribute)
            raw_text = ""
            if hasattr(resp, 'output_text') and resp.output_text:
                raw_text = resp.output_text.strip()
            else:
                # Fallback to collecting candidate part texts if structure present
                text_chunks: List[str] = []
                for cand in getattr(resp, 'candidates', []) or []:
                    content = getattr(cand, 'content', None)
                    parts = getattr(content, 'parts', []) if content else []
                    for part in parts:
                        txt = getattr(part, 'text', None)
                        if txt:
                            text_chunks.append(txt)
                raw_text = "\n".join(text_chunks).strip()
            parsed = self._parse_ranked(raw_text, candidate_ids)
            if not parsed:
                result['reason'] = 'parse_failed'
            else:
                # Compose ordered list; append leftovers preserving original order
                ranked_ids = [p['id'] for p in parsed]
                leftover = [cid for cid in result['ordered_ids'] if cid not in set(ranked_ids)]
                final_ids = ranked_ids + leftover
                result['ordered_ids'] = final_ids
                result['applied'] = True
                result['reason'] = 'success'
                # Optional numeric scores from LLM if provided
                llm_scores = {p['id']: p.get('score') for p in parsed if 'score' in p}
                if any(v is not None for v in llm_scores.values()):
                    result['llm_scores'] = {k: v for k, v in llm_scores.items() if v is not None}
            if getattr(config, 'RERANK_LOG_TOKEN_USAGE', False):
                # Attempt to extract usage metadata from response
                usage_in = input_token_count
                usage_out = None
                usage_total = None
                try:
                    # Newer API surfaces usage in resp.usage_metadata
                    if hasattr(resp, 'usage_metadata'):
                        um = getattr(resp, 'usage_metadata')
                        # Common field names (guessing based on docs patterns)
                        if um and hasattr(um, 'prompt_token_count'):
                            usage_in = getattr(um, 'prompt_token_count') or usage_in
                        if um and hasattr(um, 'candidates_token_count'):
                            usage_out = getattr(um, 'candidates_token_count')
                        if um and hasattr(um, 'total_token_count'):
                            usage_total = getattr(um, 'total_token_count')
                    # Some versions expose top-level token counts on response
                    if usage_out is None and hasattr(resp, 'output_tokens'):
                        usage_out = getattr(resp, 'output_tokens')
                    if usage_total is None and usage_in is not None and usage_out is not None:
                        try:
                            usage_total = usage_in + usage_out
                        except Exception:
                            pass
                except Exception:
                    pass
                print(f"RERANK_TOKENS query_hash={query_hash} input_tokens={usage_in} output_tokens={usage_out} total_tokens={usage_total}")
        except Exception as e:
            result['reason'] = f'error:{e.__class__.__name__}'
        finally:
            result['latency_ms'] = int((time.time() - start) * 1000)
            print(f"RERANK query_hash={query_hash} applied={result['applied']} reason={result['reason']} latency_ms={result['latency_ms']} candidates={len(candidates)}")
        return result

__all__ = ["CandidateVideo", "RerankService"]
