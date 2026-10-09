"""Adversarial local HTTP boundary checks; temporary SQLite and model stubs only."""

import asyncio
import json
import sqlite3
import threading
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from mini_learngraph.api import __main__ as server
from mini_learngraph.api.app import create_app
from mini_learngraph.api.security import MAX_BODY_BYTES, SecurityBoundary, error_body
from mini_learngraph.api.settings import PROJECT_ROOT, ServerSettings
from mini_learngraph.learning.schemas import ApiError
from mini_learngraph.learning.storage import Store

from .learning_fixtures import generator


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    # B1 tests must not depend on the developer's .env or model credentials.
    monkeypatch.setitem(ServerSettings.model_config, "env_file", None)
    for name in ("HOST", "PORT", "DB_PATH", "ALLOWED_ORIGINS"):
        monkeypatch.delenv(f"MINI_LEARNGRAPH_{name}", raising=False)


@pytest.fixture
def app(tmp_path):
    return create_app(tmp_path / "security.sqlite3", generator=generator())


@pytest.fixture
def http(app):
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        yield client


def assert_safe_error(response, status, code, *secrets):
    assert response.status_code == status, response.text
    payload = response.json()
    ApiError.model_validate(payload)
    assert payload["code"] == code
    assert "detail" not in payload
    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for key, child in value.items():
                yield key
                yield from strings(child)
        elif isinstance(value, list):
            for child in value:
                yield from strings(child)

    # JSON null is a required absence marker, not the literal Origin "null".
    # Inspect all decoded keys/text recursively so actual input echoes still fail.
    for secret in secrets:
        assert not any(secret in value for value in strings(payload))
    return payload


def test_redaction_checks_json_text_not_absence_markers():
    payload = error_body("origin_not_allowed", "Origin is not allowed.")
    assert_safe_error(httpx.Response(403, json=payload), 403, "origin_not_allowed", "null")
    for leaked in ("null", "private-origin"):
        payload["details"]["issues"] = [{
            "path": ["body"], "code": "constraint", "message": f"Rejected {leaked}",
            "node_ids": [], "edge_indexes": [],
        }]
        with pytest.raises(AssertionError):
            assert_safe_error(httpx.Response(403, json=payload), 403, "origin_not_allowed", leaked)


@pytest.mark.parametrize("host", [
    "evil.example", "127.0.0.1.evil.example", "localhost.evil.example",
    "0.0.0.0:8000", "[::1]:8000", "localhost:0", "localhost:65536",
    "localhost:-1", "localhost:bad", "user@localhost", "localhost.",
])
def test_host_rejected_before_json_and_store(http, host):
    response = http.post("/api/v1/goals", content=b"bad-json-secret", headers={"Host": host})
    assert_safe_error(response, 403, "host_not_allowed", host, "bad-json-secret")
    assert http.get("/api/v1/goals").json() == {"items": []}


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "localhost:8000", "localhost:65535"])
def test_local_hosts_allowed(http, host):
    assert http.get("/api/v1/goals", headers={"Host": host}).status_code == 200


@pytest.mark.parametrize("origin", ["null", "https://evil.example", "http://localhost:9999", "http://127.0.0.1:5173.evil.example"])
@pytest.mark.parametrize("method,path", [("GET", "/api/v1/goals"), ("POST", "/api/v1/goals"), ("GET", "/docs"), ("GET", "/nonexistent")])
def test_unknown_origin_rejected_on_every_request(http, origin, method, path):
    response = http.request(method, path, content=b"private-json", headers={"Origin": origin})
    assert_safe_error(response, 403, "origin_not_allowed", origin, "private-json")
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("origin", ["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8000"])
def test_exact_local_and_same_origin_cors(http, origin):
    response = http.get("/api/v1/goals", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "origin" in response.headers["vary"].lower()
    assert "access-control-allow-credentials" not in response.headers


def test_cors_preflight_is_explicit(http):
    headers = {"Origin": "http://127.0.0.1:5173", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "Content-Type"}
    response = http.options("/api/v1/goals", headers=headers)
    assert response.status_code == 200
    assert response.headers["access-control-allow-methods"] == "GET, POST, PUT"
    assert response.headers["access-control-allow-headers"] == "Content-Type"
    assert response.headers["access-control-allow-origin"] == headers["Origin"]
    assert "*" not in str(response.headers)
    assert_safe_error(http.options("/api/v1/goals", headers=headers | {"Origin": "null"}), 403, "origin_not_allowed")
    assert_safe_error(http.options("/api/v1/goals", headers=headers | {"Access-Control-Request-Method": "DELETE"}), 405, "method_not_allowed")
    assert_safe_error(http.options("/api/v1/goals", headers=headers | {"Access-Control-Request-Headers": "Authorization"}), 403, "origin_not_allowed")


@pytest.mark.parametrize("headers", [
    [("Host", "localhost"), ("Host", "evil.example")],
    [("Origin", "http://127.0.0.1:5173"), ("Origin", "null")],
])
def test_duplicate_security_headers_rejected(http, headers):
    response = http.get("/api/v1/goals", headers=headers)
    assert response.status_code == 403
    ApiError.model_validate(response.json())


@pytest.mark.parametrize("body", [
    b'{"prompt":"first","prompt":"secret-second"}',
    b'{"prompt":"x","extra":{"nested":1,"nested":2}}',
    b'{"prompt":NaN}', b'{"prompt":Infinity}', b'{"prompt":-Infinity}',
    b'{"prompt":1e999999}', b'{"prompt":"x"} trailing-secret',
    b'```json\n{"prompt":"x"}\n```', b'{', b'', b'\xff',
    b'{"prompt":"\\ud800"}',
    '{"prompt":"x"}'.encode("utf-16"),
    b'{"prompt":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}',
])
def test_strict_full_json_before_schema_and_writes(http, body):
    response = http.post("/api/v1/goals", content=body, headers={"Content-Type": "application/json"})
    assert_safe_error(response, 400, "invalid_json", "secret-second", "trailing-secret")
    assert http.get("/api/v1/goals").json() == {"items": []}


@pytest.mark.parametrize("content_type", [None, "text/plain", "application/x-www-form-urlencoded", "multipart/form-data", "application/jsonp"])
def test_non_json_writes_rejected(http, content_type):
    headers = {"Content-Type": content_type} if content_type else {}
    response = http.post("/api/v1/goals", content=b'{"prompt":"private-prompt"}', headers=headers)
    assert_safe_error(response, 415, "unsupported_media_type", "private-prompt")


def test_json_charset_supported_with_uniform_schema_error(http):
    response = http.post("/api/v1/goals", content=b'{}', headers={"Content-Type": "application/json; charset=utf-8", "Origin": "http://localhost:5173"})
    payload = assert_safe_error(response, 422, "validation_failed")
    assert payload["details"]["issues"][0]["code"] == "required"
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_body_size_and_get_body(http):
    response = http.post("/api/v1/goals", content=b" " * (MAX_BODY_BYTES + 1), headers={"Content-Type": "application/json"})
    assert_safe_error(response, 413, "payload_too_large")
    assert_safe_error(http.request("GET", "/api/v1/goals", content=b"private-body"), 422, "validation_failed", "private-body")


async def test_chunked_limit_cannot_be_bypassed_by_short_content_length():
    called = False
    async def forbidden_app(scope, receive, send):
        nonlocal called
        called = True

    boundary = SecurityBoundary(forbidden_app, ["http://localhost:5173"])
    messages = iter([
        {"type": "http.request", "body": b" " * (MAX_BODY_BYTES // 2), "more_body": True},
        {"type": "http.request", "body": b" " * (MAX_BODY_BYTES // 2), "more_body": True},
        {"type": "http.request", "body": b"x", "more_body": False},
    ])
    sent = []
    async def receive():
        return next(messages)
    async def send(message):
        sent.append(message)
    await boundary({"type": "http", "scheme": "http", "method": "POST", "headers": [(b"host", b"localhost:8000"), (b"content-type", b"application/json"), (b"content-length", b"1")]}, receive, send)
    assert not called
    assert sent[0]["status"] == 413
    ApiError.model_validate(json.loads(sent[1]["body"]))


async def test_exact_body_limit_replays_multichunk_json_once():
    body = b"{}" + b" " * (MAX_BODY_BYTES - 2)
    received = []
    async def downstream(scope, receive, send):
        received.append(await receive())
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})
    messages = iter([
        {"type": "http.request", "body": body[:1024], "more_body": True},
        {"type": "http.request", "body": body[1024:], "more_body": False},
    ])
    async def receive():
        return next(messages)
    sent = []
    async def send(message):
        sent.append(message)
    boundary = SecurityBoundary(downstream, [])
    await boundary({"type": "http", "scheme": "http", "method": "POST", "headers": [(b"host", b"localhost"), (b"content-type", b"application/json")]}, receive, send)
    assert received == [{"type": "http.request", "body": body, "more_body": False}]
    assert sent[0]["status"] == 200


@pytest.mark.parametrize("path", [
    "/api/v1/goals?learner_id=private-query", "/api/v1/goals?status=draft&status=confirmed",
    "/api/v1/goals?status=private-status", "/api/v1/graphs?goal_id=bad-id",
    "/api/v1/graphs?revision=1", "/api/v1/goals/not-uuid",
    "/api/v1/goals/31FDC0AB-3C53-41CB-A95E-97B19EA2D1AD",
    "/api/v1/goals/00000000-0000-1000-8000-000000000000",
])
def test_query_and_uuid_validation_are_safe(http, path):
    assert_safe_error(http.get(path), 422, "validation_failed", "private-query", "private-status", "bad-id", "not-uuid")


@pytest.mark.parametrize("revision", ["0", "-1", "true", "1.5", "1.0", "1e0", "one"])
def test_revision_is_positive_integer(http, revision):
    response = http.get(f"/api/v1/graphs/{uuid4()}", params={"revision": revision})
    assert_safe_error(response, 422, "validation_failed")


@pytest.mark.parametrize("body", [
    {"prompt": "private-secret", "private-field-name": "private-value"},
    {"prompt": {"private-nested": "private-value"}},
    {"prompt": "private-secret" * 1000},
    {"prompt": "private-secret\x00"},
])
def test_schema_errors_never_echo_input(http, body):
    payload = assert_safe_error(http.post("/api/v1/goals", json=body), 422, "validation_failed", "private-secret", "private-field-name", "private-value", "private-nested")
    assert payload["details"]["issues"]
    assert http.get("/api/v1/goals").json() == {"items": []}


def test_expected_revision_rejects_boolean_before_store(http):
    response = http.post(f"/api/v1/graphs/{uuid4()}/publish", json={"expected_revision": True, "confirmed": True})
    payload = assert_safe_error(response, 422, "validation_failed")
    assert any(entry["path"] == ["body", "expected_revision"] for entry in payload["details"]["issues"])


def test_route_method_and_missing_resource_share_error_schema(http):
    assert_safe_error(http.get("/private-nonexistent-route"), 404, "route_not_found", "private-nonexistent-route")
    assert_safe_error(http.get("/api/v1/goals/", follow_redirects=False), 404, "route_not_found")
    response = http.request("DELETE", "/api/v1/goals", content=b"{}", headers={"Content-Type": "application/json"})
    assert_safe_error(response, 405, "method_not_allowed")
    assert_safe_error(http.get(f"/api/v1/goals/{uuid4()}"), 404, "resource_not_found")
    assert_safe_error(http.get("/api/v1/graphs", params={"goal_id": str(uuid4())}), 404, "resource_not_found")


def test_internal_and_sqlite_busy_are_safe(http, app, monkeypatch):
    def failure(*args, **kwargs):
        raise RuntimeError("private-exception-and-api-key")
    monkeypatch.setattr(app.state.store, "list_goals", failure)
    response = http.get("/api/v1/goals", headers={"Origin": "http://localhost:5173"})
    assert_safe_error(response, 500, "internal_error", "private-exception-and-api-key")
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"

    def busy(*args, **kwargs):
        error = sqlite3.OperationalError("private-sql-and-database-path")
        error.sqlite_errorcode = sqlite3.SQLITE_BUSY
        raise error
    monkeypatch.setattr(app.state.store, "list_goals", busy)
    response = http.get("/api/v1/goals")
    assert assert_safe_error(response, 503, "storage_busy", "private-sql-and-database-path")["retryable"] is True


def test_response_model_failure_is_safe(http, app, monkeypatch):
    monkeypatch.setattr(app.state.store, "list_goals", lambda **kwargs: [{"private-field": "private-value"}])
    assert_safe_error(http.get("/api/v1/goals"), 500, "internal_error", "private-field", "private-value")


def test_lifespan_initializes_and_recovers_once_in_worker_thread(tmp_path, monkeypatch):
    calls = []
    main_thread = threading.get_ident()
    def initialize(self):
        calls.append(("initialize", threading.get_ident()))
    def recover(self):
        calls.append(("recover", threading.get_ident()))
    monkeypatch.setattr(Store, "initialize", initialize)
    monkeypatch.setattr(Store, "recover_interrupted", recover)
    app = create_app(tmp_path / "lazy.sqlite3", generator=generator())
    assert calls == []
    assert not (tmp_path / "lazy.sqlite3").exists()
    with TestClient(app, base_url="http://localhost:8000"):
        assert [call[0] for call in calls] == ["initialize", "recover"]
    assert len(calls) == 2
    assert all(call[1] != main_thread for call in calls)


def test_server_starts_without_loading_model_configuration(tmp_path, monkeypatch):
    def forbidden_settings(*args, **kwargs):
        raise AssertionError("model settings must be lazy")
    monkeypatch.setattr("mini_learngraph.learning.generation.Settings", forbidden_settings)
    app = create_app(tmp_path / "no-model.sqlite3")
    with TestClient(app, base_url="http://localhost:8000") as http:
        assert http.get("/api/v1/goals").json() == {"items": []}
        assert http.get("/api/v1/graphs").json() == {"items": []}
        assert http.get("/openapi.json").status_code == 200


@pytest.mark.parametrize("value", [
    "*", "null", "http://evil.example", "http://localhost:0", "http://localhost:65536",
    "http://user:pass@localhost", "http://localhost/path", "http://localhost?query=1",
    "http://localhost#fragment",
])
def test_settings_reject_nonlocal_or_ambiguous_origins(monkeypatch, value):
    monkeypatch.setenv("MINI_LEARNGRAPH_ALLOWED_ORIGINS", json.dumps([value]))
    with pytest.raises(ValidationError):
        ServerSettings()


def test_settings_origins_json_and_relative_database(monkeypatch):
    monkeypatch.setenv("MINI_LEARNGRAPH_ALLOWED_ORIGINS", '["http://localhost:9000"]')
    monkeypatch.setenv("MINI_LEARNGRAPH_DB_PATH", "data/custom.sqlite3")
    settings = ServerSettings()
    assert settings.allowed_origins == ["http://localhost:9000"]
    assert settings.db_path == PROJECT_ROOT / "data/custom.sqlite3"
    assert ServerSettings(_env_file=None).host == "127.0.0.1"


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.2", "evil.example"])
def test_production_settings_reject_nonloopback_bind(monkeypatch, host):
    monkeypatch.setenv("MINI_LEARNGRAPH_HOST", host)
    with pytest.raises(ValidationError):
        ServerSettings()


def test_production_is_single_worker_no_proxy_headers_or_access_log(monkeypatch, tmp_path):
    monkeypatch.setenv("MINI_LEARNGRAPH_DB_PATH", str(tmp_path / "unused.sqlite3"))
    calls = []
    monkeypatch.setattr(server.uvicorn, "run", lambda app, **kwargs: calls.append(kwargs))
    server.main()
    assert calls == [{"host": "127.0.0.1", "port": 8000, "workers": 1, "proxy_headers": False, "access_log": False}]


async def test_boundary_propagates_cancellation():
    async def cancelled(scope, receive, send):
        raise asyncio.CancelledError()
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}
    async def send(message):
        pytest.fail("Cancelled requests must not be converted to internal errors.")
    boundary = SecurityBoundary(cancelled, [])
    with pytest.raises(asyncio.CancelledError):
        await boundary({"type": "http", "scheme": "http", "method": "GET", "headers": [(b"host", b"localhost")]}, receive, send)
