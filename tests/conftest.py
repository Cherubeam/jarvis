"""
Shared pytest fixtures for Jarvis tests.

This module provides fixtures that can be used across all test files.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

# Add the project root to the path so we can import packages
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Also add old path for backward compatibility during migration
src_dir = project_root / "personal-context" / "src"
if src_dir.exists():
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
def sample_personal_context(temp_context_dir: Path) -> Path:
    """Create a sample personal_context.md file."""
    path = temp_context_dir / "personal_context.md"
    path.write_text(
        "I am a software engineer with 10 years of experience.\n"
        "I specialize in Python and machine learning.\n"
        "I'm currently learning about LLM applications."
    )
    return path


@pytest.fixture
def sample_professional_context(temp_context_dir: Path) -> Path:
    """Create a sample professional_context.md file."""
    path = temp_context_dir / "professional_context.md"
    path.write_text(
        "Currently working as a consultant and agile coach.\n"
        "Background in humanities and product management.\n"
        "Transitioning toward AI engineering."
    )
    return path


@pytest.fixture
def sample_preferences(temp_context_dir: Path) -> Path:
    """Create a sample preferences.md file."""
    prefs_path = temp_context_dir / "preferences.md"
    prefs_path.write_text(
        "- Be concise and technical\n- Avoid unnecessary pleasantries\n- Use technical jargon appropriately"
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
    sample_personal_context: Path,
    sample_professional_context: Path,
    sample_preferences: Path,
    sample_current_focus: Path,
    temp_context_dir: Path,
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
            "default_model": "anthropic/claude-sonnet-4.5",
        },
        "paths": {
            "context_dir": "data/context",
            "conversations_dir": "data/conversations",
            "learned_facts": "data/learned_facts.md",
        },
        "_paths": {
            "jarvis_dir": tmp_path,
        },
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
                "pricing": {"prompt": "0.000003", "completion": "0.000015"},
            },
            {
                "id": "anthropic/claude-opus-4",
                "pricing": {"prompt": "0.000015", "completion": "0.000075"},
            },
            {"id": "openai/gpt-4", "pricing": {"prompt": "0.00003", "completion": "0.00006"}},
        ]
    }


# ==================== Schema Config Fixtures ====================


@pytest.fixture
def sample_model_config() -> dict:
    """Sample model configuration for conversation schema."""
    return {
        "id": "anthropic/claude-sonnet-4.5",
        "provider": "openrouter",
        "parameters": {"temperature": 0.7, "max_tokens": 4096},
    }


@pytest.fixture
def sample_agent_config() -> dict:
    """Sample agent configuration for conversation schema."""
    return {
        "name": "JARVIS",
        "system_prompt_hash": "sha256:a1b2c3d4e5f67890",
        "tools": [],
        "metadata": {},
    }


@pytest.fixture
def sample_context_snapshot() -> dict:
    """Sample context snapshot for conversation schema."""
    return {
        "files_loaded": [
            {
                "path": "data/context/personal_context.md",
                "hash": "sha256:abcdef1234567890",
                "size_bytes": 342,
            },
        ],
        "metadata": {},
    }


@pytest.fixture
def sample_environment() -> dict:
    """Sample environment info for conversation schema."""
    return {
        "client": "cli",
        "client_version": "0.3.0",
        "platform": "darwin",
        "python_version": "3.13.1",
        "metadata": {},
    }


# ==================== Time Freezing Fixtures ====================


@pytest.fixture
def frozen_time():
    """Freeze time at a specific datetime for consistent timestamp testing."""
    from freezegun import freeze_time

    with freeze_time("2026-01-15 14:30:00"):
        yield


# ==================== Obsidian Vault Fixtures ====================


@pytest.fixture
def temp_vault(tmp_path: Path) -> Path:
    """Create a temporary Obsidian vault with Daily Notes directory."""
    daily_dir = tmp_path / "Daily Notes"
    daily_dir.mkdir()
    return tmp_path


@pytest.fixture
def sample_vault_config(temp_vault: Path):
    """Sample VaultConfig pointing at the temp vault."""
    from packages.core.filesystem_access import AccessLevel, AccessRule, FilesystemGuard
    from packages.integrations.obsidian.vault import VaultConfig

    daily_dir = temp_vault / "Daily Notes"
    guard = FilesystemGuard(
        [
            AccessRule(path=daily_dir, access=AccessLevel.READ_WRITE),
        ]
    )
    return VaultConfig(
        vault_path=temp_vault,
        filesystem_guard=guard,
        daily_note_path_format="Daily Notes/%Y-%m-%d",
        enabled=True,
    )


@pytest.fixture
def daily_note_with_callout(temp_vault: Path) -> Path:
    """Create a daily note with a JARVIS callout block."""
    note = temp_vault / "Daily Notes" / "2026-02-09.md"
    note.write_text(
        "# 2026-02-09\n"
        "\n"
        "## Notes\n"
        "Had a productive day.\n"
        "\n"
        "> [!JARVIS]\n"
        "> Morning: reviewed code architecture\n"
        "\n"
        "## Tasks\n"
        "- Finish integration\n",
        encoding="utf-8",
    )
    return note


# ==================== Cleanup ====================


@pytest.fixture(autouse=True)
def reset_lru_cache():
    """Placeholder for test isolation (pricing cache removed in favour of litellm.model_cost)."""
    yield


# ==================== LLM-as-Judge Evaluation ====================


def pytest_addoption(parser):
    """Add custom command line options for LLM-as-judge evaluation."""
    parser.addoption(
        "--evaluate",
        action="store_true",
        default=False,
        help="Run actual LLM calls and judge evaluation for golden tests (incurs cost)",
    )
    parser.addoption(
        "--judge-model",
        action="store",
        default="anthropic/claude-opus-4.5",
        help="Model to use as judge (default: claude-opus-4.5)",
    )
    parser.addoption(
        "--quality-threshold",
        action="store",
        type=float,
        default=0.70,
        help="Minimum quality score to pass (default: 0.70)",
    )


def pytest_configure(config):
    """Configure pytest with custom markers and evaluation config."""
    config.addinivalue_line(
        "markers",
        "evaluate: Mark test as requiring LLM evaluation (auto-skipped without --evaluate)",
    )

    # Store evaluation config for access in tests
    config.evaluation_enabled = config.getoption("--evaluate")
    config.judge_model = config.getoption("--judge-model")
    config.quality_threshold = config.getoption("--quality-threshold")


@pytest.fixture(scope="class")
def evaluation_config(request):
    """Provide evaluation configuration to tests."""
    return {
        "enabled": request.config.evaluation_enabled,
        "judge_model": request.config.judge_model,
        "quality_threshold": request.config.quality_threshold,
    }


@pytest.fixture(scope="class")
def evaluator(evaluation_config):
    """Create JudgeEvaluator if evaluation is enabled."""
    if not evaluation_config["enabled"]:
        pytest.skip("Evaluation not enabled (use --evaluate flag)")

    # Import here to avoid import errors if modules don't exist yet
    import os

    sys.path.insert(0, str(Path(__file__).parent / "golden"))
    from evaluator import JudgeEvaluator

    # Try new import path first, fall back to old
    try:
        from packages.core.llm_client import LLMClient
    except ImportError:
        from llm_client import LLMClient

    # Check for API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        pytest.skip("OPENROUTER_API_KEY environment variable not set")

    # Create judge client
    judge_client = LLMClient(
        api_keys={"openrouter": api_key},
        default_model=f"openrouter/{evaluation_config['judge_model']}",
    )

    return JudgeEvaluator(
        judge_client=judge_client,
        config=evaluation_config,
    )


@pytest.fixture(scope="class")
def result_storage():
    """Provide ResultStorage instance for golden tests."""
    sys.path.insert(0, str(Path(__file__).parent / "golden"))
    from result_storage import ResultStorage

    results_dir = Path(__file__).parent / "golden" / "results"
    return ResultStorage(results_dir)
