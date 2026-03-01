"""Claude CLI runner — subprocess execution with retry."""

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 1200  # 20 minutes

_ERROR_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"file.+not found", re.IGNORECASE), "Skill data unavailable"),
    (re.compile(r"permission denied", re.IGNORECASE), "System error"),
    (re.compile(r"mcp", re.IGNORECASE), "Task integration unavailable"),
    (
        re.compile(r"connection (refused|reset|timed out)", re.IGNORECASE),
        "Service connection error",
    ),
    (re.compile(r"ENOENT|EACCES|EPERM", re.IGNORECASE), "System error"),
    (re.compile(r"traceback|stacktrace", re.IGNORECASE), "Internal processing error"),
]


def _sanitize_error(raw: str) -> str:
    """Replace raw error details with user-friendly messages.

    Full error is already logged before this function is called.
    """
    for pattern, friendly in _ERROR_PATTERNS:
        if pattern.search(raw):
            return friendly
    if len(raw) > 150 or "/" in raw:
        return "Processing error"
    return raw


class ClaudeRunner:
    """Runs Claude CLI as a subprocess."""

    def __init__(
        self, vault_path: Path, todoist_api_key: str = "",
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.vault_path = Path(vault_path)
        self.todoist_api_key = todoist_api_key
        self.timeout = timeout
        self._mcp_config_path = (
            self.vault_path.parent / "mcp-config.json"
        ).resolve()

    def run(
        self, prompt: str, label: str,
    ) -> dict[str, Any]:
        """Run Claude CLI with one retry on non-zero exit (not on timeout).

        Args:
            prompt: The prompt to send to Claude.
            label: Human-readable label for log messages.

        Returns:
            Dict with "report" on success or "error" on failure.
        """
        result = self._execute(prompt, label)
        if "error" in result and "timed out" not in result["error"]:
            logger.info("Retrying %s after failure...", label)
            import time
            time.sleep(3)
            result = self._execute(prompt, label)
        return result

    def _execute(
        self, prompt: str, label: str,
    ) -> dict[str, Any]:
        """Single execution of Claude CLI."""
        try:
            env = os.environ.copy()
            if self.todoist_api_key:
                env["TODOIST_API_KEY"] = self.todoist_api_key

            proc = subprocess.run(
                [
                    "claude",
                    "--print",
                    "--dangerously-skip-permissions",
                    "--mcp-config",
                    str(self._mcp_config_path),
                    "-p",
                    prompt,
                ],
                cwd=self.vault_path.parent,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
                env=env,
            )

            logger.info(
                "%s rc=%s stdout=%.200s stderr=%.200s",
                label,
                proc.returncode,
                proc.stdout,
                proc.stderr,
            )

            if proc.returncode != 0:
                error_detail = (
                    proc.stderr.strip()
                    or proc.stdout.strip()[:200]
                    or f"exit code {proc.returncode}"
                )
                logger.error(
                    "%s failed (rc=%s): %s",
                    label,
                    proc.returncode,
                    error_detail,
                )
                return {
                    "error": f"{label} failed: {_sanitize_error(error_detail)}",
                    "processed_entries": 0,
                }

            return {
                "report": proc.stdout.strip(),
                "processed_entries": 1,
            }

        except subprocess.TimeoutExpired:
            logger.error("%s timed out", label)
            return {
                "error": f"{label} timed out",
                "processed_entries": 0,
            }
        except FileNotFoundError:
            logger.error("Claude CLI not found")
            return {
                "error": "Claude CLI not installed",
                "processed_entries": 0,
            }
        except Exception as e:
            logger.exception("Unexpected error during %s", label)
            return {"error": _sanitize_error(str(e)), "processed_entries": 0}

    def load_skill_content(self) -> str:
        """Load dbrain-processor skill content."""
        skill_path = (
            self.vault_path / ".claude/skills/dbrain-processor/SKILL.md"
        )
        if skill_path.exists():
            return skill_path.read_text()
        return ""

    def load_todoist_reference(self) -> str:
        """Load Todoist reference for inclusion in prompt."""
        ref_path = (
            self.vault_path
            / ".claude/skills/dbrain-processor/references/todoist.md"
        )
        if ref_path.exists():
            return ref_path.read_text()
        return ""

    @staticmethod
    def truncate_for_telegram(
        text: str, limit: int = 4096
    ) -> str:
        """Truncate message to fit Telegram's character limit."""
        if len(text) <= limit:
            return text
        truncated = text[: limit - 40]
        last_nl = truncated.rfind("\n")
        if last_nl > limit // 2:
            truncated = truncated[:last_nl]
        return truncated + "\n\n... (обрезано, слишком длинное)"
