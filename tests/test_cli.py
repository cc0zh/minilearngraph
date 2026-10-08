import asyncio
import os
import subprocess
import sys

import pytest

from mini_learngraph import cli
from mini_learngraph.config import Settings
from mini_learngraph.loop import AgentLoop
from mini_learngraph.runner import AgentRunner
from mini_learngraph.tools import default_tools
from mini_learngraph.types import AgentResult, Message
from tests.fakes import FixedProvider, answer


async def test_cli_processes_followup_reset_exit_and_blank_input():
    provider = FixedProvider(answer("one"), answer("two"), answer("three"))
    loop = AgentLoop(AgentRunner(provider, default_tools()), "help")
    inputs = iter([" ", "hello", "follow up", "/reset", "new", "/exit"])
    output = []
    await cli.interact(loop, lambda _: next(inputs), output.append)
    assert [m.role for m in provider.requests[1][0]] == ["system", "user", "assistant", "user"]
    assert [m.role for m in provider.requests[2][0]] == ["system", "user"]
    assert "one" in output and "two" in output and "three" in output
    assert "历史已清空。" in output
    assert loop.history == [Message("user", "new"), Message("assistant", "three")]


async def test_cli_error_boundary_continues_and_shows_result_error():
    class FaultyLoop:
        count = 0

        async def process(self, text):
            self.count += 1
            if self.count == 1:
                raise RuntimeError("private-secret")
            return AgentResult("partial", [], "step_limit", "limit reached")

    inputs = iter(["first", "second", "/exit"])
    output = []
    loop = FaultyLoop()
    await cli.interact(loop, lambda _: next(inputs), output.append)
    assert loop.count == 2
    assert "private-secret" not in "\n".join(output)
    assert "partial" in output
    assert "Error [step_limit]: limit reached" in output


async def test_cli_eof_exits():
    def eof(_):
        raise EOFError()

    await cli.interact(None, eof, lambda _: None)


@pytest.mark.parametrize("exc", [asyncio.CancelledError(), KeyboardInterrupt()])
async def test_cli_does_not_swallow_cancellation(exc):
    class CancelledLoop:
        async def process(self, text):
            raise exc

    with pytest.raises(type(exc)):
        await cli.interact(CancelledLoop(), lambda _: "hi", lambda _: None)


async def test_cli_passes_configured_budget_and_closes_provider(monkeypatch):
    class Config:
        max_steps = 3

    class Provider:
        closed = False

        def __init__(self, config):
            assert isinstance(config, Config)

        async def aclose(self):
            self.closed = True

    instances = []

    def make_provider(config):
        provider = Provider(config)
        instances.append(provider)
        return provider

    async def fake_interact(loop):
        assert loop.runner.max_steps == 3
        assert isinstance(loop, AgentLoop)
        raise RuntimeError("exit through exception")

    monkeypatch.setattr(cli, "OpenAIProvider", make_provider)
    monkeypatch.setattr(cli, "interact", fake_interact)
    with pytest.raises(RuntimeError):
        await cli.run_cli(Config())
    assert instances[0].closed


@pytest.mark.parametrize("input_text", ["/exit\n", ""])
def test_cli_module_can_start_and_exit_without_a_model_request(input_text):
    env = dict(os.environ)
    env.update({
        "MINI_LEARNGRAPH_MODEL_BASE_URL": "https://unused.example/v1",
        "MINI_LEARNGRAPH_MODEL_ID": "test-model",
        "MINI_LEARNGRAPH_MODEL_API_KEY": "dummy-key",
    })
    process = subprocess.run(
        [sys.executable, "-m", "mini_learngraph.cli"],
        input=input_text, text=True, encoding="utf-8", capture_output=True,
        env={**env, "PYTHONIOENCODING": "utf-8"}, timeout=10,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    assert "/reset" in process.stdout and "/exit" in process.stdout


def test_main_missing_configuration_has_short_diagnostic(monkeypatch, capsys):
    def missing_config():
        return Settings(_env_file=None, model_base_url="", model_id="", model_api_key="")

    monkeypatch.setattr(cli, "Settings", missing_config)
    assert cli.main([]) == 2
    error = capsys.readouterr().err
    assert ".env.example" in error
    assert "model_base_url" in error and "model_id" in error and "model_api_key" in error


async def test_trace_is_disabled_by_default_and_does_not_create_hooks(monkeypatch, capsys):
    def unexpected_hook():
        raise AssertionError("TraceHook must not be created by default")

    monkeypatch.setattr(cli, "TraceHook", unexpected_hook)
    inputs = iter(["hello", "/exit"])
    loop = AgentLoop(AgentRunner(FixedProvider(answer()), default_tools()), "help")
    await cli.interact(loop, lambda _: next(inputs))
    captured = capsys.readouterr()
    assert "done" in captured.out and captured.err == ""


async def test_trace_rounds_have_independent_hooks_and_answers_stay_stdout(monkeypatch, capsys):
    original = cli.TraceHook
    hooks = []

    def make_hook():
        hook = original()
        hooks.append(hook)
        return hook

    monkeypatch.setattr(cli, "TraceHook", make_hook)
    inputs = iter([" ", "first", "/reset", "second", "/exit"])
    loop = AgentLoop(AgentRunner(FixedProvider(answer("one"), answer("two")), default_tools()), "help")
    await cli.interact(loop, lambda _: next(inputs), trace_enabled=True)
    assert len(hooks) == 2 and hooks[0] is not hooks[1]
    assert all(hook._tool_starts == {} for hook in hooks)
    captured = capsys.readouterr()
    assert "one" in captured.out and "two" in captured.out and "历史已清空。" in captured.out
    assert "run started" not in captured.out
    lines = captured.err.splitlines()
    assert len({line.split("]")[0] for line in lines}) == 2
    assert captured.err.count("iteration=1 model started") == 2
    assert "iteration=2" not in captured.err
    assert captured.err.count('stop_reason="completed" model_calls=1') == 2


async def test_trace_context_failure_is_cli_error_without_runner_trace(capsys):
    def broken_context():
        raise RuntimeError("private-context-data")

    inputs = iter(["hello", "/exit"])
    provider = FixedProvider()
    loop = AgentLoop(AgentRunner(provider, default_tools()), "help", broken_context)
    await cli.interact(loop, lambda _: next(inputs), trace_enabled=True)
    captured = capsys.readouterr()
    assert "Error [context_error]" in captured.out
    assert "private-context-data" not in captured.out and captured.err == ""
    assert provider.requests == [] and loop.history == []


async def test_run_cli_passes_trace_flag_and_closes_provider(monkeypatch):
    closed = []
    seen = []

    class Provider:
        def __init__(self, settings):
            pass

        async def aclose(self):
            closed.append(True)

    async def fake_interact(loop, *, trace_enabled=False):
        seen.append(trace_enabled)
        raise asyncio.CancelledError()

    monkeypatch.setattr(cli, "OpenAIProvider", Provider)
    monkeypatch.setattr(cli, "interact", fake_interact)
    settings = Settings(_env_file=None, model_base_url="https://unused.example/v1", model_id="fixed", model_api_key="dummy")
    with pytest.raises(asyncio.CancelledError):
        await cli.run_cli(settings, trace_enabled=True)
    assert seen == [True] and closed == [True]


@pytest.mark.parametrize("argv,enabled", [([], False), (["--trace"], True)])
def test_main_parses_trace_flag(monkeypatch, argv, enabled):
    seen = []
    monkeypatch.setattr(cli, "Settings", lambda: object())

    async def fake_run(settings, *, trace_enabled=False):
        seen.append(trace_enabled)

    monkeypatch.setattr(cli, "run_cli", fake_run)
    assert cli.main(argv) == 0
    assert seen == [enabled]


def test_module_help_documents_trace_without_configuration():
    process = subprocess.run(
        [sys.executable, "-m", "mini_learngraph.cli", "--help"],
        text=True, encoding="utf-8", capture_output=True, timeout=10, check=False,
    )
    assert process.returncode == 0 and "--trace" in process.stdout and process.stderr == ""
