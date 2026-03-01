---
type: note
description: Analyze and build knowledge graph links in Obsidian vault. Runs a deterministic script for analysis, then the agent adds semantic links to orphan files. Three domains: Personal, Business, Projects.
last_accessed: 2026-02-26
relevance: 0.98
tier: active
name: graph-builder
allowed-tools: Bash(uv run:*), Bash(rg:*), Read, Edit
depends_on: []
---

# Graph Builder

Analyze vault link structure and build meaningful connections between notes.

## Architecture

```
+------------------------------------------+
|  1. SCRIPT analyze.py (deterministic)    |
|     -> vault-graph.json + report.md      |
+-----------------+------------------------+
                  |
                  v
+------------------------------------------+
|  2. AGENT (you)                          |
|     -> orphan analysis                   |
|     -> semantic links                    |
|     -> frontmatter updates               |
|     -> HTML report                       |
+------------------------------------------+
```

## Trigger

- `/graph` -- manual run
- After `dbrain-processor` in chain (optional)
- Weekly: full rebuild

---

## STEP 1: Run the script

```bash
uv run vault/.claude/skills/graph-builder/scripts/analyze.py
```

**Script does:**
1. Traverses all .md files in vault/
2. Parses frontmatter
3. Extracts wiki-links `[[path]]` and `[[path|alias]]`
4. Determines domain (business, projects, personal)
5. Finds orphan files (no links)
6. Finds broken links
7. Generates `vault/.graph/vault-graph.json`
8. Generates `vault/.graph/report.md`

**CRITICAL:** Always run the script first! It provides up-to-date data.

---

## STEP 2: Read script output

Read `vault/.graph/vault-graph.json`:

```json
{
  "stats": {
    "total_files": 331,
    "orphan_files": 147,
    "broken_links": 167
  },
  "orphans": ["path/to/file.md", ...],
  "broken_links": [{"from": "...", "to": "..."}, ...]
}
```

---

## STEP 3: Analyze orphan files

For each orphan file (start with **non-daily** files):

1. **Read the file content**
2. **Find potential links:**
   - Company mentions -> `business/crm/{company}.md`
   - People mentions -> search in contacts/
   - Tags -> files with matching tags
   - Dates -> daily/ for that day
   - Topics -> thoughts/learnings/, MOC/

3. **Suggest links** -- add to frontmatter `related: []`

### Link search patterns

| Mention | Link |
|---------|------|
| Acme Corp, Acme | `[[business/crm/acme-corp]]` |
| PhoneBrand | `[[business/crm/phone-brand]]` |
| TechCo | `[[business/crm/tech-co]]` |
| SchoolCo | `[[projects/leads/school-co]]` |
| AutoDealer | `[[projects/leads/auto-dealer]]` |
| AI, Claude, GPT | thoughts/learnings/ with AI topic |

---

## STEP 4: Update frontmatter

**Link format in frontmatter:**

```yaml
---
type: learning
domain: personal
tags: [ai, marketing]
related:
  - "[[business/crm/acme-corp]]"
  - "[[projects/leads/school-co]]"
  - "[[thoughts/learnings/agent-memory-system]]"
---
```

**Rules:**
- Only add real links (file exists)
- Do not duplicate existing links
- Maximum 5-7 links per file
- Use `"[[path]]"` format with quotes

---

## STEP 5: Update MOC (if needed)

Check MOC files:
- `MOC/MOC-learnings.md` -- add new learnings
- `MOC/MOC-projects.md` -- create if missing

---

## STEP 6: HTML report

**Return RAW HTML for Telegram:**

<b>Graph Builder Report</b>

<b>Analyzed:</b>
- Files: {total_files}
- Links: {total_links}
- Orphans: {orphan_files}
- Broken links: {broken_links}

<b>Business:</b> {files} files, {links} links
<b>Projects:</b> {files} files, {links} links
<b>Personal:</b> {files} files, {links} links

<b>Links added:</b> {count}
- {file1} -> {file2}
- {file3} -> {file4}

<b>Needs attention:</b>
- {broken_count} broken links
- {orphan_count} orphan files

<i>Details: vault/.graph/report.md</i>

---

## Three domains

### Personal
- `thoughts/` -- learnings, ideas, reflections
- `goals/` -- yearly, monthly, weekly
- `daily/` -- raw entries
- **Hub:** `MEMORY.md`

### Business
- `business/crm/` -- clients + deals (N files)
- `business/network/` -- org structure
- **Hub:** `business/_index.md`

### Projects
- `projects/clients/` -- project clients
- `projects/leads/` -- leads
- **Hub:** `projects/_index.md`

---

## Orphan processing priority

1. **business/crm/** -- business-critical, many orphans
2. **thoughts/learnings/** -- valuable knowledge
3. **projects/** -- active projects
4. **daily/** -- old entries (low priority)

---

## Do not

- Do not change file content (only frontmatter)
- Do not add links to non-existent files
- Do not process files in .obsidian/, attachments/, backup/
- Do not create new files without reason

---

## References

- `references/domains.md` -- domain details
- `references/entities.md` -- entity patterns
- `references/frontmatter.md` -- frontmatter schema

## Relevant Skills

- [[vault/.claude/skills/vault-health/SKILL|vault-health]] -- Health scoring, MOC generation, link repair (depends on this skill)
- [[vault/.claude/skills/dbrain-processor/SKILL|dbrain-processor]] -- Daily entry processing
