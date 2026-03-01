---
type: note
title: Agent Second Brain
last_accessed: 2026-01-31
relevance: 0.59
tier: cold
---
# Agent Second Brain

Voice-first personal assistant for capturing thoughts and managing tasks via Telegram.

## EVERY SESSION BOOTSTRAP

**Before doing anything else, read these files in order:**

1. `vault/MEMORY.md` — curated long-term memory (preferences, decisions, context)
2. `vault/.memory-config.json` — memory decay configuration
3. `vault/daily/YYYY-MM-DD.md` — today's entries
4. `vault/daily/YYYY-MM-DD.md` — yesterday's entries (for continuity)
5. `vault/goals/3-weekly.md` — this week's ONE Big Thing
6. `vault/.session/handoff.md` — previous session context (if exists)

**Don't ask permission, just do it.** This ensures context continuity across sessions.

---

## SESSION END PROTOCOL

**Before ending a significant session, write to today's daily:**

```markdown
## HH:MM [text]
Session summary: [what was discussed/decided/created]
- Key decision: [if any]
- Created: [[link]] [if any files created]
- Next action: [if any]
```

**Also update `vault/MEMORY.md` if:**
- New key decision was made
- User preference discovered
- Important fact learned
- Active context changed significantly

**Update `vault/.session/handoff.md`:**
- Last Session: what was done
- Key Decisions: if any
- In Progress: unfinished work
- Next Steps: what to do next
- Observations: friction signals, patterns, ideas (type: `[friction]`, `[pattern]`, `[idea]`)

---

## Mission

Help user stay aligned with goals, capture valuable insights, and maintain clarity.

## Directory Structure

| Folder | Purpose |
|--------|---------|
| `daily/` | Raw daily entries (YYYY-MM-DD.md) |
| `goals/` | Goal cascade (3y → yearly → monthly → weekly) |
| `thoughts/` | Processed notes by category |
| `MOC/` | Maps of Content indexes |
| `attachments/` | Photos by date |
| `business/` | Business data (CRM, network, events) |
| `projects/` | Side projects (clients, leads) |

## Business Context

**Entry point:** `business/_index.md`

```
business/
├── _index.md       ← Start here (stats, overview)
├── crm/            ← Client records (companies + deals in one file)
├── network/        ← Company structure, partners
└── events/         ← Events, conferences
```

Search: `business/crm/{kebab-case}.md` (e.g. `acme-corp.md`, `client-b.md`)

## Projects Context

**Entry point:** `projects/_index.md`

```
projects/
├── _index.md       ← Start here
├── clients/        ← Project clients
├── leads/          ← Leads
└── projects/       ← Active projects
```

## Current Focus

See [[goals/3-weekly]] for this week's ONE Big Thing.
See [[goals/2-monthly]] for monthly priorities.

## Goals Hierarchy

```
goals/0-vision-3y.md    → 3-year vision by life areas
goals/1-yearly-YYYY.md  → Annual goals + quarterly breakdown
goals/2-monthly.md      → Current month's top 3 priorities
goals/3-weekly.md       → This week's focus + ONE Big Thing
```

## Entry Format

```markdown
## HH:MM [type]
Content
```

Types: `[voice]`, `[text]`, `[forward from: Name]`, `[photo]`

## Processing Workflow

Run daily processing via `/process` command or automatically at 21:00.

### 3-Phase Pipeline:
1. **CAPTURE** — Read daily entries → classify → JSON
2. **EXECUTE** — Create Todoist tasks, save thoughts, update CRM → JSON
3. **REFLECT** — Generate HTML report, update MEMORY, record observations

Each phase = fresh Claude context for better quality.

## Card Template (agent-memory)

**Skill:** `.claude/skills/agent-memory/SKILL.md`

All new vault cards follow the agent-memory template:

```yaml
---
type: crm|lead|contact|project|personal|note
description: >-
  One line — what a searcher will see in results
tags: [tag1, tag2]        # 2-5 tags, lowercase
status: active|draft|pending|done|inactive
industry: FMCG            # for CRM/leads
region: US                 # ISO codes
created: YYYY-MM-DD
updated: YYYY-MM-DD
# Auto fields (don't edit manually):
last_accessed: YYYY-MM-DD
relevance: 0.85
tier: active
---
```

**Rules:**
- `description` — REQUIRED. Write as a search snippet, NOT "contact" or "crm"
- `tags` — REQUIRED. 2-5 tags, lowercase, hyphen-separated
- `status` ≠ `tier`: status = business status, tier = memory (automatic)
- One fact = one place (DRY). References via [[wikilinks]]
- Decay engine: `uv run .claude/skills/agent-memory/scripts/memory-engine.py decay .`

## Skills & References

| Skill | Purpose |
|-------|---------|
| `dbrain-processor` | Main daily processing (3-phase pipeline) |
| `graph-builder` | Vault link analysis and building |
| `vault-health` | Health scoring, MOC generation, link repair |
| `agent-memory` | Card template, decay engine, tiered search |
| `todoist-ai` | Todoist task management via MCP |

- **Processing:** `.claude/skills/dbrain-processor/SKILL.md`
- **Graph Builder:** `.claude/skills/graph-builder/SKILL.md`
- **Vault Health:** `.claude/skills/vault-health/SKILL.md`
- **Agent Memory:** `.claude/skills/agent-memory/SKILL.md`
- **Todoist:** `.claude/skills/todoist-ai/SKILL.md`
- **Rules:** `.claude/rules/` (daily, thoughts, goals, obsidian-markdown, weekly-reflection)
- **Docs:** `.claude/docs/`

## Graph Builder

**Purpose:** Analysis and maintenance of vault link structure.

**Architecture:**
1. `scripts/analyze.py` — deterministic vault traversal
2. `scripts/add_links.py` — batch link addition
3. Agent — semantic links for orphan files

**Usage:**
```bash
# Analyze vault
uv run vault/.claude/skills/graph-builder/scripts/analyze.py

# Result
vault/.graph/vault-graph.json  # JSON graph with stats
vault/.graph/report.md         # Human-readable report
```

**Domains:**
| Domain | Path | Hub |
|--------|------|-----|
| Personal | thoughts/, goals/, daily/ | MEMORY.md |
| Business | business/crm/, business/network/ | business/_index.md |
| Projects | projects/clients/, projects/leads/ | projects/_index.md |

## Available Agents

| Agent | Purpose |
|-------|---------|
| `weekly-digest` | Weekly review with goal progress |
| `goal-aligner` | Check task-goal alignment |
| `note-organizer` | Organize vault, fix links |
| `inbox-processor` | GTD-style inbox processing |

## Path-Specific Rules

See `.claude/rules/` for format requirements:
- `daily-format.md` — daily files format
- `thoughts-format.md` — thought notes format
- `goals-format.md` — goals format
- `telegram-report.md` — HTML report format
- `obsidian-markdown.md` — Obsidian syntax rules
- `weekly-reflection.md` — weekly reflection template

## MCP Servers

- `todoist` — Task management (add, find, complete tasks)
- `google-calendar` — Calendar events and scheduling

## CRITICAL: Tool Usage Policy

**ТЫ ОБЯЗАН ВЫЗЫВАТЬ MCP TOOLS НАПРЯМУЮ.**

Не существует ситуации, когда MCP tools "недоступны". Если ты получил эту инструкцию — у тебя есть доступ к:

- `mcp__todoist__*` — все Todoist операции
- File read/write — все файловые операции

ЗАПРЕЩЁННЫЕ ПАТТЕРНЫ (НИКОГДА не делай это):
- "MCP недоступен в текущем режиме"
- "Не удалось добавить автоматически"
- "Добавь вручную: ..."
- Любые инструкции для ручного выполнения

ПРАВИЛЬНЫЙ ПАТТЕРН:
1. Вызвать mcp__todoist__add-tasks tool
2. Получить результат (успех или ошибка)
3. Включить результат в HTML отчёт

При ошибке — показать ТОЧНУЮ ошибку от tool, не придумывать отговорки.

## MCP Tools Available

**Todoist (mcp__todoist__*):**
- `add-tasks` — создать задачи
- `find-tasks` — найти задачи по тексту
- `find-tasks-by-date` — задачи за период
- `update-tasks` — изменить задачи
- `complete-tasks` — завершить задачи
- `user-info` — информация о пользователе

## Report Format

Reports use Telegram HTML:
- `<b>bold</b>` for headers
- `<i>italic</i>` for metadata
- Only allowed tags: b, i, code, pre, a

## Quick Commands

| Command | Action |
|---------|--------|
| `/process` | Run daily processing |
| `/do` | Execute arbitrary request |
| `/weekly` | Generate weekly digest |
| `/align` | Check goal alignment |
| `/organize` | Organize vault |
| `/graph` | Analyze vault links |
| `/recall` | Search vault memory |
| `/monthly` | Generate monthly review |
| `/grow` | Growth and learning tracker |
| `/health` | Vault health check |
| `/memory` | Memory management |

## /do Command Context

When invoked via /do, Claude receives arbitrary user requests. Common patterns:

**Task Management:**
- "перенеси просроченные задачи на понедельник"
- "покажи задачи на сегодня"
- "добавь задачу: позвонить клиенту"
- "что срочного на этой неделе?"

**Vault Queries:**
- "найди заметки про AI"
- "что я записал сегодня?"
- "покажи итоги недели"

**Combined:**
- "создай задачу из первой записи сегодня"
- "перенеси всё с сегодня на завтра"

## Customization

For personal overrides: create `CLAUDE.local.md`

## Learnings (from experience)

1. **Don't rewrite working code** without reason (KISS, DRY, YAGNI)
2. **Don't add checks** that weren't there — let the agent decide
3. **Don't propose solutions** without studying git log/diff first
4. **Don't break architecture** (process.sh → Claude → skill is correct)
5. **Problems are usually simple** (e.g., sed one-liner for HTML fix)

---

*System Version: 3.0*
