"""B1 use cases: snapshot -> model I/O without a transaction -> checked commit."""

import asyncio
from typing import Any

from .errors import DomainError
from .generation import GenerationFailure, Generator
from .schemas import (
    ConfirmGoal,
    CreateGoal,
    EditCandidate,
    GraphInput,
    PublishGraph,
    ReviseGraph,
    RevisionRequest,
)
from .storage import Snapshot, Store, failure, new_id, now
from .validation import validate_graph


def state_guard(kind: str, snapshot: Snapshot, expected: str) -> None:
    key = "clarification_status" if kind == "goal" else "status"
    if snapshot[key] == "generating":
        code = "operation_in_progress"
    else:
        code = "invalid_state"
    if snapshot[key] != expected or (kind == "goal" and snapshot["status"] != "draft"):
        raise DomainError(
            409, code, "当前资源状态不允许此操作。",
            resource_type=kind, resource_id=snapshot["id"], current_revision=snapshot["revision"],
        )


def issue(path: list[str | int], code: str, *, node_ids: list[str] | None = None) -> Snapshot:
    return {
        "path": path, "code": code, "message": "输入未通过校验。",
        "node_ids": node_ids or [], "edge_indexes": [],
    }


class LearningService:
    def __init__(self, store: Store, generator: Generator | None = None) -> None:
        self.store = store
        self.generator = generator if generator is not None else Generator()

    async def _mutate(self, kind: str, snapshot: Snapshot, transform: Any) -> Snapshot:
        try:
            return await asyncio.to_thread(self.store.mutate, kind, snapshot["id"], snapshot["revision"], transform)
        except DomainError as error:
            if error.code == "storage_busy":
                raise DomainError(
                    503, "storage_busy", "本地存储忙，请查询资源状态后显式重试。",
                    resource_type=kind, resource_id=snapshot["id"],
                    expected_revision=snapshot["revision"], current_revision=snapshot["revision"], retryable=True,
                ) from None
            raise

    async def create_goal(self, request: CreateGoal) -> Snapshot:
        goal = await asyncio.to_thread(self.store.create_goal, request.prompt)
        return await self._generate("goal", goal)

    async def retry_clarify(self, goal_id: str, request: RevisionRequest) -> Snapshot:
        def start(goal: Snapshot) -> Snapshot:
            state_guard("goal", goal, "generation_failed")
            goal.update(clarification_status="generating", clarification_failure=None)
            return goal

        goal = await asyncio.to_thread(self.store.mutate, "goal", goal_id, request.expected_revision, start)
        return await self._generate("goal", goal)

    async def create_graph(self, goal_id: str, request: RevisionRequest) -> Snapshot:
        graph = await asyncio.to_thread(self.store.create_graph, goal_id, request.expected_revision)
        return await self._generate("graph", graph)

    async def retry_graph(self, graph_id: str, request: RevisionRequest) -> Snapshot:
        def start(graph: Snapshot) -> Snapshot:
            state_guard("graph", graph, "generation_failed")
            graph.update(status="generating", generation_failure=None)
            return graph

        graph = await asyncio.to_thread(self.store.mutate, "graph", graph_id, request.expected_revision, start)
        return await self._generate("graph", graph)

    async def _failed(self, kind: str, snapshot: Snapshot, reason: str) -> Snapshot:
        def save(current: Snapshot) -> Snapshot:
            state_guard(kind, current, "generating")
            if kind == "goal":
                current.update(clarification_status="generation_failed", clarification_failure=failure(reason))
            else:
                current.update(status="generation_failed", generation_failure=failure(reason), nodes=[], edges=[])
            return current

        return await self._mutate(kind, snapshot, save)

    async def _generate(self, kind: str, snapshot: Snapshot) -> Snapshot:
        try:
            if kind == "goal":
                result = await self.generator.clarify({"raw_prompt": snapshot["raw_prompt"]})
                output = result.model_dump(mode="json")

                def ready(goal: Snapshot) -> Snapshot:
                    state_guard("goal", goal, "generating")
                    goal.update(output)
                    goal.update(clarification_status="ready", clarification_failure=None, assumptions=output["suggested_assumptions"])
                    return goal

                return await self._mutate(kind, snapshot, ready)
            goal = await asyncio.to_thread(self.store.get_goal, snapshot["goal_id"])
            result_graph = await self.generator.graph(goal)
            output_graph = result_graph.model_dump(mode="json")
            graph_input = GraphInput.model_validate({
                "nodes": [dict(node, id=None, position=None) for node in output_graph["nodes"]],
                "edges": output_graph["edges"],
            })

            def candidate(graph: Snapshot) -> Snapshot:
                state_guard("graph", graph, "generating")
                updated, _ = self._replace(graph, graph_input)
                updated.update(status="candidate", generation_failure=None)
                return updated

            return await self._mutate(kind, snapshot, candidate)
        except GenerationFailure as error:
            failed = await self._failed(kind, snapshot, error.reason)
            status = {"configuration": 503, "timeout": 504}.get(error.reason, 502)
            summary = failure(error.reason)
            raise DomainError(
                status, summary["code"], summary["message"],
                resource_type=kind, resource_id=failed["id"], current_revision=failed["revision"],
                failure_reason=error.reason, retryable=summary["retryable"],
            ) from None
        except asyncio.CancelledError:
            # Best effort only. Recovery on single-process restart covers a crash.
            try:
                await asyncio.shield(self._failed(kind, snapshot, "interrupted"))
            except DomainError:
                pass
            raise

    async def confirm_goal(self, goal_id: str, request: ConfirmGoal) -> Snapshot:
        def confirm(goal: Snapshot) -> Snapshot:
            state_guard("goal", goal, "ready")
            catalog = {question["key"]: question for question in goal["questions"]}
            answers = [answer.model_dump(mode="json") for answer in request.answers]
            seen: set[str] = set()
            issues: list[Snapshot] = []
            skips: list[Snapshot] = []
            for index, answer in enumerate(answers):
                key = answer["key"]
                path: list[str | int] = ["body", "answers", index]
                if key in seen:
                    issues.append(issue(path + ["key"], "duplicate_question"))
                seen.add(key)
                if key not in catalog:
                    issues.append(issue(path + ["key"], "unknown_question"))
                    continue
                question = catalog[key]
                kind, value = answer["kind"], answer["value"]
                if (kind == "choice" and value not in {option["id"] for option in question["options"]}) or (
                    kind == "custom" and (not question["allow_custom"] or value is None)
                ) or (kind == "skip" and (not question["allow_skip"] or value is not None)):
                    issues.append(issue(path + ["value"], "invalid_answer"))
                elif kind == "skip":
                    skips.append({
                        "key": f"skip:{key}", "field": None,
                        "value": question["default_assumption"], "reason": question["reason"],
                    })
            for key in catalog.keys() - seen:
                issues.append(issue(["body", "answers"], "required"))
            suggested = {entry["key"]: entry for entry in goal["suggested_assumptions"]}
            accepted = request.accepted_suggested_assumption_keys
            if len(set(accepted)) != len(accepted) or not set(accepted) <= suggested.keys():
                issues.append(issue(["body", "accepted_suggested_assumption_keys"], "constraint"))
            users = [entry.model_dump(mode="json") for entry in request.user_assumptions]
            if len({entry["key"] for entry in users}) != len(users) or any(not entry["key"].startswith("user:") for entry in users):
                issues.append(issue(["body", "user_assumptions"], "constraint"))
            if issues:
                raise DomainError(
                    422, "validation_failed", "目标确认输入未通过校验。", resource_type="goal",
                    resource_id=goal_id, expected_revision=request.expected_revision,
                    current_revision=goal["revision"], issues=issues,
                )
            goal.update(
                values=request.values.model_dump(mode="json"), answers=answers,
                accepted_suggested_assumption_keys=accepted,
                assumptions=[suggested[key] for key in accepted] + skips + users,
                status="confirmed", confirmed_at=now(),
            )
            return goal

        return await asyncio.to_thread(self.store.mutate, "goal", goal_id, request.expected_revision, confirm)

    @staticmethod
    def _replace(graph: Snapshot, request: GraphInput) -> tuple[Snapshot, dict[str, str]]:
        old_nodes = {node["id"]: node for node in graph["nodes"]}
        issues: list[Any] = []
        seen_ids: set[str] = set()
        for index, node in enumerate(request.nodes):
            if node.id is not None:
                if node.id not in old_nodes:
                    issues.append(issue(["body", "nodes", index, "id"], "foreign_node", node_ids=[node.id, node.ref]))
                if node.id in seen_ids:
                    issues.append(issue(["body", "nodes", index, "id"], "duplicate_node", node_ids=[node.id, node.ref]))
                seen_ids.add(node.id)
        issues.extend(validate_graph(request.nodes, request.edges, scope="body"))
        if issues:
            raise DomainError(
                422, "graph_invalid", "图谱结构未通过校验。", resource_type="graph",
                resource_id=graph["id"], current_revision=graph["revision"],
                expected_revision=graph["revision"], issues=issues,
            )
        ref_map: dict[str, str] = {}
        nodes: list[Snapshot] = []
        timestamp = now()
        content_keys = ("label", "node_type", "description", "teaching_strategy")
        for node in request.nodes:
            data = node.model_dump(mode="json")
            data.pop("ref")
            node_id = node.id or new_id()
            data["id"] = node_id
            old = old_nodes.get(node_id)
            data["created_at"] = old["created_at"] if old else timestamp
            changed = old is not None and any(old[key] != data[key] for key in content_keys)
            data["node_version"] = old["node_version"] + int(changed) if old else 1
            nodes.append(data)
            ref_map[node.ref] = node_id
        edges = [
            {"source": ref_map[edge.source_ref], "target": ref_map[edge.target_ref], "relation": edge.relation}
            for edge in request.edges
        ]
        graph.update(
            nodes=sorted(nodes, key=lambda node: (node["created_at"], node["id"])),
            edges=sorted(edges, key=lambda edge: (edge["source"], edge["target"], edge["relation"])),
        )
        return graph, ref_map

    async def edit_graph(self, graph_id: str, request: EditCandidate) -> Snapshot:
        return await self._edit(graph_id, request, formal=False)

    async def revise_graph(self, graph_id: str, request: ReviseGraph) -> Snapshot:
        return await self._edit(graph_id, request, formal=True)

    async def _edit(self, graph_id: str, request: EditCandidate | ReviseGraph, *, formal: bool) -> Snapshot:
        ref_map: dict[str, str] = {}

        def save(graph: Snapshot) -> Snapshot:
            state_guard("graph", graph, "published" if formal else "candidate")
            updated, mapping = self._replace(graph, request)
            ref_map.update(mapping)
            if isinstance(request, ReviseGraph):
                updated["last_revision_reason"] = request.reason
            return updated

        graph = await asyncio.to_thread(self.store.mutate, "graph", graph_id, request.expected_revision, save)
        return {"graph": graph, "ref_map": ref_map}

    async def publish_graph(self, graph_id: str, request: PublishGraph) -> Snapshot:
        def publish(graph: Snapshot) -> Snapshot:
            state_guard("graph", graph, "candidate")
            issues = validate_graph(graph["nodes"], graph["edges"], scope="graph")
            if issues:
                raise DomainError(
                    422, "graph_invalid", "图谱结构未通过校验。", resource_type="graph",
                    resource_id=graph_id, current_revision=graph["revision"],
                    expected_revision=request.expected_revision, issues=issues,
                )
            graph.update(status="published", published_at=now())
            return graph

        return await asyncio.to_thread(self.store.mutate, "graph", graph_id, request.expected_revision, publish)
