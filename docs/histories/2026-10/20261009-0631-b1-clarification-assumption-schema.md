# 2026-10-09 06:31 UTC | 修复 B1 澄清建议假设的模型 Schema

## 用户诉求

人工操作真实 B1 页面时，一个无明确学习期限的合成 CSV 学习目标出现
`generation_failed / invalid_output`，需要定位原因并恢复原草稿。

## 诊断与结果

- 用户授权仅一次既有模型配置的诊断请求。使用 `gpt-6.1-sol`，无数据库写入、无发布，
  不记录原始模型响应或密钥；修复后未再联网调用。
- 诊断响应正常结束、无工具调用、完整 JSON 可解析，但模型建议假设的 key 不符合
  `suggested:` 来源前缀约束。历史失败未保留原文，不能断言历史响应的所有具体错误。
- 原模型 Schema 未暴露该前缀，只在运行时校验。新增模型专用 SuggestedAssumption，
  将前缀输出为 JSON Schema pattern，并明确澄清提示词中的 key 写法。
- 保持 strict 校验、来源审阅和单次请求，不修复非法输出、不自动重试。
  公开 GoalRead/Assumption 与 HTTP 字段形状不变，无数据库迁移。
- 后端说明新增失败恢复步骤：同库重启、读取最新资产、显式重试原草稿。

## 验证与未完成项

- 新增定向回归修复前为 2 failed / 3 passed，暴露 Schema 与提示词缺失。
- 修复后 B1 六组离线回归共 247 passed；Ruff 通过，Pyright 为 0 errors。
  Starlette/httpx 弃用警告未在本次修改依赖处理。
- `npm.cmd run check:docs` 文档骨架检查通过，`git diff --check` 退出 0；
  新增 history、learning 与后端恢复说明的本地链接已核对。
- 真实模型仅证明修复前问题可复现；修复后的真实澄清和图谱仍需用户重新操作验证，
  不把离线结果冒充真实模型效果，也不宣称 B1 最终验收完成。

## 受影响文件

- `mini_learngraph/learning/generation.py`
- `mini_learngraph/learning/schemas.py`
- `tests/test_learning_validation.py`
- `mini_learngraph/api/README.md`

学习记录：[让模型 Schema 与运行时校验对齐](../../learnings/2026-10/model-schema-runtime-alignment.md)。
