"""
Unit tests for card_generator_tools — the pattern card tool factory.

Covers factory structure, per-tool parameter schemas, happy-path execution,
error paths, default arguments, and closure bindings. All external calls
(vault reads, WeasyPrint, image gen) are mocked.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from packages.core.card_renderer import ImageGenerationConfig, PatternData
from packages.core.tools.base import ToolDefinition
from packages.core.tools.card_generator_tools import make_card_generator_tools
from packages.integrations.obsidian.vault import VaultConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_vault_config(vault_path="/fake/vault"):
    cfg = Mock(spec=VaultConfig)
    cfg.vault_path = Path(vault_path)
    return cfg


def _make_pattern(name="Test Pattern", category="Strategy", source_path="01/test.md"):
    return PatternData(name=name, category=category, source_path=source_path)


def _make_tools(**kwargs):
    """Create tools with sane defaults — returns (tools, output_dir)."""
    vault_config = kwargs.get("vault_config", _make_vault_config())
    patterns_dir = kwargs.get("patterns_dir", "01 – Patterns")
    output_dir = kwargs.get("output_dir", Path("/tmp/test-cards"))
    image_config = kwargs.get("image_config")
    tools = make_card_generator_tools(vault_config, patterns_dir, output_dir, image_config)
    return tools, output_dir


def _get_tool(tools, name):
    return next(t for t in tools if t.name == name)


# ---------------------------------------------------------------------------
# Factory structure
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMakeCardGeneratorTools:
    def test_returns_three_tools(self):
        tools, _ = _make_tools()
        assert len(tools) == 3

    def test_all_are_tool_definitions(self):
        tools, _ = _make_tools()
        for tool in tools:
            assert isinstance(tool, ToolDefinition)

    def test_tool_names(self):
        tools, _ = _make_tools()
        names = [t.name for t in tools]
        assert names == ["generate_card", "generate_deck", "generate_image_prompts"]


# ---------------------------------------------------------------------------
# generate_card — schema + execution
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGenerateCard:
    def test_schema_properties(self):
        tools, _ = _make_tools()
        tool = _get_tool(tools, "generate_card")
        props = tool.parameters["properties"]
        assert set(props.keys()) == {"pattern_name", "include_image"}
        assert props["pattern_name"]["type"] == "string"
        assert props["include_image"]["type"] == "boolean"
        assert tool.parameters["required"] == ["pattern_name"]
        assert tool.parameters["type"] == "object"

    @patch("packages.core.tools.card_generator_tools._slugify", return_value="test-pattern")
    @patch("packages.core.tools.card_generator_tools.generate_card_files")
    @patch("packages.core.tools.card_generator_tools.list_vault_patterns")
    def test_happy_path(self, mock_list, mock_gen, mock_slug):
        pattern = _make_pattern()
        mock_list.return_value = [pattern]
        mock_gen.return_value = {"png": Path("/out/test.png"), "html": Path("/out/test.html")}

        tools, _ = _make_tools()
        tool = _get_tool(tools, "generate_card")
        result = tool.execute(pattern_name="Test Pattern")

        assert "Generated card for 'Test Pattern'" in result
        assert "Strategy" in result
        assert "/out/test.png" in result
        assert "/out/test.html" in result
        mock_gen.assert_called_once()

    @patch("packages.core.tools.card_generator_tools.list_vault_patterns")
    def test_pattern_not_found(self, mock_list):
        mock_list.return_value = [_make_pattern(name="Other")]

        tools, _ = _make_tools()
        tool = _get_tool(tools, "generate_card")
        result = tool.execute(pattern_name="Nonexistent")

        assert result.startswith("Error:")
        assert "Nonexistent" in result
        assert "Other" in result

    @patch("packages.core.tools.card_generator_tools.list_vault_patterns")
    def test_pattern_no_name_in_frontmatter(self, mock_list):
        mock_list.return_value = [_make_pattern(name="")]

        tools, _ = _make_tools()
        tool = _get_tool(tools, "generate_card")
        # Pattern with empty name is found via case-insensitive match of ""==""
        result = tool.execute(pattern_name="")

        assert result.startswith("Error:")
        assert "no name in frontmatter" in result

    @patch("packages.core.tools.card_generator_tools.list_vault_patterns")
    def test_include_image_disabled_returns_guidance(self, mock_list):
        mock_list.return_value = [_make_pattern()]

        tools, _ = _make_tools(image_config=ImageGenerationConfig(enabled=False))
        tool = _get_tool(tools, "generate_card")
        result = tool.execute(pattern_name="Test Pattern", include_image=True)

        assert "disabled" in result.lower()
        assert "generate_image_prompts" in result

    @patch("packages.core.tools.card_generator_tools.generate_pattern_image")
    @patch("packages.core.tools.card_generator_tools._slugify", return_value="test-pattern")
    @patch("packages.core.tools.card_generator_tools.generate_card_files")
    @patch("packages.core.tools.card_generator_tools.list_vault_patterns")
    def test_include_image_enabled_calls_api(self, mock_list, mock_gen, mock_slug, mock_img):
        pattern = _make_pattern()
        mock_list.return_value = [pattern]
        mock_gen.return_value = {"png": Path("/out/test.png"), "html": Path("/out/test.html")}

        img_cfg = ImageGenerationConfig(enabled=True)
        tools, _ = _make_tools(image_config=img_cfg)
        tool = _get_tool(tools, "generate_card")
        tool.execute(pattern_name="Test Pattern", include_image=True)

        mock_img.assert_called_once()

    @patch("packages.core.tools.card_generator_tools.generate_pattern_image")
    @patch("packages.core.tools.card_generator_tools.list_vault_patterns")
    def test_image_generation_exception(self, mock_list, mock_img):
        mock_list.return_value = [_make_pattern()]
        mock_img.side_effect = RuntimeError("API timeout")

        img_cfg = ImageGenerationConfig(enabled=True)
        tools, _ = _make_tools(image_config=img_cfg)
        tool = _get_tool(tools, "generate_card")
        result = tool.execute(pattern_name="Test Pattern", include_image=True)

        assert result.startswith("Error generating image")
        assert "API timeout" in result

    @patch("packages.core.tools.card_generator_tools._slugify", return_value="test-pattern")
    @patch("packages.core.tools.card_generator_tools.generate_card_files")
    @patch("packages.core.tools.card_generator_tools.list_vault_patterns")
    def test_card_generation_exception(self, mock_list, mock_gen, mock_slug):
        mock_list.return_value = [_make_pattern()]
        mock_gen.side_effect = OSError("Disk full")

        tools, _ = _make_tools()
        tool = _get_tool(tools, "generate_card")
        result = tool.execute(pattern_name="Test Pattern")

        assert result.startswith("Error generating card")
        assert "Disk full" in result

    @patch("packages.core.tools.card_generator_tools.list_vault_patterns")
    def test_default_include_image_is_false(self, mock_list):
        """Calling without include_image exercises the default=False path."""
        mock_list.return_value = []

        tools, _ = _make_tools()
        tool = _get_tool(tools, "generate_card")
        # Pattern not found — but we reach _find_pattern, not the image branch
        result = tool.execute(pattern_name="Whatever")
        assert result.startswith("Error:")


# ---------------------------------------------------------------------------
# generate_deck — schema + execution
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGenerateDeck:
    def test_schema_properties(self):
        tools, _ = _make_tools()
        tool = _get_tool(tools, "generate_deck")
        props = tool.parameters["properties"]
        assert set(props.keys()) == {"category", "include_images"}
        assert props["category"]["type"] == "string"
        assert props["include_images"]["type"] == "boolean"
        assert tool.parameters["required"] == []
        assert tool.parameters["type"] == "object"

    @patch("packages.core.tools.card_generator_tools.generate_card_files")
    @patch("packages.core.tools.card_generator_tools.list_vault_patterns")
    def test_happy_path_all_patterns(self, mock_list, mock_gen):
        mock_list.return_value = [
            _make_pattern("Alpha", "Strategy"),
            _make_pattern("Beta", "Design"),
        ]
        mock_gen.return_value = {"png": Path("/out/x.png"), "html": Path("/out/x.html")}

        tools, output_dir = _make_tools()
        tool = _get_tool(tools, "generate_deck")
        result = tool.execute()

        assert "Generated 2 card(s)" in result
        assert "Alpha (Strategy)" in result
        assert "Beta (Design)" in result
        assert mock_gen.call_count == 2

    @patch("packages.core.tools.card_generator_tools.generate_card_files")
    @patch("packages.core.tools.card_generator_tools.list_vault_patterns")
    def test_category_filter(self, mock_list, mock_gen):
        mock_list.return_value = [
            _make_pattern("Alpha", "Strategy"),
            _make_pattern("Beta", "Design"),
        ]
        mock_gen.return_value = {"png": Path("/out/x.png"), "html": Path("/out/x.html")}

        tools, _ = _make_tools()
        tool = _get_tool(tools, "generate_deck")
        result = tool.execute(category="Design")

        assert "Generated 1 card(s)" in result
        assert "Beta (Design)" in result
        assert "Alpha" not in result

    @patch("packages.core.tools.card_generator_tools.list_vault_patterns")
    def test_no_patterns_found(self, mock_list):
        mock_list.return_value = []

        tools, _ = _make_tools()
        tool = _get_tool(tools, "generate_deck")
        result = tool.execute()

        assert result == "No patterns found in the vault."

    @patch("packages.core.tools.card_generator_tools.list_vault_patterns")
    def test_no_patterns_in_category(self, mock_list):
        mock_list.return_value = [_make_pattern("Alpha", "Strategy")]

        tools, _ = _make_tools()
        tool = _get_tool(tools, "generate_deck")
        result = tool.execute(category="Nonexistent")

        assert "No patterns found in category 'Nonexistent'" in result

    @patch("packages.core.tools.card_generator_tools.list_vault_patterns")
    def test_include_images_disabled_returns_guidance(self, mock_list):
        mock_list.return_value = [_make_pattern()]

        tools, _ = _make_tools(image_config=ImageGenerationConfig(enabled=False))
        tool = _get_tool(tools, "generate_deck")
        result = tool.execute(include_images=True)

        assert "disabled" in result.lower()
        assert "generate_image_prompts" in result

    @patch("packages.core.tools.card_generator_tools.generate_card_files")
    @patch("packages.core.tools.card_generator_tools.list_vault_patterns")
    def test_generation_errors_reported(self, mock_list, mock_gen):
        mock_list.return_value = [
            _make_pattern("Good"),
            _make_pattern("Bad"),
        ]
        mock_gen.side_effect = [
            {"png": Path("/out/good.png"), "html": Path("/out/good.html")},
            OSError("render failed"),
        ]

        tools, _ = _make_tools()
        tool = _get_tool(tools, "generate_deck")
        result = tool.execute()

        assert "Generated 1 card(s)" in result
        assert "1 error(s)" in result
        assert "Bad: render failed" in result

    @patch("packages.core.tools.card_generator_tools.generate_card_files")
    @patch("packages.core.tools.card_generator_tools.list_vault_patterns")
    def test_patterns_without_name_skipped(self, mock_list, mock_gen):
        mock_list.return_value = [
            _make_pattern("Good"),
            _make_pattern("", source_path="unnamed.md"),
        ]
        mock_gen.return_value = {"png": Path("/out/x.png"), "html": Path("/out/x.html")}

        tools, _ = _make_tools()
        tool = _get_tool(tools, "generate_deck")
        result = tool.execute()

        assert "Generated 1 card(s)" in result
        assert "Skipped: unnamed.md (no name)" in result


# ---------------------------------------------------------------------------
# generate_image_prompts — schema + execution
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGenerateImagePrompts:
    def test_schema_properties(self):
        tools, _ = _make_tools()
        tool = _get_tool(tools, "generate_image_prompts")
        props = tool.parameters["properties"]
        assert set(props.keys()) == {"pattern_name", "category"}
        assert props["pattern_name"]["type"] == "string"
        assert props["category"]["type"] == "string"
        assert tool.parameters["required"] == []
        assert tool.parameters["type"] == "object"

    @patch("packages.core.tools.card_generator_tools.export_image_prompts")
    @patch("packages.core.tools.card_generator_tools.list_vault_patterns")
    def test_single_pattern(self, mock_list, mock_export):
        pattern = _make_pattern()
        mock_list.return_value = [pattern]

        tools, output_dir = _make_tools()
        tool = _get_tool(tools, "generate_image_prompts")
        result = tool.execute(pattern_name="Test Pattern")

        assert "1 pattern(s)" in result
        assert str(output_dir / "image-prompts.md") in result
        mock_export.assert_called_once_with([pattern], output_dir / "image-prompts.md")

    @patch("packages.core.tools.card_generator_tools.export_image_prompts")
    @patch("packages.core.tools.card_generator_tools.list_vault_patterns")
    def test_all_patterns(self, mock_list, mock_export):
        patterns = [_make_pattern("A"), _make_pattern("B")]
        mock_list.return_value = patterns

        tools, _ = _make_tools()
        tool = _get_tool(tools, "generate_image_prompts")
        result = tool.execute()

        assert "2 pattern(s)" in result
        mock_export.assert_called_once()

    @patch("packages.core.tools.card_generator_tools.export_image_prompts")
    @patch("packages.core.tools.card_generator_tools.list_vault_patterns")
    def test_category_filter(self, mock_list, mock_export):
        mock_list.return_value = [
            _make_pattern("A", "Strategy"),
            _make_pattern("B", "Design"),
        ]

        tools, _ = _make_tools()
        tool = _get_tool(tools, "generate_image_prompts")
        result = tool.execute(category="Design")

        assert "1 pattern(s)" in result
        # Only the Design pattern is passed to export
        args = mock_export.call_args[0]
        assert len(args[0]) == 1
        assert args[0][0].name == "B"

    @patch("packages.core.tools.card_generator_tools.list_vault_patterns")
    def test_pattern_not_found(self, mock_list):
        mock_list.return_value = []

        tools, _ = _make_tools()
        tool = _get_tool(tools, "generate_image_prompts")
        result = tool.execute(pattern_name="Ghost")

        assert result.startswith("Error:")
        assert "Ghost" in result

    @patch("packages.core.tools.card_generator_tools.list_vault_patterns")
    def test_no_patterns_in_vault(self, mock_list):
        mock_list.return_value = []

        tools, _ = _make_tools()
        tool = _get_tool(tools, "generate_image_prompts")
        result = tool.execute()

        assert result == "No patterns found in the vault."

    @patch("packages.core.tools.card_generator_tools.list_vault_patterns")
    def test_no_patterns_in_category(self, mock_list):
        mock_list.return_value = [_make_pattern("A", "Strategy")]

        tools, _ = _make_tools()
        tool = _get_tool(tools, "generate_image_prompts")
        result = tool.execute(category="Missing")

        assert "No patterns found in category 'Missing'" in result

    @patch("packages.core.tools.card_generator_tools.export_image_prompts")
    @patch("packages.core.tools.card_generator_tools.list_vault_patterns")
    def test_output_mentions_copy_instructions(self, mock_list, mock_export):
        mock_list.return_value = [_make_pattern()]

        tools, _ = _make_tools()
        tool = _get_tool(tools, "generate_image_prompts")
        result = tool.execute(pattern_name="Test Pattern")

        assert "Copy each prompt" in result
        assert "images/{slug}.png" in result
