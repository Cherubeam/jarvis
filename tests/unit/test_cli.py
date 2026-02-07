"""
Unit tests for cli module.

Tests configuration loading and main function behavior.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, mock_open, MagicMock
import yaml

from apps.cli.main import load_config


@pytest.mark.unit
class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_success(self, tmp_path: Path, monkeypatch):
        """Test successful configuration loading."""
        # Create real config file at expected location
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_content = """
openrouter:
  default_model: "anthropic/claude-sonnet-4.5"

paths:
  context_dir: "data/context"
  conversations_dir: "data/conversations"

system_prompt_prefix: |
  You are Jarvis, an advanced personal AI assistant.
"""
        (config_dir / "default.yaml").write_text(config_content)

        # Create .env file
        (tmp_path / ".env").write_text("OPENROUTER_API_KEY=test-api-key-12345\n")

        # Point get_project_root() at tmp_path so load_config reads real files
        monkeypatch.setattr("apps.cli.main.get_project_root", lambda: tmp_path)
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-api-key-12345")

        config = load_config()

        assert config["openrouter"]["api_key"] == "test-api-key-12345"
        assert config["openrouter"]["default_model"] == "anthropic/claude-sonnet-4.5"
        assert "paths" in config
        assert "_paths" in config

    def test_load_config_missing_api_key(self, tmp_path: Path, monkeypatch):
        """Test that missing API key causes sys.exit."""
        config_content = """
openrouter:
  default_model: "anthropic/claude-sonnet-4.5"
paths:
  context_dir: "personal-context/context"
  conversations_dir: "personal-context/memory/conversations"
"""

        # Ensure API key is not in environment
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        # Create mock path hierarchy
        mock_src_dir = Mock()
        mock_personal_context_dir = Mock()
        mock_jarvis_dir = tmp_path

        mock_src_dir.parent = mock_personal_context_dir
        mock_personal_context_dir.parent = mock_jarvis_dir

        with patch('apps.cli.main.Path') as mock_path_class:
            mock_path_class.return_value = mock_src_dir

            with patch('apps.cli.main.load_dotenv'):
                with patch('builtins.open', mock_open(read_data=config_content)):
                    with patch('yaml.safe_load') as mock_yaml:
                        mock_yaml.return_value = {
                            "openrouter": {"default_model": "anthropic/claude-sonnet-4.5"},
                            "paths": {
                                "context_dir": "personal-context/context",
                                "conversations_dir": "personal-context/memory/conversations"
                            }
                        }

                        # Should call sys.exit(1)
                        with pytest.raises(SystemExit) as exc_info:
                            load_config()

                        assert exc_info.value.code == 1

    def test_load_config_missing_yaml(self, tmp_path: Path, monkeypatch):
        """Test that missing config.yaml falls back to empty config gracefully."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.setattr("apps.cli.main.get_project_root", lambda: tmp_path)

        config = load_config()

        assert config["openrouter"]["api_key"] == "test-key"
        assert "default_model" not in config["openrouter"]

    def test_load_config_paths_resolved(self, tmp_path: Path, monkeypatch):
        """Test that paths are resolved correctly."""
        config_content = """
openrouter:
  default_model: "anthropic/claude-sonnet-4.5"
paths:
  context_dir: "personal-context/context"
  conversations_dir: "personal-context/memory/conversations"
"""
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

        # Create mock path hierarchy
        mock_src_dir = Mock()
        mock_personal_context_dir = Mock()
        mock_jarvis_dir = tmp_path

        mock_src_dir.parent = mock_personal_context_dir
        mock_personal_context_dir.parent = mock_jarvis_dir

        with patch('apps.cli.main.Path') as mock_path_class:
            mock_path_class.return_value = mock_src_dir

            with patch('apps.cli.main.load_dotenv'):
                with patch('builtins.open', mock_open(read_data=config_content)):
                    with patch('yaml.safe_load') as mock_yaml:
                        mock_yaml.return_value = {
                            "openrouter": {"default_model": "anthropic/claude-sonnet-4.5"},
                            "paths": {
                                "context_dir": "personal-context/context",
                                "conversations_dir": "personal-context/memory/conversations"
                            }
                        }

                        config = load_config()

                        # Check that _paths were stored
                        assert "_paths" in config
                        assert "jarvis_dir" in config["_paths"]

    def test_load_config_env_override(self, tmp_path: Path, monkeypatch):
        """Test that environment variables are used for API key."""
        config_content = """
openrouter:
  default_model: "anthropic/claude-sonnet-4.5"
paths:
  context_dir: "personal-context/context"
"""

        # Set API key in environment
        monkeypatch.setenv("OPENROUTER_API_KEY", "env-api-key-from-env")

        # Create mock path hierarchy
        mock_src_dir = Mock()
        mock_personal_context_dir = Mock()
        mock_jarvis_dir = tmp_path

        mock_src_dir.parent = mock_personal_context_dir
        mock_personal_context_dir.parent = mock_jarvis_dir

        with patch('apps.cli.main.Path') as mock_path_class:
            mock_path_class.return_value = mock_src_dir

            with patch('apps.cli.main.load_dotenv'):
                with patch('builtins.open', mock_open(read_data=config_content)):
                    with patch('yaml.safe_load') as mock_yaml:
                        mock_yaml.return_value = {
                            "openrouter": {"default_model": "anthropic/claude-sonnet-4.5"},
                            "paths": {"context_dir": "personal-context/context"}
                        }

                        config = load_config()

                        # API key should come from environment
                        assert config["openrouter"]["api_key"] == "env-api-key-from-env"


@pytest.mark.unit
class TestMain:
    """Tests for main function.

    Note: Full testing of main() is complex due to interactive input.
    These tests cover key scenarios only.
    """

    def test_main_handles_quit(self):
        """Test that main() exits cleanly on 'quit' command."""
        # This would require mocking input() and the entire flow
        # Skipping for now as it's complex and main() is integration-level
        pytest.skip("Main function testing requires complex mocking of interactive input")

    def test_main_handles_ctrl_c(self):
        """Test that main() handles KeyboardInterrupt gracefully."""
        pytest.skip("Main function testing requires complex setup")

    def test_main_startup_info(self):
        """Test that main() prints startup information."""
        pytest.skip("Main function testing requires complex setup")
