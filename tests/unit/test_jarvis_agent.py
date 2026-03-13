"""Tests for JARVIS agent — delegation directive builder."""

from packages.agents.jarvis.agent import _build_delegation_directive, _SPECIAL_HINTS


class TestBuildDelegationDirective:
    """Tests for _build_delegation_directive()."""

    def test_empty_list_returns_empty_string(self):
        assert _build_delegation_directive([]) == ""

    def test_single_agent_appears_in_output(self):
        agents = [{"name": "writing", "description": "creative writing"}]
        result = _build_delegation_directive(agents)
        assert "**writing**" in result
        assert "creative writing" in result

    def test_all_agent_names_appear(self):
        agents = [
            {"name": "writing", "description": "creative writing"},
            {"name": "tactics", "description": "tactics search"},
            {"name": "developer", "description": "self-improvement agent"},
        ]
        result = _build_delegation_directive(agents)
        for agent in agents:
            assert f"**{agent['name']}**" in result

    def test_agents_sorted_alphabetically(self):
        agents = [
            {"name": "writing", "description": "write"},
            {"name": "clarity", "description": "clarify"},
            {"name": "developer", "description": "develop"},
        ]
        result = _build_delegation_directive(agents)
        clarity_pos = result.index("**clarity**")
        developer_pos = result.index("**developer**")
        writing_pos = result.index("**writing**")
        assert clarity_pos < developer_pos < writing_pos

    def test_special_hint_included_for_developer(self):
        agents = [{"name": "developer", "description": "self-improvement"}]
        result = _build_delegation_directive(agents)
        assert "git sandbox" in result

    def test_no_special_hint_for_unknown_agent(self):
        agents = [{"name": "custom-agent", "description": "does stuff"}]
        result = _build_delegation_directive(agents)
        assert "git sandbox" not in result

    def test_behavioral_instructions_present(self):
        agents = [{"name": "writing", "description": "write"}]
        result = _build_delegation_directive(agents)
        assert "delegate_to_agent" in result
        assert "context" in result
        assert "read_note" in result

    def test_special_hints_dict_has_developer(self):
        assert "developer" in _SPECIAL_HINTS
