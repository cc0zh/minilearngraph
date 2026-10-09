"""Opt-in synthetic real-model B1 smoke; never writes a user's database.

Without --allow-configured-model, no .env is read and no network is contacted.
Use the flag only within an explicitly approved provider/configuration budget.
"""

import argparse
import asyncio
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

# Support the documented `python scripts/verify_learning_model.py` entry.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import ValidationError

from mini_learngraph.config import Settings
from mini_learngraph.learning.errors import DomainError
from mini_learngraph.learning.generation import Generator
from mini_learngraph.learning.schemas import ConfirmGoal, CreateGoal, RevisionRequest
from mini_learngraph.learning.service import LearningService
from mini_learngraph.learning.storage import Store
from mini_learngraph.provider import OpenAIProvider


async def smoke(settings: Settings) -> int:
    report = {"at": datetime.now(UTC).isoformat(), "model_id": settings.model_id, "stage": "b1"}
    provider = OpenAIProvider(settings)
    try:
        with tempfile.TemporaryDirectory(prefix="learning-b1-smoke-") as directory:
            store = Store(Path(directory) / "synthetic.sqlite3")
            store.initialize()
            service = LearningService(store, Generator(provider=provider, timeout_seconds=settings.request_timeout_seconds))
            goal = await service.create_goal(CreateGoal(prompt="学习 Python，最终能独立处理 CSV 数据。已有基础尚不明确；不指定期限或学习时间。"))
            answers = []
            for question in goal["questions"]:
                if question["allow_skip"]:
                    kind, value = "skip", None
                elif question["options"]:
                    kind, value = "choice", question["options"][0]["id"]
                else:
                    kind, value = "custom", "合成测试：尚无相关基础"
                answers.append({"key": question["key"], "kind": kind, "value": value})
            values = dict(goal["suggested_values"], deadline_at=None, time_limit_text=None, availability=None, preferences=None)
            confirmed = await service.confirm_goal(goal["id"], ConfirmGoal.model_validate({
                "expected_revision": goal["revision"], "values": values,
                "answers": answers, "accepted_suggested_assumption_keys": [],
                "user_assumptions": [], "confirmed": True,
            }))
            graph = await service.create_graph(goal["id"], RevisionRequest(expected_revision=confirmed["revision"]))
            report.update(result="PASS", questions=len(goal["questions"]), skips=sum(answer["kind"] == "skip" for answer in answers), nodes=len(graph["nodes"]), edges=len(graph["edges"]), status=graph["status"])
    except DomainError as error:
        report.update(result="FAIL", code=error.code, failure_reason=error.as_dict()["details"]["failure_reason"])
        print(json.dumps(report, ensure_ascii=False))
        return 1
    except Exception:
        report.update(result="FAIL", code="internal_error")
        print(json.dumps(report, ensure_ascii=False))
        return 1
    finally:
        await provider.aclose()
    print(json.dumps(report, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["b1"], required=True)
    parser.add_argument("--allow-configured-model", action="store_true")
    args = parser.parse_args()
    if not args.allow_configured_model:
        print("SKIPPED: model configuration unavailable or not authorized (no configuration read, no network)")
        return 2
    try:
        settings = Settings()  # type: ignore[call-arg]
    except ValidationError:
        print("SKIPPED: model configuration unavailable")
        return 2
    return asyncio.run(smoke(settings))


if __name__ == "__main__":
    raise SystemExit(main())
