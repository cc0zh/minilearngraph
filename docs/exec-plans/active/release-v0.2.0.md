# 发布当前版本 v0.2.0

## 目标与授权

用户要求“将当前版本进行发布”，授权将当前工作区源码提交、推送至现有 `cc0zh/minilearngraph`，经默认检查后使用既有 GitHub Release 流程发布。不部署、不调用真实模型、不上传个人数据，不发布 npm/PyPI 包。

基线 HEAD 为 `dadf3a9`，工作区包含阶段 A 收尾、CLI Trace、已验收 B1 实现及 B2 待复核设计。保留全部已有内容；B2–B4 未实现、真实 B1 模型未验证的边界写入发布说明，不将设计文档作为实现证据。

从现有 `v0.1.0` 递增至功能版本 `v0.2.0`，同步 Python/Web 元数据与锁文件，不升级依赖。通过 Git Credential Manager 在进程内使用现有 GitHub 凭据，不输出或保存令牌。

## 执行与验收

- [x] 检查工作区、远端默认分支、版本 tag、发布流程和凭据可用性。
- [x] 准备版本说明、元数据；CI push 补齐实际默认分支 master；Release 显式绑定执行 SHA 并载入对应版本正文。
- [x] `uv sync --locked`、完整 `npm.cmd run ci`、Markdown lint、差异与制品敏感文件检查通过。
- [ ] 明确文件清单提交推送，远端三平台 CI 通过；创建并推送 v0.2.0 tag，以 tag ref 触发既有发布流程。
- [ ] 发布流程通过，核验 GitHub Release 非草稿、三项附件、tag/manifest SHA、源码包和 provenance。
- [ ] 记录最终证据、更新发布状态、归档本计划并提交。

## 风险与边界

发布不能覆盖已有 tag；推送不用 force，不 reset/stash 用户改动。源码包排除 `.env`、真实 SQLite、缓存和浏览器输出；B2 设计保留待复核标记。流水线或凭据失败时报告真实状态，不绕过门禁或声称发布完成。

## 验证记录

2026-10-09，本机 Windows / Node 22.17.0 / Python 3.11.11 / uv 0.8.13：

| 检查 | 实际结果 |
| --- | --- |
| `uv sync --locked` | 通过；本地项目从 0.1.0 更新为 0.2.0，无依赖升级 |
| 完整 `npm.cmd run ci` | 退出0，109.9秒；Node24、Python479、Web单元14、Mock浏览器16、实际API浏览器3全部通过；Ruff/Pyright零诊断，Web类型/lint/build通过 |
| Markdownlint 0.22.0（缓存离线） | 73文件，0错误 |
| `npm.cmd run release-package` / 归档目录检查 | 成功；204项，无 `.env`、真实数据库、node_modules、虚拟环境、Git或浏览器输出 |
| `git diff --check` | 退出0 |

首次完整 CI 在通过 Node/Python 后，因已有 Vite 开发服务锁住 esbuild 可执行文件，Web `npm ci` 报 EPERM；仅停止该项目 Vite 及其 esbuild 子进程后，按原门禁重跑全量通过，不绕过锁定安装。发布检查完成后恢复开发服务。Starlette 弃用 warning 保持1条；默认 npm 镜像 audit 404 不作为漏洞审计通过。

远端 CI、发布结果待执行；最终提交 SHA、流程链接、附件及 provenance 在核验后补齐。真实模型未调用。
