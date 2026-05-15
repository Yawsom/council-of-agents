from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Optional

from ..graph.nodes import Claim
from ..providers.base import LLMProvider
from .embedder import Embedder, NullEmbedder

logger = logging.getLogger(__name__)


@dataclass
class DedupResult:
    is_duplicate: bool
    merge_into: Optional[str]  # claim id to merge into, or None
    similarity: float
    method: str  # "embedding_high" | "embedding_low" | "disambiguation" | "exact_text" | "null_embedder"
    decision: str  # human-readable reason


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


async def _disambiguation_call(
    text_a: str,
    text_b: str,
    llm: LLMProvider,
    model: str,
) -> bool:
    """Ask a small LLM whether two claims are the same assertion. Returns True if same."""
    prompt = (
        "Are the following two statements making the same core assertion? "
        "Answer with exactly one word: Yes or No.\n\n"
        f"Statement A: {text_a}\n\n"
        f"Statement B: {text_b}"
    )
    response = await llm.call(
        messages=[{"role": "user", "content": prompt}],
        model=model,
        temperature=0.0,
        timeout=30.0,
    )
    return response.content.strip().lower().startswith("yes")


async def check_identity(
    new_text: str,
    existing_claims: list[Claim],
    embedder: Embedder,
    llm: LLMProvider,
    disambiguation_model: str,
    similarity_high: float = 0.9,
    similarity_low: float = 0.7,
    merge_log: Optional[list[dict]] = None,
) -> DedupResult:
    """
    Check if new_text duplicates any existing claim.
    Returns DedupResult describing the decision.
    All decisions are logged to merge_log (appended in-place).
    """
    if not existing_claims:
        return DedupResult(
            is_duplicate=False, merge_into=None, similarity=0.0,
            method="no_existing_claims", decision="First claim, no comparison needed",
        )

    # --- Exact text match (fast path) ---
    for claim in existing_claims:
        if claim.text.strip().lower() == new_text.strip().lower():
            result = DedupResult(
                is_duplicate=True, merge_into=claim.id, similarity=1.0,
                method="exact_text", decision=f"Exact text match with {claim.id}",
            )
            _log(merge_log, new_text, claim, result)
            return result

    # --- Embedding-based similarity ---
    is_null = isinstance(embedder, NullEmbedder)
    try:
        all_texts = [new_text] + [c.text for c in existing_claims]
        all_embeddings = await embedder.embed(all_texts)
        new_emb = all_embeddings[0]
        existing_embs = all_embeddings[1:]
    except Exception as e:
        logger.warning(
            "embedding_failure_fallback",
            extra={"error": str(e), "detail": "Falling back to exact-text matching only"},
        )
        return DedupResult(
            is_duplicate=False, merge_into=None, similarity=0.0,
            method="embedding_failure", decision=f"Embedding failed: {e}. Treating as new claim.",
        )

    # Find most similar
    similarities = [
        (_cosine_similarity(new_emb, emb), claim)
        for emb, claim in zip(existing_embs, existing_claims)
    ]
    similarities.sort(key=lambda x: x[0], reverse=True)
    best_sim, best_claim = similarities[0]

    if is_null:
        result = DedupResult(
            is_duplicate=False, merge_into=None, similarity=0.0,
            method="null_embedder", decision="NullEmbedder active — treating as new claim",
        )
        _log(merge_log, new_text, None, result)
        return result

    if best_sim >= similarity_high:
        result = DedupResult(
            is_duplicate=True, merge_into=best_claim.id, similarity=best_sim,
            method="embedding_high",
            decision=f"Similarity {best_sim:.3f} >= {similarity_high} with {best_claim.id}",
        )
        _log(merge_log, new_text, best_claim, result)
        return result

    if best_sim < similarity_low:
        result = DedupResult(
            is_duplicate=False, merge_into=None, similarity=best_sim,
            method="embedding_low",
            decision=f"Similarity {best_sim:.3f} < {similarity_low}. New claim.",
        )
        _log(merge_log, new_text, best_claim, result)
        return result

    # --- Ambiguous range: call disambiguation LLM ---
    try:
        is_same = await _disambiguation_call(new_text, best_claim.text, llm, disambiguation_model)
    except Exception as e:
        logger.warning("disambiguation_failure", extra={"error": str(e)})
        is_same = False

    if is_same:
        result = DedupResult(
            is_duplicate=True, merge_into=best_claim.id, similarity=best_sim,
            method="disambiguation",
            decision=(
                f"Similarity {best_sim:.3f} in ambiguous range; "
                f"LLM judged as duplicate of {best_claim.id}"
            ),
        )
    else:
        result = DedupResult(
            is_duplicate=False, merge_into=None, similarity=best_sim,
            method="disambiguation",
            decision=(
                f"Similarity {best_sim:.3f} in ambiguous range; "
                f"LLM judged as distinct from {best_claim.id}"
            ),
        )
    _log(merge_log, new_text, best_claim, result)
    return result


def _log(
    merge_log: Optional[list[dict]],
    new_text: str,
    best_claim: Optional[Claim],
    result: DedupResult,
) -> None:
    if merge_log is None:
        return
    merge_log.append({
        "new_text": new_text,
        "best_match_id": best_claim.id if best_claim else None,
        "best_match_text": best_claim.text if best_claim else None,
        "similarity": result.similarity,
        "method": result.method,
        "decision": result.decision,
        "is_duplicate": result.is_duplicate,
        "merge_into": result.merge_into,
    })
