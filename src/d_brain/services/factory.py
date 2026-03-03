"""Service factory — cached singletons for core services."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from d_brain.config import get_settings

if TYPE_CHECKING:
    from d_brain.services.claude_runner import ClaudeRunner
    from d_brain.services.git import VaultGit
    from d_brain.services.processor import ClaudeProcessor
    from d_brain.services.todoist import TodoistService


@lru_cache(maxsize=1)
def get_processor() -> ClaudeProcessor:
    """Return cached ClaudeProcessor instance."""
    settings = get_settings()
    from d_brain.services.processor import ClaudeProcessor

    return ClaudeProcessor(
        settings.vault_path, settings.todoist_api_key, settings.coach_model,
    )


@lru_cache(maxsize=1)
def get_todoist() -> TodoistService | None:
    """Return cached TodoistService or None if key is missing."""
    settings = get_settings()
    if not settings.todoist_api_key:
        return None
    from d_brain.services.todoist import TodoistService

    return TodoistService(settings.todoist_api_key)


@lru_cache(maxsize=1)
def get_runner() -> ClaudeRunner:
    """Return cached ClaudeRunner instance."""
    settings = get_settings()
    from d_brain.services.claude_runner import ClaudeRunner

    return ClaudeRunner(
        settings.vault_path, settings.todoist_api_key, settings.claude_timeout,
    )


@lru_cache(maxsize=1)
def get_git() -> VaultGit:
    """Return cached VaultGit instance."""
    settings = get_settings()
    from d_brain.services.git import VaultGit

    return VaultGit(settings.vault_path)
