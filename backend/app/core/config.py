from __future__ import annotations

import base64
import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent
DEFAULT_LOCAL_KEY_PATH = BACKEND_DIR / ".local_master_key"


def _decode_32byte_key(raw_value: str) -> bytes:
    """Decode a base64 or urlsafe-base64 32-byte key."""
    cleaned = raw_value.strip()
    padded = cleaned + "=" * (-len(cleaned) % 4)
    try:
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
    except Exception:
        decoded = base64.b64decode(padded.encode("ascii"))
    if len(decoded) != 32:
        raise ValueError("MASTER_ENCRYPTION_KEY must decode to exactly 32 bytes")
    return decoded


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env."""

    app_name: str = "APEX AI Trading Lab"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'apex_local.db').as_posix()}"
    redis_url: str = "redis://127.0.0.1:6379/0"
    master_encryption_key: str = ""
    session_ttl_hours: int = 24
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    session_cookie_name: str = "apex_session"

    model_config = SettingsConfigDict(
        env_file=(str(BACKEND_DIR / ".env"), str(PROJECT_ROOT / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        """Return parsed list of allowed CORS origins."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def get_master_key_bytes(self) -> bytes:
        """Return the 32-byte AES-256-GCM master key, generating a local dev key file if unset."""
        if self.master_encryption_key.strip():
            return _decode_32byte_key(self.master_encryption_key)

        if DEFAULT_LOCAL_KEY_PATH.exists():
            stored = DEFAULT_LOCAL_KEY_PATH.read_text(encoding="utf-8").strip()
            if stored:
                return _decode_32byte_key(stored)

        key_bytes = os.urandom(32)
        encoded = base64.urlsafe_b64encode(key_bytes).decode("ascii")
        DEFAULT_LOCAL_KEY_PATH.write_text(encoded, encoding="utf-8")
        try:
            os.chmod(DEFAULT_LOCAL_KEY_PATH, 0o600)
        except OSError:
            pass
        return key_bytes


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
