"""JSONL-based session persistence for storing all interactions."""

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


@dataclass
class SessionEntry:
    """Single session entry."""

    timestamp: str
    type: str  # voice, text, photo, forward, command
    content: str
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {k: v for k, v in asdict(self).items() if v is not None}


class SessionStorage:
    """JSONL-based session storage for append-only reliability.

    Stores all interactions in daily JSONL files for later analysis
    and context retrieval.
    """

    def __init__(self, vault_path: Path) -> None:
        self.vault_path = Path(vault_path)
        self.sessions_path = self.vault_path / "sessions"

    def _ensure_dirs(self) -> None:
        """Ensure sessions directory exists."""
        self.sessions_path.mkdir(parents=True, exist_ok=True)

    def _get_session_file(self, day: date) -> Path:
        """Get path to session file for given date."""
        self._ensure_dirs()
        return self.sessions_path / f"{day.isoformat()}.jsonl"

    def append(
        self,
        entry_type: str,
        content: str,
        timestamp: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Append entry to session file.

        Args:
            entry_type: Type of entry (voice, text, photo, forward, command)
            content: Entry content
            timestamp: Entry timestamp (defaults to now)
            metadata: Optional metadata dict
        """
        if timestamp is None:
            timestamp = datetime.now()

        entry = SessionEntry(
            timestamp=timestamp.isoformat(),
            type=entry_type,
            content=content,
            metadata=metadata,
        )

        file_path = self._get_session_file(timestamp.date())
        with file_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

    def get_today(self) -> list[SessionEntry]:
        """Get all entries for today."""
        return self.get_day(date.today())

    def get_day(self, day: date) -> list[SessionEntry]:
        """Get all entries for a specific day."""
        file_path = self._get_session_file(day)
        if not file_path.exists():
            return []

        entries = []
        with file_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    entries.append(
                        SessionEntry(
                            timestamp=data["timestamp"],
                            type=data["type"],
                            content=data["content"],
                            metadata=data.get("metadata"),
                        )
                    )
        return entries

    def get_recent(self, days: int = 7) -> list[SessionEntry]:
        """Get entries from the last N days.

        Args:
            days: Number of days to look back (default 7)

        Returns:
            List of entries sorted by timestamp (oldest first)
        """
        from datetime import timedelta

        entries = []
        today = date.today()

        for i in range(days):
            day = today - timedelta(days=i)
            entries.extend(self.get_day(day))

        # Sort by timestamp (oldest first)
        entries.sort(key=lambda e: e.timestamp)
        return entries

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about stored sessions.

        Returns:
            Dict with stats: total_entries, by_type, by_day, date_range
        """
        stats: dict[str, Any] = {
            "total_entries": 0,
            "by_type": {},
            "by_day": {},
            "date_range": {"first": None, "last": None},
        }

        if not self.sessions_path.exists():
            return stats

        session_files = sorted(self.sessions_path.glob("*.jsonl"))
        if not session_files:
            return stats

        # Parse first and last dates from filenames
        stats["date_range"]["first"] = session_files[0].stem
        stats["date_range"]["last"] = session_files[-1].stem

        for file_path in session_files:
            day = file_path.stem
            day_count = 0

            with file_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        entry_type = data.get("type", "unknown")

                        stats["total_entries"] += 1
                        day_count += 1
                        stats["by_type"][entry_type] = (
                            stats["by_type"].get(entry_type, 0) + 1
                        )

            stats["by_day"][day] = day_count

        return stats
