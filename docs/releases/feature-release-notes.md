# 功能发布记录

按 [记录说明](README.md) 维护。外部发布状态以 GitHub Release 和相应发布计划的核验记录为准；历史行中的“未发布”描述的是当时操作。

## 2026-10

| 日期 | 版本 | 功能域 | 用户价值 | 变更摘要 |
| --- | --- | --- | --- | --- |
| 2026-10-09 | v0.2.0 | B1 本机目标与图谱、CLI Trace | 在 Web 中澄清学习目标，编辑和明确发布图谱；刷新或重启后保留资产 | 新增 FastAPI/SQLite 与 React Web、严格模型 JSON、revision 并发保护、图谱历史和本机安全边界；保留 CLI 并加入可选 Trace。B2–B4 未实现，真实 B1 模型效果未验证。三平台CI、源码包/SBOM/provenance核验通过，已发布 [GitHub Release](https://github.com/cc0zh/minilearngraph/releases/tag/v0.2.0)；说明见 [v0.2.0](v0.2.0.md)。 |
| 2026-10-09 | 未标记（工作区） | 阶段 A 收尾 | 源码包文档可访问，应用静态检查成为日常门禁 | 同步质量与技术债状态；保留错误与取消语义，修复数值类型诊断；源码包保留项目记录并检查本地文档链接。验证结果见 [阶段 A 状态](../PHASE_A_STATUS.md)，本次不提交、推送、发布或新增 tag。 |
| 2026-10-08 | 未标记（本地提交） | CLI Trace | 使用 `--trace` 查看当前轮模型与工具步骤、耗时及停止原因，答案仍在 stdout | 默认关闭、每轮独立实例，Trace 仅将元数据写入 stderr，无持久化；直接调用 `ToolRegistry.execute` 的代码需读取 `ToolResult.text/is_error`。232 项 Python、19 项 Node 独立验收通过，固定版本 Markdown 门禁补修通过；用户日志另支持一次真实 calculate 链路。验收范围见 [阶段 A 状态](../PHASE_A_STATUS.md)，详录位于仓库的 `docs/exec-runs/trace/execution-summary.md`，无 push、发布或新 tag。 |
| 2026-10-08 | v0.1.0 | Agent MVP | 在 CLI 中持续对话，查询当前时间、计算表达式，并根据上文继续追问 | 首次版本包含 AgentLoop 与 AgentRunner、OpenAI 兼容模型适配器、两个默认工具、内存上下文、`/reset` 和 `/exit`；离线测试 172 项 Python、19 项 Node.js 通过，真实模型 gpt-6.1-sol 四个样例和 CLI 验证通过。 |

安装与启动见 [项目 README](../../README.md)，离线与真实模型的独立验收证据见 [阶段 A 完成计划](../exec-plans/completed/agent-mvp.md)。
