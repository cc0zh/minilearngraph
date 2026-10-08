# 功能发布记录

按 [记录说明](README.md) 维护。当前版本保存在本地 Git，尚未推送或发布到外部平台。

## 2026-10

| 日期 | 版本 | 功能域 | 用户价值 | 变更摘要 |
| --- | --- | --- | --- | --- |
| 2026-10-08 | v0.1.0 | Agent MVP | 在 CLI 中持续对话，查询当前时间、计算表达式，并根据上文继续追问 | 首次版本包含 AgentLoop 与 AgentRunner、OpenAI 兼容模型适配器、两个默认工具、内存上下文、`/reset` 和 `/exit`；离线测试 172 项 Python、19 项 Node.js 通过，真实模型 gpt-6.1-sol 四个样例和 CLI 验证通过。 |

安装与启动见 [项目 README](../../README.md)，离线与真实模型的独立验收证据见 [阶段 A 完成计划](../exec-plans/completed/agent-mvp.md)。
