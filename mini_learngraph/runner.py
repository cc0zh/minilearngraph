"""Execute a bounded model-tool loop over an already assembled context."""

import json
from copy import deepcopy

from .provider import InvalidResponseError, ModelProvider
from .tools import ToolRegistry
from .types import AgentResult, Message, ModelResponse, StopReason


class AgentRunner:
    def __init__(
        self, provider: ModelProvider, tools: ToolRegistry, max_steps: int = 8,
    ) -> None:
        if type(max_steps) is not int or max_steps <= 0:
            raise ValueError("max_steps must be a positive integer")
        self.provider = provider
        self.tools = tools
        self.max_steps = max_steps

    async def run(self, messages: list[Message]) -> AgentResult:
        working = deepcopy(messages)
        added: list[Message] = []
        used_ids = {call.id for message in working for call in message.tool_calls}

        def result(reason: StopReason, error: str | None = None) -> AgentResult:
            text = next(
                (m.content for m in reversed(added) if m.role == "assistant" and m.content),
                "",
            )
            return AgentResult(text, added, reason, error)

        for step in range(self.max_steps):
            try:
                response = await self.provider.chat(deepcopy(working), self.tools.definitions())
            except InvalidResponseError:
                return result("invalid_response", "Model returned an invalid response.")
            except Exception:
                return result("model_error", "Model request failed or timed out; check configuration or /reset if context is too long.")

            if not isinstance(response, ModelResponse) or not (
                response.content is None or isinstance(response.content, str)
            ) or not isinstance(response.tool_calls, list):
                return result("invalid_response", "Model returned an invalid response.")

            # Truncated/filtered responses are never allowed to trigger tools.
            if response.finish_reason in ("length", "content_filter"):
                if response.content:
                    added.append(Message("assistant", response.content))
                reason = "output_truncated" if response.finish_reason == "length" else "content_filtered"
                return result(reason, "Model output was truncated." if reason == "output_truncated" else "Model output was filtered.")

            if response.finish_reason == "stop" and not response.tool_calls:
                if not response.content or not response.content.strip():
                    return result("empty_response", "Model returned an empty answer.")
                added.append(Message("assistant", response.content))
                return result("completed")

            if response.finish_reason != "tool_calls" or not self._valid_calls(response, used_ids):
                return result("invalid_response", "Model returned invalid tool calls or an inconsistent finish reason.")

            if step + 1 == self.max_steps:
                return result("step_limit", "Model request limit reached; task is incomplete.")

            assistant = Message("assistant", response.content, deepcopy(response.tool_calls))
            working.append(assistant)
            added.append(assistant)
            for call in assistant.tool_calls:
                used_ids.add(call.id)
                try:
                    output = await self.tools.execute(deepcopy(call))
                except Exception:
                    return result("tool_error", "Tool execution failed unexpectedly.")
                tool_message = Message("tool", output, tool_call_id=call.id)
                working.append(tool_message)
                added.append(tool_message)

        return result("step_limit", "Model request limit reached; task is incomplete.")

    @staticmethod
    def _valid_calls(response: ModelResponse, used_ids: set[str]) -> bool:
        if not isinstance(response.tool_calls, list) or not response.tool_calls:
            return False
        seen = set(used_ids)
        for call in response.tool_calls:
            try:
                if (
                    not isinstance(call.id, str) or not call.id.strip() or call.id in seen
                    or not isinstance(call.name, str) or not call.name.strip()
                    or not isinstance(call.arguments, dict)
                ):
                    return False
                json.dumps(call.arguments, allow_nan=False)
                seen.add(call.id)
            except (AttributeError, TypeError, ValueError, RecursionError):
                return False
        return True
