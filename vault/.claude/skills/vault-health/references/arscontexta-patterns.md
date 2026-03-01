---
type: note
title: Arscontexta Patterns for dbrain
last_accessed: 2026-02-19
relevance: 0.88
tier: warm
---
# Arscontexta Patterns for dbrain

Паттерны из [arscontexta](https://github.com/agenticnotetaking/arscontexta), адаптированные для dbrain vault.

## Source

arscontexta — derivation engine для Claude Code (Heinrich). 249 research claims из cognitive science, network theory, Zettelkasten, agent architecture. Каждое архитектурное решение трейсится к конкретному claim.

## Adopted Patterns

### 1. Health Scoring (quantitative vault assessment)

**Claim:** Системы без метрик деградируют незаметно.

**Реализация:** `analyze.py` → `health_score` → `health-history.json`

Формула: 100 - orphan_penalty(30) - broken_penalty(30) - density_penalty(15) - desc_penalty(10)

### 2. Phase Isolation (fresh context per phase)

**Claim:** `[[LLM attention degrades as context fills]]`

**Реализация:** 3-phase pipeline в process.sh:
- CAPTURE: classify entries → JSON (minimal context)
- EXECUTE: create tasks, save thoughts → JSON (MCP tools)
- REFLECT: generate report, update MEMORY (read-only)

JSON handoff между фазами. Fallback на монолит при ошибке.

### 3. Operational Learning Loop (observations → improvements)

**Claim:** `[[operational-learning-loop]]` (INVARIANT primitive в arscontexta)

**Реализация:**
- `handoff.md` → `## Observations` (friction/pattern/idea)
- dbrain-processor Step 11: автоматический capture
- Weekly reflection: анализ observations → proposals

### 4. Description as Retrieval Filter

**Claim:** `[[descriptions are retrieval filters not summaries]]`

**Реализация:** `description: string` в frontmatter schema. Adds scope/mechanism beyond title. ~150 chars.

### 5. Prose-as-Title (claims, not labels)

**Claim:** `[[note titles should function as APIs enabling sentence transclusion]]`

**Реализация:** Для thoughts/ (не CRM): title = specific claim.
Test: `Since [[title]], ...` reads naturally.

### 6. Explicit Wikilinks in MOC

**Claim:** MOC должен быть видим для agents и graph analysis, не только для Obsidian renderer.

**Реализация:** `generate_moc.py` — 286 explicit wikilinks с context phrases.
Dataview сохранён для Obsidian UX.

### 7. Typed Relationships

**Claim:** `related:[]` без контекста = бесполезно. Нужен тип связи.

**Реализация:** 6 типов: extends, context, supports, contradicts, enables, requires.

### 8. Orient Phase (OODA loop)

**Claim:** Не тратить ресурсы на обработку пустого.

**Реализация:** Pre-flight checks в process.sh: daily exists, size > 50 bytes, handoff exists, graph freshness.

## Consciously NOT Adopted

| Pattern | Why not |
|---------|---------|
| Three-space restructure (self/notes/ops) | dbrain already has functional equivalent |
| Full 6Rs pipeline | 6 Claude calls too expensive for automated daily pipeline |
| PostToolUse hooks (schema validation) | analyze.py on rebuild sufficient for 655 files |
| Per-claim task queue (ops/queue/) | Todoist is our task manager |
| Semantic search (qmd MCP) | Hub navigation + rg sufficient at current scale |
| Personality layer | Not needed for automated processor |
| Derivation manifest | System grown organically, not derived |

## 8 Architectural Dimensions

arscontexta projects each system onto 8 axes. dbrain position:

| Axis | dbrain | Notes |
|------|--------|-------|
| Granularity | Mixed | CRM=entity (coarse), thoughts=atomic |
| Organization | Hierarchical | 3 domains with _index.md hubs |
| Linking | Explicit | Wikilinks |
| Processing | Medium | 3 phases (not 6Rs) |
| Navigation | Medium | MOC + _index hubs |
| Maintenance | Automated | systemd timer |
| Schema | Dense | 3 typed schemas (CRM, Learning, Aimasters) |
| Automation | Convention + script | No hooks, process.sh + analyze.py |

Key constraint: Atomic granularity REQUIRES explicit linking + deep navigation. Our mixed approach (CRM coarse + thoughts atomic) = conscious trade-off, compensated by hub navigation.
