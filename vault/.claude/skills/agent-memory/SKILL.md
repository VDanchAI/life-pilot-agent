---
type: note
description: >-
last_accessed: 2026-02-26
relevance: 0.98
tier: active
name: agent-memory
Use when: (1) setting up memory for a new agent, (2) diagnosing memory bloat or context
Triggers: "memory management", "organize vault", "memory decay", "forgetting curve",
---

# Agent Memory Management

Memory system with automatic decay, tiered search, and creative recall.
Works with any directory of markdown files.

## Quick Start

### 1. Scan existing files
```bash
python3 scripts/memory-engine.py scan <directory>
```
Reports: file count, YAML coverage, size, recommendations.

### 2. Bootstrap YAML frontmatter
```bash
python3 scripts/memory-engine.py init <directory> [--dry-run]
```
Adds `relevance`, `last_accessed`, `tier` to files missing frontmatter.
Infers `type` from directory path. Infers dates from YAML fields, git log, or file mtime.

### 3. Run decay
```bash
python3 scripts/memory-engine.py decay <directory> [--dry-run]
```
Updates all cards: recalculates relevance scores and reassigns tiers.
Schedule daily via cron for automatic forgetting.

### 4. Touch on read
```bash
python3 scripts/memory-engine.py touch <filepath>
```
Resets card to active (relevance=1.0). Call this when reading a card to answer a question.

### 5. Creative recall
```bash
python3 scripts/memory-engine.py creative <N> <directory>
```
Random sample from cold/archive tiers. Read these cards and look for unexpected connections.

### 6. Health check
```bash
python3 scripts/memory-engine.py stats <directory>
```
Shows tier distribution, context budget, stale card count.

## Core Concepts

### Three-Layer Architecture

| Layer | What | Size Target | Loaded |
|-------|------|-------------|--------|
| Hot context | State file (volatile focus, blockers) | <4KB | Every turn |
| Searchable vault | Cards with YAML, one per entity | Unlimited | On demand |
| Archive | Old logs, completed work | Unlimited | Deep/creative only |

**Rule:** Each fact lives in ONE place. If it's in a card, don't also put it in the state file.
See [references/architecture.md](references/architecture.md) for full design rationale.

### Forgetting Curve

Cards have `relevance: 0.0-1.0` that decays linearly over time:
- Day 0: 1.0 (just accessed)
- Day 7: 0.90 → tier: active
- Day 21: 0.69 → tier: warm  
- Day 33: 0.50 → tier: cold
- Day 60+: 0.10 (floor) → tier: archive

`core` tier is manual-only — for identity, security, pricing. Never auto-demoted.

### Tier-Aware Search

| Mode | Tiers searched | When |
|------|---------------|------|
| heartbeat | core + active | Quick checks, monitoring |
| normal | active + warm | Most questions |
| deep | all tiers | Strategy, OSINT, complex analysis |
| creative | random cold+archive | Brainstorming, ideation |

See [references/search-protocols.md](references/search-protocols.md) for detailed protocols.

### YAML Frontmatter

Minimum required fields (managed by engine):
```yaml
---
relevance: 0.85
last_accessed: 2026-02-25
tier: active
---
```

See [references/yaml-schema.md](references/yaml-schema.md) for full schema with domain-specific fields.

## Daily Files (Episodic Memory)

Daily files (`memory/YYYY-MM-DD.md`) are the agent's episodic memory — what happened each day.
They follow the same decay system as vault cards. **Never delete them.**

### Lifecycle

```
Day 0:   Created (end of day cron or manual)     → tier: active, relevance: 1.0
Day 1-7: Auto-loaded at session start (today+yesterday) → tier: active
Day 8-21:  Searchable but not auto-loaded          → tier: warm
Day 22-60: Deep search only                        → tier: cold
Day 60+:   Creative mode or explicit recall         → tier: archive
```

### YAML Frontmatter for Daily Files

Add to each daily file (engine handles this via `init` or `decay`):
```yaml
---
type: daily
date: 2026-02-18
relevance: 0.76
last_accessed: 2026-02-18
tier: warm
---
```

### Session Loading Protocol

At session start, load only active-tier daily files:
```
1. Read today's daily file (if exists)
2. Read yesterday's daily file (if exists)
3. Stop. Don't load older files.
```

For questions about the past ("what happened last week?"), search warm/cold tier dailies on demand.

### Why Never Delete

1. **Disk cost ≈ zero.** 30 daily files ≈ 300KB. Irrelevant savings.
2. **Context is lost forever.** A knowledge graph captures entities but not reasoning, tone, or "why."
3. **Semantic search works on old files.** A query about "Red Bull tender" finds the relevant daily file regardless of age.
4. **Creative mode surfaces old context.** Forgotten daily entries become unexpected inspiration.
5. **Re-reading from source (Telegram, email) is expensive.** 100+ messages per day × API calls × LLM summarization > keeping a 10KB file.

### Compression (Optional)

If daily files grow large (>20KB), compress old ones instead of deleting:
1. Extract key decisions, contacts, and outcomes into vault cards
2. Trim the daily file to a 20-line summary
3. Keep the summary with its YAML frontmatter intact

This preserves searchability while reducing storage. But even without compression, a year of daily files is ~4MB — negligible.

## Configuration

Generate default config:
```bash
python3 scripts/memory-engine.py config <directory>
```

Creates `.memory-config.json`:
```json
{
  "tiers": {"active": 7, "warm": 21, "cold": 60},
  "decay_rate": 0.015,
  "relevance_floor": 0.1,
  "skip_patterns": ["_index.md"],
  "type_inference": {"crm/": "crm", "leads/": "lead"},
  "use_git_dates": true
}
```

Adjust tier thresholds and decay rate to match your domain's natural rhythm.
Fast-moving domains (sales): tighter thresholds (active=3, warm=10, cold=30).
Slow domains (research): wider thresholds (active=14, warm=45, cold=120).

## Cron Integration

Add decay to daily maintenance (OpenClaw example):
```json
{
  "name": "memory-decay",
  "schedule": {"kind": "cron", "expr": "0 22 * * *", "tz": "UTC"},
  "payload": {"kind": "agentTurn", "message": "Run: python3 scripts/memory-engine.py decay vault/crm/"}
}
```

## Anti-Patterns

| Don't | Do Instead |
|-------|------------|
| Load all contacts into state file | Keep them in vault cards, search on demand |
| Create "knowledge graph" that duplicates vault | Vault IS the graph. Use index files for navigation |
| Store same fact in 3 files | One card per entity, reference via links |
| Delete old daily files to "save space" | Keep all dailies, let tier decay handle visibility |
| Auto-load all daily files at session start | Load only today + yesterday; search older on demand |
| Search all 500 cards for every question | Check index first, filter by tier, then search |
| Touch every card during bulk operations | Only touch on meaningful read/update |
| Build elaborate review systems | Let decay handle it — if you don't use it, it fades |
