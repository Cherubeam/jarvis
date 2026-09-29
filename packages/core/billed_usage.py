"""
Billed usage for streamed OpenRouter calls.

In streaming mode LiteLLM (up to at least 1.103, BerriAI/litellm#36168) drops
OpenRouter's final usage chunk and substitutes a local token estimate with no
cache fields and no cost. A 2026-09-29 probe logged $0.0109 for a request
OpenRouter billed at $0.0169. OpenRouter keeps a billing record per generation id,
free to read, so a turn's estimate is replaced with the billed numbers afterwards.
The record appears ~10-15 s after the stream ends (measured 2026-09-29), too slow to
wait for inside a turn; ConversationLogger reconciles when it saves.
"""

import logging
import time

import httpx

from packages.core.llm_client import TokenUsage

logger = logging.getLogger(__name__)

GENERATION_URL = "https://openrouter.ai/api/v1/generation"
# A 404 means "not published yet"; retries happen only while within the caller's deadline.
_RETRY_DELAYS_S = (0.5, 1.0, 1.5, 2.0)


def _fetch_record(client: httpx.Client, generation_id: str, deadline: float) -> dict[str, object] | None:
    attempt = 0
    while True:
        try:
            response = client.get(GENERATION_URL, params={"id": generation_id})
        except httpx.HTTPError as e:
            logger.warning("Billed usage lookup failed for %s: %s", generation_id, e)
            return None
        if response.status_code == 200:
            data = response.json().get("data")
            return data if isinstance(data, dict) else None
        if response.status_code != 404:
            logger.warning("Billed usage lookup for %s returned HTTP %s", generation_id, response.status_code)
            return None
        delay = _RETRY_DELAYS_S[min(attempt, len(_RETRY_DELAYS_S) - 1)]
        if time.monotonic() + delay > deadline:
            logger.debug("Billed usage for %s not published yet", generation_id)
            return None
        time.sleep(delay)
        attempt += 1


def _int(record: dict[str, object], key: str) -> int:
    value = record.get(key)
    return value if isinstance(value, int) else 0


def fetch_billed_usage(
    generation_ids: list[str],
    api_key: str,
    client: httpx.Client | None = None,
    deadline_s: float = 0.0,
) -> TokenUsage | None:
    """Sum OpenRouter's billed usage for *generation_ids*, or None if any record is missing.

    *deadline_s* bounds the retries while a record isn't published yet; 0 asks once.

    All-or-nothing: a partial sum would be neither the estimate nor the bill.
    Token counts are the provider's native counts, which is what is billed.
    """
    if not generation_ids:
        return None
    deadline = time.monotonic() + deadline_s
    own_client = client is None
    http = client or httpx.Client(headers={"Authorization": f"Bearer {api_key}"}, timeout=5.0)
    try:
        total = TokenUsage(reported_cost=0.0, generation_ids=list(generation_ids))
        for generation_id in generation_ids:
            record = _fetch_record(http, generation_id, deadline)
            cost = record.get("total_cost") if record else None
            if record is None or not isinstance(cost, int | float):
                return None
            prompt, completion = _int(record, "native_tokens_prompt"), _int(record, "native_tokens_completion")
            total.prompt_tokens += prompt
            total.completion_tokens += completion
            total.total_tokens += prompt + completion
            total.cache_read_tokens += _int(record, "native_tokens_cached")
            total.reported_cost = (total.reported_cost or 0.0) + float(cost)
        return total
    finally:
        if own_client:
            http.close()
