from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from mini_learngraph.config import PROJECT_ENV_FILE, Settings


def settings(**overrides):
    values = {
        "model_base_url": "https://model.example/v1/",
        "model_id": "test-model",
        "model_api_key": "test-secret",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_settings_defaults_and_secret_representation():
    config = settings()
    assert config.model_base_url == "https://model.example/v1"
    assert config.max_steps == 8
    assert config.request_timeout_seconds == 60
    assert isinstance(config.model_api_key, SecretStr)
    assert "test-secret" not in repr(config)


@pytest.mark.parametrize("field,value", [
    ("model_base_url", " "), ("model_base_url", "ftp://example.com"),
    ("model_base_url", "https://model.example/v1?route=x"),
    ("model_base_url", "https://model.example/v1#section"),
    ("model_id", ""), ("model_api_key", " \t"),
    ("max_steps", 0), ("max_steps", -1), ("max_steps", 1.5),
    ("max_steps", True), ("max_steps", False),
    ("request_timeout_seconds", 0), ("request_timeout_seconds", float("inf")),
    ("read_timeout_seconds", -1), ("connect_timeout_seconds", float("nan")),
])
def test_invalid_settings(field, value):
    with pytest.raises(ValidationError):
        settings(**{field: value})


def test_required_settings(monkeypatch):
    for field in ("MODEL_BASE_URL", "MODEL_ID", "MODEL_API_KEY"):
        monkeypatch.delenv(f"MINI_LEARNGRAPH_{field}", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_environment_prefix(monkeypatch):
    monkeypatch.setenv("MINI_LEARNGRAPH_MODEL_BASE_URL", "https://env.example/v1")
    monkeypatch.setenv("MINI_LEARNGRAPH_MODEL_ID", "env-model")
    monkeypatch.setenv("MINI_LEARNGRAPH_MODEL_API_KEY", "environment-secret")
    monkeypatch.setenv("MINI_LEARNGRAPH_MAX_STEPS", "3")
    config = Settings(_env_file=None)
    assert config.model_id == "env-model"
    assert config.model_api_key.get_secret_value() == "environment-secret"
    assert config.max_steps == 3


def test_project_env_path_does_not_follow_working_directory(monkeypatch, tmp_path):
    expected = Path(__file__).resolve().parent.parent / ".env"
    monkeypatch.chdir(tmp_path)
    assert PROJECT_ENV_FILE == expected
    assert Settings.model_config["env_file"] == expected


def test_dotenv_loading_and_explicit_precedence(monkeypatch, tmp_path):
    for field in ("MODEL_BASE_URL", "MODEL_ID", "MODEL_API_KEY", "MAX_STEPS"):
        monkeypatch.delenv(f"MINI_LEARNGRAPH_{field}", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "MINI_LEARNGRAPH_MODEL_BASE_URL=https://dotenv.example/v1\n"
        "MINI_LEARNGRAPH_MODEL_ID=file-model\n"
        "MINI_LEARNGRAPH_MODEL_API_KEY=file-secret\n"
        "MINI_LEARNGRAPH_MAX_STEPS=4\nUNRELATED_SETTING=ignored\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MINI_LEARNGRAPH_MAX_STEPS", "5")
    config = Settings(_env_file=env_file, model_id="explicit-model")
    assert config.model_base_url == "https://dotenv.example/v1"
    assert config.model_id == "explicit-model"
    assert config.max_steps == 5


def test_validation_error_does_not_display_secret():
    with pytest.raises(ValidationError) as error:
        settings(max_steps="private-invalid-value")
    assert "private-invalid-value" not in str(error.value)
