"""Tests for old_text -> new_text edit application (packages/core/tools/text_edits.py)."""

import pytest

from packages.core.tools.text_edits import EditError, apply_edits

pytestmark = pytest.mark.unit


def test_replaces_single_occurrence():
    assert apply_edits("a b c", [{"old_text": "b", "new_text": "B"}]) == "a B c"


def test_edits_apply_in_order_on_the_updated_text():
    edits = [{"old_text": "one", "new_text": "two"}, {"old_text": "two two", "new_text": "done"}]
    assert apply_edits("one two", edits) == "done"


def test_empty_new_text_deletes():
    assert apply_edits("keep drop keep", [{"old_text": " drop", "new_text": ""}]) == "keep keep"


def test_insert_by_repeating_the_anchor():
    content = "> [!LINKEDIN] LinkedIn Post\n> (content will be inserted here)\n"
    edits = [{"old_text": "> (content will be inserted here)", "new_text": "> Post 1"}]
    assert apply_edits(content, edits) == "> [!LINKEDIN] LinkedIn Post\n> Post 1\n"


def test_text_outside_the_edit_is_untouched_byte_for_byte():
    # The regression: a full-file rewrite turned these no-break spaces into spaces.
    content = "see this\u00a0[work](u)\n\n> (placeholder)\n\n*Last updated:\u00a0`x`*"
    result = apply_edits(content, [{"old_text": "(placeholder)", "new_text": "Post"}])
    assert result == "see this\u00a0[work](u)\n\n> Post\n\n*Last updated:\u00a0`x`*"


@pytest.mark.parametrize(
    ("file_text", "typed"),
    [
        ("see this\u00a0[work]", "see this [work]"),  # no-break space typed as space
        ("decade ago\u2060]", "decade ago]"),  # word joiner dropped
        ("\u201eAI is going rogue\u201c headline", '"AI is going rogue" headline'),  # German quotes
        ("it\u2019s here", "it's here"),
    ],
)
def test_matches_when_the_model_normalises_invisible_or_typographic_chars(file_text, typed):
    content = f"before {file_text} after"
    assert apply_edits(content, [{"old_text": typed, "new_text": "X"}]) == "before X after"


def test_exact_match_preferred_over_folded_match():
    # "a b" occurs once exactly; the folded view would also match "a\u00a0b".
    content = "a\u00a0b | a b"
    assert apply_edits(content, [{"old_text": "a b", "new_text": "Z"}]) == "a\u00a0b | Z"


def test_not_found_raises_and_names_the_edit():
    with pytest.raises(EditError, match=r"edit 2: old_text not found"):
        apply_edits("abc", [{"old_text": "a", "new_text": "A"}, {"old_text": "zzz", "new_text": "y"}])


def test_ambiguous_match_raises_with_count():
    with pytest.raises(EditError, match=r"edit 1: old_text occurs 2 times"):
        apply_edits("x x", [{"old_text": "x", "new_text": "y"}])


def test_ambiguous_folded_match_raises():
    with pytest.raises(EditError, match="occurs 2 times"):
        apply_edits("a\u00a0b a\u00a0b", [{"old_text": "a b", "new_text": "y"}])


@pytest.mark.parametrize("old_text", ["", "\u2060"])
def test_empty_old_text_rejected(old_text):
    with pytest.raises(EditError):
        apply_edits("abc", [{"old_text": old_text, "new_text": "y"}])


def test_no_edits_rejected():
    with pytest.raises(EditError, match="no edits"):
        apply_edits("abc", [])
