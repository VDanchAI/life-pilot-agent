"""Vault tool handlers for /health, /memory, /creative."""

import asyncio
import json
import logging
import subprocess
from html import escape as html_escape
from pathlib import Path

from aiogram import Router
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from d_brain.config import get_settings

router = Router(name="vault_tools")
logger = logging.getLogger(__name__)

_MAX_MSG = 4000  # Telegram limit 4096, leave margin


def _paths() -> tuple[Path, Path, Path]:
    """Return (vault, memory_engine_script, analyze_script)."""
    vault = get_settings().vault_path.resolve()
    engine = vault / ".claude/skills/agent-memory/scripts/memory-engine.py"
    analyze = vault / ".claude/skills/graph-builder/scripts/analyze.py"
    return vault, engine, analyze


async def _run(cmd: list[str], timeout: int = 30) -> str:
    """Run subprocess in thread, return stdout."""
    result = await asyncio.to_thread(
        subprocess.run,
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"exit code {result.returncode}")
    return result.stdout.strip()


async def _send(message: Message, text: str) -> None:
    """Send text, truncate if over Telegram limit."""
    if len(text) > _MAX_MSG:
        text = text[:_MAX_MSG]
        # Close any HTML tags left open by truncation
        for tag in ("pre", "b", "i", "code"):
            unclosed = text.count(f"<{tag}>") - text.count(f"</{tag}>")
            if unclosed > 0:
                text += f"</{tag}>" * unclosed
        text += "\n\n... (обрезано)"
    await message.answer(text)


@router.message(Command("health"))
async def cmd_health(message: Message) -> None:
    """Vault health: memory tiers + graph stats."""
    await message.chat.do(action=ChatAction.TYPING)
    vault, engine, analyze = _paths()
    parts: list[str] = ["🏥 <b>Vault Health</b>"]

    # Memory stats
    try:
        stats = await _run(["python3", str(engine), "stats", str(vault)])
        parts.append(f"\n<b>📊 Память:</b>\n<pre>{html_escape(stats)}</pre>")
    except Exception as e:
        logger.exception("health: memory stats failed")
        parts.append(f"\n❌ memory stats: {html_escape(str(e))}")

    # Graph analysis (--html returns Telegram-ready HTML)
    try:
        graph = await _run(["python3", str(analyze), str(vault), "--html"])
        parts.append(f"\n{graph}")
    except Exception as e:
        logger.exception("health: graph analysis failed")
        parts.append(f"\n❌ graph: {html_escape(str(e))}")

    await _send(message, "\n".join(parts))


@router.message(Command("memory"))
async def cmd_memory(message: Message) -> None:
    """Memory engine: scan stats + config."""
    await message.chat.do(action=ChatAction.TYPING)
    vault, engine, _ = _paths()
    parts: list[str] = ["🧠 <b>Memory Engine</b>"]

    # Scan
    try:
        scan = await _run(["python3", str(engine), "scan", str(vault)])
        parts.append(f"\n<b>📋 Статистика:</b>\n<pre>{html_escape(scan)}</pre>")
    except Exception as e:
        logger.exception("memory: scan failed")
        parts.append(f"\n❌ scan: {html_escape(str(e))}")

    # Config from .memory-config.json
    config_path = vault / ".memory-config.json"
    try:
        cfg = json.loads(config_path.read_text())
        tiers = cfg.get("tiers", {})
        decay = cfg.get("decay_rate", "?")
        floor = cfg.get("relevance_floor", "?")
        cfg_text = (
            f"  active:  &lt;{tiers.get('active', '?')} дней\n"
            f"  warm:    &lt;{tiers.get('warm', '?')} дней\n"
            f"  cold:    &lt;{tiers.get('cold', '?')} дней\n"
            f"  archive: &gt;{tiers.get('cold', '?')} дней\n"
            f"  decay:   {decay}/день\n"
            f"  floor:   {floor}"
        )
        parts.append(f"\n<b>⚙️ Конфиг:</b>\n<pre>{cfg_text}</pre>")
    except FileNotFoundError:
        parts.append("\n⚠️ .memory-config.json не найден")
    except Exception as e:
        logger.exception("memory: config read failed")
        parts.append(f"\n❌ config: {html_escape(str(e))}")

    await _send(message, "\n".join(parts))


@router.message(Command("creative"))
async def cmd_creative(
    message: Message, command: CommandObject | None = None
) -> None:
    """Random cold/archive cards for inspiration."""
    await message.chat.do(action=ChatAction.TYPING)
    vault, engine, _ = _paths()

    n = 3
    if command and command.args:
        try:
            n = max(1, min(int(command.args.strip()), 10))
        except ValueError:
            pass

    try:
        output = await _run(
            ["python3", str(engine), "creative", str(n), str(vault)]
        )
        text = (
            f"🎲 <b>Творческая находка ({n}):</b>\n\n"
            f"<pre>{html_escape(output)}</pre>\n\n"
            f"💡 <i>Найди неожиданные связи с текущей задачей</i>"
        )
    except Exception as e:
        logger.exception("creative failed")
        text = f"❌ creative: {html_escape(str(e))}"

    await _send(message, text)
