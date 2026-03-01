---
type: note
title: Wiki-Links Building
last_accessed: 2026-01-31
relevance: 0.59
tier: cold
---
# Wiki-Links Building

## Purpose

Build connections between notes to create a knowledge graph.

## When Saving a Thought

### Step 1: Search for Related Notes

Search thoughts/ for related content:

```
Grep "keyword1" in thoughts/**/*.md
Grep "keyword2" in thoughts/**/*.md
```

Keywords to search:
- Main topic of the thought
- Key entities (people, projects, technologies)
- Domain terms

### Step 2: Check MOC Indexes

Read relevant MOC files:

```
MOC/
├── MOC-ideas.md
├── MOC-projects.md
├── MOC-learnings.md
└── MOC-reflections.md
```

Find related entries.

### Step 3: Link to Goals

Check if thought relates to goals:

```
Read goals/1-yearly-2025.md
Find matching goal areas
```

### Step 4: Add Links to Note

In the thought file, add:

**In frontmatter:**
```yaml
related:
  - "[[thoughts/ideas/2024-12-15-voice-agents.md]]"
  - "[[goals/1-yearly-2025#AI Development]]"
```

**In content (inline):**
```markdown
This connects to [[Voice Agents Architecture]] we explored earlier.
```

**In Related section:**
```markdown
## Related
- [[Previous related thought]]
- [[Project this belongs to]]
- [[Goal this supports]]
```

### Step 5: Update MOC Index

Add new note to appropriate MOC:

```markdown
# MOC: Ideas

## Recent
- [[thoughts/ideas/2024-12-20-new-idea.md]] — Brief description

## By Topic
### AI & Voice
- [[thoughts/ideas/2024-12-20-new-idea.md]]
- [[thoughts/ideas/2024-12-15-voice-agents.md]]
```

### Step 6: Add Backlinks

In related notes, add backlink to new note if highly relevant.

## Link Format

### Internal Links
```markdown
[[Note Name]]                    # Simple link
[[Note Name|Display Text]]       # With alias
[[folder/Note Name]]             # With path
[[Note Name#Section]]            # To heading
```

### Link to Goals
```markdown
[[goals/1-yearly-2025#Career & Business]]
[[goals/3-weekly]] — ONE Big Thing
```

## Report Section

Track new links created:

```
<b>🔗 Новые связи:</b>
• [[Note A]] ↔ [[Note B]]
• [[New Thought]] → [[Related Project]]
```

## Example Workflow

<!-- Это пример — замените на свои реальные темы -->
New thought: "Новый инструмент X можно использовать для проекта Y"

1. **Search:**
   - Grep "keyword" in thoughts/ → finds related notes
   - Grep "tool" in thoughts/ → no results

2. **Check MOC:**
   - MOC-learnings.md has relevant section

3. **Goals:**
   - 1-yearly-2025.md has matching goal

4. **Create links:**
   ```yaml
   related:
     - "[[thoughts/ideas/related-note.md]]"
     - "[[goals/1-yearly-2025#Your Goal]]"
   ```

5. **Update MOC-learnings.md:**
   ```markdown
   ### Your Category
   - [[thoughts/learnings/2024-12-20-new-learning.md]] — Description
   ```

6. **Report:**
   ```
   <b>🔗 Новые связи:</b>
   • [[New Note]] ↔ [[Related Note]]
   ```

## Orphan Detection

A note is "orphan" if:
- No incoming links from other notes
- No related notes in frontmatter
- Not listed in any MOC

Flag orphans for review:
```
<b>⚠️ Изолированные заметки:</b>
• [[thoughts/ideas/orphan-note.md]]
```
