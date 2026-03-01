"""Vault search utility with Russian morphology support."""

import logging
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Vault path relative to project root
_VAULT_RELATIVE = "vault"

# Category mapping: path component → category name
_CATEGORY_MAP = {
    "daily": "daily",
    "ideas": "idea",
    "reflections": "reflection",
    "summaries": "summary",
    "tasks": "task",
    "learnings": "learning",
    "projects": "project",
    "goals": "goal",
}

# Russian suffixes to strip for morphological variants (longest first)
_SUFFIXES = [
    "ями", "ами", "ого", "его", "ому", "ему", "ого", "ей", "ий",
    "ой", "ая", "ую", "ие", "ые", "ов", "ев", "ью", "ью",
    "ых", "их", "ом", "ем", "ам", "ем",
    "ы", "а", "у", "е", "и", "й", "ь",
]


def _get_stems(keyword: str) -> list[str]:
    """Generate morphological variants for a Russian keyword.

    Strips common Russian suffixes to get the stem, then returns
    the stem plus the original keyword.

    Args:
        keyword: Russian word to stem.

    Returns:
        List of unique variants (stem + original).
    """
    word = keyword.lower().strip()
    variants = {word}  # always include original

    # Try stripping suffixes (longest first)
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            stem = word[: -len(suffix)]
            variants.add(stem)
            break  # only strip one suffix

    return list(variants)


def _get_category(file_path: Path) -> str:
    """Determine category from file path.

    Args:
        file_path: Absolute path to the file.

    Returns:
        Category string.
    """
    parts = file_path.parts
    for part in reversed(parts):
        if part in _CATEGORY_MAP:
            return _CATEGORY_MAP[part]
    return "note"


def _get_date(file_path: Path) -> str:
    """Extract date from file name or fall back to mtime.

    Args:
        file_path: Path to the file.

    Returns:
        ISO date string (YYYY-MM-DD).
    """
    name = file_path.stem
    # Try YYYY-MM-DD pattern at start of filename
    if len(name) >= 10 and name[4] == "-" and name[7] == "-":
        candidate = name[:10]
        try:
            datetime.strptime(candidate, "%Y-%m-%d")
            return candidate
        except ValueError:
            pass
    # Fall back to mtime
    try:
        mtime = file_path.stat().st_mtime
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    except OSError:
        return ""


def _grep_files(variant: str, vault_path: Path) -> list[Path]:
    """Run case-insensitive recursive grep and return matching file paths.

    Args:
        variant: Search term.
        vault_path: Root directory to search.

    Returns:
        List of matching file paths.
    """
    try:
        result = subprocess.run(
            ["grep", "-ril", "--include=*.md", variant, str(vault_path)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode not in (0, 1):  # 1 = no matches (normal)
            logger.warning(
                "grep returned code %s: %s", result.returncode, result.stderr
            )
        return [Path(p) for p in result.stdout.strip().splitlines() if p.strip()]
    except subprocess.TimeoutExpired:
        logger.error("grep timed out for variant: %s", variant)
        return []
    except FileNotFoundError:
        logger.error("grep not found on this system")
        return []


def search_vault(
    keywords: list[str],
    limit: int = 10,
    max_chars: int = 800,
    vault_path: Path | None = None,
) -> list[dict[str, str]]:
    """Search vault files by keywords with Russian morphology support.

    For each keyword, generates morphological variants (stem + original),
    runs grep -ril across vault, deduplicates and sorts by mtime (newest first).

    Args:
        keywords: List of search terms (Russian or English).
        limit: Maximum number of results to return.
        max_chars: Maximum characters to include from each file's content.
        vault_path: Override vault root path. Defaults to ~/life-pilot-agent/vault.

    Returns:
        List of dicts: {path, date, category, content}.
    """
    if vault_path is None:
        vault_path = Path.home() / "life-pilot-agent" / _VAULT_RELATIVE

    if not vault_path.exists():
        logger.warning("Vault path does not exist: %s", vault_path)
        return []

    # Collect all matching file paths
    matched: set[Path] = set()
    for keyword in keywords:
        for variant in _get_stems(keyword):
            files = _grep_files(variant, vault_path)
            matched.update(files)

    if not matched:
        return []

    # Sort by mtime descending (newest first), take limit
    def _mtime(p: Path) -> float:
        try:
            return p.stat().st_mtime
        except OSError:
            return 0.0

    sorted_files = sorted(matched, key=_mtime, reverse=True)[:limit]

    results = []
    for file_path in sorted_files:
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            if len(content) > max_chars:
                content = content[:max_chars] + "…"
        except OSError as e:
            logger.warning("Failed to read %s: %s", file_path, e)
            content = ""

        results.append({
            "path": str(file_path),
            "date": _get_date(file_path),
            "category": _get_category(file_path),
            "content": content,
        })

    return results
