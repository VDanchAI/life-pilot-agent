---
type: note
last_accessed: 2026-02-26
relevance: 0.98
tier: active
---
# Domains

Three knowledge organization domains in the vault.

## Personal

**Path:** `thoughts/`, `goals/`, `daily/`, `MOC/`, `MEMORY.md`

**Content:**
- Personal thoughts and reflections
- Goals (yearly -> monthly -> weekly)
- Daily entries
- Learnings and ideas

**Hub:** `MEMORY.md` -- central context

**Frontmatter:**
```yaml
domain: personal
type: learning | reflection | idea | project
```

---

## Business

**Path:** `business/`

**Structure:**
```
business/
+-- _index.md       # Entry point, dataview queries
+-- crm/            # Clients + deals
|   +-- acme-corp.md
|   +-- client-b.md
|   +-- ...
+-- network/        # Org structure (Your Holding)
|   +-- founders.md
|   +-- partner-a.md
|   +-- partner-b.md
+-- events/         # Events
```

**Hub:** `business/_index.md`

**Frontmatter (CRM):**
```yaml
domain: business
type: crm
industry: FMCG | Electronics | Banks | Pharma | Retail
priority: High | Mid | Low
status: Active | Prospect | Dormant | Declined
region: UZ | KZ | BY
owner: [Your Name] | [Team Member]
deal_status: In progress | Tender | Proposal sent
deal_deadline: YYYY-MM-DD
```

**Key clients:**
- Client-A (FMCG, High, Active)
- Client-B (Electronics, High, Active)
- Client-C (Electronics, Mid, Active)
- Client-D (FMCG, Mid, Prospect)

---

## Projects

**Path:** `projects/`

**Structure:**
```
projects/
+-- _index.md       # Entry point
+-- clients/        # Project clients
|   +-- client-a.md
|   +-- client-b.md
|   +-- client-c.md
|   +-- client-d.md
+-- leads/          # Leads
    +-- lead-a.md
    +-- lead-b.md
```

**Hub:** `projects/_index.md`

**Frontmatter:**
```yaml
domain: projects
type: client | lead
company: Name
industry: Auto | IT | Retail | Education
status: APPROVED | Proposal sent | Hot | Cold
responsible: Name
```

**Difference from Business:**
- Business = main business (agency, services)
- Projects = personal side projects (consulting, training)

---

## Cross-domain links

| Link | Example |
|------|---------|
| Projects -> Business | `lead-a` -> `partner-b` (partner) |
| Personal -> Business | `learning` -> `acme-corp` (case from practice) |
| Personal -> Projects | `learning` -> `client-a` (insight from training) |
| Business -> Contacts | `acme-corp` -> contacts (contacts) |

---

## Determining domain by path

```python
def get_domain(path: Path) -> str:
    if "business" in path.parts:
        return "business"
    elif "projects" in path.parts:
        return "projects"
    return "personal"
```
