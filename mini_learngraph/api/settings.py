"""Server settings, independent of model credentials.

MINI_LEARNGRAPH_ALLOWED_ORIGINS is a JSON array of exact local HTTP(S)
origins, for example '["http://127.0.0.1:5173"]'. Wildcards, paths, null,
credentials and non-loopback hosts are forbidden. A validated request's own
origin is also allowed. No model settings are read here.
"""

import re
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOST_PATTERN = re.compile(r"(?:127\.0\.0\.1|localhost)(?::([0-9]{1,5}))?", re.IGNORECASE)


def valid_host(value: str) -> bool:
    match = HOST_PATTERN.fullmatch(value)
    return match is not None and (
        match[1] is None or 1 <= int(match[1]) <= 65535
    )


class ServerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MINI_LEARNGRAPH_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    db_path: Path = PROJECT_ROOT / "data" / "learning.sqlite3"
    allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ]
    )
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)

    @field_validator("db_path")
    @classmethod
    def project_relative_db(cls, value: Path) -> Path:
        return value if value.is_absolute() else PROJECT_ROOT / value

    @field_validator("host")
    @classmethod
    def loopback_bind(cls, value: str) -> str:
        if value not in {"127.0.0.1", "localhost"}:
            raise ValueError("server binding must be loopback")
        return value

    @field_validator("allowed_origins")
    @classmethod
    def local_origins(cls, values: list[str]) -> list[str]:
        for value in values:
            parsed = urlsplit(value)
            if (
                parsed.scheme not in {"http", "https"}
                or not valid_host(parsed.netloc)
                or parsed.path
                or parsed.query
                or parsed.fragment
                or value != f"{parsed.scheme}://{parsed.netloc}"
            ):
                raise ValueError("origins must be exact local HTTP(S) origins")
        return list(dict.fromkeys(values))
