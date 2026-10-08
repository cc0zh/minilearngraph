# Trace 独立验收与代码审查

## 补修复核结论

2026-10-08 20:37，严审独立复核 #4/#5 补修后的真实工作区。**B1 已关闭，R1/R2 已处理；#1/#2/#3/#4/#5 均可以交付，待周经理统一接受。** 下文保留首轮审查历史，新增证据见文末“补修独立验证证据”。原有 4 项 Ruff 诊断及 `tools.py:125` 的 Pyright 诊断仍在，未将其表述为全部静态检查通过。

本次没有修改业务代码，也没有重复未变化的行为验收；首轮独立 172 项相关、232 项全量 Python 与 19 项 Node 测试的证据继续适用。未新增真实模型验证，未执行远端 Actions 或其他操作系统矩阵；本地源码包已更新，无发布。

## 首轮结论与范围（历史记录）

2026-10-08，严审独立检查工作区中的 Trace 内核与 CLI 交付。依据为 [架构 §5.2 与第 8 节测试策略](../../ARCHITECTURE.md)、[内核交接计划](../../exec-plans/completed/trace-kernel-hook.md) 和 [CLI 交接计划](../../exec-plans/completed/trace-cli.md)。审查基线 HEAD 为 `e6c1548e28ae1cb2de9bedbc3291519a8d2e9eec`，包含尚未提交的交付文件和任务开始前已有的架构修改。

**必须修复的问题：B1，完整 CI 中的 Markdown lint 门禁失败。** Trace 功能逐项通过，未确认本次新增业务代码缺陷；`npm.cmd run ci`、源码打包均通过，但不能将其表述为全部 GitHub Actions 检查已通过。B1 涉及任务开始时已有的文档格式，不能归因于本次 Trace 实现。最终验收由派单人决定。

审查者新增 [独立回归测试](../../../tests/test_trace_acceptance.py)、本记录及 history 索引，并在两份计划追加本记录链接，没有修改业务代码或交接事实。验证未调用真实模型；HTTP 模拟与固定模型桩不能替代真实模型验证。

## 逐条功能验收

表中函数名均可在对应测试文件中直接检索；路径均相对于仓库根目录。

| 要求 | 结果 | 实现与可复查测试证据 |
| --- | --- | --- |
| Trace 默认关闭，无持久化或平台连接 | 通过 | `cli.py:29` 默认 False，仅启用分支创建 TraceHook；`test_cli.py::test_trace_is_disabled_by_default_and_does_not_create_hooks`；`trace.py` 仅 stderr 与局部字典 |
| Runner/Loop 可选 Hook，结果、历史和预算语义保持 | 通过 | `runner.py:27`、`loop.py:27`；新增 `test_every_hook_can_mutate_and_fail_without_changing_result_requests_or_history` 对比完整 AgentResult、模型请求、历史及请求数；旧 Runner/Loop 回归保留 |
| 每次 Hook 独立快照，不暴露工作消息或注册表 | 通过 | `hook.py:82` deepcopy；`test_tool_lifecycle_order_and_independent_snapshots`、`test_contexts_contain_only_observation_fields`；新增恶意 Hook 回归覆盖所有九个方法 |
| 普通 Hook 异常隔离，日志不输出异常文本 | 通过 | `hook.py:83` 只捕获 Exception，日志仅方法名与类别；旧恶意 Hook 与新增全生命周期对照测试 |
| 取消与 KeyboardInterrupt/SystemExit 不被吞掉 | 通过 | `test_safe_hook_preserves_cancellation_and_exit`；CLI 取消测试；新增 `test_system_exit_propagates_with_iteration_and_run_cleanup` 覆盖模型、工具准备和 Hook |
| 正常运行、迭代、工具开始/结束顺序正确 | 通过 | `test_tool_lifecycle_order_and_independent_snapshots` 精确事件序列；旧多工具、多轮配对回归；新增双工具恶意 Hook 对照 |
| 全部受控失败按 on_error → after_run → on_finally | 通过 | 新增 `test_all_controlled_failures_finalize_in_order_without_tools` 覆盖 model_error、invalid_response、output_truncated、content_filtered、empty_response、step_limit；旧未预期工具错误测试覆盖 tool_error |
| 每步 finally 收尾，包括模型超时与工具异常 | 通过 | `runner.py:139`；模型超时、工具超时/预期/未预期错误测试及新增准备实现异常回归，均断言 after_iteration |
| Runner 未预期异常上抛，on_error 与 on_finally | 通过 | `test_runner_unexpected_exception_propagates_with_error_and_cleanup`、Trace 的 registry 异常测试；未伪造 after_run |
| 取消继续传播，运行层只尝试 on_finally | 通过 | 真实 asyncio Task 取消覆盖模型、工具、Hook；断言无 on_error、after_run 或工具错误回调，迭代先收尾；Loop 历史不变 |
| 取消/退出尽力清理 Trace 工具计时状态 | 通过 | `test_real_task_cancellation_propagates_and_cleans_up`、`test_unexpected_runner_exception_and_exit_only_cleanup`、stderr 写入失败仍清空字典测试 |
| ToolResult 显式 is_error，不靠 Error 文本判断 | 通过 | `types.py:20`、`tools.py:78`；`test_actual_execution_error_categories_and_result_flags`、`test_prepare_once_and_explicit_error_flag_independent_of_text`；成功文本可包含 Error |
| 未知工具或非法参数不触发执行开始，不虚构执行耗时 | 通过 | `runner.py:148` 先 prepare，再 before_execute_tool；内核精确回调计数与 Trace 准备失败测试；错误仍回传模型供修正 |
| 参数只校验一次，准备和执行留在 Registry | 通过 | `tools.py:62`、`:78`；计数 validator 回归证明 Runner 每次只验证一次，execute_prepared 不再验证 |
| 每个工具只有一个结束分支 | 通过 | 正常、预期错误、超时、未知工具、非法参数和未预期异常均有回调计数；新增准备实现异常仅一个 on_execute_tool_error；取消不包装为工具错误 |
| 预算耗尽、非法/截断/过滤响应不执行工具 | 通过 | `runner.py:118` 预算检查先于 assistant/tool 阶段；旧预算、协议测试和新增六类受控失败精确断言无工具事件及单次模型请求 |
| CLI 每轮独立 Hook，stderr trace / stdout 答案 | 通过 | `test_trace_rounds_have_independent_hooks_and_answers_stay_stdout` 同时检查实例、显示 ID 和输出流；Trace 隐私测试 stdout 为空 |
| /reset、/exit、EOF、空输入及配置预算兼容 | 通过 | `test_cli_processes_followup_reset_exit_and_blank_input`、EOF/子进程启动退出、预算与 Provider 关闭、开关传递和 --help 测试 |
| context_error 由 CLI 展示，Runner 未运行就无 Runner 事件 | 通过 | `loop.py:37` 返回 AgentResult，`cli.py:55` 显示 result.error；旧同步失败测试及新增异步失败恢复测试证明无模型请求/伪造 trace，既有历史保留 |
| 计时非负，按 call.id 配对，与快照对象身份无关 | 通过 | 固定时钟的工具计时测试逆序结束不同 call.id，并检查负值钳制；新增 `test_runner_model_and_run_durations_clamp_backwards_clock` 覆盖 Runner 模型与运行计时 |
| 默认输出不含密钥、用户输入、实参、结果、异常文本或私有推理 | 通过 | `test_trace_lifecycle_privacy_and_output_streams` 为各类负载置入不同标记；执行/模型异常、未知 finish_reason 测试检查类别化与不泄露；日志无异常文本 |
| 标识控制字符安全 | 通过 | `trace.py:12` JSON ASCII 转义；`test_identifier_control_characters_cannot_inject_trace_lines` 断言换行、ESC 被转义，输出仍只有一行 |

工具超时属于已知工具错误，Runner 可以继续请求模型修正；未预期工具实现异常返回 tool_error。观察回调含 ToolCall 副本和成功 ToolResult，但默认 Trace 只读取标识、状态和计数，没有序列化负载。

## context_error 疑点复核

“CLI 只有通用异常文案”不符合实际实现。`cli.py:50` 的通用文案处理 `loop.process` 抛出的普通异常；领域上下文失败由 `loop.py:37` 转为 `AgentResult("", [], "context_error", "Could not load domain context.")`，随后进入 `cli.py:55` 的 result.error 分支，显示 `Error [context_error]: Could not load domain context.`。

旧测试验证同步上下文失败没有模型请求、没有历史、stderr 为空。新增 `test_async_context_error_preserves_history_and_cli_recovers` 在 Trace 开/关两种模式下依次执行成功、异步上下文失败、再次成功，断言准确错误类别、既有历史和上下文快照保留、失败不进入历史且交互继续。开启 Trace 时只有两个实际 Runner 的 run started，没有 context_error 的 Runner 记录。因此该观察不成立为缺陷。

## 独立命令结果

环境：Windows、Python 3.11.11、uv 0.8.13、Node.js v22.17.0。命令从仓库根目录运行。

| 命令 | 结果 |
| --- | --- |
| `uv run --locked pytest tests/test_trace_acceptance.py tests/test_hook.py tests/test_trace.py tests/test_cli.py tests/test_runner.py tests/test_loop.py tests/test_tools.py -q` | exit 0，172 passed；其中本次新增 15 项 |
| `npm.cmd run ci` | exit 0，232 Python + 19 Node 全通过；文档骨架、仓库卫生、Actions 固定版本及 CJS 语法检查通过 |
| `npm.cmd run release-package` | exit 0，生成本地源码包与 manifest；仅更新约定 dist 文件，无发布 |
| `tar -tzf dist/repo-metadata.tgz` | 清单含 hook.py、trace.py、Hook/Trace/独立验收测试、uv.lock、.env.example；未将本地模型配置纳入这些匹配结果 |
| `uv run --locked python -m compileall -q mini_learngraph tests` | 通过 |
| `uvx --from pyright pyright --pythonpath .venv/Scripts/python.exe mini_learngraph/hook.py mini_learngraph/runner.py mini_learngraph/loop.py mini_learngraph/types.py mini_learngraph/provider.py mini_learngraph/trace.py mini_learngraph/cli.py mini_learngraph/__init__.py` | exit 0，0 errors / 0 warnings |
| 上述 Pyright 命令另加入 `mini_learngraph/tools.py` | exit 1，唯一错误 tools.py:125 的 AST Constant 类型收窄；HEAD 中该表达式已存在，本次 diff 未修改 |
| `uvx --from ruff ruff check mini_learngraph/trace.py mini_learngraph/cli.py mini_learngraph/__init__.py tests/test_trace.py tests/test_cli.py tests/test_trace_acceptance.py` | exit 0，All checks passed |
| 对全部新增/修改内核与 CLI 实现、Hook/Trace/CLI/独立验收测试执行 Ruff | exit 1，6 条提示；明细见建议 R2，不属于当前 ci.cjs 门禁 |
| `git diff --check -- mini_learngraph tests README.md docs/exec-plans docs/histories docs/learnings docs/exec-runs/trace` | exit 0 |
| `npx.cmd --yes --loglevel=error markdownlint-cli2@0.22.0 "**/*.md"` | exit 1，记录新增前 53 文件、写入记录后 55 文件均为相同 28 条错误，6 文件；B1 为固定 Actions 版本对应的真实门禁失败 |
| 同版本 Markdown lint 单独检查 README、两份计划、三份 history、两份 learning、本验收记录 | exit 0，9 文件，0 error；写入记录后文档骨架与仓库卫生检查再次通过 |

两份交接计划的计数是各自交付时的快照：内核相关 126、CLI 相关 31 合计 157；本次新增 15 后相关 172。内核阶段的全量 195、CLI 阶段全量 217，与最终加 15 后 232 相符，不能把历史计数改称本次证据。19 项 Node 数量一致。

GitHub Actions 的 Ubuntu Markdown lint 步骤使用固定 action `ce4853d43830c74c1753b39f3cf40f71c2031eb9`。审查只读核对该提交 package.json，依赖明确为 markdownlint-cli2 0.22.0；本地按此版本复查。初次用 0.23.3 运行也得 28 条，最终判断以固定版本为准。本次没有执行远端 Actions 或其他操作系统矩阵；本地验证不冒充远端已成功。

## 必须修复的问题

### B1 — 阻断：Markdown lint 门禁失败（已关闭，保留首轮证据）

- 位置：`docs/ARCHITECTURE.md:362`（MD012，1 条）；`docs/code-understanding/ARCHITECTURE_GRAPH_GUIDE.md:74`（MD060，4 条）；`docs/code-understanding/README.md:19`（MD060，6 条）；`docs/code-understanding/trace-path.md:18`（MD060，6 条）；`docs/code-understanding/understanding-budget.md:8`（MD060，8 条）；`docs/exec-runs/templates/execution-summary.md:23`（MD060，3 条）。合计 28 条。
- 复现：在现有工作区执行 `npx.cmd --yes --loglevel=error markdownlint-cli2@0.22.0 "**/*.md"`。
- 期望：无 Markdown lint 错误，退出 0。
- 实际：退出 1，报告上述格式错误；本地 `npm.cmd run ci` 没有调用 Markdown lint，所以仍可通过。
- 影响：`.github/workflows/ci.yml` 的 Ubuntu job 会在 Markdown lint 步骤失败，完整交付门禁不成立；不影响本次已验证的 Trace 执行行为。
- 来源：架构空行在任务初始读取时已经存在；其余五文件相对 HEAD 没有 diff。不得归因于老秦或阿岚新增 Trace 业务代码，也不是测试不稳定。
- 归属：周经理安排文档维护工程师处理（可交阿岚），保留用户既有架构内容，只修格式。严审按岗位约定未修改这些文档。修复后重跑同版本全仓 Markdown lint 即可，若业务代码未改变，不需要重复全部行为测试。

## 非阻断审查建议与已有问题

### R1 — 建议：README 增加 Registry 返回类型迁移提示（已处理）

- 位置：`README.md:57` 的工具接入说明；真实类型变化在 `mini_learngraph/tools.py:72`。
- 检查方式：README 说明工具函数返回文本，但未直接说明 `ToolRegistry.execute` 从 str 改为 ToolResult；内核计划第 42 行明确记录迁移，架构也明确 text/is_error。CLI 计划未声称 README 已提供迁移教程，交接事实无矛盾。
- 影响：旧直接调用者若仍把 execute 结果当字符串调用 `.startswith`，将遇到 AttributeError；工具函数返回文本这一 README 陈述本身正确。
- 建议：说明读取 `.text`，使用 `.is_error` 判断状态；工具函数仍返回 str。归属阿岚（README），老秦提供接口确认。由于架构与交接文档已经准确说明，作为可维护性建议，不认定为业务缺陷。

### R2 — 建议：内核 Ruff 提示单独处理（新增提示已处理）

完整检查命令：

```powershell
uvx --from ruff ruff check mini_learngraph/hook.py mini_learngraph/runner.py mini_learngraph/loop.py mini_learngraph/types.py mini_learngraph/provider.py mini_learngraph/trace.py mini_learngraph/cli.py mini_learngraph/tools.py mini_learngraph/__init__.py tests/test_hook.py tests/test_trace.py tests/test_cli.py tests/test_trace_acceptance.py
```

- 新增提示：`hook.py:83` BLE001；`runner.py:3` I001。safe_hook 捕获普通 Exception 是架构要求，可以像 CLI 边界一样补充有理由的 lint 说明；Runner import 可按 Ruff 排版。归属老秦。
- 既有模式提示：`loop.py:36`、`runner.py:90`、`runner.py:128` 的 BLE001，原实现已有同类异常边界；`tools.py:107` 的 PYI041 原类型标注未修改。
- 这些提示不是输入校验/权限漏洞。当前 CI 不执行 Ruff；CLI 阶段的范围检查独立通过，与其交接报告一致。禁止为了消除 BLE001 改成吞取消/退出的 BaseException 捕获。

### R3 — 建议：既有 tools.py Pyright 诊断保留记录

`tools.py:125` 的 `_bounded_number(node.value)` 不能被 Pyright 从 AST `_ConstantValue` 自动收窄为 int|float。`git show HEAD:mini_learngraph/tools.py` 可找到完全相同表达式，当前 diff 没有改动它。运行时计算器边界测试通过；唯一该诊断不应误报为 Trace 引入。归属老秦后续按范围处理，审查者没有改业务代码。

## 真实模型与交接事实

README 记录的 `gpt-6.1-sol` 真实模型验证属于此前阶段 A；两份 Trace 计划均明确未新增真实模型验证，本次也没有新增。不能据旧结果声称 --trace 已经对真实模型完成验收。固定模型演示、MockTransport 和本次离线测试分别按其事实报告。

两份计划与 history 均说明“实现完成、自检通过、待独立验收”，没有将实现自检冒充最终接受。README 的 CLI 入口、stderr/stdout、默认关闭、每轮实例、context_error、内存历史、预算限制与实际代码/测试一致。接口迁移文档准确，但主入口发现性可按 R1 改善。

## 补修独立验证证据

复核输入为 [#4 文档补修记录](../../histories/2026-10/20261008-2032-trace-docs-lint.md) 与 [#5 内核 lint 补修记录](../../histories/2026-10/20261008-2033-trace-kernel-lint.md)，所有下列命令由严审在仓库根目录实际执行。首轮源码包生成于 20:21，先用其文件内容对比最终工作区，再更新制品；没有仅依赖工程师自检结论。

### 范围、语义与迁移核对

- B1 六份文档相对首轮源码包，移除空白后的内容逐份完全相等；五份表格仅增加分隔行空格，`docs/ARCHITECTURE.md` 仅删除尾部多余空行。架构中任务开始前已有的内容完整保留，没有用 HEAD 的旧版本覆盖用户修改。
- README 相对首轮源码包仅增加一段迁移说明，准确对应 `tools.py:72` 的 `execute -> ToolResult`、成功文本包装和已知错误的 `is_error=True`：直接调用者读取 `.text`、使用 `.is_error`，注册的工具函数仍返回 `str`。
- `.markdownlint.json`、`pyproject.toml`、`.github/workflows/ci.yml` 与 HEAD 完全一致，没有关闭或调整 Markdown/Ruff 规则。Hook 的局部 `noqa: BLE001` 带明确理由，与普通观察器异常隔离、取消和退出继续传播的架构契约相符。
- 前次包完整包含当前 23 份 Python 源码、Python 测试及 Node 测试文件。逐文件比对仅 Hook/Runner 有差异：Hook 只新增有理由的注释，Runner 只展开同一组导入，导入名称与顺序不变；其他源码与测试完全一致。
- 使用 `.venv/Scripts/python.exe` 的 `ast.parse` 与 `ast.dump(include_attributes=False)` 对比首轮包及工作区，两份源码 AST 完全相同。SHA-256：Hook `865b5aa48ad6202a415bb517b517fbdb8939c4ddb7db467223c20949a17de1c8`；Runner `f94935bcba64988a2b4d6d4c32ba4d9bd4b5bf72f4f22b602d2967944c2e11f8`。`except Exception` 的捕获类型、日志及执行语句均未改变，仍不捕获取消、KeyboardInterrupt 或 SystemExit。
- 未发现新的行为变化或测试失败，因此本轮不重复行为测试。#5 自检的 93 项回归属于工程师证据；本轮独立证据是文件/AST 对比与针对性门禁，首轮独立行为测试计数保留其实际执行时间。

### 命令结果与剩余诊断

| 独立复核命令 | 实际结果 |
| --- | --- |
| `npx.cmd --yes --loglevel=error markdownlint-cli2@0.22.0 "**/*.md"` | exit 0，57 文件、0 errors；补修复核记录与 history 更新后全仓再次通过同一门禁 |
| `uvx --from ruff ruff check mini_learngraph/hook.py` | exit 0，All checks passed；新增 BLE001 消失 |
| `uvx --from ruff ruff check --select I001 mini_learngraph/runner.py` | exit 0，All checks passed；新增 I001 消失 |
| R2 保留的完整 Ruff 命令 | exit 1，只有原有 4 项：`loop.py:36` BLE001、`runner.py:94` BLE001、`runner.py:132` BLE001、`tools.py:107` PYI041 |
| `uvx --from pyright pyright --pythonpath .venv/Scripts/python.exe mini_learngraph/hook.py mini_learngraph/runner.py` | exit 0，0 errors / 0 warnings |
| 上述 Pyright 命令加入 `mini_learngraph/tools.py` | exit 1，仅原有 `tools.py:125` AST Constant 类型收窄错误，R3 保留 |
| `npm.cmd run check:docs` | exit 0，文档骨架通过；最终记录更新后再次通过 |
| `npm.cmd run check:repo` | exit 0，仓库卫生通过；最终记录更新后再次通过 |
| `git diff --check` | exit 0，全工作区无空白错误；最终记录更新后再次通过 |
| `npm.cmd run release-package` | exit 0，仅更新本地约定源码包与 manifest，没有发布 |

R1 已由 README 迁移说明处理；R2 的两项新增提示已处理，既有诊断继续按原范围记录，未升级为本次阻断。B1 的固定版本全仓门禁已从 28 errors 变为 0 errors。结合首轮功能验收与本轮范围核对，#1/#2/#3 保持可接受，#4/#5 补修可以接受，当前无必须修复项。最终接受归周经理。

### 本地制品一致性

使用 Python `tarfile` 只读读取更新后的 `dist/repo-metadata.tgz`，逐字节核对 34 份文件（23 份源码/测试、README、六份 B1 文档及 Markdown 配置、pyproject、锁文件、`.env.example`），均与最终工作区一致；未含 `.env`、`config.local.yaml`、`.venv`、Python 缓存或 `.git`。包 SHA-256 为 `8f4b7caf4a2f35c762aa0fe1a374edeb5818f29693dfd22e063e4518af0ffc8f`。

manifest 的 `git_sha` 为审查基线 `e6c1548e28ae1cb2de9bedbc3291519a8d2e9eec`，生成时间为 `2026-10-08T12:37:16.006Z`；当前交付尚未提交，SHA 表示 HEAD，制品内容以实际打包及逐字节核对为准。`scripts/lib/scaffold.cjs` 按既有规则排除任务级 history、Trace execution run 和学习记录，因此随后更新本验收记录与 history 不改变包内最终文件。

## 用户补充的真实 CLI 计算记录

来源：**用户提供的CLI运行日志（群聊seq51）**。此记录是在上述独立验收之后由用户补充，老秦与严审没有亲自执行该次模型请求。此前实现、自检及独立验收未新增真实模型验证的历史事实保持不变。

| 项目 | 用户日志中的结果 |
| --- | --- |
| 模型 | `gpt-6.1-sol` |
| 输入 | `请调用calculate工具计算(12+8)/5` |
| 临时显示 ID | `6007eb33` |
| 工具 | `calculate` 启动并成功完成；call_id 为 `call_92c9cd4ad17e4b6b8b1f9196cd5f95f7` |
| 首次模型请求 | `model_ms=3422.0`，`finish_reason=tool_calls` |
| 第二次模型请求 | `model_ms=2984.0`，`finish_reason=stop` |
| 运行汇总 | `model_calls=2`，`duration_ms=6422.0`，`stop_reason=completed`，`error_type=none` |
| 最终答案 | `4` |

该日志仅支持一次真实计算工具链路：模型请求、calculate 执行成功、第二次模型请求与最终答案。两次模型请求属于同一次用户交互，不能扩大为真实多轮对话、时间工具或真实模型取消测试通过；原有离线取消测试证据仍按其实际范围报告。
