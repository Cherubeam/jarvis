"""Tests for JARVIS agent — delegation directive builder."""

from unittest.mock import MagicMock

from packages.agents.jarvis.agent import (
    JarvisAgent,
    _build_delegation_directive,
    _build_outcome_tracking_directive,
)
from packages.core.settings import ContextFilesSettings


class TestBuildOutcomeTrackingDirective:
    """Tests for _build_outcome_tracking_directive()."""

    def test_mentions_track_recommendation(self):
        directive = _build_outcome_tracking_directive()
        assert "track_recommendation" in directive

    def test_mentions_outcomes_command(self):
        directive = _build_outcome_tracking_directive()
        assert "/outcomes" in directive

    def test_lists_do_not_use_cases(self):
        directive = _build_outcome_tracking_directive()
        assert "Do NOT call it for" in directive
        assert "Opinions" in directive
        assert "Hypotheticals" in directive

    def test_mentions_recall_outcomes_for_dedup(self):
        directive = _build_outcome_tracking_directive()
        assert "recall_outcomes" in directive


class TestBuildDelegationDirective:
    """Tests for _build_delegation_directive()."""

    def test_empty_list_returns_empty_string(self):
        assert _build_delegation_directive([]) == ""

    def test_single_agent_appears_in_output(self):
        agents = [{"name": "writer", "description": "creative writing"}]
        result = _build_delegation_directive(agents)
        assert "**writer**" in result
        assert "creative writing" in result

    def test_all_agent_names_appear(self):
        agents = [
            {"name": "writer", "description": "creative writing"},
            {"name": "tactics_coach", "description": "tactics search"},
            {"name": "content_reviewer", "description": "reviews drafts"},
        ]
        result = _build_delegation_directive(agents)
        for agent in agents:
            assert f"**{agent['name']}**" in result

    def test_agents_sorted_alphabetically(self):
        agents = [
            {"name": "writer", "description": "write"},
            {"name": "simplifier", "description": "simplify"},
            {"name": "content_reviewer", "description": "review"},
        ]
        result = _build_delegation_directive(agents)
        reviewer_pos = result.index("**content_reviewer**")
        simplifier_pos = result.index("**simplifier**")
        writer_pos = result.index("**writer**")
        assert reviewer_pos < simplifier_pos < writer_pos

    def test_agent_line_is_name_and_description_only(self):
        agents = [{"name": "custom-agent", "description": "does stuff"}]
        result = _build_delegation_directive(agents)
        assert "\n- **custom-agent**: does stuff\n" in result

    def test_behavioral_instructions_present(self):
        agents = [{"name": "writer", "description": "write"}]
        result = _build_delegation_directive(agents)
        assert "delegate_to_agent" in result
        assert "context" in result
        assert "read_note" in result


class TestJarvisAgentContextFiles:
    """HUB-03: JARVIS builds and refreshes its prompt from the configured files and tasks path."""

    def test_uses_configured_files_and_tasks_file(self, tmp_path):
        context_dir = tmp_path / "JARVIS"
        (context_dir / "Memory").mkdir(parents=True)
        (context_dir / "JARVIS Soul.md").write_text("SOUL\n")
        (context_dir / "Memory" / "Current Focus.md").write_text("FOCUS\n")
        (context_dir / "soul.md").write_text("OLD SOUL\n")
        tasks_file = tmp_path / "cache" / "tasks.md"
        tasks_file.parent.mkdir()
        tasks_file.write_text("TASKS\n")
        files = ContextFilesSettings(soul="JARVIS Soul.md", focus="Memory/Current Focus.md")

        agent = JarvisAgent(MagicMock(), context_dir, context_files=files, tasks_file=tasks_file)

        assert agent.config.system_prompt == "SOUL\n\n## Current focus\n\nFOCUS\n\n\n---\n\n## Their tasks\n\nTASKS\n"
        assert agent.context_files is files
        assert agent.tasks_file == tasks_file

    def test_refresh_context_rereads_configured_files(self, tmp_path):
        (tmp_path / "Soul.md").write_text("FIRST\n")
        tasks_file = tmp_path / "tasks-cache.md"
        agent = JarvisAgent(
            MagicMock(), tmp_path, context_files=ContextFilesSettings(soul="Soul.md"), tasks_file=tasks_file
        )
        (tmp_path / "Soul.md").write_text("SECOND\n")
        tasks_file.write_text("TASKS\n")

        agent.refresh_context()

        assert agent.config.system_prompt == "SECOND\n\n## Their tasks\n\nTASKS\n"

    def test_defaults_keep_todays_names(self, tmp_path):
        (tmp_path / "soul.md").write_text("SOUL\n")
        (tmp_path / "tasks.md").write_text("TASKS\n")

        agent = JarvisAgent(MagicMock(), tmp_path)

        assert agent.config.system_prompt == "SOUL\n\n## Their tasks\n\nTASKS\n"
        assert agent.context_files is None
        assert agent.tasks_file is None
