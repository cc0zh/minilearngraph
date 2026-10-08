"""OpenAI-compatible model transport and conversion to the kernel protocol."""

import asyncio
import json
from typing import Any, Protocol

import httpx

from .config import Settings
from .types import Message, ModelResponse, ToolCall


class InvalidResponseError(Exception):
    """The model response does not satisfy the supported message protocol."""


class ModelError(Exception):
    """A model request failed; its message is safe to display to the user."""


class ModelProvider(Protocol):
    async def chat(self, messages: list[Message], tools: list[dict]) -> ModelResponse:
        ...


def _message_payload(message: Message) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments, ensure_ascii=False, allow_nan=False),
                },
            }
            for call in message.tool_calls
        ]
    if message.tool_call_id is not None:
        payload["tool_call_id"] = message.tool_call_id
    return payload


def _reject_constant(value: str) -> None:
    raise ValueError("Non-finite JSON number")


def _parse_response(payload: Any) -> ModelResponse:
    if not isinstance(payload, dict):
        raise InvalidResponseError("Model response must be an object.")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise InvalidResponseError("Model response has no valid choice.")
    choice = choices[0]
    message = choice.get("message")
    reason = choice.get("finish_reason")
    if not isinstance(message, dict) or message.get("role") != "assistant":
        raise InvalidResponseError("Model response has no assistant message.")
    if not isinstance(reason, str) or reason not in {"stop", "tool_calls", "length", "content_filter"}:
        raise InvalidResponseError("Model response has an unsupported finish reason.")
    content = message.get("content")
    if content is not None and not isinstance(content, str):
        raise InvalidResponseError("Model response content must be text.")
    usage = payload.get("usage")
    if usage is not None and not isinstance(usage, dict):
        raise InvalidResponseError("Model response usage must be an object.")
    # Truncated/filtered tool arguments may be incomplete; never execute them.
    if reason in {"length", "content_filter"}:
        return ModelResponse(content, [], reason, usage)
    raw_calls = message.get("tool_calls", [])
    if raw_calls is None:
        raw_calls = []
    if not isinstance(raw_calls, list):
        raise InvalidResponseError("Model tool calls must be a list.")
    if (reason == "tool_calls" and not raw_calls) or (reason == "stop" and raw_calls):
        raise InvalidResponseError("Model finish reason disagrees with its tool calls.")
    calls: list[ToolCall] = []
    seen_ids: set[str] = set()
    for raw in raw_calls:
        if not isinstance(raw, dict) or raw.get("type") != "function":
            raise InvalidResponseError("Model tool call must be a function call.")
        call_id = raw.get("id")
        function = raw.get("function")
        if not isinstance(call_id, str) or not call_id.strip() or call_id in seen_ids:
            raise InvalidResponseError("Model tool call IDs must be present and unique.")
        if not isinstance(function, dict):
            raise InvalidResponseError("Model tool call has no function.")
        name = function.get("name")
        arguments = function.get("arguments")
        if not isinstance(name, str) or not name.strip() or not isinstance(arguments, str):
            raise InvalidResponseError("Model tool call has invalid name or arguments.")
        try:
            parsed = json.loads(arguments, parse_constant=_reject_constant)
        except (ValueError, RecursionError):
            raise InvalidResponseError("Model tool arguments must be valid JSON.") from None
        if not isinstance(parsed, dict):
            raise InvalidResponseError("Model tool arguments must be a JSON object.")
        seen_ids.add(call_id)
        calls.append(ToolCall(call_id, name, parsed))
    return ModelResponse(content, calls, reason, usage)


class OpenAIProvider:
    def __init__(self, config: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._config = config
        self._owns_client = client is None
        self._client = client if client is not None else httpx.AsyncClient()

    @property
    def model_id(self) -> str:
        return self._config.model_id

    async def chat(self, messages: list[Message], tools: list[dict]) -> ModelResponse:
        payload: dict[str, Any] = {
            "model": self._config.model_id,
            "messages": [_message_payload(message) for message in messages],
        }
        if tools:
            payload["tools"] = tools
        timeout = httpx.Timeout(
            self._config.request_timeout_seconds,
            connect=self._config.connect_timeout_seconds,
            read=self._config.read_timeout_seconds,
        )
        try:
            async with asyncio.timeout(self._config.request_timeout_seconds):
                response = await self._client.post(
                    f"{self._config.model_base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._config.model_api_key.get_secret_value()}"},
                    json=payload,
                    timeout=timeout,
                )
                response.raise_for_status()
                try:
                    body = response.json()
                except (ValueError, RecursionError):
                    raise InvalidResponseError("Model response must be valid JSON.") from None
        except (TimeoutError, httpx.TimeoutException):
            raise ModelError("Model request timed out.") from None
        except httpx.HTTPStatusError as error:
            raise ModelError(f"Model request failed (HTTP {error.response.status_code}).") from None
        except httpx.HTTPError:
            raise ModelError("Model request failed.") from None
        return _parse_response(body)

    async def aclose(self) -> None:
        """Close an owned client; injected clients remain owned by their caller."""
        if self._owns_client:
            await self._client.aclose()
