"""Interactive, sequential CLI: python -m mini_learngraph.cli."""

import argparse
import asyncio
import sys
from collections.abc import Callable

from pydantic import ValidationError

from .config import Settings
from .loop import AgentLoop
from .provider import OpenAIProvider
from .runner import AgentRunner
from .tools import default_tools
from .trace import TraceHook

DEFAULT_INSTRUCTIONS = (
    "You are a helpful assistant. Use the registered tools for current time and "
    "arithmetic. If a tool reports an error, correct its arguments when possible. "
    "Answer in the user's language."
)


async def interact(
    loop: AgentLoop,
    read_input: Callable[[str], str] = input,
    write: Callable[[str], None] = print,
    *,
    trace_enabled: bool = False,
) -> None:
    write("mini-learngraph · /reset 清空历史 · /exit 退出")
    while True:
        try:
            user_input = read_input("you> ").strip()
        except EOFError:
            return
        if user_input == "/exit":
            return
        if user_input == "/reset":
            loop.reset()
            write("历史已清空。")
            continue
        if not user_input:
            continue
        try:
            if trace_enabled:
                result = await loop.process(user_input, hook=TraceHook())
            else:
                result = await loop.process(user_input)
        except Exception:  # noqa: BLE001 -- CLI boundary keeps the next turn available.
            write("Error: 本轮处理失败，请重试或 /reset。")
            continue
        if result.final_text:
            write(result.final_text)
        if result.error:
            write(f"Error [{result.stop_reason}]: {result.error}")


async def run_cli(settings: Settings, *, trace_enabled: bool = False) -> None:
    provider = OpenAIProvider(settings)
    try:
        runner = AgentRunner(provider, default_tools(), max_steps=settings.max_steps)
        loop = AgentLoop(runner, DEFAULT_INSTRUCTIONS)
        if trace_enabled:
            await interact(loop, trace_enabled=True)
        else:
            await interact(loop)
    finally:
        await provider.aclose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="mini-learngraph interactive agent")
    parser.add_argument("--trace", action="store_true", help="print lifecycle metadata to stderr")
    args = parser.parse_args(argv)
    try:
        # BaseSettings fills required fields from the environment, not call arguments.
        settings = Settings()  # pyright: ignore[reportCallIssue]
    except ValidationError as exc:
        fields = ", ".join(".".join(map(str, error["loc"])) for error in exc.errors())
        print(f"配置无效或缺失：{fields}。请按 .env.example 配置项目根目录的 .env。", file=sys.stderr)
        return 2
    try:
        if args.trace:
            asyncio.run(run_cli(settings, trace_enabled=True))
        else:
            asyncio.run(run_cli(settings))
    except KeyboardInterrupt:
        print("\n已停止。")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
