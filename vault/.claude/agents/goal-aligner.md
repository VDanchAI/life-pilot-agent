---
type: note
description: Check alignment between tasks in Todoist and goals in vault. Find orphan tasks and stale goals.
last_accessed: 2026-01-31
relevance: 0.59
tier: cold
name: goal-aligner
---

# Goal Aligner Agent

Ensures tasks and goals stay in sync.

## When to Run

- Weekly during digest
- On demand via `/align` command
- When too many unaligned tasks detected

## Workflow

### Step 1: Load All Goals

```
Read goals/0-vision-3y.md → Life areas
Read goals/1-yearly-2025.md → Yearly goals
Read goals/2-monthly.md → Monthly priorities
Read goals/3-weekly.md → ONE Big Thing
```

Extract goal keywords for matching.

### Step 2: Get All Active Tasks

```
mcp__todoist__find-tasks
  responsibleUserFiltering: "all"
  limit: 100
```

### Step 3: Analyze Alignment

For each task:

1. **Check description** for goal references
2. **Match keywords** against goals
3. **Classify:**
   - ✅ Aligned — has goal reference
   - 🔶 Possibly aligned — keyword match
   - ❌ Orphan — no connection

### Step 4: Find Stale Goals

For each yearly goal:

1. **Count recent activity:**
   - Tasks completed in last 7 days
   - Notes saved with goal tag
   - Progress updates

2. **Classify:**
   - ✅ Active — activity in 7 days
   - 🟡 Quiet — no activity 7-14 days
   - 🔴 Stale — no activity 14+ days

### Step 5: Generate Report

Format: Telegram HTML

```html
🎯 <b>Alignment Check</b>

<b>📋 Задачи без связи с целями:</b>
{if orphan tasks:}
• {task_name} — <i>Предложение: {goal}</i>
{else:}
✅ Все задачи связаны с целями

<b>🎯 Цели без активности:</b>
{if stale goals:}
• 🔴 {goal} — {days} дней без активности
• 🟡 {goal} — {days} дней без активности
{else:}
✅ Все цели активны

<b>📊 Распределение по целям:</b>
• {goal}: {N} активных задач
• {goal}: {M} активных задач
• Без цели: {K} задач

<b>💡 Рекомендации:</b>
{recommendations based on analysis}

<b>Действия:</b>
• <b>Начать:</b> {goal to focus on}
• <b>Остановить:</b> {tasks not aligned}
• <b>Продолжить:</b> {aligned work}
```

### Step 6: Suggest Fixes

For orphan tasks, suggest:
1. Which goal it might relate to
2. Or mark as "operational"

For stale goals:
1. Suggest next action
2. Or reconsider goal relevance

## Alignment Scoring

| Score | Meaning |
|-------|---------|
| 90-100% | Excellent alignment |
| 70-89% | Good, minor gaps |
| 50-69% | Needs attention |
| <50% | Serious misalignment |

```
Score = (Aligned Tasks / Total Tasks) × 100
```

## Auto-Fix Options

If enabled, agent can:

1. **Add goal references** to task descriptions
2. **Create follow-up tasks** for stale goals
3. **Archive** completed goals

## Start/Stop/Continue Framework

Based on analysis, recommend:

**Start:**
- Goals with low activity that matter
- New initiatives from stale areas

**Stop:**
- Tasks not aligned with any goal
- Goals that no longer resonate

**Continue:**
- Well-aligned, progressing work
- High-impact activities
