"""Additional B1 frozen-contract checks, independent of model credentials."""

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mini_learngraph.api.app import create_app
from mini_learngraph.api.settings import ServerSettings
from mini_learngraph.learning.schemas import ApiError

from .learning_fixtures import clarification, confirm_request, generator


@pytest.fixture
def http(tmp_path, monkeypatch):
    monkeypatch.setitem(ServerSettings.model_config, "env_file", None)
    for name in ("HOST", "PORT", "DB_PATH", "ALLOWED_ORIGINS"):
        monkeypatch.delenv(f"MINI_LEARNGRAPH_{name}", raising=False)
    with TestClient(
        create_app(tmp_path / "contract.sqlite3", generator(clarification())),
        base_url="http://127.0.0.1:8000",
    ) as client:
        yield client


def test_frozen_document_methods_match_live_openapi(http):
    contract = Path("docs/design-docs/learning-b1-api-contract.md").read_text(encoding="utf-8")
    frozen = {
        (method.lower(), "/api/v1" + path)
        for method, path in re.findall(r"\| (GET|POST|PUT) `([^`]+)`", contract)
    }
    openapi = http.get("/openapi.json").json()
    live = {(method, path) for path, operations in openapi["paths"].items() for method in operations}
    assert len(frozen) == 12 and frozen == live
    for schema in openapi["components"]["schemas"].values():
        if schema.get("type") == "object" and "properties" in schema:
            assert schema["additionalProperties"] is False
            assert set(schema["required"]) == set(schema["properties"])


@pytest.mark.parametrize("case,expected", [
    ("duplicate", "duplicate_question"), ("skip-value", "invalid_answer"),
    ("unknown", "unknown_question"), ("missing", "required"),
])
def test_confirmation_fixed_issue_codes_preserve_goal(http, case, expected):
    goal = http.post("/api/v1/goals", json={"prompt": "合成 CSV 学习目标"}).json()
    body = confirm_request(goal)
    if case == "duplicate":
        body["answers"] *= 2
    elif case == "skip-value":
        body["answers"][0]["value"] = "private-answer"
    elif case == "unknown":
        body["answers"][0]["key"] = "private-unknown-question"
    else:
        body["answers"] = []
    response = http.post(f"/api/v1/goals/{goal['id']}/confirm", json=body)
    assert response.status_code == 422
    error = ApiError.model_validate(response.json())
    assert expected in {issue.code for issue in error.details.issues}
    assert "private-answer" not in response.text and "private-unknown-question" not in response.text
    assert http.get(f"/api/v1/goals/{goal['id']}").json() == goal


def test_schema_confirmation_errors_are_uniform_json(http):
    goal = http.post("/api/v1/goals", json={"prompt": "CSV"}).json()
    request = confirm_request(goal)
    request["confirmed"] = 1
    response = http.post(f"/api/v1/goals/{goal['id']}/confirm", json=request)
    assert response.status_code == 422
    assert set(json.loads(response.text)) == {"code", "message", "details", "retryable"}
    assert http.get(f"/api/v1/goals/{goal['id']}").json() == goal
