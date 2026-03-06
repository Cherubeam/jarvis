"""Pattern Language Expert agent — design, evolve, and apply pattern languages."""

from packages.agents.pattern_language_expert.agent import PatternLanguageExpertAgent

AGENT_META = {
    "name": "pattern-language-expert",
    "description": "Design, evolve, and apply pattern languages and pattern libraries",
    "command": "/pattern-language-expert",
    "agent_class": PatternLanguageExpertAgent,
}

__all__ = ["PatternLanguageExpertAgent", "AGENT_META"]
