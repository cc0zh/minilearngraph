"""Independent B1 risk checks; synthetic provider and temporary assets only."""

import asyncio
import builtins
import json
import runpy
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mini_learngraph.api.app import create_app
from mini_learngraph.api.settings import ServerSettings
from mini_learngraph.learning.errors import DomainError
from mini_learngraph.learning.generation import Generator
from mini_learngraph.learning.schemas import ConfirmGoal, CreateGoal, RevisionRequest
from mini_learngraph.learning.service import LearningService
from mini_learngraph.learning.storage import Store
from mini_learngraph.types import ModelResponse

from .learning_fixtures import clarification, confirm_request, generator, graph_request, model_graph
from .test_learning_api import http_asset


@pytest.fixture
def http(tmp_path):
    app = create_app(tmp_path / "acceptance.sqlite3", generator(clarification(), model_graph(), clarification(), model_graph()))
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        yield client, app.state.store


def counts(store, graph_id):
    with store.connection() as db:
        return tuple(db.execute(f"SELECT count(*) FROM {table} WHERE graph_id=?", (graph_id,)).fetchone()[0]
                     for table in ("graph_revisions", "node_versions"))


@pytest.mark.parametrize("operation", ["edit", "publish", "revise"])
def test_real_http_race_and_exactly_one_snapshot(http, operation):
    client, store = http
    _, graph = http_asset(client)
    url = f"/api/v1/graphs/{graph['id']}"
    if operation == "revise":
        graph = client.post(url + "/publish", json={"expected_revision": graph["revision"], "confirmed": True}).json()
    before = counts(store, graph["id"])
    barrier = threading.Barrier(2)

    def submit(_):
        barrier.wait(timeout=5)
        if operation == "publish":
            return client.post(url + "/publish", json={"expected_revision": graph["revision"], "confirmed": True})
        body = graph_request(graph)
        if operation == "revise":
            return client.post(url + "/revise", json=body | {"confirmed": True, "reason": "并发独立验收"})
        return client.put(url, json=body)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(submit, range(2)))
    assert sorted(response.status_code for response in responses) == [200, 409]
    conflict = next(response.json() for response in responses if response.status_code == 409)
    assert conflict["code"] == "revision_conflict"
    assert conflict["details"]["expected_revision"] == graph["revision"]
    assert conflict["details"]["current_revision"] == graph["revision"] + 1
    current = client.get(url).json()
    assert current["revision"] == graph["revision"] + 1
    assert counts(store, graph["id"]) == (before[0] + 1, before[1])
    assert client.get(url, params={"revision": graph["revision"]}).json() == graph
    assert client.get(url, params={"revision": graph["revision"] + 2}).status_code == 404


@pytest.mark.parametrize("operation", ["edit", "publish", "revise", "create"])
def test_history_failure_rolls_back_all_asset_writes(http, monkeypatch, operation):
    client, store = http
    goal, graph = http_asset(client)
    url = f"/api/v1/graphs/{graph['id']}"
    if operation == "revise":
        graph = client.post(url + "/publish", json={"expected_revision": graph["revision"], "confirmed": True}).json()
    before = counts(store, graph["id"])
    if operation == "create":
        draft = client.post("/api/v1/goals", json={"prompt": "另一个合成目标"}).json()
        goal = client.post(f"/api/v1/goals/{draft['id']}/confirm", json=confirm_request(draft)).json()

    def reject_history(*args):
        raise DomainError(500, "internal_error", "Synthetic history failure.")

    monkeypatch.setattr(store, "_history", reject_history)
    if operation == "create":
        response = client.post(f"/api/v1/goals/{goal['id']}/graphs", json={"expected_revision": goal["revision"]})
        assert client.get(f"/api/v1/goals/{goal['id']}").json() == goal
        assert client.get("/api/v1/graphs", params={"goal_id": goal["id"]}).json() == {"items": []}
    elif operation == "publish":
        response = client.post(url + "/publish", json={"expected_revision": graph["revision"], "confirmed": True})
    else:
        body = graph_request(graph)
        body["nodes"][0]["description"] = "新的合成内容版本"
        if operation == "revise":
            response = client.post(url + "/revise", json=body | {"confirmed": True, "reason": "原子性验收"})
        else:
            response = client.put(url, json=body)
    assert response.status_code == 500 and response.json()["code"] == "internal_error"
    assert client.get(url).json() == graph
    assert counts(store, graph["id"]) == before
    assert client.get(url, params={"revision": graph["revision"] + 1}).status_code == 404


def test_foreign_node_cannot_enter_graph_or_modify_either_history(http):
    client, store = http
    _, first = http_asset(client)
    _, second = http_asset(client)
    before = [counts(store, graph["id"]) for graph in (first, second)]
    body = graph_request(first)
    body["nodes"][0]["id"] = second["nodes"][0]["id"]
    response = client.put(f"/api/v1/graphs/{first['id']}", json=body)
    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "graph_invalid"
    issue = next(issue for issue in payload["details"]["issues"] if issue["code"] == "foreign_node")
    assert issue["path"] == ["body", "nodes", 0, "id"]
    for index, graph in enumerate((first, second)):
        assert client.get(f"/api/v1/graphs/{graph['id']}").json() == graph
        assert counts(store, graph["id"]) == before[index]


@pytest.mark.parametrize("field,new_value", [
    ("label", "新标签"), ("node_type", "assessment"),
    ("description", "新说明"), ("teaching_strategy", "新教学策略"),
])
def test_each_content_field_versions_exactly_one_node_and_preserves_source(http, field, new_value):
    client, store = http
    _, graph = http_asset(client)
    url = f"/api/v1/graphs/{graph['id']}"
    body = graph_request(graph)
    index = next(i for i, node in enumerate(body["nodes"]) if node["node_type"] != "root")
    changed_id = body["nodes"][index]["id"]
    body["nodes"][index][field] = new_value
    response = client.put(url, json=body)
    assert response.status_code == 200
    current = response.json()["graph"]
    assert {node["id"]: node["node_version"] for node in current["nodes"]} == {
        node["id"]: 2 if node["id"] == changed_id else 1 for node in graph["nodes"]
    }
    assert counts(store, graph["id"])[1] == len(graph["nodes"]) + 1
    assert client.get(url, params={"revision": graph["revision"]}).json() == graph
    trimmed = graph_request(current)
    for node in trimmed["nodes"]:
        for key in ("label", "description", "teaching_strategy"):
            node[key] = "  " + node[key] + "  "
    unchanged = client.put(url, json=trimmed).json()["graph"]
    assert unchanged["nodes"] == current["nodes"]
    assert counts(store, graph["id"])[1] == len(graph["nodes"]) + 1


async def test_graph_model_await_has_no_write_transaction_and_cancel_does_not_replay(tmp_path):
    store = Store(tmp_path / "await.sqlite3")
    store.initialize()
    service = LearningService(store, generator(clarification()))
    draft = await service.create_goal(CreateGoal(prompt="合成 CSV"))
    goal = await service.confirm_goal(draft["id"], ConfirmGoal.model_validate(confirm_request(draft)))
    entered = asyncio.Event()

    class BlockingProvider:
        calls = 0

        async def chat(self, messages, tools):
            self.calls += 1
            assert tools == []
            data = json.loads(messages[1].content.removeprefix("BEGIN INPUT DATA\n").removesuffix("\nEND INPUT DATA"))
            assert data["answers"] == goal["answers"] and data["assumptions"] == goal["assumptions"]
            entered.set()
            await asyncio.Event().wait()
            return ModelResponse("", [], "stop")

    provider = BlockingProvider()
    service.generator = Generator(provider=provider)
    task = asyncio.create_task(service.create_graph(goal["id"], RevisionRequest(expected_revision=goal["revision"])))
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        pending = store.list_graphs()[0]
        assert pending["status"] == "generating" and pending["nodes"] == []
        unrelated = await asyncio.to_thread(store.create_goal, "模型等待时仍能提交独立写入")
        assert store.get_goal(unrelated["id"])["revision"] == 1
        with pytest.raises(DomainError) as error:
            await service.retry_graph(pending["id"], RevisionRequest(expected_revision=pending["revision"]))
        assert error.value.code == "operation_in_progress"
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    failed = store.get_graph(pending["id"])
    assert failed["generation_failure"]["reason"] == "interrupted"
    reopened = Store(store.path)
    reopened.initialize()
    reopened.recover_interrupted()
    reopened.recover_interrupted()
    assert reopened.get_graph(pending["id"]) == failed
    assert provider.calls == 1


def test_b1_fixture_never_reads_repository_dotenv(tmp_path, monkeypatch):
    original = builtins.open
    repository_dotenv = Path(__file__).resolve().parents[1] / ".env"
    negative_dotenv = tmp_path / "guard.env"
    negative_dotenv.write_text("MINI_LEARNGRAPH_HOST=127.0.0.1\n", encoding="utf-8")

    def forbid_dotenv(file, *args, **kwargs):
        if isinstance(file, (str, Path)) and Path(file).resolve() in {
            repository_dotenv, negative_dotenv,
        }:
            raise AssertionError("Repository dotenv must not be read by B1 checks.")
        return original(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", forbid_dotenv)
    assert ServerSettings.model_config["env_file"] is None
    app = create_app(tmp_path / "isolation.sqlite3", generator())
    with TestClient(app, base_url="http://localhost:8000") as client:
        assert client.get("/api/v1/goals").json() == {"items": []}
    # An existing synthetic file exercises the guard even on a clean CI checkout.
    monkeypatch.setitem(ServerSettings.model_config, "env_file", negative_dotenv)
    with pytest.raises(AssertionError, match="Repository dotenv must not be read"):
        ServerSettings()  # Negative control: stopped before any dotenv contents are read.
    monkeypatch.setenv("MINI_LEARNGRAPH_HOST", "invalid-host")
    monkeypatch.setattr(sys, "argv", ["api_fixture.py", "--db", str(tmp_path / "browser.sqlite3")])
    observed = []

    def fake_server(app, **kwargs):
        assert app.state.store.path == tmp_path / "browser.sqlite3"
        assert app.state.server_settings.host == "127.0.0.1"
        assert ServerSettings.model_config["env_file"] is None
        observed.append(kwargs)

    monkeypatch.setattr("uvicorn.run", fake_server)
    runpy.run_path("web/tests/api_fixture.py", run_name="__main__")
    assert len(observed) == 1 and observed[0]["access_log"] is False
