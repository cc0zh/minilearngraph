# 发布当前版本 v0.2.0

## 目标与授权

用户要求“将当前版本进行发布”，授权将当前工作区源码提交、推送至现有 `cc0zh/minilearngraph`，经默认检查后使用既有 GitHub Release 流程发布。不部署、不调用真实模型、不上传个人数据，不发布 npm/PyPI 包。

基线 HEAD 为 `dadf3a9`，工作区包含阶段 A 收尾、CLI Trace、已验收 B1 实现及 B2 待复核设计。保留全部已有内容；B2–B4 未实现、真实 B1 模型未验证的边界写入发布说明，不将设计文档作为实现证据。

从现有 `v0.1.0` 递增至功能版本 `v0.2.0`，同步 Python/Web 元数据与锁文件，不升级依赖。通过 Git Credential Manager 在进程内使用现有 GitHub 凭据，不输出或保存令牌。

## 执行与验收

- [x] 检查工作区、远端默认分支、版本 tag、发布流程和凭据可用性。
- [x] 准备版本说明、元数据；CI push 补齐实际默认分支 master；Release 显式绑定执行 SHA 并载入对应版本正文。
- [x] `uv sync --locked`、完整 `npm.cmd run ci`、Markdown lint、差异与制品敏感文件检查通过。
- [x] 明确文件清单提交推送，远端三平台 CI 通过；创建并推送 v0.2.0 tag，以 tag ref 触发既有发布流程。
- [x] 发布流程通过，核验 GitHub Release 非草稿、三项附件、tag/manifest SHA、源码包和 provenance。
- [x] 记录最终证据、更新发布状态、归档本计划并提交。

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

### 首次远端矩阵失败与修复

提交 `1a2de3d` 的 [CI 37898437558](https://github.com/cc0zh/minilearngraph/actions/runs/37898437558) 未通过：Ubuntu/macOS 各478 passed/1 failed，dotenv负对照依赖仓库实际存在 `.env`，干净checkout中没有触发读取；Windows Node20 passed/4 failed，native tar在argv中的中文路径变为问号，Python/Web未执行。

修复保留门禁强度：dotenv负对照改用临时目录的已存在合成文件，guard同时禁止个人与合成dotenv读取；源码打包tar使用staging cwd与相对参数，测试解包用stdin、保留中文cwd与文件存在断言，归档列表用相对文件名。生产ServerSettings/业务代码不变，无个人配置/数据库操作。修复后本地定向、远端全量结果待登记；未创建tag或Release。

同时补齐Web说明已要求的Linux CI系统库安装：三平台参数回归先RED，证明Linux Chromium安装缺少`--with-deps`，再让默认CI仅在Linux/CI=true追加该参数，保留Windows/macOS及本地行为。dotenv/tar首次修复定向实跑Node24/24、acceptance14/14、打包、Markdown73文件零错误与diff通过；最终参数回归及下一远端矩阵待执行。

## 最终发布与核验

状态：**2026-10-09 已发布并核验**。发布标签 `v0.2.0` 指向 **`e3b6ae3afc7f9129b09e60263db4352adf35a090`**，Release 非草稿、非预发布，GitHub发布时间 `2026-10-09T07:31:46Z`。收尾文档与学习速记在默认分支追加提交，不移动已发布tag、不替换已发布制品；包内计划为打包时的历史快照，最终证据以本节为准。

| 验证 | 最终证据 |
| --- | --- |
| 修复后本地定向 | Node24/24（包含三平台参数模拟）、acceptance14/14、文档骨架、Markdown73文件零错误、diff通过；默认Web流程未绕过 |
| [CI 37899007262](https://github.com/cc0zh/minilearngraph/actions/runs/37899007262) | Ubuntu、macOS、Windows全绿；每个平台Node24、Python479、Web单元14/Mock16/实际API3、Ruff/Pyright/typecheck/lint/build与源码打包通过；Ubuntu额外Markdown lint通过 |
| [发布 37899349718](https://github.com/cc0zh/minilearngraph/actions/runs/37899349718) | ref=v0.2.0 / HEAD=e3b6ae3；默认CI、打包、SBOM、attestation、上传及创建Release均成功 |
| [GitHub Release](https://github.com/cc0zh/minilearngraph/releases/tag/v0.2.0) | 三个附件均uploaded，发布目标SHA与tag一致；正文含安装方式和未实现/未验证边界 |
| 远端附件实际下载检查 | manifest的repository/SHA匹配；归档204项无敏感/生成/越界路径与链接；7个关键源码/元数据/说明文件与tag逐字节一致；SPDX有78个package |
| `gh attestation verify` | 限定repo、signer-workflow=.github/workflows/release.yml、source-ref=refs/tags/v0.2.0，退出0；JSON验证结果存在本地临时目录，不纳入仓库 |
| 开发服务恢复 | Vite在127.0.0.1:5173就绪，启动日志无错误；只恢复暂停的Web开发服务 |
| 收尾文档与学习速记检查 | 文档骨架/全仓本地链接/diff通过；Markdown75文件零错误；Node24/24（含更新后文档的源包与初始化回归）通过 |

附件的本地SHA256均与GitHub asset digest一致：

| 制品 | 字节 | SHA256 |
| --- | --- | --- |
| repo-metadata.tgz | 339466 | `26463b886c70424d39ca08d6935a1dd7f0d5605848efdc4d00520aeb060860b3` |
| release-manifest.json | 294 | `d7d7deef8c121a957cccf46410d265b01cf68b9c063541f10b15b3bc48e8ae82` |
| sbom.spdx.json | 355034 | `4a7318c75aa1e60f1e1180db1f357a2ae80d3e10e977cf98a6784949962f89c0` |

遗留不阻断本次源码发布：真实B1模型未验证；B2设计待复核且B2–B4未实现；Starlette弃用提示、setup-node旧Node runtime提示另属升级债；SBOM与provenance不等于漏洞审计或生产部署通过。没有模型调用、个人数据上传或DB迁移/删除。
