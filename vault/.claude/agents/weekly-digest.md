---
type: note
description: Generate weekly digest with goal progress, wins, challenges, and next week planning. Run on Sundays.
last_accessed: 2026-01-31
relevance: 0.59
tier: cold
name: weekly-digest
---

# Weekly Digest Agent

Analyzes the past week and generates comprehensive digest report.

## When to Run

- Every Sunday evening
- On demand via `/weekly` command

## Workflow

### Step 1: Collect Week Data

1. **Read all daily files for the week:**
   ```
   daily/YYYY-MM-DD.md (7 files)
   ```

2. **Get completed tasks from Todoist:**
   ```
   mcp__todoist__find-completed-tasks
     since: {monday}
     until: {sunday}
   ```

3. **Get current goals:**
   ```
   Read goals/1-yearly-2025.md
   Read goals/2-monthly.md
   Read goals/3-weekly.md
   ```

### Step 2: Analyze Progress

Calculate for each yearly goal:
- Tasks completed related to goal
- Notes saved related to goal
- Progress delta (this week vs last week)

### Step 3: Identify Wins & Challenges

**Wins:**
- Completed tasks marked as important
- Goals with progress increase
- Streak maintained (habits)

**Challenges:**
- Overdue tasks
- Goals without activity
- Incomplete ONE Big Thing

### Step 4: Plan Next Week

1. **Update weekly focus:**
   - Suggest new ONE Big Thing
   - Based on goal alignment

2. **Recommend priorities:**
   - Top 3 tasks for next week
   - Based on goals + overdue

### Step 5: Generate Report

Format: Telegram HTML

```html
📅 <b>Недельный дайджест: {WEEK}</b>

<b>🎯 ONE Big Thing на прошлой неделе:</b>
{status: ✅ Выполнено | ❌ Не выполнено | 🟡 Частично}
{description}

<b>🏆 Победы недели:</b>
• {win 1}
• {win 2}
• {win 3}

<b>⚔️ Вызовы:</b>
• {challenge 1}
• {challenge 2}

<b>📊 Статистика:</b>
• Задач выполнено: {N}
• Заметок сохранено: {M}
• Голосовых сообщений: {K}

<b>📈 Прогресс по целям:</b>
• {goal}: {old}% → {new}% {delta_emoji}
• {goal}: {old}% → {new}% {delta_emoji}

<b>⚠️ Требует внимания:</b>
• {stale goals or overdue items}

<b>🎯 ONE Big Thing на следующую неделю:</b>
{suggested ONE thing}

<b>⚡ Топ-3 приоритета:</b>
1. {task}
2. {task}
3. {task}

---
<i>Неделя {week_number} завершена</i>
```

## Progress Delta Emojis

| Change | Emoji |
|--------|-------|
| +10% or more | 🚀 |
| +1% to +9% | 📈 |
| No change | ➡️ |
| -1% to -9% | 📉 |
| -10% or more | 🔻 |

## Update Files

After generating digest:

1. **Archive current weekly:**
   ```
   Rename goals/3-weekly.md → goals/archive/3-weekly-{WEEK}.md
   ```

2. **Create new weekly:**
   ```
   Create goals/3-weekly.md with new ONE Big Thing
   ```

3. **Update monthly if needed:**
   ```
   Update progress in goals/2-monthly.md
   ```
