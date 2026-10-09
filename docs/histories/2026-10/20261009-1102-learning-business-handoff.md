## [2026-10-09 11:02] | Task: 编写学习业务扩展交接文档

### Execution Context

- **Agent ID**: 当前主会话，未获取会话标识。
- **Base Model**: GPT-6。
- **Runtime**: pi / Enso Code。

### User Query

> 当前 Agent 已实现；参考 LearnGraph 的 README 与业务实现，交付可交接的业务扩展文档。下一阶段已选择学习闭环与 Web。
>
> 补充要求：接手者无法访问原 LearnGraph 代码，交接必须独立可用。

### Changes Overview

**Scope:** 文档。

- 新增[交接文档](../../design-docs/learning-business-handoff.md)，区分已确认范围、原项目事实、实施建议与待定选择。
- 梳理目标、图谱、节点学习、作答、证据、能力状态和推荐的契约及分阶段验收。
- 更新设计文档索引；没有实施业务代码。
- 按补充要求展开原项目算法，新增 mini 状态转换、完整数据样例、评估与推荐起始规则、API 语义、提交/恢复顺序和验收案例；外部代码及 README 不再是接手前置条件。

### Design Intent

让接手者脱离聊天记录也能了解现状、依据与下一步，同时避免将调研结论、算法建议或未来验收误认为已实现能力。

所有实施相关知识直接写入本仓库，保留“原项目事实 / mini 建议”区别；源码路径索引不能代替实现契约。

### Files Modified

- `docs/design-docs/learning-business-handoff.md`
- `docs/design-docs/index.md`
- 本 history。

### Validation

- `npm.cmd run check:docs`：文档骨架检查通过。
- 固定版本 `markdownlint-cli2@0.22.0` 检查本次三个 Markdown 文件：0 个错误。
- 仓库现有 `checkMarkdownLinks` 检查：本地 Markdown 文件链接全部通过。
- 设计索引 `git diff --check`：通过。
- 自包含修订后重新检查文档骨架、三个文件的 Markdown lint 与本地链接：通过；两段 JSON 示例经解析检查均有效。
- 内容复核：原源码定位表已移除，核心流程、公式及 mini 建议直接展开，16 个验收案例不依赖原仓库。
- 原项目调查仅为静态阅读；没有运行原项目或验证真实模型。
