"""Persistent state, atomic CAS, history and interrupted recovery."""

import asyncio
import sqlite3

import pytest

from mini_learngraph.learning.errors import DomainError
from mini_learngraph.learning.generation import GenerationFailure, Generator
from mini_learngraph.learning.schemas import ClarificationOutput, ConfirmGoal, CreateGoal, EditCandidate, PublishGraph, RevisionRequest, ReviseGraph
from mini_learngraph.learning.service import LearningService
from mini_learngraph.learning.storage import Store
from .learning_fixtures import clarification, confirm_request, generator, graph_request, model_graph


@pytest.fixture
def store(tmp_path):
    result = Store(tmp_path / "learning.sqlite3")
    result.initialize()
    return result


async def asset(store):
    service = LearningService(store, generator(clarification(), model_graph()))
    draft = await service.create_goal(CreateGoal(prompt="学习 Python 最终能独立处理 CSV"))
    goal = await service.confirm_goal(draft["id"], ConfirmGoal.model_validate(confirm_request(draft)))
    graph = await service.create_graph(goal["id"], RevisionRequest(expected_revision=goal["revision"]))
    return service, goal, graph


async def test_complete_persistent_loop_and_versions(store):
    service, goal, graph = await asset(store)
    assert goal["status"] == "confirmed" and goal["graph_id"] is None
    assert goal["assumptions"] == [{"key": "skip:loop_background", "field": None, "value": "按需补循环基础", "reason": "决定是否补基础"}]
    saved_goal = store.get_goal(goal["id"])
    assert saved_goal["status"] == "confirmed" and saved_goal["graph_id"] == graph["id"]
    assert saved_goal["revision"] == goal["revision"] + 1
    request = graph_request(graph)
    request["nodes"][0]["position"] = {"x": 100, "y": 200}
    request["nodes"][0]["target_weight"] = 10
    root = next(node for node in request["nodes"] if node["node_type"] == "root")
    child = next(node for node in request["nodes"] if node["node_type"] != "root")
    request["edges"].append({"source_ref": child["ref"], "target_ref": root["ref"], "relation": "related"})
    written = await service.edit_graph(graph["id"], EditCandidate.model_validate(request))
    updated = written["graph"]
    assert all(node["node_version"] == 1 for node in updated["nodes"])
    assert len(updated["edges"]) == len(graph["edges"]) + 1
    published = await service.publish_graph(graph["id"], PublishGraph(expected_revision=updated["revision"], confirmed=True))
    with pytest.raises(DomainError) as error:
        await service.edit_graph(graph["id"], EditCandidate.model_validate(graph_request(published)))
    assert error.value.code == "invalid_state"
    formal = graph_request(published) | {"confirmed": True, "reason": "更明确地描述循环"}
    changed_id = formal["nodes"][1]["id"]
    formal["nodes"][1]["description"] = "每行逐项处理"
    revised = (await service.revise_graph(graph["id"], ReviseGraph.model_validate(formal)))["graph"]
    assert revised["published_at"] == published["published_at"]
    assert revised["last_revision_reason"] == formal["reason"]
    assert {n["id"]: n["node_version"] for n in revised["nodes"]} == {n["id"]: 2 if n["id"] == changed_id else 1 for n in published["nodes"]}
    reopened = Store(store.path)
    reopened.initialize()
    reopened.recover_interrupted()
    assert reopened.get_graph(graph["id"]) == revised
    assert reopened.get_graph(graph["id"], graph["revision"]) == graph
    with reopened.connection() as db:
        row = db.execute("SELECT before_snapshot,actor,reason FROM graph_revisions WHERE graph_id=? AND revision=?", (graph["id"], revised["revision"])).fetchone()
        assert row[0] is not None and row[1] == "local-user" and row[2] == formal["reason"]


@pytest.mark.parametrize("operation", ["edit", "publish", "revise"])
async def test_concurrent_same_revision_exactly_one_success(store, operation):
    service, _, graph = await asset(store)
    if operation == "revise":
        graph = await service.publish_graph(graph["id"], PublishGraph(expected_revision=graph["revision"], confirmed=True))
    if operation == "edit":
        request = EditCandidate.model_validate(graph_request(graph))
        method = service.edit_graph
    elif operation == "publish":
        request = PublishGraph(expected_revision=graph["revision"], confirmed=True)
        method = service.publish_graph
    else:
        request = ReviseGraph.model_validate(graph_request(graph) | {"confirmed": True, "reason": "复查"})
        method = service.revise_graph
    results = await asyncio.gather(method(graph["id"], request), method(graph["id"], request), return_exceptions=True)
    assert sum(isinstance(result, dict) for result in results) == 1
    failures = [result for result in results if isinstance(result, DomainError)]
    assert len(failures) == 1 and failures[0].code == "revision_conflict"
    assert store.get_graph(graph["id"])["revision"] == graph["revision"] + 1


async def test_invalid_combined_cycle_atomic_and_precisely_located(store):
    service, _, graph = await asset(store)
    request = graph_request(graph)
    root = next(node for node in request["nodes"] if node["node_type"] == "root")
    child = next(node for node in request["nodes"] if node["node_type"] != "root")
    request["edges"].append({"source_ref": child["ref"], "target_ref": root["ref"], "relation": "prerequisite"})
    with pytest.raises(DomainError) as error:
        await service.edit_graph(graph["id"], EditCandidate.model_validate(request))
    payload = error.value.as_dict()
    assert payload["code"] == "graph_invalid"
    cycle = next(entry for entry in payload["details"]["issues"] if entry["code"] == "structural_cycle")
    assert root["ref"] in cycle["node_ids"] and child["ref"] in cycle["node_ids"]
    assert len(request["edges"]) - 1 in cycle["edge_indexes"]
    assert store.get_graph(graph["id"]) == graph
    with pytest.raises(DomainError):
        store.get_graph(graph["id"], graph["revision"] + 1)


async def test_delete_history_retained_and_deleted_id_cannot_reappear(store):
    service, _, graph = await asset(store)
    request = graph_request(graph)
    removed = next(node for node in request["nodes"] if node["node_type"] == "practice")
    request["nodes"] = [node for node in request["nodes"] if node != removed]
    request["edges"] = [edge for edge in request["edges"] if removed["ref"] not in {edge["source_ref"], edge["target_ref"]}]
    current = (await service.edit_graph(graph["id"], EditCandidate.model_validate(request)))["graph"]
    assert removed["id"] not in {node["id"] for node in current["nodes"]}
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM node_versions WHERE node_id=?", (removed["id"],)).fetchone()[0] == 1
    restore = graph_request(graph) | {"expected_revision": current["revision"]}
    with pytest.raises(DomainError) as error:
        await service.edit_graph(graph["id"], EditCandidate.model_validate(restore))
    assert error.value.as_dict()["details"]["issues"][0]["code"] == "foreign_node"
    removed["id"] = None
    removed["ref"] = "new_csv"
    add = graph_request(current)
    add["nodes"].append(removed)
    root = next(node for node in add["nodes"] if node["node_type"] == "root")
    add["edges"].append({"source_ref": root["ref"], "target_ref": removed["ref"], "relation": "contains"})
    result = await service.edit_graph(graph["id"], EditCandidate.model_validate(add))
    assert result["ref_map"][removed["ref"]] not in {node["id"] for node in graph["nodes"]}


async def test_interrupted_states_recovery_and_explicit_retry(store):
    goal = store.create_goal("学习 CSV")
    store.recover_interrupted()
    interrupted = store.get_goal(goal["id"])
    assert interrupted["clarification_failure"]["reason"] == "interrupted"
    service = LearningService(store, generator(clarification(), model_graph()))
    ready = await service.retry_clarify(goal["id"], RevisionRequest(expected_revision=interrupted["revision"]))
    confirmed = await service.confirm_goal(goal["id"], ConfirmGoal.model_validate(confirm_request(ready)))
    graph = store.create_graph(goal["id"], confirmed["revision"])
    store.recover_interrupted()
    failed = store.get_graph(graph["id"])
    assert failed["status"] == "generation_failed" and failed["generation_failure"]["reason"] == "interrupted"
    recovered = await service.retry_graph(graph["id"], RevisionRequest(expected_revision=failed["revision"]))
    assert recovered["status"] == "candidate"
    with pytest.raises(DomainError) as error:
        await service.create_graph(goal["id"], RevisionRequest(expected_revision=store.get_goal(goal["id"])["revision"]))
    assert error.value.code == "graph_already_exists"


async def test_storage_busy_does_not_submit_write(store):
    goal = store.create_goal("CSV")
    with store.connection(write=True):
        with pytest.raises(DomainError) as error:
            store.mutate("goal", goal["id"], goal["revision"], lambda item: item)
    assert error.value.code == "storage_busy"
    assert store.get_goal(goal["id"]) == goal


def test_unknown_schema_or_existing_db_not_modified(tmp_path):
    path = tmp_path / "unknown.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE real_assets(id TEXT)")
        db.execute("INSERT INTO real_assets VALUES ('preserve')")
    with pytest.raises(DomainError):
        Store(path).initialize()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT * FROM real_assets").fetchall() == [("preserve",)]
        db.execute("PRAGMA user_version=2")
    with pytest.raises(DomainError):
        Store(path).initialize()


async def test_no_write_lock_during_model_and_cancel_persists_failure(store):
    entered, release = asyncio.Event(), asyncio.Event()

    class BlockingGenerator(Generator):
        async def clarify(self, data):
            entered.set()
            await release.wait()
            return ClarificationOutput.model_validate(clarification())

    service = LearningService(store, BlockingGenerator())
    task = asyncio.create_task(service.create_goal(CreateGoal(prompt="合成 CSV")))
    await entered.wait()
    pending = store.list_goals()[0]
    assert pending["clarification_status"] == "generating"
    another = await asyncio.to_thread(store.create_goal, "另一个合成目标")
    assert another["revision"] == 1  # A write is possible while the model waits.
    with pytest.raises(DomainError) as error:
        await service.retry_clarify(pending["id"], RevisionRequest(expected_revision=pending["revision"]))
    assert error.value.code == "operation_in_progress"
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    failed = store.get_goal(pending["id"])
    assert failed["clarification_failure"]["reason"] == "interrupted"
    assert failed["clarification_status"] == "generation_failed"


async def test_configuration_failure_persisted_without_model_request(store):
    class MissingConfiguration(Generator):
        async def clarify(self, data):
            raise GenerationFailure("configuration")

    service = LearningService(store, MissingConfiguration())
    with pytest.raises(DomainError) as error:
        await service.create_goal(CreateGoal(prompt="合成 CSV"))
    assert error.value.status == 503 and error.value.code == "model_not_configured"
    payload = error.value.as_dict()
    goal = store.get_goal(payload["details"]["resource_id"])
    assert goal["revision"] == payload["details"]["current_revision"]
    assert goal["clarification_failure"]["reason"] == "configuration"
    assert payload["retryable"] is False
    service.generator = generator(clarification())
    retried = await service.retry_clarify(goal["id"], RevisionRequest(expected_revision=goal["revision"]))
    assert retried["clarification_status"] == "ready"


@pytest.mark.parametrize("kind", ["goal", "graph"])
async def test_busy_final_commit_preserves_generating_queryable_state(store, monkeypatch, kind):
    def busy(*args):
        raise DomainError(503, "storage_busy", "本地存储忙。", retryable=True)

    service = LearningService(store, generator(clarification(), model_graph()))
    if kind == "graph":
        draft = await service.create_goal(CreateGoal(prompt="合成 CSV"))
        confirmed = await service.confirm_goal(draft["id"], ConfirmGoal.model_validate(confirm_request(draft)))
    monkeypatch.setattr(store, "mutate", busy)
    with pytest.raises(DomainError) as error:
        if kind == "goal":
            await service.create_goal(CreateGoal(prompt="合成 CSV"))
        else:
            await service.create_graph(confirmed["id"], RevisionRequest(expected_revision=confirmed["revision"]))
    details = error.value.as_dict()["details"]
    assert error.value.code == "storage_busy" and details["resource_type"] == kind
    saved = store.get_goal(details["resource_id"]) if kind == "goal" else store.get_graph(details["resource_id"])
    assert saved["clarification_status" if kind == "goal" else "status"] == "generating"
    assert saved["revision"] == details["current_revision"]
