import asyncio
import re

import pytest
from pydantic import BaseModel, ConfigDict

from mini_learngraph import TraceHook
from mini_learngraph.hook import RunHookContext, StepHookContext, ToolHookError
from mini_learngraph.runner import AgentRunner
from mini_learngraph.tools import Tool, ToolExecutionError, ToolRegistry, default_tools
from mini_learngraph.types import Message, ModelResponse, ToolCall, ToolResult
from tests.fakes import FixedProvider, answer, calls


class Parameters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str = ""


def registry_for(execute):
    registry = ToolRegistry(timeout_seconds=0.01)
    registry.register(Tool("sample", "private-description", Parameters, execute))
    return registry


async def test_trace_lifecycle_privacy_and_output_streams(capsys):
    async def execute(parameters):
        return "Error: private-tool-result"

    call = ToolCall("call-1", "sample", {"value": "private-argument"})
    response = calls(call, content="private-reasoning")
    response.usage = {"private-usage": "private-key"}
    provider = FixedProvider(response, answer("public-answer"))
    provider.model_id = "fixed-model"
    result = await AgentRunner(provider, registry_for(execute)).run(
        [Message("system", "private-key"), Message("user", "private-user-data")], TraceHook(),
    )
    assert result.stop_reason == "completed" and result.final_text == "public-answer"
    captured = capsys.readouterr()
    assert captured.out == ""
    trace = captured.err
    assert "private-" not in trace and "public-answer" not in trace
    lines = trace.splitlines()
    assert len({line.split("]")[0] for line in lines}) == 1
    assert [line.split("] ", 1)[1].split(" ", 1)[0] for line in lines] == [
        "run", "iteration=1", 'tool="sample"', 'tool="sample"',
        "iteration=1", "iteration=2", "iteration=2", "run", "run",
    ]
    assert 'model_id="fixed-model" messages=2' in trace
    assert 'call_id="call-1" ok duration_ms=' in trace
    assert 'iteration=1 finished model_ms=' in trace and "tool_calls=1" in trace
    assert 'finish_reason="tool_calls"' in trace and 'finish_reason="stop"' in trace
    assert 'run finished stop_reason="completed" model_calls=2' in trace
    assert all(float(value) >= 0 for value in re.findall(r"(?:duration_ms|model_ms)=([\d.]+)", trace))


async def test_tool_clock_is_local_keyed_by_id_and_never_negative(monkeypatch, capsys):
    ticks = iter([10, 20, 21, 9])
    monkeypatch.setattr("mini_learngraph.trace.monotonic", lambda: next(ticks))
    hook = TraceHook()
    step = StepHookContext(1, None, 1)
    first = ToolCall("first", "sample", {"secret": "hidden"})
    second = ToolCall("second", "sample", {})
    await hook.before_execute_tool(step, first)
    await hook.before_execute_tool(step, second)
    # Fresh snapshots are unrelated objects; only call.id pairs the timer.
    await hook.after_execute_tool(StepHookContext(1, None, 1), second, ToolResult("hidden"))
    await hook.on_execute_tool_error(step, first, ToolHookError("tool_error"))
    await hook.after_iteration(StepHookContext(1, None, 1, model_duration_ms=-4))
    await hook.after_run(RunHookContext(duration_ms=-7))
    trace = capsys.readouterr().err
    assert 'call_id="second" ok duration_ms=1000.0' in trace
    assert 'call_id="first" error error_type="tool_error" duration_ms=0.0' in trace
    assert "model_ms=0.0" in trace and "duration_ms=0.0" in trace
    assert hook._tool_starts == {}


@pytest.mark.parametrize("call", [
    ToolCall("unknown", "missing", {}),
    ToolCall("invalid", "calculate", {"expression": 3}),
])
async def test_prepare_failure_has_no_start_or_execution_duration(call, capsys):
    result = await AgentRunner(FixedProvider(calls(call), answer()), default_tools()).run([], TraceHook())
    assert result.stop_reason == "completed"
    trace = capsys.readouterr().err
    tool_lines = [line for line in trace.splitlines() if " tool=" in line]
    assert len(tool_lines) == 1
    assert 'error error_type="tool_error"' in tool_lines[0]
    assert "started" not in tool_lines[0] and "duration_ms" not in tool_lines[0]


@pytest.mark.parametrize("mode", ["expected", "unexpected", "timeout"])
async def test_execution_errors_use_categories_without_exception_text(mode, capsys):
    async def execute(parameters):
        if mode == "timeout":
            await asyncio.Event().wait()
        if mode == "expected":
            raise ToolExecutionError("private-exception")
        raise ValueError("private-exception")

    provider = FixedProvider(calls(ToolCall("sample-id", "sample", {})), answer())
    result = await AgentRunner(provider, registry_for(execute)).run([], TraceHook())
    assert result.stop_reason == ("tool_error" if mode == "unexpected" else "completed")
    trace = capsys.readouterr().err
    assert "private-" not in trace
    assert 'call_id="sample-id" started' in trace
    category = "ValueError" if mode == "unexpected" else "tool_error"
    assert f'error error_type="{category}" duration_ms=' in trace
    assert 'call_id="sample-id" ok' not in trace


@pytest.mark.parametrize("response,reason", [
    (RuntimeError("private-model-error"), "model_error"),
    (ModelResponse(None, [], "private-invalid-finish"), "invalid_response"),
    (calls(ToolCall("blocked", "calculate", {"expression": "1+2"})), "step_limit"),
])
async def test_runner_failure_reason_and_model_terminal_output(response, reason, capsys):
    result = await AgentRunner(FixedProvider(response), default_tools(), max_steps=1).run([], TraceHook())
    assert result.stop_reason == reason
    trace = capsys.readouterr().err
    assert "private-" not in trace and "tool=" not in trace
    assert f'error_type="{reason}"' in trace
    assert f'run finished stop_reason="{reason}" model_calls=1' in trace
    assert "iteration=1 finished" in trace and "run cleanup" in trace


@pytest.mark.parametrize("stage", ["model", "tool"])
async def test_real_task_cancellation_propagates_and_cleans_up(stage, capsys):
    started = asyncio.Event()

    async def wait():
        started.set()
        await asyncio.Event().wait()

    class WaitingProvider:
        async def chat(self, messages, tools):
            await wait()

    async def execute(parameters):
        await wait()
        return "unreachable"

    # Avoid racing the tool timeout while explicitly cancelling the task.
    registry = ToolRegistry(timeout_seconds=60)
    registry.register(Tool("sample", "test", Parameters, execute))
    provider = WaitingProvider() if stage == "model" else FixedProvider(calls(ToolCall("pending", "sample", {})))
    hook = TraceHook()
    task = asyncio.create_task(AgentRunner(provider, registry).run([], hook))
    await asyncio.wait_for(started.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert hook._tool_starts == {}
    trace = capsys.readouterr().err
    assert 'run cleanup stop_reason="cancelled" error_type="cancelled" model_calls=1' in trace
    assert 'iteration=1 finished' in trace and 'error_type="cancelled"' in trace
    assert "run finished" not in trace and "run error" not in trace
    if stage == "tool":
        assert 'call_id="pending" interrupted error_type="cancelled" duration_ms=' in trace
        assert 'call_id="pending" error' not in trace


async def test_unexpected_runner_exception_and_exit_only_cleanup(capsys):
    class BrokenRegistry(ToolRegistry):
        def definitions(self):
            raise RuntimeError("private-registry-error")

    with pytest.raises(RuntimeError):
        await AgentRunner(FixedProvider(), BrokenRegistry()).run([], TraceHook())
    trace = capsys.readouterr().err
    assert 'run error stop_reason="unexpected_error" error_type="RuntimeError"' in trace
    assert 'run cleanup stop_reason="unexpected_error"' in trace
    assert "private-" not in trace and "run finished" not in trace

    with pytest.raises(KeyboardInterrupt):
        await AgentRunner(FixedProvider(KeyboardInterrupt()), default_tools()).run([], TraceHook())
    trace = capsys.readouterr().err
    assert 'run cleanup stop_reason="interrupted" error_type="KeyboardInterrupt"' in trace
    assert "run finished" not in trace


async def test_identifier_control_characters_cannot_inject_trace_lines(capsys):
    hook = TraceHook()
    await hook.before_execute_tool(StepHookContext(1, None, 1), ToolCall("id\nforged", "sample\x1b[31m", {}))
    trace = capsys.readouterr().err
    assert len(trace.splitlines()) == 1
    assert "\\n" in trace and "\\u001b" in trace and "\x1b" not in trace


async def test_cleanup_clears_timers_even_when_stderr_write_fails(monkeypatch):
    hook = TraceHook()
    await hook.before_execute_tool(StepHookContext(1, None, 1), ToolCall("pending", "sample", {}))

    def fail(text):
        raise OSError("closed stream")

    monkeypatch.setattr(hook, "_write", fail)
    with pytest.raises(OSError):
        await hook.on_finally(RunHookContext(stop_reason="cancelled", error_type="cancelled"))
    assert hook._tool_starts == {}
