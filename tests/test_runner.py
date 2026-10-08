import asyncio
from copy import deepcopy

import pytest

from mini_learngraph.provider import InvalidResponseError
from mini_learngraph.runner import AgentRunner
from mini_learngraph.tools import default_tools
from mini_learngraph.types import Message, ModelResponse, ToolCall, ToolResult
from tests.fakes import FixedProvider, answer, calls


class SpyTools:
    def __init__(self, failure: BaseException | None = None):
        self.called = []
        self.failure = failure

    def definitions(self):
        return []

    def prepare_call(self, call):
        return call

    async def execute_prepared(self, call):
        self.called.append(deepcopy(call))
        if self.failure is not None:
            raise self.failure
        return ToolResult("result")


async def test_direct_answer_returns_only_new_messages():
    provider = FixedProvider(answer("hello"))
    messages = [Message("system", "help"), Message("user", "hi")]
    result = await AgentRunner(provider, default_tools()).run(messages)
    assert result.stop_reason == "completed"
    assert result.final_text == "hello"
    assert result.messages == [Message("assistant", "hello")]
    assert provider.requests[0][0] == messages


async def test_single_tool_request_preserves_pairing():
    call = ToolCall("c1", "calculate", {"expression": "(12 + 8) / 5"})
    provider = FixedProvider(calls(call), answer("4"))
    result = await AgentRunner(provider, default_tools()).run([Message("user", "compute")])
    assert result.stop_reason == "completed"
    assert result.final_text == "4"
    next_messages = provider.requests[1][0]
    assert [m.role for m in next_messages] == ["user", "assistant", "tool"]
    assert next_messages[1].tool_calls == [call]
    assert next_messages[2].tool_call_id == "c1"
    assert float(next_messages[2].content) == 4
    assert result.messages == [*next_messages[1:], Message("assistant", "4")]


async def test_same_round_multiple_tools_execute_in_order():
    a = ToolCall("a", "one", {})
    b = ToolCall("b", "two", {})
    provider = FixedProvider(calls(a, b), answer())
    tools = SpyTools()
    result = await AgentRunner(provider, tools).run([Message("user", "both")])
    assert result.stop_reason == "completed"
    assert tools.called == [a, b]
    chain = provider.requests[1][0]
    assert chain[1].tool_calls == [a, b]
    assert [m.tool_call_id for m in chain[2:]] == ["a", "b"]


async def test_multiple_model_tool_rounds():
    provider = FixedProvider(
        calls(ToolCall("a", "calculate", {"expression": "2 + 3"})),
        calls(ToolCall("b", "calculate", {"expression": "5 * 2"})),
        answer("10"),
    )
    result = await AgentRunner(provider, default_tools()).run([Message("user", "two steps")])
    assert result.final_text == "10"
    assert [m.role for m in provider.requests[2][0]] == ["user", "assistant", "tool", "assistant", "tool"]
    assert [m.tool_call_id for m in result.messages if m.role == "tool"] == ["a", "b"]


@pytest.mark.parametrize("bad_call", [
    ToolCall("bad", "calculate", {"expression": 23}),
    ToolCall("bad", "calculate", {"expression": "1 / 0"}),
    ToolCall("bad", "Calculate", {"expression": "1 + 2"}),
    ToolCall("bad", "get_current_time", {"timezone": "not/a/zone"}),
    ToolCall("bad", "calculate", {"expression": "1 + 2", "extra": True}),
])
async def test_tool_errors_can_be_corrected(bad_call):
    provider = FixedProvider(
        calls(bad_call),
        calls(ToolCall("fixed", "calculate", {"expression": "1 + 2"})),
        answer("3"),
    )
    result = await AgentRunner(provider, default_tools()).run([Message("user", "calculate")])
    assert result.stop_reason == "completed"
    assert provider.requests[1][0][-1].content.startswith("Error:")
    assert float(provider.requests[2][0][-1].content) == 3


@pytest.mark.parametrize("response", [
    calls(ToolCall("", "one", {})),
    calls(ToolCall("x", "one", {}), ToolCall("x", "two", {})),
    calls(ToolCall("valid", "one", {}), ToolCall("", "two", {})),
    calls(ToolCall("x", "", {})),
    calls(ToolCall("x", "one", "{}")),
    calls(ToolCall("x", "one", [])),
    calls(ToolCall("x", "one", {"number": float("nan")})),
    ModelResponse("wrong", [ToolCall("x", "one", {})], "stop"),
    ModelResponse(None, [], "tool_calls"),
    ModelResponse("wrong", [ToolCall("x", "one", {})], "unknown"),
    ModelResponse("answer", None, "stop"),
])
async def test_invalid_response_executes_no_tools(response):
    tools = SpyTools()
    provider = FixedProvider(response)
    result = await AgentRunner(provider, tools).run([Message("user", "test")])
    assert result.stop_reason == "invalid_response"
    assert result.error
    assert tools.called == []
    assert len(provider.requests) == 1


async def test_reused_call_id_is_invalid_on_later_round():
    provider = FixedProvider(calls(ToolCall("x", "one", {})), calls(ToolCall("x", "two", {})))
    tools = SpyTools()
    result = await AgentRunner(provider, tools).run([Message("user", "test")])
    assert result.stop_reason == "invalid_response"
    assert len(tools.called) == 1


@pytest.mark.parametrize("finish,reason", [("length", "output_truncated"), ("content_filter", "content_filtered")])
async def test_truncated_or_filtered_text_never_executes_tools(finish, reason):
    provider = FixedProvider(ModelResponse("partial", [ToolCall("x", "one", {})], finish))
    tools = SpyTools()
    result = await AgentRunner(provider, tools).run([Message("user", "test")])
    assert result.stop_reason == reason
    assert result.final_text == "partial"
    assert result.messages == [Message("assistant", "partial")]
    assert tools.called == []


@pytest.mark.parametrize("content", [None, "", "   "])
async def test_empty_response(content):
    result = await AgentRunner(FixedProvider(answer(content)), SpyTools()).run([])
    assert result.stop_reason == "empty_response"
    assert result.error and not result.messages


@pytest.mark.parametrize("exc,reason", [
    (RuntimeError("secret-token"), "model_error"),
    (TimeoutError("secret-token"), "model_error"),
    (InvalidResponseError("secret-token"), "invalid_response"),
])
async def test_model_error_is_separate_from_model_text(exc, reason):
    result = await AgentRunner(FixedProvider(exc), SpyTools()).run([])
    assert result.stop_reason == reason
    assert result.final_text == "" and result.messages == []
    assert result.error and "secret-token" not in result.error


async def test_tool_implementation_error_terminates_run():
    tools = SpyTools(ValueError("private implementation detail"))
    provider = FixedProvider(calls(ToolCall("x", "one", {})), answer())
    result = await AgentRunner(provider, tools).run([])
    assert result.stop_reason == "tool_error"
    assert len(provider.requests) == 1
    assert "private" not in result.error


@pytest.mark.parametrize("where", ["model", "tool"])
async def test_cancellation_propagates(where):
    provider = FixedProvider(asyncio.CancelledError()) if where == "model" else FixedProvider(calls(ToolCall("x", "one", {})))
    tools = SpyTools(asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await AgentRunner(provider, tools).run([])


async def test_last_model_request_never_executes_tools_or_makes_extra_request():
    provider = FixedProvider(calls(ToolCall("a", "one", {})), calls(ToolCall("b", "two", {})))
    tools = SpyTools()
    result = await AgentRunner(provider, tools, max_steps=2).run([])
    assert result.stop_reason == "step_limit"
    assert len(provider.requests) == 2
    assert [c.id for c in tools.called] == ["a"]
    assert result.error


async def test_one_request_budget_allows_direct_answer_but_no_tool():
    tools = SpyTools()
    result = await AgentRunner(FixedProvider(calls(ToolCall("a", "one", {}))), tools, 1).run([])
    assert result.stop_reason == "step_limit" and tools.called == []
    assert (await AgentRunner(FixedProvider(answer()), tools, 1).run([])).stop_reason == "completed"


@pytest.mark.parametrize("max_steps", [0, -1, True, 1.5, "2"])
def test_max_steps_must_be_positive_integer(max_steps):
    with pytest.raises(ValueError):
        AgentRunner(FixedProvider(), SpyTools(), max_steps)


async def test_runner_never_mutates_nested_input_and_has_no_run_state():
    class MutatingProvider(FixedProvider):
        async def chat(self, messages, tools):
            messages[1].tool_calls[0].arguments["nested"]["items"].append(99)
            return await super().chat(messages, tools)

    messages = [Message("user", "old"), Message("assistant", None, [ToolCall("old", "one", {"nested": {"items": [1]}})]), Message("tool", "ok", tool_call_id="old")]
    before = deepcopy(messages)
    runner = AgentRunner(MutatingProvider(answer("first"), answer("second")), SpyTools())
    first = await runner.run(messages)
    second = await runner.run(messages)
    assert messages == before
    assert first.messages == [Message("assistant", "first")]
    assert second.messages == [Message("assistant", "second")]
