---
paths: "thoughts/**/*.md"
---

# Thoughts Format

Rules for notes in `thoughts/` folder and its subfolders.

## Folder Structure

```
thoughts/
├── ideas/       # Creative ideas, concepts
├── reflections/ # Personal reflections, lessons
├── projects/    # Project-related notes
└── learnings/   # Knowledge, discoveries
```

## File Naming

- Format: `YYYY-MM-DD-slug.md`
- Slug: lowercase, hyphens, descriptive
- Example: `2024-12-20-voice-agent-architecture.md`

## Frontmatter (Required)

```yaml
---
date: 2024-12-20
type: idea | reflection | project | learning
tags: [relevant, tags]
source: daily/2024-12-20.md
related: []
---
```

## Content Structure

```markdown
# Title

## Summary
One paragraph summary of the key insight.

## Details
Full content of the thought.

## Action Items
- [ ] Any tasks that emerged
- [ ] Follow-up actions

## Related
- [[Link to related note]]
- [[goals/1-yearly-2025#Section]]
```

## Tags Convention

Use hierarchical tags:

```
#type/idea
#type/learning
#topic/ai
#topic/productivity
#project/d-brain
#status/active
```

## Wiki-Links

When saving a thought:

1. **Search for related notes** in thoughts/
2. **Check MOC indexes** for topic clusters
3. **Link to relevant goals** in goals/
4. **Add backlinks** to source daily note

Example:
```markdown
Extracted from [[daily/2024-12-20]].
Related to [[Voice Agents]] and [[goals/1-yearly-2025#AI Development]].
```

## Category Guidelines

### ideas/
- Novel concepts, inventions
- Business ideas
- Creative solutions
- "What if..." thoughts

### reflections/
- Personal insights
- Lessons learned
- Emotional processing
- Gratitude, wins

### projects/
- Project-specific notes
- Meeting notes
- Status updates
- Decisions made

### learnings/
- New knowledge
- Book/article insights
- Technical discoveries
- "TIL" moments
