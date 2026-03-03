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

    def __init__(
        self, vault_path: Path, todoist_api_key: str = "",
        coach_model: str = "",
    ) -> None:
        self.vault_path = Path(vault_path)
        self.todoist_api_key = todoist_api_key
        self.coach_model = coach_model
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

    def _read_diary_recent(self, max_chars: int = 800) -> str:
        """Read today's and yesterday's daily entries, capped at max_chars."""
        from datetime import timedelta
        lines: list[str] = []
        for delta in (0, 1):
            day = date.today() - timedelta(days=delta)
            path = self.vault_path / "daily" / f"{day.isoformat()}.md"
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8").strip()
                    if content:
                        lines.append(f"[{day.isoformat()}]\n{content}")
                except Exception:
                    pass
        combined = "\n\n".join(lines)
        return combined[:max_chars] if combined else ""

    def _read_last_coach_session(self) -> str:
        """Return summary of the last coach session from coach_sessions.jsonl."""
        sessions_path = self.vault_path / "sessions" / "coach_sessions.jsonl"
        if not sessions_path.exists():
            return ""
        try:
            lines = [
                l.strip()
                for l in sessions_path.read_text(encoding="utf-8").splitlines()
                if l.strip()
            ]
            if not lines:
                return ""
            last = json.loads(lines[-1])
            parts = [f"Дата: {last.get('session_date', '?')}"]
            if last.get("main_topic"):
                parts.append(f"Тема: {last['main_topic']}")
            insights = last.get("insights", [])
            if insights:
                parts.append("Инсайты: " + "; ".join(insights[:3]))
            decisions = last.get("decisions", [])
            if decisions:
                parts.append("Решения: " + "; ".join(decisions[:2]))
            return "\n".join(parts)
        except Exception:
            return ""

    def chat_with_coach(self, history: list[dict[str, str]]) -> dict[str, Any]:
        """Send next message to Claude in coach mode with full conversation history."""
        today = date.today()
        coaching_ctx = self._read_coaching_context()
        diary_recent = self._read_diary_recent()
        last_session = self._read_last_coach_session()

        history_text = "\n".join(
            f"{'Пользователь' if m['role'] == 'user' else 'Коуч'}: {m['content']}"
            for m in history[:-1]
        )
        last_message = history[-1]["content"] if history else ""
        is_first = len(history) == 1

        first_message_hint = ""
        if is_first:
            first_message_hint = """
ДЕТЕКЦИЯ ПЕРВОГО СООБЩЕНИЯ — выбери первый ход по типу:
- Выгрузка (эмоции, длинное, несколько тем) → Отражение чувства. БЕЗ вопроса.
- Запрос на решение ("не могу выбрать", конкретная развилка) → "Между чем и чем выбираешь?"
- Запрос на поддержку ("не тяну", "устал от") → Валидация + "Что сейчас самое тяжёлое?"
- Быстрый вопрос (короткий конкретный) → Короткий конкретный ответ. Не раздувать.
- Обновление/отчёт ("сделал X") → Признание + "Как ощущения?"
НЕ начинай с "Привет, о чём хочешь поговорить?"
"""

        diary_block = (
            f"\nДНЕВНИК (последние записи):\n{diary_recent}\n"
            if diary_recent else ""
        )
        last_session_block = (
            f"\nПОСЛЕДНЯЯ КОУЧ-СЕССИЯ:\n{last_session}\n"
            if last_session else ""
        )

        prompt = f"""Сегодня {today}. Ты — умный друг, который умеет слушать и задавать правильные вопросы. НЕ коуч с сертификатом, НЕ ассистент-исполнитель. Собеседник с навыками.

ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ:
{coaching_ctx}{diary_block}{last_session_block}
ПРАВИЛО КОНТЕКСТА: НЕ демонстрируй знание профиля/дневника в каждом сообщении. Используй только когда тема органично пересекается с тем, что говорит пользователь. Без ссылки на источник: "Это ведь связано с [цель]?"

ИСТОРИЯ:
{history_text}

НОВОЕ СООБЩЕНИЕ:
{last_message}
{first_message_hint}
STATE MACHINE — определи состояние по сигналам в НОВОМ СООБЩЕНИИ:

ПОТОК (выгружает, прыгает между темами, думает вслух):
  Сигналы: длинное сообщение, несколько тем, "ну короче", эмоциональная речь
  ВЫБОР ТЕХНИКИ:
    → Отражение (по умолчанию, безопасный ход)
    → Уточняющий вопрос (если совсем непонятно, о чём речь)
    → Пространство (если высокая эмоциональность — признание без вопроса)

ФОКУС (крутит одну тему, сравнивает варианты):
  Сигналы: возврат к одной теме, "не тяну"/"бесит"/"не уверен", конкретная ситуация
  ВЫБОР ТЕХНИКИ:
    → Уточняющий вопрос (по умолчанию)
    → Шкалирование (если оценочная тема: "не тяну", "не нравится", "не уверен")
    → Провокативный вопрос (если повторяет одно и то же 2+ сообщения подряд)
    → Привязка к профилю (если тема органично пересекается с целью/триггером)

ГОТОВНОСТЬ (появился инсайт, пользователь сам формулирует вывод):
  Сигналы: "значит мне надо", "я понял что", "наверное стоит", "окей, я сделаю"
  ВЫБОР ТЕХНИКИ:
    → Закрепление (по умолчанию: переформулировать конкретно)
    → Уточняющий вопрос (если решение размытое: что именно? когда? как поймёшь что сделал?)

Смена темы пользователем = сброс в ПОТОК (даже если был в ГОТОВНОСТИ).
Можно перескочить ПОТОК → ГОТОВНОСТЬ (если пришёл с готовым решением).

ТЕХНИКИ (одна за ход):
- Отражение: "Звучит как..." / "То есть для тебя..."
- Уточняющий вопрос: один конкретный вопрос
- Шкалирование: "Насколько это [важно/тяжело/срочно] от 1 до 10?"
- Провокативный вопрос: мягко ломает рамку. "А если бы X не было — ты бы всё равно...?"
- Пространство: "Это реально тяжело." Точка. Без вопроса.
- Привязка к профилю: "Это ведь связано с [цель]?" — ТОЛЬКО когда органично.
- Закрепление: "Окей, то есть план: [переформулировать конкретно]."

ГРАНИЧНЫЕ СЛУЧАИ:
- Пришёл с готовым решением ("я решил уволиться") → не допрашивать. Валидация + один проверочный: "Как ты к этому пришёл?" Если уверен — закрепить.
- Просто вентилирует (длинные эмоции, нет запроса на решение) → Пространство + Отражение. НЕ тащить к действию. Выговориться — тоже результат.
- Меняет тему каждое сообщение → после 3-й смены: "Ты говоришь про несколько вещей. Что из этого прямо сейчас самое горящее?"
- Конкретный бытовой вопрос ("во сколько встреча?") → ответить по данным, не превращать в коуч-сессию.
- Кризисные маркеры ("всё бессмысленно", "не вижу смысла") → НЕ коучить. Прямо: "Слышу, что тебе сейчас реально тяжело. Хочешь поговорить об этом?"

АНТИПАТТЕРНЫ — никогда не делай:
- Два вопроса в одном сообщении → один вопрос, точка
- "Расскажи подробнее?" без направления → конкретный: "Что именно тебя зацепило в этом?"
- Советы без запроса → задай вопрос, который подведёт к решению самому
- "Как ты себя чувствуешь?" → конкретнее: "Что сейчас самое тяжёлое?"
- "Я вижу из твоего профиля, что..." → упомяни связь без ссылки на источник
- Вопрос про действие когда человек в ПОТОКЕ → сначала дай пространство
- Перечисление вариантов → задай вопрос, который поможет увидеть варианты самому
- Длинные ответы (>800 символов) → 2-4 предложения, одна мысль, один вопрос

ФОРМАТ:
- 2-4 предложения, до 800 символов
- Без эмодзи (если пользователь не использует — ты тоже нет)
- Без буллетов, заголовков, списков — это чат, не отчёт
- Тёплый, прямой тон. Как умный друг, не как терапевт.
- Типичная структура: [Отражение — 1 пред.] [Вопрос — 1 пред.]
  Или только признание без вопроса (ПРОСТРАНСТВО)
  Или закрепление + уточнение (ГОТОВНОСТЬ)

Верни ТОЛЬКО текст ответа. HTML для Telegram, allowed tags: <b>, <i>, <u>."""

        return self.runner.run(prompt, "Coach chat", model=self.coach_model)

    def generate_reflection_question(self, history: list[dict[str, str]]) -> dict[str, Any]:
        """Generate personalized closing reflection question based on session history."""
        history_text = "\n".join(
            f"{'Пользователь' if m['role'] == 'user' else 'Коуч'}: {m['content']}"
            for m in history
        )
        prompt = f"""Ты завершаешь коуч-сессию. Вот полная история разговора:

{history_text}

Сформулируй один закрывающий вопрос по шаблону:
"Ты начал с [суть первого сообщения], пришёл к [суть последнего инсайта/темы]. Что из этого самое важное для тебя?"

Правила:
- Одно предложение
- [суть первого] и [суть последнего] — короткие, 3-5 слов, своими словами
- Если в разговоре не было явного движения — просто: "Что из этого разговора самое важное для тебя?"
- Без эмодзи, без форматирования

Верни ТОЛЬКО текст вопроса."""

        return self.runner.run(prompt, "Coach reflection", model=self.coach_model)

    def _patch_section_with_cap(
        self, content: str, header: str, new_item: str, max_items: int = 15,
    ) -> str:
        """Add item to markdown list section, evict oldest if over cap."""
        lines = content.splitlines()
        section_start: int | None = None
        item_lines: list[int] = []

        for i, line in enumerate(lines):
            if section_start is None:
                if header in line:
                    section_start = i
            else:
                if line.startswith("##") and i > section_start:
                    break
                if line.startswith("- "):
                    item_lines.append(i)

        if section_start is None:
            return content

        if len(item_lines) >= max_items and item_lines:
            del lines[item_lines[0]]
            # item_lines[0] > section_start always, so section_start unchanged

        lines.insert(section_start + 1, f"- {new_item}")
        return "\n".join(lines)

    def save_coach_insights(
        self, history: list[dict[str, str]], reflection_answer: str = "",
    ) -> dict[str, Any]:
        """Summarize coach session, update coaching_context, save to daily vault."""
        from datetime import datetime

        today = date.today()
        coaching_ctx = self._read_coaching_context()

        history_text = "\n".join(
            f"{'Пользователь' if m['role'] == 'user' else 'Коуч'}: {m['content']}"
            for m in history
        )
        reflection_block = (
            f"\nОТВЕТ НА ФИНАЛЬНЫЙ ВОПРОС:\n{reflection_answer}\n"
            if reflection_answer else ""
        )

        prompt = f"""Проанализируй коуч-сессию и извлеки структурированные данные.

ТЕКУЩИЙ ПРОФИЛЬ:
{coaching_ctx}

СЕССИЯ ({len(history)} сообщений):
{history_text}{reflection_block}

Верни валидный JSON без markdown:
{{
  "entry_state": "ПОТОК|ФОКУС|ГОТОВНОСТЬ|НЕИЗВЕСТНО",
  "main_topic": "краткое описание темы (1 строка)",
  "insights": ["инсайт — слова пользователя, не твои интерпретации"],
  "decisions": ["конкретное решение/шаг если был"],
  "energy_updates": ["новый источник энергии если выявлен"],
  "flag_updates": ["новый триггер/паттерн если выявлен"],
  "daily_note": "1-2 предложения — суть сессии для дневника"
}}

Правила:
- entry_state — по тональности первых 2-3 реплик пользователя
- insights — только то что пользователь СКАЗАЛ, не твои интерпретации
- decisions — конкретные действия ("перенесу задачу"), не намерения ("подумать")
- Если ничего нового в секциях — оставь списки пустыми []
- Только валидный JSON без ```json```"""

        result = self.runner.run(prompt, "Coach insights", model=self.coach_model)
        if "error" in result:
            return result

        raw = result.get("report", "")
        data: dict[str, Any] = {}
        try:
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text.rsplit("\n", 1)[0] if "\n" in text else text[:-3]
            data = json.loads(text.strip())
        except (json.JSONDecodeError, ValueError):
            m = re.search(r'\{[\s\S]*\}', raw)
            try:
                data = json.loads(m.group()) if m else {}
            except Exception:
                data = {}

        # Append to coach_sessions.jsonl
        sessions_path = self.vault_path / "sessions" / "coach_sessions.jsonl"
        sessions_path.parent.mkdir(parents=True, exist_ok=True)
        session_record: dict[str, Any] = {
            "session_date": today.isoformat(),
            "session_id": f"coach-{datetime.now().strftime('%Y%m%dT%H%M%S')}",
            "turns": len(history),
            "entry_state": data.get("entry_state", "НЕИЗВЕСТНО"),
            "main_topic": data.get("main_topic", ""),
            "insights": data.get("insights", []),
            "decisions": data.get("decisions", []),
            "energy_updates": data.get("energy_updates", []),
            "flag_updates": data.get("flag_updates", []),
            "diary_note": data.get("daily_note", ""),
        }
        try:
            with sessions_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(session_record, ensure_ascii=False) + "\n")
        except Exception:
            logger.warning("Could not append to coach_sessions.jsonl")

        # Patch coaching_context.md with sliding window cap
        ctx_path = self.vault_path / "goals" / "coaching_context.md"
        if ctx_path.exists() and data:
            content = ctx_path.read_text(encoding="utf-8")
            for item in data.get("energy_updates", []):
                if item and item not in content:
                    content = self._patch_section_with_cap(
                        content, "## Что даёт энергию", item,
                    )
            for item in data.get("flag_updates", []):
                if item and item not in content:
                    content = self._patch_section_with_cap(
                        content, "## Флаги (когда нужно пнуть)", item,
                    )
            ctx_path.write_text(content, encoding="utf-8")

        # Append diary note
        note = data.get("daily_note", "")
        if note:
            daily_path = self.vault_path / "daily" / f"{today.isoformat()}.md"
            ts = datetime.now().strftime("%H:%M")
            try:
                with daily_path.open("a", encoding="utf-8") as f:
                    f.write(f"\n**{ts} [coach]** {note}\n")
            except Exception:
                logger.warning("Could not append coach note to daily vault")

        if not data:
            return {
                "report": "✅ Coach Mode завершён. Ничего нового в профиль не добавлено."
            }

        parts = ["✅ <b>Инсайты сохранены</b>"]

        if data.get("main_topic"):
            parts.append(f"\n🎯 <b>Тема:</b> {data['main_topic']}")

        insights = data.get("insights", [])
        if insights:
            parts.append("\n💡 <b>Инсайты:</b>")
            for ins in insights:
                parts.append(f"• {ins}")

        decisions = data.get("decisions", [])
        if decisions:
            parts.append("\n✅ <b>Решения:</b>")
            for dec in decisions:
                parts.append(f"• {dec}")

        flags = data.get("flag_updates", [])
        if flags:
            parts.append("\n🚩 <b>Флаги:</b>")
            for fl in flags:
                parts.append(f"• {fl}")

        energy = data.get("energy_updates", [])
        if energy:
            parts.append("\n⚡ <b>Энергия:</b>")
            for en in energy:
                parts.append(f"• {en}")

        if note:
            parts.append(f"\n📝 <b>Заметка:</b>\n<i>{note}</i>")

        return {"report": "\n".join(parts)}

    def compact_coach_profile(self) -> dict[str, Any]:
        """Monthly: read coach sessions JSONL for current month, regenerate profile."""
        today = date.today()
        month_prefix = today.strftime("%Y-%m")

        sessions_path = self.vault_path / "sessions" / "coach_sessions.jsonl"
        sessions_this_month: list[dict[str, Any]] = []
        if sessions_path.exists():
            try:
                for line in sessions_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if record.get("session_date", "").startswith(month_prefix):
                            sessions_this_month.append(record)
                    except Exception:
                        pass
            except Exception:
                logger.warning("Could not read coach_sessions.jsonl")

        if not sessions_this_month:
            logger.info("No coach sessions in %s — skipping compact", month_prefix)
            return {"report": ""}

        ctx_path = self.vault_path / "goals" / "coaching_context.md"
        if not ctx_path.exists():
            return {"error": "coaching_context.md not found"}

        current_profile = ctx_path.read_text(encoding="utf-8")

        sessions_text = "\n\n".join(
            f"[{s.get('session_date')} / {s.get('entry_state', '?')}] "
            f"{s.get('main_topic', '')}\n"
            f"Инсайты: {'; '.join(s.get('insights', []))}\n"
            f"Решения: {'; '.join(s.get('decisions', []))}\n"
            f"Энергия: {'; '.join(s.get('energy_updates', []))}\n"
            f"Флаги: {'; '.join(s.get('flag_updates', []))}"
            for s in sessions_this_month
        )

        prompt = f"""Обнови профиль пользователя на основе коуч-сессий за {month_prefix}.

ТЕКУЩИЙ ПРОФИЛЬ:
{current_profile}

СЕССИИ ЗА МЕСЯЦ ({len(sessions_this_month)} сессий):
{sessions_text}

ЗАДАЧА:
1. Синтезируй паттерны из инсайтов и решений всех сессий
2. Обнови секцию "Что даёт энергию" — добавь новое, убери повторы и устаревшее
3. Обнови секцию "Флаги" — оставь подтверждённые паттерны, убери разовые
4. Обнови "Текущие цели и ежедневные действия" если decisions указывают на изменения
5. Сохрани структуру и заголовки файла без изменений
6. Не более 15 пунктов суммарно в динамических секциях
7. Обнови строку "Последнее обновление" на {today.isoformat()}

Верни ТОЛЬКО обновлённый markdown файл без пояснений и без ```markdown```."""

        # Backup before overwrite
        backup_path = ctx_path.with_suffix(".md.bak")
        try:
            backup_path.write_text(current_profile, encoding="utf-8")
        except Exception:
            logger.warning("Could not backup coaching_context.md")

        result = self.runner.run(
            prompt, "Coach profile compact", model=self.coach_model,
        )
        if "error" in result:
            return result

        new_content = result.get("report", "")
        if len(new_content) < 100:
            logger.warning("Compact returned too short — skipping overwrite")
            return {"error": "Compact result too short, profile not updated"}

        ctx_path.write_text(new_content, encoding="utf-8")
        logger.info(
            "coaching_context.md compacted (%d sessions)", len(sessions_this_month),
        )
        return {
            "report": (
                f"✅ Профиль обновлён по итогам "
                f"{len(sessions_this_month)} коуч-сессий за {month_prefix}."
            ),
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
