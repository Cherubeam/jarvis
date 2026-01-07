"""
Command-line interface for the personal assistant.
Ties everything together.
"""

import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from context_builder import build_system_prompt
from llm_client import LLMClient
from memory import ConversationLogger
from pricing import get_model_pricing, format_cost


def load_config() -> dict:
    """Load configuration from YAML file and environment."""
    # Find project roots
    src_dir = Path(__file__).parent
    personal_context_dir = src_dir.parent
    jarvis_dir = personal_context_dir.parent
    
    # Load .env from jarvis root
    load_dotenv(jarvis_dir / ".env")
    
    # Load config.yaml from jarvis root
    config_path = jarvis_dir / "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Get API key from environment
    config["openrouter"]["api_key"] = os.getenv("OPENROUTER_API_KEY")
    
    if not config["openrouter"]["api_key"]:
        print("Error: OPENROUTER_API_KEY not found in .env file")
        sys.exit(1)
    
    # Store paths for later use
    config["_paths"] = {
        "jarvis_dir": jarvis_dir,
        "personal_context_dir": personal_context_dir,
    }
    
    return config


def main():
    config = load_config()

    jarvis_dir = config["_paths"]["jarvis_dir"]
    model_id = config["openrouter"]["default_model"]

    # Initialize components — paths now relative to jarvis root
    context_dir = jarvis_dir / config["paths"]["context_dir"]
    conversations_dir = jarvis_dir / config["paths"]["conversations_dir"]

    system_prompt = build_system_prompt(
        context_dir,
        config["system_prompt_prefix"]
    )

    client = LLMClient(
        api_key=config["openrouter"]["api_key"],
        default_model=model_id
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
                cost_usd = pricing.calculate_cost(usage.prompt_tokens, usage.completion_tokens)
                print(f"[{usage.total_tokens:,} tokens | {format_cost(cost_usd)}]")

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