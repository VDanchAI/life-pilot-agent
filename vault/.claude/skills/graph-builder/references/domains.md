# Domain Configuration

Domains define the organizational structure of the vault. Each domain has specific linking rules and priorities.

## Core Domains

### daily/
**Purpose:** Daily journal entries, raw captures
**Format:** `YYYY-MM-DD.md`
**Linking:**
- Outgoing to thoughts/ when content is processed
- Outgoing to projects/ when project mentioned
- Should reference MOCs for categorization

### thoughts/
**Purpose:** Processed and refined ideas
**Subdirectories:**
- `ideas/` — Creative concepts, innovations
- `reflections/` — Personal insights, lessons learned
- `learnings/` — Knowledge captured from reading/experience
- `projects/` — Project-specific notes

**Linking:**
- Incoming from daily/ (source entries)
- Outgoing to MOC/ (categorization)
- Cross-links within thoughts/ (related concepts)

### goals/
**Purpose:** Goal hierarchy and tracking
**Files:**
- `0-vision-3y.md` — Long-term vision
- `1-yearly-YYYY.md` — Annual goals
- `2-monthly.md` — Monthly priorities
- `3-weekly.md` — Weekly focus

**Linking:**
- Incoming from thoughts/ (ideas aligned with goals)
- Incoming from daily/ (progress updates)
- Should be highly connected as navigation hubs

### MOC/
**Purpose:** Maps of Content — index pages
**Linking:**
- Incoming from all domains (everything should have a MOC)
- Outgoing to related MOCs
- Central navigation hubs

### projects/
**Purpose:** Active project documentation
**Linking:**
- Incoming from daily/ (work logs)
- Incoming from thoughts/ (related ideas)
- Outgoing to goals/ (alignment)

## Link Priority Rules

When suggesting links, prioritize:

1. **Orphan → MOC** — Every note should belong to a Map of Content
2. **Daily → Thought** — Processed entries link to their refined notes
3. **Thought → Goal** — Ideas should align with goals
4. **Cross-domain** — Bridge related concepts across domains

## Custom Domains

Add custom domains by creating subdirectories and documenting them here:

```markdown
### your-domain/
**Purpose:** Description
**Linking:** Rules for incoming/outgoing links
```

## Entity Patterns

Common patterns to detect for auto-linking:

- `[[Note Name]]` — Existing wiki-links
- `@mention` — People/contacts (if contacts domain exists)
- `#tag` — Tags that may map to notes
- Project names — Match against projects/ directory
- Dates — Link to daily/ entries
