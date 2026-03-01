"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str = Field(description="Telegram Bot API token")
    deepgram_api_key: str = Field(description="Deepgram API key for transcription")
    todoist_api_key: str = Field(default="", description="Todoist API key for tasks")
    vault_path: Path = Field(
        default=Path("./vault"),
        description="Path to Obsidian vault directory",
    )
    google_token_path: Path = Field(
        default=Path("~/life-pilot-agent/token.json"),
        description="Path to Google OAuth token JSON file",
    )
    allowed_user_ids: list[int] = Field(
        default_factory=list,
        description="List of Telegram user IDs allowed to use the bot",
    )
    allow_all_users: bool = Field(
        default=False,
        description="Whether to allow access to all users (security risk!)",
    )
    transcription_language: str = Field(
        default="ru",
        description="Deepgram transcription language (e.g. ru, en, multi)",
    )
    claude_timeout: int = Field(
        default=1200,
        description="Claude CLI subprocess timeout in seconds",
    )

    @property
    def daily_path(self) -> Path:
        """Path to daily notes directory."""
        return self.vault_path / "daily"

    @property
    def attachments_path(self) -> Path:
        """Path to attachments directory."""
        return self.vault_path / "attachments"

    @property
    def thoughts_path(self) -> Path:
        """Path to thoughts directory."""
        return self.vault_path / "thoughts"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get application settings instance (cached singleton)."""
    return Settings()  # type: ignore[call-arg]
