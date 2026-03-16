"""
Content evaluator tool — wraps the content-evaluator skill as a callable tool.

Factory function that creates a ToolDefinition backed by the skill's SKILL.md
system prompt and configured temperature.
"""

from pathlib import Path

from packages.core.context_builder import parse_frontmatter
from packages.core.llm_client import LLMClient
from packages.core.tools.base import ToolDefinition


def _import_skill_module(skill_dir: Path):
    """Import a skill's skill.py module by path (reuses base.py logic)."""
    import importlib.util

    parts = skill_dir.absolute().parts
    try:
        pkg_idx = parts.index("packages")
    except ValueError:
        raise ImportError(f"Cannot determine module path for {skill_dir}")

    module_name = ".".join(parts[pkg_idx:]) + ".skill"
    skill_py = skill_dir / "skill.py"
    spec = importlib.util.spec_from_file_location(module_name, skill_py)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create module spec for {skill_py}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_content_evaluator_tool(
    skill_dir: Path,
    llm_client: LLMClient,
    model: str,
) -> ToolDefinition:
    """Create a content evaluation tool from the content-evaluator skill.

    Args:
        skill_dir: Path to the content-evaluator skill directory.
        llm_client: LLM client for API calls.
        model: Model ID to use for evaluation.

    Returns:
        A ToolDefinition that evaluates content through the 5-lens framework.
    """
    # Load system prompt from SKILL.md
    skill_md = skill_dir / "SKILL.md"
    raw = skill_md.read_text(encoding="utf-8")
    _, body = parse_frontmatter(raw)
    system_prompt = body.strip()

    # Load temperature from skill.py SKILL_CONFIG
    temperature = 0.8  # default
    skill_py = skill_dir / "skill.py"
    if skill_py.is_file():
        try:
            module = _import_skill_module(skill_dir)
            skill_config = getattr(module, "SKILL_CONFIG", {})
            temperature = skill_config.get("temperature", temperature)
        except Exception:
            pass

    def _evaluate(content: str, audience: str = "") -> str:
        user_msg = content
        if audience:
            user_msg = f"Target audience: {audience}\n\n{content}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ]

        try:
            response = llm_client.complete(
                messages, model=model, temperature=temperature,
            )
            return response.choices[0].message.content or "No evaluation generated."
        except Exception as e:
            return f"Content evaluation failed: {e}"

    return ToolDefinition(
        name="evaluate_content",
        description=(
            "Run a structured 5-lens content evaluation on written content. "
            "Evaluates through: marketing strategist debate, busy subscriber test, "
            "substance scan, skimmer's path analysis, and voice authenticity scan."
        ),
        parameters={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The full text content to evaluate.",
                },
                "audience": {
                    "type": "string",
                    "description": "Optional target audience description.",
                },
            },
            "required": ["content"],
        },
        execute=_evaluate,
    )
