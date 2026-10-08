"""Environment-backed settings resolved relative to the project directory."""

from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MINI_LEARNGRAPH_",
        env_file=PROJECT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    model_base_url: str
    model_id: str
    model_api_key: SecretStr
    max_steps: int = Field(default=8, gt=0)
    request_timeout_seconds: float = Field(default=60, gt=0, allow_inf_nan=False)
    connect_timeout_seconds: float = Field(default=10, gt=0, allow_inf_nan=False)
    read_timeout_seconds: float = Field(default=60, gt=0, allow_inf_nan=False)

    @field_validator("max_steps", mode="before")
    @classmethod
    def reject_boolean_steps(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("must be a positive integer, not a boolean")
        return value

    @field_validator("model_base_url", "model_id")
    @classmethod
    def nonempty_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("model_base_url")
    @classmethod
    def http_address(cls, value: str) -> str:
        address = urlsplit(value)
        if address.scheme not in {"http", "https"} or not address.hostname:
            raise ValueError("must be an HTTP or HTTPS base URL")
        if address.query or address.fragment:
            raise ValueError("base URL must not contain a query or fragment")
        return value.rstrip("/")

    @field_validator("model_api_key")
    @classmethod
    def nonempty_key(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("must not be empty")
        return value
