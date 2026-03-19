"""
Command-line interface for the personal assistant.
Ties everything together.
"""

import argparse
import os
import platform
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from apps.cli.display import (
    console,
    create_prompt_session,
    finish_live_stream,
    make_live_chunk_handler,
    print_agent_prefix,
    print_assistant_prefix,
    print_error,
    print_separator,
    print_startup,
    print_system,
    print_tool_feedback,
    print_usage_stats,
    prompt_user,
    start_live_stream,
)
from packages.agents.base import agent_from_meta
from packages.agents.jarvis.agent import JarvisAgent
from packages.agents.registry import AgentMeta, discover_agents, get_by_command
from packages.core.context_builder import build_system_prompt, build_system_prompt_with_metadata, parse_frontmatter
from packages.skills.registry import discover_skills
from packages.core.llm_client import LLMClient
from packages.core.memory import ConversationLogger, hash_content
from packages.core.model_resolver import resolve_model, collect_api_keys, get_api_key
from packages.core.model_router import route_query
from packages.core.pricing import ModelPricing, get_model_pricing, format_cost
from packages.core.stream_handler import StreamHandler, StreamResult
from packages.integrations.things3.task_sync import sync_tasks_to_file
from packages.core.filesystem_access import load_filesystem_guard
from packages.integrations.obsidian.vault import load_vault_config, read_note, get_daily_note_path
from packages.integrations.obsidian.callout import find_jarvis_callout, CalloutNotFound
from packages.integrations.obsidian.writer import CLIConfirmationHandler, append_to_daily_note
from packages.telemetry.metrics import MetricsTracker

CLIENT_VERSION = "0.4.0"


def _assemble_agent_tools(
    meta: AgentMeta,
    shared_tools: list,
    tool_groups: dict[str, list],
    only_tool_groups: set[str] | None = None,
    include_shared: bool = True,
) -> list:
    """Assemble tools for an agent from shared_tools + its declared tool_groups.

    Args:
        only_tool_groups: If set, include only these tool groups
            (overrides meta.tool_groups). If None, use meta.tool_groups.
        include_shared: Whether to include shared tools (default True).
    """
    agent_tools = list(shared_tools) if include_shared else []
    groups = only_tool_groups if only_tool_groups is not None else set(meta.tool_groups)
    for group_name in groups:
        if group_name in tool_groups:
            agent_tools.extend(tool_groups[group_name])
    return agent_tools


def _instantiate_agent(
    meta: AgentMeta,
    client: LLMClient,
    model_id: str,
    extra_tools: list | None = None,
    skill_registry: dict | None = None,
    card_search_tool=None,
    skill_names_override: list[str] | None = None,
    prompt_includes_override: dict[str, str] | None = None,
):
    """Create an agent from AgentMeta via agent_from_meta()."""
    return agent_from_meta(
        meta.meta_path, client, model_id,
        extra_tools=extra_tools or None,
        skill_registry=skill_registry,
        card_search_tool=card_search_tool,
        skill_names_override=skill_names_override,
        prompt_includes_override=prompt_includes_override,
    )


def _make_agent_vault_tools(meta: AgentMeta, config: dict, vault_config) -> list:
    """Create vault write tools scoped to an agent's declared vault_writing config section.

    Reads meta.vault_writing (e.g. "patterns", "slip_box"), looks up the
    corresponding obsidian.writing.<key> config, and calls make_vault_write_tools()
    with the right target_dir and template_path.

    Returns [] if the agent doesn't declare vault_writing or the config section is empty.
    """
    if vault_config is None or not meta.vault_writing:
        return []

    section = config.get("obsidian", {}).get("writing", {}).get(meta.vault_writing, {})
    target_dir = section.get("target_dir", "")
    template_path = section.get("template_path", "")
    if not target_dir:
        return []

    try:
        from packages.core.tools.vault_write_tools import make_vault_write_tools

        return make_vault_write_tools(
            vault_config, CLIConfirmationHandler(),
            target_dir=target_dir, template_path=template_path,
        )
    except Exception:
        return []


def stream_and_track(
    client: LLMClient,
    messages: list[dict],
    metrics_tracker: MetricsTracker,
    pricing: ModelPricing | None,
    model_id: str,
    print_chunks: bool = False,
    max_tokens: int | None = None,
) -> StreamResult:
    """Stream an LLM response, tracking metrics and cost.

    Thin wrapper around StreamHandler.stream() for backward compatibility.
    """
    handler = StreamHandler(client, metrics_tracker, pricing, model_id)
    handler.max_tokens = max_tokens
    return handler.stream(messages, print_chunks=print_chunks)


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

    # Store paths for later use
    config["_paths"] = {
        "jarvis_dir": jarvis_dir,
    }

    return config


def handle_daily_summary(config: dict, client: LLMClient, logger: ConversationLogger,
                         system_prompt: str, metrics_tracker: MetricsTracker,
                         pricing: ModelPricing | None, model_id: str) -> None:
    """Handle the /daily-summary command."""
    fs_guard = load_filesystem_guard(config)
    vault_config = load_vault_config(config, filesystem_guard=fs_guard)
    if vault_config is None:
        print_system("\nObsidian integration is not configured or disabled.")
        print_system("Set obsidian.enabled=true and obsidian.vault_path in config/local.yaml\n")
        return

    # Get today's daily note
    note_path = get_daily_note_path(vault_config)
    try:
        note_content = read_note(note_path, vault_config)
    except FileNotFoundError:
        print_error(f"\nDaily note not found: {note_path.name}")
        print_system("Create the note with a > [!JARVIS] callout block first.\n")
        return
    except PermissionError as e:
        print_error(f"\n{e}\n")
        return

    # Check for JARVIS callout
    callout = find_jarvis_callout(note_content)
    if isinstance(callout, CalloutNotFound):
        print_error(f"\nNo > [!JARVIS] callout block found in {note_path.name}")
        print_system("Add a '> [!JARVIS]' line to your daily note first.\n")
        return

    # Strip existing JARVIS callout from note content to avoid duplication
    note_lines = note_content.split("\n")
    note_without_callout = "\n".join(
        note_lines[:callout.start_line] + note_lines[callout.end_line + 1:]
    ).strip()

    # Load prompt and build LLM messages
    try:
        daily_prompt = JarvisAgent.get_daily_note_instructions()
    except FileNotFoundError:
        print("\nDaily note prompt file not found.\n")
        return

    user_content = (
        f"Generate my daily note summary for today.\n\n"
        f"---\n\n"
        f"**Today's daily note ({note_path.name}):**\n\n"
        f"{note_without_callout}"
    )
    if callout.existing_content.strip():
        user_content += (
            f"\n\n---\n\n"
            f"**Existing JARVIS callout entries (DO NOT repeat these):**\n\n"
            f"{callout.existing_content.strip()}"
        )

    messages = [
        {"role": "system", "content": f"{system_prompt}\n\n{daily_prompt}"},
        *logger.get_messages_for_api(),
        {"role": "user", "content": user_content},
    ]

    # Stream LLM response with activity spinner
    print_assistant_prefix("JARVIS")
    live, buf = start_live_stream()

    handler = StreamHandler(client, metrics_tracker, pricing, model_id)
    handler.max_tokens = 4096
    handler.on_chunk = make_live_chunk_handler(live, buf)
    result = handler.stream(messages, print_chunks=True)

    finish_live_stream(live, result.text)

    # Log the exchange so save() writes conversation + prints session summary
    logger.add_message("user", "/daily-summary")
    logger.add_message(
        "assistant",
        result.text,
        prompt_tokens=result.usage.prompt_tokens,
        completion_tokens=result.usage.completion_tokens,
        total_tokens=result.usage.total_tokens,
        cost_usd=result.cost_usd,
        ttft_ms=result.metrics.ttft_ms,
        total_latency_ms=result.metrics.total_latency_ms,
        agent_name="JARVIS",
    )

    # Write to vault with diff + confirmation
    handler = CLIConfirmationHandler()
    write_result = append_to_daily_note(result.text, vault_config, handler)

    if write_result.success:
        print(f"\n{write_result.message}\n")
    else:
        print(f"\n{write_result.message}\n")

    print_usage_stats(result)


def handle_model_command(
    payload: str,
    config: dict,
    client: LLMClient,
    model_id: str,
    stream_handler: StreamHandler,
) -> tuple[str, ModelPricing | None]:
    """Handle the /model slash command.

    Returns (new_model_id, new_pricing) so the caller can update its state.
    """
    api_keys = client.api_keys
    models_config = config.get("models", {})
    presets = models_config.get("presets", {})

    if not payload:
        # Show current model + available presets
        print_system(f"\nCurrent model: {model_id}")
        if presets:
            print_system("\nAvailable presets:")
            for name, mid in presets.items():
                marker = " (active)" if mid == model_id else ""
                print_system(f"  {name}: {mid}{marker}")
        print_system("\nUsage: /model <preset-or-model-id>\n")
        pricing = get_model_pricing(model_id)
        return model_id, pricing

    # Resolve the requested model
    resolved = resolve_model(payload, config)

    # Check API key
    key = get_api_key(resolved.provider, api_keys)
    if not key:
        print_error(
            f"\nNo API key for provider '{resolved.provider}'. "
            f"Set {resolved.provider.upper()}_API_KEY in your .env file.\n"
        )
        pricing = get_model_pricing(model_id)
        return model_id, pricing

    # Switch
    client.set_model(resolved.model_id)
    new_pricing = get_model_pricing(resolved.model_id)

    # Update stream handler
    stream_handler.model_id = resolved.model_id
    stream_handler.pricing = new_pricing

    if new_pricing:
        price_info = (
            f"${new_pricing.prompt_cost * 1_000_000:.2f}/"
            f"${new_pricing.completion_cost * 1_000_000:.2f} per 1M tokens"
        )
    else:
        price_info = "pricing unavailable"

    print_system(f"\nSwitched to {resolved.display_name} ({price_info})\n")
    return resolved.model_id, new_pricing


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="JARVIS personal assistant")
    parser.add_argument(
        "--agent",
        type=str,
        default=None,
        help="Run a standalone agent instead of the default JARVIS orchestrator (e.g. --agent writer)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model preset or LiteLLM model ID (e.g. --model fast, --model anthropic/claude-sonnet-4.6)",
    )
    parser.add_argument(
        "--auto-confirm",
        action="store_true",
        help="Auto-approve file writes within developer.scope (for CI/unattended runs)",
    )
    return parser.parse_args(argv)


def _run_agent_session(
    agent,
    agent_name: str,
    stream_handler: StreamHandler,
    logger: ConversationLogger,
    session,
    initial_message: str | None = None,
    context: str | None = None,
    prior_session: list[dict] | None = None,
) -> list[dict]:
    """Run a multi-turn agent session until the user types /exit or /back.

    Args:
        agent: The agent instance to run.
        agent_name: Display name for the agent.
        stream_handler: StreamHandler for streaming + metrics.
        logger: ConversationLogger for persistence.
        session: prompt_toolkit session for user input.
        initial_message: If set, process this as the first message before prompting.
        context: JARVIS's summary of its conversation before delegating.
        prior_session: Full conversation history from a previous agent session.

    Returns:
        The session history (list of user/assistant message dicts).
    """
    print_system(f"\nEntering {agent_name} session. Type /exit or /back to return to JARVIS.\n")

    session_history: list[dict] = []

    # Inject prior agent session as conversation context
    if prior_session:
        session_history.extend(prior_session)

    # Inject JARVIS's pre-delegation context as a context exchange
    if context:
        session_history.append({"role": "user", "content": f"[Context from JARVIS] {context}"})
        session_history.append({"role": "assistant", "content": "Understood, I have this context. How can I help?"})

    def _process_message(user_input: str) -> None:
        logger.add_message("user", user_input)
        session_history.append({"role": "user", "content": user_input})

        print_agent_prefix(agent_name)
        live, buf = start_live_stream()
        stream_handler.on_chunk = make_live_chunk_handler(live, buf)
        stream_handler.on_before_tool_exec = lambda: live.stop()
        stream_handler.on_after_tool_exec = lambda: live.start()
        result = agent.run(
            user_input,
            stream_handler,
            print_chunks=True,
            messages_override=session_history[:-1],
        )
        stream_handler.on_chunk = None
        stream_handler.on_before_tool_exec = None
        stream_handler.on_after_tool_exec = None
        finish_live_stream(live, result.text)

        print_usage_stats(result)
        print_separator()

        # Persist tool call context before the final assistant message
        if result.tool_messages:
            session_history.extend(result.tool_messages)
            logger.add_tool_messages(result.tool_messages, agent_name=agent_name)

        session_history.append({"role": "assistant", "content": result.text})
        logger.add_message(
            "assistant",
            result.text,
            prompt_tokens=result.usage.prompt_tokens,
            completion_tokens=result.usage.completion_tokens,
            total_tokens=result.usage.total_tokens,
            cost_usd=result.cost_usd,
            ttft_ms=result.metrics.ttft_ms,
            total_latency_ms=result.metrics.total_latency_ms,
            agent_name=agent_name,
        )

    # Process initial message if provided (e.g. from delegation)
    if initial_message:
        framed = (
            f"[JARVIS delegated this goal to you: {initial_message}]\n\n"
            "Start by confirming what I want — acknowledge the goal, "
            "ask scoping questions, and propose a session plan before "
            "taking any action."
        )
        _process_message(framed)

    try:
        while True:
            try:
                user_input = prompt_user(session)
            except EOFError:
                break

            if not user_input:
                continue
            if user_input.strip().lower() in ("/exit", "/quit", "/back"):
                break

            _process_message(user_input)
    except KeyboardInterrupt:
        pass

    print_system(f"\nReturning to JARVIS.\n")
    return session_history


def _handle_agent_command(
    command: str,
    payload: str,
    client: LLMClient,
    stream_handler: StreamHandler,
    logger: ConversationLogger,
    model_id: str,
    agent_registry: dict,
    shared_tools: list | None = None,
    tool_groups: dict[str, list] | None = None,
    session=None,
    skill_registry: dict | None = None,
    card_search_tool=None,
    config: dict | None = None,
    vault_config=None,
) -> bool:
    """Route a slash command to the matching agent. Returns True if handled."""
    meta = get_by_command(command, agent_registry)
    if meta is None:
        return False

    # Show usage if no payload and no interactive session
    if not payload and session is None:
        print_system(f"\nUsage: {command} <text>")
        print_system(f"  {meta.description}\n")
        return True

    # Assemble tools: shared + per-agent tool_groups + vault write tools
    all_tools = _assemble_agent_tools(meta, shared_tools or [], tool_groups or {})
    if config is not None:
        all_tools.extend(_make_agent_vault_tools(meta, config, vault_config))

    agent = _instantiate_agent(
        meta, client, model_id, all_tools or None,
        skill_registry=skill_registry,
        card_search_tool=card_search_tool,
    )

    if not payload:
        _run_agent_session(agent, meta.name, stream_handler, logger, session)
        return True

    logger.add_message("user", f"{command} {payload}")

    print_agent_prefix(meta.name)
    live, buf = start_live_stream()
    stream_handler.on_chunk = make_live_chunk_handler(live, buf)
    stream_handler.on_before_tool_exec = lambda: live.stop()
    stream_handler.on_after_tool_exec = lambda: live.start()
    result = agent.run(payload, stream_handler, print_chunks=True)
    stream_handler.on_chunk = None
    stream_handler.on_before_tool_exec = None
    stream_handler.on_after_tool_exec = None
    finish_live_stream(live, result.text)

    print_usage_stats(result)
    print_separator()

    logger.add_message(
        "assistant",
        result.text,
        prompt_tokens=result.usage.prompt_tokens,
        completion_tokens=result.usage.completion_tokens,
        total_tokens=result.usage.total_tokens,
        cost_usd=result.cost_usd,
        ttft_ms=result.metrics.ttft_ms,
        total_latency_ms=result.metrics.total_latency_ms,
        agent_name=meta.name,
    )
    return True


def main(argv: list[str] | None = None):
    args = parse_args(argv)
    config = load_config()

    jarvis_dir = config["_paths"]["jarvis_dir"]

    # Collect API keys from environment
    api_keys = collect_api_keys()

    # Resolve model: CLI flag > config default
    models_config = config.get("models", {})
    model_source = args.model or models_config.get("default", "openrouter/anthropic/claude-sonnet-4.6")
    resolved = resolve_model(model_source, config)
    model_id = resolved.model_id

    # Validate that we have an API key for the resolved provider
    if not get_api_key(resolved.provider, api_keys):
        print(f"Error: No API key for provider '{resolved.provider}'. "
              f"Set {resolved.provider.upper()}_API_KEY in your .env file.")
        sys.exit(1)

    # Initialize components - paths now relative to jarvis root
    context_dir = jarvis_dir / config.get("paths", {}).get("context_dir", "data/context")
    conversations_dir = jarvis_dir / config.get("paths", {}).get("conversations_dir", "data/conversations")

    # Sync tasks from Things 3 (if enabled)
    sync_tasks_to_file(context_dir / "tasks.md", config)

    system_prompt, context_metadata = build_system_prompt_with_metadata(context_dir)

    client = LLMClient(
        api_keys=api_keys,
        default_model=model_id,
    )

    # Discover registered agents and skills for slash-command routing
    agent_registry = discover_agents()
    skill_registry = discover_skills()

    # Initialize RAG if enabled
    # Shared tools — always available to JARVIS and all delegated agents
    shared_tools: list = []
    # Named tool groups — assigned per-agent via meta.yaml `tools:` field
    tool_groups: dict[str, list] = {}
    card_search_tool = None  # Set by RAG card indexing if available
    rag_cfg = config.get("rag", {})
    if rag_cfg.get("enabled", False):
        try:
            from packages.core.rag.indexer import ConversationIndexer
            from packages.core.tools.conversation_recall import make_conversation_recall_tool

            db_path = jarvis_dir / rag_cfg.get("db_path", "data/rag/chroma")
            embedding_model = rag_cfg.get("embedding_model", "openrouter/openai/text-embedding-3-small")

            # Use the OpenRouter key for RAG embeddings (backward compatible)
            rag_api_key = get_api_key("openrouter", api_keys) or ""

            indexer = ConversationIndexer(db_path, embedding_model, rag_api_key)
            n_new = indexer.index_new(conversations_dir)
            if n_new:
                print_system(f"[RAG] Indexed {n_new} new conversation(s).")

            recall_tool = make_conversation_recall_tool(db_path, embedding_model, rag_api_key)
            shared_tools.append(recall_tool)

            # Index deck-skill cards if any deck-skills have a deck.yaml
            if rag_cfg.get("index_cards", True):
                deck_dirs = [
                    meta.path for meta in skill_registry.values()
                    if (meta.path / "deck.yaml").is_file()
                ]
                if deck_dirs:
                    from packages.core.rag.card_indexer import CardIndexer
                    from packages.core.tools.card_search import make_card_search_tool

                    card_indexer = CardIndexer(db_path, embedding_model, rag_api_key)
                    n_cards = card_indexer.index_new(deck_dirs)
                    if n_cards:
                        print_system(f"[RAG] Indexed {n_cards} new card(s).")

                    card_search_tool = make_card_search_tool(db_path, embedding_model, rag_api_key)
                    tool_groups["card_search"] = [card_search_tool]

        except ImportError:
            print_system("[RAG] chromadb not installed — recall disabled. Run: uv add chromadb")
        except Exception as e:
            print_system(f"[RAG] Startup failed — recall disabled. ({e})")

    # Initialize vault tools
    fs_guard = load_filesystem_guard(config)
    vault_config = load_vault_config(config, filesystem_guard=fs_guard)

    # Vault read tools — shared (available to JARVIS and all delegated agents)
    if vault_config is not None:
        try:
            from packages.core.tools.vault_read_tools import make_vault_read_tools

            vault_read_tools = make_vault_read_tools(vault_config)
            shared_tools.extend(vault_read_tools)
            print_system(f"[Vault] {len(vault_read_tools)} vault read tools loaded.")
        except Exception as e:
            print_system(f"[Vault] Startup failed — vault read tools disabled. ({e})")

    # Blog tools — tool group for writing agent
    if vault_config is not None:
        try:
            from packages.core.tools.blog_tools import make_blog_tools

            obsidian_cfg = config.get("obsidian", {})
            writing_cfg = obsidian_cfg.get("writing", {})
            blog_dir = writing_cfg.get("blog_dir", "")
            template_path = writing_cfg.get("template_path", "")

            if blog_dir:
                blog_tools = make_blog_tools(
                    vault_config, CLIConfirmationHandler(), blog_dir, template_path,
                )
                tool_groups["blog_tools"] = blog_tools
                print_system(f"[Blog] {len(blog_tools)} blog tools loaded.")
        except Exception as e:
            print_system(f"[Blog] Startup failed — blog tools disabled. ({e})")

    # Content-evaluator tool — tool group for writing agent
    skill_dir = jarvis_dir / "packages" / "skills" / "content-evaluator"
    if (skill_dir / "SKILL.md").is_file():
        try:
            from packages.core.tools.content_evaluator import make_content_evaluator_tool

            evaluator_tool = make_content_evaluator_tool(skill_dir, client, model_id)
            tool_groups["content_evaluator"] = [evaluator_tool]
            print_system("[Tools] Content evaluator loaded.")
        except Exception as e:
            print_system(f"[Tools] Content evaluator failed: {e}")

    # Developer tools — tool group for developer agent
    dev_cfg = config.get("developer", {})
    if dev_cfg.get("enabled", True):
        try:
            from packages.core.tools.codebase_tools import make_codebase_tools
            from packages.core.tools.git_tools import make_git_tools
            from packages.core.tools.project_write_tools import make_project_write_tools
            from packages.core.tools.test_tools import make_test_runner_tool

            dev_scope = dev_cfg.get("scope", [
                "packages/agents/", "packages/skills/",
                "data/context/", "data/prompts/", "config/",
            ])
            dev_extensions = dev_cfg.get("allowed_extensions", [".md", ".yaml", ".yml"])

            dev_tools: list = []
            dev_tools.extend(make_codebase_tools(jarvis_dir))
            dev_tools.extend(make_git_tools(jarvis_dir))
            if args.auto_confirm:
                from packages.agents.developer.confirmation import AutoConfirmationHandler
                dev_confirmation = AutoConfirmationHandler(dev_scope, jarvis_dir)
            else:
                dev_confirmation = CLIConfirmationHandler()
            dev_tools.extend(make_project_write_tools(
                jarvis_dir, dev_confirmation,
                allowed_dirs=dev_scope, allowed_extensions=dev_extensions,
            ))
            dev_tools.append(make_test_runner_tool(jarvis_dir))
            tool_groups["dev_tools"] = dev_tools
            print_system(f"[Developer] {len(dev_tools)} developer tools loaded.")
        except Exception as e:
            print_system(f"[Developer] Startup failed — developer tools disabled. ({e})")

    # Suggest-improvements tool — tool group for writing agent
    if vault_config is not None:
        try:
            from packages.core.tools.suggest_improvements import make_suggest_improvements_tool

            suggest_tool = make_suggest_improvements_tool(
                vault_config, CLIConfirmationHandler(),
            )
            tool_groups["suggest_improvements"] = [suggest_tool]
            print_system("[Tools] Suggest improvements loaded.")
        except Exception as e:
            print_system(f"[Tools] Suggest improvements failed: {e}")

    # Build the active agent
    if args.agent:
        if args.agent not in agent_registry:
            available = ", ".join(sorted(agent_registry)) or "(none)"
            print_error(f"Error: unknown agent '{args.agent}'. Available: {available}")
            sys.exit(1)
        meta = agent_registry[args.agent]
        all_agent_tools = _assemble_agent_tools(meta, shared_tools, tool_groups)
        all_agent_tools.extend(_make_agent_vault_tools(meta, config, vault_config))
        active_agent = _instantiate_agent(
            meta, client, model_id, all_agent_tools,
            skill_registry=skill_registry,
            card_search_tool=card_search_tool,
        )
        agent_name = meta.name
    else:
        available_agents = [
            {"name": meta.name, "description": meta.description}
            for meta in agent_registry.values()
        ]
        active_agent = JarvisAgent(
            llm_client=client,
            context_dir=context_dir,
            model=model_id,
            extra_tools=shared_tools or None,
            available_agents=available_agents or None,
        )
        agent_name = "JARVIS"

    # Build schema config dicts for ConversationLogger
    model_config = {
        "id": model_id,
        "provider": resolved.provider,
        "parameters": {},
    }

    logger_agent_config = {
        "name": agent_name,
        "system_prompt_hash": f"sha256:{hash_content(active_agent.config.system_prompt)}",
        "tools": [],
        "metadata": {},
    }

    context_files = []
    if context_dir.exists():
        for f in sorted(context_dir.iterdir()):
            if f.is_file() and f.suffix == ".md":
                content = f.read_text(encoding="utf-8")
                size_bytes = f.stat().st_size
                context_files.append({
                    "path": str(f.relative_to(jarvis_dir)),
                    "hash": f"sha256:{hash_content(content)}",
                    "size_bytes": size_bytes,
                    "approx_tokens": size_bytes // 4,
                })
        # Include project context files with frontmatter metadata
        projects_dir = context_dir / "projects"
        if projects_dir.is_dir():
            for f in sorted(projects_dir.glob("*.md")):
                content = f.read_text(encoding="utf-8")
                meta_fm, _ = parse_frontmatter(content)
                is_active = meta_fm.get("active", True)
                size_bytes = f.stat().st_size
                entry = {
                    "path": str(f.relative_to(jarvis_dir)),
                    "hash": f"sha256:{hash_content(content)}",
                    "size_bytes": size_bytes,
                    "approx_tokens": size_bytes // 4,
                    "active": is_active,
                }
                if meta_fm:
                    entry["frontmatter"] = meta_fm
                context_files.append(entry)

    context_snapshot = {
        "files_loaded": context_files,
        "metadata": {},
    }

    environment = {
        "client": "cli",
        "client_version": CLIENT_VERSION,
        "platform": sys.platform,
        "python_version": platform.python_version(),
        "metadata": {},
    }

    logger = ConversationLogger(
        conversations_dir,
        model_config=model_config,
        agent_config=logger_agent_config,
        context_snapshot=context_snapshot,
        environment=environment,
        context_metadata=context_metadata,
    )
    metrics_tracker = MetricsTracker()

    # Fetch pricing for the model
    pricing = get_model_pricing(model_id)
    if pricing:
        price_info = f"(${pricing.prompt_cost * 1_000_000:.2f}/${pricing.completion_cost * 1_000_000:.2f} per 1M tokens)"
    else:
        price_info = "(pricing unavailable)"

    stream_handler = StreamHandler(
        client, metrics_tracker, pricing, model_id,
        on_tool_call=print_tool_feedback,
        max_tokens=config.get("models", {}).get("default_max_tokens"),
    )

    # Print startup info
    commands = None
    if agent_registry:
        cmds = [m.command for m in agent_registry.values()]
        cmds.append("/daily-summary")
        cmds.append("/model")
        commands = cmds
    print_startup(agent_name, model_id, price_info, commands)

    # Create prompt_toolkit session for robust input handling
    cli_cfg = config.get("cli", {})
    history_file = cli_cfg.get("history_file", "data/.cli_history")
    if history_file:
        history_file = str(jarvis_dir / history_file)
    session = create_prompt_session(history_file)

    # Track last agent session for agent-to-agent handoff
    last_agent_session: list[dict] | None = None

    # Main chat loop
    try:
        while True:
            try:
                user_input = prompt_user(session)
            except EOFError:
                break

            if not user_input:
                continue

            # Handle slash commands
            if user_input.startswith("/"):
                parts = user_input.split(None, 1)
                command = parts[0]
                payload = parts[1] if len(parts) > 1 else ""

                # Built-in commands
                if command in ("/exit", "/quit"):
                    break

                if command == "/daily-summary":
                    handle_daily_summary(config, client, logger, system_prompt,
                                         metrics_tracker, pricing, model_id)
                    continue

                if command == "/model":
                    model_id, pricing = handle_model_command(
                        payload, config, client, model_id, stream_handler,
                    )
                    continue

                # Agent-routed commands
                if _handle_agent_command(
                    command, payload, client, stream_handler, logger,
                    model_id, agent_registry,
                    shared_tools=shared_tools,
                    tool_groups=tool_groups,
                    session=session,
                    skill_registry=skill_registry,
                    card_search_tool=card_search_tool,
                    config=config,
                    vault_config=vault_config,
                ):
                    continue

                print_error(f"\nUnknown command: {command}\n")
                continue

            # Regular chat — route through active agent
            # Grab existing history before adding user message (run() appends it)
            history = logger.get_messages_for_api()

            # Track history size for token economics instrumentation
            history_bytes = sum(
                len(str(m.get("content", "")).encode("utf-8")) for m in history
            )
            logger.metrics.record_history_tokens(history_bytes // 4)

            logger.add_message("user", user_input)

            # Intelligent model routing (opt-in via config)
            routed_model_id = None
            if config.get("routing", {}).get("enabled", False):
                decision = route_query(user_input, config, agent_name=agent_name)
                if decision.resolved.model_id != model_id:
                    routed_model_id = model_id  # save original to restore
                    client.set_model(decision.resolved.model_id)
                    stream_handler.model_id = decision.resolved.model_id

            print_assistant_prefix(agent_name)
            live, buf = start_live_stream()
            stream_handler.on_chunk = make_live_chunk_handler(live, buf)
            stream_handler.on_before_tool_exec = lambda: live.stop()
            stream_handler.on_after_tool_exec = lambda: live.start()
            result = active_agent.run(
                user_input,
                stream_handler,
                print_chunks=True,
                messages_override=history,
            )
            stream_handler.on_chunk = None
            stream_handler.on_before_tool_exec = None
            stream_handler.on_after_tool_exec = None
            finish_live_stream(live, result.text)

            # Restore original model after routed call
            if routed_model_id is not None:
                client.set_model(routed_model_id)
                stream_handler.model_id = routed_model_id

            print_usage_stats(result)
            print_separator()

            # Persist tool call context before the final assistant message
            if result.tool_messages:
                logger.add_tool_messages(result.tool_messages, agent_name=agent_name)

            logger.add_message(
                "assistant",
                result.text,
                prompt_tokens=result.usage.prompt_tokens,
                completion_tokens=result.usage.completion_tokens,
                total_tokens=result.usage.total_tokens,
                cost_usd=result.cost_usd,
                ttft_ms=result.metrics.ttft_ms,
                total_latency_ms=result.metrics.total_latency_ms,
                agent_name=agent_name,
            )

            # Record context utilization for token economics instrumentation
            if context_metadata and result.text:
                section_names = [s.name for s in context_metadata.sections]
                logger.record_utilization(result.text, section_names)

            # Handle delegation to a specialized agent
            if result.delegate_to and result.delegate_to in agent_registry:
                delegate_meta = agent_registry[result.delegate_to]
                all_delegate_tools = _assemble_agent_tools(
                    delegate_meta, shared_tools, tool_groups,
                )
                all_delegate_tools.extend(_make_agent_vault_tools(delegate_meta, config, vault_config))
                delegate_agent = _instantiate_agent(
                    delegate_meta, client, model_id, all_delegate_tools,
                    skill_registry=skill_registry,
                    card_search_tool=card_search_tool,
                )
                agent_session = _run_agent_session(
                    delegate_agent, delegate_meta.name, stream_handler,
                    logger, session,
                    initial_message=result.delegate_task,
                    context=result.delegate_context,
                    prior_session=last_agent_session,
                )
                # Store for next delegation + inject summary into JARVIS history
                last_agent_session = agent_session
                if agent_session:
                    summary = (
                        f"[Completed session with {delegate_meta.name} agent"
                        f" — {len(agent_session)} messages exchanged]"
                    )
                    active_agent.add_to_history("assistant", summary)

    except KeyboardInterrupt:
        print("\n")

    finally:
        logger.save()
        print("Goodbye!")


if __name__ == "__main__":
    main()
