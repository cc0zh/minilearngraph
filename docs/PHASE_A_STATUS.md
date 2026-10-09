# 阶段 A 状态与验收范围

阶段 A 的 Agent MVP 和轻量 Trace 已实现，阶段 B/C 尚未开展。内核职责见 [架构](ARCHITECTURE.md)，安装和交互入口见 [README](../README.md)。

## 已实现能力

| 能力 | 实现与测试证据 |
| --- | --- |
| 会话、上下文快照、成功历史与 reset | [Loop](../mini_learngraph/loop.py)、[会话回归](../tests/test_loop.py) |
| 模型—工具循环、消息配对、响应校验与请求预算 | [Runner](../mini_learngraph/runner.py)、[执行回归](../tests/test_runner.py) |
| OpenAI 兼容协议、总超时与客户端生命周期 | [Provider](../mini_learngraph/provider.py)、[HTTP 模拟回归](../tests/test_provider.py) |
| 时间、受限 AST 计算、参数校验与工具超时 | [工具注册表](../mini_learngraph/tools.py)、[工具回归](../tests/test_tools.py) |
| CLI、可选 Trace、输出隐私与取消清理 | [CLI 回归](../tests/test_cli.py)、[Hook 回归](../tests/test_hook.py)、[Trace 回归](../tests/test_trace.py)、[独立验收回归](../tests/test_trace_acceptance.py) |

## 验证状态

- 2026-10-09 收尾前复查：Windows、Python 3.11.11 下，232 项 Python 和 19 项 Node 测试通过；Markdownlint 0.22.0 检查 57 文件、0 错误。
- 2026-10-09 收尾 CI：232 项 Python、21 项 Node 测试通过；新增固定版本 Ruff 0.16.10 / Pyright 1.1.414 门禁，全量应用检查均通过，Pyright 为 0 errors / 0 warnings。
- Markdownlint 0.22.0 检查最终 58 份仓库文档，0 错误；配置排除虚拟环境和生成目录，避免扫描新安装的 Pyright 第三方文档，仓库规则未放宽。源码包本地文档链接检查通过，全部 109 份包内文件已与工作区逐字节核对；详细证据位于源码包中的 `docs/exec-plans/completed/phase-a-closeout.md`。
- 原 Trace 的独立验收详录位于 `docs/exec-runs/trace/execution-summary.md`；开发计划、history 与学习记录随源码包保留，初始化模板省略任务记录。

## 真实模型证据

2026-10-08 的 [阶段 A 完成计划](exec-plans/completed/agent-mvp.md) 记录模型 `gpt-6.1-sol` 通过时间查询、计算、同一响应两个工具调用和依赖上文的追问，另验证 CLI 计算、reset 和退出。

Trace 独立验收记录另收录用户提供的一次真实 calculate 日志，只支持该次计算工具链。固定模型桩、HTTP 模拟和此次收尾均不能扩大为新的真实模型验证。

## 交付边界

历史只在当前进程内存中；非流式、顺序交互，不自动重试、不持久化或恢复。学习能力仅保留 instructions/context/tools 接入点。阶段 B 将验证节点讲解与练习反馈，阶段 C 按实际需求决定服务化范围。

本地验证不代表远端 GitHub Actions 的 Ubuntu/macOS/Windows 矩阵均已运行。质量状态见 [质量评分](QUALITY_SCORE.md)，剩余工程事项见 [技术债追踪](exec-plans/tech-debt-tracker.md)。
