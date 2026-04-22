"""
Pattern card generator tools for JARVIS.

Factory function that creates tools for generating visual pattern cards
from Obsidian vault notes. Uses the closure pattern to capture config.
"""

from pathlib import Path

from packages.core.card_renderer import (
    ImageGenerationConfig,
    _slugify,
    export_image_prompts,
    generate_card_files,
    generate_pattern_image,
    list_vault_patterns,
)
from packages.core.tools.base import ToolDefinition
from packages.integrations.obsidian.vault import VaultConfig


def make_card_generator_tools(
    vault_config: VaultConfig,
    patterns_dir: str,
    output_dir: Path,
    image_config: ImageGenerationConfig | None = None,
) -> list[ToolDefinition]:
    """Create pattern card generator tools.

    Args:
        vault_config: Vault configuration with path validation.
        patterns_dir: Patterns directory relative to vault root.
        output_dir: Directory for generated card files (absolute).
        image_config: Optional image generation configuration.

    Returns:
        List of 3 ToolDefinitions: generate_card, generate_deck, generate_image_prompts.
    """
    images_dir = output_dir / "images"
    img_cfg = image_config or ImageGenerationConfig()

    def _find_pattern(pattern_name: str):
        """Find a pattern by name (case-insensitive). Returns (pattern, error_msg)."""
        patterns = list_vault_patterns(vault_config.vault_path, patterns_dir)
        for p in patterns:
            if p.name.lower() == pattern_name.lower():
                return p, None
        available = ", ".join(p.name for p in patterns) if patterns else "(none found)"
        return None, f"Error: Pattern '{pattern_name}' not found. Available: {available}"

    # --- generate_card ---

    def _generate_card(pattern_name: str, include_image: bool = False) -> str:
        match, err = _find_pattern(pattern_name)
        if err:
            return err

        if not match.name:
            return f"Error: Pattern at '{match.source_path}' has no name in frontmatter."

        # Optionally generate image via API first
        if include_image and img_cfg.enabled:
            try:
                generate_pattern_image(match, images_dir, img_cfg)
            except Exception as e:
                return f"Error generating image for '{match.name}': {e}"
        elif include_image and not img_cfg.enabled:
            return (
                "Image generation via API is disabled. Either:\n"
                "1. Use `generate_image_prompts` to get prompts for manual image creation, or\n"
                "2. Enable API generation in config: pattern_cards.image_generation.enabled: true"
            )

        try:
            files = generate_card_files(match, output_dir, images_dir=images_dir)
            slug = _slugify(match.name)
            has_image = any((images_dir / f"{slug}{ext}").is_file() for ext in (".png", ".jpg", ".jpeg", ".webp"))
            image_status = "with image" if has_image else "without image (placeholder used)"
            return (
                f"Generated card for '{match.name}' ({match.category}) {image_status}:\n"
                f"  PNG: {files['png']}\n"
                f"  HTML: {files['html']}"
            )
        except Exception as e:
            return f"Error generating card for '{pattern_name}': {e}"

    generate_card_tool = ToolDefinition(
        name="generate_card",
        description=(
            "Generate a visual pattern card (PNG + HTML) from an Obsidian pattern note. "  # pragma: no mutate
            "Set include_image=true to generate an AI image via API (requires config). "  # pragma: no mutate
            "If images exist in data/pattern-cards/images/, they are used automatically."  # pragma: no mutate
        ),
        parameters={
            "type": "object",
            "properties": {
                "pattern_name": {
                    "type": "string",
                    "description": "The name of the pattern to generate a card for.",  # pragma: no mutate
                },
                "include_image": {
                    "type": "boolean",
                    "description": "If true, generate an AI image via API before rendering the card. Requires image generation to be enabled in config.",  # pragma: no mutate
                },
            },
            "required": ["pattern_name"],
        },
        execute=_generate_card,
    )

    # --- generate_deck ---

    def _generate_deck(category: str = "", include_images: bool = False) -> str:
        patterns = list_vault_patterns(vault_config.vault_path, patterns_dir)

        if not patterns:
            return "No patterns found in the vault."

        if category:
            patterns = [p for p in patterns if p.category.lower() == category.lower()]
            if not patterns:
                return f"No patterns found in category '{category}'."

        # Image generation via API (Track B)
        if include_images and img_cfg.enabled:
            image_count = 0
            image_errors: list[str] = []
            for p in patterns:
                if not p.name or image_count >= img_cfg.max_images_per_run:
                    break
                slug = _slugify(p.name)
                # Skip if image already exists
                if any((images_dir / f"{slug}{ext}").is_file() for ext in (".png", ".jpg", ".jpeg", ".webp")):
                    continue
                try:
                    generate_pattern_image(p, images_dir, img_cfg)
                    image_count += 1
                except Exception as e:
                    image_errors.append(f"  {p.name}: {e}")
        elif include_images and not img_cfg.enabled:
            return (
                "Image generation via API is disabled. Either:\n"
                "1. Use `generate_image_prompts` to get prompts for manual image creation, or\n"
                "2. Enable API generation in config: pattern_cards.image_generation.enabled: true"
            )

        results: list[str] = []
        errors: list[str] = []

        for p in patterns:
            if not p.name:
                errors.append(f"Skipped: {p.source_path} (no name)")
                continue
            try:
                generate_card_files(p, output_dir, images_dir=images_dir)
                results.append(f"  {p.name} ({p.category})")
            except Exception as e:
                errors.append(f"  {p.name}: {e}")

        output_parts = [f"Generated {len(results)} card(s) in {output_dir / 'cards'}:"]
        output_parts.extend(results)

        if errors:
            output_parts.append(f"\n{len(errors)} error(s):")
            output_parts.extend(errors)

        return "\n".join(output_parts)

    generate_deck_tool = ToolDefinition(
        name="generate_deck",
        description=(
            "Generate visual cards (PNG + HTML) for all patterns in the vault, "  # pragma: no mutate
            "or filtered by category. Set include_images=true to generate AI images via API."  # pragma: no mutate
        ),
        parameters={
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional category filter. Only patterns in this category will be generated. Leave empty for all.",  # pragma: no mutate
                },
                "include_images": {
                    "type": "boolean",
                    "description": "If true, generate AI images via API for patterns that don't already have images.",  # pragma: no mutate
                },
            },
            "required": [],
        },
        execute=_generate_deck,
    )

    # --- generate_image_prompts (Track A) ---

    def _generate_image_prompts(
        pattern_name: str = "",
        category: str = "",
    ) -> str:
        if pattern_name:
            match, err = _find_pattern(pattern_name)
            if err:
                return err
            patterns = [match]
        else:
            patterns = list_vault_patterns(vault_config.vault_path, patterns_dir)

            if not patterns:
                return "No patterns found in the vault."

            if category:
                patterns = [p for p in patterns if p.category.lower() == category.lower()]
                if not patterns:
                    return f"No patterns found in category '{category}'."

        prompts_path = output_dir / "image-prompts.md"
        export_image_prompts(patterns, prompts_path)

        return (
            f"Generated image prompts for {len(patterns)} pattern(s).\n"
            f"File: {prompts_path}\n\n"
            "Copy each prompt into Gemini or another image tool, "
            "then save the image as data/pattern-cards/images/{slug}.png"
        )

    generate_prompts_tool = ToolDefinition(
        name="generate_image_prompts",
        description=(
            "Generate image creation prompts for a single pattern, a category, or all patterns. "  # pragma: no mutate
            "Writes prompts to a markdown file for manual use in Gemini, DALL-E, etc. "  # pragma: no mutate
            "Use this when API image generation is not available."  # pragma: no mutate
        ),
        parameters={
            "type": "object",
            "properties": {
                "pattern_name": {
                    "type": "string",
                    "description": "Generate prompt for a single pattern by name. Takes precedence over category filter.",  # pragma: no mutate
                },
                "category": {
                    "type": "string",
                    "description": "Optional category filter. Leave empty for all patterns. Ignored if pattern_name is set.",  # pragma: no mutate
                },
            },
            "required": [],
        },
        execute=_generate_image_prompts,
    )

    return [generate_card_tool, generate_deck_tool, generate_prompts_tool]
