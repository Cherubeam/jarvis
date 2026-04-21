"""
Core JARVIS functionality.
Shared modules for LLM interaction, context building, memory, and pricing.
"""

from packages.core.context_builder import build_system_prompt, load_context_file
from packages.core.llm_client import LLMClient, StreamingResponse, TokenUsage
from packages.core.memory import ConversationLogger, SessionMetrics
from packages.core.pricing import (
    ModelPricing,
    calculate_cost_from_litellm,
    format_cost,
    get_model_pricing,
)

__all__ = [
    # llm_client
    "LLMClient",
    "StreamingResponse",
    "TokenUsage",
    # context_builder
    "build_system_prompt",
    "load_context_file",
    # memory
    "ConversationLogger",
    "SessionMetrics",
    # pricing
    "ModelPricing",
    "get_model_pricing",
    "calculate_cost_from_litellm",
    "format_cost",
]
