"""
Unit tests for cli module.

Tests configuration loading and main function behavior.
"""

from pathlib import Path

import pytest

from apps.cli.main import _deep_merge, load_config


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
    fast: "openrouter/google/gemini-2.5-flash"

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
        """Missing config files fall back to typed defaults (PR-8a behavior change).

        Previously the dict only contained sections present in YAML; now every
        section is always populated by the typed Settings defaults so callers
        never have to special-case absence.
        """
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.setattr("apps.cli.main.get_project_root", lambda: tmp_path)

        config = load_config()

        assert "_paths" in config
        assert config["models"]["default"] == "openrouter/qwen/qwen3.5-flash-02-23"
        assert config["outcomes"]["enabled"] is True

    def test_load_config_paths_resolved(self, tmp_path: Path, monkeypatch):
        """Test that paths are resolved correctly."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "default.yaml").write_text("""
models:
  default: "openrouter/anthropic/claude-sonnet-4.6"
paths:
  context_dir: "personal-context/context"
  conversations_dir: "personal-context/memory/conversations"
""")

        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.setattr("apps.cli.main.get_project_root", lambda: tmp_path)

        config = load_config()

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

    def test_load_config_local_override_preserves_sibling_keys(self, tmp_path: Path, monkeypatch):
        """local.yaml partial override must not clobber sibling defaults (deep merge)."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "default.yaml").write_text("""
obsidian:
  enabled: true
  vault_path: "/default/vault"
  writing:
    slip_box:
      target_dir: "inbox"
      template_path: "templates/slip.md"
""")
        (config_dir / "local.yaml").write_text("""
obsidian:
  vault_path: "/my/real/vault"
""")

        monkeypatch.setattr("apps.cli.main.get_project_root", lambda: tmp_path)

        config = load_config()

        # Overridden key wins
        assert config["obsidian"]["vault_path"] == "/my/real/vault"
        # Sibling keys from default survive
        assert config["obsidian"]["enabled"] is True
        assert config["obsidian"]["writing"]["slip_box"]["target_dir"] == "inbox"
        assert config["obsidian"]["writing"]["slip_box"]["template_path"] == "templates/slip.md"


@pytest.mark.unit
class TestDeepMerge:
    """Tests for _deep_merge helper."""

    def test_merges_nested_dicts(self):
        base = {"a": {"x": 1, "y": 2}}
        override = {"a": {"y": 99, "z": 3}}
        assert _deep_merge(base, override) == {"a": {"x": 1, "y": 99, "z": 3}}

    def test_override_wins_for_primitives(self):
        assert _deep_merge({"k": 1}, {"k": 2}) == {"k": 2}

    def test_lists_are_replaced_not_concatenated(self):
        base = {"servers": ["a", "b"]}
        override = {"servers": ["c"]}
        assert _deep_merge(base, override) == {"servers": ["c"]}

    def test_override_adds_new_keys(self):
        assert _deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}

    def test_dict_replaces_non_dict(self):
        # If base has a scalar and override has a dict, override wins.
        assert _deep_merge({"k": 1}, {"k": {"nested": True}}) == {"k": {"nested": True}}

    def test_non_dict_replaces_dict(self):
        # If base has a dict and override has a scalar, override wins.
        assert _deep_merge({"k": {"nested": True}}, {"k": 1}) == {"k": 1}

    def test_deeply_nested_merge(self):
        base = {"a": {"b": {"c": {"d": 1, "e": 2}}}}
        override = {"a": {"b": {"c": {"e": 99}}}}
        assert _deep_merge(base, override) == {"a": {"b": {"c": {"d": 1, "e": 99}}}}

    def test_inputs_not_mutated(self):
        base = {"a": {"x": 1}}
        override = {"a": {"y": 2}}
        _deep_merge(base, override)
        assert base == {"a": {"x": 1}}
        assert override == {"a": {"y": 2}}

    def test_empty_override_returns_copy_of_base(self):
        base = {"a": 1}
        result = _deep_merge(base, {})
        assert result == base
        assert result is not base  # new dict
