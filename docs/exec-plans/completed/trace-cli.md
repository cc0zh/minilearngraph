# CLI TraceHook 接入

## 目标与范围

按 [架构 §5.2](../../ARCHITECTURE.md) 与 [内核交接契约](../completed/trace-kernel-hook.md) 接入临时 TraceHook 和默认关闭的 `--trace`。仅更改 CLI、TraceHook、导出、测试和说明文档，不修改内核执行语义，不增加依赖、持久化或外部平台。

## 步骤与验证

- [x] 核对 Hook 字段、CLI 默认行为与编码规范。
- [x] 实现 stderr Trace、每轮独立实例与 CLI 开关；用固定模型验证默认关闭、输出流、多轮和 context_error。
- [x] 覆盖计时、准备失败、执行错误和取消；检查敏感负载不出现在 Trace。
- [x] 运行相关回归、CI、类型检查与差异检查，记录实际结果并交严审独立验证。

## 技术决定

- 工具计时由 TraceHook 的单调时钟字典按 call.id 保存，准备失败无起点，因此不显示 started 或虚构执行耗时。
- 临时显示 ID 每实例生成；默认调用不向原 process/interact/run_cli 传入新关键字，保持原调用兼容。
- 只选取契约中的元数据；标识使用 JSON 字符串转义防止换行或终端控制符注入。未知 finish_reason 归为 unknown，避免无效响应文本泄露。
- on_finally 尽力显示清理和未结束工具，finally 清空计时字典；context_error 只由 CLI 错误展示，不制造 Runner 事件。
- CLI 原有 Settings() 从环境载入必填字段，Pyright 会将这些字段误判为必填调用参数；仅该行增加有理由的 reportCallIssue 注释。原 CLI 普通异常边界按架构保留，并添加有理由的 BLE001 注释；导出排序与 subprocess 的显式 check=False 仅满足检查，不改变运行行为。

## 验证与交接

- `uv run --locked pytest tests/test_trace.py tests/test_cli.py -q`：31 passed。新增 22 项回归覆盖元数据隐私、stderr/stdout、默认关闭、每轮新实例、非负时钟、多工具 call.id 配对、准备失败、预期/未预期错误、超时、真实任务取消、退出与写流失败清理。
- `npm.cmd run ci`：217 项 Python、19 项 Node 测试通过，文档、仓库卫生、Actions 和脚本检查通过。
- `uvx --from pyright pyright --pythonpath .venv/Scripts/python.exe mini_learngraph/trace.py mini_learngraph/cli.py mini_learngraph/__init__.py`：0 errors、0 warnings。
- `uvx --from ruff ruff check mini_learngraph/trace.py mini_learngraph/cli.py mini_learngraph/__init__.py tests/test_trace.py tests/test_cli.py`：All checks passed。只临时调用工具，未新增项目依赖或修改构建配置。
- `uv run --locked python -m compileall -q mini_learngraph tests` 与本阶段文件 `git diff --check`：通过。
- 离线交互示例实际得到答案 `5`，stderr 显示两次模型请求、一次 calculate 开始/成功、计数及 completed 和 cleanup。示例见下方；固定模型演示不代表真实模型验证，本阶段未新增真实模型验证。
- 未改 ARCHITECTURE.md 及内核业务实现。已有 tools.py AST 类型收窄问题不在本阶段修改范围，内核计划中保留记录。
- 实现与本地自检已交接；最终验收由派单人与严审独立确认。

### 文件

`mini_learngraph/trace.py`、`mini_learngraph/cli.py`、`mini_learngraph/__init__.py`、`tests/test_trace.py`、`tests/test_cli.py`、`README.md`、本计划、[history](../../histories/2026-10/20261008-2011-trace-cli.md) 与 [学习速记](../../learnings/2026-10/trace-metadata-and-local-timers.md)。

### 可复制运行

真实交互入口（使用 README 的模型配置）：

```powershell
uv run --locked python -m mini_learngraph.cli --trace
```

输入“计算 2 + 3”，再输入 `/reset`、另一问题及 `/exit`，验证每个真实问题获得不同显示 ID，答案在 stdout，跟踪在 stderr。默认入口去掉 `--trace` 后不应有跟踪。

不使用密钥的 PowerShell 离线示例，从仓库根目录运行；通过 stdin 传递代码，避免 Windows python -c 的引号重解析：

```powershell
$traceDemoScript = @'
import asyncio
from mini_learngraph.cli import interact
from mini_learngraph import AgentLoop, AgentRunner
from mini_learngraph.tools import default_tools
from mini_learngraph.types import ToolCall
from tests.fakes import FixedProvider, answer, calls
async def demo():
    inputs = iter(["calculate 2 + 3", "/exit"])
    provider = FixedProvider(calls(ToolCall("demo-1", "calculate", {"expression": "2 + 3"})), answer("5"))
    await interact(AgentLoop(AgentRunner(provider, default_tools()), "help"), lambda _: next(inputs), trace_enabled=True)
asyncio.run(demo())
'@
$traceDemoScript | uv run --locked python -
```

独立复核的逐条验收、实际命令结果和门禁问题见 [Trace 独立验收记录](../../exec-runs/trace/execution-summary.md)。
