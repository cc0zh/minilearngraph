"""Own one in-memory conversation and obtain fresh domain context per turn."""

import inspect
from collections.abc import Awaitable, Callable
from copy import deepcopy

from .context import build_messages
from .runner import AgentRunner
from .types import AgentResult, Message

ContextProvider = Callable[[], str | None | Awaitable[str | None]]


class AgentLoop:
    def __init__(
        self,
        runner: AgentRunner,
        instructions: str,
        context_provider: ContextProvider | None = None,
    ) -> None:
        self.runner = runner
        self.instructions = instructions
        self.context_provider = context_provider
        self.history: list[Message] = []

    async def process(self, user_input: str) -> AgentResult:
        context = None
        if self.context_provider is not None:
            try:
                context = self.context_provider()
                if inspect.isawaitable(context):
                    context = await context
                if context is not None and not isinstance(context, str):
                    raise TypeError("Context must be text or None")
            except Exception:
                return AgentResult("", [], "context_error", "Could not load domain context.")

        messages = build_messages(self.instructions, self.history, user_input, context)
        # Keep the exact current user message, independent of Runner's working copy.
        user_message = deepcopy(messages[-1])
        result = await self.runner.run(messages)
        if result.stop_reason == "completed":
            self.history.extend([user_message, *deepcopy(result.messages)])
        return result

    def reset(self) -> None:
        self.history.clear()
