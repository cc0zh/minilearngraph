# 阶段 A 收尾

## 目标、范围与风险

- 用户要求完成项目检查中发现的收尾项：质量状态与技术债记录、全量应用静态检查、源码包文档完整性和本地制品更新。
- 保持 Agent 执行、历史、取消和 Pydantic 校验语义；不扩展阶段 B/C，不调用真实模型，不提交、推送、发布或部署。
- 源码包保留完整项目文档，初始化继续精简任务记录。公共入口链接阶段 A 状态页，避免初始化后的文档引用已排除记录。
- 风险：仅为消除 lint 改坏异常语义；链接检查误读 Markdown 示例；包内文档与最终工作区不同。分别通过局部规则说明、示例/链接回归和解包比对验证。

## 进度与决定

- [x] 核对源码、仓库规范、静态诊断和源码包筛选规则。
- [x] 修复静态诊断并将固定版本 Ruff/Pyright 接入现有 CI。
- [x] 修复源码包文档完整性，增加本地 Markdown 链接检查和打包回归。
- [x] 更新质量状态、技术债、架构状态与发布说明。
- [x] 完成 CI、Markdown lint、源码包验证，归档计划与 history/学习记录。
- 2026-10-09：本地可逆实现和验证由用户“收尾”授权；模型验证沿用原记录并区分来源。
- 2026-10-09：三个普通异常边界保留 Exception 捕获并写明 lint 理由；Pydantic before validator 保留 ValueError，避免 TypeError 直接逃出校验。AST 数值用 isinstance 收窄，并明确排除 bool；数值范围与文本结果不变。
- 2026-10-09：默认 dev 组固定 Ruff 0.16.10 / Pyright 1.1.414，更新 uv.lock，并接入唯一现有 CI 入口。静态检查范围为全部应用源码，未声称测试源码也全部通过静态检查。
- 2026-10-09：源码包保留项目记录，不采用初始化文档覆盖；新增打包暂存目录链接检查。初始化继续精简任务记录，公共入口改为随包状态页。
- 2026-10-09：安装 Pyright 后首次 Markdown lint 扫到 .venv 第三方文档并失败；新增 .markdownlint-cli2.jsonc 排除虚拟环境与生成目录，未修改 .markdownlint.json 规则，复验通过。

## 验收与交接

- `uv lock` 与 `uv sync --locked`：通过；新增 Ruff、Pyright 和其 nodeenv 依赖，锁文件与环境一致。
- `npm.cmd run ci`：通过。Windows、Python 3.11.11、Node.js v22.17.0；232 Python、21 Node 测试，文档骨架、仓库卫生、Action 固定 SHA 与脚本语法均通过；全量应用 Ruff 通过，Pyright 0 errors / 0 warnings。
- Markdown 环境排除配置及其分发断言新增后，重跑 `node --test tests/tooling.test.cjs`：21 passed。应用代码未再变化，沿用上述 Python 与静态检查证据。
- `npx.cmd --yes --loglevel=error markdownlint-cli2@0.22.0 "**/*.md"`：最终记录与归档后 58 文件、0 errors；虚拟环境与生成目录已排除。
- Node 新增两项测试，覆盖实际本地链接、图片、引用定义、URL 编码、代码示例跳过、越界/缺失目标，以及 Trace 记录进入包和失败不覆盖制品。既有初始化/打包回归更新为两种文档范围。
- `npm.cmd run check:docs`、`npm.cmd run check:repo` 和 `git diff --check`：最终记录与归档后通过。
- `npm.cmd run release-package`：通过，打包暂存目录的本地文档链接检查通过。Python tarfile 只读比对全部 109 份包内文件与工作区，逐字节一致；清单完整匹配源码包规则，包含 Trace 计划、独立验收、收尾记录与 Markdown 配置，不含 .env、虚拟环境、Git 或缓存。
- manifest 的 `git_sha` 已更新为当前 HEAD `dadf3a9b881e93b967a5a4b4669910210d51f134`。本次改动未提交，SHA 仅表示基线，制品一致性以实际文件比对为证；记录补齐后再次打包并核对最终工作区。
- 边界：本次不新增真实模型验证，不运行远端 Actions 或其他系统矩阵。原模型与 Trace 的不同证据来源继续保留；剩余范围见 [技术债追踪](../tech-debt-tracker.md)。
