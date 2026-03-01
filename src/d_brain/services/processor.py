"""Claude processing service."""

import json
import logging
import re
from datetime import date
from pathlib import Path
from typing import Any

import pytz

from .calendar_integration import get_calendar_events
from .claude_runner import ClaudeRunner
from .todoist import TodoistService

logger = logging.getLogger(__name__)

_TZ = pytz.timezone("Europe/Kyiv")


class ClaudeProcessor:
    """Service for triggering Claude Code processing."""

    def __init__(self, vault_path: Path, todoist_api_key: str = "") -> None:
        self.vault_path = Path(vault_path)
        self.todoist_api_key = todoist_api_key
        self.runner = ClaudeRunner(vault_path, todoist_api_key)
        self.todoist: TodoistService | None = (
            TodoistService(todoist_api_key) if todoist_api_key else None
        )

    def _html_to_markdown(self, html: str) -> str:
        """Convert Telegram HTML to Obsidian Markdown."""
        text = html
        text = re.sub(r"<b>(.*?)</b>", r"**\1**", text)
        text = re.sub(r"<i>(.*?)</i>", r"*\1*", text)
        text = re.sub(r"<code>(.*?)</code>", r"`\1`", text)
        text = re.sub(r"<s>(.*?)</s>", r"~~\1~~", text)
        text = re.sub(r"</?u>", "", text)
        text = re.sub(r'<a href="([^"]+)">([^<]+)</a>', r"[\2](\1)", text)
        return text

    def _save_weekly_summary(self, report_html: str, week_date: date) -> Path:
        """Save weekly summary to vault/summaries/YYYY-WXX-summary.md."""
        year, week, _ = week_date.isocalendar()
        filename = f"{year}-W{week:02d}-summary.md"
        summary_path = self.vault_path / "summaries" / filename

        content = self._html_to_markdown(report_html)

        frontmatter = f"""---
date: {week_date.isoformat()}
type: weekly-summary
week: {year}-W{week:02d}
---

"""
        summary_path.write_text(frontmatter + content)
        logger.info("Weekly summary saved to %s", summary_path)
        return summary_path

    def _update_weekly_moc(self, summary_path: Path) -> None:
        """Add link to new summary in MOC-weekly.md."""
        moc_path = self.vault_path / "MOC" / "MOC-weekly.md"
        if moc_path.exists():
            content = moc_path.read_text()
            link = f"- [[summaries/{summary_path.name}|{summary_path.stem}]]"
            if summary_path.stem not in content:
                content = content.replace(
                    "## Previous Weeks\n",
                    f"## Previous Weeks\n\n{link}\n",
                )
                moc_path.write_text(content)
                logger.info(
                    "Updated MOC-weekly.md with link to %s",
                    summary_path.stem,
                )

    def categorize_daily(self, day: date | None = None) -> dict[str, Any]:
        """First-pass: categorize entries in the daily file."""
        if day is None:
            day = date.today()

        daily_file = self.vault_path / "daily" / f"{day.isoformat()}.md"

        if not daily_file.exists():
            logger.warning("No daily file for %s", day)
            return {"error": f"No daily file for {day}", "processed_entries": 0}

        content = daily_file.read_text(encoding="utf-8", errors="replace")

        prompt = f"""Сегодня {day}. Проанализируй записи из дневника за сегодня.

ДНЕВНИК:
{content}

ЗАДАЧА: Классифицируй каждую запись на:
- task: явное действие, требующее выполнения ("купить", "позвонить", "сделать X")
- thought: размышление, наблюдение, мысль
- idea: идея, концепция, предложение

НЕОДНОЗНАЧНЫЕ ЗАПИСИ (uncertain) — это записи где непонятно, что имелось в виду:
- "надо бы к стоматологу" — задача или просто мысль?
- "интересная статья про ИИ" без ссылки — идея или мысль?
- "поговорить с Машей" — конкретная задача или неопределённое желание?

Верни ТОЛЬКО валидный JSON (без markdown, без ```json):
{{
  "confident": [
    {{"text": "текст", "category": "task|thought|idea", "action": "действие"}}
  ],
  "uncertain": [
    {{"text": "текст", "options": ["task", "thought"], "question": "Вопрос?"}}
  ]
}}

Если все записи понятны — uncertain должен быть пустым списком [].
Не добавляй пояснений — только JSON."""

        result = self.runner.run(prompt, "Daily categorization")
        if "error" in result:
            return result

        raw = result.get("report", "")
        try:
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text.rsplit("\n", 1)[0] if "\n" in text else text[:-3]
            parsed = json.loads(text.strip())
        except (json.JSONDecodeError, ValueError):
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                try:
                    parsed = json.loads(match.group())
                except (json.JSONDecodeError, ValueError):
                    parsed = None
            else:
                parsed = None

        if parsed and isinstance(parsed, dict):
            return {
                "confident": parsed.get("confident", []),
                "uncertain": parsed.get("uncertain", []),
            }

        logger.warning(
            "Failed to parse categorization JSON.\nRaw: %s", raw[:300]
        )
        return {
            "confident": [], "uncertain": [],
            "parse_error": "no valid JSON", "raw": raw,
        }

    def process_daily_finalize(
        self, day: date | None, entries: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Second-pass: process categorized entries."""
        if day is None:
            day = date.today()

        skill_content = self.runner.load_skill_content()

        entries_text = "\n".join(
            f"- [{e.get('category', 'thought').upper()}] {e.get('text', '')} "
            f"(действие: {e.get('action', '')})"
            for e in entries
        )

        prompt = f"""Сегодня {day}. Обработай уже категоризированные записи.

=== SKILL INSTRUCTIONS ===
{skill_content}
=== END SKILL ===

КАТЕГОРИЗИРОВАННЫЕ ЗАПИСИ:
{entries_text}

ПЕРВЫМ ДЕЛОМ: вызови mcp__todoist__user-info чтобы убедиться что MCP работает.

CRITICAL MCP RULE:
- ТЫ ИМЕЕШЬ ДОСТУП к mcp__todoist__* tools — ВЫЗЫВАЙ ИХ НАПРЯМУЮ
- Для записей [TASK]: добавь в Todoist через mcp__todoist__add-tasks
- Для записей [THOUGHT]: сохрани в vault/thoughts/
- Для записей [IDEA]: сохрани в vault/thoughts/ideas/
- НИКОГДА не пиши "MCP недоступен" или "добавь вручную"

CRITICAL OUTPUT FORMAT:
- Return ONLY raw HTML for Telegram (parse_mode=HTML)
- NO markdown: no **, no ##, no ```, no tables
- Start directly with 📊 <b>Обработка за {day}</b>
- Allowed tags: <b>, <i>, <code>, <s>, <u>"""

        return self.runner.run(prompt, "Daily finalize")

    def process_daily(self, day: date | None = None) -> dict[str, Any]:
        """Process daily file with Claude."""
        if day is None:
            day = date.today()

        daily_file = self.vault_path / "daily" / f"{day.isoformat()}.md"

        if not daily_file.exists():
            logger.warning("No daily file for %s", day)
            return {
                "error": f"No daily file for {day}",
                "processed_entries": 0,
            }

        skill_content = self.runner.load_skill_content()

        prompt = f"""Сегодня {day}. Выполни ежедневную обработку.

=== SKILL INSTRUCTIONS ===
{skill_content}
=== END SKILL ===

ПЕРВЫМ ДЕЛОМ: вызови mcp__todoist__user-info чтобы убедиться что MCP работает.

CRITICAL MCP RULE:
- ТЫ ИМЕЕШЬ ДОСТУП к mcp__todoist__* tools — ВЫЗЫВАЙ ИХ НАПРЯМУЮ
- НИКОГДА не пиши "MCP недоступен" или "добавь вручную"
- Для задач: вызови mcp__todoist__add-tasks tool
- Если tool вернул ошибку — покажи ТОЧНУЮ ошибку в отчёте

CRITICAL OUTPUT FORMAT:
- Return ONLY raw HTML for Telegram (parse_mode=HTML)
- NO markdown: no **, no ## , no ```, no tables
- Start directly with 📊 <b>Обработка за {day}</b>
- Allowed tags: <b>, <i>, <code>, <s>, <u>
- If entries already processed, return status report in same HTML format"""

        return self.runner.run(prompt, "Claude processing")

    def _read_coaching_context(self, max_chars: int = 2000) -> str:
        """Read vault/goals/coaching_context.md, capped at max_chars."""
        ctx_path = self.vault_path / "goals" / "coaching_context.md"
        if not ctx_path.exists():
            return ""
        try:
            return ctx_path.read_text(encoding="utf-8")[:max_chars]
        except Exception:
            logger.warning("Could not read coaching_context.md")
            return ""

    def _get_habit_actions_section(self) -> str:
        """Extract daily behavior actions from coaching_context table for /plan."""
        ctx_path = self.vault_path / "goals" / "coaching_context.md"
        if not ctx_path.exists():
            return ""
        try:
            content = ctx_path.read_text(encoding="utf-8")
        except Exception:
            return ""

        # Parse markdown table rows: | outcome | behavior |
        behaviors: list[str] = []
        in_table = False
        for line in content.splitlines():
            if "Текущие цели и ежедневные действия" in line:
                in_table = True
                continue
            if in_table:
                if line.startswith("|") and "---" not in line and "Цель" not in line:
                    cols = [c.strip() for c in line.strip("|").split("|")]
                    if len(cols) >= 2 and cols[1]:
                        behaviors.append(f"• {cols[1]}")
                elif in_table and line.startswith("##"):
                    break

        if not behaviors:
            return ""
        return "🎯 Habit Actions:\n" + "\n".join(behaviors) + "\n\n"

    def execute_prompt(self, user_prompt: str) -> dict[str, Any]:
        """Execute arbitrary prompt with Claude."""
        today = date.today()

        todoist_ref = self.runner.load_todoist_reference()

        coaching_ctx = self._read_coaching_context()
        coaching_section = (
            f"\n=== COACHING CONTEXT ===\n{coaching_ctx}\n=== END CONTEXT ===\n"
            if coaching_ctx
            else ""
        )

        prompt = f"""Ты - персональный ассистент d-brain.

CONTEXT:
- Текущая дата: {today}
- Vault path: {self.vault_path}
{coaching_section}
=== TODOIST REFERENCE ===
{todoist_ref}
=== END REFERENCE ===

ПЕРВЫМ ДЕЛОМ: вызови mcp__todoist__user-info чтобы убедиться что MCP работает.

CRITICAL MCP RULE:
- ТЫ ИМЕЕШЬ ДОСТУП к mcp__todoist__* tools — ВЫЗЫВАЙ ИХ НАПРЯМУЮ
- НИКОГДА не пиши "MCP недоступен" или "добавь вручную"
- Если tool вернул ошибку — покажи ТОЧНУЮ ошибку в отчёте

USER REQUEST:
{user_prompt}

CRITICAL OUTPUT FORMAT:
- Return ONLY raw HTML for Telegram (parse_mode=HTML)
- NO markdown: no **, no ##, no ```, no tables, no -
- Start with emoji and <b>header</b>
- Allowed tags: <b>, <i>, <code>, <s>, <u>
- Be concise - Telegram has 4096 char limit

EXECUTION:
1. Analyze the request
2. Call MCP tools directly (mcp__todoist__*, read/write files)
3. Return HTML status report with results"""

        return self.runner.run(prompt, "Claude execution")

    def chat_with_coach(self, history: list[dict[str, str]]) -> dict[str, Any]:
        """Send next message to Claude in coach mode with full conversation history."""
        today = date.today()
        coaching_ctx = self._read_coaching_context()

        history_text = "\n".join(
            f"{'Пользователь' if m['role'] == 'user' else 'Коуч'}: {m['content']}"
            for m in history[:-1]
        )
        last_message = history[-1]["content"] if history else ""

        prompt = f"""Сегодня {today}. Ты — персональный коуч пользователя.

ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ (coaching context):
{coaching_ctx}

ИСТОРИЯ РАЗГОВОРА:
{history_text}

НОВОЕ СООБЩЕНИЕ:
{last_message}

ПРАВИЛА:
- Отвечай как живой коуч, не как ассистент-исполнитель
- Используй профиль — ссылайся на цели и ежедневные действия пользователя
- Сначала понять, потом советовать
- Задавай один точный вопрос если нужно прояснить
- Если момент подходит для структурированной рефлексии — предложи GROW
- Обычный ответ: 2-4 предложения

CRITICAL OUTPUT FORMAT:
- Return ONLY raw HTML for Telegram (parse_mode=HTML)
- NO markdown: no **, no ##, no ```, no -
- Start directly with ответом (без префикса "Коуч:")
- Allowed tags: <b>, <i>, <u>"""

        return self.runner.run(prompt, "Coach chat")

    def save_coach_insights(self, history: list[dict[str, str]]) -> dict[str, Any]:
        """Summarize coach session, update coaching_context, save to daily vault."""
        import json as _json
        from datetime import datetime

        today = date.today()
        coaching_ctx = self._read_coaching_context()

        history_text = "\n".join(
            f"{'Пользователь' if m['role'] == 'user' else 'Коуч'}: {m['content']}"
            for m in history
        )

        prompt = f"""Проанализируй коуч-сессию и выдели инсайты для обновления профиля.

ТЕКУЩИЙ ПРОФИЛЬ:
{coaching_ctx}

СЕССИЯ:
{history_text}

Верни JSON:
{{
  "energy_additions": ["что нового узнали про источники энергии — если есть"],
  "flag_additions": ["новые паттерны или триггеры для раздела Флаги — если есть"],
  "daily_note": "1-2 предложения: суть сессии для дневника"
}}

Если ничего нового не выявлено — оставь списки пустыми.
CRITICAL OUTPUT FORMAT: только валидный JSON без markdown."""

        result = self.runner.run(prompt, "Coach insights")
        if "error" in result:
            return result

        raw = result.get("report", "")
        try:
            from services.grow import _parse_json  # type: ignore[import]
            data = _parse_json(raw)
        except Exception:
            import json as _json2
            import re as _re
            m = _re.search(r'\{[\s\S]*\}', raw)
            try:
                data = _json2.loads(m.group()) if m else {}
            except Exception:
                data = {}

        ctx_path = self.vault_path / "goals" / "coaching_context.md"
        if ctx_path.exists() and data:
            content = ctx_path.read_text(encoding="utf-8")
            for item in data.get("energy_additions", []):
                if item and item not in content:
                    content = content.replace(
                        "## Что даёт энергию\n",
                        f"## Что даёт энергию\n- {item}\n",
                    )
            for item in data.get("flag_additions", []):
                if item and item not in content:
                    content = content.replace(
                        "## Флаги (когда нужно пнуть)\n",
                        f"## Флаги (когда нужно пнуть)\n- {item}\n",
                    )
            ctx_path.write_text(content, encoding="utf-8")

        # Append note to daily vault
        note = data.get("daily_note", "")
        if note:
            daily_path = self.vault_path / "daily" / f"{today.isoformat()}.md"
            ts = datetime.now().strftime("%H:%M")
            try:
                with daily_path.open("a", encoding="utf-8") as f:
                    f.write(f"\n**{ts} [coach]** {note}\n")
            except Exception:
                logger.warning("Could not append coach note to daily vault")

        return {
            "report": (
                f"✅ <b>Инсайты сохранены</b>\n\n"
                f"<i>{_json.dumps(data, ensure_ascii=False, indent=2)}</i>"
                if data else
                "✅ Coach Mode завершён. Ничего нового в профиль не добавлено."
            )
        }

    def zoom_in(self) -> dict[str, Any]:
        """Zoom In — concrete actions for today based on coaching context."""
        today = date.today()

        coaching_ctx = self._read_coaching_context()

        weekly_goals = ""
        weekly_path = self.vault_path / "goals" / "3-weekly.md"
        if weekly_path.exists():
            try:
                weekly_goals = weekly_path.read_text(encoding="utf-8")[:1500]
            except Exception:
                pass

        prompt = f"""Сегодня {today}. Zoom in — конкретные действия.

COACHING CONTEXT (ежедневные habit actions):
{coaching_ctx}

НЕДЕЛЬНЫЕ ЦЕЛИ:
{weekly_goals}

ЗАДАЧА: Дай конкретный план действий на сегодня.
- 3-5 конкретных шагов из ежедневных habit actions
- Что сделать прямо сейчас (первый шаг)
- Убери всё лишнее — только то что двигает к целям

CRITICAL OUTPUT FORMAT:
- Return ONLY raw HTML for Telegram (parse_mode=HTML)
- NO markdown: no **, no ##, no ```, no tables, no -
- Start with 🎯 <b>Zoom In — что делать сейчас</b>
- Allowed tags: <b>, <i>, <code>, <s>, <u>
- Be concise - Telegram has 4096 char limit"""

        return self.runner.run(prompt, "Zoom In")

    def zoom_out(self) -> dict[str, Any]:
        """Zoom Out — big picture vision and main annual goals."""
        today = date.today()

        vision = ""
        vision_path = self.vault_path / "goals" / "0-vision-3y.md"
        if vision_path.exists():
            try:
                vision = vision_path.read_text(encoding="utf-8")[:1500]
            except Exception:
                pass

        yearly_goals = ""
        yearly_path = self.vault_path / "goals" / f"1-yearly-{today.year}.md"
        if yearly_path.exists():
            try:
                yearly_goals = yearly_path.read_text(encoding="utf-8")[:1500]
            except Exception:
                pass

        coaching_ctx = self._read_coaching_context(max_chars=1500)

        prompt = f"""Сегодня {today}. Режим zoom out — нужна большая картина и фокус.

VISION (3 года):
{vision}

ГОДОВЫЕ ЦЕЛИ ({today.year}):
{yearly_goals}

COACHING CONTEXT:
{coaching_ctx}

ЗАДАЧА: Напомни большую картину и верни фокус.
- Зачем всё это? (vision, смысл)
- 2-3 главные цели на год
- Как то, над чем работает сейчас, связано с большой картиной
- Один вопрос, который возвращает смысл

CRITICAL OUTPUT FORMAT:
- Return ONLY raw HTML for Telegram (parse_mode=HTML)
- NO markdown: no **, no ##, no ```, no tables, no -
- Start with 🔭 <b>Zoom Out — большая картина</b>
- Allowed tags: <b>, <i>, <code>, <s>, <u>
- Be concise - Telegram has 4096 char limit"""

        return self.runner.run(prompt, "Zoom Out")

    def generate_weekly(self) -> dict[str, Any]:
        """Generate weekly digest with Claude."""
        today = date.today()

        prompt = f"""Сегодня {today}. Сгенерируй недельный дайджест.

ПЕРВЫМ ДЕЛОМ: вызови mcp__todoist__user-info чтобы убедиться что MCP работает.

CRITICAL MCP RULE:
- ТЫ ИМЕЕШЬ ДОСТУП к mcp__todoist__* tools — ВЫЗЫВАЙ ИХ НАПРЯМУЮ
- НИКОГДА не пиши "MCP недоступен" или "добавь вручную"
- Для выполненных задач: вызови mcp__todoist__find-completed-tasks tool
- Если tool вернул ошибку — покажи ТОЧНУЮ ошибку в отчёте

WORKFLOW:
1. Собери данные за неделю (daily файлы в vault/daily/, completed tasks через MCP)
2. Проанализируй прогресс по целям (goals/3-weekly.md)
3. Определи победы и вызовы
4. Сгенерируй HTML отчёт

CRITICAL OUTPUT FORMAT:
- Return ONLY raw HTML for Telegram (parse_mode=HTML)
- NO markdown: no **, no ##, no ```, no tables
- Start with 📅 <b>Недельный дайджест</b>
- Allowed tags: <b>, <i>, <code>, <s>, <u>
- Be concise - Telegram has 4096 char limit"""

        result = self.runner.run(prompt, "Weekly digest")

        if "report" in result:
            try:
                summary_path = self._save_weekly_summary(
                    result["report"], today,
                )
                self._update_weekly_moc(summary_path)
            except Exception as e:
                logger.warning("Failed to save weekly summary: %s", e)

        return result

    def generate_monthly(self) -> dict[str, Any]:
        """Генерирует месячный отчёт"""
        from datetime import datetime, timedelta

        tz = _TZ
        today = datetime.now(tz)
        last_month = today.replace(day=1) - timedelta(days=1)
        month_name = last_month.strftime('%B %Y')

        prompt = f"""Сегодня {today.date()}. Сгенерируй месячный отчёт за {month_name}.

ПЕРВЫМ ДЕЛОМ: вызови mcp__todoist__user-info чтобы убедиться что MCP работает.

WORKFLOW:
1. Собери данные за месяц (daily файлы, completed tasks через MCP)
2. Проанализируй прогресс по месячным целям (goals/2-monthly.md)
3. Определи ключевые достижения и уроки
4. Сгенерируй HTML отчёт

CRITICAL OUTPUT FORMAT:
- Return ONLY raw HTML for Telegram (parse_mode=HTML)
- NO markdown: no **, no ##, no ```, no tables
- Start with 📊 <b>Месячный отчёт {month_name}</b>
- Allowed tags: <b>, <i>, <code>, <s>, <u>
- Be concise - Telegram has 4096 char limit"""

        return self.runner.run(prompt, "Monthly check")

    def generate_next_monthly_goals(
        self,
        summary: str,
        period: str,
        process_goals: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Generate new 2-monthly.md content based on GROW monthly insights.

        Args:
            summary: GROW monthly session summary.
            period:  Current period string, e.g. "2026-03".
            process_goals: List of {outcome, behavior} from GROW analysis.

        Returns:
            dict with key "content" containing the markdown for 2-monthly.md.
        """
        today = date.today()

        yearly_context = ""
        yearly_path = self.vault_path / "goals" / f"1-yearly-{today.year}.md"
        if yearly_path.exists():
            try:
                yearly_context = yearly_path.read_text(encoding="utf-8")[:2000]
            except Exception:
                pass

        goals_block = ""
        if process_goals:
            rows = "\n".join(
                f"- **{g.get('outcome', '')}** → {g.get('behavior', '')}"
                for g in process_goals
            )
            goals_block = f"\n\nEжедневные действия из GROW:\n{rows}"

        prompt = f"""GROW-рефлексия {period}. Сгенерируй файл целей на месяц.

GROW ИТОГ:
{summary}{goals_block}

ГОДОВЫЕ ЦЕЛИ (контекст):
{yearly_context}

Формат файла (только markdown, без ```markdown```):

---
type: monthly
period: {period}
updated: {today.isoformat()}
---

# Monthly Focus — {period}

## Top 3 Priorities
### Priority 1: [название]
[1-2 предложения что и зачем]

**Why it matters:** [одна строка]

**Key Actions:**
- [ ] ...

---

### Priority 2: [название]
...

---

### Priority 3: [название]
...

## NOT Doing This Month
- ...

---

## Weekly Check-ins

| Week | Progress | Blockers | Adjustments |
|------|----------|----------|-------------|
| W1 | | | |
| W2 | | | |
| W3 | | | |
| W4 | | | |

---

## Links

- [[0-vision-3y]] - 3-year vision
- [[1-yearly-{today.year}]] - Annual goals
- [[3-weekly]] - This week's plan

---

*Next Review: End of {period}*

Верни ТОЛЬКО markdown без ```markdown```.
Приоритеты — конкретные, из GROW-рефлексии."""

        result = self.runner.run(prompt, "Generate monthly goals")
        # runner returns dict with "report"; rename to "content"
        content = result.get("report", "")
        return {"content": content}

    # ── Evening / Morning plans ──────────────────────────────────────

    def get_evening_summary(self) -> str:
        """Вечерний итог дня"""
        from datetime import datetime

        tz = _TZ
        today = datetime.now(tz)
        today_str = today.strftime('%Y-%m-%d')

        try:
            events = get_calendar_events(days_ahead=0)
        except Exception as e:
            logger.warning("Calendar unavailable: %s", e)
            events = []

        all_active = (
            self.todoist.fetch_active_tasks() if self.todoist else []
        )
        tasks_planned = [
            t for t in all_active
            if t.get('due') and t['due'].get('date', '') == today_str
        ]
        overdue = [
            t for t in all_active
            if t.get('due') and t['due'].get('date', '') < today_str
        ]

        completed_count = (
            self.todoist.fetch_completed_today(today_str)
            if self.todoist else 0
        )

        summary = "🌙 ИТОГИ ДНЯ\n\n"

        if events:
            summary += f"🗓 События ({len(events)}):\n"
            for event in events:
                summary += f"• {event['summary']}\n"
            summary += "\n"

        total_planned = len(tasks_planned)
        if total_planned > 0 or completed_count > 0:
            summary += (
                f"✅ Выполнено: {completed_count}/{total_planned} задач\n"
            )
            if total_planned > 0:
                progress = int((completed_count / total_planned) * 100)
                summary += f"📊 Прогресс: {progress}%\n"
            summary += "\n"

        if overdue:
            summary += f"⚠️ Просрочено задач: {len(overdue)}\n"
            for task in sorted(
                overdue, key=lambda t: -t.get('priority', 1)
            )[:3]:
                summary += f"• {task['content']}\n"
            summary += "\n"

        summary += f"📋 Всего активных задач: {len(all_active)}\n\n"
        summary += "💡 Завтра:\n• Проверь /plan утром\n"

        return ClaudeRunner.truncate_for_telegram(summary)

    def get_daily_plan(self) -> str:
        """Формирует утренний план на день"""
        from datetime import datetime

        tz = _TZ
        today = datetime.now(tz)
        today_str = today.strftime('%Y-%m-%d')

        try:
            events = get_calendar_events(days_ahead=0)
        except Exception as e:
            logger.warning("Calendar unavailable: %s", e)
            events = []

        all_tasks = (
            self.todoist.fetch_active_tasks() if self.todoist else []
        )

        priority_map = {4: '🔴 P1', 3: '🟡 P2', 2: '⚪ P3', 1: '⚫ P4'}

        def sort_key(t: dict[str, Any]) -> int:
            return -int(t.get('priority', 1))

        today_tasks = []
        overdue_tasks = []
        fresh_overdue = []
        old_overdue = []
        upcoming_tasks = []
        no_date_tasks = []

        for task in all_tasks:
            due = task.get('due')
            if not due:
                no_date_tasks.append(task)
                continue

            due_date_str = due.get('date', '')
            if due_date_str == today_str:
                today_tasks.append(task)
            elif due_date_str < today_str:
                overdue_tasks.append(task)
                try:
                    due_date = tz.localize(
                        datetime.strptime(due_date_str, '%Y-%m-%d')
                    )
                    days_overdue = (today - due_date).days
                    if 1 <= days_overdue <= 3:
                        fresh_overdue.append(task)
                    elif days_overdue >= 5:
                        old_overdue.append(task)
                except Exception:
                    pass
            else:
                upcoming_tasks.append(task)

        # Автоперенос свежих просрочек (1-3 дня)
        moved_count = 0
        if self.todoist and fresh_overdue:
            for task in fresh_overdue:
                if self.todoist.reschedule_to_today(task['id']):
                    moved_count += 1

        # Расчёт времени
        work_start = today.replace(
            hour=9, minute=0, second=0, microsecond=0
        )
        work_end = today.replace(
            hour=18, minute=0, second=0, microsecond=0
        )
        total_available = 9.0

        busy_hours = 0.0
        if events:
            for event in events:
                try:
                    event_start = datetime.fromisoformat(
                        event['start'].replace('Z', '+00:00')
                    ).astimezone(tz)
                    event_end = datetime.fromisoformat(
                        event['end'].replace('Z', '+00:00')
                    ).astimezone(tz)
                    busy_hours += (
                        (event_end - event_start).total_seconds() / 3600
                    )
                except Exception:
                    pass

        free_hours = total_available - busy_hours

        # Расчёт свободных окон
        free_windows: list[dict[str, Any]] = []
        if events:
            sorted_events = sorted(events, key=lambda e: e['start'])
            current_time = work_start

            for event in sorted_events:
                try:
                    event_start = datetime.fromisoformat(
                        event['start'].replace('Z', '+00:00')
                    ).astimezone(tz)
                    event_end = datetime.fromisoformat(
                        event['end'].replace('Z', '+00:00')
                    ).astimezone(tz)

                    if event_start > current_time:
                        gap_hours = (
                            (event_start - current_time).total_seconds()
                            / 3600
                        )
                        if gap_hours >= 1:
                            free_windows.append({
                                'start': current_time.strftime('%H:%M'),
                                'end': event_start.strftime('%H:%M'),
                                'hours': gap_hours,
                            })
                    current_time = max(current_time, event_end)
                except Exception:
                    pass

            if current_time < work_end:
                gap_hours = (
                    (work_end - current_time).total_seconds() / 3600
                )
                if gap_hours >= 1:
                    free_windows.append({
                        'start': current_time.strftime('%H:%M'),
                        'end': work_end.strftime('%H:%M'),
                        'hours': gap_hours,
                    })

        # ── Формируем план ──
        plan = "📅 ПЛАН НА СЕГОДНЯ\n\n"

        plan += (
            f"⏱ Доступно: {free_hours:.1f}ч"
            f" | 📋 Занято: {busy_hours:.1f}ч\n\n"
        )

        if events:
            plan += "🗓 События:\n"
            for event in events:
                start_time = (
                    event['start'].split('T')[1][:5]
                    if 'T' in event['start']
                    else event['start']
                )
                end_time = (
                    event['end'].split('T')[1][:5]
                    if 'T' in event['end']
                    else event['end']
                )
                plan += (
                    f"• {start_time}-{end_time}: {event['summary']}\n"
                )
            plan += "\n"

        if free_windows:
            plan += "⏰ Свободные окна:\n"
            for window in free_windows:
                plan += (
                    f"• {window['start']}-{window['end']}"
                    f" ({window['hours']:.1f}ч)\n"
                )
            plan += "\n"

        total_today = len(today_tasks) + moved_count
        if total_today > 0:
            sorted_today = sorted(today_tasks, key=sort_key)

            plan += f"🔥 Задачи на сегодня ({total_today}):\n"
            for task in sorted_today[:10]:
                p = task.get('priority', 1)
                plan += (
                    f"{priority_map.get(p, '⚫ P4')}: {task['content']}\n"
                )

            if moved_count > 0:
                plan += (
                    f"\n🔄 Автоперенесено просрочек: {moved_count}\n"
                )
            plan += "\n"

            if total_today > 8:
                plan += "⚠️ Много задач — возможна перегрузка\n\n"

        if overdue_tasks:
            sorted_overdue = sorted(overdue_tasks, key=sort_key)
            plan += f"⚠️ Просрочены ({len(overdue_tasks)}):\n"
            for task in sorted_overdue[:5]:
                p = task.get('priority', 1)
                due_str = task.get('due', {}).get('date', '')
                plan += (
                    f"{priority_map.get(p, '⚫ P4')}:"
                    f" {task['content']} (до {due_str})\n"
                )
            if len(overdue_tasks) > 5:
                plan += f"... и ещё {len(overdue_tasks) - 5}\n"
            plan += "\n"

        if upcoming_tasks:
            sorted_upcoming = sorted(upcoming_tasks, key=sort_key)
            plan += f"📋 Ближайшие ({len(upcoming_tasks)}):\n"
            for task in sorted_upcoming[:7]:
                p = task.get('priority', 1)
                due_str = task.get('due', {}).get('date', '')
                plan += (
                    f"{priority_map.get(p, '⚫ P4')}:"
                    f" {task['content']} (до {due_str})\n"
                )
            if len(upcoming_tasks) > 7:
                plan += f"... и ещё {len(upcoming_tasks) - 7}\n"
            plan += "\n"

        if no_date_tasks:
            sorted_nodate = sorted(no_date_tasks, key=sort_key)
            plan += f"📌 Без срока ({len(no_date_tasks)}):\n"
            for task in sorted_nodate[:5]:
                p = task.get('priority', 1)
                plan += (
                    f"{priority_map.get(p, '⚫ P4')}: {task['content']}\n"
                )
            if len(no_date_tasks) > 5:
                plan += f"... и ещё {len(no_date_tasks) - 5}\n"
            plan += "\n"

        if today.day % 3 == 0:
            goals_file = self.vault_path / "goals/3-weekly.md"
            if goals_file.exists():
                plan += (
                    "🎯 Напоминание о недельных целях"
                    " — проверь goals/3-weekly.md\n\n"
                )

        total_all = len(all_tasks)
        if not events and total_all == 0:
            plan += "Событий и задач нет — свободный день! 🎉\n"

        # Inject habit actions from coaching_context
        habit_section = self._get_habit_actions_section()
        if habit_section:
            plan += habit_section

        return ClaudeRunner.truncate_for_telegram(plan)
