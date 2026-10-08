import asyncio
from dataclasses import fields
from itertools import count

import pytest
from pydantic import BaseModel, ConfigDict, model_validator

from mini_learngraph.hook import AgentHook, RunHookContext, StepHookContext, safe_hook
from mini_learngraph.loop import AgentLoop
from mini_learngraph.runner import AgentRunner
from mini_learngraph.tools import Tool, ToolExecutionError, ToolRegistry, default_tools
from mini_learngraph.types import Message, ToolCall, ToolResult
from tests.fakes import FixedProvider, answer, calls
from tests.test_loop import FakeRunner


class CaptureHook(AgentHook):
    def __init__(self):
        self.events = []

    async def before_run(self, context):
        self.events.append(("before_run", context))

    async def before_iteration(self, context):
        self.events.append(("before_iteration", context))

    async def after_iteration(self, context):
        self.events.append(("after_iteration", context))

    async def before_execute_tool(self, context, call):
        self.events.append(("before_execute_tool", context, call))

    async def after_execute_tool(self, context, call, result):
        self.events.append(("after_execute_tool", context, call, result))

    async def on_execute_tool_error(self, context, call, error):
        self.events.append(("on_execute_tool_error", context, call, error))

    async def on_error(self, context):
        self.events.append(("on_error", context))

    async def after_run(self, context):
        self.events.append(("after_run", context))

    async def on_finally(self, context):
        self.events.append(("on_finally", context))


def names(hook):
    return [event[0] for event in hook.events]


async def test_tool_lifecycle_order_and_independent_snapshots(monkeypatch):
    ticks = count()
    monkeypatch.setattr("mini_learngraph.runner.monotonic", lambda: next(ticks))
    hook = CaptureHook()
    call = ToolCall("calc", "calculate", {"expression": "2+3"})
    provider = FixedProvider(calls(call), answer("5"))
    provider.model_id = "fixed-model"
    result = await AgentRunner(provider, default_tools()).run([Message("user", "secret-input")], hook)
    assert result.stop_reason == "completed"
    assert names(hook) == [
        "before_run", "before_iteration", "before_execute_tool", "after_execute_tool",
        "after_iteration", "before_iteration", "after_iteration", "after_run", "on_finally",
    ]
    start_step = hook.events[1][1]
    end_step = hook.events[4][1]
    assert start_step.iteration == end_step.iteration == 1
    assert start_step.model_id == "fixed-model" and start_step.message_count == 1
    assert start_step.finish_reason is None and start_step.tools == ()
    assert end_step.finish_reason == "tool_calls" and end_step.model_duration_ms == 1000
    assert end_step.tools[0].call_id == "calc" and not end_step.tools[0].is_error
    assert hook.events[2][2] == call
    assert hook.events[3][3] == ToolResult("5")
    assert hook.events[5][1].iteration == 2 and hook.events[5][1].message_count == 3
    assert hook.events[0][1].model_calls == 0
    end_run = hook.events[-2][1]
    assert end_run.stop_reason == "completed" and end_run.error_type is None
    assert end_run.model_calls == 2 and end_run.duration_ms >= 0
    assert "secret-input" not in repr(start_step) + repr(end_run)


@pytest.mark.parametrize("call,executed", [
    (ToolCall("unknown", "missing", {}), False),
    (ToolCall("invalid", "calculate", {"expression": 3}), False),
    (ToolCall("expected", "calculate", {"expression": "1/0"}), True),
    (ToolCall("success", "calculate", {"expression": "1+2"}), True),
])
async def test_preparation_and_exactly_one_terminal_callback(call, executed):
    hook = CaptureHook()
    provider = FixedProvider(calls(call), answer())
    result = await AgentRunner(provider, default_tools()).run([], hook)
    assert result.stop_reason == "completed"
    assert names(hook).count("before_execute_tool") == int(executed)
    terminals = [e for e in hook.events if e[0] in {"after_execute_tool", "on_execute_tool_error"}]
    assert len(terminals) == 1 and terminals[0][2].id == call.id
    expected_error = call.id != "success"
    assert terminals[0][0] == ("on_execute_tool_error" if expected_error else "after_execute_tool")
    summary = next(e[1].tools[0] for e in hook.events if e[0] == "after_iteration")
    assert summary.is_error is expected_error
    if expected_error:
        assert terminals[0][3].error_type == "tool_error"


class EmptyParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")


@pytest.mark.parametrize("mode", ["timeout", "expected", "unexpected", "error_word_success"])
async def test_actual_execution_error_categories_and_result_flags(mode):
    async def execute(parameters):
        if mode == "timeout":
            await asyncio.Event().wait()
        if mode == "expected":
            raise ToolExecutionError("private-result")
        if mode == "unexpected":
            raise ValueError("private-exception")
        return "Error: this text is a successful result"

    registry = ToolRegistry(timeout_seconds=0.01)
    registry.register(Tool("sample", "test", EmptyParameters, execute))
    provider = FixedProvider(calls(ToolCall("sample-id", "sample", {})), answer())
    hook = CaptureHook()
    result = await AgentRunner(provider, registry).run([], hook)
    assert names(hook).count("before_execute_tool") == 1
    terminal = [e for e in hook.events if e[0] in {"after_execute_tool", "on_execute_tool_error"}]
    assert len(terminal) == 1
    if mode == "error_word_success":
        assert terminal[0][0] == "after_execute_tool" and not terminal[0][3].is_error
    else:
        assert terminal[0][0] == "on_execute_tool_error"
        assert terminal[0][3].error_type == ("ValueError" if mode == "unexpected" else "tool_error")
        assert "private" not in repr(terminal[0][3])
    assert result.stop_reason == ("tool_error" if mode == "unexpected" else "completed")
    assert names(hook).count("after_iteration") == (1 if mode == "unexpected" else 2)
    if mode == "unexpected":
        assert names(hook)[-3:] == ["on_error", "after_run", "on_finally"]
        assert hook.events[-3][1].error_type == "tool_error"


@pytest.mark.parametrize("response,reason", [
    (TimeoutError("private-secret"), "model_error"),
    (answer(""), "empty_response"),
    (calls(ToolCall("bad", "calculate", {})), "step_limit"),
])
async def test_controlled_failure_lifecycle(response, reason):
    hook = CaptureHook()
    result = await AgentRunner(FixedProvider(response), default_tools(), max_steps=1).run([], hook)
    assert result.stop_reason == reason
    assert names(hook) == [
        "before_run", "before_iteration", "after_iteration", "on_error", "after_run", "on_finally",
    ]
    end_step = hook.events[2][1]
    assert end_step.error_type == reason and end_step.tools == ()
    assert end_step.finish_reason == (None if reason == "model_error" else response.finish_reason)
    assert hook.events[-2][1].model_calls == 1


async def test_runner_unexpected_exception_propagates_with_error_and_cleanup():
    class BrokenRegistry(ToolRegistry):
        def definitions(self):
            raise RuntimeError("private-bug")

    hook = CaptureHook()
    with pytest.raises(RuntimeError, match="private-bug"):
        await AgentRunner(FixedProvider(answer()), BrokenRegistry()).run([], hook)
    assert names(hook) == [
        "before_run", "before_iteration", "after_iteration", "on_error", "on_finally",
    ]
    assert hook.events[-1][1].stop_reason == "unexpected_error"
    assert hook.events[-1][1].error_type == "RuntimeError"
    assert hook.events[-1][1].model_calls == 0


@pytest.mark.parametrize("where", ["model", "tool", "hook"])
async def test_real_task_cancellation_propagates_and_only_finalizes_run(where):
    entered = asyncio.Event()

    async def block():
        entered.set()
        await asyncio.Event().wait()

    class BlockingProvider(FixedProvider):
        async def chat(self, messages, tools):
            await block()

    class BlockingHook(CaptureHook):
        async def before_iteration(self, context):
            await super().before_iteration(context)
            await block()

    async def execute(parameters):
        await block()

    registry = ToolRegistry()
    registry.register(Tool("block", "test", EmptyParameters, execute))
    provider = BlockingProvider() if where == "model" else FixedProvider(calls(ToolCall("block-id", "block", {})))
    hook = BlockingHook() if where == "hook" else CaptureHook()
    loop = AgentLoop(AgentRunner(provider, registry), "help")
    task = asyncio.create_task(loop.process("private-input", hook))
    await asyncio.wait_for(entered.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert loop.history == []
    assert names(hook)[-2:] == ["after_iteration", "on_finally"]
    assert "after_run" not in names(hook) and "on_error" not in names(hook)
    assert "on_execute_tool_error" not in names(hook)
    assert hook.events[-2][1].error_type == "cancelled"
    assert hook.events[-1][1].stop_reason == hook.events[-1][1].error_type == "cancelled"


async def test_hook_mutations_and_ordinary_exceptions_cannot_change_execution(caplog):
    class HostileHook(CaptureHook):
        async def before_iteration(self, context):
            context.iteration = 99
            context.message_count = 99
            raise RuntimeError("secret-hook-message")

        async def before_execute_tool(self, context, call):
            call.id = "wrong-id"
            call.arguments["expression"] = "100+200"
            context.tools = ()
            raise ValueError("secret-hook-message")

        async def after_execute_tool(self, context, call, result):
            raise LookupError("secret-hook-message")

        async def on_finally(self, context):
            context.stop_reason = "wrong"
            raise RuntimeError("secret-hook-message")

    provider = FixedProvider(calls(ToolCall("calc", "calculate", {"expression": "2+3"})), answer("5"))
    hook = HostileHook()
    result = await AgentRunner(provider, default_tools()).run([], hook)
    assert result.stop_reason == "completed"
    assert provider.requests[-1][0][-1] == Message("tool", "5", tool_call_id="calc")
    assert "secret-hook-message" not in caplog.text
    assert "before_iteration" in caplog.text and "RuntimeError" in caplog.text
    assert next(e[1] for e in hook.events if e[0] == "after_iteration").iteration == 1


@pytest.mark.parametrize("exception", [asyncio.CancelledError, KeyboardInterrupt, SystemExit])
async def test_safe_hook_preserves_cancellation_and_exit(exception):
    class InterruptingHook(AgentHook):
        async def before_run(self, context):
            raise exception()

    with pytest.raises(exception):
        await safe_hook(InterruptingHook(), "before_run", RunHookContext())


async def test_loop_passes_hook_and_context_failure_emits_no_runner_trace():
    runner = FakeRunner()
    hook = CaptureHook()
    await AgentLoop(runner, "help").process("hi", hook)
    assert runner.hooks == [hook]

    def broken_context():
        raise RuntimeError("private-context")

    loop = AgentLoop(AgentRunner(FixedProvider(answer()), default_tools()), "help", broken_context)
    result = await loop.process("hi", hook)
    assert result.stop_reason == "context_error" and hook.events == []


async def test_prepare_once_and_explicit_error_flag_independent_of_text():
    validated = []

    class CountParameters(BaseModel):
        model_config = ConfigDict(extra="forbid")

        @model_validator(mode="after")
        def count_validation(self):
            validated.append(True)
            return self

    async def execute(parameters):
        return "Error: success"

    registry = ToolRegistry()
    registry.register(Tool("sample", "test", CountParameters, execute))
    hook = CaptureHook()
    result = await AgentRunner(FixedProvider(calls(ToolCall("sample", "sample", {})), answer()), registry).run([], hook)
    assert result.stop_reason == "completed" and len(validated) == 1
    assert "after_execute_tool" in names(hook) and "on_execute_tool_error" not in names(hook)
    prepared = registry.prepare_call(ToolCall("sample", "sample", {}))
    assert await registry.execute_prepared(prepared) == ToolResult("Error: success")
    assert len(validated) == 2


def test_contexts_contain_only_observation_fields():
    assert {f.name for f in fields(RunHookContext)} == {"stop_reason", "error_type", "model_calls", "duration_ms"}
    assert {f.name for f in fields(StepHookContext)} == {
        "iteration", "model_id", "message_count", "model_duration_ms", "finish_reason", "tools", "error_type",
    }
