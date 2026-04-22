"""Diagnostic script: test which prompt caching approach works via LiteLLM + OpenRouter.

Makes pairs of API calls with identical system prompts to test cache hits.
Requires OPENROUTER_API_KEY in environment (loaded from .env).

Usage: uv run python scripts/test_prompt_caching.py
"""

import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Project root on sys.path so litellm picks up .env
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

import litellm

MODEL = "openrouter/anthropic/claude-sonnet-4.6"

# ~2000 tokens of static content (well above minimum cacheable threshold)
SYSTEM_TEXT = (
    "You are a helpful assistant. "
    "Here is extensive reference material that should be cached:\n\n"
    + "The quick brown fox jumps over the lazy dog. " * 400
    + "\n\nAlways respond in one short sentence."
)

USER_MSG = "What color is the fox?"


def _print_usage(label: str, usage: Any) -> None:
    """Print all relevant usage fields."""
    print(f"\n  [{label}]")
    print(f"  prompt_tokens:   {getattr(usage, 'prompt_tokens', '?')}")
    print(f"  completion_tokens: {getattr(usage, 'completion_tokens', '?')}")

    # Anthropic-style
    cr = getattr(usage, "cache_read_input_tokens", None)
    cw = getattr(usage, "cache_creation_input_tokens", None)
    print(f"  cache_read_input_tokens:     {cr}")
    print(f"  cache_creation_input_tokens:  {cw}")

    # OpenAI/OpenRouter-style
    ptd = getattr(usage, "prompt_tokens_details", None)
    if ptd:
        print(f"  prompt_tokens_details:        {ptd}")
        cached = getattr(ptd, "cached_tokens", None)
        print(f"  prompt_tokens_details.cached: {cached}")
    else:
        print("  prompt_tokens_details:        None")

    # Raw dict fallback
    if hasattr(usage, "__dict__"):
        extras = {k: v for k, v in usage.__dict__.items() if "cache" in k.lower() or "cached" in k.lower()}
        if extras:
            print(f"  (extra cache fields): {extras}")


def test_approach(name: str, call_fn: Callable[[], Any]) -> bool:
    """Run a caching approach twice and report results."""
    print(f"\n{'=' * 60}")
    print(f"APPROACH: {name}")
    print(f"{'=' * 60}")

    try:
        print("\n--- Call 1 (cache write expected) ---")
        r1 = call_fn()
        _print_usage("Call 1", r1.usage)
        print(f"  Response: {r1.choices[0].message.content[:100]}")

        print("\n  Waiting 2s for cache propagation...")
        time.sleep(2)

        print("\n--- Call 2 (cache read expected) ---")
        r2 = call_fn()
        _print_usage("Call 2", r2.usage)
        print(f"  Response: {r2.choices[0].message.content[:100]}")

        # Verdict
        cr2 = getattr(r2.usage, "cache_read_input_tokens", 0) or 0
        ptd2 = getattr(r2.usage, "prompt_tokens_details", None)
        cached2 = getattr(ptd2, "cached_tokens", 0) if ptd2 else 0

        if cr2 > 0 or cached2 > 0:
            print(f"\n  ✓ CACHE HIT on call 2! (cache_read={cr2}, cached_tokens={cached2})")
            return True
        else:
            print("\n  ✗ No cache hit detected on call 2")
            return False

    except Exception as e:
        print(f"\n  ✗ ERROR: {e}")
        return False


def main() -> None:
    print(f"Model: {MODEL}")
    print(f"System prompt length: ~{len(SYSTEM_TEXT)} chars")

    results = {}

    # Approach A: Per-block cache_control (current JARVIS implementation)
    def call_a() -> Any:
        return litellm.completion(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": SYSTEM_TEXT,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                },
                {"role": "user", "content": USER_MSG},
            ],
            max_tokens=50,
        )

    results["A: Per-block cache_control"] = test_approach(
        "A: Per-block cache_control (current JARVIS approach)", call_a
    )

    time.sleep(3)

    # Approach B: Top-level cache_control via extra_body
    def call_b() -> Any:
        return litellm.completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_TEXT},
                {"role": "user", "content": USER_MSG},
            ],
            max_tokens=50,
            extra_body={"cache_control": {"type": "ephemeral"}},
        )

    results["B: Top-level extra_body"] = test_approach("B: Top-level cache_control via extra_body", call_b)

    time.sleep(3)

    # Approach C: LiteLLM auto-inject
    def call_c() -> Any:
        return litellm.completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_TEXT},
                {"role": "user", "content": USER_MSG},
            ],
            max_tokens=50,
            cache_control_injection_points=[{"location": "message", "role": "system"}],
        )

    results["C: LiteLLM auto-inject"] = test_approach("C: LiteLLM cache_control_injection_points", call_c)

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    for name, worked in results.items():
        status = "✓ WORKS" if worked else "✗ No cache hit"
        print(f"  {name}: {status}")


if __name__ == "__main__":
    main()
