"""Token limits for the embedding model, measured with its own tokenizer.

``text-embedding-3-small`` rejects any input over 8,191 tokens. Counting
characters (the old ~3 chars/token rule) under-counts dense text such as code,
JSON or German, so a 24,000-character chunk could exceed the limit and fail the
whole indexing run. ``cl100k_base`` is that model's tokenizer; LiteLLM ships it
inside the package, so this works offline.
"""

from litellm.litellm_core_utils.default_encoding import encoding

MAX_EMBED_TOKENS = 8_000  # model limit is 8,191; keep a margin
CHUNK_OVERLAP_TOKENS = 800  # ~10 % of MAX_EMBED_TOKENS


def count_tokens(text: str) -> int:
    """Number of embedding-model tokens in *text*."""
    return len(encoding.encode(text, disallowed_special=()))


def chunk_by_tokens(text: str, max_tokens: int = MAX_EMBED_TOKENS, overlap: int = CHUNK_OVERLAP_TOKENS) -> list[str]:
    """Split *text* into overlapping windows of at most *max_tokens* tokens.

    Text within the limit is returned unchanged as a single-element list.
    """
    tokens = encoding.encode(text, disallowed_special=())
    if len(tokens) <= max_tokens:
        return [text]

    step = max_tokens - overlap
    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        chunks.append(encoding.decode(tokens[start : start + max_tokens]))
        if start + max_tokens >= len(tokens):
            break
        start += step
    return chunks


def truncate_to_tokens(text: str, max_tokens: int = MAX_EMBED_TOKENS) -> str:
    """Cut *text* to at most *max_tokens* tokens (used for search queries)."""
    tokens = encoding.encode(text, disallowed_special=())
    if len(tokens) <= max_tokens:
        return text
    return encoding.decode(tokens[:max_tokens])
