---
type: note
last_accessed: 2026-02-26
relevance: 0.98
tier: active
---
# Frontmatter Schema

YAML frontmatter schema for vault files.

## Basic schema (all files)

```yaml
---
type: string       # Record type (see below)
domain: string     # business | projects | personal
description: string # Retrieval filter ~150 chars (NOT summary -- adds scope/mechanism/implication beyond title)
tags: [string]     # Tags for categorization
related: [string]  # Wiki-links to related files
created: date      # Creation date (YYYY-MM-DD)
updated: date      # Update date
---
```

### Description field

**NOT a summary** -- description adds information BEYOND the title, does not repeat it.
This is a **retrieval filter**: the agent reads title + description and decides whether to open the file.

**Rules:**
- ~150 characters max
- Adds scope, mechanism or implication
- Does NOT repeat the title
- Specifics > abstractions

**Examples:**

```yaml
# CRM (title = acme-corp.md):
description: "Major FMCG client, Project $XXK active deal, promo codes in progress"

# Thought (title = 2026-02-05-hormonal-agent-algorithm.md):
description: "4 hormones as sine waves + noise -> mood -> intentions. Gives agent free will."

# Learning (title = 2026-01-30-session-persistence.md):
description: "JSONL append-only files for interaction history. Pattern from Clawdbot."
```

---

## Record types

### Personal domain

| type | Folder | Description |
|------|--------|-------------|
| learning | thoughts/learnings/ | Knowledge, discoveries, TIL |
| idea | thoughts/ideas/ | Ideas, concepts |
| reflection | thoughts/reflections/ | Reflections, conclusions |
| project | thoughts/projects/ | Project notes |

### Business domain

| type | Folder | Description |
|------|--------|-------------|
| crm | business/crm/ | Client + deals |
| network | business/network/ | Org structure |
| event | business/events/ | Events |

### Projects domain

| type | Folder | Description |
|------|--------|-------------|
| client | projects/clients/ | Project client |
| lead | projects/leads/ | Lead |

---

## CRM Schema (business/crm/)

```yaml
---
type: crm
domain: business
description: string          # Retrieval filter: key client context (~150 chars)
industry: FMCG | Electronics | Banks | Pharma | Retail | Auto | IT | Telecom
priority: High | Mid | Low
status: Active | Prospect | Dormant | Declined
region: UZ | KZ | BY | Global
owner: [Your Name] | [Team Member]
responsible: string          # Responsible person on client side

# Active deal (if any)
deal_status: In progress | Tender | Proposal sent | Meeting held
deal_deadline: YYYY-MM-DD

# Links
related:
  - "[[thoughts/learnings/...]]"

updated: YYYY-MM-DD
---
```

**Example:**

```yaml
---
type: crm
domain: business
industry: FMCG
priority: High
status: Active
region: UZ, KZ
owner: [Your Name]
deal_status: In progress
deal_deadline: 2026-02-09
updated: 2026-01-29
---
```

---

## Learning Schema (thoughts/learnings/)

```yaml
---
type: learning
domain: personal
description: string          # Retrieval filter: key insight (~150 chars)
tags: [ai, marketing, automation, ...]
source: daily/YYYY-MM-DD.md | URL | @mention
related:
  - "[[business/crm/acme-corp]]"
  - "[[projects/leads/lead-a]]"
created: YYYY-MM-DD
---
```

**Example:**

```yaml
---
type: learning
domain: personal
tags: [ai, marketing, panel]
source: event
related:
  - "[[projects/leads/lead-a]]"
  - "[[business/network/partner-a]]"
created: 2026-01-27
---
```

---

## Projects Client Schema

```yaml
---
type: client
domain: projects
description: string          # Retrieval filter: client type and status (~150 chars)
company: string
industry: Auto | IT | Retail | Pharma | Education | Finance
region: BY | UZ | KZ | RU
status: APPROVED | Proposal sent | In progress | Completed
responsible: string
budget: string              # Optional
related:
  - "[[thoughts/learnings/...]]"
updated: YYYY-MM-DD
---
```

---

## Projects Lead Schema

```yaml
---
type: lead
domain: projects
description: string          # Retrieval filter: who and why (~150 chars)
company: string
industry: Education | IT | ...
region: UZ | ...
status: Hot | Warm | Cold | Contacted | Proposal sent
source: string              # Where lead came from
responsible: string
next_action: string         # Next step
related: []
updated: YYYY-MM-DD
---
```

---

## Related format

**Correct:**

```yaml
related:
  - "[[business/crm/acme-corp]]"
  - "[[thoughts/learnings/agent-memory-system]]"
```

**Incorrect:**

```yaml
# Without quotes (may break YAML)
related:
  - [[business/crm/acme-corp]]

# With alias in frontmatter (redundant)
related:
  - "[[business/crm/acme-corp|Acme Corp]]"
```

---

## Adding links by agent

When updating frontmatter:

1. **Read** existing frontmatter
2. **Get** current `related: []`
3. **Add** new links (no duplicates)
4. **Verify** that files exist
5. **Write** updated frontmatter

```python
def add_related(content: str, new_links: list[str]) -> str:
    """Add links to frontmatter."""

    # Parse frontmatter
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return content

    fm = yaml.safe_load(match.group(1)) or {}

    # Get current links
    existing = set(fm.get("related", []))

    # Add new (format with quotes)
    for link in new_links:
        formatted = f'[[{link}]]' if not link.startswith('[[') else link
        existing.add(formatted)

    # Update
    fm["related"] = sorted(list(existing))

    # Write
    new_fm = yaml.dump(fm, allow_unicode=True, default_flow_style=False)
    return f"---\n{new_fm}---\n" + content[match.end():]
```
