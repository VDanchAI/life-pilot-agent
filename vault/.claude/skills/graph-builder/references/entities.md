---
type: note
title: Entity Extraction Patterns
last_accessed: 2026-02-26
relevance: 0.98
tier: active
---
# Entity Extraction Patterns

Patterns for finding entities in text.

## Companies (Business CRM)

### Exact matches

| Pattern | File |
|---------|------|
| Client-A, ClientA | `business/crm/client-a.md` |
| Client-B | `business/crm/client-b.md` |
| Client-C | `business/crm/client-c.md` |
| Client-D | `business/crm/client-d.md` |
| Client-E | `business/crm/client-e.md` |
| Client-F | `business/crm/client-f.md` |
| Client-G | `business/crm/client-g.md` |
| Client-H | `business/crm/client-h.md` |
| Client-I | `business/crm/client-i.md` |
| Client-J | `business/crm/client-j.md` |

### Regex for companies

```python
COMPANY_PATTERNS = [
    r'\b(Client-A|ClientA)\b',
    r'\b(Client-B)\b',
    r'\b(Client-C)\b',
    r'\b(Client-D)\b',
    r'\b(Client-E)\b',
    r'\bClient-F\b',
    r'\b(Client-G)\b',
    r'\bClient-H\b',
    r'\bClient-I\b',
]
```

---

## Companies (Projects)

| Pattern | File |
|---------|------|
| Project-Client-A | `projects/clients/project-client-a.md` |
| Project-Client-B | `projects/clients/project-client-b.md` |
| Project-Client-C | `projects/clients/project-client-c.md` |
| Project-Client-D | `projects/clients/project-client-d.md` |
| Lead-A | `projects/leads/lead-a.md` |
| Lead-B | `projects/leads/lead-b.md` |

---

## People

### Name format

```python
# Names in your language
LOCAL_NAME = r'[A-Z][a-z]+\s+[A-Z][a-z]+'
# Examples: [First Name] [Last Name]

# English names
ENGLISH_NAME = r'[A-Z][a-z]+\s+[A-Z][a-z]+'
# Examples: [First Name] [Last Name]
```

### Telegram handles

```python
TELEGRAM_HANDLE = r'@([a-zA-Z0-9_]+)'
# Examples: @username1, @username2, @username3
```

---

## Projects

### Project patterns

```python
PROJECT_PATTERNS = [
    r'project\s+([A-Za-z0-9\s]+)',
    r'(?:NCP|SMM|BTL|ATL)\s+([A-Za-z]+)',
    r'tender\s+([A-Za-z]+)',
]
```

### Active projects

| Mention | Link |
|---------|------|
| Client-A Campaign | `business/crm/client-a.md` |
| Client-B SMM | `business/crm/client-b.md` |
| Client-C Project | `business/crm/client-c.md` |

---

## Topics (for learnings)

| Keywords | Links to |
|----------|----------|
| Claude, AI agent, LLM | `thoughts/learnings/` with AI |
| Second Brain, Obsidian, PKM | Methodology |
| Zettelkasten, graph | Knowledge organization |
| Prompt, prompt engineering | AI techniques |
| Marketing, SMM, content | Business |

---

## Finding file for entity

```python
def find_file_for_entity(entity: str, vault_path: Path) -> Path | None:
    """Find file for an entity."""

    # Normalize: Client-A -> client-a
    slug = entity.lower().replace(" ", "-")

    # Search in CRM
    crm_path = vault_path / "business" / "crm" / f"{slug}.md"
    if crm_path.exists():
        return crm_path

    # Search in Projects
    for subdir in ["clients", "leads"]:
        path = vault_path / "projects" / subdir / f"{slug}.md"
        if path.exists():
            return path

    # Fuzzy search by filename
    for f in vault_path.rglob("*.md"):
        if slug in f.stem.lower():
            return f

    return None
```

---

## Link normalization

```python
def normalize_link(link: str) -> str:
    """Normalize wiki-link."""

    # Remove section: [[file#section]] -> file
    link = link.split("#")[0]

    # Remove alias: [[file|alias]] -> file
    link = link.split("|")[0]

    # Add .md if missing
    if not link.endswith(".md"):
        link = link + ".md"

    return link
```
