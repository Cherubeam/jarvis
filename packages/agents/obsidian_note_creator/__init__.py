"""Obsidian Note Creator agent — extract atomic evergreen notes from conversations or material."""

from packages.agents.obsidian_note_creator.agent import ObsidianNoteCreatorAgent

AGENT_META = {
    "name": "obsidian-note-creator",
    "description": "Extract atomic evergreen notes from conversations or material",
    "command": "/obsidian-note-creator",
    "agent_class": ObsidianNoteCreatorAgent,
}

__all__ = ["ObsidianNoteCreatorAgent", "AGENT_META"]
