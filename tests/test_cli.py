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
    )
    assert process.returncode == 0, process.stderr
    assert "/reset" in process.stdout and "/exit" in process.stdout


def test_main_missing_configuration_has_short_diagnostic(monkeypatch, capsys):
    def missing_config():
        return Settings(_env_file=None, model_base_url="", model_id="", model_api_key="")

    monkeypatch.setattr(cli, "Settings", missing_config)
    assert cli.main() == 2
    error = capsys.readouterr().err
    assert ".env.example" in error
    assert "model_base_url" in error and "model_id" in error and "model_api_key" in error
