# Trace 内核 Hook 与工具生命周期

用户授权按架构 §5.2 新增轻量 Trace 内核，范围为 Hook、Runner、Loop 和工具注册表；CLI 展示由后续任务接入。

已增加默认空异步 Hook、独立精简快照、安全异常隔离与运行/迭代/工具生命周期；工具结果迁移为显式错误标志，保持模型消息、预算和历史语义。未引入存储、回放或外部平台。

文件清单、设计决定、测试证据和接入契约维护在 [执行计划](../../exec-plans/completed/trace-kernel-hook.md)，本阶段由独立审查确认最终验收。

可迁移知识见 [异步观察器的错误隔离与取消](../../learnings/2026-10/async-observer-lifecycle.md)。
