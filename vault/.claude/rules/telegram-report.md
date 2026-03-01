---
type: note
last_accessed: 2026-01-31
relevance: 0.59
tier: cold
paths: "**/REPORT*.md"
---

# Telegram Report Formatting

Rules for generating HTML reports for Telegram.

## CRITICAL: Output Format

**Return RAW HTML only. No markdown wrappers.**

WRONG:
```html
<b>Title</b>
```

CORRECT:
<b>Title</b>

The output goes directly to Telegram `parse_mode=HTML`. Any markdown syntax will break parsing.

## Allowed Tags

- `<b>` or `<strong>` — bold (section headers)
- `<i>` or `<em>` — italic (metadata, clarifications)
- `<code>` — inline code (commands, paths)
- `<pre>` — code blocks (rarely needed)
- `<s>`, `<strike>`, `<del>` — strikethrough
- `<u>` — underline
- `<a href="url">text</a>` — links

## FORBIDDEN

- Markdown syntax: `**`, `##`, `-`, `*`, backticks
- Markdown code blocks: triple backticks
- Tables (not supported by Telegram)
- Unsupported tags: `<div>`, `<span>`, `<br>`, `<p>`, `<table>`
- Unescaped `<` and `>` in text (use `&lt;` `&gt;`)
- Nested same tags: `<b><b>text</b></b>`

## Report Template

📊 <b>Обработка за {DATE}</b>

<b>🎯 Текущий фокус:</b>
{ONE_BIG_THING from goals/3-weekly.md}

<b>📓 Сохранено мыслей:</b> {N}
• {emoji} {title} → {category}/

<b>✅ Создано задач:</b> {M}
• {task_name} <i>({priority}, {due_date})</i>

<b>📅 Загрузка на неделю:</b>
Пн: {n} | Вт: {n} | Ср: {n} | Чт: {n} | Пт: {n} | Сб: {n} | Вс: {n}

<b>⚠️ Требует внимания:</b>
• {count} просроченных задач
• Цель "{goal}" без активности {days} дней

<b>🔗 Новые связи:</b>
• [[Note A]] ↔ [[Note B]]

<b>⚡ Топ-3 приоритета на завтра:</b>
1. {task} <i>({goal link if exists})</i>
2. {task}
3. {task}

<b>📈 Прогресс по целям:</b>
• {goal}: {progress}% {status_emoji}

---
<i>Обработано за {time}</i>

## Section Emojis

📊 Title
🎯 Focus
📓 Thoughts saved
✅ Tasks created
📅 Week load
⚠️ Attention needed
🔗 New links
⚡ Priorities
📈 Goal progress

## Category Emojis (Thoughts)

💡 idea
🪞 reflection
🎯 project
📚 learning

## Priority Format

p1 → <i>(p1, urgent)</i>
p2 → <i>(p2, {date})</i>
p3 → <i>(p3, {date})</i>
p4 → <i>(no priority)</i>

## Progress Emojis

🔴 0-25%
🟡 26-50%
🟢 51-75%
✅ 76-100%

## Error Report

❌ <b>Ошибка обработки</b>

<b>Причина:</b> {error_message}

<b>Файл:</b> <code>{file_path}</code>

<i>Попробуйте /process снова или проверьте логи</i>

## Empty Report

📭 <b>Нет записей для обработки</b>

Файл <code>daily/{date}.md</code> пуст или не найден.

<i>Добавьте голосовые сообщения или текст в течение дня</i>

## Validation Rules

Before sending report:
1. All tags are properly closed
2. No raw < or > in text
3. No markdown syntax anywhere
4. No tables
5. Total length under 4096 characters

If over 4096 chars, truncate "Новые связи" section first.
