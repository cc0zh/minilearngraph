import asyncio
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from mini_learngraph.loop import AgentLoop
from mini_learngraph.runner import AgentRunner
from mini_learngraph.tools import default_tools
from mini_learngraph.types import AgentResult, Message, ToolCall
from tests.fakes import FixedProvider, answer, calls


class FakeRunner:
    def __init__(self, result=None):
        self.result = result or AgentResult("answer", [Message("assistant", "answer")], "completed")
        self.requests = []
        self.hooks = []

    async def run(self, messages, hook=None):
        self.requests.append(deepcopy(messages))
        self.hooks.append(hook)
        return self.result


async def test_context_assembly_and_success_history_without_duplicates():
    runner = FakeRunner()
    loop = AgentLoop(runner, "teach", lambda: "target=t1; node=n1; state=new")
    result = await loop.process("explain")
    request = runner.requests[0]
    assert [m.role for m in request] == ["system", "user"]
    assert "reference data" in request[0].content
    assert request[1].content.startswith("explain\n\n<domain_context>")
    assert "node=n1" in request[1].content
    assert loop.history == [request[1], Message("assistant", "answer")]
    assert result.final_text == "answer"
    result.messages[0].content = "changed externally"
    assert loop.history[-1].content == "answer"
    await loop.process("follow up")
    assert [m.role for m in runner.requests[1]] == ["system", "user", "assistant", "user"]
    assert len(loop.history) == 4
    assert all(m.role != "system" for m in loop.history)


async def test_async_context_is_refreshed_and_old_snapshots_are_retained():
    node = "n1"

    async def context():
        return f"target=t1; node={node}"

    runner = FakeRunner()
    loop = AgentLoop(runner, "teach", context)
    await loop.process("first")
    node = "n2"
    await loop.process("that earlier concept")
    messages = runner.requests[-1]
    assert "node=n1" in messages[1].content
    assert "node=n2" in messages[-1].content
    assert "node=n2" not in loop.history[0].content


@pytest.mark.parametrize("reason", [
    "model_error", "invalid_response", "output_truncated", "content_filtered",
    "empty_response", "step_limit", "tool_error", "context_error",
])
async def test_failed_turn_never_changes_history(reason):
    runner = FakeRunner(AgentResult("partial", [Message("assistant", "partial")], reason, "error"))
    loop = AgentLoop(runner, "help")
    loop.history = [Message("user", "earlier"), Message("assistant", "earlier answer")]
    before = deepcopy(loop.history)
    result = await loop.process("failing turn")
    assert result.stop_reason == reason
    assert loop.history == before


@pytest.mark.parametrize("async_provider", [False, True])
async def test_context_failure_prevents_runner_call(async_provider):
    def failing():
        raise RuntimeError("private-secret")

    async def async_failing():
        return failing()

    runner = FakeRunner()
    loop = AgentLoop(runner, "help", async_failing if async_provider else failing)
    result = await loop.process("hi")
    assert result.stop_reason == "context_error"
    assert result.final_text == "" and result.messages == []
    assert "private-secret" not in result.error
    assert runner.requests == [] and loop.history == []


async def test_context_cancellation_propagates():
    async def context():
        raise asyncio.CancelledError()

    loop = AgentLoop(FakeRunner(), "help", context)
    with pytest.raises(asyncio.CancelledError):
        await loop.process("hi")
    assert loop.history == []


async def test_reference_data_instructions_remain_when_current_snapshot_is_absent():
    snapshot = "target=t1; node=n1"
    runner = FakeRunner()
    loop = AgentLoop(runner, "help", lambda: snapshot)
    await loop.process("first")
    snapshot = None
    await loop.process("follow up")
    messages = runner.requests[-1]
    assert "reference data" in messages[0].content
    assert "node=n1" in messages[1].content
    assert messages[-1].content == "follow up"


async def test_reset_only_clears_history():
    runner = FakeRunner()
    loop = AgentLoop(runner, "instructions", lambda: "node=n")
    await loop.process("hi")
    loop.reset()
    assert loop.history == []
    await loop.process("new")
    assert [m.role for m in runner.requests[-1]] == ["system", "user"]
    assert "instructions" in runner.requests[-1][0].content
    assert "node=n" in runner.requests[-1][-1].content


async def test_combined_loop_two_tools_followup_and_snapshot_switch():
    node = "arithmetic"
    provider = FixedProvider(
        calls(
            ToolCall("time", "get_current_time", {"timezone": "UTC"}),
            ToolCall("calc", "calculate", {"expression": "(12 + 8) / 5"}),
        ),
        answer("现在是 2030-01-01T12:00:00+00:00，结果为 4。"),
        answer("刚才的结果是 4；加 1 为 5。"),
    )
    registry = default_tools(clock=lambda: datetime(2030, 1, 1, 12, tzinfo=timezone.utc))
    loop = AgentLoop(AgentRunner(provider, registry), "help", lambda: f"target=math; node={node}")
    first = await loop.process("查询时间，并计算 (12 + 8) / 5")
    node = "addition"
    second = await loop.process("刚才结果加 1 呢？")
    assert first.stop_reason == second.stop_reason == "completed"
    messages = provider.requests[2][0]
    assert [m.role for m in messages] == ["system", "user", "assistant", "tool", "tool", "assistant", "user"]
    assert "node=arithmetic" in messages[1].content
    assert "node=addition" in messages[-1].content
    assert "2030-01-01T12:00:00+00:00" in messages[3].content
    assert float(messages[4].content) == 4
    assert len(loop.history) == 7


async def test_combined_failed_tool_chain_does_not_pollute_next_request():
    provider = FixedProvider(
        answer("first"),
        calls(ToolCall("calc", "calculate", {"expression": "1+2"})),
        RuntimeError("network failed"),
        answer("recovered"),
    )
    loop = AgentLoop(AgentRunner(provider, default_tools()), "help")
    await loop.process("ok")
    before = deepcopy(loop.history)
    failed = await loop.process("bad turn")
    assert failed.stop_reason == "model_error"
    assert loop.history == before
    await loop.process("retry")
    assert provider.requests[-1][0] == [Message("system", "help"), *before, Message("user", "retry")]
