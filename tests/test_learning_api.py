"""Frozen B1 route and state contract exercised through real HTTP boundaries."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from mini_learngraph.api.app import create_app
from mini_learngraph.learning.generation import GenerationFailure, Generator
from mini_learngraph.provider import ModelError
from .learning_fixtures import clarification, confirm_request, generator, graph_request, model_graph


ROUTES = {
    ("GET", "/api/v1/goals"), ("POST", "/api/v1/goals"),
    ("GET", "/api/v1/goals/{goal_id}"), ("POST", "/api/v1/goals/{goal_id}/clarify"),
    ("POST", "/api/v1/goals/{goal_id}/confirm"), ("GET", "/api/v1/graphs"),
    ("POST", "/api/v1/goals/{goal_id}/graphs"), ("GET", "/api/v1/graphs/{graph_id}"),
    ("POST", "/api/v1/graphs/{graph_id}/generate"), ("PUT", "/api/v1/graphs/{graph_id}"),
    ("POST", "/api/v1/graphs/{graph_id}/publish"), ("POST", "/api/v1/graphs/{graph_id}/revise"),
}


def client(tmp_path, *outputs):
    return TestClient(create_app(db_path=tmp_path / "api.sqlite3", generator=generator(*outputs)), base_url="http://127.0.0.1:8000")


def http_asset(http):
    response = http.post("/api/v1/goals", json={"prompt": "学习 Python 最终能独立处理 CSV"})
    assert response.status_code == 201, response.text
    goal = response.json()
    response = http.post(f"/api/v1/goals/{goal['id']}/confirm", json=confirm_request(goal))
    assert response.status_code == 200, response.text
    goal = response.json()
    response = http.post(f"/api/v1/goals/{goal['id']}/graphs", json={"expected_revision": goal["revision"]})
    assert response.status_code == 201, response.text
    return goal, response.json()


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    payload = response.json()
    assert set(payload) == {"code", "message", "details", "retryable"}
    assert payload["code"] == code
    assert set(payload["details"]) == {"resource_type", "resource_id", "expected_revision", "current_revision", "failure_reason", "issues"}
    return payload


def test_frozen_12_routes_and_openapi_error_models(tmp_path):
    with client(tmp_path) as http:
        schema = http.get("/openapi.json").json()
        actual = {(method.upper(), path) for path, value in schema["paths"].items() for method in value if method in {"get", "post", "put", "patch", "delete"}}
        assert actual == ROUTES
        assert schema["components"]["schemas"]["CreateGoal"]["additionalProperties"] is False
        for path, methods in schema["paths"].items():
            for operation in methods.values():
                assert "422" in operation["responses"]
                assert operation["responses"]["422"]["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/ApiError"}


def test_all_read_edit_publish_revise_routes(tmp_path):
    with client(tmp_path, clarification(), model_graph()) as http:
        goal, graph = http_asset(http)
        assert http.get("/api/v1/goals", params={"status": "confirmed"}).json()["items"][0]["id"] == goal["id"]
        current_goal = http.get(f"/api/v1/goals/{goal['id']}").json()
        assert current_goal["graph_id"] == graph["id"] and current_goal["status"] == "confirmed"
        assert http.get("/api/v1/graphs", params={"goal_id": goal["id"], "status": "candidate"}).json()["items"] == [graph]
        graph_url = f"/api/v1/graphs/{graph['id']}"
        edit = http.put(graph_url, json=graph_request(graph))
        assert edit.status_code == 200
        graph = edit.json()["graph"]
        published = http.post(graph_url + "/publish", json={"expected_revision": graph["revision"], "confirmed": True})
        assert published.status_code == 200
        graph = published.json()
        revision = http.post(graph_url + "/revise", json=graph_request(graph) | {"confirmed": True, "reason": "范围复查"})
        assert revision.status_code == 200
        revised = revision.json()["graph"]
        assert revised["status"] == "published"
        assert http.get(graph_url).json() == revised
        assert http.get(graph_url, params={"revision": graph["revision"]}).json() == graph
        assert_error(http.put(graph_url, json=graph_request(revised)), 409, "invalid_state")
        assert_error(http.post(graph_url + "/generate", json={"expected_revision": revised["revision"]}), 409, "invalid_state")
        assert_error(http.get(graph_url, params={"revision": 999}), 404, "resource_not_found")


@pytest.mark.parametrize("output, status, reason", [
    ("", 502, "invalid_output"), ("{", 502, "invalid_output"),
    ("```json\n{}\n```", 502, "invalid_output"), ({}, 502, "invalid_output"),
    (ModelError("Model request timed out."), 504, "timeout"),
    (ModelError("secret upstream trace"), 502, "transport"),
], ids=["empty", "truncated-json", "fenced-json", "invalid-schema", "timeout", "transport"])
def test_clarification_failed_persistent_get_retry(tmp_path, output, status, reason):
    with client(tmp_path, output, clarification()) as http:
        failed = http.post("/api/v1/goals", json={"prompt": "CSV 合成"})
        payload = assert_error(failed, status, "generation_failed")
        details = payload["details"]
        assert details["failure_reason"] == reason
        goal = http.get(f"/api/v1/goals/{details['resource_id']}").json()
        assert goal["status"] == "draft" and goal["clarification_status"] == "generation_failed"
        assert goal["revision"] == details["current_revision"]
        assert goal["suggested_values"] is None and goal["questions"] == []
        assert "secret" not in failed.text
        retry = http.post(f"/api/v1/goals/{goal['id']}/clarify", json={"expected_revision": goal["revision"]})
        assert retry.status_code == 200
        assert retry.json()["clarification_status"] == "ready"


@pytest.mark.parametrize("case,status,reason", [
    ("empty", 502, "invalid_output"), ("truncated-json", 502, "invalid_output"),
    ("foreign-ref", 502, "invalid_output"), ("cycle", 502, "invalid_output"),
    ("timeout", 504, "timeout"), ("transport", 502, "transport"),
])
def test_graph_failed_state_and_explicit_retry(tmp_path, case, status, reason):
    if case == "empty":
        invalid = ""
    elif case == "truncated-json":
        invalid = '{"nodes":'
    elif case in {"timeout", "transport"}:
        invalid = ModelError("Model request timed out." if case == "timeout" else "secret upstream trace")
    else:
        invalid = model_graph()
        if case == "foreign-ref":
            invalid["edges"][0]["target_ref"] = "foreign"
        else:
            invalid["edges"].append({"source_ref": "loop", "target_ref": "root", "relation": "prerequisite"})
    with client(tmp_path, clarification(), invalid, model_graph()) as http:
        draft = http.post("/api/v1/goals", json={"prompt": "CSV"}).json()
        confirmed = http.post(f"/api/v1/goals/{draft['id']}/confirm", json=confirm_request(draft)).json()
        response = http.post(f"/api/v1/goals/{draft['id']}/graphs", json={"expected_revision": confirmed["revision"]})
        details = assert_error(response, status, "generation_failed")["details"]
        assert details["resource_type"] == "graph" and details["failure_reason"] == reason
        assert "secret upstream trace" not in response.text
        graph_url = f"/api/v1/graphs/{details['resource_id']}"
        graph = http.get(graph_url).json()
        assert graph["status"] == "generation_failed" and graph["nodes"] == [] and graph["edges"] == []
        assert http.get(f"/api/v1/goals/{draft['id']}").json()["status"] == "confirmed"
        retry = http.post(graph_url + "/generate", json={"expected_revision": graph["revision"]})
        assert retry.status_code == 200 and retry.json()["status"] == "candidate"


def test_dynamic_catalog_complete_answers_and_all_assumption_sources_persist(tmp_path):
    output = clarification()
    template = output["questions"][0]
    output["questions"] = [dict(template, key=key) for key in ("csv_choice", "schedule_custom", "scope_skip")]
    with client(tmp_path, output) as http:
        goal = http.post("/api/v1/goals", json={"prompt": "合成动态 CSV 目标"}).json()
        request = confirm_request(goal)
        request["answers"] = [
            {"key": "csv_choice", "kind": "choice", "value": "new"},
            {"key": "schedule_custom", "kind": "custom", "value": "暂未指定时间"},
            {"key": "scope_skip", "kind": "skip", "value": None},
        ]
        request["accepted_suggested_assumption_keys"] = ["suggested:scope"]
        manual = {"key": "user:format", "field": None, "value": "只用合成 CSV", "reason": "不上传资料"}
        request["user_assumptions"] = [manual]
        url = f"/api/v1/goals/{goal['id']}"
        response = http.post(url + "/confirm", json=request)
        assert response.status_code == 200, response.text
        confirmed = response.json()
        assert confirmed["questions"] == output["questions"]
        assert confirmed["answers"] == request["answers"]
        assert confirmed["assumptions"] == [output["suggested_assumptions"][0], {
            "key": "skip:scope_skip", "field": None,
            "value": template["default_assumption"], "reason": template["reason"],
        }, manual]
    with client(tmp_path) as reopened:
        assert reopened.get(url).json() == confirmed


@pytest.mark.parametrize("kind", ["custom", "skip"])
def test_answer_capability_is_checked_against_saved_catalog(tmp_path, kind):
    output = clarification()
    output["questions"][0][f"allow_{kind}"] = False
    if kind == "skip":
        output["questions"][0]["default_assumption"] = None
    with client(tmp_path, output) as http:
        goal = http.post("/api/v1/goals", json={"prompt": "CSV"}).json()
        request = confirm_request(goal, kind=kind, value="synthetic-answer" if kind == "custom" else None)
        response = http.post(f"/api/v1/goals/{goal['id']}/confirm", json=request)
        payload = assert_error(response, 422, "validation_failed")
        assert "invalid_answer" in {entry["code"] for entry in payload["details"]["issues"]}
        assert http.get(f"/api/v1/goals/{goal['id']}").json() == goal


@pytest.mark.parametrize("kind", ["goal", "graph"])
def test_missing_configuration_http_keeps_failed_asset_and_explicit_retry(tmp_path, kind):
    class MissingConfiguration(Generator):
        async def _generate(self, data, schema, task):
            raise GenerationFailure("configuration")

    app = create_app(tmp_path / "missing.sqlite3", generator(clarification()))
    with TestClient(app, base_url="http://localhost:8000") as http:
        if kind == "graph":
            goal = http.post("/api/v1/goals", json={"prompt": "合成 CSV"}).json()
            goal = http.post(f"/api/v1/goals/{goal['id']}/confirm", json=confirm_request(goal)).json()
            url, body = f"/api/v1/goals/{goal['id']}/graphs", {"expected_revision": goal["revision"]}
        else:
            url, body = "/api/v1/goals", {"prompt": "合成 CSV"}
        app.state.service.generator = MissingConfiguration()
        response = http.post(url, json=body)
        payload = assert_error(response, 503, "model_not_configured")
        assert payload["retryable"] is False and payload["details"]["failure_reason"] == "configuration"
        assert payload["details"]["resource_type"] == kind
        saved_url = f"/api/v1/{kind}s/{payload['details']['resource_id']}"
        saved = http.get(saved_url).json()
        assert saved["revision"] == payload["details"]["current_revision"]
        assert saved["clarification_status" if kind == "goal" else "status"] == "generation_failed"
        app.state.service.generator = generator(clarification() if kind == "goal" else model_graph())
        retry = http.post(saved_url + ("/clarify" if kind == "goal" else "/generate"), json={"expected_revision": saved["revision"]})
        assert retry.status_code == 200
        assert retry.json()["clarification_status" if kind == "goal" else "status"] == ("ready" if kind == "goal" else "candidate")


@pytest.mark.parametrize("kind,value", [("choice", "unknown"), ("skip", "not-null"), ("custom", None)])
def test_catalog_answers_validated_and_no_confirmation_on_failure(tmp_path, kind, value):
    with client(tmp_path, clarification()) as http:
        goal = http.post("/api/v1/goals", json={"prompt": "CSV"}).json()
        request = confirm_request(goal, kind=kind, value=value)
        response = http.post(f"/api/v1/goals/{goal['id']}/confirm", json=request)
        assert_error(response, 422, "validation_failed")
        assert http.get(f"/api/v1/goals/{goal['id']}").json() == goal


def test_http_concurrency_conflict_has_current_revision(tmp_path):
    with client(tmp_path, clarification(), model_graph()) as http:
        _, graph = http_asset(http)
        graph_url = f"/api/v1/graphs/{graph['id']}"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: http.put(graph_url, json=graph_request(graph)), range(2)))
        assert sorted(response.status_code for response in results) == [200, 409]
        conflict = assert_error(next(response for response in results if response.status_code == 409), 409, "revision_conflict")
        assert conflict["details"]["expected_revision"] == graph["revision"]
        assert conflict["details"]["current_revision"] == graph["revision"] + 1
