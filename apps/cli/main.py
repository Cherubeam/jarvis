"""
Command-line interface for the personal assistant.
Ties everything together.
"""

import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from packages.core.context_builder import build_system_prompt
from packages.core.llm_client import LLMClient
from packages.core.memory import ConversationLogger
from packages.core.pricing import get_model_pricing, format_cost, calculate_cost_from_litellm
from packages.integrations.things3.task_sync import sync_tasks_to_file


def get_project_root() -> Path:
    """Get the project root directory."""
    # Navigate from apps/cli/main.py to project root
    return Path(__file__).parent.parent.parent


def load_config() -> dict:
    """Load configuration from YAML file and environment."""
    jarvis_dir = get_project_root()

    # Load .env from jarvis root
    load_dotenv(jarvis_dir / ".env")

    # Load config from config/ directory (default.yaml with local.yaml override)
    default_config_path = jarvis_dir / "config" / "default.yaml"
    local_config_path = jarvis_dir / "config" / "local.yaml"

    # Start with default config
    if default_config_path.exists():
        with open(default_config_path) as f:
            config = yaml.safe_load(f) or {}
    else:
        # Fallback to old config location during migration
        old_config_path = jarvis_dir / "config.yaml"
        if old_config_path.exists():
            with open(old_config_path) as f:
                config = yaml.safe_load(f) or {}
        else:
            config = {}

    # Override with local config if exists
    if local_config_path.exists():
        with open(local_config_path) as f:
            local_config = yaml.safe_load(f) or {}
            # Deep merge would be better, but shallow works for now
            config.update(local_config)

    # Get API key from environment
    if "openrouter" not in config:
        config["openrouter"] = {}
    config["openrouter"]["api_key"] = os.getenv("OPENROUTER_API_KEY")

    if not config["openrouter"]["api_key"]:
        print("Error: OPENROUTER_API_KEY not found in .env file")
        sys.exit(1)

    # Store paths for later use
    config["_paths"] = {
        "jarvis_dir": jarvis_dir,
    }

    return config


def main():
    config = load_config()

    jarvis_dir = config["_paths"]["jarvis_dir"]
    model_id = config["openrouter"]["default_model"]

    # Initialize components - paths now relative to jarvis root
    # Use new data/ directory structure
    context_dir = jarvis_dir / config.get("paths", {}).get("context_dir", "data/context")
    conversations_dir = jarvis_dir / config.get("paths", {}).get("conversations_dir", "data/conversations")

    # Sync tasks from Things 3 (if enabled)
    sync_tasks_to_file(context_dir / "tasks.md", config)

    system_prompt = build_system_prompt(
        context_dir,
        config.get("system_prompt_prefix", "You are a helpful assistant.")
    )

    client = LLMClient(
        api_key=config["openrouter"]["api_key"],
        default_model=model_id,
        provider="openrouter"
    )

    logger = ConversationLogger(conversations_dir)

    # Fetch pricing for the model
    pricing = get_model_pricing(model_id)
    if pricing:
        price_info = f"(${pricing.prompt_cost * 1_000_000:.2f}/${pricing.completion_cost * 1_000_000:.2f} per 1M tokens)"
    else:
        price_info = "(pricing unavailable)"

    # Print startup info
    print("Personal Assistant")
    print(f"Model: {model_id} {price_info}")
    print("Type 'quit' or 'exit' to end. Ctrl+C also works.\n")

    # Main chat loop
    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except EOFError:
                break

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit"):
                break

            logger.add_message("user", user_input)

            messages = [
                {"role": "system", "content": system_prompt},
                *logger.get_messages_for_api()
            ]

            print("\nAssistant: ", end="", flush=True)
            full_response = []

            stream = client.chat_stream(messages)
            for chunk in stream:
                print(chunk, end="", flush=True)
                full_response.append(chunk)

            print("\n")

            usage = stream.usage

            # Calculate cost if pricing is available
            cost_usd = 0.0
            if pricing:
                # Primary: Use OpenRouter pricing
                cost_usd = pricing.calculate_cost(usage.prompt_tokens, usage.completion_tokens)
            else:
                # Fallback: Use LiteLLM's built-in cost calculation
                # Note: Suppresses Pydantic warnings for streaming responses
                cost_usd = calculate_cost_from_litellm(stream.raw_response)

            if cost_usd > 0:
                print(f"[{usage.total_tokens:,} tokens | {format_cost(cost_usd)}]")
            else:
                print(f"[{usage.total_tokens:,} tokens]")

            logger.add_message(
                "assistant",
                "".join(full_response),
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                cost_usd=cost_usd,
            )

    except KeyboardInterrupt:
        print("\n")

    finally:
        logger.save()
        print("Goodbye!")


if __name__ == "__main__":
    main()
