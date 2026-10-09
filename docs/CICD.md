# CI/CD 说明

这个模板自带一套不依赖具体语言栈的 CI/CD 骨架。

## 默认包含的内容

- `ci.yml`：Windows、Ubuntu、macOS 矩阵，运行文档/仓库/Action 检查、Node.js 语法检查、Node.js 与 Python 回归测试和源码打包；Markdown lint 在 Ubuntu 执行。
- `supply-chain-security.yml`：在 PR 上做依赖变更检查，并在 PR、定时任务和手动触发时运行 OSV 扫描。
- `release.yml`：手动触发的 release 流水线，用来打包仓库级制品、生成 provenance，并创建 GitHub Release。

CI 的 push 门禁覆盖 `main` 和当前默认分支 `master`。发布先提交全部待发布源码与锁文件，创建并推送版本 tag，再以该 tag 为 ref 手动触发 `release.yml`（tag 输入保持一致）；Release 显式绑定执行 SHA，正文读取 `docs/releases/<tag>.md`。先确认对应提交的 CI 矩阵通过，发布后核对 tag、manifest 的 SHA、三项附件和 provenance，不用本地脏工作区的包冒充远端制品。

## 设计原则

这套默认流水线的目标，是在项目真正成形前先把交付链路搭起来，而不是假装已经知道未来项目该怎么 build 和 deploy。

当新项目的技术栈确定后，你应该把 `scripts/release-package.cjs` 里的占位打包逻辑替换成真实构建产物，而不是另起一套平行流程。

所有 GitHub Actions 都已经 pin 到 commit SHA。后续升级 action 时，也要继续保持这个约束。

## 推荐接入顺序

1. 保留 `ci.yml`，作为唯一默认常驻的仓库基础门禁。
2. 在 `scripts/ci.cjs` 里继续叠加项目自己的验证命令。
3. 用真实构建产物替换 `scripts/release-package.cjs`。
4. 技术栈和环境稳定后，再补具体的部署 job。
5. 即使交付方式变化，SBOM 和 provenance 这类供应链能力也建议保留。

## 阶段 A 的 Python 验证

现有 `scripts/ci.cjs` 在存在 `pyproject.toml` 时依次执行 `uv run --locked ruff check mini_learngraph`、`uv run --locked pyright mini_learngraph` 和 `uv run --locked pytest`，检查全部应用源码，测试无需模型配置。CI 与发布检查先安装固定版本 uv 0.8.13，再用 `uv sync --locked --python 3.11` 建立环境。默认 dev 组包含 pytest、pytest-asyncio 和固定版本 Ruff 0.16.10、Pyright 1.1.414。

本地运行 `uv sync --locked` 后执行 `npm.cmd run ci`（macOS/Linux 使用 `npm run ci`）。模型桩与 HTTP 模拟验证会在此运行；真实模型验证仍须单独记录，不能由 CI 离线测试替代。

本地 Markdown 门禁使用 `npx.cmd --yes --loglevel=error markdownlint-cli2@0.22.0 "**/*.md"`（macOS/Linux 使用 `npx`），与固定 Action 依赖版本一致。`.markdownlint-cli2.jsonc` 排除虚拟环境、node_modules 和 dist，避免检查依赖或生成制品中的第三方文档；仓库 Markdown 规则保持不变。

## B1 HTTP 与 Web 门禁

FastAPI/Uvicorn锁定在uv.lock；默认pytest加入strict JSON/动态澄清、完整图结构/归属/联合DAG、SQLite CAS/历史/重启中断、12路由/OpenAPI与Host/Origin/body/安全错误测试，不读取真实模型配置、不访问模型。默认Ruff/Pyright仍检查整个mini_learngraph。

存在web/package.json时，同一个scripts/ci.cjs顺序执行npm ci、typecheck、lint、test、build、Playwright Chromium安装、test:flow与test:api-flow；流程不能并行争用固定端口，不另起绕过默认CI的入口。test:flow使用HTTP mock；test:api-flow使用真实FastAPI/安全边界与临时SQLite，但Provider仍为固定桩，不能证明真实模型效果。Windows通过npm-cli.js运行，不直接spawn npm.cmd；npm run ci会提供npm_execpath，直接node入口使用Node安装相邻npm CLI（Linux/macOS可走PATH npm）。Linux需具备Playwright系统库；缺失应安装对应系统依赖再复验，不以skip冒充流程通过。

Git/源码复制排除生成的test-results、playwright-report、.playwright目录，避免并行流程测试写删trace时产生复制竞态，也不分发本地浏览器记录；源码tests/e2e、Playwright配置和lock仍保留并执行。

真实B1验证单独执行`uv run --locked python scripts/verify_learning_model.py --stage b1`，默认SKIPPED/退出2；获准网络/预算后加`--allow-configured-model`。真实效果与桩测分开登记，前端开发中全量CI失败不得当作后端已验收。源包现在保留web目录及lock，仍排除node_modules/dist与本地数据库；模板裁剪execution task记录，契约链接计划目录以免悬空。

## 默认 release 产物

当前 release 流水线会产出：

- `release-manifest.json`
- `repo-metadata.tgz`
- `sbom.spdx.json`
- 对 release artifact 生成的 GitHub artifact attestation

也就是说，即使项目还没进入真实部署阶段，这个模板也已经把“可追溯的制品封装”这一步准备好了。

本地执行 `npm run release-package`（PowerShell 用 `npm.cmd`）仅生成前两项；SBOM、attestation 和 GitHub Release 由 Ubuntu 发布任务生成。发布前先运行 `npm run ci`。本地检查和打包需要 Node.js 22+、Git、tar；Python 验收还需要 uv；有Web时默认CI安装其锁定npm依赖，根工具仍无运行依赖。

制品与初始化共享文件复制及环境/缓存排除规则，包含点文件、CODEOWNERS、Python 内核、pyproject.toml、uv.lock、.env.example 和测试。源码包保留完整项目文档，包括计划、验收、history 和学习记录；初始化模板继续精简任务记录，并可使用 `.template` 的文档覆盖。源码包直接使用工作区文档，不使用初始化专用覆盖。演示页和 nono 扩展仍不分发。

打包先检查暂存目录中 Markdown 的本地文件链接，包括图片、内联链接和引用定义；跳过代码示例、外部 URL 与仅锚点链接，不校验标题锚点或网络可用性。缺失目标或越出包根目录时失败，保留既有制品。此门禁及包内 Trace 文档回归由 Node 测试覆盖。

解包后先执行 `uv sync --locked`，再运行 `node scripts/ci.cjs`。打包仅更新约定产物，不清空 `dist`。manifest 的 SHA 表示 HEAD，制品内容来自当前工作区；未提交改动不能由 HEAD SHA 单独证明，验收须检查实际包内容。当前目录不是 Git 仓库时以 `unknown` 记录 SHA。阶段 A 交付源码包，不增加部署服务。
