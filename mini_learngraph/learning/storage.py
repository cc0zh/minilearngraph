"""SQLite snapshots and short, revision-checked transactions.

Connections are local to each operation/thread. No transaction spans model I/O.
Schema v1 initializes new databases only; unknown versions require an explicit
backup/migration decision rather than an implicit destructive upgrade.
"""

import json
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .errors import DomainError

Snapshot = dict[str, Any]


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def new_id() -> str:
    return str(uuid4())


def failure(reason: str) -> Snapshot:
    messages = {
        "configuration": "模型配置不可用。",
        "timeout": "模型请求超时。",
        "transport": "模型请求失败。",
        "invalid_output": "模型输出未通过严格校验。",
        "interrupted": "生成已中断，请显式重试。",
    }
    return {
        "code": "model_not_configured" if reason == "configuration" else "generation_failed",
        "message": messages[reason],
        "reason": reason,
        "retryable": reason != "configuration",
    }


def check_revision(kind: str, old: Snapshot, expected: int) -> None:
    if old["revision"] != expected:
        raise DomainError(
            409, "revision_conflict", "资源已更新，请读取最新修订后重新确认。",
            resource_type=kind, resource_id=old["id"], expected_revision=expected,
            current_revision=old["revision"],
        )


class Store:
    def __init__(self, path: str | Path, *, busy_timeout_ms: int = 1000) -> None:
        self.path = Path(path)
        self.busy_timeout_ms = busy_timeout_ms

    @contextmanager
    def connection(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(self.path, timeout=self.busy_timeout_ms / 1000)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            if write:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            if write:
                connection.commit()
        except sqlite3.OperationalError as error:
            if "locked" in str(error).lower() or "busy" in str(error).lower():
                raise DomainError(503, "storage_busy", "本地存储忙，请查询最新状态后重试。", retryable=True) from None
            raise DomainError(500, "internal_error", "本地存储操作失败。") from None
        except sqlite3.DatabaseError:
            raise DomainError(500, "internal_error", "本地存储操作失败。") from None
        finally:
            if connection is not None:
                connection.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection(write=True) as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in {0, 1}:
                raise DomainError(500, "internal_error", "数据库版本不受支持；请先备份并确认迁移。")
            if version == 0:
                # A pre-existing unrelated DB must never be repurposed silently.
                if db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
                    raise DomainError(500, "internal_error", "现有数据库需要显式迁移。")
                statements = [
                    "CREATE TABLE goals (id TEXT PRIMARY KEY, learner_id TEXT NOT NULL CHECK(learner_id='local-user'), revision INTEGER NOT NULL CHECK(revision>0), snapshot TEXT NOT NULL)",
                    "CREATE TABLE graphs (id TEXT PRIMARY KEY, goal_id TEXT NOT NULL UNIQUE REFERENCES goals(id), learner_id TEXT NOT NULL CHECK(learner_id='local-user'), revision INTEGER NOT NULL CHECK(revision>0), snapshot TEXT NOT NULL)",
                    "CREATE TABLE graph_revisions (graph_id TEXT NOT NULL REFERENCES graphs(id), revision INTEGER NOT NULL CHECK(revision>0), before_snapshot TEXT, snapshot TEXT NOT NULL, actor TEXT NOT NULL CHECK(actor='local-user'), reason TEXT, created_at TEXT NOT NULL, PRIMARY KEY(graph_id,revision))",
                    "CREATE TABLE node_versions (graph_id TEXT NOT NULL REFERENCES graphs(id), node_id TEXT NOT NULL, node_version INTEGER NOT NULL CHECK(node_version>0), snapshot TEXT NOT NULL, PRIMARY KEY(node_id,node_version))",
                ]
                for statement in statements:
                    db.execute(statement)
                db.execute("PRAGMA user_version=1")

    @staticmethod
    def _get(db: sqlite3.Connection, kind: str, resource_id: str) -> Snapshot:
        table = "goals" if kind == "goal" else "graphs"
        row = db.execute(f"SELECT snapshot FROM {table} WHERE id=? AND learner_id=?", (resource_id, "local-user")).fetchone()
        if row is None:
            raise DomainError(404, "resource_not_found", "资源不存在。")
        return json.loads(row[0])

    def get_goal(self, resource_id: str) -> Snapshot:
        with self.connection() as db:
            return self._get(db, "goal", resource_id)

    def get_graph(self, resource_id: str, revision: int | None = None) -> Snapshot:
        with self.connection() as db:
            current = self._get(db, "graph", resource_id)
            if revision is None:
                return current
            if revision > 9223372036854775807:
                raise DomainError(404, "resource_not_found", "历史修订不存在。")
            row = db.execute("SELECT snapshot FROM graph_revisions WHERE graph_id=? AND revision=?", (resource_id, revision)).fetchone()
            if row is None:
                raise DomainError(404, "resource_not_found", "历史修订不存在。")
            return json.loads(row[0])

    def list_goals(self, status: str | None = None) -> list[Snapshot]:
        with self.connection() as db:
            rows = db.execute("SELECT snapshot FROM goals WHERE learner_id=?", ("local-user",)).fetchall()
            items = [json.loads(row[0]) for row in rows]
        return self._sorted([item for item in items if status is None or item["status"] == status])

    def list_graphs(self, goal_id: str | None = None, status: str | None = None) -> list[Snapshot]:
        with self.connection() as db:
            if goal_id is not None:
                self._get(db, "goal", goal_id)
            rows = db.execute("SELECT snapshot FROM graphs WHERE learner_id=?", ("local-user",)).fetchall()
            items = [json.loads(row[0]) for row in rows]
        return self._sorted([
            item for item in items
            if (goal_id is None or item["goal_id"] == goal_id) and (status is None or item["status"] == status)
        ])

    @staticmethod
    def _sorted(items: list[Snapshot]) -> list[Snapshot]:
        return sorted(sorted(items, key=lambda item: item["id"]), key=lambda item: item["created_at"], reverse=True)

    def create_goal(self, prompt: str) -> Snapshot:
        timestamp = now()
        goal: Snapshot = {
            "id": new_id(), "learner_id": "local-user", "raw_prompt": prompt,
            "status": "draft", "revision": 1, "clarification_status": "generating",
            "suggested_values": None, "values": None, "questions": [], "answers": [],
            "accepted_suggested_assumption_keys": [], "suggested_assumptions": [],
            "assumptions": [], "clarification_failure": None, "graph_id": None,
            "created_at": timestamp, "updated_at": timestamp, "confirmed_at": None,
        }
        with self.connection(write=True) as db:
            db.execute("INSERT INTO goals VALUES (?,?,?,?)", (goal["id"], "local-user", 1, self._json(goal)))
        return goal

    @staticmethod
    def _json(snapshot: Snapshot) -> str:
        return json.dumps(snapshot, ensure_ascii=False, allow_nan=False, separators=(",", ":"))

    def _save(self, db: sqlite3.Connection, kind: str, old: Snapshot, updated: Snapshot) -> None:
        updated["revision"] = old["revision"] + 1
        updated["updated_at"] = now()
        table = "goals" if kind == "goal" else "graphs"
        result = db.execute(
            f"UPDATE {table} SET revision=?, snapshot=? WHERE id=? AND revision=? AND learner_id=?",
            (updated["revision"], self._json(updated), old["id"], old["revision"], "local-user"),
        )
        if result.rowcount != 1:
            check_revision(kind, self._get(db, kind, old["id"]), old["revision"])
            raise DomainError(409, "revision_conflict", "资源已更新。")
        if kind == "graph":
            self._history(db, updated, old)

    def _history(self, db: sqlite3.Connection, graph: Snapshot, old: Snapshot | None) -> None:
        db.execute(
            "INSERT INTO graph_revisions VALUES (?,?,?,?,?,?,?)",
            (graph["id"], graph["revision"], self._json(old) if old else None, self._json(graph),
             "local-user", graph["last_revision_reason"], graph["updated_at"]),
        )
        for node in graph["nodes"]:
            existing = db.execute("SELECT graph_id FROM node_versions WHERE node_id=? AND node_version=?", (node["id"], node["node_version"])).fetchone()
            if existing is None:
                db.execute("INSERT INTO node_versions VALUES (?,?,?,?)", (graph["id"], node["id"], node["node_version"], self._json(node)))
            elif existing[0] != graph["id"]:
                raise DomainError(500, "internal_error", "节点历史归属冲突。")

    def mutate(self, kind: str, resource_id: str, expected_revision: int, transform: Callable[[Snapshot], Snapshot]) -> Snapshot:
        with self.connection(write=True) as db:
            old = self._get(db, kind, resource_id)
            check_revision(kind, old, expected_revision)
            updated = transform(json.loads(self._json(old)))
            self._save(db, kind, old, updated)
            return updated

    def create_graph(self, goal_id: str, expected_revision: int) -> Snapshot:
        with self.connection(write=True) as db:
            goal = self._get(db, "goal", goal_id)
            check_revision("goal", goal, expected_revision)
            if goal["status"] != "confirmed":
                raise DomainError(409, "invalid_state", "请先确认学习目标。", resource_type="goal", resource_id=goal_id, current_revision=goal["revision"])
            if goal["graph_id"] is not None:
                graph = self._get(db, "graph", goal["graph_id"])
                raise DomainError(409, "graph_already_exists", "该目标已有图谱。", resource_type="graph", resource_id=graph["id"], current_revision=graph["revision"])
            timestamp = now()
            graph: Snapshot = {
                "id": new_id(), "goal_id": goal_id, "status": "generating", "revision": 1,
                "nodes": [], "edges": [], "generation_failure": None,
                "created_at": timestamp, "updated_at": timestamp, "published_at": None,
                "last_revision_reason": None,
            }
            db.execute("INSERT INTO graphs VALUES (?,?,?,?,?)", (graph["id"], goal_id, "local-user", 1, self._json(graph)))
            self._history(db, graph, None)
            updated_goal = dict(goal, graph_id=graph["id"])
            self._save(db, "goal", goal, updated_goal)
            return graph

    def recover_interrupted(self) -> None:
        with self.connection(write=True) as db:
            for kind, table, state_key, error_key in [
                ("goal", "goals", "clarification_status", "clarification_failure"),
                ("graph", "graphs", "status", "generation_failure"),
            ]:
                rows = db.execute(f"SELECT snapshot FROM {table} WHERE learner_id=?", ("local-user",)).fetchall()
                for row in rows:
                    old = json.loads(row[0])
                    if old[state_key] == "generating":
                        updated = dict(old)
                        updated[state_key] = "generation_failed"
                        updated[error_key] = failure("interrupted")
                        self._save(db, kind, old, updated)
