"""GROW coaching protocol — question selection, analysis, and reflection persistence."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from d_brain.config import get_settings
from d_brain.services.factory import get_runner, get_todoist

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Question bank — all questions VERBATIM
# ---------------------------------------------------------------------------

QUESTION_BANK: dict[str, list[dict[str, str]]] = {
    "weekly": [
        # GOAL
        {
            "id": "W-G1",
            "text": 'Твоя главная цель на неделю была "{ONE Big Thing}". Как ощущаешь — по шкале 1-10, насколько удалось продвинуться?',  # noqa: E501
        },
        {
            "id": "W-G2",
            "text": "Как ты мог бы себе помочь придерживаться цели на следующей неделе?",  # noqa: E501
        },
        # REALITY
        {
            "id": "W-R1",
            "text": "Что на этой неделе шло не так гладко, как хотелось? (данные: {N} просрочек, {паттерн переносов})",  # noqa: E501
        },
        {
            "id": "W-R2",
            "text": "Что на этой неделе дало больше всего энергии? Что забрало?",
        },
        {
            "id": "W-R3",
            "text": 'Задача "{задача}" переносится уже {K}-ю неделю. Может, за этим стоит что-то важное — что ты чувствуешь по этому поводу?',  # noqa: E501
        },
        {
            "id": "W-R4",
            "text": "Что на этой неделе пошло не по плану и чему тебя это научило?",
        },
        # OPTIONS
        {
            "id": "W-O1",
            "text": "Если бы на следующей неделе ты мог сделать только ОДНО дело — какое?",  # noqa: E501
        },
        {
            "id": "W-O2",
            "text": "Как лучше перестроить жизнь, чтобы появились возможности и силы для главного?",  # noqa: E501
        },
        # WILL
        {
            "id": "W-W1",
            "text": "Что может тебе помочь начать неделю легко?",
        },
        {
            "id": "W-W2",
            "text": "Какой запасной план ты можешь подготовить себе на случай, если что-то пойдёт не так?",  # noqa: E501
        },
    ],
    "monthly": [
        # GOAL
        {
            "id": "M-G1",
            "text": "Цели месяца были: {цели}. Они всё ещё актуальны или что-то сдвинулось?",  # noqa: E501
        },
        {
            "id": "M-G2",
            "text": "Что было бы реально полезно сделать в этом месяце?",
        },
        {
            "id": "M-G3",
            "text": "Что ценного ты понял в прошлом месяце, а что бы взял в этот?",
        },
        # REALITY
        {
            "id": "M-R1",
            "text": "Рефлексия была {N} из {4} недель. Бывает по-разному — что мешало найти на это время?",  # noqa: E501
        },
        {
            "id": "M-R2",
            "text": "Иногда планы расходятся с реальностью — что, на твой взгляд, вызвало этот разрыв в прошлом месяце?",  # noqa: E501
        },
        {
            "id": "M-R3",
            "text": "Какое твоё главное достижение за месяц? А главный урок?",
        },
        {
            "id": "M-R4",
            "text": "Что чаще всего тебе мешает достигать месячных целей? Понимание этого — уже шаг вперёд.",  # noqa: E501
        },
        # OPTIONS
        {
            "id": "M-O1",
            "text": "Выбери максимум 2 приоритета на следующий месяц. Почему именно эти?",  # noqa: E501
        },
        {
            "id": "M-O2",
            "text": "Что из текущего списка задач окончательно потеряло актуальность, а что стоит перенести?",  # noqa: E501
        },
        {
            "id": "M-O3",
            "text": "Какие ресурсы тебе нужны, которых сейчас нет? Есть ли возможность их получить, и если да — как? (время, знания, помощь, инструмент)",  # noqa: E501
        },
        # WILL
        {
            "id": "M-W1",
            "text": "Какой самый маленький, но реальный шаг ты можешь сделать завтра по каждому приоритету?",  # noqa: E501
        },
        {
            "id": "M-W2",
            "text": "Как ты можешь помочь себе не потерять фокус в следующем месяце?",
        },
        {
            "id": "M-W3",
            "text": "Что ты можешь с добротой к себе отпустить, чтобы стало легче двигаться?",  # noqa: E501
        },
    ],
    "quarterly": [
        # GOAL
        {
            "id": "Q-G1",
            "text": "Ты ставил годовые цели: {цели}. Что из этого по-прежнему зажигает, а что уже не откликается?",  # noqa: E501
        },
        {
            "id": "Q-G2",
            "text": "За три месяца многое могло измениться. Что нового появилось в твоей жизни, что стоит учесть в целях?",  # noqa: E501
        },
        # REALITY
        {
            "id": "Q-R1",
            "text": "За квартал — где ты реально продвинулся? Даже маленький прогресс считается.",  # noqa: E501
        },
        {
            "id": "Q-R2",
            "text": 'Что чаще всего тебе мешало? (данные: {паттерны из monthly рефлексий}). Это нормально — важно увидеть.',  # noqa: E501
        },
        {
            "id": "Q-R3",
            "text": "Какое решение за квартал оказалось удачным? Что ты тогда сделал правильно?",  # noqa: E501
        },
        # OPTIONS
        {
            "id": "Q-O1",
            "text": "Как ты можешь помочь себе двигаться к годовым целям легче и эффективнее в следующем квартале?",  # noqa: E501
        },
        {
            "id": "Q-O2",
            "text": "Что можно убрать или упростить, чтобы у тебя появилось больше пространства для главного?",  # noqa: E501
        },
        # WILL
        {
            "id": "Q-W1",
            "text": "Какой фокус на следующий квартал больше всего тебя продвинет?",
        },
        {
            "id": "Q-W2",
            "text": "Как ты можешь поддержать себя, чтобы держать этот фокус три месяца?",  # noqa: E501
        },
    ],
    "yearly_end": [
        # REALITY
        {
            "id": "YE-R1",
            "text": "Какое главное достижение года? Чем гордишься?",
        },
        {
            "id": "YE-R2",
            "text": "Что было самым сложным? Как ты с этим справился?",
        },
        {
            "id": "YE-R3",
            "text": "За что ты можешь себя поблагодарить?",
        },
        {
            "id": "YE-R4",
            "text": "Что ты делал регулярно и это дало результат?",
        },
        {
            "id": "YE-R5",
            "text": "Что в этом году забирало больше энергии, чем приносило пользы? Полезно это заметить.",  # noqa: E501
        },
        # GOAL
        {
            "id": "YE-G1",
            "text": "В начале года ты ставил: {цели}. Что из этого реально получилось?",
        },
        {
            "id": "YE-G2",
            "text": "Какие цели оказались неактуальны? Это нормально — иногда мы перерастаем свои планы.",  # noqa: E501
        },
        # OPTIONS
        {
            "id": "YE-O1",
            "text": "Какой главный урок года ты берёшь с собой?",
        },
        {
            "id": "YE-O2",
            "text": "Зная то, что ты знаешь сейчас — какой совет ты бы дал себе в начале года?",  # noqa: E501
        },
        # WILL
        {
            "id": "YE-W1",
            "text": "С каким чувством ты закрываешь этот год?",
        },
        {
            "id": "YE-W2",
            "text": "Что из этого года точно стоит взять дальше?",
        },
    ],
    "yearly_start": [
        # GOAL
        {
            "id": "YS-G1",
            "text": "Каким ты видишь себя через год? Что изменится в жизни?",
        },
        {
            "id": "YS-G2",
            "text": "Какие 2-3 цели сделают этот год значимым для тебя?",
        },
        {
            "id": "YS-G3",
            "text": "Как эти цели связаны с твоим видением на 3 года?",
        },
        # REALITY
        {
            "id": "YS-R1",
            "text": "Какие ресурсы и возможности у тебя есть прямо сейчас?",
        },
        {
            "id": "YS-R2",
            "text": "Что может стать вызовом? И как ты можешь заранее себе в этом помочь?",  # noqa: E501
        },
        # OPTIONS
        {
            "id": "YS-O1",
            "text": "Как ты можешь помочь себе не терять фокус на протяжении года?",
        },
        {
            "id": "YS-O2",
            "text": "Какую поддержку или среду тебе стоит создать?",
        },
        # WILL
        {
            "id": "YS-W1",
            "text": "Какой первый шаг в январе по каждой цели?",
        },
        {
            "id": "YS-W2",
            "text": "Мотивация бывает переменчивой — как ты можешь поддержать себя в моменты, когда она угасает?",  # noqa: E501
        },
    ],
}

# ---------------------------------------------------------------------------
# Question count bounds per session type
# ---------------------------------------------------------------------------

QUESTION_COUNT: dict[str, tuple[int, int]] = {
    "weekly": (2, 3),
    "monthly": (3, 4),
    "quarterly": (3, 4),
    "yearly_end": (3, 4),
    "yearly_start": (3, 4),
}

# ---------------------------------------------------------------------------
# Goal files per session type
# ---------------------------------------------------------------------------


def get_goal_file(session_type: str) -> str:
    """Return the goal file path relative to vault for a session type.

    Uses dynamic year calculation for yearly types.
    """
    year = date.today().year
    mapping = {
        "weekly": "goals/3-weekly.md",
        "monthly": "goals/2-monthly.md",
        "quarterly": f"goals/1-yearly-{year}.md",
        "yearly_end": f"goals/1-yearly-{year}.md",
        "yearly_start": f"goals/1-yearly-{year}.md",
    }
    return mapping.get(session_type, "goals/3-weekly.md")


# Human-readable labels for markdown output
_SESSION_LABELS: dict[str, str] = {
    "weekly": "Неделя",
    "monthly": "Месяц",
    "quarterly": "Квартал",
    "yearly_end": "Итоги года",
    "yearly_start": "Начало года",
}

# Period names used in prompts
_PERIOD_LABELS: dict[str, str] = {
    "weekly": "неделю",
    "monthly": "месяц",
    "quarterly": "квартал",
    "yearly_end": "год",
    "yearly_start": "год",
}


# ---------------------------------------------------------------------------
# Utility: safe JSON parsing (strips markdown fences)
# ---------------------------------------------------------------------------

def _parse_json(text: str) -> Any:
    """Parse JSON from text, stripping optional markdown code fences."""
    cleaned = text.strip()
    # Remove ```json ... ``` or ``` ... ```
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    return json.loads(cleaned.strip())


# ---------------------------------------------------------------------------
# Period helpers
# ---------------------------------------------------------------------------

def get_period_for_session(session_type: str) -> str:
    """Return period string for the current date.

    - weekly:      2026-W08
    - monthly:     2026-02
    - quarterly:   2026-Q1
    - yearly_end:  2026-end
    - yearly_start: 2026-start
    """
    today = date.today()
    if session_type == "weekly":
        iso_year, iso_week, iso_day = today.isocalendar()
        if iso_day == 1:  # Monday retry belongs to Sat-Sun cycle
            prev = today - timedelta(days=1)
            iso_year, iso_week, _ = prev.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    if session_type == "monthly":
        return today.strftime("%Y-%m")
    if session_type == "quarterly":
        quarter = (today.month - 1) // 3 + 1
        return f"{today.year}-Q{quarter}"
    if session_type == "yearly_end":
        return f"{today.year}-end"
    if session_type == "yearly_start":
        return f"{today.year}-start"
    raise ValueError(f"Unknown session_type: {session_type}")


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def load_grow_state(vault_path: Path) -> dict:
    """Load .grow_state.json from vault root. Returns empty dict if missing."""
    state_file = vault_path / ".grow_state.json"
    if not state_file.exists():
        return {}
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Failed to parse .grow_state.json, returning empty state")
        return {}


def save_grow_state(vault_path: Path, state: dict) -> None:
    """Save .grow_state.json to vault root."""
    state_file = vault_path / ".grow_state.json"
    state_file.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Reflection check
# ---------------------------------------------------------------------------

def is_reflection_done(session_type: str, period: str, vault_path: Path) -> bool:
    """Check if a final .md reflection file exists for this session+period."""
    target = vault_path / "reflections" / session_type / f"{period}.md"
    return target.exists()


# ---------------------------------------------------------------------------
# Draft management
# ---------------------------------------------------------------------------

def save_draft(
    session_type: str, period: str, data: dict, vault_path: Path
) -> Path:
    """Save a JSON draft to vault/reflections/{session_type}/{period}.draft.md."""
    draft_dir = vault_path / "reflections" / session_type
    draft_dir.mkdir(parents=True, exist_ok=True)
    draft_path = draft_dir / f"{period}.draft.md"
    draft_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("Draft saved: %s", draft_path)
    return draft_path


def load_draft(
    session_type: str, period: str, vault_path: Path
) -> dict | None:
    """Load draft if it exists. Returns parsed dict or None."""
    draft_path = vault_path / "reflections" / session_type / f"{period}.draft.md"
    if not draft_path.exists():
        return None
    try:
        return json.loads(draft_path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Failed to parse draft %s", draft_path)
        return None


def delete_draft(
    session_type: str, period: str, vault_path: Path
) -> None:
    """Delete draft file if it exists."""
    draft_path = vault_path / "reflections" / session_type / f"{period}.draft.md"
    if draft_path.exists():
        draft_path.unlink()
        logger.info("Draft deleted: %s", draft_path)


# ---------------------------------------------------------------------------
# Context collection
# ---------------------------------------------------------------------------

def get_previous_reflections(
    session_type: str, vault_path: Path, limit: int = 4
) -> str:
    """Read previous reflection .md files (not .draft.md), sorted descending.

    Returns their content concatenated.
    """
    ref_dir = vault_path / "reflections" / session_type
    if not ref_dir.exists():
        return ""
    files = sorted(
        [
            f
            for f in ref_dir.iterdir()
            if f.suffix == ".md" and not f.name.endswith(".draft.md")
        ],
        key=lambda p: p.name,
        reverse=True,
    )
    parts: list[str] = []
    for f in files[:limit]:
        try:
            parts.append(f"--- {f.stem} ---\n{f.read_text(encoding='utf-8')}")
        except Exception:
            logger.warning("Could not read reflection file %s", f)
    return "\n\n".join(parts)


def collect_grow_context(session_type: str, vault_path: Path) -> str:
    """Collect context for Claude question-selection prompt.

    Reads goals, Todoist tasks, previous reflections, and (for weekly)
    recent daily notes.
    """
    sections: list[str] = []

    # 1. Goals file
    goal_rel = get_goal_file(session_type)
    goal_path = vault_path / goal_rel
    if goal_path.exists():
        try:
            goal_text = goal_path.read_text(encoding="utf-8")
            sections.append(f"=== GOALS ({goal_rel}) ===\n{goal_text}")
        except Exception:
            logger.warning("Could not read goals file %s", goal_path)
    else:
        sections.append(f"=== GOALS ({goal_rel}) === [file not found]")

    # 2. Todoist tasks
    todoist = get_todoist()
    if todoist is not None:
        try:
            tasks = todoist.fetch_active_tasks()
            today_str = date.today().isoformat()
            overdue = [
                t for t in tasks
                if t.get("due")
                and t["due"].get("date")
                and t["due"]["date"] < today_str
            ]
            total = len(tasks)
            overdue_count = len(overdue)
            overdue_names = ", ".join(t.get("content", "?") for t in overdue[:5])
            sections.append(
                f"=== TODOIST ===\n"
                f"Active tasks: {total}\n"
                f"Overdue: {overdue_count}\n"
                f"Overdue tasks: {overdue_names or 'none'}"
            )
        except Exception:
            logger.warning("Failed to fetch Todoist tasks for GROW context")
            sections.append("=== TODOIST === [fetch failed]")
    else:
        sections.append("=== TODOIST === [not configured]")

    # 3. Previous reflections
    prev = get_previous_reflections(session_type, vault_path, limit=4)
    if prev:
        sections.append(f"=== PREVIOUS REFLECTIONS ===\n{prev}")

    # 4. Weekly: also read last 7 days of daily notes (first 300 chars each)
    if session_type == "weekly":
        daily_dir = vault_path / "daily"
        if daily_dir.exists():
            today = date.today()
            daily_parts: list[str] = []
            for offset in range(7):
                d = today - timedelta(days=offset)
                note_path = daily_dir / f"{d.isoformat()}.md"
                if note_path.exists():
                    try:
                        content = note_path.read_text(encoding="utf-8")[:300]
                        daily_parts.append(f"--- {d.isoformat()} ---\n{content}")
                    except Exception:
                        pass
            if daily_parts:
                sections.append(
                    "=== DAILY NOTES (last 7 days) ===\n" + "\n".join(daily_parts)
                )

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Claude call #1: select questions
# ---------------------------------------------------------------------------

async def select_questions(session_type: str) -> list[dict]:
    """Use Claude to select the most relevant questions for the session."""
    settings = get_settings()
    vault_path = settings.vault_path

    context = await asyncio.to_thread(collect_grow_context, session_type, vault_path)
    prev_reflections = await asyncio.to_thread(
        get_previous_reflections, session_type, vault_path
    )

    # Format question bank
    bank = QUESTION_BANK.get(session_type, [])
    bank_text = "\n".join(f"- {q['id']}: {q['text']}" for q in bank)

    min_q, max_q = QUESTION_COUNT.get(session_type, (2, 3))
    period_label = _PERIOD_LABELS.get(session_type, session_type)

    prompt = f"""Ты коуч. Используешь GROW фреймворк.

Данные пользователя за {period_label}:
{context}

Предыдущие рефлексии:
{prev_reflections}

Банк вопросов:
{bank_text}

Выбери {min_q}-{max_q} самых релевантных вопроса. Подставь реальные данные в шаблоны.

ПРАВИЛА ВЫБОРА:
- Не выбирай вопросы с пересекающимся смыслом
  (например W-R4 "чему научило" и M-R3 "главный урок")
- Если есть M-G1 (актуальность целей), НЕ бери M-G2 (что полезно)
  в ту же сессию — они конфликтуют
- Один вопрос из GOAL, минимум один из REALITY, минимум один из WILL/OPTIONS
- Учитывай что пользователь пропускал/откладывал в прошлых сессиях —
  не задавай то что он не хочет

Верни JSON:
[
  {{"id": "W-G1", "text": "Твоя главная цель — \\"продвижение\\". 1-10?"}},
  {{"id": "W-R3", "text": "Задача \\"посты\\" переносится уже 3-ю неделю..."}},
  {{"id": "W-W1", "text": "Что может тебе помочь начать неделю легко?"}}
]

CRITICAL OUTPUT FORMAT: Верни ТОЛЬКО валидный JSON, без markdown-обёртки."""

    runner = get_runner()
    result = await asyncio.to_thread(runner.run, prompt, "GROW select_questions")

    if "error" in result:
        logger.error("Claude select_questions failed: %s", result["error"])
        return _fallback_random_selection(session_type)

    raw = result.get("report", "")
    try:
        parsed = _parse_json(raw)
        if isinstance(parsed, list) and all(
            isinstance(q, dict) and "id" in q and "text" in q for q in parsed
        ):
            return parsed
        logger.warning("Claude returned unexpected structure, using fallback")
        return _fallback_random_selection(session_type)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("JSON parse failed for select_questions: %s", exc)
        return _fallback_random_selection(session_type)


def _fallback_random_selection(session_type: str) -> list[dict]:
    """Randomly pick questions from the bank if Claude call fails."""
    bank = QUESTION_BANK.get(session_type, [])
    min_q, max_q = QUESTION_COUNT.get(session_type, (2, 3))
    count = min(max_q, len(bank))
    return random.sample(bank, k=count)


# ---------------------------------------------------------------------------
# Claude call #2: analyze answers
# ---------------------------------------------------------------------------

async def analyze_answers(
    session_type: str,
    questions: list[dict],
    answers: dict,
    correction: str | None = None,
) -> dict:
    """Use Claude to produce a summary and optional goal updates."""
    settings = get_settings()
    vault_path = settings.vault_path

    # Format Q&A block
    qa_parts: list[str] = []
    for q in questions:
        qid = q["id"]
        ans = answers.get(qid)
        if ans == "skipped" or ans is None:
            ans_text = "[пропущен]"
        elif isinstance(ans, list):
            ans_text = "\n".join(str(a) for a in ans)
        else:
            ans_text = str(ans)
        qa_parts.append(f"{qid}: {q['text']}\nОтвет: {ans_text}")
    qa_block = "\n\n".join(qa_parts)

    # Read goals file
    goal_rel = get_goal_file(session_type)
    goal_path = vault_path / goal_rel
    goals_content = ""
    if goal_path.exists():
        try:
            goals_content = goal_path.read_text(encoding="utf-8")
        except Exception:
            pass

    prompt = f"""Ты коуч. Пользователь завершил {session_type} рефлексию по GROW.

ВОПРОСЫ И ОТВЕТЫ:
{qa_block}

ТЕКУЩИЕ ЦЕЛИ:
{goals_content}

ЗАДАЧА:
1. Напиши краткий итог рефлексии (3-5 предложений). Тон: поддерживающий,
без оценки. Отметь что пользователь осознал, какие паттерны видны.

2. Предложи конкретные обновления файла целей.

3. Для каждой цели которую называл пользователь — придумай 1-2 конкретных
ежедневных действия которые он полностью контролирует (process goals, не
outcome). Не результат, а действие: не "написать 5 постов", а "30 минут
утром — написать 1 пост до 10:00".

Формат — JSON:
{{
  "summary": "Краткий итог рефлексии...",
  "goal_updates": {{
    "file": "{goal_rel}",
    "sections": {{
      "ONE Big Thing": "новое значение",
      "Фокус недели": "обновлённый фокус"
    }}
  }},
  "process_goals": [
    {{
      "outcome": "Закончить LinkedIn наполнение",
      "behavior": "30 минут утром — написать 1 пост до 10:00"
    }}
  ]
}}

Если ответы не требуют обновления целей — goal_updates = null.
Если цели из ответов неясны — process_goals = [].
Если все вопросы пропущены — summary: "Сессия пропущена", goal_updates: null,
process_goals: [].

Не выдумывай ответы за пользователя. Основывайся ТОЛЬКО на том что он написал.
{f"""
КОРРЕКЦИЯ ОТ ПОЛЬЗОВАТЕЛЯ:
Пользователь попросил скорректировать предыдущий анализ:
"{correction}"
Учти это замечание при формировании итога и предложений по целям.
""" if correction else ""}
CRITICAL OUTPUT FORMAT:
Верни ТОЛЬКО валидный JSON, без markdown-обёртки."""

    runner = get_runner()
    result = await asyncio.to_thread(runner.run, prompt, "GROW analyze_answers")

    if "error" in result:
        logger.error("Claude analyze_answers failed: %s", result["error"])
        return {"summary": f"Analysis failed: {result['error']}", "goal_updates": None}

    raw = result.get("report", "")
    try:
        parsed = _parse_json(raw)
        if isinstance(parsed, dict) and "summary" in parsed:
            return parsed
        logger.warning("Claude returned unexpected structure for analysis")
        return {"summary": raw, "goal_updates": None}
    except (json.JSONDecodeError, ValueError):
        logger.warning("JSON parse failed for analyze_answers, returning raw text")
        return {"summary": raw, "goal_updates": None}


# ---------------------------------------------------------------------------
# Coaching context update
# ---------------------------------------------------------------------------


def _update_coaching_context(
    process_goals: list[dict],
    session_type: str,
    period: str,
    vault_path: Path,
) -> None:
    """Update vault/goals/coaching_context.md with process goals from GROW session.

    Rewrites the "Текущие цели и ежедневные действия" table and the
    "Последнее обновление" line.  Creates the file from a minimal template
    if it does not yet exist.
    """
    ctx_path = vault_path / "goals" / "coaching_context.md"

    if not ctx_path.exists():
        ctx_path.parent.mkdir(parents=True, exist_ok=True)
        ctx_path.write_text(
            "# Coaching Context\n\n"
            "## Профиль\n\n"
            "- Часовой пояс: Europe/Kyiv\n\n"
            "## Текущие цели и ежедневные действия\n\n"
            "| Цель (outcome) | Ежедневное действие |\n"
            "|---|---|\n\n"
            "## Что даёт энергию\n\n"
            "-\n\n"
            "## Флаги (когда нужно пнуть)\n\n"
            "-\n\n"
            "## Последнее обновление\n\n"
            "-\n",
            encoding="utf-8",
        )

    rows = "\n".join(
        f"| {g.get('outcome', '')} | {g.get('behavior', '')} |"
        for g in process_goals
        if g.get("outcome") and g.get("behavior")
    )
    table = (
        "| Цель (outcome) | Ежедневное действие |\n"
        "|---|---|\n"
        f"{rows}"
    )

    today_str = date.today().isoformat()
    session_label = _SESSION_LABELS.get(session_type, session_type)

    update_goals(
        ctx_path,
        {
            "Текущие цели и ежедневные действия": table,
            "Последнее обновление": f"{today_str}, {session_label} {period}",
        },
    )
    logger.info("coaching_context.md updated after %s %s", session_type, period)


# ---------------------------------------------------------------------------
# Finalize reflection
# ---------------------------------------------------------------------------

def finalize_reflection(
    session_type: str,
    period: str,
    summary: str,
    questions: list[dict],
    answers: dict,
    vault_path: Path,
    process_goals: list[dict] | None = None,
) -> Path:
    """Convert draft to final markdown with YAML frontmatter.

    Saves to vault/reflections/{session_type}/{period}.md,
    deletes draft, returns path.
    """
    today_str = date.today().isoformat()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    session_label = _SESSION_LABELS.get(session_type, session_type)

    # Build Q&A section
    qa_sections: list[str] = []
    for q in questions:
        qid = q["id"]
        ans = answers.get(qid)
        if ans == "skipped" or ans is None:
            ans_text = "*Пропущен*"
        elif isinstance(ans, list):
            ans_text = "\n".join(str(a) for a in ans)
        else:
            ans_text = str(ans)
        qa_sections.append(f"### {qid}: {q['text']}\n\n{ans_text}")

    qa_block = "\n\n".join(qa_sections)

    md = f"""---
type: grow-{session_type}
period: {period}
date: {today_str}
---

# GROW Рефлексия — {session_label} {period}

## Итог

{summary}

## Вопросы и ответы

{qa_block}

---

*Сгенерировано {now_str}*
"""

    ref_dir = vault_path / "reflections" / session_type
    ref_dir.mkdir(parents=True, exist_ok=True)
    target = ref_dir / f"{period}.md"
    target.write_text(md, encoding="utf-8")
    logger.info("Reflection finalized: %s", target)

    # Remove draft
    delete_draft(session_type, period, vault_path)

    # Update coaching context with process goals if provided
    if process_goals:
        try:
            _update_coaching_context(process_goals, session_type, period, vault_path)
        except Exception:
            logger.warning("Failed to update coaching_context.md", exc_info=True)

    return target


# ---------------------------------------------------------------------------
# Goal file updater
# ---------------------------------------------------------------------------

def update_goals(file_path: Path, sections: dict[str, str]) -> None:
    """Update a markdown file by finding section headers and replacing content.

    For each key in *sections*:
    - Find the header line matching ``## {key}`` or ``### {key}`` (case-insensitive)
    - Replace everything between it and the next same-or-higher-level header
    - If section not found, append to end of file
    """
    if not file_path.exists():
        logger.warning("Goal file does not exist: %s", file_path)
        return

    lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)

    for section_name, new_content in sections.items():
        header_idx: int | None = None
        header_level: int = 0

        # Find the header
        pattern = re.compile(
            r"^(#{2,6})\s+" + re.escape(section_name) + r"\s*$",
            re.IGNORECASE,
        )
        for i, line in enumerate(lines):
            m = pattern.match(line.rstrip("\n"))
            if m:
                header_idx = i
                header_level = len(m.group(1))
                break

        if header_idx is not None:
            # Find next section boundary (same or fewer #'s)
            boundary = len(lines)
            for j in range(header_idx + 1, len(lines)):
                stripped = lines[j].lstrip()
                if stripped.startswith("#"):
                    hashes = 0
                    for ch in stripped:
                        if ch == "#":
                            hashes += 1
                        else:
                            break
                    if hashes <= header_level:
                        boundary = j
                        break

            # Replace content between header (exclusive) and boundary (exclusive)
            replacement = new_content.strip() + "\n\n"
            lines[header_idx + 1 : boundary] = [replacement]
        else:
            # Section not found — append
            lines.append(f"\n## {section_name}\n\n{new_content.strip()}\n")

    file_path.write_text("".join(lines), encoding="utf-8")
    logger.info("Goals updated: %s", file_path)


# ---------------------------------------------------------------------------
# Yearly goals file bootstrap
# ---------------------------------------------------------------------------


def ensure_yearly_goals_file(year: int, vault_path: Path) -> Path:
    """Create a yearly goals file from template if it doesn't exist.

    Returns the path to the file.
    """
    target = vault_path / "goals" / f"1-yearly-{year}.md"
    if target.exists():
        return target

    template = f"""---
type: yearly
period: {year}
updated: {date.today().isoformat()}
---

# Goals {year}

## Annual Theme

**[Theme]** — ...

---

## Top Goals

1.
2.
3.

## Key Actions

-

## Definition of Done

-

---

## End of Year Review

### What Worked

-

### What Didn't Work

-

### Key Learnings

-

---

## Links

- [[0-vision-3y]] - 3-year vision
- [[2-monthly]] - Current month focus
- [[3-weekly]] - This week's plan

---

*Created {date.today().isoformat()}*
"""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(template, encoding="utf-8")
    logger.info("Created yearly goals file: %s", target)
    return target
