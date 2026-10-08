"""Independent acceptance: compare execution, then inspect observer evidence."""

from copy import deepcopy
from itertools import count

import pytest

from mini_learngraph.cli import interact
from mini_learngraph.hook import RunHookContext, StepHookContext
from mini_learngraph.loop import AgentLoop
from mini_learngraph.runner import AgentRunner
from mini_learngraph.tools import ToolRegistry, default_tools
from mini_learngraph.types import Message, ModelResponse, ToolCall
from tests.fakes import FixedProvider, answer, calls
from tests.test_hook import CaptureHook, names


@pytest.mark.parametrize("response,reason", [
    (TimeoutError("private-timeout"), "model_error"),
    (ModelResponse(None, [], "tool_calls"), "invalid_response"),
    (ModelResponse("partial", [ToolCall("blocked", "calculate", {})], "length"), "output_truncated"),
    (ModelResponse("partial", [ToolCall("blocked", "calculate", {})], "content_filter"), "content_filtered"),
    (answer(" "), "empty_response"),
    (calls(ToolCall("blocked", "calculate", {"expression": "2+3"})), "step_limit"),
])
async def test_all_controlled_failures_finalize_in_order_without_tools(response, reason):
    hook = CaptureHook()
    provider = FixedProvider(response)
    loop = AgentLoop(AgentRunner(provider, default_tools(), max_steps=1), "help")
    loop.history = [Message("user", "old"), Message("assistant", "old-answer")]
    original_history = deepcopy(loop.history)
    result = await loop.process("private-input", hook)
    assert result.stop_reason == reason and result.error
    assert len(provider.requests) == 1 and loop.history == original_history
    assert names(hook) == [
        "before_run", "before_iteration", "after_iteration",
        "on_error", "after_run", "on_finally",
    ]
    assert hook.events[2][1].error_type == reason
    assert hook.events[2][1].tools == ()
    assert hook.events[2][1].finish_reason == (None if reason == "model_error" else response.finish_reason)
    assert all(event[1].stop_reason == reason for event in hook.events[-3:])
    assert all(event[1].model_calls == 1 for event in hook.events[-3:])


@pytest.mark.parametrize("final_answer", ["5", ""])
async def test_every_hook_can_mutate_and_fail_without_changing_result_requests_or_history(final_answer, caplog):
    observed = CaptureHook()
    methods = [
        "before_run", "before_iteration", "after_iteration", "before_execute_tool",
        "after_execute_tool", "on_execute_tool_error", "after_run", "on_error", "on_finally",
    ]

    def hostile_callback(original):
        async def callback(*args):
            await original(*deepcopy(args))
            for arg in args:
                if isinstance(arg, RunHookContext):
                    arg.model_calls = 999
                    arg.stop_reason = "mutated"
                elif isinstance(arg, StepHookContext):
                    arg.iteration = 999
                    arg.tools = ()
                elif isinstance(arg, ToolCall):
                    arg.id = "mutated"
                    arg.arguments["expression"] = "999"
            raise RuntimeError("private-hook-exception")
        return callback

    for method in methods:
        setattr(observed, method, hostile_callback(getattr(observed, method)))

    def provider():
        return FixedProvider(
            calls(ToolCall("ok", "calculate", {"expression": "2+3"}),
                  ToolCall("error", "calculate", {"expression": "1/0"})),
            answer(final_answer),
            answer("next-answer"),
        )

    baseline_provider, observed_provider = provider(), provider()
    baseline = AgentLoop(AgentRunner(baseline_provider, default_tools(), max_steps=2), "help")
    with_hook = AgentLoop(AgentRunner(observed_provider, default_tools(), max_steps=2), "help")
    assert await baseline.process("first") == await with_hook.process("first", observed)
    assert await baseline.process("second") == await with_hook.process("second", observed)
    assert baseline_provider.requests == observed_provider.requests
    assert baseline.history == with_hook.history
    assert len(observed_provider.requests) == 3
    expected_methods = set(methods) if not final_answer else set(methods) - {"on_error"}
    assert set(names(observed)) == expected_methods
    assert all(event[1].iteration != 999 for event in observed.events if isinstance(event[1], StepHookContext))
    assert "private-hook-exception" not in caplog.text
    assert all(method in caplog.text for method in expected_methods)


@pytest.mark.parametrize("stage", ["model", "tool", "hook"])
async def test_system_exit_propagates_with_iteration_and_run_cleanup(stage):
    class ExitingRegistry(ToolRegistry):
        def prepare_call(self, call):
            raise SystemExit(7)

    class ExitingHook(CaptureHook):
        async def before_iteration(self, context):
            await super().before_iteration(context)
            raise SystemExit(7)

    hook = ExitingHook() if stage == "hook" else CaptureHook()
    registry = ExitingRegistry() if stage == "tool" else default_tools()
    response = SystemExit(7) if stage == "model" else calls(ToolCall("exit", "calculate", {}))
    with pytest.raises(SystemExit) as caught:
        await AgentRunner(FixedProvider(response), registry).run([], hook)
    assert caught.value.code == 7
    assert names(hook) == ["before_run", "before_iteration", "after_iteration", "on_finally"]
    assert hook.events[-2][1].error_type == "SystemExit"
    assert hook.events[-1][1].stop_reason == "interrupted"
    assert hook.events[-1][1].error_type == "SystemExit"


async def test_preparation_implementation_error_has_one_error_no_execution_start():
    class BrokenRegistry(ToolRegistry):
        def prepare_call(self, call):
            raise RuntimeError("private-preparation-bug")

    hook = CaptureHook()
    result = await AgentRunner(
        FixedProvider(calls(ToolCall("bad", "sample", {}))), BrokenRegistry(),
    ).run([], hook)
    assert result.stop_reason == "tool_error"
    assert names(hook) == [
        "before_run", "before_iteration", "on_execute_tool_error", "after_iteration",
        "on_error", "after_run", "on_finally",
    ]
    assert hook.events[2][2].id == "bad"
    assert hook.events[2][3].error_type == "RuntimeError"
    assert hook.events[3][1].tools[0].is_error
    assert "private-preparation-bug" not in repr(hook.events)


async def test_runner_model_and_run_durations_clamp_backwards_clock(monkeypatch):
    ticks = count(100, -1)
    monkeypatch.setattr("mini_learngraph.runner.monotonic", lambda: next(ticks))
    hook = CaptureHook()
    result = await AgentRunner(FixedProvider(answer("ok")), default_tools()).run([], hook)
    assert result.final_text == "ok"
    assert hook.events[2][1].model_duration_ms == 0
    assert hook.events[-2][1].duration_ms == hook.events[-1][1].duration_ms == 0


@pytest.mark.parametrize("trace_enabled", [False, True])
async def test_async_context_error_preserves_history_and_cli_recovers(trace_enabled, capsys):
    contexts = iter(["first-context", RuntimeError("private-context-error"), "next-context"])

    async def context():
        value = next(contexts)
        if isinstance(value, Exception):
            raise value
        return value

    provider = FixedProvider(answer("first-answer"), answer("next-answer"))
    loop = AgentLoop(AgentRunner(provider, default_tools()), "help", context)
    inputs = iter(["first", "failed", "next", "/exit"])
    await interact(loop, lambda _: next(inputs), trace_enabled=trace_enabled)
    captured = capsys.readouterr()
    assert "Error [context_error]: Could not load domain context." in captured.out
    assert "本轮处理失败" not in captured.out
    assert "private-context-error" not in captured.out + captured.err
    assert "next-answer" in captured.out and len(provider.requests) == 2
    assert len(loop.history) == 4
    assert [message.role for message in provider.requests[-1][0]] == ["system", "user", "assistant", "user"]
    assert "first-context" in provider.requests[-1][0][1].content
    assert all(message.content != "failed" for message in loop.history)
    assert captured.err.count("run started") == (2 if trace_enabled else 0)
    assert 'stop_reason="context_error"' not in captured.err
