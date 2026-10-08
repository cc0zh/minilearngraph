"""Validated tools and bounded implementations for time and arithmetic."""

import ast
import asyncio
import math
import operator
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, ValidationError

from .types import ToolCall, ToolResult


class ToolExecutionError(Exception):
    """An expected tool failure with a short, safe message for the model."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: type[BaseModel]
    execute: Callable[[BaseModel], Awaitable[str]]


@dataclass(frozen=True)
class PreparedToolCall:
    tool: Tool
    parameters: BaseModel


class ToolRegistry:
    def __init__(self, timeout_seconds: float = 10) -> None:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("Tool timeout must be positive and finite")
        self._timeout_seconds = timeout_seconds
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError("Tool name is already registered")
        if tool.parameters.model_config.get("extra") != "forbid":
            raise ValueError("Tool parameters must forbid extra fields")
        self._tools[tool.name] = tool

    def definitions(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters.model_json_schema(),
                },
            }
            for _, tool in sorted(self._tools.items())
        ]

    def prepare_call(self, call: ToolCall) -> PreparedToolCall | ToolResult:
        tool = self._tools.get(call.name)
        if tool is None:
            return ToolResult("Error: unknown tool.", is_error=True)
        try:
            parameters = tool.parameters.model_validate(call.arguments)
        except ValidationError:
            return ToolResult("Error: invalid tool arguments.", is_error=True)
        return PreparedToolCall(tool, parameters)

    async def execute(self, call: ToolCall) -> ToolResult:
        prepared = self.prepare_call(call)
        if isinstance(prepared, ToolResult):
            return prepared
        return await self.execute_prepared(prepared)

    async def execute_prepared(self, prepared: PreparedToolCall) -> ToolResult:
        try:
            async with asyncio.timeout(self._timeout_seconds):
                result = await prepared.tool.execute(prepared.parameters)
            if not isinstance(result, str):
                raise TypeError("Tool must return a string")
            return ToolResult(result)
        except TimeoutError:
            return ToolResult("Error: tool execution timed out.", is_error=True)
        except ToolExecutionError as error:
            return ToolResult(f"Error: {error}", is_error=True)


class TimeParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timezone: str = "UTC"


class CalculateParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expression: str


MAX_EXPRESSION_LENGTH = 256
MAX_EXPRESSION_NODES = 64
MAX_NUMBER = 1_000_000_000_000
_OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def _bounded_number(value: int | float) -> int | float:
    if abs(value) > MAX_NUMBER or not math.isfinite(value):
        raise ToolExecutionError("number exceeds the allowed range.")
    return value


def _calculate(expression: str) -> str:
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise ToolExecutionError("expression is too long.")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except (SyntaxError, ValueError, RecursionError):
        raise ToolExecutionError("expression is not valid arithmetic.") from None
    if sum(1 for _ in ast.walk(tree)) > MAX_EXPRESSION_NODES:
        raise ToolExecutionError("expression is too complex.")

    def visit(node: ast.AST) -> int | float:
        if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
            return _bounded_number(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand)
            return _bounded_number(value if isinstance(node.op, ast.UAdd) else -value)
        if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Div) and right == 0:
                raise ToolExecutionError("division by zero.")
            return _bounded_number(_OPERATORS[type(node.op)](left, right))
        raise ToolExecutionError("only numbers, parentheses and + - * / are allowed.")

    result = visit(tree.body)
    if isinstance(result, float) and result.is_integer():
        return str(int(result))
    return str(result)


def default_tools(clock: Callable[[], datetime] | None = None) -> ToolRegistry:
    now = clock if clock is not None else lambda: datetime.now(UTC)

    async def current_time(parameters: BaseModel) -> str:
        assert isinstance(parameters, TimeParameters)
        try:
            timezone = ZoneInfo(parameters.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ToolExecutionError("timezone must be a valid IANA timezone.") from None
        instant = now()
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("Clock must return a timezone-aware datetime")
        return f"{parameters.timezone}: {instant.astimezone(timezone).isoformat()}"

    async def calculate(parameters: BaseModel) -> str:
        assert isinstance(parameters, CalculateParameters)
        return _calculate(parameters.expression)

    registry = ToolRegistry()
    registry.register(Tool("get_current_time", "Get the current time in an IANA timezone (default UTC).", TimeParameters, current_time))
    registry.register(Tool("calculate", "Calculate numbers and parentheses using + - * /.", CalculateParameters, calculate))
    return registry
