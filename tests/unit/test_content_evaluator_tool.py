"""
Unit tests for the content-evaluator tool factory.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from packages.core.llm_client import LLMClient
from packages.core.tools.base import ToolDefinition
from packages.core.tools.content_evaluator import make_content_evaluator_tool

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
    skill_py.write_text('SKILL_CONFIG = {"temperature": 0.9, "max_tokens": 4096}\n')
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
        params = tool.parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"content", "audience"}
        assert params["properties"]["content"]["type"] == "string"
        assert params["properties"]["audience"]["type"] == "string"
        assert params["required"] == ["content"]

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
        assert messages[1]["content"] == "Target audience: Engineering managers\n\nMy post"

    def test_execute_handles_llm_failure(self, skill_dir, mock_client):
        mock_client.complete.side_effect = RuntimeError("API timeout")
        tool = make_content_evaluator_tool(skill_dir, mock_client, "test-model")

        result = tool.execute(content="test")
        assert result == "Content evaluation failed: API timeout"

    def test_execute_handles_empty_response(self, skill_dir, mock_client):
        mock_client.complete.return_value.choices[0].message.content = None
        tool = make_content_evaluator_tool(skill_dir, mock_client, "test-model")

        result = tool.execute(content="test")
        assert result == "No evaluation generated."

    def test_skill_py_temperature_override(self, skill_dir_with_py, mock_client):
        """skill.py SKILL_CONFIG temperature overrides the default 0.8."""
        mock_module = MagicMock()
        mock_module.SKILL_CONFIG = {"temperature": 0.9}
        with patch("packages.core.tools.content_evaluator._import_skill_module", return_value=mock_module):
            tool = make_content_evaluator_tool(skill_dir_with_py, mock_client, "test-model")
        tool.execute(content="test")

        call_kwargs = mock_client.complete.call_args
        assert call_kwargs[1]["temperature"] == 0.9

    def test_model_passed_to_llm_client(self, skill_dir, mock_client):
        tool = make_content_evaluator_tool(skill_dir, mock_client, "gpt-4")
        tool.execute(content="test")

        call_kwargs = mock_client.complete.call_args
        assert call_kwargs[1]["model"] == "gpt-4"

    def test_system_prompt_from_skill_md(self, skill_dir, mock_client):
        """System prompt is the body of SKILL.md (after frontmatter), stripped."""
        tool = make_content_evaluator_tool(skill_dir, mock_client, "test-model")
        tool.execute(content="test")

        messages = mock_client.complete.call_args[0][0]
        system_content = messages[0]["content"]
        # Body after frontmatter, stripped
        assert system_content.startswith("# Content Evaluator")
        assert "Evaluate content through five lenses." in system_content
