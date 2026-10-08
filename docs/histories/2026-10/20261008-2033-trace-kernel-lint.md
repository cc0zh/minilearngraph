# Trace 内核新增 Ruff 提示清理

2026-10-08 20:33，老秦按周经理重试 #5 派单处理 [独立验收记录 R2](../../exec-runs/trace/execution-summary.md#r2--建议内核-ruff-提示单独处理)。接手时两项新增提示仍可复现，未发现此前重试已完成的修复。此记录独立保存本次自检证据，最终复核由严审与派单人确认。

## 诉求与改动

- 仅清理新增 `hook.py` BLE001 与 `runner.py` I001，不扩大修复既有诊断，不编辑独立验收记录或前端文档。
- `mini_learngraph/hook.py:83`：为 `except Exception as error` 添加局部 `noqa: BLE001` 和理由，普通观察器异常应隔离，取消与退出必须继续传播。捕获类型、日志内容及执行语句均保持原样。
- `mini_learngraph/runner.py:8`：按 Ruff 建议将 Hook 导入展开为每项一行，导入名称及顺序保持原样。
- 新增本 history。接口、返回类型、数据结构、业务逻辑、取消与退出行为均无变化，无数据迁移。

## 验证证据

环境为 Windows / EnsoCode；Ruff 0.16.10，Pyright 1.1.414。命令从仓库根目录运行，无真实模型调用。

- `uvx --from ruff ruff check mini_learngraph/hook.py`：exit 0，`All checks passed!`，新增 BLE001 消失。
- `uvx --from ruff ruff check --select I001 mini_learngraph/runner.py`：exit 0，`All checks passed!`，新增 I001 消失。
- 按 R2 原完整 Ruff 命令复查：exit 1，提示由 6 项降至 4 项，仅余原有 `loop.py:36` BLE001、`runner.py:94` 与 `runner.py:132` BLE001、`tools.py:107` PYI041。Runner 行号因导入展开增加 4 行。
- `uv run --locked pytest tests/test_hook.py tests/test_runner.py tests/test_trace.py tests/test_trace_acceptance.py -q`：exit 0，93 passed，覆盖普通异常隔离、真实任务取消、KeyboardInterrupt/SystemExit 传播及生命周期收尾。
- `uvx --from pyright pyright --pythonpath .venv/Scripts/python.exe mini_learngraph/hook.py mini_learngraph/runner.py`：exit 0，0 errors / 0 warnings。
- 以 `ast.parse` / `ast.dump(include_attributes=False)` 生成 AST 文本并计算 SHA-256：两份源码修改前后摘要完全一致。Hook 为 `865b5aa48ad6202a415bb517b517fbdb8939c4ddb7db467223c20949a17de1c8`，Runner 为 `f94935bcba64988a2b4d6d4c32ba4d9bd4b5bf72f4f22b602d2967944c2e11f8`，确认只有注释与排版变化。
- `git diff --check -- mini_learngraph/hook.py mini_learngraph/runner.py docs/histories/2026-10/20261008-2033-trace-kernel-lint.md`：exit 0。
- `npx.cmd --yes --loglevel=error markdownlint-cli2@0.22.0 "docs/histories/2026-10/20261008-2033-trace-kernel-lint.md"`：exit 0，1 file / 0 errors。
- `npm.cmd run check:docs`：exit 0，文档骨架检查通过。

## 范围与未完成项

既有 Ruff 4 项诊断及 `tools.py` 的既有 Pyright 类型诊断按派单保留；本次未重跑包含 tools.py 的类型检查。此次仅注释与导入排版调整，采用相关回归，不重复先前 232 Python + 19 Node 的全量验收。本文不替代独立验收，也不声称完整 Ruff 或远端 CI 已通过。
