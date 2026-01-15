"""
Shared pytest fixtures for Jarvis tests.

This module provides fixtures that can be used across all test files.
"""

import sys
from pathlib import Path
from typing import Generator
import pytest
from unittest.mock import Mock, MagicMock

# Add the src directory to the path so we can import modules
src_dir = Path(__file__).parent.parent / "personal-context" / "src"
sys.path.insert(0, str(src_dir))


# ==================== Path Fixtures ====================

@pytest.fixture
def project_root() -> Path:
    """Path to the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def tests_dir() -> Path:
    """Path to the tests directory."""
    return Path(__file__).parent


@pytest.fixture
def fixtures_dir(tests_dir: Path) -> Path:
    """Path to the fixtures directory."""
    return tests_dir / "fixtures"


@pytest.fixture
def context_fixtures_dir(fixtures_dir: Path) -> Path:
    """Path to the context fixtures directory."""
    return fixtures_dir / "context"


# ==================== Temp Directory Fixtures ====================

@pytest.fixture
def temp_context_dir(tmp_path: Path) -> Path:
    """Temporary directory for context files."""
    context_dir = tmp_path / "context"
    context_dir.mkdir()
    return context_dir


@pytest.fixture
def temp_conversations_dir(tmp_path: Path) -> Path:
    """Temporary directory for conversation logs."""
    conversations_dir = tmp_path / "conversations"
    conversations_dir.mkdir()
    return conversations_dir


# ==================== Context File Fixtures ====================

@pytest.fixture
def sample_profile(temp_context_dir: Path) -> Path:
    """Create a sample profile.md file."""
    profile_path = temp_context_dir / "profile.md"
    profile_path.write_text(
        "I am a software engineer with 10 years of experience.\n"
        "I specialize in Python and machine learning.\n"
        "I'm currently learning about LLM applications."
    )
    return profile_path


@pytest.fixture
def sample_preferences(temp_context_dir: Path) -> Path:
    """Create a sample preferences.md file."""
    prefs_path = temp_context_dir / "preferences.md"
    prefs_path.write_text(
        "- Be concise and technical\n"
        "- Avoid unnecessary pleasantries\n"
        "- Use technical jargon appropriately"
    )
    return prefs_path


@pytest.fixture
def sample_current_focus(temp_context_dir: Path) -> Path:
    """Create a sample current_focus.md file."""
    focus_path = temp_context_dir / "current_focus.md"
    focus_path.write_text(
        "I'm currently building a personal AI assistant called Jarvis.\n"
        "My main focus is implementing a testing framework this week."
    )
    return focus_path


@pytest.fixture
def sample_context_all_files(
    sample_profile: Path,
    sample_preferences: Path,
    sample_current_focus: Path,
    temp_context_dir: Path
) -> Path:
    """Create all context files and return the context directory."""
    return temp_context_dir


# ==================== Config Fixtures ====================

@pytest.fixture
def sample_config(tmp_path: Path) -> dict:
    """Sample configuration dictionary."""
    return {
        "openrouter": {
            "api_key": "test-api-key-12345",
            "default_model": "anthropic/claude-sonnet-4.5"
        },
        "paths": {
            "context_dir": "personal-context/context",
            "conversations_dir": "personal-context/memory/conversations",
            "learned_facts": "personal-context/memory/learned_facts.md"
        },
        "system_prompt_prefix": "You are Jarvis, an advanced personal AI assistant.",
        "_paths": {
            "jarvis_dir": tmp_path,
            "personal_context_dir": tmp_path / "personal-context"
        }
    }


# ==================== Mock LiteLLM Fixtures ====================

@pytest.fixture
def mock_litellm_chunk():
    """Create a mock LiteLLM streaming chunk."""
    def create_chunk(content: str):
        chunk = Mock()
        chunk.choices = [Mock()]
        chunk.choices[0].delta = Mock()
        chunk.choices[0].delta.content = content
        return chunk
    return create_chunk


@pytest.fixture
def mock_litellm_response():
    """Create a mock LiteLLM response with usage data."""
    response = Mock()
    response.usage = Mock()
    response.usage.prompt_tokens = 100
    response.usage.completion_tokens = 50
    response.usage.total_tokens = 150
    return response


@pytest.fixture
def mock_litellm_stream(mock_litellm_chunk, mock_litellm_response):
    """Create a mock LiteLLM streaming response."""
    def create_stream(text_chunks: list[str]):
        """Create a generator that yields chunks and has usage attribute."""
        chunks = [mock_litellm_chunk(chunk) for chunk in text_chunks]

        # Create an iterator with usage attribute
        class MockStream:
            def __init__(self, chunks, response):
                self.chunks = iter(chunks)
                self.usage = response.usage
                self.response = response

            def __iter__(self):
                return self.chunks

            def __next__(self):
                return next(self.chunks)

        return MockStream(chunks, mock_litellm_response)

    return create_stream


# ==================== Pricing Fixtures ====================

@pytest.fixture
def sample_pricing_data() -> dict:
    """Sample pricing data from OpenRouter API."""
    return {
        "data": [
            {
                "id": "anthropic/claude-sonnet-4.5",
                "pricing": {
                    "prompt": "0.000003",
                    "completion": "0.000015"
                }
            },
            {
                "id": "anthropic/claude-opus-4",
                "pricing": {
                    "prompt": "0.000015",
                    "completion": "0.000075"
                }
            },
            {
                "id": "openai/gpt-4",
                "pricing": {
                    "prompt": "0.00003",
                    "completion": "0.00006"
                }
            }
        ]
    }


# ==================== Time Freezing Fixtures ====================

@pytest.fixture
def frozen_time():
    """Freeze time at a specific datetime for consistent timestamp testing."""
    from freezegun import freeze_time
    with freeze_time("2026-01-15 14:30:00"):
        yield


# ==================== Cleanup ====================

@pytest.fixture(autouse=True)
def reset_lru_cache():
    """Reset LRU caches between tests to ensure isolation."""
    yield
    # Clear pricing cache after each test
    try:
        from pricing import fetch_all_pricing
        fetch_all_pricing.cache_clear()
    except ImportError:
        pass
