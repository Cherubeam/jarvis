// Field lists for the sections that render as plain scalar forms.

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
    { path: ['auto_router', 'enabled'], label: 'auto_router.enabled' },
    { path: ['auto_router', 'cost_tier'], label: 'auto_router.cost_tier' },
    { path: ['auto_router', 'excluded_models'], label: 'auto_router.excluded_models' },
  ],
  paths: [
    { path: ['context_dir'], label: 'context_dir' },
    { path: ['context_files', 'soul'], label: 'context_files.soul' },
    { path: ['context_files', 'personal'], label: 'context_files.personal' },
    { path: ['context_files', 'professional'], label: 'context_files.professional' },
    { path: ['context_files', 'preferences'], label: 'context_files.preferences' },
    { path: ['context_files', 'focus'], label: 'context_files.focus' },
    { path: ['context_files', 'reading'], label: 'context_files.reading' },
    { path: ['tasks_file'], label: 'tasks_file' },
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
  readwise: [
    { path: ['enabled'], label: 'enabled' },
    { path: ['cache_ttl_seconds'], label: 'cache_ttl_seconds' },
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
  readwise: 'Readwise reading list, highlights, and persona.',
  pattern_cards: 'Pattern card generator output + image generation.',
}
