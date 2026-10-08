"""Optional, observation-only lifecycle hooks with independent snapshots."""

import logging
from copy import deepcopy
from dataclasses import dataclass

from .types import ToolCall, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class RunHookContext:
    stop_reason: str | None = None
    error_type: str | None = None
    model_calls: int = 0
    duration_ms: float = 0


@dataclass(frozen=True)
class ToolHookSummary:
    call_id: str
    name: str
    is_error: bool
    error_type: str | None = None


@dataclass
class StepHookContext:
    iteration: int
    model_id: str | None
    message_count: int
    model_duration_ms: float = 0
    finish_reason: str | None = None
    tools: tuple[ToolHookSummary, ...] = ()
    error_type: str | None = None


@dataclass(frozen=True)
class ToolHookError:
    """Safe error category only; no exception, arguments or result text."""

    error_type: str


class AgentHook:
    async def before_run(self, context: RunHookContext) -> None:
        pass

    async def before_iteration(self, context: StepHookContext) -> None:
        pass

    async def after_iteration(self, context: StepHookContext) -> None:
        pass

    async def before_execute_tool(self, context: StepHookContext, call: ToolCall) -> None:
        pass

    async def after_execute_tool(
        self, context: StepHookContext, call: ToolCall, result: ToolResult,
    ) -> None:
        pass

    async def on_execute_tool_error(
        self, context: StepHookContext, call: ToolCall, error: ToolHookError,
    ) -> None:
        pass

    async def after_run(self, context: RunHookContext) -> None:
        pass

    async def on_error(self, context: RunHookContext) -> None:
        pass

    async def on_finally(self, context: RunHookContext) -> None:
        pass


async def safe_hook(hook: AgentHook, method: str, *args: object) -> None:
    """Isolate ordinary observer errors, while preserving cancellation and exit."""
    try:
        await getattr(hook, method)(*deepcopy(args))
    except Exception as error:  # noqa: BLE001 -- Isolate observer failures; cancellation and exit must propagate.
        logger.warning("Hook %s failed: %s", method, type(error).__name__)
