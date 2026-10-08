# mini-learngraph

阶段 A 的 Python Agent MVP：在当前进程中持续对话，使用时间与计算工具，并把工具结果交回模型继续回答。内核依赖 httpx、Pydantic、pydantic-settings 和 tzdata。

调用路径是 **CLI → AgentLoop → AgentRunner → Provider / ToolRegistry**。Loop 管内存会话与上下文，Runner 管模型—工具循环；详细契约见 [架构](docs/ARCHITECTURE.md)。

## 安装与启动

安装 Python 3.11+ 和 [uv](https://docs.astral.sh/uv/getting-started/installation/)，在仓库根目录执行：

```powershell
uv sync --locked
Copy-Item .env.example .env
```

macOS/Linux 用 `cp .env.example .env`。编辑 `.env`，填入实际的模型地址、模型 ID 和密钥：

```dotenv
MINI_LEARNGRAPH_MODEL_BASE_URL=https://api.example.com/v1
MINI_LEARNGRAPH_MODEL_ID=your-model-id
MINI_LEARNGRAPH_MODEL_API_KEY=replace-me
MINI_LEARNGRAPH_MAX_STEPS=8
MINI_LEARNGRAPH_REQUEST_TIMEOUT_SECONDS=60
MINI_LEARNGRAPH_CONNECT_TIMEOUT_SECONDS=10
MINI_LEARNGRAPH_READ_TIMEOUT_SECONDS=60
```

适配器支持非流式 OpenAI Chat Completions 兼容协议，向 base URL 追加 `/chat/completions`；模型需要支持 function tools。配置从项目根目录 `.env` 读取，也可由同名环境变量覆盖。示例值是占位符，需要替换；不要提交 `.env`。

```powershell
uv run python -m mini_learngraph.cli
```

加 `--trace` 可观察当前轮的模型与工具生命周期，默认关闭：

```powershell
uv run python -m mini_learngraph.cli --trace
```

每轮创建独立 TraceHook 和临时显示 ID。Trace 写入 stderr，答案与原 CLI 提示仍在 stdout；只包含模型/工具标识、消息与调用计数、单调时钟耗时、结束原因和错误类别，不输出实参、工具结果、异常文本、用户资料或私有推理。工具准备失败只显示错误，未实际执行时不显示 started 或执行耗时。

Trace 观察 Runner，耗时不含 Loop 的上下文获取与历史更新。上下文获取失败由 CLI 显示 `Error [context_error]`，没有 Runner Trace；取消会继续传播，清理信息尽力写出。Trace 不存文件，不连接外部平台，进程退出后不保留记录。接口与离线验证见 [Trace CLI 接入计划](docs/exec-plans/completed/trace-cli.md)。

输入问题后等待本轮完成，再输入下一轮。可尝试“查询上海当前时间”“计算 (12 + 8) / 5”“查询 UTC 时间并计算 17 * 23”，随后问“刚才计算结果再加 10 呢”。

- `/reset` 清空当前对话历史，保留工具和指令。
- `/exit` 或输入结束（EOF）退出，Ctrl+C 停止并退出进程。
- 缺少模型配置时 CLI 给出提示；安装、内核使用和桩测试不需要密钥。

历史只在内存中，进程退出后丢失。失败轮次不加入历史；工具错误回传模型，让模型在剩余请求预算内修正。默认最多请求模型 8 次，最后一次请求发出工具调用时返回轮数限制并停止工具执行。每次模型请求有总超时，异步工具默认限时 10 秒；不自动重试。

## 默认工具和接入方式

| 工具 | 参数 | 行为 |
| --- | --- | --- |
| `get_current_time` | `timezone`，默认 `UTC` | IANA 时区和带偏移的 ISO 8601 时间 |
| `calculate` | `expression` | 数字、括号、一元正负号和 `+ - * /`；受限 AST，不执行代码 |

学习扩展只保留三个接入点：Loop 的 `instructions`、无参同步或异步 `context_provider`（返回文本或 `None`），以及 Runner 的工具注册表。上下文文本由调用者带上目标/节点标识，按轮次存成数据快照。注册工具使用 `Tool(name, description, parameters, execute)`：Pydantic 参数模型需 `extra="forbid"`，异步函数返回文本，可预期错误抛 `ToolExecutionError`。阶段 B/C 暂未实现。

`await ToolRegistry.execute(call)` 的返回类型已从 `str` 改为 `ToolResult`。直接调用者应读取结果的 `.text` 获取文本，用 `.is_error` 判断错误状态；原先对返回值调用的字符串方法应改为对 `.text` 调用，不能通过文本是否包含 `Error` 判断状态。注册的工具函数仍返回 `str`，由注册表包装为 `ToolResult`。

```python
from mini_learngraph import AgentLoop, AgentRunner
from mini_learngraph.tools import default_tools

# provider 实现 async chat(messages, tools) -> ModelResponse。
runner = AgentRunner(provider=provider, tools=default_tools(), max_steps=8)
loop = AgentLoop(runner=runner, instructions="用中文回答。")
result = await loop.process("计算 (12 + 8) / 5")
print(result.final_text)
if result.error:
    print(result.stop_reason, result.error)
```

程序调用可使用 `from mini_learngraph import TraceHook`，然后 `await loop.process("计算 2 + 3", hook=TraceHook())`。每次调用创建新实例；也可向 `runner.run(messages, hook=TraceHook())` 传入观察器，原来的无 Hook 调用继续有效。

## 验证

无需配置模型，直接运行：

```powershell
uv run pytest
```

固定模型桩验证工具循环、多轮消息配对、参数修正、错误与轮数预算、上下文快照、失败历史处理和 CLI。Trace 测试额外检查默认关闭、输出流与隐私、每轮隔离、工具计时、准备失败以及模型/工具错误和取消路径。Provider 测试使用 HTTP MockTransport，验证兼容协议、超时与客户端生命周期，不连接真实模型。

真实模型验证状态和离线验收结果分别见 [阶段 A 验收记录](docs/exec-plans/completed/agent-mvp.md)。2026-10-08 使用 `gpt-6.1-sol` 通过时间查询、计算、同一响应两个工具调用和依赖上文的追问，并验证 CLI 计算、重置与退出。此结果单独记录，不把固定响应或 HTTP 模拟计为真实验证。

## 开发准备

仓库工具需要 Node.js 22+、Git、uv；完整测试与打包还需要 tar，无需安装 npm 依赖。

```powershell
npm.cmd run ci
npm.cmd run release-package
```

`npm.cmd run ci` 执行文档/仓库/Action 检查、Node.js 回归测试和 Python 验收测试。macOS/Linux 使用 `npm`。源码包包含 Python 内核、锁文件、配置示例和测试，排除本地环境及缓存。Windows 环境问题见 [使用说明](docs/WINDOWS.md)。

## 项目约定

- 从 [AGENTS.md](AGENTS.md) 查阅相关规则。
- 架构边界见 [ARCHITECTURE.md](docs/ARCHITECTURE.md)，验证入口见 [CI/CD](docs/CICD.md)。
- 新增的计划、history 和学习记录只记本项目的事实。
