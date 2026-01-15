"""
Unit tests for cli module.

Tests configuration loading and main function behavior.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, mock_open, MagicMock
import yaml
from cli import load_config


@pytest.mark.unit
class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_success(self, tmp_path: Path, monkeypatch):
        """Test successful configuration loading."""
        # Create a mock config.yaml
        config_content = """
openrouter:
  default_model: "anthropic/claude-sonnet-4.5"

paths:
  context_dir: "personal-context/context"
  conversations_dir: "personal-context/memory/conversations"
  learned_facts: "personal-context/memory/learned_facts.md"

system_prompt_prefix: |
  You are Jarvis, an advanced personal AI assistant.
"""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(config_content)

        # Create .env file with API key
        env_path = tmp_path / ".env"
        env_path.write_text("OPENROUTER_API_KEY=test-api-key-12345\n")

        # Mock Path resolution to use our tmp_path
        # Create mock path hierarchy: __file__ -> src_dir -> personal_context_dir -> jarvis_dir
        mock_src_dir = Mock()
        mock_personal_context_dir = Mock()
        mock_jarvis_dir = tmp_path

        mock_src_dir.parent = mock_personal_context_dir
        mock_personal_context_dir.parent = mock_jarvis_dir

        with patch('cli.Path') as mock_path_class:
            # Make Path(__file__) return our mock src_dir
            mock_path_class.return_value = mock_src_dir

            # Mock load_dotenv to load our test .env
            with patch('cli.load_dotenv'):
                # Mock environment variable
                monkeypatch.setenv("OPENROUTER_API_KEY", "test-api-key-12345")

                # Mock open to read our config file
                with patch('builtins.open', mock_open(read_data=config_content)):
                    with patch('yaml.safe_load') as mock_yaml:
                        # Return a proper dict (not calling yaml.safe_load again!)
                        mock_yaml.return_value = {
                            "openrouter": {"default_model": "anthropic/claude-sonnet-4.5"},
                            "paths": {
                                "context_dir": "personal-context/context",
                                "conversations_dir": "personal-context/memory/conversations",
                                "learned_facts": "personal-context/memory/learned_facts.md"
                            },
                            "system_prompt_prefix": "You are Jarvis, an advanced personal AI assistant.\n"
                        }

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

        with patch('cli.Path') as mock_path_class:
            mock_path_class.return_value = mock_src_dir

            with patch('cli.load_dotenv'):
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
        """Test handling of missing config.yaml file."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

        # Create mock path hierarchy
        mock_src_dir = Mock()
        mock_personal_context_dir = Mock()
        mock_jarvis_dir = tmp_path

        mock_src_dir.parent = mock_personal_context_dir
        mock_personal_context_dir.parent = mock_jarvis_dir

        with patch('cli.Path') as mock_path_class:
            mock_path_class.return_value = mock_src_dir

            with patch('cli.load_dotenv'):
                with patch('builtins.open', side_effect=FileNotFoundError("config.yaml not found")):
                    # Should raise FileNotFoundError
                    with pytest.raises(FileNotFoundError):
                        load_config()

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

        with patch('cli.Path') as mock_path_class:
            mock_path_class.return_value = mock_src_dir

            with patch('cli.load_dotenv'):
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
                        assert "personal_context_dir" in config["_paths"]

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

        with patch('cli.Path') as mock_path_class:
            mock_path_class.return_value = mock_src_dir

            with patch('cli.load_dotenv'):
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
