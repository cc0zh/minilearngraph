"""Ephemeral CLI lifecycle trace; never serialize payloads or exception text."""

import json
import sys
from time import monotonic
from uuid import uuid4

from .hook import AgentHook, RunHookContext, StepHookContext, ToolHookError
from .types import ToolCall, ToolResult


def _label(value: str | None) -> str:
    # Quote identifiers so a model-supplied ID cannot inject terminal lines.
    return json.dumps(value, ensure_ascii=True) if value is not None else "none"


class TraceHook(AgentHook):
    def __init__(self) -> None:
        self._display_id = uuid4().hex[:8]
        self._tool_starts: dict[str, tuple[str, float]] = {}

    def _write(self, text: str) -> None:
        print(f"[{self._display_id}] {text}", file=sys.stderr)

    def _tool_duration(self, call_id: str) -> str:
        started = self._tool_starts.pop(call_id, None)
        if started is None:
            return ""
        duration = max(0, (monotonic() - started[1]) * 1000)
        return f" duration_ms={duration:.1f}"

    async def before_run(self, context: RunHookContext) -> None:
        self._tool_starts.clear()
        self._write("run started")

    async def before_iteration(self, context: StepHookContext) -> None:
        self._write(
            f"iteration={context.iteration} model started "
            f"model_id={_label(context.model_id)} messages={context.message_count}"
        )

    async def after_iteration(self, context: StepHookContext) -> None:
        # An invalid provider finish reason may contain arbitrary response text.
        finish = context.finish_reason
        if finish not in (None, "stop", "tool_calls", "length", "content_filter"):
            finish = "unknown"
        self._write(
            f"iteration={context.iteration} finished "
            f"model_ms={max(0, context.model_duration_ms):.1f} "
            f"tool_calls={len(context.tools)} finish_reason={_label(finish)} "
            f"error_type={_label(context.error_type)}"
        )

    async def before_execute_tool(self, context: StepHookContext, call: ToolCall) -> None:
        self._tool_starts[call.id] = (call.name, monotonic())
        self._write(f"tool={_label(call.name)} call_id={_label(call.id)} started")

    async def after_execute_tool(
        self, context: StepHookContext, call: ToolCall, result: ToolResult,
    ) -> None:
        self._write(
            f"tool={_label(call.name)} call_id={_label(call.id)} ok"
            f"{self._tool_duration(call.id)}"
        )

    async def on_execute_tool_error(
        self, context: StepHookContext, call: ToolCall, error: ToolHookError,
    ) -> None:
        self._write(
            f"tool={_label(call.name)} call_id={_label(call.id)} error "
            f"error_type={_label(error.error_type)}{self._tool_duration(call.id)}"
        )

    async def after_run(self, context: RunHookContext) -> None:
        self._write(
            f"run finished stop_reason={_label(context.stop_reason)} "
            f"model_calls={context.model_calls} duration_ms={max(0, context.duration_ms):.1f}"
        )

    async def on_error(self, context: RunHookContext) -> None:
        self._write(
            f"run error stop_reason={_label(context.stop_reason)} "
            f"error_type={_label(context.error_type)}"
        )

    async def on_finally(self, context: RunHookContext) -> None:
        try:
            for call_id, (name, _) in list(self._tool_starts.items()):
                self._write(
                    f"tool={_label(name)} call_id={_label(call_id)} interrupted "
                    f"error_type={_label(context.error_type)}{self._tool_duration(call_id)}"
                )
            self._write(
                f"run cleanup stop_reason={_label(context.stop_reason)} "
                f"error_type={_label(context.error_type)} model_calls={context.model_calls} "
                f"duration_ms={max(0, context.duration_ms):.1f}"
            )
        finally:
            self._tool_starts.clear()
