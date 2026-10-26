"""
Application configuration loaded from environment variables.

Uses pydantic-settings to read from .env file or environment.
All configurable values have sensible defaults so the app
can start without a .env file for basic development.
"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Gemini API
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    gemini_timeout: int = 120  # seconds

    # Application
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_debug: bool = True

    # Database
    database_dir: str = "./data"

    @property
    def database_path(self) -> Path:
        """Full path to the SQLite database file."""
        return Path(self.database_dir) / "labmate.db"

    @property
    def database_url(self) -> str:
        """SQLAlchemy connection string for SQLite."""
        return f"sqlite:///{self.database_path}"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Singleton instance used throughout the app
settings = Settings()
