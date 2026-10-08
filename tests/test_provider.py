import asyncio
import copy
import json

import httpx
import pytest

from mini_learngraph.config import Settings
from mini_learngraph.provider import InvalidResponseError, ModelError, OpenAIProvider
from mini_learngraph.types import Message, ToolCall


def config(**overrides):
    return Settings(_env_file=None, model_base_url="https://model.example/v1", model_id="test-model", model_api_key="private-secret", **overrides)


def response(content="answer", reason="stop", calls=None):
    message = {"role": "assistant", "content": content}
    if calls is not None:
        message["tool_calls"] = calls
    return {"choices": [{"message": message, "finish_reason": reason}], "usage": {"total_tokens": 10}}


def tool_call(arguments='{"expression":"1+2"}', call_id="c1"):
    return {"id": call_id, "type": "function", "function": {"name": "calculate", "arguments": arguments}}


async def invoke(payload):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))) as client:
        return await OpenAIProvider(config(), client).chat([Message("user", "hello")], [])


async def test_request_conversion_response_and_input_immutability():
    messages = [
        Message("system", "instructions"), Message("user", "计算"),
        Message("assistant", None, [ToolCall("c1", "calculate", {"expression": "1+2"})]),
        Message("tool", "3", tool_call_id="c1"),
    ]
    tools = [{"type": "function", "function": {"name": "calculate"}}]
    original = copy.deepcopy((messages, tools))

    def handle(request):
        assert str(request.url) == "https://model.example/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer private-secret"
        body = json.loads(request.content)
        assert body["model"] == "test-model"
        assert body["tools"] == tools
        assert body["messages"][0] == {"role": "system", "content": "instructions"}
        assert body["messages"][1] == {"role": "user", "content": "计算"}
        assert body["messages"][2]["content"] is None
        assert json.loads(body["messages"][2]["tool_calls"][0]["function"]["arguments"]) == {"expression": "1+2"}
        assert body["messages"][3] == {"role": "tool", "content": "3", "tool_call_id": "c1"}
        assert request.extensions["timeout"]["connect"] == 10
        assert request.extensions["timeout"]["read"] == 60
        return httpx.Response(200, json=response())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        provider = OpenAIProvider(config(), client)
        result = await provider.chat(messages, tools)
        await provider.aclose()
        assert not client.is_closed
    assert result.content == "answer"
    assert result.finish_reason == "stop"
    assert result.tool_calls == []
    assert result.usage == {"total_tokens": 10}
    assert (messages, tools) == original


async def test_multiple_tool_response_conversion():
    result = await invoke(response(None, "tool_calls", [tool_call(), tool_call('{"expression":"3*4"}', "c2")]))
    assert result.content is None
    assert result.tool_calls == [ToolCall("c1", "calculate", {"expression": "1+2"}), ToolCall("c2", "calculate", {"expression": "3*4"})]


async def test_explicit_null_tool_calls_is_valid_for_normal_answer():
    payload = response("answer")
    payload["choices"][0]["message"]["tool_calls"] = None
    result = await invoke(payload)
    assert result.content == "answer" and result.tool_calls == []


async def test_explicit_null_tool_calls_is_invalid_for_tool_finish():
    payload = response(None, "tool_calls")
    payload["choices"][0]["message"]["tool_calls"] = None
    with pytest.raises(InvalidResponseError):
        await invoke(payload)


@pytest.mark.parametrize("reason", ["length", "content_filter"])
async def test_truncated_or_filtered_response_ignores_even_malformed_calls(reason):
    result = await invoke(response("partial text", reason, [tool_call("{broken")]))
    assert result.content == "partial text"
    assert result.finish_reason == reason
    assert result.tool_calls == []


@pytest.mark.parametrize("arguments", ["{broken", "[]", "null", '"string"', "1", '{"x":NaN}', '{"x":Infinity}', {"expression": "1"}])
async def test_invalid_tool_arguments_raise_protocol_error(arguments):
    with pytest.raises(InvalidResponseError):
        await invoke(response(None, "tool_calls", [tool_call(arguments)]))


@pytest.mark.parametrize("payload", [
    None, [], {}, {"choices": []}, {"choices": [None]},
    response("ok", "tool_calls", []), response("ok", "stop", [tool_call()]),
    response("ok", "unknown"), response("ok", []), response(123),
    response(None, "tool_calls", [tool_call(call_id="")]),
    response(None, "tool_calls", [tool_call(), tool_call()]),
    response(None, "tool_calls", [None]),
    response(None, "tool_calls", [{"id": "c", "type": "function", "function": None}]),
    response(None, "tool_calls", [{"id": "c", "type": "other", "function": {}}]),
    response(None, "tool_calls", [{"id": "c", "type": "function", "function": {"name": "", "arguments": "{}"}}]),
])
async def test_invalid_response_shapes(payload):
    with pytest.raises(InvalidResponseError):
        await invoke(payload)


async def test_non_json_response_is_protocol_error():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, text="private-secret invalid json"))) as client:
        with pytest.raises(InvalidResponseError) as error:
            await OpenAIProvider(config(), client).chat([], [])
    assert "private-secret" not in str(error.value)


@pytest.mark.parametrize("status", [401, 429, 500])
async def test_http_failure_is_short_and_safe(status):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(status, text="private-secret external failure"))) as client:
        with pytest.raises(ModelError) as error:
            await OpenAIProvider(config(), client).chat([], [])
    assert str(error.value) == f"Model request failed (HTTP {status})."


@pytest.mark.parametrize("error_type,expected", [(httpx.ConnectError, "Model request failed."), (httpx.ReadTimeout, "Model request timed out.")])
async def test_transport_error_is_safe(error_type, expected):
    def fail(request):
        raise error_type("private-secret Authorization external details", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as client:
        with pytest.raises(ModelError) as error:
            await OpenAIProvider(config(), client).chat([], [])
    assert str(error.value) == expected


async def test_total_request_deadline_even_if_transport_has_no_timeout():
    async def block(request):
        await asyncio.Event().wait()
        return httpx.Response(200, json=response())

    async with httpx.AsyncClient(transport=httpx.MockTransport(block)) as client:
        provider = OpenAIProvider(config(request_timeout_seconds=0.01), client)
        with pytest.raises(ModelError, match="timed out"):
            await provider.chat([], [])


async def test_cancellation_propagates():
    started = asyncio.Event()

    async def block(request):
        started.set()
        await asyncio.Event().wait()
        return httpx.Response(200, json=response())

    async with httpx.AsyncClient(transport=httpx.MockTransport(block)) as client:
        task = asyncio.create_task(OpenAIProvider(config(), client).chat([], []))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


async def test_owned_client_is_closed():
    provider = OpenAIProvider(config())
    await provider.aclose()
    assert provider._client.is_closed
