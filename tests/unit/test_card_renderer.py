"""Tests for packages.core.card_renderer."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from packages.core.card_renderer import (
    ImageGenerationConfig,
    PatternData,
    build_image_prompt,
    export_image_prompts,
    generate_pattern_image,
    parse_pattern,
    list_vault_patterns,
    render_card_html,
    render_card_back_html,
    _slugify,
    _truncate,
    _extract_intent,
    _extract_sections,
    _clean_wikilinks,
    _category_color,
    CATEGORY_COLORS,
    DEFAULT_COLOR,
)


# ---------------------------------------------------------------------------
# Sample pattern markdown
# ---------------------------------------------------------------------------

FULL_PATTERN = """\
---
created: 2026-03-17
aliases:
  - CoT
tags: collection-patterns
type: pattern
name: Chain-of-Thought
category: Reasoning & Planning
related-patterns:
  - "[[ReAct]]"
  - "[[Reflection]]"
status: draft
---
# Chain-of-Thought

> **Intent:** Make AI reasoning visible by forcing it to show its work.

## Context

A language model is asked a question requiring multiple steps.

## Problem

Models jump to plausible-sounding answers, skipping intermediate reasoning.

## Solution

Instruct the model to reason step by step before producing its final answer.

## Consequences

**Positive:**
- Improves accuracy on multi-step tasks
- Makes reasoning auditable
"""

MINIMAL_PATTERN = """\
---
type: pattern
name: Simple Pattern
---
# Simple Pattern
"""

NO_FRONTMATTER = """\
# Just a heading

Some content.
"""


# ---------------------------------------------------------------------------
# parse_pattern
# ---------------------------------------------------------------------------

class TestParsePattern:
    def test_full_pattern(self):
        p = parse_pattern(FULL_PATTERN)
        assert p.name == "Chain-of-Thought"
        assert p.category == "Reasoning & Planning"
        assert p.intent == "Make AI reasoning visible by forcing it to show its work."
        assert "multiple steps" in p.context
        assert "plausible-sounding" in p.problem
        assert "step by step" in p.solution
        assert "auditable" in p.consequences
        assert p.related_patterns == ["ReAct", "Reflection"]
        assert p.status == "draft"

    def test_minimal_pattern(self):
        p = parse_pattern(MINIMAL_PATTERN)
        assert p.name == "Simple Pattern"
        assert p.category == ""
        assert p.intent == ""
        assert p.problem == ""
        assert p.solution == ""
        assert p.related_patterns == []

    def test_no_frontmatter(self):
        p = parse_pattern(NO_FRONTMATTER)
        assert p.name == ""
        assert p.category == ""

    def test_source_path_preserved(self):
        p = parse_pattern(FULL_PATTERN, source_path="patterns/cot.md")
        assert p.source_path == "patterns/cot.md"

    def test_tags_as_string(self):
        md = "---\ntype: pattern\nname: T\ntags: single-tag\n---\n"
        p = parse_pattern(md)
        assert p.tags == ["single-tag"]

    def test_tags_as_list(self):
        md = "---\ntype: pattern\nname: T\ntags:\n  - a\n  - b\n---\n"
        p = parse_pattern(md)
        assert p.tags == ["a", "b"]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestExtractIntent:
    def test_standard_intent(self):
        body = '> **Intent:** Do something useful.'
        assert _extract_intent(body) == "Do something useful."

    def test_no_intent(self):
        assert _extract_intent("No intent here.") == ""


class TestExtractSections:
    def test_multiple_sections(self):
        body = "## Context\nSome context.\n## Problem\nSome problem."
        sections = _extract_sections(body)
        assert "context" in sections
        assert "problem" in sections
        assert "Some context." in sections["context"]

    def test_empty_body(self):
        assert _extract_sections("") == {}


class TestCleanWikilinks:
    def test_simple_link(self):
        assert _clean_wikilinks(["[[ReAct]]"]) == ["ReAct"]

    def test_aliased_link(self):
        assert _clean_wikilinks(["[[path/to/Note|Display Name]]"]) == ["Display Name"]

    def test_quoted_entries(self):
        assert _clean_wikilinks(['"[[Foo]]"']) == ["Foo"]


class TestTruncate:
    def test_short_text_unchanged(self):
        assert _truncate("Short text.", 100) == "Short text."

    def test_truncation_at_sentence(self):
        text = "First sentence. Second sentence. Third sentence that is very long."
        result = _truncate(text, 40)
        assert result.endswith(".")
        assert len(result) <= 40

    def test_truncation_at_word_boundary(self):
        text = "word " * 100
        result = _truncate(text, 30)
        assert result.endswith("...")
        assert len(result) <= 33  # 30 + "..."


class TestSlugify:
    def test_simple_name(self):
        assert _slugify("Chain-of-Thought") == "chain-of-thought"

    def test_spaces(self):
        assert _slugify("Multi Agent System") == "multi-agent-system"

    def test_special_chars(self):
        assert _slugify("RAG (Retrieval)") == "rag-retrieval"


class TestCategoryColor:
    def test_known_category(self):
        assert _category_color("Reasoning & Planning") == CATEGORY_COLORS["reasoning & planning"]

    def test_unknown_category(self):
        assert _category_color("Unknown Category") == DEFAULT_COLOR

    def test_case_insensitive(self):
        assert _category_color("REASONING & PLANNING") == CATEGORY_COLORS["reasoning & planning"]


# ---------------------------------------------------------------------------
# list_vault_patterns
# ---------------------------------------------------------------------------

class TestListVaultPatterns:
    def test_finds_patterns(self, tmp_path):
        patterns_dir = tmp_path / "patterns"
        patterns_dir.mkdir()
        (patterns_dir / "pattern1.md").write_text(FULL_PATTERN)
        (patterns_dir / "pattern2.md").write_text(MINIMAL_PATTERN)

        result = list_vault_patterns(tmp_path, "patterns")
        assert len(result) == 2

    def test_skips_non_pattern_files(self, tmp_path):
        patterns_dir = tmp_path / "patterns"
        patterns_dir.mkdir()
        (patterns_dir / "pattern1.md").write_text(FULL_PATTERN)
        (patterns_dir / "not_a_pattern.md").write_text(NO_FRONTMATTER)

        result = list_vault_patterns(tmp_path, "patterns")
        assert len(result) == 1
        assert result[0].name == "Chain-of-Thought"

    def test_skips_index_files(self, tmp_path):
        patterns_dir = tmp_path / "patterns"
        patterns_dir.mkdir()
        (patterns_dir / "_overview.md").write_text(FULL_PATTERN)
        (patterns_dir / "pattern1.md").write_text(FULL_PATTERN)

        result = list_vault_patterns(tmp_path, "patterns")
        assert len(result) == 1

    def test_empty_dir(self, tmp_path):
        patterns_dir = tmp_path / "patterns"
        patterns_dir.mkdir()
        assert list_vault_patterns(tmp_path, "patterns") == []

    def test_missing_dir(self, tmp_path):
        assert list_vault_patterns(tmp_path, "nonexistent") == []

    def test_recursive_scan(self, tmp_path):
        sub = tmp_path / "patterns" / "subdir"
        sub.mkdir(parents=True)
        (sub / "pattern.md").write_text(FULL_PATTERN)

        result = list_vault_patterns(tmp_path, "patterns")
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

class TestRenderCardHtml:
    def test_contains_pattern_name(self):
        p = parse_pattern(FULL_PATTERN)
        html = render_card_html(p)
        assert "Chain-of-Thought" in html

    def test_contains_category(self):
        p = parse_pattern(FULL_PATTERN)
        html = render_card_html(p)
        assert "Reasoning &amp; Planning" in html or "Reasoning & Planning" in html

    def test_contains_intent(self):
        p = parse_pattern(FULL_PATTERN)
        html = render_card_html(p)
        assert "show its work" in html

    def test_image_placeholder_when_no_image(self):
        p = parse_pattern(FULL_PATTERN)
        html = render_card_html(p)
        assert "card-image-placeholder" in html
        assert "<img" not in html

    def test_image_included_when_provided(self):
        p = parse_pattern(FULL_PATTERN)
        html = render_card_html(p, image_path="/tmp/test.png")
        assert '<img' in html
        assert "/tmp/test.png" in html

    def test_missing_sections_omitted(self):
        p = parse_pattern(MINIMAL_PATTERN)
        html = render_card_html(p)
        assert "Problem" not in html
        assert "Solution" not in html

    def test_related_patterns_shown(self):
        p = parse_pattern(FULL_PATTERN)
        html = render_card_html(p)
        assert "ReAct" in html
        assert "Reflection" in html


class TestRenderCardBack:
    def test_card_back_html(self):
        html = render_card_back_html()
        assert "Pattern" in html
        assert "Language" in html
        assert "card-back" in html


# ---------------------------------------------------------------------------
# Phase 2: Image prompt generation
# ---------------------------------------------------------------------------

class TestBuildImagePrompt:
    def test_includes_pattern_name(self):
        p = parse_pattern(FULL_PATTERN)
        prompt = build_image_prompt(p)
        assert "Chain-of-Thought" in prompt

    def test_includes_intent(self):
        p = parse_pattern(FULL_PATTERN)
        prompt = build_image_prompt(p)
        assert "show its work" in prompt

    def test_no_text_instruction(self):
        p = parse_pattern(FULL_PATTERN)
        prompt = build_image_prompt(p)
        assert "No text" in prompt

    def test_uses_category_palette(self):
        p = parse_pattern(FULL_PATTERN)
        prompt = build_image_prompt(p)
        # "Reasoning & Planning" maps to "deep blues and silver"
        assert "deep blues" in prompt

    def test_fallback_palette_for_unknown_category(self):
        p = PatternData(name="Test", category="Unknown Category")
        prompt = build_image_prompt(p)
        assert "slate blue" in prompt

    def test_uses_problem_when_no_intent(self):
        p = PatternData(name="Test", problem="Something is broken.")
        prompt = build_image_prompt(p)
        assert "broken" in prompt

    def test_uses_name_when_no_intent_or_problem(self):
        p = PatternData(name="Bare Pattern")
        prompt = build_image_prompt(p)
        assert "Bare Pattern" in prompt


class TestExportImagePrompts:
    def test_writes_file(self, tmp_path):
        patterns = [parse_pattern(FULL_PATTERN)]
        output = tmp_path / "prompts.md"
        result = export_image_prompts(patterns, output)
        assert result == output
        assert output.is_file()

    def test_contains_pattern_heading(self, tmp_path):
        patterns = [parse_pattern(FULL_PATTERN)]
        output = tmp_path / "prompts.md"
        export_image_prompts(patterns, output)
        content = output.read_text()
        assert "## Chain-of-Thought" in content

    def test_contains_slug(self, tmp_path):
        patterns = [parse_pattern(FULL_PATTERN)]
        output = tmp_path / "prompts.md"
        export_image_prompts(patterns, output)
        content = output.read_text()
        assert "chain-of-thought" in content

    def test_contains_prompt_text(self, tmp_path):
        patterns = [parse_pattern(FULL_PATTERN)]
        output = tmp_path / "prompts.md"
        export_image_prompts(patterns, output)
        content = output.read_text()
        assert "Abstract conceptual illustration" in content

    def test_skips_nameless_patterns(self, tmp_path):
        patterns = [PatternData(name=""), PatternData(name="Valid")]
        output = tmp_path / "prompts.md"
        export_image_prompts(patterns, output)
        content = output.read_text()
        assert "## Valid" in content
        assert content.count("## ") == 1  # only one pattern heading

    def test_multiple_patterns(self, tmp_path):
        patterns = [
            parse_pattern(FULL_PATTERN),
            parse_pattern(MINIMAL_PATTERN),
        ]
        output = tmp_path / "prompts.md"
        export_image_prompts(patterns, output)
        content = output.read_text()
        assert "Chain-of-Thought" in content
        assert "Simple Pattern" in content


# ---------------------------------------------------------------------------
# Phase 2: ImageGenerationConfig
# ---------------------------------------------------------------------------

class TestImageGenerationConfig:
    def test_defaults(self):
        cfg = ImageGenerationConfig()
        assert cfg.enabled is False
        assert "imagen" in cfg.model
        assert cfg.max_images_per_run == 10

    def test_from_dict_empty(self):
        cfg = ImageGenerationConfig.from_dict({})
        assert cfg.enabled is False

    def test_from_dict_enabled(self):
        d = {"image_generation": {"enabled": True, "model": "gemini/test-model", "size": "512x512"}}
        cfg = ImageGenerationConfig.from_dict(d)
        assert cfg.enabled is True
        assert cfg.model == "gemini/test-model"
        assert cfg.size == "512x512"


# ---------------------------------------------------------------------------
# Phase 2: API image generation (mocked)
# ---------------------------------------------------------------------------

class TestGeneratePatternImage:
    def test_raises_when_disabled(self, tmp_path):
        p = parse_pattern(FULL_PATTERN)
        cfg = ImageGenerationConfig(enabled=False)
        with pytest.raises(RuntimeError, match="disabled"):
            generate_pattern_image(p, tmp_path, cfg)

    def test_skips_when_cached(self, tmp_path):
        p = parse_pattern(FULL_PATTERN)
        cfg = ImageGenerationConfig(enabled=True)
        # Pre-create the cached image
        (tmp_path / "chain-of-thought.png").write_bytes(b"fake image")

        result = generate_pattern_image(p, tmp_path, cfg)
        assert result == tmp_path / "chain-of-thought.png"

    def test_force_regenerates(self, tmp_path):
        p = parse_pattern(FULL_PATTERN)
        cfg = ImageGenerationConfig(enabled=True)
        (tmp_path / "chain-of-thought.png").write_bytes(b"old image")

        mock_image = MagicMock()
        mock_image.b64_json = None
        mock_image.url = "https://example.com/image.png"
        mock_response = MagicMock()
        mock_response.data = [mock_image]

        mock_httpx_response = MagicMock()
        mock_httpx_response.content = b"new image data"

        with patch("litellm.image_generation", return_value=mock_response), \
             patch("httpx.get", return_value=mock_httpx_response):
            result = generate_pattern_image(p, tmp_path, cfg, force=True)

        assert result == tmp_path / "chain-of-thought.png"
        assert (tmp_path / "chain-of-thought.png").read_bytes() == b"new image data"

    def test_handles_b64_response(self, tmp_path):
        import base64
        p = parse_pattern(FULL_PATTERN)
        cfg = ImageGenerationConfig(enabled=True)

        fake_b64 = base64.b64encode(b"png image bytes").decode()
        mock_image = MagicMock()
        mock_image.b64_json = fake_b64
        mock_image.url = None
        mock_response = MagicMock()
        mock_response.data = [mock_image]

        with patch("litellm.image_generation", return_value=mock_response):
            result = generate_pattern_image(p, tmp_path, cfg)

        assert result == tmp_path / "chain-of-thought.png"
        assert (tmp_path / "chain-of-thought.png").read_bytes() == b"png image bytes"
