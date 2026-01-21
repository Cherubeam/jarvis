"""
Judge prompt templates for LLM-as-judge evaluation.

This module provides prompt templates organized by test category
to ensure consistent and effective evaluation of AI responses.
"""

from dataclasses import dataclass


# System prompt for the judge
JUDGE_SYSTEM_PROMPT = """You are an expert evaluator assessing AI assistant responses for quality.

Your role is to provide objective, structured evaluations based on specific criteria.

Guidelines:
- Be strict but fair in scoring
- Provide clear reasoning for each score
- Focus on the specific criteria provided
- Consider the context and user intent
- Output responses in structured JSON format

Scoring scale:
- 1.0: Excellent - Exceeds expectations
- 0.8-0.9: Good - Meets all criteria well
- 0.6-0.7: Acceptable - Meets minimum requirements
- 0.4-0.5: Poor - Missing key elements
- 0.0-0.3: Failing - Does not meet criteria

Threshold: 0.70 = acceptable minimum"""


# Category-specific evaluation templates
CATEGORY_TEMPLATES = {
    "reasoning": """Evaluate this technical/reasoning response:

USER QUERY: {user_message}

ASSISTANT RESPONSE: {actual_response}

CRITERIA TO EVALUATE:
{criteria_list}

Provide scores (0.0-1.0) for each criterion and an overall assessment.

Return your evaluation as JSON:
{{
    "dimension_scores": {{"criterion_name": score, ...}},
    "overall_score": score,
    "reasoning": "Detailed explanation of scores",
    "passed_criteria": ["list", "of", "passed"],
    "failed_criteria": ["list", "of", "failed"]
}}""",

    "context_recall": """Evaluate whether the assistant correctly used personal context:

PERSONAL CONTEXT PROVIDED:
{context}

USER QUERY: {user_message}

ASSISTANT RESPONSE: {actual_response}

CRITERIA TO EVALUATE:
{criteria_list}

Key evaluation points:
- Does the response demonstrate awareness of the context?
- Are facts from context recalled accurately?
- Is the personalization appropriate and natural?

Return your evaluation as JSON:
{{
    "dimension_scores": {{"criterion_name": score, ...}},
    "overall_score": score,
    "reasoning": "Detailed explanation",
    "context_usage_quality": "excellent|good|poor|none",
    "passed_criteria": ["list"],
    "failed_criteria": ["list"]
}}""",

    "personalization": """Evaluate whether the assistant followed style/tone preferences:

PREFERENCES PROVIDED:
{context}

USER QUERY: {user_message}

ASSISTANT RESPONSE: {actual_response}

CRITERIA TO EVALUATE:
{criteria_list}

{forbidden_section}

Key evaluation points:
- Does the tone match preferences?
- Are forbidden phrases avoided?
- Is the style consistent?

Return your evaluation as JSON:
{{
    "dimension_scores": {{"criterion_name": score, ...}},
    "overall_score": score,
    "reasoning": "Detailed explanation",
    "tone_match_quality": "excellent|good|poor",
    "passed_criteria": ["list"],
    "failed_criteria": ["list"]
}}""",

    "edge_cases": """Evaluate how the assistant handles this edge case:

USER QUERY: {user_message}

ASSISTANT RESPONSE: {actual_response}

CRITERIA TO EVALUATE:
{criteria_list}

Key evaluation points:
- Does it handle ambiguity gracefully?
- Does it ask for clarification when appropriate?
- Is the response helpful despite constraints?

Return your evaluation as JSON:
{{
    "dimension_scores": {{"criterion_name": score, ...}},
    "overall_score": score,
    "reasoning": "Detailed explanation",
    "edge_case_handling": "excellent|good|poor",
    "passed_criteria": ["list"],
    "failed_criteria": ["list"]
}}""",
}


def format_criteria(qualities: dict) -> str:
    """Format criteria dict as bullet points."""
    if not qualities:
        return "- No specific criteria provided"

    lines = []
    for key, value in qualities.items():
        if isinstance(value, bool):
            lines.append(f"- {key}: {'must be present' if value else 'must not be present'}")
        elif isinstance(value, str):
            lines.append(f"- {key}: {value}")
        elif isinstance(value, (int, float)):
            lines.append(f"- {key}: {value}")
        else:
            lines.append(f"- {key}: {value}")

    return "\n".join(lines)


def format_context(context: dict) -> str:
    """Format context dict as readable text."""
    if not context:
        return "No context provided"

    lines = []
    for key, value in context.items():
        lines.append(f"**{key.upper()}**:")
        lines.append(value.strip())
        lines.append("")

    return "\n".join(lines)


def format_forbidden_patterns(patterns: list[str]) -> str:
    """Format forbidden patterns as bullet points."""
    if not patterns:
        return ""

    lines = ["FORBIDDEN PATTERNS (must not appear):"]
    for pattern in patterns:
        lines.append(f"- \"{pattern}\"")

    return "\n".join(lines)


def build_judge_prompt(
    category: str,
    context: dict,
    user_message: str,
    actual_response: str,
    criteria_qualities: dict,
    forbidden_patterns: list[str] | None = None,
) -> list[dict]:
    """
    Build judge prompt messages for LLMClient.

    Args:
        category: Test category (reasoning, context_recall, personalization, edge_cases)
        context: Personal context dict (profile, preferences, current_focus)
        user_message: The user's query
        actual_response: The assistant's response to evaluate
        criteria_qualities: Dict of quality criteria from YAML
        forbidden_patterns: Optional list of patterns that should not appear

    Returns:
        List of message dicts for LLMClient.chat_stream()
    """
    # Format criteria as bullet points
    criteria_list = format_criteria(criteria_qualities)

    # Format forbidden patterns if present
    forbidden_section = ""
    if forbidden_patterns:
        forbidden_section = format_forbidden_patterns(forbidden_patterns)

    # Get template for category (default to reasoning if unknown)
    template = CATEGORY_TEMPLATES.get(category, CATEGORY_TEMPLATES["reasoning"])

    # Format template
    user_content = template.format(
        context=format_context(context),
        user_message=user_message,
        actual_response=actual_response,
        criteria_list=criteria_list,
        forbidden_section=forbidden_section,
    )

    return [
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
