# B1 学习目标与图谱 Web

本机个人学习入口；仅包含目标澄清、透明假设审阅、候选图谱审核和明确发布/正式修订。
不含 B2 教学、B3 练习、B4 推荐，不上传资料、不展示数值掌握分。
接口唯一事实源是 [B1 冻结契约](../docs/design-docs/learning-b1-api-contract.md)，
阶段验收由派单人与独立审查确认，见[实施计划目录](../docs/exec-plans/active/)；
当前唯一计划为 `learning-loop-web.md`（初始化模板会裁剪具体任务记录）。

## 安装与启动

需要 Node.js >=22.12（仓库推荐 Node 22+）、npm、后端所需的 Python/uv。
从仓库根目录运行（Windows 使用 `npm.cmd`，其他平台使用 `npm`）：

```powershell
npm.cmd --prefix web ci
npm.cmd --prefix web run dev
```

浏览器打开 `http://127.0.0.1:5173`；开发服务只绑定回环，固定端口且被占用时直接报错。
另一个终端按[后端说明](../mini_learngraph/api/README.md)启动：

```powershell
uv run --locked python -m mini_learngraph.api
```

默认请求 `http://127.0.0.1:8000/api/v1`，直接使用后端的精确 Origin/CORS 守卫，
没有代理绕过、凭据、自动 HTTP 重放或假成功。缺模型配置不阻止查询已有资产；
创建或生成失败将显示服务端已保存的草稿与明确错误。

可在 `web/.env.local` 配置 `VITE_API_BASE_URL` 为**获准本机服务**的完整 `/api/v1` 地址。
这不是模型配置；不要将密钥、真实学习内容或远端 API 地址写入 Vite 环境变量。
改变开发/预览端口时需同步后端允许的精确 Origin，不能启用 `*`。
`npm.cmd --prefix web run build` 输出 `web/dist/`，`run preview` 仍使用回环 5173；
此任务未部署，预览不是生产发布方案。

## 页面与恢复约定

- 左侧列表继续已有目标；URL `?goal=<服务端ID>` 刷新读取目标/图谱，绝不重放创建或生成。
- 澄清问题按服务端动态 key 展示理由/图谱影响，只提供题目允许的选项、自定义与跳过。
  跳过的默认假设始终可见；若不接受，必须改为具体回答。
- 模型建议假设默认不接受，可逐条接受/拒绝；目标事实所有字段可审阅修改，
  未设定可选字段明确提交 null。人工假设保留 `user:` 来源和理由。
  修改回答/值/假设会清除先前的确认勾选，确认目标必须再次明确勾选。
- 候选节点名称/类型/描述/教学策略/重要性/可空位置与所有关系均可增删改。
  新节点提交临时 ref 和 `id=null`，服务端赋 ID；端点下拉只来自本图。
  删除节点同时清理关联边，但不隐式删除子树；子节点需在同次整图保存前改挂。
- 422 全部 issues 展示 path、node ID/ref 和 edge index，相关目标事实字段、节点/关系
  以文字和边框标记；目标文本字段增加 `aria-invalid`。
  本地可保留临时坏结构，服务端不会保存半图。
- 409 或刷新发现不同 revision 时保留草稿，禁止保存；对照最新快照后人工调整，
  点击“已人工合并，采用最新修订号”才可重新确认。也可显式放弃草稿采用最新图。
  对照和历史快照展示全部可编辑节点字段（含重要性、可空位置）以及关系端点 ID，
  方便区分同名节点；不会自动把远端变更合并进本地输入。
- 发布只针对已保存候选，必须明确勾选；未保存编辑不能发布。
  正式图修改使用 `/revise`，要求 reason 和新的明确确认，不发送候选 PUT。
  历史修订按 revision 读取，仅展示，不提供隐式回滚。
- 写入失败/响应丢失先 GET 列表或详情确认事实；状态读取失败时暂停写入，
  成功“读取最新资产”后才能显式操作。创建响应不确定时禁止直接重发，
  先列表找回草稿；用户核查后仍可明确决定另建目标。
  手动刷新/切换目标时 GET 失败同样暂停写入，切换“创建新目标”不会绕过暂停。
- 草稿/原始目标输入暂存在当前标签页 `sessionStorage`；同一标签页刷新可续接，
  不作为服务端事实、不同标签页不共享草稿，关闭标签页后不承诺保留未保存输入。
  存储不可用时表单仍可操作，但刷新只恢复服务端资产。此本机临时存储含学习内容，
  不是加密保管；代码不上传或记录这些草稿。
- 生成后的目标补充 GET 绑定当前读取生命周期；切换目标、重新读取或离开页面使
  旧读取失效，同一目标的迟到响应也不能降低已读取的 revision。
- 查询失败、空列表、生成等待、失败状态均有提示和明确操作。所有表单控件有标签，
  原生按钮/radio/checkbox/select 可键盘操作；跳到主要内容链接、可见焦点、状态/错误
  live region、窄屏单列与 reduced-motion 样式作为基本 a11y 支持。

## 选型与依赖

独立 package/lock 不改根工具骨架；精确直接版本与 lock 固定传递依赖。
React 19.2.0 / React DOM 19.2.0、TypeScript 5.9.3、Vite 7.3.7 与 React 插件 5.1.0。
小规模个人资产直接用 React state、原生表单和 CSS；不引入 UI、Router、状态管理、图布局库。
Web 不依赖根包：已移除本轮 npm lock 维护意外加入且未使用的 `mini-learngraph: file:..`；
更新依赖请先进入 `web` 再执行 `npm install`，不要从根目录用 `--prefix web install`
更新 lock（本机 npm 10.9.2 在该用法下把当前根包加入了 Web）。标准 `--prefix web ci`
仍可从根目录复现安装，不修改包清单。
图谱用完整节点/关系表单编辑，易于键盘操作和结构错误定位。
设计采用浅色靛蓝、清晰分区与高对比文本，系统字体，无外部字体/图标请求。

开发依赖：ESLint 9.39.0 / typescript-eslint 8.71.1、Vitest 4.1.11 + jsdom 27.0.0、
Testing Library、Playwright 1.56.0。Vitest/Testing Library 验证权限守卫和请求形状，
Playwright 验证真实浏览器中的完整流程与刷新行为，均不进生产包。
最初选用的 Vite/Vitest/typescript-eslint 旧次版本存在安全通告，已经同大版本更新；
当前全依赖 `npm audit` 为 0 vulnerabilities。

初次无 lock 安装 Vitest 4.1 时 npm 10.9.2 的 Arborist 触发 `edgesOut` 内部错误；
临时使用 `npx --yes npm@11.6.2` 生成 lock，没有全局安装或修改 npm 配置。
落定 lock 后，系统 npm 10.9.2 的标准 `npm ci` 已成功验证，日常安装不需要 workaround。

## 检查入口与证据

```powershell
npm.cmd --prefix web run typecheck
npm.cmd --prefix web run lint
npm.cmd --prefix web test
npm.cmd --prefix web run build
Push-Location web
npx.cmd playwright install chromium
Pop-Location
npm.cmd --prefix web run test:flow
npm.cmd --prefix web run test:api-flow
```

`check` 串联类型/lint/单元/构建/纯 Mock 浏览器流程，安装 Chromium 后可一次执行。
`test:api-flow` 另起真实后端 `create_app` + Uvicorn + 临时 SQLite，使用固定 Provider 桩，
不接触个人数据库、不调用真实模型、不增加测试控制 API。需要根 Python locked 环境；
8000 必须空闲，该测试不会复用正在运行的个人 API。两个浏览器入口均自动管理 Vite，
CI 不复用已有开发服务器；Linux CI 需 `playwright install --with-deps chromium`。
API 测试以 `uv run --locked` 解析 Python 后直接管理自己的子进程与独立临时库，
实际终止生成中的进程并以同库重启；启动恢复标记、显式重试、发布后再次重启/历史读取
都有浏览器断言。仅停止测试自己创建的 Python 进程，不扫描或结束已有个人 API。
根 CI 应调用这些独立标准 scripts，不能只验证纯 Mock 代替 API 集成或真实模型。

2026-10-09 续接本机自测（不是独立最终审查；复用上轮产物后补测）：

| 检查 | 实际结果 |
| --- | --- |
| `npm --prefix web ci --no-audit`（系统 npm 10.9.2 / Node 22.17.0） | 安装 268 packages，退出 0；随后顺序执行 `check` + `test:api-flow` 通过 |
| `typecheck` / `lint` | 均退出 0 |
| `test` | 4 files / 13 tests passed，退出 0 |
| `build` | Vite 7.3.7；33 modules；JS 226.19 kB / gzip 71.22 kB，退出 0 |
| `test:flow` | 纯 HTTP Mock，12 passed；CSV 向导/假设、图谱增删改挂/发布/正式修订/历史、409/422、丢失响应、失败显式 retry、GET 恢复失败守卫、刷新/键盘/375–1440px；续接新增手动 GET 失败防绕过与已有子节点改挂/父节点删除场景 |
| `test:api-flow` | 实际回环 HTTP/CORS + FastAPI/严格 Schema/SQLite/CAS，3 passed；CSV 到正式修订/历史/刷新、失败 GET/retry、目标事实 422 字段定位、真实 409 合并及联合环 422、生成中进程中断/同库重启/retry/发布后重启/历史继续读 |
| `npm audit --registry=https://registry.npmjs.org`（包含开发依赖） | 0 vulnerabilities，退出 0；默认镜像 audit endpoint 404，因此显式用 npm 官方入口查证 |

2026-10-09 12:54 起第二次续接：先复查 `git status` / `git diff`，复用原 Web 文件，
仅修复本说明中的具体 active 计划链接（改为目录，保留契约入口），未改模板裁剪或门禁。
前台顺序复跑 `typecheck`、`lint`、`test`、`build`：退出均为 0，单元仍为 4 files /
13 tests，构建仍为 33 modules / JS 226.19 kB（gzip 71.22 kB）。随后分别运行
`test:flow`（12 passed，10.1s）与 `test:api-flow`（3 passed，7.9s），均退出 0。
额外运行根 `node --test tests/tooling.test.cjs`：23 passed / 0 failed，包含初始化
裁剪和制品本地链接检查，确认修复不再产生悬空链接；`git diff --check` 退出 0。
这次没有重装依赖或重跑 audit，上表安装/audit 仍是上轮证据；根全量 CI、真实模型和
独立审查结果由各责任人另行记录，不能用本次 Web 自测代替整体验收。

2026-10-09 13:06 独立审查后的修复自测：严审发现生成后迟到 GET 串错目标、409 对照
缺重要性与位置两项阻断；新增浏览器回归先实跑 **3 failed**，分别复现切换目标后串错、
同目标最新 r5 被迟到 r4 降低、最新快照没有重要性。修复 `src/App.tsx` 读取生命周期/
同目标 revision 守卫与 `src/GraphEditor.tsx` 完整快照后，定向复跑 **3 passed**。
随后前台顺序运行 `check` + `test:api-flow`，退出均为 0：类型/lint、单元 **13 passed**、
Mock 浏览器 **15 passed（12.1s）**、实际 API 浏览器 **3 passed（8.0s）**；
构建 33 modules，JS **226.62 kB / gzip 71.35 kB**。新增 Mock 回归同时断言人工
合并保存保留远端重要性/位置及本地描述、历史快照字段完整。
实现过程的首次全检遇到 effect cleanup 的 ref lint 诊断，改为稳定的失效回调后上述
全检通过，没有关闭规则；随后提交严审独立复验。

严审独立复验（delegation `1e1b865f-dc4b-4dbc-b794-9722adb22f48`）确认上述两项
阻断均可撤销，Web 修复可交付，无新增阻断。其新增 `src/GraphSnapshot.review.test.tsx`
及一条 Mock 浏览器回归，补查零/负/边界坐标、同名关系端点 ID、迟到 GET 不退出新目标
页面或抹去新输入；未改业务代码。独立运行 `check`、`test:api-flow` 均退出 0，最新计数
为 **5 files / 14 单元、16 Mock 浏览器、3 实际 API 浏览器**；`git diff --check` 通过，
测试端口已释放。以上独立检查仍使用固定 Provider 桩，B1 最终验收归派单人。

续接中曾误将 `npm ci` 与 API 流程并行，重装中的 `node_modules` 导致 Vite 缺 Rollup
原生依赖而未启动；安装结束后顺序执行 API 流程 3/3 通过，不是业务接口失败。
依赖安装与任何类型/构建/测试不可并行；两个浏览器流程使用同一 5173/8000 也须顺序执行。

`test:api-flow` 证明真实软件边界兼容冻结契约，**模型仍为固定桩，不证明真实模型效果**。
真实模型检查由后端/派单人单独登记。未验证远端 CI 三平台矩阵、完整读屏工具、个人数据库
迁移或生产部署；不宣称 B1 整体验收通过。

测试文件：`src/*.test.ts(x)`、`tests/b1-flow.spec.ts`（Mock）、
`tests/api-flow.spec.ts`（实际 API）、`tests/api_fixture.py`（固定 Provider/临时库）。
Mock 只用于测试，生产入口没有 Mock 开关或通用成功兜底。

## 给根文件维护者的接入建议

此派单只修改 `web/**`，根文件由后端/派单人维护：

- `scripts/ci.cjs`：已有 Web 标准检查之后，增加 `npm --prefix web run test:api-flow`，
  与纯 Mock 流程分别保留结果。API 测试需要 locked Python 环境和空闲的 8000。
- `scripts/lib/common.cjs`：在制品/模板排除名单加入 `test-results`、`playwright-report`，
  不把失败 trace/截图/本机结果打包；`web/.gitignore` 已为 Git 排除这些目录。
- 根 README、`docs/CICD.md`、`docs/WINDOWS.md`：链接本 Web 说明，记录上述安装/启动/检查
  入口；无 lock 安装的 npm 10 内部错误与标准 `npm ci` 验证结果分别说明。
- 唯一实施计划记录最新独立复验：14 单元 + 16 Mock 浏览器 + 3 实际 HTTP/SQLite 浏览器，
  两项 Web 阻断已由严审撤销；真实模型效果未验证、B1 最终验收待派单人，不能把固定
  Provider 桩算作真实模型证据。
- 按 `docs/HISTORY_GUIDE.md` 留同任务 history 索引；本阶段同时触发可迁移恢复模式与并发
  陷阱，建议按 `docs/learnings/WRITING_GUIDE.md` 沉淀“请求结果未知不等于资产失败”：
  HTTP 失败先读持久化事实，CAS 冲突保留编辑基线/最新快照并人工合并，而不是自动覆盖。
