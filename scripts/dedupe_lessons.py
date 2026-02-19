"""Deduplicate lessons in CLAUDE.md 'Уроки D.A.O.S.' section.

Finds duplicate/near-duplicate lessons and merges them, keeping only the
latest date. No date lists — clean and minimal.

Usage:
    uv run scripts/dedupe_lessons.py
    uv run scripts/dedupe_lessons.py --dry-run
"""

from __future__ import annotations

import re
import string
import sys
from pathlib import Path

CLAUDE_MD = Path(__file__).resolve().parent.parent / "CLAUDE.md"
SECTION_HEADER = "## Уроки D.A.O.S."
DATE_PATTERN = re.compile(r"^###\s+(\d{4}-\d{2}-\d{2})\s*[—–-]\s*(.+)$")
LESSON_PATTERN = re.compile(r"^-\s+(.+)$")


def normalize(text: str) -> str:
    """Normalize text for comparison: lowercase, strip punctuation/spaces."""
    text = text.lower().strip()
    text = text.translate(str.maketrans("", "", string.punctuation))
    text = re.sub(r"\s+", " ", text)
    return text


def parse_section(lines: list[str]) -> tuple[int, int]:
    """Find start and end line indices of the lessons section."""
    start = -1
    for i, line in enumerate(lines):
        if line.strip().startswith(SECTION_HEADER):
            start = i
            break
    if start == -1:
        return -1, -1
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].strip().startswith("## ") and not lines[i].strip().startswith("###"):
            end = i
            break
    return start, end


def find_lessons_start(lines: list[str], section_start: int, section_end: int) -> int:
    """Find where actual lesson entries begin (after header + description)."""
    for i in range(section_start + 1, section_end):
        stripped = lines[i].strip()
        if DATE_PATTERN.match(stripped) or LESSON_PATTERN.match(stripped):
            return i
    return -1


def parse_lessons(lines: list[str]) -> list[tuple[str, str, str]]:
    """Parse lessons into (date, doc_name, text) tuples."""
    lessons: list[tuple[str, str, str]] = []
    current_date = ""
    current_doc = ""
    for line in lines:
        date_match = DATE_PATTERN.match(line.strip())
        if date_match:
            current_date = date_match.group(1)
            current_doc = date_match.group(2).strip()
            continue
        lesson_match = LESSON_PATTERN.match(line.strip())
        if lesson_match and current_date:
            lessons.append((current_date, current_doc, lesson_match.group(1).strip()))
    return lessons


def dedupe(lessons: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    """Merge duplicates, keeping the latest date for each unique lesson."""
    seen: dict[str, int] = {}
    result: list[tuple[str, str, str]] = []

    for date, doc, text in lessons:
        key = normalize(text)
        if not key:
            continue
        if key in seen:
            idx = seen[key]
            existing_date = result[idx][0]
            if date > existing_date:
                result[idx] = (date, doc, result[idx][2])
        else:
            seen[key] = len(result)
            result.append((date, doc, text))

    return result


def format_lessons(lessons: list[tuple[str, str, str]]) -> list[str]:
    """Format deduplicated lessons back to markdown grouped by date+doc."""
    if not lessons:
        return []

    grouped: dict[tuple[str, str], list[str]] = {}
    order: list[tuple[str, str]] = []
    for date, doc, text in lessons:
        key = (date, doc)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(text)

    output: list[str] = []
    for date, doc in order:
        output.append(f"### {date} — {doc}")
        for text in grouped[(date, doc)]:
            output.append(f"- {text}")
        output.append("")

    return output


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    if not CLAUDE_MD.exists():
        print(f"ERROR: {CLAUDE_MD} not found")
        sys.exit(1)

    content = CLAUDE_MD.read_text(encoding="utf-8")
    lines = content.splitlines()

    start, end = parse_section(lines)
    if start == -1:
        print("Section 'Уроки D.A.O.S.' not found in CLAUDE.md")
        sys.exit(0)

    lessons_start = find_lessons_start(lines, start, end)
    if lessons_start == -1:
        print("No lessons found — nothing to deduplicate.")
        sys.exit(0)

    section_lines = lines[lessons_start:end]
    lessons = parse_lessons(section_lines)

    if not lessons:
        print("No lessons found — nothing to deduplicate.")
        sys.exit(0)

    before_count = len(lessons)
    deduped = dedupe(lessons)
    after_count = len(deduped)
    removed = before_count - after_count

    if removed == 0:
        print(f"All {before_count} lessons are unique — no duplicates found.")
        sys.exit(0)

    formatted = format_lessons(deduped)
    header_lines = lines[start:lessons_start]
    new_section = header_lines + [""] + formatted
    new_lines = lines[:start] + new_section + lines[end:]
    new_content = "\n".join(new_lines)

    if dry_run:
        print(f"DRY RUN: would merge {removed} duplicate(s) ({before_count} → {after_count})")
        print("\nResult:\n")
        print("\n".join(formatted))
    else:
        CLAUDE_MD.write_text(new_content, encoding="utf-8")
        print(f"Merged {removed} duplicate(s): {before_count} → {after_count} lessons")


if __name__ == "__main__":
    main()
