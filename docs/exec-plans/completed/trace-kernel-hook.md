# Trace 内核 Hook 与工具生命周期

## 目标、范围与风险

- 按 ARCHITECTURE.md §5.2 实现默认空异步 AgentHook、独立精简快照、Runner/Loop 可选 Hook 与工具准备/执行生命周期。
- 保持 AgentResult、模型请求预算、消息配对及失败不入历史语义；不修改 CLI、TraceHook、README，不增加持久化、回放或平台集成。
- 风险：Registry.execute 从文本迁移为 ToolResult；准备失败不能计为执行，取消/退出不能被普通异常隔离吞掉，finally 不能遗漏迭代。
- 已授权本地实现、回归和文档同步；无迁移、发布或外部写入。

## 进度与决定

- [x] 读取架构、编码规则、计划规范与内核直接依赖。
- [x] 定义 Hook/context、ToolResult 与错误类别契约；尝试直接同步阿岚被代理权限拒绝，最终通过派单人交接。
- [x] 实现工具准备和 Runner/Loop 生命周期；126 项内核回归通过，消息、预算和历史保持兼容。
- [x] 更新旧测试，增加关键生命周期回归，运行相关检查。
- [x] 写 history 与学习记录，准备 CLI 接入及独立审查交接；本阶段实现完成，不代替最终验收。
- 快照使用独立数据副本；仅提供标识、计数、耗时和错误类别，Hook 修改副本不影响执行。
- 已知工具错误继续回传模型，未预期工具异常仍返回 tool_error；Runner 本身未预期异常传播。
- OpenAIProvider 新增只读 model_id 属性，避免 Runner 读取私有配置；其他 Provider 无该属性时快照为 None，不强迫原 ModelProvider 实现改接口。
- ToolHookError 只传类别，不把异常对象及其文本交给 Trace。已知工具错误统一为 tool_error，未预期工具错误为异常类名；工具摘要保留 call_id/name/is_error/error_type。
- safe_hook 每次 deepcopy 参数，只捕获 Exception；取消与退出异常向上传播。迭代 finally 始终收尾；受控失败按 on_error → after_run → on_finally，未预期 Runner 异常按 on_error → on_finally 后传播；取消只进入运行 on_finally。

## 验收与交接

- 已执行 `uv run --locked pytest tests/test_hook.py tests/test_runner.py tests/test_loop.py tests/test_tools.py -q`：126 passed。包含实际任务取消、参数只校验一次、恶意 Hook 修改/抛错、结果含 Error 但成功、超时与异常、旧预算/历史/配对回归。
- `npm.cmd run ci`：文档骨架、仓库卫生、Actions 固定版本和脚本检查通过，19 项 Node 仓库工具测试与 195 项 Python 全量测试通过。
- `uv run --locked python -m compileall -q mini_learngraph tests`：通过。
- `uvx --from pyright pyright --pythonpath .venv/Scripts/python.exe mini_learngraph/hook.py mini_learngraph/runner.py mini_learngraph/loop.py mini_learngraph/types.py mini_learngraph/provider.py mini_learngraph/__init__.py`：0 errors，0 warnings。
- 在同一 Pyright 命令中加入 tools.py 时有 1 个原有错误：AST Constant 的 `_ConstantValue` 不能自动收窄为 int|float（当前 tools.py:125）。`git show HEAD:mini_learngraph/tools.py` 确认该表达式原已存在且本次未改动，不扩大修复范围；运行时计算器边界回归均通过。
- `git diff --check -- mini_learngraph tests docs/exec-plans docs/histories docs/learnings`：通过。本任务范围外原有 ARCHITECTURE.md 改动有末尾空行提示，本次未修改该文件。
- 真实模型验证不在本子任务范围；完成后由严审独立复核。

### CLI 接入契约

- `mini_learngraph.hook.AgentHook` 默认九个空异步方法，名称与架构 §5.2 一致。`Runner.run(messages, hook=None)` 和 `Loop.process(user_input, hook=None)` 保持原默认调用；Loop 只透传，不额外发事件。领域上下文失败不触发 Runner Hook。
- `RunHookContext`：`stop_reason: str | None`、`error_type: str | None`、`model_calls: int`、`duration_ms: float`。before_run 初值为空/0；after_run 获得完成或受控失败；on_finally 获得最终耗时。
- `StepHookContext`：`iteration: int`（从 1 开始）、`model_id: str | None`、`message_count: int`（请求前）、`model_duration_ms: float`、`finish_reason: str | None`、`tools: tuple[ToolHookSummary, ...]`、`error_type: str | None`。未取得响应时 finish_reason=None，耗时使用单调时钟，单位毫秒。
- `ToolHookSummary`：`call_id: str`、`name: str`、`is_error: bool`、`error_type: str | None`；不含实参、文本或异常。
- 工具回调都先传 StepHookContext、再传 ToolCall 副本；成功回调第三参为 `ToolResult(text: str, is_error: bool=False)`，错误回调第三参为 `ToolHookError(error_type: str)`。Trace 只读 call.id/name，不打印 call.arguments 或 result.text。
- Run/Step 受控失败 error_type 为 AgentResult.stop_reason（model_error、invalid_response、output_truncated、content_filtered、empty_response、step_limit、tool_error）；成功为 None。取消 stop_reason/error_type=cancelled；Runner 未预期异常 stop_reason=unexpected_error、error_type=异常类名；退出 stop_reason=interrupted、error_type=KeyboardInterrupt/SystemExit。
- 工具已知错误（未知名称、参数校验、预期执行失败、超时）的错误回调类别为 tool_error；工具实现异常为异常类名，随后 AgentResult 为 tool_error。取消不会触发工具错误回调。
- `ToolRegistry.prepare_call(call)` 同步返回 PreparedToolCall(tool, parameters) 或 ToolResult 错误；`execute_prepared(prepared)` 异步返回 ToolResult；原 `execute(call)` 仍负责准备与执行，但返回类型已从 str 变为 ToolResult。
- 每次 Hook 获取独立快照；Trace 如需跨回调记录工具耗时，使用自己的 call.id 字典，不依赖上下文对象身份，不持有可变执行状态。

### 文件与后续验证

- 实现：`mini_learngraph/hook.py`、`runner.py`、`loop.py`、`tools.py`、`types.py`、`__init__.py`，以及 `provider.py` 的 model_id 属性。
- 回归：新增 `tests/test_hook.py`；更新 `tests/test_runner.py`、`tests/test_tools.py`、`tests/test_loop.py` 适应 ToolResult 与 hook 参数。
- 文档：本计划、`docs/histories/2026-10/20261008-1953-trace-kernel-hook.md`、`docs/learnings/2026-10/async-observer-lifecycle.md`。
- 后续由阿岚完成 CLI/TraceHook，并由严审独立验证输出安全与生命周期；本子任务未修改 cli.py、trace.py 或 README。

独立复核的逐条验收、实际命令结果和门禁问题见 [Trace 独立验收记录](../../exec-runs/trace/execution-summary.md)。
