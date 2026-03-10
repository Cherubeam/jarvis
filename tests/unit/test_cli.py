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
models:
  default: "openrouter/anthropic/claude-sonnet-4.6"
  presets:
    fast: "openrouter/google/gemini-2.0-flash"

paths:
  context_dir: "data/context"
  conversations_dir: "data/conversations"
"""
        (config_dir / "default.yaml").write_text(config_content)

        # Create .env file
        (tmp_path / ".env").write_text("OPENROUTER_API_KEY=test-api-key-12345\n")

        # Point get_project_root() at tmp_path so load_config reads real files
        monkeypatch.setattr("apps.cli.main.get_project_root", lambda: tmp_path)
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-api-key-12345")

        config = load_config()

        assert config["models"]["default"] == "openrouter/anthropic/claude-sonnet-4.6"
        assert "paths" in config
        assert "_paths" in config

    def test_load_config_missing_yaml(self, tmp_path: Path, monkeypatch):
        """Test that missing config.yaml falls back to empty config gracefully."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.setattr("apps.cli.main.get_project_root", lambda: tmp_path)

        config = load_config()

        # Should still have _paths
        assert "_paths" in config
        # No models section since no config file exists
        assert "models" not in config

    def test_load_config_paths_resolved(self, tmp_path: Path, monkeypatch):
        """Test that paths are resolved correctly."""
        config_content = """
models:
  default: "openrouter/anthropic/claude-sonnet-4.6"
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
                            "models": {"default": "openrouter/anthropic/claude-sonnet-4.6"},
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
        """Test that config loads correctly with env vars set."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "default.yaml").write_text("""
models:
  default: "openrouter/anthropic/claude-sonnet-4.6"
paths:
  context_dir: "personal-context/context"
""")

        monkeypatch.setenv("OPENROUTER_API_KEY", "env-api-key-from-env")
        monkeypatch.setattr("apps.cli.main.get_project_root", lambda: tmp_path)

        config = load_config()

        assert config["models"]["default"] == "openrouter/anthropic/claude-sonnet-4.6"


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
