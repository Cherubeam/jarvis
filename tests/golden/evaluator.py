"""
Core evaluation engine for LLM-as-judge system.

This module orchestrates judge calls, parses responses, and performs
basic quality checks on AI assistant responses.
"""

import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from judge_prompts import build_judge_prompt

from packages.core.llm_client import LLMClient
from packages.core.pricing import get_model_pricing


@dataclass
class EvaluationCriteria:
    """
    Evaluation criteria extracted from YAML expected_qualities.

    Attributes:
        qualities: Dict of quality criteria (e.g., {"accurate": true, "concise": true})
        forbidden_patterns: List of phrases that should not appear in response
        expected_content: List of keywords that should appear in response
        expected_themes: List of themes that should be present
        min_length: Minimum character length (optional)
        max_length: Maximum character length (optional)
    """

    qualities: dict[str, bool | str | int] = field(default_factory=dict)
    forbidden_patterns: list[str] = field(default_factory=list)
    expected_content: list[str] = field(default_factory=list)
    expected_themes: list[str] = field(default_factory=list)
    min_length: int | None = None
    max_length: int | None = None


@dataclass
class EvaluationScore:
    """
    Results from judge evaluation.

    Attributes:
        overall_score: Overall quality score (0.0 to 1.0)
        dimension_scores: Scores for each quality dimension
        reasoning: Judge's detailed explanation
        passed_criteria: List of criteria that passed
        failed_criteria: List of criteria that failed
        forbidden_patterns_found: List of forbidden patterns detected
        content_checks_passed: Whether expected content was found
        themes_present: List of themes identified in response
    """

    overall_score: float
    dimension_scores: dict[str, float] = field(default_factory=dict)
    reasoning: str = ""
    passed_criteria: list[str] = field(default_factory=list)
    failed_criteria: list[str] = field(default_factory=list)
    forbidden_patterns_found: list[str] = field(default_factory=list)
    content_checks_passed: bool = True
    themes_present: list[str] = field(default_factory=list)


@dataclass
class EvaluationResult:
    """
    Complete evaluation result for storage.

    Contains all information about a test execution including
    context, response, evaluation scores, and performance metrics.
    """

    test_name: str
    timestamp: str
    model_tested: str
    judge_model: str
    test_category: str

    # Context and conversation
    context: dict[str, str]
    user_message: str
    actual_response: str

    # Evaluation
    evaluation: EvaluationScore
    passed: bool
    quality_threshold: float

    # Performance metrics
    response_cost_usd: float
    judge_cost_usd: float
    total_cost_usd: float
    response_latency_ms: float
    judge_latency_ms: float

    # Token usage
    response_tokens: dict[str, int]
    judge_tokens: dict[str, int]

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        result = asdict(self)
        # Ensure nested dataclass is also converted
        result["evaluation"] = asdict(self.evaluation)
        return result


@dataclass
class ToolCallCheckResult:
    """Results from programmatic tool call validation."""

    passed: bool
    score_cap: float  # Maximum allowed score (1.0 if all checks pass)
    details: list[str] = field(default_factory=list)
    tool_calls_found: list[dict] = field(default_factory=list)


def evaluate_tool_calls(
    actual_tool_calls: list[dict],
    final_text: str | None,
    assertions: dict,
) -> ToolCallCheckResult:
    """
    Programmatic validation of tool calls against YAML assertions.

    Checks expected_tool_calls (name + args), expected_tool_call_count,
    expects_final_text, and expects_no_tool_calls.

    Scoring caps:
    - Wrong tool name → 0.3
    - Wrong enum arg → 0.3
    - Wrong free-text arg → 0.5
    - Wrong count → 0.5
    - Missing final text → 0.4
    """
    score_cap = 1.0
    details: list[str] = []

    # Check expects_no_tool_calls
    if assertions.get("expects_no_tool_calls", False):
        if actual_tool_calls:
            names = [tc.get("function", {}).get("name", "?") for tc in actual_tool_calls]
            details.append(f"Expected no tool calls, but got: {names}")
            score_cap = min(score_cap, 0.3)
        else:
            details.append("Correctly made no tool calls")

    # Check expected_tool_call_count
    expected_count = assertions.get("expected_tool_call_count")
    if expected_count is not None:
        if len(actual_tool_calls) != expected_count:
            details.append(f"Expected {expected_count} tool call(s), got {len(actual_tool_calls)}")
            score_cap = min(score_cap, 0.5)
        else:
            details.append(f"Correct tool call count: {expected_count}")

    # Check expected_tool_calls (ordered list)
    expected_calls = assertions.get("expected_tool_calls", [])
    for _i, expected in enumerate(expected_calls):
        expected_name = expected["tool_name"]

        # Find matching tool call by name (search all, not by index)
        matching = [tc for tc in actual_tool_calls if tc.get("function", {}).get("name") == expected_name]

        if not matching:
            details.append(f"Expected tool call '{expected_name}' not found")
            score_cap = min(score_cap, 0.3)
            continue

        details.append(f"Found expected tool call: {expected_name}")
        tc = matching[0]

        # Check arguments
        expected_args = expected.get("expected_args", {})
        exact_match_args = set(expected.get("exact_match_args", []))
        if expected_args:
            try:
                actual_args = json.loads(tc.get("function", {}).get("arguments", "{}"))
            except (json.JSONDecodeError, TypeError):
                actual_args = {}

            for arg_name, expected_value in expected_args.items():
                actual_value = actual_args.get(arg_name)
                if actual_value is None:
                    details.append(f"  Missing arg '{arg_name}' (expected: {expected_value})")
                    score_cap = min(score_cap, 0.5)
                elif arg_name in exact_match_args:
                    # Exact match (for enum args like agent_name)
                    actual_str = str(actual_value)
                    if actual_str.lower() == str(expected_value).lower():
                        details.append(f"  Arg '{arg_name}' matches: {expected_value}")
                    else:
                        details.append(f"  Arg '{arg_name}' mismatch: expected '{expected_value}', got '{actual_str}'")
                        score_cap = min(score_cap, 0.3)
                else:
                    # Substring match (default for free-text args)
                    actual_str = str(actual_value).lower()
                    if str(expected_value).lower() in actual_str:
                        details.append(f"  Arg '{arg_name}' contains '{expected_value}'")
                    else:
                        details.append(f"  Arg '{arg_name}' missing substring '{expected_value}' in '{actual_str}'")
                        score_cap = min(score_cap, 0.5)

    # Check expects_final_text
    if assertions.get("expects_final_text", True) and (not final_text or not final_text.strip()):
        # Only penalize if we weren't expecting no tool calls (termination test
        # with no tools still needs text, but terminal tool tests don't)
        has_terminal = any(tc.get("_terminal", False) for tc in actual_tool_calls)
        if not has_terminal:
            details.append("Expected final text response, but none produced")
            score_cap = min(score_cap, 0.4)

    passed = score_cap >= 0.7
    return ToolCallCheckResult(
        passed=passed,
        score_cap=score_cap,
        details=details,
        tool_calls_found=[
            {
                "name": tc.get("function", {}).get("name"),
                "arguments": tc.get("function", {}).get("arguments"),
            }
            for tc in actual_tool_calls
        ],
    )


class JudgeEvaluator:
    """
    Orchestrates LLM-as-judge evaluation of assistant responses.

    This class handles:
    - Building judge prompts from criteria
    - Calling the judge model
    - Parsing structured responses
    - Performing basic checks (patterns, length, content)
    - Calculating costs and metrics
    """

    def __init__(self, judge_client: LLMClient, config: dict):
        """
        Initialize evaluator.

        Args:
            judge_client: LLMClient configured for judge model
            config: Configuration dict with quality_threshold, etc.
        """
        self.judge_client = judge_client
        self.quality_threshold = config.get("quality_threshold", 0.70)
        self.judge_model = config.get("judge_model", "anthropic/claude-opus-4.5")
        self.judge_pricing = get_model_pricing(f"openrouter/{self.judge_model}")

    def evaluate_response(
        self,
        test_name: str,
        test_category: str,
        context: dict[str, str],
        user_message: str,
        actual_response: str,
        criteria: EvaluationCriteria,
        model_tested: str,
        response_metrics: dict,
        tools_description: str | None = None,
        transcript: str | None = None,
    ) -> EvaluationResult:
        """
        Evaluate a single response against criteria.

        Steps:
        1. Perform basic checks (patterns, length, content)
        2. Build judge prompt from criteria and category
        3. Call judge model
        4. Parse structured response
        5. Combine scores
        6. Return complete EvaluationResult

        Args:
            test_name: Name of the test
            test_category: Category (reasoning, context_recall, etc.)
            context: Personal context dict
            user_message: The user's query
            actual_response: The assistant's response to evaluate
            criteria: EvaluationCriteria with qualities and checks
            model_tested: Model identifier for the response
            response_metrics: Dict with latency_ms and tokens

        Returns:
            Complete EvaluationResult with scores and metrics
        """
        # Perform basic checks first
        basic_checks = self._perform_basic_checks(actual_response, criteria)

        # Call judge for evaluation
        judge_start = time.time()
        try:
            judge_evaluation = self._call_judge(
                test_category=test_category,
                context=context,
                user_message=user_message,
                actual_response=actual_response,
                criteria=criteria,
                tools_description=tools_description,
                transcript=transcript,
            )
            judge_latency_ms = (time.time() - judge_start) * 1000

        except Exception as e:
            # Fallback to basic checks only on judge failure
            print(f"Warning: Judge evaluation failed: {e}. Using fallback evaluation.")
            judge_evaluation = self._fallback_evaluation(
                actual_response=actual_response,
                criteria=criteria,
                error=str(e),
            )
            judge_latency_ms = (time.time() - judge_start) * 1000
            judge_evaluation["tokens"] = {"prompt": 0, "completion": 0, "total": 0}
            judge_evaluation["cost_usd"] = 0.0

        # Combine judge evaluation with basic checks
        evaluation_score = self._combine_evaluations(judge_evaluation, basic_checks)

        # Determine pass/fail
        passed = (
            evaluation_score.overall_score >= self.quality_threshold
            and len(evaluation_score.forbidden_patterns_found) == 0
        )

        # Build complete result
        result = EvaluationResult(
            test_name=test_name,
            timestamp=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            model_tested=model_tested,
            judge_model=self.judge_model,
            test_category=test_category,
            context=context,
            user_message=user_message,
            actual_response=actual_response,
            evaluation=evaluation_score,
            passed=passed,
            quality_threshold=self.quality_threshold,
            response_cost_usd=response_metrics.get("cost_usd", 0.0),
            judge_cost_usd=judge_evaluation.get("cost_usd", 0.0),
            total_cost_usd=response_metrics.get("cost_usd", 0.0) + judge_evaluation.get("cost_usd", 0.0),
            response_latency_ms=response_metrics.get("latency_ms", 0.0),
            judge_latency_ms=judge_latency_ms,
            response_tokens=response_metrics.get("tokens", {}),
            judge_tokens=judge_evaluation.get("tokens", {}),
        )

        return result

    def _call_judge(
        self,
        test_category: str,
        context: dict,
        user_message: str,
        actual_response: str,
        criteria: EvaluationCriteria,
        tools_description: str | None = None,
        transcript: str | None = None,
    ) -> dict:
        """
        Call judge model for evaluation.

        Returns:
            Dict with scores, reasoning, tokens, and cost
        """
        # Build judge prompt
        messages = build_judge_prompt(
            category=test_category,
            context=context,
            user_message=user_message,
            actual_response=actual_response,
            criteria_qualities=criteria.qualities,
            forbidden_patterns=criteria.forbidden_patterns,
            tools_description=tools_description,
            transcript=transcript,
        )

        # Call judge via streaming
        stream = self.judge_client.chat_stream(messages)

        # Collect full response
        judge_output = ""
        for chunk in stream:
            judge_output += chunk

        # Get usage and calculate cost
        usage = stream.usage

        # Calculate cost using model pricing (same approach as production)
        if self.judge_pricing:
            cost_usd = self.judge_pricing.calculate_cost(
                usage.prompt_tokens,
                usage.completion_tokens,
            )
        else:
            cost_usd = 0.0

        # Parse judge response
        parsed = self._parse_judge_response(judge_output)

        # Add tokens and cost
        parsed["tokens"] = {
            "prompt": usage.prompt_tokens,
            "completion": usage.completion_tokens,
            "total": usage.total_tokens,
        }
        parsed["cost_usd"] = cost_usd

        return parsed

    def _parse_judge_response(self, judge_output: str) -> dict:
        """
        Parse judge response with error handling.

        Expects JSON format with dimension_scores, overall_score, reasoning, etc.
        Falls back to text parsing if JSON is malformed.
        """
        try:
            # Try to extract JSON from response
            json_match = re.search(r"\{.*\}", judge_output, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())

                # Validate required fields
                if "overall_score" not in data:
                    raise ValueError("Missing overall_score in judge response")

                return {
                    "overall_score": float(data.get("overall_score", 0.5)),
                    "dimension_scores": data.get("dimension_scores", {}),
                    "reasoning": data.get("reasoning", judge_output),
                    "passed_criteria": data.get("passed_criteria", []),
                    "failed_criteria": data.get("failed_criteria", []),
                }
            else:
                raise ValueError("No JSON found in response")

        except (json.JSONDecodeError, ValueError):
            # Fallback: Try to extract scores from text
            return self._fallback_parse(judge_output)

    def _fallback_parse(self, text: str) -> dict:
        """
        Extract scores from free-form text as fallback.

        Looks for patterns like "score: 0.8" or "overall: 0.9"
        Returns conservative estimates if nothing found.
        """
        # Try to find numeric scores in text
        score_pattern = r"(?:overall|score)[:\s]+([0-9.]+)"
        match = re.search(score_pattern, text.lower())

        overall_score = 0.5  # Conservative default
        if match:
            try:
                overall_score = float(match.group(1))
                # Clamp to [0, 1]
                overall_score = max(0.0, min(1.0, overall_score))
            except ValueError:
                pass

        return {
            "overall_score": overall_score,
            "dimension_scores": {},
            "reasoning": f"Fallback parsing used. Original text: {text[:200]}...",
            "passed_criteria": [],
            "failed_criteria": [],
        }

    def _fallback_evaluation(self, actual_response: str, criteria: EvaluationCriteria, error: str) -> dict:
        """
        Provide basic evaluation when judge fails.

        Uses only pattern matching and length checks.
        """
        basic_checks = self._perform_basic_checks(actual_response, criteria)

        # Conservative score since judge failed
        overall_score = 0.5
        if basic_checks["forbidden_patterns_found"]:
            overall_score = 0.3  # Penalize forbidden patterns
        elif basic_checks["content_checks_passed"]:
            overall_score = 0.6  # Slight bonus if content present

        return {
            "overall_score": overall_score,
            "dimension_scores": {},
            "reasoning": f"Judge evaluation failed: {error}. Using basic checks only.",
            "passed_criteria": [],
            "failed_criteria": [],
            "tokens": {"prompt": 0, "completion": 0, "total": 0},
            "cost_usd": 0.0,
        }

    def _perform_basic_checks(self, actual_response: str, criteria: EvaluationCriteria) -> dict:
        """
        Perform basic checks: length, forbidden patterns, expected content.

        Returns dict with check results.
        """
        response_lower = actual_response.lower()

        # Check forbidden patterns
        forbidden_found = []
        for pattern in criteria.forbidden_patterns:
            if pattern.lower() in response_lower:
                forbidden_found.append(pattern)

        # Check expected content
        content_found = []
        for content in criteria.expected_content:
            if content.lower() in response_lower:
                content_found.append(content)

        content_checks_passed = len(content_found) == len(criteria.expected_content)

        # Check length constraints
        response_length = len(actual_response)
        length_ok = True
        if criteria.min_length and response_length < criteria.min_length:
            length_ok = False
        if criteria.max_length and response_length > criteria.max_length:
            length_ok = False

        return {
            "forbidden_patterns_found": forbidden_found,
            "content_checks_passed": content_checks_passed,
            "content_found": content_found,
            "length_ok": length_ok,
            "response_length": response_length,
        }

    def _combine_evaluations(self, judge_eval: dict, basic_checks: dict) -> EvaluationScore:
        """
        Combine judge evaluation with basic checks.

        Basic checks can override judge (e.g., forbidden patterns always fail).
        """
        # Start with judge evaluation
        overall_score = judge_eval["overall_score"]
        dimension_scores = judge_eval.get("dimension_scores", {})
        reasoning = judge_eval.get("reasoning", "")
        passed_criteria = judge_eval.get("passed_criteria", [])
        failed_criteria = judge_eval.get("failed_criteria", [])

        # Override with basic checks
        forbidden_found = basic_checks["forbidden_patterns_found"]
        if forbidden_found:
            # Forbidden patterns are a critical failure
            overall_score = min(overall_score, 0.3)
            reasoning += f"\n\nForbidden patterns detected: {', '.join(forbidden_found)}"
            failed_criteria.append("no_forbidden_patterns")

        if not basic_checks["content_checks_passed"]:
            reasoning += f"\n\nExpected content missing: {basic_checks.get('content_found', [])}"

        if not basic_checks["length_ok"]:
            reasoning += f"\n\nLength constraint violated (length: {basic_checks['response_length']})"

        return EvaluationScore(
            overall_score=overall_score,
            dimension_scores=dimension_scores,
            reasoning=reasoning.strip(),
            passed_criteria=passed_criteria,
            failed_criteria=failed_criteria,
            forbidden_patterns_found=forbidden_found,
            content_checks_passed=basic_checks["content_checks_passed"],
            themes_present=[],  # Would need NLP to extract themes
        )
