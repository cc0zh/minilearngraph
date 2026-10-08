"""Fixed model responses with captured request snapshots."""

from copy import deepcopy

from mini_learngraph.types import Message, ModelResponse, ToolCall


class FixedProvider:
    def __init__(self, *responses: ModelResponse | BaseException) -> None:
        self.responses = list(responses)
        self.requests: list[tuple[list[Message], list[dict]]] = []

    async def chat(self, messages: list[Message], tools: list[dict]) -> ModelResponse:
        self.requests.append((deepcopy(messages), deepcopy(tools)))
        if not self.responses:
            raise AssertionError("Unexpected model request")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return deepcopy(response)


def answer(text: str = "done") -> ModelResponse:
    return ModelResponse(text, [], "stop")


def calls(*tool_calls: ToolCall, content: str | None = None) -> ModelResponse:
    return ModelResponse(content, list(tool_calls), "tool_calls")
