"""
Golden test conversations runner.

This module provides infrastructure for running and evaluating golden test conversations.
For now, tests are marked as manual - they load and validate the YAML structure.

In Phase 2, these will be automated with LLM-as-judge evaluation.
"""

import pytest
import yaml
from pathlib import Path
from typing import Dict, Any, List


@pytest.fixture
def golden_conversations_dir() -> Path:
    """Path to the golden conversations directory."""
    return Path(__file__).parent / "conversations"


@pytest.fixture
def load_golden_test():
    """Factory fixture to load a golden test by filename."""
    def _load(filename: str) -> Dict[str, Any]:
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
        ]

        for filename in expected_files:
            file_path = golden_conversations_dir / filename
            assert file_path.exists(), f"Golden test file missing: {filename}"

    def test_golden_file_structure_valid(self, golden_conversations_dir: Path):
        """Test that all golden test files have valid YAML structure."""
        yaml_files = list(golden_conversations_dir.glob("*.yaml"))
        assert len(yaml_files) >= 8, "Expected at least 8 golden test files"

        for yaml_file in yaml_files:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)

            # Required top-level fields
            assert "name" in data, f"{yaml_file.name}: missing 'name' field"
            assert "description" in data, f"{yaml_file.name}: missing 'description' field"
            assert "category" in data, f"{yaml_file.name}: missing 'category' field"
            assert "context" in data, f"{yaml_file.name}: missing 'context' field"
            assert "conversation" in data, f"{yaml_file.name}: missing 'conversation' field"

            # Validate conversation structure
            conversation = data["conversation"]
            assert isinstance(conversation, list), f"{yaml_file.name}: conversation must be a list"
            assert len(conversation) >= 2, f"{yaml_file.name}: conversation must have at least user + assistant"


@pytest.mark.golden
@pytest.mark.slow
class TestGoldenConversations:
    """
    Golden conversation tests.

    These tests represent real-world usage scenarios and are used to:
    1. Validate response quality across different models
    2. Catch regressions in behavior
    3. Establish quality baselines

    Currently marked as manual/slow as they require actual LLM calls.
    In Phase 2, these will be automated with LLM-as-judge evaluation.
    """

    @pytest.mark.skip(reason="Manual test - requires LLM call and manual evaluation")
    def test_01_basic_qa(self, load_golden_test):
        """Test basic factual question answering."""
        test_case = load_golden_test("01_basic_qa.yaml")

        # TODO: Implement actual test execution
        # 1. Load context (if any)
        # 2. Send user message to LLM
        # 3. Get response
        # 4. Evaluate against expected_content and expected_qualities

        pytest.skip("Golden test implementation pending - Phase 2")

    @pytest.mark.skip(reason="Manual test - requires LLM call and manual evaluation")
    def test_02_context_recall(self, load_golden_test):
        """Test that assistant recalls information from profile."""
        test_case = load_golden_test("02_context_recall.yaml")
        pytest.skip("Golden test implementation pending - Phase 2")

    @pytest.mark.skip(reason="Manual test - requires LLM call and manual evaluation")
    def test_03_multi_turn_reasoning(self, load_golden_test):
        """Test multi-turn technical conversation with context retention."""
        test_case = load_golden_test("03_multi_turn_reasoning.yaml")
        pytest.skip("Golden test implementation pending - Phase 2")

    @pytest.mark.skip(reason="Manual test - requires LLM call and manual evaluation")
    def test_04_personalization_tone(self, load_golden_test):
        """Test that assistant follows tone preferences."""
        test_case = load_golden_test("04_personalization_tone.yaml")
        pytest.skip("Golden test implementation pending - Phase 2")

    @pytest.mark.skip(reason="Manual test - requires LLM call and manual evaluation")
    def test_05_technical_deep_dive(self, load_golden_test):
        """Test handling of complex technical questions."""
        test_case = load_golden_test("05_technical_deep_dive.yaml")
        pytest.skip("Golden test implementation pending - Phase 2")

    @pytest.mark.skip(reason="Manual test - requires LLM call and manual evaluation")
    def test_06_current_focus_aware(self, load_golden_test):
        """Test awareness of current priorities from current_focus.md."""
        test_case = load_golden_test("06_current_focus_aware.yaml")
        pytest.skip("Golden test implementation pending - Phase 2")

    @pytest.mark.skip(reason="Manual test - requires LLM call and manual evaluation")
    def test_07_ambiguous_query(self, load_golden_test):
        """Test graceful handling of ambiguous questions."""
        test_case = load_golden_test("07_ambiguous_query.yaml")
        pytest.skip("Golden test implementation pending - Phase 2")

    @pytest.mark.skip(reason="Manual test - requires LLM call and manual evaluation")
    def test_08_preferences_adherence(self, load_golden_test):
        """Test following multiple preference guidelines simultaneously."""
        test_case = load_golden_test("08_preferences_adherence.yaml")
        pytest.skip("Golden test implementation pending - Phase 2")


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

    print(f"\n{'='*60}")
    print(f"Golden Test: {test_case['name']}")
    print(f"Description: {test_case['description']}")
    print(f"Category: {test_case['category']}")
    print(f"{'='*60}\n")

    # Print context if present
    if test_case['context']:
        print("Context:")
        for key, value in test_case['context'].items():
            print(f"  {key}:")
            for line in value.strip().split('\n'):
                print(f"    {line}")
        print()

    # Print conversation
    print("Conversation:")
    for turn in test_case['conversation']:
        if turn['role'] == 'user':
            print(f"\n  User: {turn['content']}")
        else:
            print(f"\n  Expected Assistant Response:")
            if 'expected_themes' in turn:
                print(f"    Themes: {', '.join(turn['expected_themes'])}")
            if 'expected_qualities' in turn:
                print(f"    Qualities: {turn['expected_qualities']}")
            if 'expected_content' in turn:
                print(f"    Content: {turn['expected_content']}")

    print(f"\n{'='*60}\n")
    print("To run this test with actual LLM:")
    print("1. Implement LLM call with context")
    print("2. Evaluate response against expected qualities")
    print("3. Use LLM-as-judge for automated evaluation (Phase 2)")
    print()
