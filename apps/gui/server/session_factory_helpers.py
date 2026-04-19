"""
Small helpers the bridge needs that depend on session_factory functions but
shouldn't live in state.py (to avoid a circular import).
"""

from __future__ import annotations

from apps.cli.session_factory import (
    SessionComponents,
    assemble_agent_tools,
    instantiate_agent,
    make_agent_vault_tools,
)


def build_delegate_agent(c: SessionComponents, delegate_meta, confirmation_handler):
    """Build a delegate agent at runtime (mirrors apps/cli/main.py:1247-1255)."""
    all_tools = assemble_agent_tools(delegate_meta, c.shared_tools, c.tool_groups)
    all_tools.extend(make_agent_vault_tools(delegate_meta, c.config, c.vault_config, confirmation_handler))
    return instantiate_agent(
        delegate_meta, c.client, c.model_id, all_tools,
        skill_registry=c.skill_registry,
        card_search_tool=c.card_search_tool,
    )
