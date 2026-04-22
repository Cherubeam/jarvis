"""
Golden test conversations runner with LLM-as-judge evaluation.

This module provides infrastructure for running and evaluating golden test conversations.
Use --evaluate flag to run actual LLM calls with judge evaluation.
"""

import os
import sys
import time
from pathlib import Path
from typing import Any

import pytest
import yaml

# Add project root and golden directory to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(Path(__file__).parent))

# Import evaluation modules (only when --evaluate is used)
try:
    # Imports are availability checks for the optional --evaluate path.
    from evaluator import EvaluationCriteria, JudgeEvaluator  # noqa: F401
    from result_storage import ResultStorage  # noqa: F401

    from packages.core.context_builder import build_system_prompt  # noqa: F401
    from packages.core.llm_client import LLMClient  # noqa: F401

    EVALUATION_AVAILABLE = True
except ImportError:
    EVALUATION_AVAILABLE = False


@pytest.fixture
def golden_conversations_dir() -> Path:
    """Path to the golden conversations directory."""
    return Path(__file__).parent / "conversations"


@pytest.fixture
def load_golden_test():
    """Factory fixture to load a golden test by filename."""

    def _load(filename: str) -> dict[str, Any]:
        test_path = Path(__file__).parent / "conversations" / filename
        with open(test_path) as f:
            return yaml.safe_load(f)

    return _load


@pytest.mark.golden
class TestGoldenConversationStructure:
    """
    Tests that validate golden conversation file structure.

    These tests ensure all golden test files are properly formatted
    and contain the required fields.
    """

    def test_all_golden_files_exist(self, golden_conversations_dir: Path):
        """Test that all expected golden test files exist."""
        expected_files = [
            "01_basic_qa.yaml",
            "02_context_recall.yaml",
            "03_multi_turn_reasoning.yaml",
            "04_personalization_tone.yaml",
            "05_technical_deep_dive.yaml",
            "06_current_focus_aware.yaml",
            "07_ambiguous_query.yaml",
            "08_preferences_adherence.yaml",
            "09_tool_calling.yaml",
            "10_delegation.yaml",
            "11_multi_step_tool_use.yaml",
            "12_tool_termination.yaml",
        ]

        for filename in expected_files:
            file_path = golden_conversations_dir / filename
            assert file_path.exists(), f"Golden test file missing: {filename}"

    def test_golden_file_structure_valid(self, golden_conversations_dir: Path):
        """Test that all golden test files have valid YAML structure."""
        yaml_files = list(golden_conversations_dir.glob("*.yaml"))
        assert len(yaml_files) >= 12, "Expected at least 12 golden test files"

        for yaml_file in yaml_files:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)

            # Required top-level fields (both schemas)
            assert "name" in data, f"{yaml_file.name}: missing 'name' field"
            assert "description" in data, f"{yaml_file.name}: missing 'description' field"
            assert "category" in data, f"{yaml_file.name}: missing 'category' field"
            assert "context" in data, f"{yaml_file.name}: missing 'context' field"

            # Agentic tests have 'tools' + 'prompt'; conversation tests have 'conversation'
            is_agentic = "tools" in data

            if is_agentic:
                assert "prompt" in data, f"{yaml_file.name}: agentic test missing 'prompt' field"
                assert isinstance(data["tools"], list), f"{yaml_file.name}: 'tools' must be a list"
                for tool in data["tools"]:
                    assert "name" in tool, f"{yaml_file.name}: tool missing 'name'"
                    assert "description" in tool, f"{yaml_file.name}: tool missing 'description'"
            else:
                assert "conversation" in data, f"{yaml_file.name}: missing 'conversation' field"
                conversation = data["conversation"]
                assert isinstance(conversation, list), f"{yaml_file.name}: conversation must be a list"
                assert len(conversation) >= 2, f"{yaml_file.name}: conversation must have at least user + assistant"


@pytest.mark.golden
@pytest.mark.evaluate
class TestGoldenConversations:
    """
    Golden conversation tests with LLM-as-judge evaluation.

    These tests represent real-world usage scenarios and are used to:
    1. Validate response quality across different models
    2. Catch regressions in behavior
    3. Establish quality baselines

    Run with: pytest tests/golden/ --evaluate
    Optional: pytest tests/golden/ --evaluate --judge-model=anthropic/claude-opus-4.5
    """

    @pytest.fixture(scope="class", autouse=True)
    def setup_evaluation(self, request, evaluation_config, result_storage):
        """Setup evaluation run if enabled."""
        if evaluation_config["enabled"]:
            model_tested = os.getenv("DEFAULT_MODEL", "anthropic/claude-sonnet-4.5")
            # Store on class object so all test methods can access via self
            request.cls.run_id = result_storage.start_run(
                model_tested=model_tested,
                judge_model=evaluation_config["judge_model"],
            )
            request.cls.results = []
            request.cls.model_tested = model_tested
        yield
        # Finalize run after all tests
        if evaluation_config["enabled"] and hasattr(request.cls, "results") and request.cls.results:
            result_storage.finalize_run(request.cls.run_id, request.cls.results)

    def _run_golden_test(
        self,
        test_file: str,
        evaluator,
        evaluation_config,
        result_storage,
    ):
        """
        Execute a golden test with evaluation.

        Steps:
        1. Load YAML test case
        2. Build context from YAML
        3. Execute conversation with model under test
        4. Evaluate response with judge
        5. Store result
        6. Assert on quality threshold
        """
        # Check if evaluation is enabled
        if not evaluation_config["enabled"]:
            pytest.skip("Use --evaluate flag to run golden tests")

        # Load test case
        test_path = Path(__file__).parent / "conversations" / test_file
        with open(test_path) as f:
            test_case = yaml.safe_load(f)

        # Setup model under test
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            pytest.fail("OPENROUTER_API_KEY environment variable not set")

        # Import modules here (already in path from conftest.py)
        try:
            from packages.core.llm_client import LLMClient
        except ImportError:
            from llm_client import LLMClient

        model_id = (
            f"openrouter/{self.model_tested}" if not self.model_tested.startswith("openrouter/") else self.model_tested
        )
        model_client = LLMClient(
            api_keys={"openrouter": api_key},
            default_model=model_id,
        )

        # Look up model pricing once (same approach as production StreamHandler)
        from packages.core.pricing import get_model_pricing

        pricing = get_model_pricing(model_id)

        # Extract context from test case
        context = test_case.get("context", {})

        # Build system prompt if context is provided
        system_prompt = "You are Jarvis, an advanced personal AI assistant."
        if context:
            context_parts = []
            for key, value in context.items():
                context_parts.append(f"{key.upper()}:\n{value}")
            if context_parts:
                system_prompt += "\n\n" + "\n\n".join(context_parts)

        # Branch: agentic tests (have 'tools' field) vs conversation tests
        if "tools" in test_case:
            self._run_agentic_test(
                test_case,
                model_client,
                system_prompt,
                context,
                evaluator,
                evaluation_config,
                result_storage,
                pricing,
            )
        else:
            self._run_conversation_test(
                test_case,
                model_client,
                system_prompt,
                context,
                evaluator,
                evaluation_config,
                result_storage,
                pricing,
            )

    @staticmethod
    def _calculate_cost(pricing, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost using ModelPricing (same approach as production StreamHandler)."""
        if pricing:
            return pricing.calculate_cost(prompt_tokens, completion_tokens)
        return 0.0

    def _run_conversation_test(
        self,
        test_case,
        model_client,
        system_prompt,
        context,
        evaluator,
        evaluation_config,
        result_storage,
        pricing,
    ):
        """Execute a conversation-based golden test (tests 01-08)."""
        from evaluator import EvaluationCriteria

        for turn in test_case["conversation"]:
            if turn["role"] == "user":
                user_message = turn["content"]

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ]

                start_time = time.time()
                stream = model_client.chat_stream(messages)

                response_text = ""
                for chunk in stream:
                    response_text += chunk

                response_latency = (time.time() - start_time) * 1000

                usage = stream.usage
                response_cost = self._calculate_cost(
                    pricing,
                    usage.prompt_tokens,
                    usage.completion_tokens,
                )

            elif turn["role"] == "assistant":
                criteria = EvaluationCriteria(
                    qualities=turn.get("expected_qualities", {}),
                    forbidden_patterns=turn.get("forbidden_patterns", []),
                    expected_content=turn.get("expected_content", []),
                    expected_themes=turn.get("expected_themes", []),
                    min_length=turn.get("min_length"),
                    max_length=turn.get("max_length"),
                )

                result = evaluator.evaluate_response(
                    test_name=test_case["name"],
                    test_category=test_case["category"],
                    context=context,
                    user_message=user_message,
                    actual_response=response_text,
                    criteria=criteria,
                    model_tested=self.model_tested,
                    response_metrics={
                        "latency_ms": response_latency,
                        "tokens": {
                            "prompt": usage.prompt_tokens,
                            "completion": usage.completion_tokens,
                            "total": usage.total_tokens,
                        },
                        "cost_usd": response_cost,
                    },
                )

                result_storage.save_result(self.run_id, result)
                self.results.append(result)

                assert result.passed, (
                    f"Test {result.test_name} failed quality threshold "
                    f"(score: {result.evaluation.overall_score:.2f}, "
                    f"threshold: {evaluation_config['quality_threshold']})\n"
                    f"Reason: {result.evaluation.reasoning}"
                )

    def _run_agentic_test(
        self,
        test_case,
        model_client,
        system_prompt,
        context,
        evaluator,
        evaluation_config,
        result_storage,
        pricing,
    ):
        """Execute an agentic golden test with tool calls (tests 09-12)."""
        from evaluator import EvaluationCriteria, evaluate_tool_calls
        from judge_prompts import format_tools_description, format_transcript

        tools_yaml = test_case["tools"]
        mock_results = test_case.get("mock_tool_results", {})
        assertions = test_case.get("assertions", {})
        evaluation = test_case.get("evaluation", {})
        user_message = test_case["prompt"]
        max_rounds = assertions.get("max_tool_call_rounds", 5)

        # Build terminal tool set
        terminal_tools = {t["name"] for t in tools_yaml if t.get("terminal", False)}

        # Convert tool defs to LiteLLM format
        tools_litellm = []
        for t in tools_yaml:
            tools_litellm.append(
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t.get("parameters", {"type": "object", "properties": {}}),
                    },
                }
            )

        # Build initial messages
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        # Track metrics across loop iterations
        all_tool_calls: list[dict] = []
        transcript_messages: list[dict] = []
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_cost = 0.0
        final_text: str | None = None
        start_time = time.time()

        # Agentic loop
        for _iteration in range(max_rounds):
            response = model_client.complete(messages, tools=tools_litellm)
            choice = response.choices[0]

            # Accumulate token usage
            usage = response.usage
            iter_prompt = getattr(usage, "prompt_tokens", 0)
            iter_completion = getattr(usage, "completion_tokens", 0)
            total_prompt_tokens += iter_prompt
            total_completion_tokens += iter_completion
            total_cost += self._calculate_cost(pricing, iter_prompt, iter_completion)

            msg = choice.message
            tool_calls = getattr(msg, "tool_calls", None) or []
            content = getattr(msg, "content", None) or ""

            if tool_calls:
                # Record tool calls
                tc_dicts = []
                for tc in tool_calls:
                    tc_dict = {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    # Mark terminal tools for later checks
                    if tc.function.name in terminal_tools:
                        tc_dict["_terminal"] = True
                    tc_dicts.append(tc_dict)
                    all_tool_calls.append(tc_dict)

                # Build assistant message for transcript and conversation
                assistant_msg = {"role": "assistant", "content": content, "tool_calls": tc_dicts}
                messages.append(assistant_msg)
                transcript_messages.append(assistant_msg)

                # Check for terminal tool — break immediately
                has_terminal = any(tc.function.name in terminal_tools for tc in tool_calls)
                if has_terminal:
                    break

                # Append mock tool results
                for tc in tool_calls:
                    mock_content = mock_results.get(tc.function.name, f"Error: unknown tool '{tc.function.name}'")
                    tool_msg = {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.function.name,
                        "content": mock_content,
                    }
                    messages.append(tool_msg)
                    transcript_messages.append(tool_msg)
            else:
                # Model produced text response — done
                final_text = content
                transcript_messages.append({"role": "assistant", "content": content})
                break
        else:
            # Max iterations exhausted without final text
            pytest.fail(f"Test {test_case['name']}: model did not converge in {max_rounds} iterations")

        response_latency = (time.time() - start_time) * 1000

        # Run programmatic tool call checks
        tool_check = evaluate_tool_calls(all_tool_calls, final_text, assertions)

        # Format transcript for judge and actual_response storage
        transcript_str = format_transcript(transcript_messages)
        tools_desc = format_tools_description(tools_yaml)

        # Build evaluation criteria from YAML evaluation section
        criteria = EvaluationCriteria(
            qualities=evaluation.get("expected_qualities", {}),
            forbidden_patterns=evaluation.get("forbidden_patterns", []),
            expected_content=evaluation.get("expected_content", []),
            expected_themes=evaluation.get("expected_themes", []),
            min_length=evaluation.get("min_length"),
            max_length=evaluation.get("max_length"),
        )

        # Use transcript as actual_response for judge
        actual_response_for_judge = transcript_str
        if final_text:
            actual_response_for_judge += f"\n\n[FINAL RESPONSE]\n{final_text}"

        # Call judge with tool_use-specific params
        result = evaluator.evaluate_response(
            test_name=test_case["name"],
            test_category=test_case["category"],
            context=context,
            user_message=user_message,
            actual_response=actual_response_for_judge,
            criteria=criteria,
            model_tested=self.model_tested,
            response_metrics={
                "latency_ms": response_latency,
                "tokens": {
                    "prompt": total_prompt_tokens,
                    "completion": total_completion_tokens,
                    "total": total_prompt_tokens + total_completion_tokens,
                },
                "cost_usd": total_cost,
            },
            tools_description=tools_desc,
            transcript=transcript_str,
        )

        # Apply programmatic score cap
        if tool_check.score_cap < 1.0:
            capped_score = min(result.evaluation.overall_score, tool_check.score_cap)
            result.evaluation.overall_score = capped_score
            result.evaluation.reasoning += (
                f"\n\nTool call checks: {'; '.join(tool_check.details)}\nScore capped at {tool_check.score_cap}"
            )
            result.passed = (
                capped_score >= evaluation_config["quality_threshold"]
                and len(result.evaluation.forbidden_patterns_found) == 0
            )

        result_storage.save_result(self.run_id, result)
        self.results.append(result)

        assert result.passed, (
            f"Test {result.test_name} failed "
            f"(score: {result.evaluation.overall_score:.2f}, "
            f"threshold: {evaluation_config['quality_threshold']})\n"
            f"Tool checks: {tool_check.details}\n"
            f"Reason: {result.evaluation.reasoning}"
        )

    def test_01_basic_qa(self, evaluator, evaluation_config, result_storage):
        """Test basic factual question answering."""
        self._run_golden_test("01_basic_qa.yaml", evaluator, evaluation_config, result_storage)

    def test_02_context_recall(self, evaluator, evaluation_config, result_storage):
        """Test that assistant recalls information from profile."""
        self._run_golden_test("02_context_recall.yaml", evaluator, evaluation_config, result_storage)

    def test_03_multi_turn_reasoning(self, evaluator, evaluation_config, result_storage):
        """Test multi-turn technical conversation with context retention."""
        self._run_golden_test("03_multi_turn_reasoning.yaml", evaluator, evaluation_config, result_storage)

    def test_04_personalization_tone(self, evaluator, evaluation_config, result_storage):
        """Test that assistant follows tone preferences."""
        self._run_golden_test("04_personalization_tone.yaml", evaluator, evaluation_config, result_storage)

    def test_05_technical_deep_dive(self, evaluator, evaluation_config, result_storage):
        """Test handling of complex technical questions."""
        self._run_golden_test("05_technical_deep_dive.yaml", evaluator, evaluation_config, result_storage)

    def test_06_current_focus_aware(self, evaluator, evaluation_config, result_storage):
        """Test awareness of current priorities from current_focus.md."""
        self._run_golden_test("06_current_focus_aware.yaml", evaluator, evaluation_config, result_storage)

    def test_07_ambiguous_query(self, evaluator, evaluation_config, result_storage):
        """Test graceful handling of ambiguous questions."""
        self._run_golden_test("07_ambiguous_query.yaml", evaluator, evaluation_config, result_storage)

    def test_08_preferences_adherence(self, evaluator, evaluation_config, result_storage):
        """Test following multiple preference guidelines simultaneously."""
        self._run_golden_test(
            "08_preferences_adherence.yaml",
            evaluator,
            evaluation_config,
            result_storage,
        )

    def test_09_tool_calling(self, evaluator, evaluation_config, result_storage):
        """Test that model calls the correct tool with appropriate arguments."""
        self._run_golden_test("09_tool_calling.yaml", evaluator, evaluation_config, result_storage)

    def test_10_delegation(self, evaluator, evaluation_config, result_storage):
        """Test that model delegates coding tasks to the developer agent."""
        self._run_golden_test("10_delegation.yaml", evaluator, evaluation_config, result_storage)

    def test_11_multi_step_tool_use(self, evaluator, evaluation_config, result_storage):
        """Test that model chains search then read to answer a question."""
        self._run_golden_test("11_multi_step_tool_use.yaml", evaluator, evaluation_config, result_storage)

    def test_12_tool_termination(self, evaluator, evaluation_config, result_storage):
        """Test that model answers directly without unnecessary tool calls."""
        self._run_golden_test("12_tool_termination.yaml", evaluator, evaluation_config, result_storage)


# Helper function for manual golden test evaluation (to be used in Phase 2)
def run_golden_test_manual(test_file: str):
    """
    Helper function to manually run a golden test conversation.

    Usage:
        python -c "from tests.golden.test_golden_conversations import run_golden_test_manual; \
                   run_golden_test_manual('01_basic_qa.yaml')"

    This function can be used during development to manually test conversations.
    """
    test_path = Path(__file__).parent / "conversations" / test_file
    with open(test_path) as f:
        test_case = yaml.safe_load(f)

    print(f"\n{'=' * 60}")
    print(f"Golden Test: {test_case['name']}")
    print(f"Description: {test_case['description']}")
    print(f"Category: {test_case['category']}")
    print(f"{'=' * 60}\n")

    # Print context if present
    if test_case["context"]:
        print("Context:")
        for key, value in test_case["context"].items():
            print(f"  {key}:")
            for line in value.strip().split("\n"):
                print(f"    {line}")
        print()

    # Print conversation
    print("Conversation:")
    for turn in test_case["conversation"]:
        if turn["role"] == "user":
            print(f"\n  User: {turn['content']}")
        else:
            print("\n  Expected Assistant Response:")
            if "expected_themes" in turn:
                print(f"    Themes: {', '.join(turn['expected_themes'])}")
            if "expected_qualities" in turn:
                print(f"    Qualities: {turn['expected_qualities']}")
            if "expected_content" in turn:
                print(f"    Content: {turn['expected_content']}")

    print(f"\n{'=' * 60}\n")
    print("To run this test with actual LLM:")
    print("1. Implement LLM call with context")
    print("2. Evaluate response against expected qualities")
    print("3. Use LLM-as-judge for automated evaluation (Phase 2)")
    print()
