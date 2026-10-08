# CI/CD 说明

这个模板自带一套不依赖具体语言栈的 CI/CD 骨架。

## 默认包含的内容

- `ci.yml`：Windows、Ubuntu、macOS 矩阵，运行文档/仓库/Action 检查、Node.js 语法检查、Node.js 与 Python 回归测试和源码打包；Markdown lint 在 Ubuntu 执行。
- `supply-chain-security.yml`：在 PR 上做依赖变更检查，并在 PR、定时任务和手动触发时运行 OSV 扫描。
- `release.yml`：手动触发的 release 流水线，用来打包仓库级制品、生成 provenance，并创建 GitHub Release。

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

现有 `scripts/ci.cjs` 在存在 `pyproject.toml` 时执行 `uv run --locked pytest`，测试无需模型配置。CI 与发布检查先安装固定版本 uv 0.8.13，再用 `uv sync --locked --python 3.11` 建立环境。默认 dev 组包含 pytest 与 pytest-asyncio。

本地运行 `uv sync --locked` 后执行 `npm.cmd run ci`（macOS/Linux 使用 `npm run ci`）。模型桩与 HTTP 模拟验证会在此运行；真实模型验证仍须单独记录，不能由 CI 离线测试替代。

## 默认 release 产物

当前 release 流水线会产出：

- `release-manifest.json`
- `repo-metadata.tgz`
- `sbom.spdx.json`
- 对 release artifact 生成的 GitHub artifact attestation

也就是说，即使项目还没进入真实部署阶段，这个模板也已经把“可追溯的制品封装”这一步准备好了。

本地执行 `npm run release-package`（PowerShell 用 `npm.cmd`）仅生成前两项；SBOM、attestation 和 GitHub Release 由 Ubuntu 发布任务生成。发布前先运行 `npm run ci`。本地检查和打包需要 Node.js 22+、Git、tar；Python 验收还需要 uv，无 npm 依赖安装步骤。

制品与初始化使用相同的精简规则，包含点文件、CODEOWNERS、文档骨架、Python 内核、pyproject.toml、uv.lock、.env.example 和测试；排除本地环境、Python 缓存、旧记录、演示页或 nono 扩展。解包后先执行 `uv sync --locked`，再运行 `node scripts/ci.cjs`。打包仅更新约定产物，不清空 `dist`。当前目录不是 Git 仓库时以 `unknown` 记录 SHA。阶段 A 交付源码包，不增加部署服务。
