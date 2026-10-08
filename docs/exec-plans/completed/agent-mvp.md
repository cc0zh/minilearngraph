# 阶段 A：Agent MVP

## 目标、范围与风险

- 依据 [架构](../../ARCHITECTURE.md) 实现 Python AgentLoop、AgentRunner、消息契约、OpenAI 兼容 Provider、工具注册表、两个默认工具和交互式 CLI。
- 学习能力仅提供 instructions/context/tools 接入点，不实现 B/C 阶段或运行持久化、状态机、队列、恢复等系统。
- 本地实现、环境安装和验收已获授权。模型配置不作为实现前置条件，真实模型验证与固定模型桩验证分别记录。
- 风险：非法模型响应触发工具、失败历史污染、计算阻塞、密钥进入错误信息。分别以响应全量校验、成功才提交历史、AST 复杂度限制和简短错误处理验证。

## 进度与决定

- [x] 核对架构、仓库规范和 Python/uv 环境。
- [x] 实现内核与 CLI；检查依赖方向为 CLI → Loop → Runner → Provider/Tools。
- [x] 使用固定模型桩验收直接回答、工具链、错误修正、协议错误、轮数预算、上下文和历史；使用 HTTP MockTransport 验收适配器。
- [x] 运行仓库检查，补齐启动说明、真实模型状态、history 和学习记录。
- 2026-10-08：以异步 Python 接口实现；Runner 每次运行仅使用局部状态，Loop 仅在 completed 时提交历史。保留现有仓库工具，业务依赖交由 uv 管理。
- 2026-10-08：审查发现并修复正常回答显式 null 工具列表、当前快照缺失时历史快照声明和 URL query/fragment 拼接问题，均补回归测试。
- 2026-10-08：用户补齐真实模型配置后，使用 gpt-6.1-sol 完成四个真实模型样例和 CLI 验证；应用代码无需调整。

## 交付文件与边界

- `mini_learngraph/loop.py` 与 `context.py`：指令、内存历史、同步/异步上下文，按成功轮次提交消息快照。
- `mini_learngraph/runner.py` 与 `types.py`：局部工作上下文、请求轮数、统一结果、响应全量校验、工具链配对与错误边界。
- `mini_learngraph/provider.py` 与 `config.py`：非流式 OpenAI Chat Completions 适配器、HTTP 客户端和总期限、根目录 .env 配置。
- `mini_learngraph/tools.py`：排序与精确名称注册、Pydantic Schema/实参校验、10 秒工具期限、受限 AST 计算与可替换时钟。
- `mini_learngraph/cli.py`：逐轮交互、结果和错误展示、reset/exit、取消退出、关闭 HTTP 客户端。
- `pyproject.toml`、`uv.lock`、`.env.example`、README 与 Python 测试；现有仓库检查接入 Python 验收，源码打包保留内核并排除缓存。
- 学习扩展仅提供 instructions/context/tools 接口，无学习领域实现，无 Web 框架/数据库或运行持久化系统。

## 验收与交接

### 固定模型桩与离线验收

- `uv sync --locked`：成功安装并校验锁文件。
- `npm.cmd run ci`：通过；Windows、Python 3.11.11 下 172 项 Python 测试、19 项 Node.js 测试通过，文档骨架、仓库卫生、Action 固定 SHA 与 Node.js 语法检查通过。
- `uv run --locked pytest -q`：此前 Python 3.13.2 下 167 项通过；随后 5 项审查回归在最终 Python 3.11 验收中通过。
- Python 测试包含直接回答、单工具、同轮多工具、多轮工具、参数修正、模型错误/总超时、非法响应、过滤/截断不执行工具、最大轮数、嵌套输入不变性、失败历史、连续追问、节点快照切换和缺失、reset、CLI 启动/退出/异常边界。
- 下一次模型请求中的实际 assistant/tool 消息和调用 ID 均有断言；不是只比较最终回答。工具时钟固定，Provider 使用 HTTP MockTransport，没有真实模型请求。
- 缺配置 CLI 启动有明确诊断；测试另用占位配置验证模块可启动并通过 /exit 或 EOF 退出，不将其计为真实模型验证。
- 源码包由现有 Node.js 回归验证包含 Python 内核、锁文件与配置示例，排除环境和缓存。
- `npm.cmd run release-package`：本地源码打包通过，生成 `dist/repo-metadata.tgz` 和 `dist/release-manifest.json`，未发布或部署。
- 改动的 7 份 Markdown 文档使用 markdownlint-cli2 0.20.0 检查通过；本地文件引用检查通过。

### 真实模型验证

状态：**四个样例均通过**。2026-10-08 用户补齐配置后，使用模型 `gpt-6.1-sol`、max_steps=8、单次请求总期限 60 秒验证。初次离线交付时缺少配置；本次验证独立于固定模型桩和 HTTP 模拟结果。未保存密钥、模型地址或请求头。

| 样例 | 模型 ID | 模型请求次数 | 工具与回答结果 |
| --- | --- | --- | --- |
| Asia/Shanghai 时间查询 | gpt-6.1-sol | 2 | 调用 get_current_time，返回并展示 `2026-10-08T19:07:52.334296+08:00` |
| 计算 (12 + 8) / 5 | gpt-6.1-sol | 2 | 调用 calculate，工具和回答均为 `4` |
| 同一任务查询 UTC 时间并计算 17 * 23 | gpt-6.1-sol | 2 | 同一个 assistant 响应包含两个工具调用；返回 `2026-10-08T11:08:03.527934+00:00` 和 `391`，模型汇总正确 |
| 上述会话追问“刚才的计算结果再加 10” | gpt-6.1-sol | 2 | 实际请求包含前轮回答；模型调用 calculate，实参为 `391 + 10`，工具和回答均为 `401` |

四个样例均通过真实 OpenAIProvider、AgentRunner、AgentLoop 和默认工具完成，停止原因为 completed，无模型或工具错误。临时验证脚本只在内存中检查实际请求的 assistant/tool 配对和 ID、工具结果、成功历史追加，并检查时间结果落在该轮开始与结束之间。前两例各自使用新会话，后两例复用同一 Loop。验证脚本未加入应用内核或默认测试，验证结束后删除。

另通过 `uv run --locked python -m mini_learngraph.cli` 传入计算输入、`/reset` 和 `/exit`，CLI 返回 `4`、显示历史已清空并正常退出。此次补验仅更新记录，未改应用代码，离线测试的 172/19 项结果沿用上节记录。

复验：按 [README](../../../README.md) 配置 `.env` 后执行 `uv run python -m mini_learngraph.cli`，依次输入上述样例，记录模型 ID、实际回答和工具使用结果，不保存密钥。本次通过证明该配置可完成这些样例，不代表所有兼容服务、模型或输入均已验证；协议异常、错误修正与取消等边界仍由离线验收覆盖。
