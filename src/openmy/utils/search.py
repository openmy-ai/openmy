"""General-purpose fuzzy matching utilities for item resolution."""

from __future__ import annotations

import re
from typing import Any, Callable


def normalize_match_text(text: str) -> str:
    """Normalize text for fuzzy matching by collapsing whitespace and lowercasing."""
    return re.sub(r"\s+", "", str(text or "")).strip().lower()


def score_match(query: str, *candidates: str) -> int:
    """Score how well *query* matches any of *candidates*.

    Returns a positive score on match (higher is better) or -1 on no match.
    """
    normalized_query = normalize_match_text(query)
    if not normalized_query:
        return -1

    best = -1
    for candidate in candidates:
        normalized_candidate = normalize_match_text(candidate)
        if not normalized_candidate:
            continue
        if normalized_query == normalized_candidate:
            return 1000 + len(normalized_candidate)
        if normalized_query in normalized_candidate:
            best = max(best, 500 - max(0, len(normalized_candidate) - len(normalized_query)))
        elif normalized_candidate in normalized_query:
            best = max(best, 100 - max(0, len(normalized_query) - len(normalized_candidate)))
    return best


def resolve_item(items: list[Any], query: str, candidate_getter: Callable) -> Any | None:
    """Find the best-matching item from *items* using fuzzy scoring.

    *candidate_getter* should return a list of candidate strings for each item.
    """
    best_item = None
    best_score = -1
    for item in items:
        s = score_match(query, *candidate_getter(item))
        if s > best_score:
            best_score = s
            best_item = item
    if best_score < 0:
        return None
    return best_item
