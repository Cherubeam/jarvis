"""
Pattern card generator tools for JARVIS.

Factory function that creates tools for generating visual pattern cards
from Obsidian vault notes. Uses the closure pattern to capture config.
"""

from pathlib import Path

from packages.core.card_renderer import (
    generate_card_files,
    list_vault_patterns,
    parse_pattern,
    _slugify,
)
from packages.core.tools.base import ToolDefinition
from packages.integrations.obsidian.vault import VaultConfig, read_note


def make_card_generator_tools(
    vault_config: VaultConfig,
    patterns_dir: str,
    output_dir: Path,
) -> list[ToolDefinition]:
    """Create pattern card generator tools.

    Args:
        vault_config: Vault configuration with path validation.
        patterns_dir: Patterns directory relative to vault root.
        output_dir: Directory for generated card files (absolute).

    Returns:
        List of 2 ToolDefinitions: generate_card, generate_deck.
    """
    images_dir = output_dir / "images"

    # --- generate_card ---

    def _generate_card(pattern_name: str) -> str:
        patterns = list_vault_patterns(vault_config.vault_path, patterns_dir)
        match = None
        for p in patterns:
            if p.name.lower() == pattern_name.lower():
                match = p
                break

        if not match:
            available = ", ".join(p.name for p in patterns) if patterns else "(none found)"
            return f"Error: Pattern '{pattern_name}' not found. Available: {available}"

        if not match.name:
            return f"Error: Pattern at '{match.source_path}' has no name in frontmatter."

        try:
            files = generate_card_files(match, output_dir, images_dir=images_dir)
            slug = _slugify(match.name)
            has_image = (images_dir / f"{slug}.png").is_file() or any(
                (images_dir / f"{slug}{ext}").is_file()
                for ext in (".jpg", ".jpeg", ".webp")
            )
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
            "Generate a visual pattern card (PNG + HTML) from an Obsidian pattern note. "
            "Provide the pattern name exactly as it appears in the vault."
        ),
        parameters={
            "type": "object",
            "properties": {
                "pattern_name": {
                    "type": "string",
                    "description": "The name of the pattern to generate a card for.",
                },
            },
            "required": ["pattern_name"],
        },
        execute=_generate_card,
    )

    # --- generate_deck ---

    def _generate_deck(category: str = "") -> str:
        patterns = list_vault_patterns(vault_config.vault_path, patterns_dir)

        if not patterns:
            return "No patterns found in the vault."

        if category:
            patterns = [
                p for p in patterns
                if p.category.lower() == category.lower()
            ]
            if not patterns:
                return f"No patterns found in category '{category}'."

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
            "Generate visual cards (PNG + HTML) for all patterns in the vault, "
            "or filtered by category. Cards are saved to the pattern-cards output directory."
        ),
        parameters={
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional category filter. Only patterns in this category will be generated. Leave empty for all.",
                },
            },
            "required": [],
        },
        execute=_generate_deck,
    )

    return [generate_card_tool, generate_deck_tool]
