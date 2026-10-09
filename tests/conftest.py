"""Keep B1 checks independent of a developer's server settings and dotenv."""

import pytest

from mini_learngraph.api.settings import ServerSettings


@pytest.fixture(autouse=True)
def isolate_b1_server_settings(request, monkeypatch):
    if request.module.__name__.split(".")[-1].startswith("test_learning_"):
        monkeypatch.setitem(ServerSettings.model_config, "env_file", None)
        for name in ("HOST", "PORT", "DB_PATH", "ALLOWED_ORIGINS"):
            monkeypatch.delenv(f"MINI_LEARNGRAPH_{name}", raising=False)
