from __future__ import annotations

from typing import Iterable, List, Tuple

RERANK_SYSTEM_PROMPT = """
    You are a strict relevance ranking module. 
    Given a user query and YouTube video metadata, rank videos by relevance to the query. 
    Return only the requested JSON structure.
"""


def build_rerank_prompt(query: str, ranking_json: str) -> str:
    return (
        f"{RERANK_SYSTEM_PROMPT}\n\n"
        f"Query: {query}\n\n"
        f"Candidates to rank:\n{ranking_json}\n\n"
        "Rank these videos by relevance to the query."
    )


TOPIC_LABEL_PROMPT_HEADER = """
    You label clusters of YouTube videos. Respond with strict JSON only.
    Each cluster entry must contain: id (int), label (<=4 words), keywords
    (<= {max_keywords}, lowercase). Keep labels specific and readable.
"""


def build_topic_label_prompt(
    clusters: Iterable[Tuple[int, List[str]]],
    *,
    max_keywords: int,
) -> str:
    lines: List[str] = [TOPIC_LABEL_PROMPT_HEADER.format(max_keywords=max_keywords), "Clusters:"]
    for cluster_id, texts in clusters:
        samples = []
        for text in texts[:15]:
            clean = " ".join(text.split())
            if len(clean) > 140:
                clean = clean[:140] + "…"
            if clean:
                samples.append(f"- {clean}")
        if not samples:
            samples.append("- (no content)")
        lines.append(f"Cluster {cluster_id}:\n" + "\n".join(samples))
    lines.append('Respond with JSON {"clusters":[{"id":1,"label":"...","keywords":["..."]}]}')
    return "\n\n".join(lines)


__all__ = [
    "RERANK_SYSTEM_PROMPT",
    "build_rerank_prompt",
    "build_topic_label_prompt",
]
