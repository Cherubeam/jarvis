# Prompt Engineering

> Experiments, learnings, and best practices for prompting Jarvis.

---

## Current System Prompt

### Structure

```
{system_prompt_prefix from config.yaml}

## About this person
{contents of profile.md}

## Their preferences
{contents of preferences.md}

## Current focus
{contents of current_focus.md}
```

### Example

```markdown
You are a helpful personal assistant.

## About this person

I am a software engineer learning AI engineering.
I work primarily with Python and enjoy building tools.

## Their preferences

- Be concise and technical
- Provide code examples when relevant
- Ask clarifying questions when ambiguous

## Current focus

Working on:
- Building Jarvis, a personal AI assistant
- Learning about RAG and vector databases
- Exploring agentic AI frameworks
```

---

## Prompt Engineering Principles

### 1. Be Specific

**Bad:**
```
Help me with coding.
```

**Good:**
```
Explain how to implement streaming responses in Python using generators.
Include code examples and common pitfalls.
```

### 2. Provide Context

**Bad:**
```
Fix this bug.
```

**Good:**
```
I'm getting a "StopIteration" error in my streaming response handler.
Here's the relevant code: [code snippet]
The error occurs when iterating over the response generator.
```

### 3. Specify Output Format

**Bad:**
```
Compare these models.
```

**Good:**
```
Compare Claude Sonnet 4.5 and GPT-4o in a table with these columns:
- Cost per 1M tokens
- Strengths
- Best use cases
```

---

## Context Files Best Practices

### profile.md

**Purpose**: Who you are, stable facts.

**Good:**
```markdown
# About Me

## Professional
- Software engineer with 5 years experience
- Specialize in backend systems and APIs
- Learning AI engineering

## Personal
- Prefer practical, hands-on learning
- Value simplicity over complexity
```

**Avoid:**
- Temporary information (put in current_focus.md)
- Daily tasks (too specific)
- Opinions that change frequently

---

### preferences.md

**Purpose**: How the assistant should behave.

**Good:**
```markdown
# Communication Preferences

- Be concise and direct
- Use technical terminology appropriately
- Provide code examples for technical topics
- Ask clarifying questions instead of assuming

# Response Style

- Skip pleasantries, get to the point
- Use markdown formatting for readability
- Include sources when making factual claims
```

**Avoid:**
- Vague preferences ("be helpful")
- Contradictory instructions
- Too many rules (keep it simple)

---

### current_focus.md

**Purpose**: What you're working on right now.

**Good:**
```markdown
# Current Projects

## Jarvis (Primary)
- Building personal AI assistant
- Phase 1: Foundation and metrics
- Current task: Setting up documentation structure

## Learning Goals
- Understanding RAG architectures
- Exploring LiteLLM for provider abstraction
- Studying AI engineering frameworks
```

**Update Frequency**: Weekly or when focus changes.

**Avoid:**
- Daily tasks (too granular)
- Completed projects (archive them)
- Unrelated information

---

## Prompt Experiments

### Experiment Log Template

```markdown
## Experiment: [Name]
**Date**: YYYY-MM-DD
**Hypothesis**: What we think will happen
**Change**: What we modified
**Result**: What actually happened
**Conclusion**: Keep, iterate, or discard

### Example Query
[User query that tests this]

### Response Quality
- Accuracy: X/10
- Relevance: X/10
- Personalization: X/10

### Notes
[Additional observations]
```

---

## Future Experiments (Planned)

### 1. System Prompt Optimization

**Goal**: Reduce token usage without losing quality.

**Current**: ~1,100 tokens
**Target**: <800 tokens

**Approach**:
- Remove redundant instructions
- More concise context descriptions
- Test on golden test suite

---

### 2. Temperature & Sampling

**Goal**: Find optimal settings for different task types.

**Variables**:
- `temperature`: 0.0 (deterministic) to 1.0 (creative)
- `top_p`: Nucleus sampling
- `frequency_penalty`: Reduce repetition

**Tasks to Test**:
- Factual queries (low temperature)
- Creative writing (higher temperature)
- Code generation (very low temperature)

---

### 3. Few-Shot Examples

**Goal**: Improve response format consistency.

**Approach**:
Include 1-3 example Q&A pairs in system prompt for:
- Technical explanations
- Code reviews
- Planning tasks

**Trade-off**: Uses more tokens.

---

### 4. Chain-of-Thought

**Goal**: Improve reasoning on complex tasks.

**Approach**:
Add to system prompt:
```
For complex queries, think step-by-step:
1. Understand the problem
2. Break it into sub-problems
3. Solve each step
4. Synthesize the answer
```

**Expected**: Better quality on reasoning tasks.

---

## Prompt Versioning

### Version Control Strategy

Store prompts in git:
- Context files: `personal-context/context/*.md`
- System prompt prefix: `config.yaml`

Track changes:
```bash
git log --oneline personal-context/context/
```

### Naming Convention

For experiments:
```
experiments/
├── YYYY-MM-DD-experiment-name.md
└── results/
    └── YYYY-MM-DD-experiment-name-results.json
```

---

## Tools & Resources

### Prompt Engineering Guides

- [Anthropic Prompt Engineering](https://docs.anthropic.com/claude/docs/prompt-engineering)
- [OpenAI Best Practices](https://platform.openai.com/docs/guides/prompt-engineering)
- [Prompting Guide](https://www.promptingguide.ai/)

### Evaluation Tools

- **Manual**: Golden test suite (Phase 2)
- **Automated**: LLM-as-judge (Phase 3)
- **Metrics**: BLEU, ROUGE, custom scoring

---

*Last updated: 2026-01-14*
