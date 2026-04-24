"""Unit tests for cli module — typed Settings loader (PR-8a)."""

from pathlib import Path

import pytest

from apps.cli.main import load_config
from packages.core.settings import Settings


@pytest.mark.unit
class TestLoadConfig:
    """``apps.cli.main.load_config`` — re-exported typed Settings loader."""

    def test_load_config_success(self, tmp_path: Path, monkeypatch):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "default.yaml").write_text('models:\n  default: "openrouter/anthropic/claude-sonnet-4.6"\n')

        monkeypatch.setattr("packages.core.settings.get_project_root", lambda: tmp_path)

        settings = load_config()

        assert isinstance(settings, Settings)
        assert settings.models.default == "openrouter/anthropic/claude-sonnet-4.6"
        assert settings.jarvis_dir == tmp_path

    def test_load_config_missing_yaml_uses_defaults(self, tmp_path: Path, monkeypatch):
        """Missing config files fall back to typed defaults — every section
        is always populated so callers don't have to special-case absence."""
        monkeypatch.setattr("packages.core.settings.get_project_root", lambda: tmp_path)

        settings = load_config()

        assert isinstance(settings, Settings)
        assert settings.models.default == "openrouter/qwen/qwen3.5-flash-02-23"
        assert settings.outcomes.enabled is True
        assert settings.jarvis_dir == tmp_path

    def test_load_config_local_override_preserves_sibling_keys(self, tmp_path: Path, monkeypatch):
        """local.yaml partial override must not clobber sibling defaults
        (the deep-merge in read_yaml_layers is what guarantees this)."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "default.yaml").write_text(
            "obsidian:\n"
            "  enabled: true\n"
            '  vault_path: "/default/vault"\n'
            "  writing:\n"
            "    slip_box:\n"
            '      target_dir: "inbox"\n'
            '      template_path: "templates/slip.md"\n'
        )
        (config_dir / "local.yaml").write_text('obsidian:\n  vault_path: "/my/real/vault"\n')

        monkeypatch.setattr("packages.core.settings.get_project_root", lambda: tmp_path)

        settings = load_config()

        assert settings.obsidian.vault_path == "/my/real/vault"
        assert settings.obsidian.enabled is True
        assert settings.obsidian.writing.slip_box.target_dir == "inbox"
        assert settings.obsidian.writing.slip_box.template_path == "templates/slip.md"
