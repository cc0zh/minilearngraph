"""Browser integration fixture: real B1 API/SQLite, synthetic provider only.

Run only via the Web test:api-flow script. No live model, production DB or
extra routes. The temporary directory is discarded when this test server ends.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import uvicorn

from mini_learngraph.api.app import create_app
from mini_learngraph.api.settings import ServerSettings
from mini_learngraph.learning.generation import Generator
from mini_learngraph.types import Message, ModelResponse


class BrowserProvider:
    def __init__(self) -> None:
        self.failed: set[str] = set()

    async def chat(self, messages: list[Message], tools: list[dict]) -> ModelResponse:
        assert tools == []
        data = json.loads((messages[1].content or "").removeprefix("BEGIN INPUT DATA\n").removesuffix("\nEND INPUT DATA"))
        graph_request = "Design a complete learning graph" in (messages[0].content or "")
        prompt = data["raw_prompt"]
        if graph_request and "PAUSE_GRAPH" in prompt and os.environ.get("B1_TEST_PAUSE_GENERATION") == "1":
            print("B1_TEST_GENERATION_WAITING", flush=True)
            await asyncio.Event().wait()
        key = f"{graph_request}:{prompt}"
        if ((not graph_request and "FAIL_CLARIFY_ONCE" in prompt) or (graph_request and "FAIL_GRAPH_ONCE" in prompt)) and key not in self.failed:
            self.failed.add(key)
            return ModelResponse("{", [], "stop")
        if graph_request:
            payload = {
                "nodes": [
                    {"ref": ref, "label": label, "node_type": kind, "description": "理解并说明处理步骤", "teaching_strategy": "先预测结果再解释", "target_weight": 80}
                    for ref, label, kind in [("root", "CSV 数据处理", "root"), ("loop", "循环", "concept"), ("csv", "CSV 读取", "practice")]
                ],
                "edges": [
                    {"source_ref": "root", "target_ref": "loop", "relation": "contains"},
                    {"source_ref": "root", "target_ref": "csv", "relation": "contains"},
                    {"source_ref": "loop", "target_ref": "csv", "relation": "prerequisite"},
                ],
            }
        else:
            payload = {
                "suggested_values": {"title": "Python CSV 数据处理", "intent": "项目", "prior_knowledge": None, "desired_outcome": "能说明读取、逐行转换和写出的步骤", "time_limit_text": None, "deadline_at": None, "target_weight": 80, "availability": None, "preferences": None},
                "questions": [
                    {"key": "loop_background", "prompt": "你能独立写循环吗？", "reason": "决定是否补充循环基础", "graph_impact": "nodes", "options": [{"id": "yes", "label": "可以独立完成"}], "allow_custom": True, "allow_skip": True, "default_assumption": "按需要补充循环基础设计路线"},
                    {"key": "csv_tooling", "prompt": "你使用什么工具？", "reason": "影响教学示例", "graph_impact": "teaching", "options": [], "allow_custom": True, "allow_skip": False, "default_assumption": None},
                    {"key": "output_format", "prompt": "目标输出是什么？", "reason": "决定学习范围", "graph_impact": "scope", "options": [{"id": "csv", "label": "清理后的 CSV 文件"}], "allow_custom": False, "allow_skip": False, "default_assumption": None},
                ],
                "suggested_assumptions": [{"key": "suggested:headers", "field": "desired_outcome", "value": "包含表头处理", "reason": "CSV 读取通常需要区分表头"}],
            }
        return ModelResponse(json.dumps(payload, ensure_ascii=False), [], "stop")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path)
    args = parser.parse_args()
    # This is a test server, not the user's configured service. Never read
    # repository dotenv or inherit settings that point to personal assets.
    ServerSettings.model_config["env_file"] = None
    for name in ("HOST", "PORT", "DB_PATH", "ALLOWED_ORIGINS"):
        os.environ.pop(f"MINI_LEARNGRAPH_{name}", None)
    os.environ["MINI_LEARNGRAPH_ALLOWED_ORIGINS"] = '["http://127.0.0.1:5173"]'
    with TemporaryDirectory(prefix="mini-web-b1-") as directory:
        app = create_app(db_path=args.db or Path(directory) / "browser.sqlite3", generator=Generator(provider=BrowserProvider()))
        uvicorn.run(app, host="127.0.0.1", port=8000, access_log=False, proxy_headers=False)
