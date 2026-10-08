import asyncio
from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, ConfigDict

from mini_learngraph.tools import (
    MAX_EXPRESSION_LENGTH, MAX_NUMBER, Tool, ToolExecutionError, ToolRegistry,
    default_tools,
)
from mini_learngraph.types import ToolCall


async def calculate(expression):
    return await default_tools().execute(ToolCall("c", "calculate", {"expression": expression}))


@pytest.mark.parametrize("expression,result", [
    ("(12 + 8) / 5", "4"), ("-2 * +3 + 8", "2"),
    ("7 / 2", "3.5"), ("1e2 + 0.5", "100.5"), (" 2 + 3 ", "5"),
    (str(MAX_NUMBER), str(MAX_NUMBER)), ("(" * 120 + "1" + ")" * 120, "1"),
])
async def test_calculate_arithmetic(expression, result):
    assert await calculate(expression) == result


@pytest.mark.parametrize("expression", [
    "1/0", "", "x + 1", "(1).__class__", "abs(-1)",
    "__import__('os').system('echo unsafe')", "2 ** 3", "5 // 2", "5 % 2",
    "[1, 2]", "True + 1", "1j", "1e309", str(MAX_NUMBER + 1),
    "1000000 * 10000000", "9" * 250,
    "1" * (MAX_EXPRESSION_LENGTH + 1), "+".join(["1"] * 30),
    "1\x00+2",
])
async def test_calculate_rejects_unsafe_or_unbounded_input(expression):
    assert (await calculate(expression)).startswith("Error:")


async def test_time_uses_fixed_clock_and_zoneinfo():
    fixed = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)
    registry = default_tools(clock=lambda: fixed)
    assert await registry.execute(ToolCall("t", "get_current_time", {})) == "UTC: 2025-01-02T03:04:05+00:00"
    assert await registry.execute(ToolCall("t", "get_current_time", {"timezone": "Asia/Shanghai"})) == "Asia/Shanghai: 2025-01-02T11:04:05+08:00"
    assert await registry.execute(ToolCall("t", "get_current_time", {"timezone": "America/New_York"})) == "America/New_York: 2025-01-01T22:04:05-05:00"


@pytest.mark.parametrize("timezone", ["Not/AZone", "../UTC", "/etc/passwd", ""])
async def test_invalid_timezone(timezone):
    result = await default_tools().execute(ToolCall("t", "get_current_time", {"timezone": timezone}))
    assert result.startswith("Error:")


async def test_naive_clock_is_a_programming_error():
    with pytest.raises(ValueError, match="timezone-aware"):
        await default_tools(clock=lambda: datetime(2025, 1, 1)).execute(ToolCall("t", "get_current_time", {}))


@pytest.mark.parametrize("name,arguments", [
    ("Calculate", {"expression": "1"}), ("unknown", {}),
    ("calculate", {}), ("calculate", {"expression": 123}),
    ("calculate", {"expression": "1", "extra": "private-data"}),
    ("get_current_time", {"timezone": 5}), ("get_current_time", {"extra": 1}),
])
async def test_unknown_names_and_invalid_arguments(name, arguments):
    result = await default_tools().execute(ToolCall("c", name, arguments))
    assert result.startswith("Error:")
    assert "private-data" not in result


class EmptyParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")


async def succeed(parameters):
    return "ok"


def test_definitions_are_sorted_and_strict():
    registry = default_tools()
    definitions = registry.definitions()
    assert [item["function"]["name"] for item in definitions] == ["calculate", "get_current_time"]
    assert all(item["function"]["parameters"]["additionalProperties"] is False for item in definitions)
    assert definitions[1]["function"]["parameters"]["properties"]["timezone"]["default"] == "UTC"
    definitions[0]["function"]["name"] = "changed"
    assert registry.definitions()[0]["function"]["name"] == "calculate"


def test_duplicate_registration_and_non_strict_parameters():
    registry = ToolRegistry()
    tool = Tool("sample", "test", EmptyParameters, succeed)
    registry.register(tool)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(tool)
    with pytest.raises(ValueError, match="forbid"):
        registry.register(Tool("loose", "test", BaseModel, succeed))


async def test_expected_error_and_unexpected_error_boundaries():
    async def expected(parameters):
        raise ToolExecutionError("cannot perform this operation.")

    async def unexpected(parameters):
        raise RuntimeError("implementation bug")

    registry = ToolRegistry()
    registry.register(Tool("expected", "test", EmptyParameters, expected))
    registry.register(Tool("unexpected", "test", EmptyParameters, unexpected))
    assert await registry.execute(ToolCall("c", "expected", {})) == "Error: cannot perform this operation."
    with pytest.raises(RuntimeError):
        await registry.execute(ToolCall("c", "unexpected", {}))


@pytest.mark.parametrize("result", [None, 123, {"value": "text"}])
async def test_non_string_tool_result_is_a_programming_error(result):
    async def invalid_result(parameters):
        return result

    registry = ToolRegistry()
    registry.register(Tool("invalid", "test", EmptyParameters, invalid_result))
    with pytest.raises(TypeError, match="must return a string"):
        await registry.execute(ToolCall("c", "invalid", {}))


async def test_tool_timeout_and_cancellation():
    async def block(parameters):
        await asyncio.Event().wait()
        return "unreachable"

    registry = ToolRegistry(timeout_seconds=0.01)
    registry.register(Tool("block", "test", EmptyParameters, block))
    assert await registry.execute(ToolCall("c", "block", {})) == "Error: tool execution timed out."
    task = asyncio.create_task(registry.execute(ToolCall("c", "block", {})))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
