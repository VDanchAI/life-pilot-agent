# Frontmatter Schema

Standard YAML frontmatter for vault notes.

## Basic Schema

```yaml
---
title: Note Title
created: YYYY-MM-DD
modified: YYYY-MM-DD
tags: [tag1, tag2]
aliases: [alternate-name]
---
```

## Extended Schema

```yaml
---
title: Note Title
created: YYYY-MM-DD
modified: YYYY-MM-DD
tags: [tag1, tag2]
aliases: [alternate-name]
type: idea | reflection | learning | project | moc | daily
domain: thoughts | goals | projects | daily
status: draft | active | archived
links:
  - "[[Related Note]]"
  - "[[Another Note]]"
---
```

## Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| title | string | Yes | Display title for the note |
| created | date | Yes | Creation date (YYYY-MM-DD) |
| modified | date | No | Last modification date |
| tags | array | No | Categorization tags |
| aliases | array | No | Alternative names for linking |
| type | enum | No | Note type classification |
| domain | enum | No | Primary domain |
| status | enum | No | Note lifecycle status |
| links | array | No | Explicit related notes |

## Type Values

- `idea` — Creative concept or innovation
- `reflection` — Personal insight or lesson
- `learning` — Knowledge from external source
- `project` — Project documentation
- `moc` — Map of Content index
- `daily` — Daily journal entry

## Status Values

- `draft` — Work in progress
- `active` — Current and maintained
- `archived` — No longer active, kept for reference

## Usage in Graph Analysis

The graph analyzer uses frontmatter to:

1. **Classify notes** by type and domain
2. **Detect orphans** based on links field
3. **Suggest connections** using tags and aliases
4. **Track freshness** via modified date

## Example Notes

### Thought Note
```yaml
---
title: API Design Principles
created: 2025-01-15
tags: [development, architecture]
type: learning
domain: thoughts
---
```

### MOC Note
```yaml
---
title: Development Index
created: 2024-06-01
modified: 2025-01-20
tags: [index, development]
type: moc
aliases: [Dev MOC, Development Map]
---
```

### Project Note
```yaml
---
title: Project Alpha
created: 2025-01-01
tags: [project, active]
type: project
status: active
links:
  - "[[goals/3-weekly]]"
  - "[[MOC/Projects]]"
---
```
