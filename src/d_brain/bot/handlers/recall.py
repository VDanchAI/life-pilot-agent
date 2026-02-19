"""Recall command — semantic search through vault (ТЗ 5)."""

import asyncio
import logging
from html import escape as html_escape

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from d_brain.bot.states import RecallStates
from d_brain.bot.utils import transcribe_voice
from d_brain.config import get_settings
from d_brain.services.factory import get_runner
from d_brain.services.vault_search import search_vault

router = Router(name="recall")
logger = logging.getLogger(__name__)

# Max chars per block in split output
_BLOCK_MAX = 3500


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from a search query."""
    stop_words = {
        "что", "как", "где", "когда", "это", "про", "для",
        "или", "мне", "меня", "моих", "моей", "моя", "мой", "мои",
        "было", "были", "есть", "нет", "все", "каком", "какой",
        "которые", "этой", "этот", "этого", "него", "них",
    }
    words = [w.strip(".,!?:;()[]\"'") for w in text.lower().split()]
    return [w for w in words if len(w) > 3 and w not in stop_words][:8]


def _split_by_records(text: str) -> list[str]:
    """Split Claude response into record-boundary blocks (max _BLOCK_MAX chars)."""
    if len(text) <= _BLOCK_MAX:
        return [text]

    blocks = []
    current = ""

    paragraphs = text.split("\n\n")
    for para in paragraphs:
        candidate = current + ("\n\n" if current else "") + para
        if len(candidate) > _BLOCK_MAX and current:
            blocks.append(current)
            current = para
        else:
            current = candidate

    if current:
        blocks.append(current)

    return blocks or [text[:_BLOCK_MAX]]


# ── shared search logic ────────────────────────────────────────────────


async def _run_search(message: Message, query_text: str) -> None:
    """Run vault search + Claude analysis and send results."""
    status_msg = await message.answer("🔍 Ищу в vault...")

    settings = get_settings()
    keywords = _extract_keywords(query_text)

    if not keywords:
        await status_msg.edit_text(
            "❓ Не смог извлечь ключевые слова. Попробуй другой запрос."
        )
        return

    results = await asyncio.to_thread(
        search_vault, keywords, 10, 800, settings.vault_path
    )

    if not results:
        await status_msg.edit_text(
            f"Не нашёл записей по запросу <b>{html_escape(query_text)}</b>.\n\n"
            "Попробуй другие слова."
        )
        return

    await status_msg.edit_text(f"📂 Нашёл {len(results)} записей. Анализирую...")

    records_text = "\n\n---\n\n".join(
        f"[{r['date']} / {r['category']}] {r['path'].split('/')[-1]}\n{r['content']}"
        for r in results
    )

    prompt = f"""Запрос пользователя: "{query_text}"

Найденные записи из личного vault:

{records_text}

ЗАДАЧА:
1. Сначала: короткая выжимка (3-5 предложений) — что нашёл, ключевые паттерны.
2. Затем: каждая запись отдельным блоком:

📄 [ДАТА] [КАТЕГОРИЯ]
[Краткое содержание 2-3 предложения]

---

КРИТИЧНО: разделяй блоки записей символом "---" на отдельных строках.
Не используй markdown, только простой текст. Не более 4000 символов."""

    runner = get_runner()
    result = await asyncio.to_thread(runner.run, prompt, "Recall search")

    response_text = result.get("report", result.get("error", "❌ Ошибка анализа"))
    blocks = _split_by_records(response_text)

    try:
        await status_msg.edit_text(blocks[0], parse_mode=None)
    except Exception:
        await status_msg.edit_text(blocks[0])

    for block in blocks[1:]:
        await message.answer(block, parse_mode=None)


# ── /recall command ───────────────────────────────────────────────────


@router.message(Command("recall"))
async def cmd_recall(
    message: Message, state: FSMContext, command: CommandObject | None = None
) -> None:
    """Start /recall — search inline if args given, else enter FSM."""
    await state.clear()

    if command and command.args and command.args.strip():
        await _run_search(message, command.args.strip())
        return

    await state.set_state(RecallStates.waiting_query)
    await message.answer(
        "🔍 <b>Поиск по записям</b>\n\n"
        "Что ищешь? Отправь текст или голосовое сообщение."
    )


# ── FSM: receive query ────────────────────────────────────────────────


@router.message(RecallStates.waiting_query)
async def handle_recall_query(message: Message, bot: Bot, state: FSMContext) -> None:
    """Process search query — voice or text, then run vault search."""
    if message.text and message.text.startswith("/"):
        await state.clear()
        return

    query_text: str | None = None

    if message.voice:
        await message.chat.do(action="typing")
        query_text = await transcribe_voice(bot, message)
        if not query_text:
            return
        await message.answer(f"🎤 <i>{html_escape(query_text)}</i>")
    elif message.text:
        query_text = message.text
    else:
        await message.answer("Отправь текст или голосовое сообщение")
        return

    await state.clear()

    await _run_search(message, query_text)
