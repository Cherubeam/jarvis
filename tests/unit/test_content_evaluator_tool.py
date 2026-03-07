"""
Unit tests for the content-evaluator tool factory.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from packages.core.tools.base import ToolDefinition
from packages.core.tools.content_evaluator import make_content_evaluator_tool
from packages.core.llm_client import LLMClient


SKILL_MD_CONTENT = """\
---
name: content-evaluator
description: Evaluates written content through five lenses.
---

# Content Evaluator

Evaluate content through five lenses.
"""


@pytest.fixture
def skill_dir(tmp_path):
    """Create a minimal content-evaluator skill directory."""
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text(SKILL_MD_CONTENT)
    return tmp_path


@pytest.fixture
def skill_dir_with_py(skill_dir):
    """Skill directory with a skill.py that sets temperature."""
    skill_py = skill_dir / "skill.py"
    skill_py.write_text(
        'SKILL_CONFIG = {"temperature": 0.9, "max_tokens": 4096}\n'
    )
    return skill_dir


@pytest.fixture
def mock_client():
    client = Mock(spec=LLMClient)
    response = Mock()
    response.choices = [Mock()]
    response.choices[0].message.content = "Great evaluation result."
    client.complete.return_value = response
    return client


@pytest.mark.unit
class TestContentEvaluatorTool:

    def test_factory_returns_tool_definition(self, skill_dir, mock_client):
        tool = make_content_evaluator_tool(skill_dir, mock_client, "test-model")

        assert isinstance(tool, ToolDefinition)
        assert tool.name == "evaluate_content"
        assert "content" in tool.parameters["properties"]
        assert "audience" in tool.parameters["properties"]
        assert tool.parameters["required"] == ["content"]

    def test_execute_calls_llm_complete(self, skill_dir, mock_client):
        tool = make_content_evaluator_tool(skill_dir, mock_client, "test-model")

        result = tool.execute(content="My blog post content here.")

        mock_client.complete.assert_called_once()
        call_kwargs = mock_client.complete.call_args
        messages = call_kwargs[0][0]
        assert messages[0]["role"] == "system"
        assert "Content Evaluator" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert "My blog post content here." in messages[1]["content"]
        assert result == "Great evaluation result."

    def test_execute_passes_temperature(self, skill_dir, mock_client):
        tool = make_content_evaluator_tool(skill_dir, mock_client, "test-model")
        tool.execute(content="test")

        call_kwargs = mock_client.complete.call_args
        assert call_kwargs[1]["temperature"] == 0.8  # default

    def test_execute_includes_audience(self, skill_dir, mock_client):
        tool = make_content_evaluator_tool(skill_dir, mock_client, "test-model")
        tool.execute(content="My post", audience="Engineering managers")

        messages = mock_client.complete.call_args[0][0]
        assert "Engineering managers" in messages[1]["content"]

    def test_execute_handles_llm_failure(self, skill_dir, mock_client):
        mock_client.complete.side_effect = RuntimeError("API timeout")
        tool = make_content_evaluator_tool(skill_dir, mock_client, "test-model")

        result = tool.execute(content="test")
        assert "Content evaluation failed" in result
        assert "API timeout" in result

    def test_execute_handles_empty_response(self, skill_dir, mock_client):
        mock_client.complete.return_value.choices[0].message.content = None
        tool = make_content_evaluator_tool(skill_dir, mock_client, "test-model")

        result = tool.execute(content="test")
        assert result == "No evaluation generated."
