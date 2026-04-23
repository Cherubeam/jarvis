"""
Command-line interface for the personal assistant.
Ties everything together.
"""

import argparse
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from rich.spinner import Spinner
from rich.text import Text

from apps.cli.display import (
    console,
    create_prompt_session,
    finish_live_stream,
    finish_waiting,
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
    start_waiting_spinner,
)
from packages.agents.base import agent_from_meta
from packages.agents.jarvis.agent import JarvisAgent
from packages.agents.prompt_includes import format_issue, validate_agent_includes
from packages.agents.registry import AgentMeta, get_by_command
from packages.core.daily_summary import (
    DailySummaryFailure,
    build_daily_summary_request,
)
from packages.core.filesystem_access import load_filesystem_guard
from packages.core.history import summarize_history, trim_tool_results
from packages.core.llm_client import LLMClient
from packages.core.memory import ConversationLogger
from packages.core.model_resolver import get_api_key, resolve_model
from packages.core.model_router import route_query
from packages.core.pricing import ModelPricing, get_model_pricing
from packages.core.stream_handler import StreamHandler, StreamResult
from packages.core.tools.base import ToolDefinition
from packages.integrations.obsidian.vault import load_vault_config
from packages.integrations.obsidian.writer import CLIConfirmationHandler, append_to_daily_note
from packages.telemetry.metrics import MetricsTracker

try:
    CLIENT_VERSION = version("jarvis")
except PackageNotFoundError:
    # Running outside an editable/installed context (e.g. raw PYTHONPATH).
    CLIENT_VERSION = "dev"


def _assemble_agent_tools(
    meta: AgentMeta,
    shared_tools: list[Any],
    tool_groups: dict[str, list[Any]],
    only_tool_groups: set[str] | None = None,
    include_shared: bool = True,
) -> list[Any]:
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
    extra_tools: list[Any] | None = None,
    skill_registry: dict[str, Any] | None = None,
    card_search_tool: ToolDefinition | None = None,
    skill_names_override: list[str] | None = None,
    prompt_includes_override: dict[str, str] | None = None,
) -> Any:
    """Create an agent from AgentMeta via agent_from_meta()."""
    if meta.meta_path is None:
        raise ValueError(f"AgentMeta {meta.name!r} has no meta_path; cannot instantiate")
    return agent_from_meta(
        meta.meta_path,
        client,
        model_id,
        extra_tools=extra_tools or None,
        skill_registry=skill_registry,
        card_search_tool=card_search_tool,
        skill_names_override=skill_names_override,
        prompt_includes_override=prompt_includes_override,
    )


def _make_agent_vault_tools(meta: AgentMeta, config: dict[str, Any], vault_config: Any) -> list[Any]:
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
            vault_config,
            CLIConfirmationHandler(),
            target_dir=target_dir,
            template_path=template_path,
        )
    except Exception:
        return []


def stream_and_track(
    client: LLMClient,
    messages: list[dict[str, Any]],
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


def _warn_on_prompt_include_issues(agent_registry: dict[str, AgentMeta]) -> None:
    """Print a startup warning block for any non-canonical prompt_includes.

    Canonical = the agent's local ``prompts/<name>.md`` or the shared
    ``_shared/prompts/<name>.md``. Anything else (``.md.example`` fallback
    or nothing at all) is flagged so the user can fix it before it bites
    them mid-conversation.
    """
    meta_paths = [m.meta_path for m in agent_registry.values() if m.meta_path is not None]
    issues = validate_agent_includes(meta_paths)
    if not issues:
        return
    print_system("\n[prompt_includes] Non-canonical include resolution:")
    for issue in issues:
        print_system(f"  - {format_issue(issue)}")
    print_system("")


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override into base.

    Semantics:
    - Nested dicts are merged key-by-key.
    - Lists are replaced wholesale (not concatenated). This matches user
      expectation for keys like mcp.servers or developer.scope.
    - Any non-dict value in override replaces the base value at that key.

    Returns a new dict; inputs are not mutated.
    """
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config() -> dict[str, Any]:
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
        config = {}

    # Override with local config if exists (deep-merged so partial overrides
    # don't clobber sibling defaults, e.g. obsidian.vault_path wiping other
    # obsidian.* keys).
    if local_config_path.exists():
        with open(local_config_path) as f:
            local_config = yaml.safe_load(f) or {}
        config = _deep_merge(config, local_config)

    # Store paths for later use
    config["_paths"] = {
        "jarvis_dir": jarvis_dir,
    }

    return config


def handle_daily_summary(
    config: dict[str, Any],
    client: LLMClient,
    logger: ConversationLogger,
    system_prompt: str,
    metrics_tracker: MetricsTracker,
    pricing: ModelPricing | None,
    model_id: str,
    target_date: str | None = None,
) -> None:
    """Handle the /daily-summary command.

    Args:
        target_date: Optional ISO date string (YYYY-MM-DD). Defaults to today.
    """
    # Validate date format early
    if target_date is not None:
        from datetime import date

        try:
            date.fromisoformat(target_date)
        except ValueError:
            print_error(f"\nInvalid date format: '{target_date}'. Use YYYY-MM-DD.\n")
            return

    fs_guard = load_filesystem_guard(config)
    vault_config = load_vault_config(config, filesystem_guard=fs_guard)

    try:
        daily_prompt = JarvisAgent.get_daily_note_instructions()
    except FileNotFoundError:
        print("\nDaily note prompt file not found.\n")
        return

    request = build_daily_summary_request(
        vault_config=vault_config,
        system_prompt=system_prompt,
        history=logger.get_messages_for_api(),
        daily_prompt=daily_prompt,
        target_date=target_date,
    )
    if isinstance(request, DailySummaryFailure):
        print_error(f"\n{request.message}\n")
        return
    assert vault_config is not None  # narrowed: builder returns Failure when None

    # Stream LLM response with activity spinner
    print_assistant_prefix("JARVIS")
    live, buf = start_live_stream()

    handler = StreamHandler(client, metrics_tracker, pricing, model_id)
    handler.max_tokens = 4096
    handler.on_chunk = make_live_chunk_handler(live, buf)
    result = handler.stream(request.messages, print_chunks=True)

    finish_live_stream(live, result.text)

    # Log the exchange so save() writes conversation + prints session summary
    logger.add_message("user", "/daily-summary")
    logger.add_message(
        "assistant",
        result.text,
        prompt_tokens=result.usage.prompt_tokens,
        completion_tokens=result.usage.completion_tokens,
        total_tokens=result.usage.total_tokens,
        cache_read_tokens=result.usage.cache_read_tokens,
        cache_write_tokens=result.usage.cache_write_tokens,
        cost_usd=result.cost_usd,
        ttft_ms=result.metrics.ttft_ms,
        total_latency_ms=result.metrics.total_latency_ms,
        agent_name="JARVIS",
    )

    # Write to vault with diff + confirmation
    confirmation = CLIConfirmationHandler()
    write_result = append_to_daily_note(result.text, vault_config, confirmation, date=target_date)

    if write_result.success:
        print(f"\n{write_result.message}\n")
    else:
        print(f"\n{write_result.message}\n")

    print_usage_stats(result)


def handle_model_command(
    payload: str,
    config: dict[str, Any],
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
            f"${new_pricing.prompt_cost * 1_000_000:.2f}/${new_pricing.completion_cost * 1_000_000:.2f} per 1M tokens"
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
    agent: Any,
    agent_name: str,
    stream_handler: StreamHandler,
    logger: ConversationLogger,
    session: Any,
    initial_message: str | None = None,
    context: str | None = None,
    prior_session: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
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

    session_history: list[dict[str, Any]] = []

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
        result = _run_with_display(
            stream_handler,
            agent,
            user_input,
            messages_override=trim_tool_results(session_history[:-1]),
        )

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
            cache_read_tokens=result.usage.cache_read_tokens,
            cache_write_tokens=result.usage.cache_write_tokens,
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

    print_system("\nReturning to JARVIS.\n")
    return session_history


def _run_with_display(
    stream_handler: StreamHandler,
    agent: Any,
    user_input: str,
    print_chunks: bool = True,
    messages_override: list[dict[str, Any]] | None = None,
) -> StreamResult:
    """Run agent with appropriate display (streaming or spinner)."""
    if stream_handler.streaming:
        live, buf = start_live_stream()
        stream_handler.on_chunk = make_live_chunk_handler(live, buf)
    else:
        live = start_waiting_spinner()

    def _resume_spinner() -> None:
        live.update(Spinner("dots", text=Text(" Thinking…", style="dim")))
        live.start()

    stream_handler.on_before_tool_exec = lambda: live.stop()
    stream_handler.on_after_tool_exec = _resume_spinner
    result = agent.run(
        user_input,
        stream_handler,
        print_chunks=print_chunks,
        messages_override=messages_override,
    )
    stream_handler.on_chunk = None
    stream_handler.on_before_tool_exec = None
    stream_handler.on_after_tool_exec = None

    if stream_handler.streaming:
        finish_live_stream(live, result.text)
    else:
        finish_waiting(live, result.text)
    final: StreamResult = result
    return final


def _handle_agent_command(
    command: str,
    payload: str,
    client: LLMClient,
    stream_handler: StreamHandler,
    logger: ConversationLogger,
    model_id: str,
    agent_registry: dict[str, Any],
    shared_tools: list[Any] | None = None,
    tool_groups: dict[str, list[Any]] | None = None,
    session: Any = None,
    skill_registry: dict[str, Any] | None = None,
    card_search_tool: ToolDefinition | None = None,
    config: dict[str, Any] | None = None,
    vault_config: Any = None,
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
        meta,
        client,
        model_id,
        all_tools or None,
        skill_registry=skill_registry,
        card_search_tool=card_search_tool,
    )

    if not payload:
        _run_agent_session(agent, meta.name, stream_handler, logger, session)
        return True

    logger.add_message("user", f"{command} {payload}")

    print_agent_prefix(meta.name)
    result = _run_with_display(stream_handler, agent, payload)

    print_usage_stats(result)
    print_separator()

    logger.add_message(
        "assistant",
        result.text,
        prompt_tokens=result.usage.prompt_tokens,
        completion_tokens=result.usage.completion_tokens,
        total_tokens=result.usage.total_tokens,
        cache_read_tokens=result.usage.cache_read_tokens,
        cache_write_tokens=result.usage.cache_write_tokens,
        cost_usd=result.cost_usd,
        ttft_ms=result.metrics.ttft_ms,
        total_latency_ms=result.metrics.total_latency_ms,
        agent_name=meta.name,
    )
    return True


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    config = load_config()

    # All session-component wiring lives in apps/cli/session_factory.build_session.
    # The CLI passes its own ConfirmationHandler + tool-feedback printer.
    from apps.cli.session_factory import (
        assemble_agent_tools as _assemble_agent_tools,
    )
    from apps.cli.session_factory import (
        build_session,
        make_agent_vault_tools,
    )
    from apps.cli.session_factory import (
        instantiate_agent as _instantiate_agent,
    )

    confirmation_handler = CLIConfirmationHandler()
    try:
        components = build_session(
            args,
            config,
            confirmation_handler,
            on_tool_call=print_tool_feedback,
            client_label="cli",
            auto_confirm=getattr(args, "auto_confirm", False),
        )
    except RuntimeError as e:
        print_error(f"Error: {e}")
        sys.exit(1)

    jarvis_dir = components.jarvis_dir
    model_id = components.model_id
    client = components.client
    pricing = components.pricing
    metrics_tracker = components.metrics_tracker
    stream_handler = components.stream_handler
    logger = components.logger
    system_prompt = components.system_prompt
    context_metadata = components.context_metadata
    agent_registry = components.agent_registry
    skill_registry = components.skill_registry
    shared_tools = components.shared_tools
    tool_groups = components.tool_groups
    card_search_tool = components.card_search_tool
    vault_config = components.vault_config
    active_agent = components.active_agent
    agent_name = components.agent_name
    mcp_manager = components.mcp_manager

    # Helper: bind the CLI confirmation handler into delegate-agent vault tools.
    def _make_agent_vault_tools(meta: AgentMeta, _config: dict[str, Any], _vc: Any) -> list[Any]:
        return make_agent_vault_tools(meta, _config, _vc, confirmation_handler)

    # Pricing display string for the startup banner.
    if pricing:
        price_info = (
            f"(${pricing.prompt_cost * 1_000_000:.2f}/${pricing.completion_cost * 1_000_000:.2f} per 1M tokens)"
        )
    else:
        price_info = "(pricing unavailable)"

    # Print startup info
    commands = None
    if agent_registry:
        cmds = [m.command for m in agent_registry.values()]
        cmds.append("/daily-summary")
        cmds.append("/outcomes")
        cmds.append("/model")
        cmds.append("/stream")
        commands = cmds
    print_startup(agent_name, model_id, price_info, commands)

    # Create prompt_toolkit session for robust input handling
    cli_cfg = config.get("cli", {})
    history_file = cli_cfg.get("history_file", "data/.cli_history")
    if history_file:
        history_file = str(jarvis_dir / history_file)
    session = create_prompt_session(history_file)

    # Track last agent session for agent-to-agent handoff
    last_agent_session: list[dict[str, Any]] | None = None

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
                    handle_daily_summary(
                        config,
                        client,
                        logger,
                        system_prompt,
                        metrics_tracker,
                        pricing,
                        model_id,
                        target_date=payload.strip() or None,
                    )
                    continue

                if command == "/model":
                    model_id, pricing = handle_model_command(
                        payload,
                        config,
                        client,
                        model_id,
                        stream_handler,
                    )
                    continue

                if command == "/stream":
                    stream_handler.streaming = not stream_handler.streaming
                    state = "on" if stream_handler.streaming else "off (caching enabled)"
                    print_system(f"\nStreaming: {state}\n")
                    continue

                if command == "/outcomes":
                    outcomes_cfg = config.get("outcomes", {})
                    if not outcomes_cfg.get("enabled", True):
                        print_system("Outcome tracking is disabled. Set outcomes.enabled: true in config to enable.")
                    else:
                        from apps.cli.review import handle_review_command

                        outcomes_dir = jarvis_dir / outcomes_cfg.get("dir", "data/outcomes")
                        handle_review_command(outcomes_dir, console, session)
                    continue

                # Agent-routed commands
                if _handle_agent_command(
                    command,
                    payload,
                    client,
                    stream_handler,
                    logger,
                    model_id,
                    agent_registry,
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
            history_bytes = sum(len(str(m.get("content", "")).encode("utf-8")) for m in history)
            logger.metrics.record_history_tokens(history_bytes // 4)

            # History summarization (opt-in via config)
            summ_config = config.get("summarization", {})
            if summ_config.get("enabled", False):
                fast_model = resolve_model("fast", config).model_id
                history = summarize_history(
                    history,
                    client,
                    model_id=fast_model,
                    token_threshold=summ_config.get("token_threshold", 40000),
                    keep_recent=summ_config.get("keep_recent", 10),
                )

            logger.add_message("user", user_input)

            # Intelligent model routing (opt-in via config)
            routed_model_id = None
            routed_display: str | None = None
            if config.get("routing", {}).get("enabled", False):
                decision = route_query(user_input, config, agent_name=agent_name)
                if decision.resolved.model_id != model_id:
                    routed_model_id = model_id  # save original to restore
                    routed_display = decision.resolved.display_name
                    client.set_model(decision.resolved.model_id)
                    stream_handler.model_id = decision.resolved.model_id

            print_assistant_prefix(agent_name)
            result = _run_with_display(
                stream_handler,
                active_agent,
                user_input,
                messages_override=trim_tool_results(history),
            )

            # Restore original model after routed call
            if routed_model_id is not None:
                client.set_model(routed_model_id)
                stream_handler.model_id = routed_model_id

            print_usage_stats(result, routed_model=routed_display)
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
                cache_read_tokens=result.usage.cache_read_tokens,
                cache_write_tokens=result.usage.cache_write_tokens,
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
                    delegate_meta,
                    shared_tools,
                    tool_groups,
                )
                all_delegate_tools.extend(_make_agent_vault_tools(delegate_meta, config, vault_config))
                delegate_agent = _instantiate_agent(
                    delegate_meta,
                    client,
                    model_id,
                    all_delegate_tools,
                    skill_registry=skill_registry,
                    card_search_tool=card_search_tool,
                )
                agent_session = _run_agent_session(
                    delegate_agent,
                    delegate_meta.name,
                    stream_handler,
                    logger,
                    session,
                    initial_message=result.delegate_task,
                    context=result.delegate_context,
                    prior_session=last_agent_session,
                )
                # Store for next delegation + inject summary into JARVIS history
                last_agent_session = agent_session
                if agent_session:
                    summary = (
                        f"[Completed session with {delegate_meta.name} agent — {len(agent_session)} messages exchanged]"
                    )
                    active_agent.add_to_history("assistant", summary)

    except KeyboardInterrupt:
        print("\n")

    finally:
        if mcp_manager is not None:
            mcp_manager.shutdown()
        logger.save()
        print("Goodbye!")


if __name__ == "__main__":
    main()
