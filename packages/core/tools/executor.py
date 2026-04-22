"""
Tool call executor — runs tool calls returned by the LLM and formats results.
"""

import json
import logging
import time
from typing import Any

from packages.core.tools.base import ToolRegistry

logger = logging.getLogger(__name__)


def execute_tool_calls(tool_calls: list[Any], registry: ToolRegistry) -> list[dict[str, Any]]:
    """
    Execute a list of tool calls and return formatted result messages.

    Args:
        tool_calls: Tool call objects from a LiteLLM completion response
                    (each has .id, .function.name, .function.arguments).
        registry: ToolRegistry to look up implementations.

    Returns:
        List of {"role": "tool", "tool_call_id": ..., "content": ...} dicts
        ready to append to the message list for the next LLM call.
    """
    results = []

    for call in tool_calls:
        tool_call_id = call.id
        name = call.function.name
        raw_args = call.function.arguments

        tool = registry.get(name)
        if tool is None:
            content = f"Error: Unknown tool '{name}'."
            results.append({"role": "tool", "tool_call_id": tool_call_id, "content": content})
            continue

        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            start = time.perf_counter()
            content = tool.execute(**args)
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info("Tool %s executed in %.1fms", name, elapsed_ms)
        except Exception as e:
            content = f"Error executing tool '{name}': {e}. Do not retry this tool with the same arguments — try a different tool or approach."

        results.append({"role": "tool", "tool_call_id": tool_call_id, "content": content})

    return results
