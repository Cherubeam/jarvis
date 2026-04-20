"""Conversations browser — index + derivation over data/conversations/YYYY/*.json."""

from apps.gui.server.history.index import ConversationIndex
from apps.gui.server.history.summary import ConversationDetail, ConversationSummary

__all__ = ["ConversationIndex", "ConversationDetail", "ConversationSummary"]
