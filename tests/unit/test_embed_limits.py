"""Token-based embedding limits (packages/core/rag/embed_limits.py)."""

import pytest

from packages.core.rag.embed_limits import (
    CHUNK_OVERLAP_TOKENS,
    MAX_EMBED_TOKENS,
    chunk_by_tokens,
    count_tokens,
    truncate_to_tokens,
)
from packages.core.rag.embed_limits import encoding as enc

DENSE = '{"a":1,'  # repeated: 7 chars per 4 tokens, far denser than the old 3-chars-per-token rule


@pytest.mark.unit
class TestLimits:
    def test_limit_stays_below_the_model_maximum(self):
        assert MAX_EMBED_TOKENS == 8_000
        assert MAX_EMBED_TOKENS < 8_191
        assert CHUNK_OVERLAP_TOKENS == 800

    def test_count_tokens_uses_the_model_tokenizer(self):
        assert count_tokens("Hallo Welt") == 2
        assert count_tokens(DENSE * 10) == 41

    def test_special_token_text_is_counted_not_rejected(self):
        assert count_tokens("<|endoftext|>") > 1


@pytest.mark.unit
class TestChunkByTokens:
    def test_short_text_returned_unchanged(self):
        assert chunk_by_tokens("Short text") == ["Short text"]

    def test_text_exactly_at_limit_is_one_chunk(self):
        text = enc.decode(enc.encode(DENSE * 3000)[:MAX_EMBED_TOKENS])
        assert count_tokens(text) == MAX_EMBED_TOKENS
        assert chunk_by_tokens(text) == [text]

    def test_dense_text_under_old_char_limit_is_still_split(self):
        """Regression: 21,000 chars passed the old 24,000-char limit but is ~12,000 tokens."""
        text = DENSE * 3000
        assert len(text) < 24_000
        chunks = chunk_by_tokens(text)
        assert len(chunks) == 2
        assert count_tokens(text) == 12_001
        assert [count_tokens(c) for c in chunks] == [8_000, 12_001 - 7_200]

    def test_every_chunk_fits_and_overlaps(self):
        text = DENSE * 6000  # 24,000 tokens
        chunks = chunk_by_tokens(text)
        assert all(count_tokens(c) <= MAX_EMBED_TOKENS for c in chunks)
        tail = enc.decode(enc.encode(chunks[0])[-CHUNK_OVERLAP_TOKENS:])
        assert chunks[1].startswith(tail)

    def test_no_text_lost(self):
        text = "".join(f"line {i}\n" for i in range(9000))
        chunks = chunk_by_tokens(text)
        assert chunks[0].startswith("line 0\n")
        assert chunks[-1].endswith("line 8999\n")
        step = MAX_EMBED_TOKENS - CHUNK_OVERLAP_TOKENS
        rebuilt = []
        for i, chunk in enumerate(chunks):
            tokens = enc.encode(chunk)
            rebuilt.extend(tokens if i == 0 else tokens[CHUNK_OVERLAP_TOKENS:])
        assert enc.decode(rebuilt) == text
        assert len(chunks) == -(-(count_tokens(text) - CHUNK_OVERLAP_TOKENS) // step)

    def test_custom_window(self):
        text = DENSE * 5  # 21 tokens
        chunks = chunk_by_tokens(text, max_tokens=8, overlap=2)
        # windows start at tokens 0, 6, 12, 18
        assert [count_tokens(c) for c in chunks] == [8, 8, 8, 3]
        assert chunks[0] == '{"a":1,{"a":1'


@pytest.mark.unit
class TestTruncateToTokens:
    def test_short_text_unchanged(self):
        assert truncate_to_tokens("query") == "query"

    def test_long_text_cut_to_limit(self):
        text = DENSE * 2500  # 10,000 tokens
        cut = truncate_to_tokens(text)
        assert count_tokens(cut) == MAX_EMBED_TOKENS
        assert text.startswith(cut)

    def test_custom_limit(self):
        assert truncate_to_tokens(DENSE * 3, max_tokens=4) == '{"a":1'
