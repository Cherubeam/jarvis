// Field lists for the 12 sections that render as plain scalar forms.

import type { SectionKey } from './sections'
import type { FieldSpec } from './ScalarPanel'

export const SCALAR_SECTIONS: Partial<Record<SectionKey, FieldSpec[]>> = {
  models: [
    { path: ['default'], label: 'default' },
    { path: ['default_max_tokens'], label: 'default_max_tokens' },
    { path: ['streaming'], label: 'streaming' },
    { path: ['presets', 'fast'], label: 'presets.fast' },
    { path: ['presets', 'quality'], label: 'presets.quality' },
    { path: ['presets', 'balanced'], label: 'presets.balanced' },
  ],
  paths: [
    { path: ['context_dir'], label: 'context_dir' },
    { path: ['conversations_dir'], label: 'conversations_dir' },
    { path: ['learned_facts'], label: 'learned_facts' },
    { path: ['prompt_history_dir'], label: 'prompt_history_dir' },
  ],
  cli: [
    { path: ['colors'], label: 'colors' },
    { path: ['history_file'], label: 'history_file' },
  ],
  outcomes: [
    { path: ['enabled'], label: 'enabled' },
    { path: ['dir'], label: 'dir' },
  ],
  things3: [
    { path: ['enabled'], label: 'enabled' },
    { path: ['sync_on_startup'], label: 'sync_on_startup' },
    { path: ['cache_ttl_seconds'], label: 'cache_ttl_seconds' },
    { path: ['lists_to_include'], label: 'lists_to_include' },
    { path: ['max_tasks_per_list'], label: 'max_tasks_per_list' },
  ],
  evaluation: [
    { path: ['judge_model'], label: 'judge_model' },
    { path: ['quality_threshold'], label: 'quality_threshold' },
    { path: ['results_dir'], label: 'results_dir' },
    { path: ['max_cost_per_run'], label: 'max_cost_per_run ($)' },
    { path: ['warn_cost_threshold'], label: 'warn_cost_threshold ($)' },
  ],
  rag: [
    { path: ['enabled'], label: 'enabled' },
    { path: ['db_path'], label: 'db_path' },
    { path: ['embedding_model'], label: 'embedding_model' },
    { path: ['index_cards'], label: 'index_cards' },
  ],
  routing: [
    { path: ['enabled'], label: 'enabled' },
    { path: ['simple_threshold'], label: 'simple_threshold (chars)' },
    { path: ['complex_threshold'], label: 'complex_threshold (chars)' },
  ],
  summarization: [
    { path: ['enabled'], label: 'enabled' },
    { path: ['token_threshold'], label: 'token_threshold' },
    { path: ['keep_recent'], label: 'keep_recent' },
  ],
  cortex: [
    { path: ['enabled'], label: 'enabled' },
    { path: ['base_url'], label: 'base_url' },
    { path: ['timeout_seconds'], label: 'timeout_seconds' },
  ],
  readwise: [
    { path: ['enabled'], label: 'enabled' },
    { path: ['cache_ttl_seconds'], label: 'cache_ttl_seconds' },
  ],
  developer: [
    { path: ['enabled'], label: 'enabled' },
    { path: ['scope'], label: 'scope (one per line)' },
    { path: ['allowed_extensions'], label: 'allowed_extensions (one per line)' },
  ],
}

export const SECTION_SUBTITLES: Partial<Record<SectionKey, string>> = {
  models: 'LLM model defaults and named presets.',
  paths: 'Project-relative data paths.',
  cli: 'Interactive CLI display preferences.',
  outcomes: 'Close-the-loop tracking on recommendations JARVIS makes.',
  things3: 'Things 3 task integration.',
  evaluation: 'LLM-as-judge settings for golden conversation evals.',
  rag: 'Conversation recall via ChromaDB + embeddings.',
  routing: 'Intelligent model routing by query complexity.',
  summarization: 'History compression once token threshold exceeds.',
  obsidian: 'Obsidian vault integration — paths, daily notes, writing targets.',
  mcp: 'Model Context Protocol server connections.',
  filesystem: 'Per-path access rules enforced by FilesystemGuard.',
  cortex: 'Shared semantic vault search service.',
  readwise: 'Readwise reading list, highlights, and persona.',
  pattern_cards: 'Pattern card generator output + image generation.',
  developer: 'Self-improvement agent scope and allowed file types.',
}
