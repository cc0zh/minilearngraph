"""Synthetic B1 fixtures; no personal data or live model calls."""

import json

from mini_learngraph.learning.generation import Generator
from .fakes import FixedProvider, answer


def values() -> dict:
    return {
        "title": "Python CSV", "intent": None, "prior_knowledge": None,
        "desired_outcome": "独立处理 CSV", "time_limit_text": None,
        "deadline_at": None, "target_weight": 80, "availability": None, "preferences": None,
    }


def clarification() -> dict:
    return {
        "suggested_values": values(),
        "questions": [{
            "key": "loop_background", "prompt": "循环基础？",
            "options": [{"id": "new", "label": "刚开始"}],
            "reason": "决定是否补基础", "graph_impact": "nodes",
            "allow_custom": True, "allow_skip": True,
            "default_assumption": "按需补循环基础",
        }],
        "suggested_assumptions": [{"key": "suggested:scope", "field": None, "value": "只学习标准库", "reason": "首版范围"}],
    }


def model_graph() -> dict:
    return {
        "nodes": [
            {"ref": "root", "label": "CSV", "node_type": "root", "description": "处理 CSV", "teaching_strategy": "解释流程", "target_weight": 80},
            {"ref": "loop", "label": "循环", "node_type": "concept", "description": "逐项处理", "teaching_strategy": "预测再解释", "target_weight": 70},
            {"ref": "csv", "label": "CSV读取", "node_type": "practice", "description": "表头和数据行", "teaching_strategy": "解释边界", "target_weight": 90},
        ],
        "edges": [
            {"source_ref": "root", "target_ref": "loop", "relation": "contains"},
            {"source_ref": "root", "target_ref": "csv", "relation": "contains"},
            {"source_ref": "loop", "target_ref": "csv", "relation": "prerequisite"},
        ],
    }


def generator(*outputs: dict | str | BaseException) -> Generator:
    responses = [output if isinstance(output, BaseException) else answer(json.dumps(output, ensure_ascii=False) if isinstance(output, dict) else output) for output in outputs]
    return Generator(provider=FixedProvider(*responses))


def confirm_request(goal: dict, *, kind: str = "skip", value: str | None = None) -> dict:
    return {
        "expected_revision": goal["revision"], "values": values(),
        "answers": [{"key": "loop_background", "kind": kind, "value": value}],
        "accepted_suggested_assumption_keys": [], "user_assumptions": [], "confirmed": True,
    }


def graph_request(graph: dict) -> dict:
    nodes = []
    refs = {node["id"]: f"n{index}" for index, node in enumerate(graph["nodes"])}
    for node in graph["nodes"]:
        nodes.append({key: value for key, value in node.items() if key not in {"created_at", "node_version"}} | {"ref": refs[node["id"]]})
    return {
        "expected_revision": graph["revision"], "nodes": nodes,
        "edges": [{"source_ref": refs[edge["source"]], "target_ref": refs[edge["target"]], "relation": edge["relation"]} for edge in graph["edges"]],
    }
