"""
Intelligent model routing — classify query complexity and select the
appropriate model preset (fast / balanced / quality).

Uses heuristic-based classification (no LLM calls) to route simple queries
to cheap/fast models and complex queries to high-quality models.
"""

import re
from dataclasses import dataclass

from packages.core.model_resolver import ResolvedModel, resolve_model
from packages.core.settings import Settings


@dataclass
class RoutingDecision:
    """Result of routing a query to a model preset."""

    preset: str  # "fast", "balanced", "quality"
    resolved: ResolvedModel
    reason: str  # human-readable explanation
    confidence: float  # 0.0-1.0


# Agents that always get the quality model
_QUALITY_AGENTS = {"developer", "writer", "content_reviewer", "substack_publisher"}

# Patterns that indicate complexity
_CODE_BLOCK_RE = re.compile(r"```")
_MULTI_PART_RE = re.compile(r"\b(additionally|furthermore|also|and also|moreover)\b", re.IGNORECASE)
_NUMBERED_LIST_RE = re.compile(r"^\s*\d+\.\s", re.MULTILINE)


def classify_query(
    query: str,
    settings: Settings,
    agent_name: str | None = None,
) -> tuple[str, str, float]:
    """Classify query complexity and return (preset, reason, confidence).

    Returns:
        Tuple of (preset_name, reason, confidence)
    """
    simple_threshold = settings.routing.simple_threshold
    complex_threshold = settings.routing.complex_threshold

    # Agent-specific overrides
    if agent_name and agent_name in _QUALITY_AGENTS:
        return ("quality", f"agent '{agent_name}' always uses quality model", 0.95)

    query_len = len(query)

    # Check for complexity signals
    has_code = bool(_CODE_BLOCK_RE.search(query))
    has_multi_part = bool(_MULTI_PART_RE.search(query))
    has_numbered_list = bool(_NUMBERED_LIST_RE.search(query))
    complexity_signals = sum([has_code, has_multi_part, has_numbered_list])

    # Complex: long query or multiple complexity signals
    if query_len > complex_threshold or complexity_signals >= 2:
        return ("quality", "complex query detected", 0.8)
    if has_code:
        return ("quality", "code block detected", 0.85)

    # Simple: short query without complexity signals
    if query_len < simple_threshold and complexity_signals == 0:
        return ("fast", "short simple query", 0.8)

    # Default: balanced
    return ("balanced", "moderate complexity", 0.6)


def route_query(
    query: str,
    settings: Settings,
    agent_name: str | None = None,
) -> RoutingDecision:
    """Route a query to the appropriate model based on complexity.

    Args:
        query: The user's input text.
        settings: Typed JARVIS settings.
        agent_name: Optional agent name for agent-specific routing.

    Returns:
        RoutingDecision with the selected preset and resolved model.
    """
    preset, reason, confidence = classify_query(query, settings, agent_name)
    resolved = resolve_model(preset, settings.models)
    return RoutingDecision(
        preset=preset,
        resolved=resolved,
        reason=reason,
        confidence=confidence,
    )
