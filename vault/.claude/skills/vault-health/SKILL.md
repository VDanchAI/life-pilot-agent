---
type: note
description: "Vault health monitoring, MOC generation, link repair, and system evolution. Use this skill when checking vault quality metrics, regenerating MOC indexes, fixing broken links, finding backlinks, or triggering weekly system reflections. Also use it when the user mentions health score, link density, orphans, dead-ends, or description coverage."
last_accessed: 2026-02-26
relevance: 0.98
tier: active
name: vault-health
depends_on: [graph-builder]
---

# Vault Health

Monitoring and improving knowledge graph health. Built on patterns from [arscontexta](https://github.com/agenticnotetaking/arscontexta) — derivation engine for Claude Code.

## Origin

Skill based on arscontexta analysis (Heinrich's derivation engine, 249 research claims).

Key adopted patterns:
- **Health scoring** — composite metric for quantitative vault assessment
- **Explicit wikilinks in MOC** — instead of dataview (invisible to agents)
- **Operational learning loop** — observations → patterns → improvements
- **Typed relationships** — links with context phrases, not bare `related:[]`
- **Description as retrieval filter** — progressive disclosure for agents

---

## Quick Start

```bash
# Full diagnostics (health score, orphans, broken links, dead-ends)
uv run vault/.claude/skills/graph-builder/scripts/analyze.py

# Regenerate MOC with explicit wikilinks
uv run vault/.claude/skills/vault-health/scripts/generate_moc.py

# Find who links to a file
bash vault/.claude/skills/vault-health/scripts/backlinks.sh "business/crm/acme-corp"

# Find and fix broken links (dry run)
uv run vault/.claude/skills/vault-health/scripts/fix_links.py

# Apply fixes
uv run vault/.claude/skills/vault-health/scripts/fix_links.py --apply
```

---

## Health Score

Composite metric in analyze.py. Formula:

```
health_score = 100
    - (orphan_ratio × 30)         # orphans = knowledge loss
    - (broken_ratio × 30)         # broken links = fragmentation
    - max(0, (3 - avg_links) × 15)  # target: 3+ links/file
    - ((1 - desc_ratio) × 10)     # description coverage
```

### Metrics and targets

| Metric | Target | How to improve |
|--------|--------|----------------|
| Health Score | >80 | All other metrics |
| Avg links/file | >3.0 | generate_moc.py, typed relationships |
| Broken links | <50 | fix_links.py, manual review |
| Orphans | <30 | graph-builder orphan resolution |
| Dead-ends | <100 | Add backlinks to CRM |
| Desc coverage | >50% | Add description to frontmatter |

### Trend tracking

History stored in `.graph/health-history.json` (up to 90 entries). Each analyze.py run adds a data point.

```bash
# View trend
cat vault/.graph/health-history.json | python3 -c "
import json, sys
data = json.load(sys.stdin)
for d in data[-10:]:
    print(f\"{d['date']}: {d['health_score']}/100 | links: {d['total_links']} | broken: {d['broken_links']}\")
"
```

---

## MOC Generation

`generate_moc.py` creates Maps of Content with **explicit wikilinks and context phrases** (arscontexta pattern). Dataview queries preserved at end of files.

### What it generates

**MOC-business.md:**
- Active Deals (with deadline and deal value)
- High Priority clients
- Grouping by industry (FMCG, Banks, Retail, ...)
- Within industry: Active first, then Prospect

**MOC-projects.md:**
- Hot/Active leads
- Clients
- Projects, Resources

### Wikilink format

```markdown
- [[business/crm/acme-corp\|Acme Corp]] — Active, p1, Project $XXK, deadline YYYY-MM-DD
```

Each link contains: status, priority, deal info, region, deadline — agent sees context without opening file.

### When to run

- After adding new CRM files
- After updating status/deal_status in CRM
- Recommended: weekly or when changes in `business/crm/` / `projects/`

---

## Link Repair

### fix_links.py

Finds broken links and suggests fixes via fuzzy stem matching.

**Strategies:**
1. **Trailing backslash** — Obsidian table escaping artifact (`\|`)
2. **Wrong prefix** — `crm/company` → `business/crm/company`
3. **Stem match** — `old-name` → finds `new-name.md` by stem match

**Exclusions:** backup directories, attachment embeds, directory links.

```bash
# Dry run — shows suggestions
uv run vault/.claude/skills/vault-health/scripts/fix_links.py

# Apply
uv run vault/.claude/skills/vault-health/scripts/fix_links.py --apply
```

### backlinks.sh

Find files linking TO specified file (incoming links).

```bash
# Who links to Acme Corp?
bash vault/.claude/skills/vault-health/scripts/backlinks.sh "business/crm/acme-corp"

# Who links to MEMORY.md?
bash vault/.claude/skills/vault-health/scripts/backlinks.sh "MEMORY"
```

### Dead-end detection

Dead-end = file with outgoing links but no incoming (knows about others, but nobody knows about it). Detected by analyze.py, output in report.md.

---

## Weekly Reflection

Operational learning loop: observations → patterns → proposals.

### Trigger

- Every Sunday
- When observations in `.session/handoff.md` reach ≥10

### Process

1. Read `.session/handoff.md` → collect `## Observations`
2. Read `.graph/health-history.json` → week's trend
3. Group observations by type (friction/pattern/idea)
4. Find recurring patterns (>2 occurrences)
5. Propose concrete improvements (file + change)
6. Write reflection file
7. Clear processed observations from handoff.md

### Output

```
thoughts/reflections/YYYY-WNN-system-reflection.md
```

Detailed template: `.claude/rules/weekly-reflection.md`

### Observation format

In `.session/handoff.md`, section `## Observations`:

```markdown
- [friction] 2026-02-19: mcp-cli timeout 3x — retry saved, -60 sec
- [pattern] 2026-02-19: 65 "broken links" were attachment embeds
- [idea] 2026-02-19: generate_moc.py in process.sh chain
```

Types: `friction` (something broke/slow), `pattern` (recurring), `idea` (improvement).

---

## Typed Relationships

When adding links between files, use context phrases (arscontexta pattern):

| Type | When | Example |
|------|------|---------|
| **extends** | Develops an idea | `[[note]] — extends: deepens analysis` |
| **context** | Background info | `[[note]] — context: meeting where discussed` |
| **supports** | Supports a goal | `[[goal]] — supports: annual target` |
| **contradicts** | Contradicts | `[[note]] — contradicts: different approach` |
| **enables** | Makes possible | `[[tool]] — enables: workflow` |
| **requires** | Dependency | `[[resource]] — requires: API key` |

---

## Description Guidelines

Description = retrieval filter, NOT summary. Adds information BEYOND title.

```yaml
# WRONG (repeats title):
# title: "Acme Corp"
description: "Company Acme Corp"

# RIGHT (adds retrieval info):
# title: "Acme Corp"
description: "Key client in [industry], active deal $XXK, [project] in progress"
```

Target: ~150 chars. Scope, mechanism, implication — not retelling.

---

## Automation in process.sh

analyze.py runs **automatically** every day through `scripts/process.sh`:
- If daily is empty → graph-only rebuild
- After full processing → final rebuild

generate_moc.py, fix_links.py, backlinks.sh — manual run as needed.

---

## References

- `references/arscontexta-patterns.md` — patterns from arscontexta, adapted for agent-second-brain
- `.claude/rules/weekly-reflection.md` — template for weekly reflections

## Relevant Skills

- [[vault/.claude/skills/graph-builder/SKILL|graph-builder]] — core graph analysis (analyze.py)
- [[vault/.claude/skills/dbrain-processor/SKILL|dbrain-processor]] — daily processing pipeline
