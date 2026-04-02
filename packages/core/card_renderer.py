"""
Pattern card renderer for JARVIS.

Parses Obsidian pattern notes and renders them as visual cards
(HTML/CSS + PNG via WeasyPrint) for workshop facilitation.

Phase 2 adds image generation:
- Track A: build_image_prompt() + export_image_prompts() for manual use
- Track B: generate_pattern_image() via litellm API (opt-in)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import Template

from packages.core.context_builder import parse_frontmatter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class PatternData:
    """Parsed pattern extracted from an Obsidian markdown note."""

    name: str
    category: str = ""
    intent: str = ""
    context: str = ""
    problem: str = ""
    solution: str = ""
    consequences: str = ""
    related_patterns: list[str] = field(default_factory=list)
    status: str = ""
    tags: list[str] = field(default_factory=list)
    source_path: str = ""


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_SECTION_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def _extract_sections(body: str) -> dict[str, str]:
    """Split markdown body into {heading_lower: content} dict."""
    matches = list(_SECTION_RE.finditer(body))
    sections: dict[str, str] = {}
    for i, m in enumerate(matches):
        heading = m.group(1).strip().lower()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections[heading] = body[start:end].strip()
    return sections


def _extract_intent(body: str) -> str:
    """Extract intent from ``> **Intent:** ...`` line."""
    m = re.search(r">\s*\*\*Intent:\*\*\s*(.+)", body)
    return m.group(1).strip() if m else ""


def _clean_wikilinks(text: str) -> list[str]:
    """Convert Obsidian wikilinks to plain names."""
    results: list[str] = []
    for item in text if isinstance(text, list) else [text]:
        cleaned = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", str(item))
        cleaned = cleaned.strip().strip('"').strip("'")
        if cleaned:
            results.append(cleaned)
    return results


def _truncate(text: str, max_chars: int = 280) -> str:
    """Truncate text to max_chars, ending at a sentence or word boundary."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    # Try to cut at last sentence end
    last_period = truncated.rfind(". ")
    if last_period > max_chars // 2:
        return truncated[: last_period + 1]
    # Fall back to word boundary
    last_space = truncated.rfind(" ")
    if last_space > 0:
        return truncated[:last_space] + "..."
    return truncated + "..."


def parse_pattern(markdown: str, source_path: str = "") -> PatternData:
    """Parse an Obsidian pattern markdown file into PatternData."""
    meta, body = parse_frontmatter(markdown)

    sections = _extract_sections(body)
    intent = _extract_intent(body)

    related_raw = meta.get("related-patterns", [])
    related = _clean_wikilinks(related_raw)

    tags_raw = meta.get("tags", [])
    if isinstance(tags_raw, str):
        tags_raw = [tags_raw]

    return PatternData(
        name=meta.get("name", ""),
        category=meta.get("category", ""),
        intent=intent,
        context=sections.get("context", ""),
        problem=sections.get("problem", ""),
        solution=sections.get("solution", ""),
        consequences=sections.get("consequences", ""),
        related_patterns=related,
        status=meta.get("status", ""),
        tags=tags_raw,
        source_path=source_path,
    )


def list_vault_patterns(vault_path: Path, patterns_dir: str) -> list[PatternData]:
    """Scan an Obsidian vault directory for pattern notes and parse them.

    Recursively finds all .md files in the patterns directory, skipping
    files that start with '_' (index/overview files).
    """
    target = vault_path / patterns_dir
    if not target.is_dir():
        return []

    patterns: list[PatternData] = []
    for md_file in sorted(target.rglob("*.md")):
        if md_file.name.startswith("_"):
            continue
        text = md_file.read_text(encoding="utf-8")
        meta, _ = parse_frontmatter(text)
        if meta.get("type") != "pattern":
            continue
        rel_path = str(md_file.relative_to(vault_path))
        patterns.append(parse_pattern(text, source_path=rel_path))

    return patterns


# ---------------------------------------------------------------------------
# Category colors
# ---------------------------------------------------------------------------

CATEGORY_COLORS: dict[str, str] = {
    "reasoning & planning": "#4A90D9",
    "knowledge & retrieval": "#50B88E",
    "interaction & interface": "#E8A840",
    "reliability & safety": "#D94A4A",
    "orchestration & architecture": "#8B5CF6",
    "learning & adaptation": "#EC6B9C",
    "flow management": "#3B82F6",
}

DEFAULT_COLOR = "#64748B"


def _category_color(category: str) -> str:
    return CATEGORY_COLORS.get(category.lower(), DEFAULT_COLOR)


# ---------------------------------------------------------------------------
# HTML/CSS templates
# ---------------------------------------------------------------------------

CARD_STYLES = """\
@page {
    size: 750px 1050px;
    margin: 0;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    background: #ffffff;
}

.card {
    width: 750px;
    height: 1050px;
    background: #ffffff;
    border: 3px solid {{ color }};
    border-radius: 24px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    position: relative;
}

.card-header {
    background: {{ color }};
    color: #ffffff;
    padding: 24px 32px 16px;
    text-transform: uppercase;
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 2px;
}

.card-title {
    padding: 24px 32px 8px;
    font-size: 36px;
    font-weight: 800;
    color: #1a1a2e;
    line-height: 1.2;
}

.card-intent {
    padding: 0 32px 24px;
    font-size: 18px;
    font-style: italic;
    color: #4a4a6a;
    line-height: 1.5;
    border-bottom: 2px solid {{ color }}20;
}

.card-image {
    width: 686px;
    height: 300px;
    margin: 16px 32px;
    border-radius: 12px;
    object-fit: cover;
    background: linear-gradient(135deg, {{ color }}15, {{ color }}30);
    display: flex;
    align-items: center;
    justify-content: center;
}

.card-image-placeholder {
    width: 686px;
    height: 300px;
    margin: 16px 32px;
    border-radius: 12px;
    background: linear-gradient(135deg, {{ color }}20, {{ color }}40);
}

.card-body {
    padding: 16px 32px;
    flex: 1;
    overflow: hidden;
}

.card-section-label {
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: {{ color }};
    margin-bottom: 6px;
    margin-top: 16px;
}

.card-section-label:first-child {
    margin-top: 0;
}

.card-section-text {
    font-size: 15px;
    color: #2d2d44;
    line-height: 1.55;
}

.card-footer {
    padding: 16px 32px 20px;
    border-top: 2px solid {{ color }}20;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.card-related-tag {
    background: {{ color }}15;
    color: {{ color }};
    font-size: 12px;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 999px;
    border: 1px solid {{ color }}30;
}
"""

CARD_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
{{ styles }}
</style>
</head>
<body>
<div class="card">
    <div class="card-header">{{ category or "Pattern" }}</div>
    <div class="card-title">{{ name }}</div>
    {% if intent %}
    <div class="card-intent">{{ intent }}</div>
    {% endif %}
    {% if image_path %}
    <img class="card-image" src="file://{{ image_path }}" alt="{{ name }}">
    {% else %}
    <div class="card-image-placeholder"></div>
    {% endif %}
    <div class="card-body">
        {% if problem %}
        <div class="card-section-label">Problem</div>
        <div class="card-section-text">{{ problem_short }}</div>
        {% endif %}
        {% if solution %}
        <div class="card-section-label">Solution</div>
        <div class="card-section-text">{{ solution_short }}</div>
        {% endif %}
    </div>
    {% if related_patterns %}
    <div class="card-footer">
        {% for rp in related_patterns %}
        <span class="card-related-tag">{{ rp }}</span>
        {% endfor %}
    </div>
    {% endif %}
</div>
</body>
</html>
"""

CARD_BACK_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@page {
    size: 750px 1050px;
    margin: 0;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; }
.card-back {
    width: 750px;
    height: 1050px;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    border-radius: 24px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: #ffffff;
}
.card-back-title {
    font-size: 42px;
    font-weight: 800;
    letter-spacing: 4px;
    text-transform: uppercase;
    margin-bottom: 16px;
}
.card-back-subtitle {
    font-size: 18px;
    font-weight: 400;
    letter-spacing: 6px;
    text-transform: uppercase;
    opacity: 0.6;
}
.card-back-ornament {
    width: 120px;
    height: 4px;
    background: rgba(255,255,255,0.3);
    border-radius: 2px;
    margin: 24px 0;
}
</style>
</head>
<body>
<div class="card-back">
    <div class="card-back-title">Pattern</div>
    <div class="card-back-ornament"></div>
    <div class="card-back-subtitle">Language</div>
</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_card_html(
    pattern: PatternData,
    image_path: str | None = None,
) -> str:
    """Render a pattern as an HTML card string."""
    color = _category_color(pattern.category)
    styles = Template(CARD_STYLES).render(color=color)

    return Template(CARD_TEMPLATE).render(
        styles=styles,
        name=pattern.name,
        category=pattern.category,
        intent=pattern.intent,
        image_path=image_path,
        problem_short=_truncate(pattern.problem),
        solution_short=_truncate(pattern.solution),
        related_patterns=pattern.related_patterns[:5],
        problem=pattern.problem,
        solution=pattern.solution,
    )


def render_card_back_html() -> str:
    """Render the card back as an HTML string."""
    return CARD_BACK_TEMPLATE


def render_card_to_png(html: str, output_path: Path) -> Path:
    """Render an HTML card string to a PNG file using WeasyPrint."""
    from weasyprint import HTML

    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html).write_png(str(output_path))
    return output_path


def render_card_to_pdf(html: str, output_path: Path) -> Path:
    """Render an HTML card string to a PDF file using WeasyPrint."""
    from weasyprint import HTML

    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html).write_pdf(str(output_path))
    return output_path


def _slugify(name: str) -> str:
    """Convert a pattern name to a filesystem-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def generate_card_files(
    pattern: PatternData,
    output_dir: Path,
    images_dir: Path | None = None,
) -> dict[str, Path]:
    """Generate HTML and PNG card files for a single pattern.

    Returns dict with keys 'html' and 'png' pointing to output paths.
    """
    slug = _slugify(pattern.name)

    # Check for a user-provided image
    image_path: str | None = None
    if images_dir:
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            candidate = images_dir / f"{slug}{ext}"
            if candidate.is_file():
                image_path = str(candidate.resolve())
                break

    html_content = render_card_html(pattern, image_path=image_path)

    cards_dir = output_dir / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)

    html_path = cards_dir / f"{slug}.html"
    html_path.write_text(html_content, encoding="utf-8")

    png_path = cards_dir / f"{slug}.png"
    render_card_to_png(html_content, png_path)

    return {"html": html_path, "png": png_path}


# ---------------------------------------------------------------------------
# Image prompt generation (Track A — manual)
# ---------------------------------------------------------------------------

# Map categories to visual palette descriptions for consistent image style
_CATEGORY_PALETTE: dict[str, str] = {
    "reasoning & planning": "deep blues and silver, geometric precision, crystalline structures",
    "knowledge & retrieval": "emerald greens and gold, flowing information streams, library motifs",
    "interaction & interface": "warm amber and copper, human silhouettes, bridge-like connections",
    "reliability & safety": "crimson and steel grey, shields, fortress-like solidity",
    "orchestration & architecture": "violet and indigo, interconnected nodes, constellation patterns",
    "learning & adaptation": "coral pink and teal, organic growth spirals, neural branching",
    "flow management": "ocean blue and white, water currents, smooth gradients",
}

_DEFAULT_PALETTE = "slate blue and warm grey, abstract geometric forms"


def build_image_prompt(pattern: PatternData) -> str:
    """Craft an image generation prompt from a pattern's content.

    Produces a prompt suitable for Imagen, DALL-E, or Gemini image models.
    Style: abstract conceptual illustration, no text in image.
    """
    palette = _CATEGORY_PALETTE.get(pattern.category.lower(), _DEFAULT_PALETTE)

    # Build the core concept from available fields
    concept_parts: list[str] = []
    if pattern.intent:
        concept_parts.append(pattern.intent)
    elif pattern.problem:
        concept_parts.append(_truncate(pattern.problem, 150))

    concept = concept_parts[0] if concept_parts else pattern.name

    return (
        f"Abstract conceptual illustration representing '{pattern.name}'. "
        f"The core idea: {concept} "
        f"Visual style: modern, clean, abstract art with {palette}. "
        f"No text, no letters, no words in the image. "
        f"Minimalist composition with a single strong visual metaphor. "
        f"Suitable as a card illustration at 1024x1024 resolution. "
        f"Professional, polished, slightly futuristic aesthetic."
    )


def export_image_prompts(
    patterns: list[PatternData],
    output_path: Path,
) -> Path:
    """Write image generation prompts for all patterns to a markdown file.

    The user can copy these prompts into Gemini UI or another image tool.
    Returns the path to the written file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        "# Pattern Card — Image Prompts",
        "",
        "Copy each prompt into your image generation tool (e.g. Gemini, DALL-E).",
        f"Save the generated image as `data/pattern-cards/images/{{slug}}.png`.",
        "",
        "---",
        "",
    ]

    for p in patterns:
        if not p.name:
            continue
        slug = _slugify(p.name)
        prompt = build_image_prompt(p)
        lines.extend([
            f"## {p.name}",
            f"**Slug:** `{slug}`  ",
            f"**Save as:** `images/{slug}.png`",
            "",
            f"> {prompt}",
            "",
            "---",
            "",
        ])

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# API image generation (Track B — opt-in)
# ---------------------------------------------------------------------------

@dataclass
class ImageGenerationConfig:
    """Configuration for API-based image generation."""

    enabled: bool = False
    model: str = "gemini/imagen-4.0-generate-001"
    size: str = "1024x1024"
    max_images_per_run: int = 10

    @classmethod
    def from_dict(cls, d: dict) -> ImageGenerationConfig:
        img_cfg = d.get("image_generation", {})
        return cls(
            enabled=img_cfg.get("enabled", False),
            model=img_cfg.get("model", "gemini/imagen-4.0-generate-001"),
            size=img_cfg.get("size", "1024x1024"),
            max_images_per_run=img_cfg.get("max_images_per_run", 10),
        )


def generate_pattern_image(
    pattern: PatternData,
    images_dir: Path,
    config: ImageGenerationConfig,
    force: bool = False,
) -> Path:
    """Generate an image for a pattern using the litellm image generation API.

    Args:
        pattern: The pattern to generate an image for.
        images_dir: Directory to save images in.
        config: Image generation configuration.
        force: If True, regenerate even if image already exists.

    Returns:
        Path to the generated image file.

    Raises:
        RuntimeError: If image generation fails or is not enabled.
    """
    if not config.enabled:
        raise RuntimeError(
            "Image generation is disabled. "
            "Set pattern_cards.image_generation.enabled: true in local.yaml "
            "and ensure GEMINI_API_KEY is set."
        )

    slug = _slugify(pattern.name)
    output_path = images_dir / f"{slug}.png"

    # Cache check — skip if image already exists
    if output_path.is_file() and not force:
        logger.info("Image already exists for '%s', skipping.", pattern.name)
        return output_path

    import litellm

    prompt = build_image_prompt(pattern)
    images_dir.mkdir(parents=True, exist_ok=True)

    response = litellm.image_generation(
        model=config.model,
        prompt=prompt,
        size=config.size,
        n=1,
    )

    # Extract image data — litellm returns URL or base64
    image_data = response.data[0]

    if hasattr(image_data, "b64_json") and image_data.b64_json:
        import base64
        img_bytes = base64.b64decode(image_data.b64_json)
        output_path.write_bytes(img_bytes)
    elif hasattr(image_data, "url") and image_data.url:
        import httpx
        resp = httpx.get(image_data.url, timeout=60)
        resp.raise_for_status()
        output_path.write_bytes(resp.content)
    else:
        raise RuntimeError(f"Unexpected image response format: {image_data}")

    logger.info("Generated image for '%s' at %s", pattern.name, output_path)
    return output_path
