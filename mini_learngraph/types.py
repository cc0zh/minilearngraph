"""Messages shared by the session loop, runner and model adapter."""

from dataclasses import dataclass, field
from typing import Any, Literal

StopReason = Literal[
    "completed", "model_error", "invalid_response", "output_truncated",
    "content_filtered", "empty_response", "step_limit", "tool_error", "context_error",
]


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    text: str
    is_error: bool = False


@dataclass
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None


@dataclass
class ModelResponse:
    content: str | None
    tool_calls: list[ToolCall]
    finish_reason: str
    usage: dict[str, Any] | None = None


@dataclass
class AgentResult:
    final_text: str
    messages: list[Message]
    stop_reason: StopReason
    error: str | None = None
