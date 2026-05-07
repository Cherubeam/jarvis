"""
Core JARVIS functionality.
Shared modules for LLM interaction, context building, memory, and pricing.
"""

# Configure litellm process-wide before any submodule imports it.
# Multiple packages.core.* submodules (llm_client, pricing, rag/*) each
# `import litellm` at module top, so this single chokepoint is the only
# place that reliably runs before all of them — a per-submodule mutation
# would be racy with import order.
import litellm

litellm.suppress_debug_info = True

from packages.core.context_builder import build_system_prompt, load_context_file  # noqa: E402
from packages.core.llm_client import LLMClient, StreamingResponse, TokenUsage  # noqa: E402
from packages.core.memory import ConversationLogger, SessionMetrics  # noqa: E402
from packages.core.pricing import (  # noqa: E402
    ModelPricing,
    calculate_cost_from_litellm,
    format_cost,
    get_model_pricing,
)

__all__ = [
    "ConversationLogger",
    "LLMClient",
    "ModelPricing",
    "SessionMetrics",
    "StreamingResponse",
    "TokenUsage",
    "build_system_prompt",
    "calculate_cost_from_litellm",
    "format_cost",
    "get_model_pricing",
    "load_context_file",
]
