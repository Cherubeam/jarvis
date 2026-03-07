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
from packages.agents.jarvis.agent import JarvisAgent
from packages.agents.registry import discover_agents, get_by_command
from packages.core.context_builder import build_system_prompt, parse_frontmatter
from packages.skills.base import BaseSkill
from packages.skills.registry import discover_skills, get_skill_by_command
from packages.core.llm_client import LLMClient
from packages.core.memory import ConversationLogger, hash_content
from packages.core.pricing import ModelPricing, get_model_pricing, format_cost
from packages.core.stream_handler import StreamHandler, StreamResult
from packages.integrations.things3.task_sync import sync_tasks_to_file
from packages.integrations.obsidian.vault import load_vault_config, read_note, get_daily_note_path
from packages.integrations.obsidian.callout import find_jarvis_callout, CalloutNotFound
from packages.integrations.obsidian.writer import CLIConfirmationHandler, append_to_daily_note
from packages.integrations.obsidian.prompts import get_daily_note_instructions
from packages.telemetry.metrics import MetricsTracker

CLIENT_VERSION = "0.4.0"


def stream_and_track(
    client: LLMClient,
    messages: list[dict],
    metrics_tracker: MetricsTracker,
    pricing: ModelPricing | None,
    model_id: str,
    print_chunks: bool = False,
) -> StreamResult:
    """Stream an LLM response, tracking metrics and cost.

    Thin wrapper around StreamHandler.stream() for backward compatibility.
    """
    handler = StreamHandler(client, metrics_tracker, pricing, model_id)
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


def handle_daily_summary(config: dict, client: LLMClient, logger: ConversationLogger,
                         system_prompt: str, metrics_tracker: MetricsTracker,
                         pricing: ModelPricing | None, model_id: str) -> None:
    """Handle the /daily-summary command."""
    vault_config = load_vault_config(config)
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
        daily_prompt = get_daily_note_instructions()
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

    # Collect streamed LLM response for the summary
    print_system("\nGenerating daily summary...")
    result = stream_and_track(client, messages, metrics_tracker, pricing, model_id)

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
    )

    # Write to vault with diff + confirmation
    handler = CLIConfirmationHandler()
    write_result = append_to_daily_note(result.text, vault_config, handler)

    if write_result.success:
        print(f"\n{write_result.message}\n")
    else:
        print(f"\n{write_result.message}\n")

    print_usage_stats(result)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="JARVIS personal assistant")
    parser.add_argument(
        "--agent",
        type=str,
        default=None,
        help="Run a standalone agent instead of the default JARVIS orchestrator (e.g. --agent writing)",
    )
    parser.add_argument(
        "--skill",
        type=str,
        default=None,
        help="Run a standalone skill (e.g. --skill nano-banana-pro)",
    )
    return parser.parse_args(argv)


def _run_agent_session(
    agent,
    agent_name: str,
    stream_handler: StreamHandler,
    logger: ConversationLogger,
    session,
    initial_message: str | None = None,
) -> None:
    """Run a multi-turn agent session until the user types /exit or /back.

    Args:
        agent: The agent instance to run.
        agent_name: Display name for the agent.
        stream_handler: StreamHandler for streaming + metrics.
        logger: ConversationLogger for persistence.
        session: prompt_toolkit session for user input.
        initial_message: If set, process this as the first message before prompting.
    """
    print_system(f"\nEntering {agent_name} session. Type /exit to return to JARVIS.\n")

    session_history: list[dict] = []

    def _process_message(user_input: str) -> None:
        logger.add_message("user", user_input)
        session_history.append({"role": "user", "content": user_input})

        print_agent_prefix(agent_name)
        live, buf = start_live_stream()
        stream_handler.on_chunk = make_live_chunk_handler(live, buf)
        result = agent.run(
            user_input,
            stream_handler,
            print_chunks=True,
            messages_override=session_history[:-1],
        )
        stream_handler.on_chunk = None
        finish_live_stream(live, result.text)

        print_usage_stats(result)
        print_separator()

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
        )

    # Process initial message if provided (e.g. from delegation)
    if initial_message:
        _process_message(initial_message)

    try:
        while True:
            try:
                user_input = prompt_user(session)
            except EOFError:
                break

            if not user_input:
                continue
            if user_input.strip().lower() in ("/exit", "/back"):
                break

            _process_message(user_input)
    except KeyboardInterrupt:
        pass

    print_system(f"\nReturning to JARVIS.\n")


def _handle_agent_command(
    command: str,
    payload: str,
    client: LLMClient,
    stream_handler: StreamHandler,
    logger: ConversationLogger,
    model_id: str,
    agent_registry: dict,
    extra_tools: list | None = None,
    session=None,
) -> bool:
    """Route a slash command to the matching agent. Returns True if handled."""
    meta = get_by_command(command, agent_registry)
    if meta is None:
        return False

    # Pass extra_tools to agents that accept them (e.g. TacticsAgent)
    import inspect
    sig = inspect.signature(meta.agent_class.__init__)
    if "extra_tools" in sig.parameters and extra_tools:
        agent = meta.agent_class(llm_client=client, model=model_id, extra_tools=extra_tools)
    else:
        agent = meta.agent_class(llm_client=client, model=model_id)

    if not payload:
        if session is not None:
            _run_agent_session(agent, meta.name, stream_handler, logger, session)
        else:
            print_system(f"\nUsage: {command} <text>")
            print_system(f"  {meta.description}\n")
        return True

    logger.add_message("user", f"{command} {payload}")

    print_agent_prefix(meta.name)
    live, buf = start_live_stream()
    stream_handler.on_chunk = make_live_chunk_handler(live, buf)
    result = agent.run(payload, stream_handler, print_chunks=True)
    stream_handler.on_chunk = None
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
    )
    return True


def _handle_skill_command(
    command: str,
    payload: str,
    client: LLMClient,
    stream_handler: StreamHandler,
    logger: ConversationLogger,
    model_id: str,
    skill_registry: dict,
) -> bool:
    """Route a slash command to the matching skill. Returns True if handled."""
    meta = get_skill_by_command(command, skill_registry)
    if meta is None:
        return False

    if not payload:
        print_system(f"\nUsage: {command} <text>")
        print_system(f"  {meta.description}\n")
        return True

    skill = BaseSkill.from_skill_md(meta.path, client, model=model_id)

    logger.add_message("user", f"{command} {payload}")

    print_agent_prefix(meta.name)
    live, buf = start_live_stream()
    stream_handler.on_chunk = make_live_chunk_handler(live, buf)
    result = skill.run(payload, stream_handler, print_chunks=True)
    stream_handler.on_chunk = None
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
    )
    return True


def main(argv: list[str] | None = None):
    args = parse_args(argv)
    config = load_config()

    jarvis_dir = config["_paths"]["jarvis_dir"]
    model_id = config["openrouter"]["default_model"]

    # Initialize components - paths now relative to jarvis root
    context_dir = jarvis_dir / config.get("paths", {}).get("context_dir", "data/context")
    conversations_dir = jarvis_dir / config.get("paths", {}).get("conversations_dir", "data/conversations")

    # Sync tasks from Things 3 (if enabled)
    sync_tasks_to_file(context_dir / "tasks.md", config)

    system_prompt = build_system_prompt(context_dir)

    client = LLMClient(
        api_key=config["openrouter"]["api_key"],
        default_model=model_id,
        provider="openrouter"
    )

    # Discover registered agents and skills for slash-command routing
    agent_registry = discover_agents()
    skill_registry = discover_skills()

    # Initialize RAG if enabled
    api_key = config["openrouter"]["api_key"]
    extra_tools = []
    rag_cfg = config.get("rag", {})
    if rag_cfg.get("enabled", False):
        try:
            from packages.core.rag.indexer import ConversationIndexer
            from packages.core.tools.conversation_recall import make_conversation_recall_tool

            db_path = jarvis_dir / rag_cfg.get("db_path", "data/rag/chroma")
            embedding_model = rag_cfg.get("embedding_model", "openrouter/openai/text-embedding-3-small")

            indexer = ConversationIndexer(db_path, embedding_model, api_key)
            n_new = indexer.index_new(conversations_dir)
            if n_new:
                print_system(f"[RAG] Indexed {n_new} new conversation(s).")

            recall_tool = make_conversation_recall_tool(db_path, embedding_model, api_key)
            extra_tools.append(recall_tool)

            # Index deck-skill cards if any deck-skills have a deck.yaml
            if rag_cfg.get("index_cards", True):
                deck_dirs = [
                    meta.path for meta in skill_registry.values()
                    if (meta.path / "deck.yaml").is_file()
                ]
                if deck_dirs:
                    from packages.core.rag.card_indexer import CardIndexer
                    from packages.core.tools.card_search import make_card_search_tool

                    card_indexer = CardIndexer(db_path, embedding_model, api_key)
                    n_cards = card_indexer.index_new(deck_dirs)
                    if n_cards:
                        print_system(f"[RAG] Indexed {n_cards} new card(s).")

                    card_search_tool = make_card_search_tool(db_path, embedding_model, api_key)
                    extra_tools.append(card_search_tool)

        except ImportError:
            print_system("[RAG] chromadb not installed — recall disabled. Run: uv add chromadb")
        except Exception as e:
            print_system(f"[RAG] Startup failed — recall disabled. ({e})")

    # Initialize agent-only tools list (tools available to delegated agents but not JARVIS)
    agent_only_tools: list = []

    # Initialize blog tools for writing agent (if obsidian enabled)
    # Blog tools are agent-only so JARVIS delegates instead of reading/reviewing directly.
    vault_config = load_vault_config(config)
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
                agent_only_tools.extend(blog_tools)
                print_system(f"[Blog] {len(blog_tools)} blog tools loaded.")
        except Exception as e:
            print_system(f"[Blog] Startup failed — blog tools disabled. ({e})")

    # Initialize content-evaluator tool (if skill directory exists)
    # This tool is for specialized agents only — JARVIS delegates instead of evaluating directly.
    skill_dir = jarvis_dir / "packages" / "skills" / "content-evaluator"
    if (skill_dir / "SKILL.md").is_file():
        try:
            from packages.core.tools.content_evaluator import make_content_evaluator_tool

            evaluator_tool = make_content_evaluator_tool(skill_dir, client, model_id)
            agent_only_tools.append(evaluator_tool)
            print_system("[Tools] Content evaluator loaded.")
        except Exception as e:
            print_system(f"[Tools] Content evaluator failed: {e}")

    # Build the active agent (or skill in standalone mode)
    active_skill = None
    if args.skill:
        if args.skill not in skill_registry:
            available = ", ".join(sorted(skill_registry)) or "(none)"
            print_error(f"Error: unknown skill '{args.skill}'. Available: {available}")
            sys.exit(1)
        skill_meta = skill_registry[args.skill]
        active_skill = BaseSkill.from_skill_md(skill_meta.path, client, model=model_id)
        agent_name = skill_meta.name
        # Create a dummy active_agent config for logger compatibility
        active_agent = active_skill
    elif args.agent:
        if args.agent not in agent_registry:
            available = ", ".join(sorted(agent_registry)) or "(none)"
            print_error(f"Error: unknown agent '{args.agent}'. Available: {available}")
            sys.exit(1)
        meta = agent_registry[args.agent]
        # Pass extra_tools + agent_only_tools to agents that accept them
        all_agent_tools = extra_tools + agent_only_tools
        import inspect
        sig = inspect.signature(meta.agent_class.__init__)
        if "extra_tools" in sig.parameters and all_agent_tools:
            active_agent = meta.agent_class(llm_client=client, model=model_id, extra_tools=all_agent_tools)
        else:
            active_agent = meta.agent_class(llm_client=client, model=model_id)
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
            extra_tools=extra_tools or None,
            available_agents=available_agents or None,
        )
        agent_name = "JARVIS"

    # Build schema config dicts for ConversationLogger
    model_config = {
        "id": model_id,
        "provider": "openrouter",
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
                context_files.append({
                    "path": str(f.relative_to(jarvis_dir)),
                    "hash": f"sha256:{hash_content(content)}",
                    "size_bytes": f.stat().st_size,
                })
        # Include project context files with frontmatter metadata
        projects_dir = context_dir / "projects"
        if projects_dir.is_dir():
            for f in sorted(projects_dir.glob("*.md")):
                content = f.read_text(encoding="utf-8")
                meta_fm, _ = parse_frontmatter(content)
                is_active = meta_fm.get("active", True)
                entry = {
                    "path": str(f.relative_to(jarvis_dir)),
                    "hash": f"sha256:{hash_content(content)}",
                    "size_bytes": f.stat().st_size,
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
    )

    # Print startup info
    commands = None
    if agent_registry or skill_registry:
        cmds = [m.command for m in agent_registry.values()]
        cmds.extend(m.command for m in skill_registry.values())
        cmds.append("/skills")
        cmds.append("/daily-summary")
        commands = cmds
    print_startup(agent_name, model_id, price_info, commands)

    # Create prompt_toolkit session for robust input handling
    cli_cfg = config.get("cli", {})
    history_file = cli_cfg.get("history_file", "data/.cli_history")
    if history_file:
        history_file = str(jarvis_dir / history_file)
    session = create_prompt_session(history_file)

    # Main chat loop
    try:
        while True:
            try:
                user_input = prompt_user(session)
            except EOFError:
                break

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit"):
                break

            # Handle slash commands
            if user_input.startswith("/"):
                parts = user_input.split(None, 1)
                command = parts[0]
                payload = parts[1] if len(parts) > 1 else ""

                # Built-in commands
                if command == "/daily-summary":
                    handle_daily_summary(config, client, logger, system_prompt,
                                         metrics_tracker, pricing, model_id)
                    continue

                if command == "/skills":
                    if not skill_registry:
                        print_system("\nNo skills available.\n")
                    else:
                        print_system("\nAvailable skills:")
                        for meta in skill_registry.values():
                            py_marker = " [+py]" if meta.has_skill_py else ""
                            print_system(f"  {meta.command}  — {meta.description}{py_marker}")
                        print_system("")
                    continue

                # Agent-routed commands
                all_agent_tools = extra_tools + agent_only_tools
                if _handle_agent_command(
                    command, payload, client, stream_handler, logger,
                    model_id, agent_registry,
                    extra_tools=all_agent_tools or None,
                    session=session,
                ):
                    continue

                # Skill-routed commands
                if _handle_skill_command(
                    command, payload, client, stream_handler, logger,
                    model_id, skill_registry,
                ):
                    continue

                print_error(f"\nUnknown command: {command}\n")
                continue

            # Regular chat — route through active agent
            # Grab existing history before adding user message (run() appends it)
            history = logger.get_messages_for_api()
            logger.add_message("user", user_input)

            print_assistant_prefix(agent_name)
            live, buf = start_live_stream()
            stream_handler.on_chunk = make_live_chunk_handler(live, buf)
            result = active_agent.run(
                user_input,
                stream_handler,
                print_chunks=True,
                messages_override=history,
            )
            stream_handler.on_chunk = None
            finish_live_stream(live, result.text)

            print_usage_stats(result)
            print_separator()

            # Persist tool call context before the final assistant message
            if result.tool_messages:
                logger.add_tool_messages(result.tool_messages)

            logger.add_message(
                "assistant",
                result.text,
                prompt_tokens=result.usage.prompt_tokens,
                completion_tokens=result.usage.completion_tokens,
                total_tokens=result.usage.total_tokens,
                cost_usd=result.cost_usd,
                ttft_ms=result.metrics.ttft_ms,
                total_latency_ms=result.metrics.total_latency_ms,
            )

            # Handle delegation to a specialized agent
            if result.delegate_to and result.delegate_to in agent_registry:
                delegate_meta = agent_registry[result.delegate_to]
                all_delegate_tools = agent_only_tools
                import inspect as _inspect
                _sig = _inspect.signature(delegate_meta.agent_class.__init__)
                if "extra_tools" in _sig.parameters and all_delegate_tools:
                    delegate_agent = delegate_meta.agent_class(
                        llm_client=client, model=model_id, extra_tools=all_delegate_tools,
                    )
                else:
                    delegate_agent = delegate_meta.agent_class(
                        llm_client=client, model=model_id,
                    )
                _run_agent_session(
                    delegate_agent, delegate_meta.name, stream_handler,
                    logger, session, initial_message=result.delegate_task,
                )

    except KeyboardInterrupt:
        print("\n")

    finally:
        logger.save()
        print("Goodbye!")


if __name__ == "__main__":
    main()
