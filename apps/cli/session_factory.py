"""
Session factory — assembles the agent + tools + logger + stream handler that
both the CLI and the GUI need at startup.

Extracted from apps/cli/main.py so the GUI can reuse the exact same wiring
with a different ConfirmationHandler injected. The CLI passes
CLIConfirmationHandler(); the GUI passes WebConfirmationHandler() per turn.

Behavior parity with the previous in-line wiring is intentional. If you
change something here, run the CLI smoke test (`uv run jarvis`) to verify.
"""

from __future__ import annotations

import platform
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from apps.cli.display import print_system
from packages.agents.base import agent_from_meta
from packages.agents.jarvis.agent import JarvisAgent
from packages.agents.prompt_includes import format_issue, validate_agent_includes
from packages.agents.registry import AgentMeta, discover_agents
from packages.core.context_builder import build_system_prompt_with_metadata, parse_frontmatter
from packages.core.filesystem_access import load_filesystem_guard
from packages.core.llm_client import LLMClient
from packages.core.memory import ConversationLogger, generate_conversation_id, hash_content
from packages.core.model_resolver import collect_api_keys, get_api_key, resolve_model
from packages.core.pricing import ModelPricing, get_model_pricing
from packages.core.settings import Settings
from packages.core.stream_handler import StreamHandler
from packages.core.tools.base import ToolDefinition
from packages.integrations.obsidian.vault import load_vault_config
from packages.integrations.obsidian.writer import ConfirmationHandler
from packages.integrations.things3.task_sync import sync_tasks_to_file
from packages.skills.registry import discover_skills
from packages.telemetry.metrics import MetricsTracker

try:
    CLIENT_VERSION = version("jarvis")
except PackageNotFoundError:
    CLIENT_VERSION = "dev"


@dataclass
class SessionComponents:
    """Everything the chat loop (CLI or GUI) needs to handle a turn.

    Intentionally a bag-of-fields: the alternative is passing 14 args to
    every helper. The chat loop reads what it needs.
    """

    config: dict[str, Any]
    settings: Settings
    args: Any  # argparse.Namespace or a GUI-shim equivalent
    jarvis_dir: Path
    context_dir: Path
    conversations_dir: Path
    model_id: str
    provider: str
    api_keys: dict[str, str]
    client: LLMClient
    pricing: ModelPricing | None
    metrics_tracker: MetricsTracker
    stream_handler: StreamHandler
    logger: ConversationLogger
    conversation_id: str
    system_prompt: str
    context_metadata: Any
    agent_registry: dict[str, AgentMeta]
    skill_registry: dict[str, Any]
    shared_tools: list[Any] = field(default_factory=list)
    tool_groups: dict[str, list[Any]] = field(default_factory=dict)
    card_search_tool: Any = None
    vault_config: Any = None
    fs_guard: Any = None
    active_agent: Any = None
    agent_name: str = "JARVIS"
    mcp_manager: Any = None
    client_label: str = "cli"
    # Set by the GUI session to route per-turn confirmation prompts back to
    # the WS client. Unused by the CLI.
    _deferred_handler: Any = None


def _warn_on_prompt_include_issues(agent_registry: dict[str, AgentMeta]) -> None:
    meta_paths = [m.meta_path for m in agent_registry.values() if m.meta_path is not None]
    issues = validate_agent_includes(meta_paths)
    if not issues:
        return
    print_system("\n[prompt_includes] Non-canonical include resolution:")
    for issue in issues:
        print_system(f"  - {format_issue(issue)}")
    print_system("")


def make_agent_vault_tools(
    meta: AgentMeta,
    settings: Settings,
    vault_config: Any,
    confirmation_handler: ConfirmationHandler,
) -> list[Any]:
    """Create vault write tools scoped to an agent's `vault_writing` config section."""
    if vault_config is None or not meta.vault_writing:
        return []
    section = getattr(settings.obsidian.writing, meta.vault_writing, None)
    if section is None:
        return []
    target_dir = section.target_dir
    template_path = section.template_path
    if not target_dir:
        return []
    try:
        from packages.core.tools.vault_write_tools import make_vault_write_tools

        return make_vault_write_tools(
            vault_config,
            confirmation_handler,
            target_dir=target_dir,
            template_path=template_path,
        )
    except Exception:
        return []


def assemble_agent_tools(
    meta: AgentMeta,
    shared_tools: list[Any],
    tool_groups: dict[str, list[Any]],
    only_tool_groups: set[str] | None = None,
    include_shared: bool = True,
) -> list[Any]:
    """Assemble tools for an agent from shared_tools + its declared tool_groups."""
    agent_tools = list(shared_tools) if include_shared else []
    groups = only_tool_groups if only_tool_groups is not None else set(meta.tool_groups)
    for group_name in groups:
        if group_name in tool_groups:
            agent_tools.extend(tool_groups[group_name])
    return agent_tools


def instantiate_agent(
    meta: AgentMeta,
    client: LLMClient,
    model_id: str,
    extra_tools: list[Any] | None = None,
    skill_registry: dict[str, Any] | None = None,
    card_search_tool: ToolDefinition | None = None,
    skill_names_override: list[str] | None = None,
    prompt_includes_override: dict[str, str] | None = None,
) -> Any:
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


def build_session(
    args: Any,
    config: dict[str, Any],
    settings: Settings,
    confirmation_handler: ConfirmationHandler,
    *,
    on_tool_call: Callable[[str], None] | None = None,
    client_label: str = "cli",
    auto_confirm: bool = False,
) -> SessionComponents:
    """Build everything the chat loop (CLI or GUI) needs.

    Args:
        args: argparse.Namespace (CLI) or any duck-typed equivalent (GUI).
            Reads: args.model, args.agent, args.auto_confirm.
        config: Loaded config dict (from load_config()).
        confirmation_handler: CLIConfirmationHandler() for CLI; a
            WebConfirmationHandler() (or per-turn factory) for GUI.
        on_tool_call: Optional callback(tool_name) for stream-handler tool
            announcements. CLI passes print_tool_feedback. GUI passes None
            (events go via the typed on_event bus instead).
        client_label: 'cli' or 'gui' — recorded in conversation env metadata.
        auto_confirm: If True, developer-tool writes auto-approve (CLI dev
            mode). GUI never sets this.
    """
    jarvis_dir = config["_paths"]["jarvis_dir"]
    api_keys = collect_api_keys()

    model_source = getattr(args, "model", None) or settings.models.default
    resolved = resolve_model(model_source, settings.models)
    model_id = resolved.model_id

    if not get_api_key(resolved.provider, api_keys):
        raise RuntimeError(
            f"No API key for provider '{resolved.provider}'. Set {resolved.provider.upper()}_API_KEY in your .env file."
        )

    context_dir = jarvis_dir / settings.paths.context_dir
    conversations_dir = jarvis_dir / settings.paths.conversations_dir

    sync_tasks_to_file(context_dir / "tasks.md", settings.things3)

    system_prompt, context_metadata = build_system_prompt_with_metadata(context_dir)

    client = LLMClient(api_keys=api_keys, default_model=model_id)

    agent_registry = discover_agents()
    skill_registry = discover_skills()
    _warn_on_prompt_include_issues(agent_registry)

    conversation_id = generate_conversation_id()

    shared_tools: list[Any] = []
    tool_groups: dict[str, list[Any]] = {}
    card_search_tool = None

    rag_cfg = config.get("rag", {})
    if rag_cfg.get("enabled", False):
        try:
            from packages.core.rag.indexer import ConversationIndexer
            from packages.core.tools.conversation_recall import make_conversation_recall_tool

            db_path = jarvis_dir / rag_cfg.get("db_path", "data/rag/chroma")
            embedding_model = rag_cfg.get("embedding_model", "openrouter/openai/text-embedding-3-small")
            rag_api_key = get_api_key("openrouter", api_keys) or ""

            indexer = ConversationIndexer(db_path, embedding_model, rag_api_key)
            n_new = indexer.index_new(conversations_dir)
            if n_new:
                print_system(f"[RAG] Indexed {n_new} new conversation(s).")

            shared_tools.append(make_conversation_recall_tool(db_path, embedding_model, rag_api_key))

            outcomes_cfg_for_index = config.get("outcomes", {})
            if outcomes_cfg_for_index.get("enabled", True):
                from packages.core.rag.outcome_indexer import OutcomeIndexer

                outcomes_dir_for_index = jarvis_dir / outcomes_cfg_for_index.get("dir", "data/outcomes")
                outcome_indexer = OutcomeIndexer(db_path, embedding_model, rag_api_key)
                n_outcomes = outcome_indexer.index_new(outcomes_dir_for_index)
                if n_outcomes:
                    print_system(f"[RAG] Indexed {n_outcomes} new outcome(s).")

            if rag_cfg.get("index_cards", True):
                deck_dirs = [meta.path for meta in skill_registry.values() if (meta.path / "deck.yaml").is_file()]
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
            print_system("[RAG] chromadb not installed — recall disabled.")
        except Exception as e:
            print_system(f"[RAG] Startup failed — recall disabled. ({e})")

    fs_guard = load_filesystem_guard(config)
    vault_config = load_vault_config(settings.obsidian, filesystem_guard=fs_guard)

    if vault_config is not None:
        try:
            from packages.core.tools.vault_read_tools import make_vault_read_tools

            vault_read_tools = make_vault_read_tools(vault_config)
            shared_tools.extend(vault_read_tools)
            print_system(f"[Vault] {len(vault_read_tools)} vault read tools loaded.")
        except Exception as e:
            print_system(f"[Vault] Startup failed — vault read tools disabled. ({e})")

    cortex_cfg = config.get("cortex", {})
    if cortex_cfg.get("enabled", False):
        try:
            from packages.core.tools.cortex_search import make_cortex_search_tool
            from packages.integrations.cortex.client import CortexClient

            cortex_client = CortexClient(
                base_url=cortex_cfg.get("base_url", "http://127.0.0.1:8100"),
                timeout=cortex_cfg.get("timeout_seconds", 10),
            )
            shared_tools.append(make_cortex_search_tool(cortex_client))
            if cortex_client.is_available():
                print_system("[Cortex] Connected — vault semantic search enabled.")
            else:
                print_system("[Cortex] Service unreachable — tool registered but may fail.")
        except Exception as e:
            print_system(f"[Cortex] Startup failed — semantic search disabled. ({e})")

    outcomes_cfg = config.get("outcomes", {})
    if outcomes_cfg.get("enabled", True):
        try:
            from packages.core.tools.outcome_tools import make_outcome_tools

            outcomes_dir = jarvis_dir / outcomes_cfg.get("dir", "data/outcomes")
            outcomes_dir.mkdir(parents=True, exist_ok=True)
            shared_tools.extend(make_outcome_tools(outcomes_dir, fs_guard, conversation_id))
        except Exception as e:
            print_system(f"[Outcomes] Startup failed — track_recommendation disabled. ({e})")

        if rag_cfg.get("enabled", False):
            try:
                from packages.core.tools.outcome_recall import make_outcome_recall_tool

                db_path_for_outcomes = jarvis_dir / rag_cfg.get("db_path", "data/rag/chroma")
                embedding_model_for_outcomes = rag_cfg.get(
                    "embedding_model", "openrouter/openai/text-embedding-3-small"
                )
                outcomes_api_key = get_api_key("openrouter", api_keys) or ""
                shared_tools.append(
                    make_outcome_recall_tool(
                        db_path_for_outcomes,
                        embedding_model_for_outcomes,
                        outcomes_api_key,
                    )
                )
            except Exception as e:
                print_system(f"[Outcomes] Recall tool failed — disabled. ({e})")

    if vault_config is not None:
        try:
            from packages.core.tools.blog_tools import make_blog_tools

            blog_dir = settings.obsidian.writing.blog_dir
            template_path = settings.obsidian.writing.template_path
            if blog_dir:
                blog_tools = make_blog_tools(
                    vault_config,
                    confirmation_handler,
                    blog_dir,
                    template_path,
                )
                tool_groups["blog_tools"] = blog_tools
                print_system(f"[Blog] {len(blog_tools)} blog tools loaded.")
        except Exception as e:
            print_system(f"[Blog] Startup failed — blog tools disabled. ({e})")

    skill_dir = jarvis_dir / "packages" / "skills" / "content-evaluator"
    if (skill_dir / "SKILL.md").is_file():
        try:
            from packages.core.tools.content_evaluator import make_content_evaluator_tool

            tool_groups["content_evaluator"] = [make_content_evaluator_tool(skill_dir, client, model_id)]
            print_system("[Tools] Content evaluator loaded.")
        except Exception as e:
            print_system(f"[Tools] Content evaluator failed: {e}")

    dev_cfg = config.get("developer", {})
    if dev_cfg.get("enabled", True):
        try:
            from packages.core.tools.codebase_tools import make_codebase_tools
            from packages.core.tools.git_tools import make_git_tools
            from packages.core.tools.mutation_tools import make_mutation_tools
            from packages.core.tools.project_write_tools import make_project_write_tools
            from packages.core.tools.test_tools import make_test_runner_tool

            dev_scope = dev_cfg.get(
                "scope",
                [
                    "packages/agents/",
                    "packages/skills/",
                    "data/context/",
                    "data/prompts/",
                    "config/",
                ],
            )
            dev_extensions = dev_cfg.get("allowed_extensions", [".md", ".yaml", ".yml"])

            dev_tools: list[Any] = []
            dev_tools.extend(make_codebase_tools(jarvis_dir))
            dev_tools.extend(make_git_tools(jarvis_dir))
            dev_confirmation: ConfirmationHandler
            if auto_confirm:
                from packages.agents.developer.confirmation import AutoConfirmationHandler

                dev_confirmation = AutoConfirmationHandler(dev_scope, jarvis_dir)
            else:
                dev_confirmation = confirmation_handler
            dev_tools.extend(
                make_project_write_tools(
                    jarvis_dir,
                    dev_confirmation,
                    allowed_dirs=dev_scope,
                    allowed_extensions=dev_extensions,
                )
            )
            dev_tools.append(make_test_runner_tool(jarvis_dir))
            dev_tools.extend(make_mutation_tools(jarvis_dir))
            tool_groups["dev_tools"] = dev_tools
            print_system(f"[Developer] {len(dev_tools)} developer tools loaded.")
        except Exception as e:
            print_system(f"[Developer] Startup failed — developer tools disabled. ({e})")

    if vault_config is not None:
        try:
            from packages.core.tools.suggest_improvements import make_suggest_improvements_tool

            tool_groups["suggest_improvements"] = [make_suggest_improvements_tool(vault_config, confirmation_handler)]
            print_system("[Tools] Suggest improvements loaded.")
        except Exception as e:
            print_system(f"[Tools] Suggest improvements failed: {e}")

    from packages.core.tools.web_fetch import FETCH_URL_TOOL
    from packages.core.tools.web_search import WEB_SEARCH_TOOL

    tool_groups["web_tools"] = [WEB_SEARCH_TOOL, FETCH_URL_TOOL]
    print_system("[Tools] Web search + fetch loaded.")

    if settings.things3.enabled:
        try:
            from packages.core.tools.things3_tools import make_things3_tools

            things3_tools = make_things3_tools(settings.things3)
            if things3_tools:
                tool_groups["things3_tools"] = things3_tools
                print_system(f"[Tools] {len(things3_tools)} Things 3 tools loaded.")
        except Exception as e:
            print_system(f"[Tools] Things 3 tools failed: {e}")

    readwise_cfg = config.get("readwise", {})
    if readwise_cfg.get("enabled", False):
        try:
            from packages.core.tools.readwise_tools import make_readwise_tools

            readwise_tools = make_readwise_tools(readwise_cfg)
            if readwise_tools:
                tool_groups["readwise_tools"] = readwise_tools
                print_system(f"[Tools] {len(readwise_tools)} Readwise tools loaded.")
        except Exception as e:
            print_system(f"[Tools] Readwise tools failed: {e}")

    if vault_config is not None:
        patterns_dir = settings.obsidian.writing.patterns.target_dir
        if patterns_dir:
            try:
                from packages.core.card_renderer import ImageGenerationConfig
                from packages.core.tools.card_generator_tools import make_card_generator_tools

                card_cfg = config.get("pattern_cards", {})
                card_output = jarvis_dir / card_cfg.get("output_dir", "data/pattern-cards")
                img_config = ImageGenerationConfig.from_dict(card_cfg)
                card_gen_tools = make_card_generator_tools(
                    vault_config,
                    patterns_dir,
                    card_output,
                    image_config=img_config,
                )
                tool_groups["card_generator"] = card_gen_tools
                img_status = "enabled" if img_config.enabled else "prompts only"
                print_system(f"[Cards] {len(card_gen_tools)} card generator tools loaded (images: {img_status}).")
            except Exception as e:
                print_system(f"[Cards] Startup failed — card generator disabled. ({e})")

    mcp_manager = None
    from packages.integrations.mcp.config import parse_mcp_config

    try:
        mcp_configs = parse_mcp_config(config)
        if mcp_configs:
            from packages.integrations.mcp import MCPManager

            mcp_manager = MCPManager()
            mcp_tool_groups = mcp_manager.start(mcp_configs)
            tool_groups.update(mcp_tool_groups)
            total = sum(len(v) for v in mcp_tool_groups.values())
            print_system(f"[MCP] {total} tool(s) from {len(mcp_tool_groups)} server(s).")
    except Exception as e:
        print_system(f"[MCP] Startup failed: {e}")

    requested_agent = getattr(args, "agent", None)
    if requested_agent:
        if requested_agent not in agent_registry:
            available = ", ".join(sorted(agent_registry)) or "(none)"
            raise RuntimeError(f"Unknown agent '{requested_agent}'. Available: {available}")
        meta = agent_registry[requested_agent]
        all_agent_tools = assemble_agent_tools(meta, shared_tools, tool_groups)
        all_agent_tools.extend(make_agent_vault_tools(meta, settings, vault_config, confirmation_handler))
        active_agent = instantiate_agent(
            meta,
            client,
            model_id,
            all_agent_tools,
            skill_registry=skill_registry,
            card_search_tool=card_search_tool,
        )
        agent_name = meta.name
    else:
        available_agents = [{"name": meta.name, "description": meta.description} for meta in agent_registry.values()]
        jarvis_tools = (
            list(shared_tools)
            + tool_groups.get("web_tools", [])
            + tool_groups.get("things3_tools", [])
            + tool_groups.get("readwise_tools", [])
        )
        active_agent = JarvisAgent(
            llm_client=client,
            context_dir=context_dir,
            model=model_id,
            extra_tools=jarvis_tools or None,
            available_agents=available_agents or None,
        )
        agent_name = "JARVIS"

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
                context_files.append(
                    {
                        "path": str(f.relative_to(jarvis_dir)),
                        "hash": f"sha256:{hash_content(content)}",
                        "size_bytes": size_bytes,
                        "approx_tokens": size_bytes // 4,
                    }
                )
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

    context_snapshot = {"files_loaded": context_files, "metadata": {}}

    environment = {
        "client": client_label,
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
        conversation_id=conversation_id,
    )
    metrics_tracker = MetricsTracker()

    pricing = get_model_pricing(model_id)

    stream_handler = StreamHandler(
        client,
        metrics_tracker,
        pricing,
        model_id,
        on_tool_call=on_tool_call,
        max_tokens=settings.models.default_max_tokens,
        streaming=settings.models.streaming,
    )

    return SessionComponents(
        config=config,
        settings=settings,
        args=args,
        jarvis_dir=jarvis_dir,
        context_dir=context_dir,
        conversations_dir=conversations_dir,
        model_id=model_id,
        provider=resolved.provider,
        api_keys=api_keys,
        client=client,
        pricing=pricing,
        metrics_tracker=metrics_tracker,
        stream_handler=stream_handler,
        logger=logger,
        conversation_id=conversation_id,
        system_prompt=system_prompt,
        context_metadata=context_metadata,
        agent_registry=agent_registry,
        skill_registry=skill_registry,
        shared_tools=shared_tools,
        tool_groups=tool_groups,
        card_search_tool=card_search_tool,
        vault_config=vault_config,
        fs_guard=fs_guard,
        active_agent=active_agent,
        agent_name=agent_name,
        mcp_manager=mcp_manager,
        client_label=client_label,
    )
