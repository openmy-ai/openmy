from __future__ import annotations

import time
from typing import TypeVar

T = TypeVar("T")


def is_retryable_llm_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "429" in message
        or "503" in message
        or "resource exhausted" in message
        or "temporarily unavailable" in message
    )


def retry_llm_call(
    fn,
    *,
    max_attempts: int = 3,
    backoff_base: int = 2,
    is_retryable=is_retryable_llm_error,
):
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as exc:
            last_error = exc
            if attempt == max_attempts or not is_retryable(exc):
                raise
            time.sleep(backoff_base ** (attempt - 1))
    if last_error is not None:
        raise last_error
