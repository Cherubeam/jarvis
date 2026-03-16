"""Tests for JARVIS agent — delegation directive builder."""

from packages.agents.jarvis.agent import _build_delegation_directive, _SPECIAL_HINTS


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
            {"name": "developer", "description": "self-improvement agent"},
        ]
        result = _build_delegation_directive(agents)
        for agent in agents:
            assert f"**{agent['name']}**" in result

    def test_agents_sorted_alphabetically(self):
        agents = [
            {"name": "writer", "description": "write"},
            {"name": "simplifier", "description": "simplify"},
            {"name": "developer", "description": "develop"},
        ]
        result = _build_delegation_directive(agents)
        developer_pos = result.index("**developer**")
        simplifier_pos = result.index("**simplifier**")
        writer_pos = result.index("**writer**")
        assert developer_pos < simplifier_pos < writer_pos

    def test_special_hint_included_for_developer(self):
        agents = [{"name": "developer", "description": "self-improvement"}]
        result = _build_delegation_directive(agents)
        assert "git sandbox" in result

    def test_no_special_hint_for_unknown_agent(self):
        agents = [{"name": "custom-agent", "description": "does stuff"}]
        result = _build_delegation_directive(agents)
        assert "git sandbox" not in result

    def test_behavioral_instructions_present(self):
        agents = [{"name": "writer", "description": "write"}]
        result = _build_delegation_directive(agents)
        assert "delegate_to_agent" in result
        assert "context" in result
        assert "read_note" in result

    def test_special_hints_dict_has_developer(self):
        assert "developer" in _SPECIAL_HINTS
