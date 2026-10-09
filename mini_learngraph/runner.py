"""Execute a bounded model-tool loop over an already assembled context."""

import asyncio
import json
from copy import deepcopy
from time import monotonic

from .hook import (
    AgentHook,
    RunHookContext,
    StepHookContext,
    ToolHookError,
    ToolHookSummary,
    safe_hook,
)
from .provider import InvalidResponseError, ModelProvider
from .tools import ToolRegistry
from .types import AgentResult, Message, ModelResponse, StopReason, ToolCall, ToolResult


class AgentRunner:
    def __init__(
        self, provider: ModelProvider, tools: ToolRegistry, max_steps: int = 8,
    ) -> None:
        if type(max_steps) is not int or max_steps <= 0:
            raise ValueError("max_steps must be a positive integer")
        self.provider = provider
        self.tools = tools
        self.max_steps = max_steps

    async def run(self, messages: list[Message], hook: AgentHook | None = None) -> AgentResult:
        observer = hook if hook is not None else AgentHook()
        context = RunHookContext()
        started = monotonic()
        try:
            await safe_hook(observer, "before_run", context)
            result = await self._run(messages, observer, context)
            context.duration_ms = max(0, (monotonic() - started) * 1000)
            if result.stop_reason != "completed":
                await safe_hook(observer, "on_error", context)
            await safe_hook(observer, "after_run", context)
            return result
        except asyncio.CancelledError:
            context.stop_reason = context.error_type = "cancelled"
            raise
        except Exception as error:
            context.stop_reason = "unexpected_error"
            context.error_type = type(error).__name__
            context.duration_ms = max(0, (monotonic() - started) * 1000)
            await safe_hook(observer, "on_error", context)
            raise
        except (KeyboardInterrupt, SystemExit) as error:
            context.stop_reason = "interrupted"
            context.error_type = type(error).__name__
            raise
        finally:
            context.duration_ms = max(0, (monotonic() - started) * 1000)
            await safe_hook(observer, "on_finally", context)

    async def _run(
        self, messages: list[Message], hook: AgentHook, context: RunHookContext,
    ) -> AgentResult:
        working = deepcopy(messages)
        added: list[Message] = []
        used_ids = {call.id for message in working for call in message.tool_calls}

        def result(reason: StopReason, error: str | None = None) -> AgentResult:
            context.stop_reason = reason
            context.error_type = None if reason == "completed" else reason
            if reason != "completed":
                step_context.error_type = reason
            text = next(
                (m.content for m in reversed(added) if m.role == "assistant" and m.content),
                "",
            )
            return AgentResult(text, added, reason, error)

        for step in range(self.max_steps):
            model_id = getattr(self.provider, "model_id", None)
            step_context = StepHookContext(
                iteration=step + 1,
                model_id=model_id if isinstance(model_id, str) else None,
                message_count=len(working),
            )
            try:
                await safe_hook(hook, "before_iteration", step_context)
                definitions = self.tools.definitions()
                model_started = monotonic()
                context.model_calls += 1
                try:
                    response = await self.provider.chat(deepcopy(working), definitions)
                except InvalidResponseError:
                    return result("invalid_response", "Model returned an invalid response.")
                except Exception:  # noqa: BLE001 -- Provider failures become results; cancellation and exit propagate.
                    return result("model_error", "Model request failed or timed out; check configuration or /reset if context is too long.")
                finally:
                    step_context.model_duration_ms = max(0, (monotonic() - model_started) * 1000)

                if not isinstance(response, ModelResponse) or not (
                    response.content is None or isinstance(response.content, str)
                ) or not isinstance(response.tool_calls, list):
                    return result("invalid_response", "Model returned an invalid response.")
                if isinstance(response.finish_reason, str):
                    step_context.finish_reason = response.finish_reason

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
                        output = await self._execute_tool(step_context, deepcopy(call), hook)
                    except Exception:  # noqa: BLE001 -- Tool defects stop this turn; cancellation and exit propagate.
                        return result("tool_error", "Tool execution failed unexpectedly.")
                    tool_message = Message("tool", output.text, tool_call_id=call.id)
                    working.append(tool_message)
                    added.append(tool_message)
            except asyncio.CancelledError:
                step_context.error_type = "cancelled"
                raise
            except BaseException as error:
                step_context.error_type = type(error).__name__
                raise
            finally:
                await safe_hook(hook, "after_iteration", step_context)

        return result("step_limit", "Model request limit reached; task is incomplete.")

    async def _execute_tool(
        self, context: StepHookContext, call: ToolCall, hook: AgentHook,
    ) -> ToolResult:
        try:
            prepared = self.tools.prepare_call(call)
            if isinstance(prepared, ToolResult):
                output = prepared
            else:
                await safe_hook(hook, "before_execute_tool", context, call)
                output = await self.tools.execute_prepared(prepared)
        except Exception as error:
            category = type(error).__name__
            context.tools += (ToolHookSummary(call.id, call.name, True, category),)
            await safe_hook(hook, "on_execute_tool_error", context, call, ToolHookError(category))
            raise
        category = "tool_error" if output.is_error else None
        context.tools += (ToolHookSummary(call.id, call.name, output.is_error, category),)
        if output.is_error:
            await safe_hook(hook, "on_execute_tool_error", context, call, ToolHookError("tool_error"))
        else:
            await safe_hook(hook, "after_execute_tool", context, call, output)
        return output

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
