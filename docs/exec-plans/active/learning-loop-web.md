# 学习闭环 + Web：B1 → B4

## 目标、范围与风险

状态：2026-10-09 计划与 B1 契约已获周经理、严审设计复核（历史冻结契约 SHA 前12 `c9a2d8720c73`），**B1 本机固定Provider软件契约验收已获周经理接受；真实模型未验证。进入B2契约/持久化/Agent接入设计，待周经理与严审复核后派实现**。本任务只建立这一份 active execution plan，不另建平行计划。产品输入来自自包含的[学习业务交接](../../design-docs/learning-business-handoff.md)，无需原仓库。阶段 A 的既有验收保持原范围，见[状态](../../PHASE_A_STATUS.md)。

### 目标与授权

- 用户经询问选择“全部按建议推进 B1→B4”：本机个人、服务端稳定学习者 `local-user`、默认回环地址、不上传资料；候选节点/关系可编辑，正式图谱明确确认修订；简答评价失败保存答案并允许重评；推荐直接可见、用户自主选择；前端只显示状态与依据，不展示数值掌握分。
- 授权本地实现、可逆编辑与验证；用户“全部按建议B1→B4”的本地授权持续有效，无需阶段逐项审批。B1前后端软件契约已验收；当前B2派单仅限计划/契约设计，合同经周经理与严审复核后再派业务实现，不抢先写代码。
- 无部署、发布、外部写入、批量删改数据授权。真实模型检查单独使用已有获准的模型配置；本轮不读取 `.env`、不调用模型、不声称验证了效果。LAN/公网/多人使用需另行认证授权设计。
- 贯穿验收：“学习 Python，最终能独立处理 CSV 数据” → 澄清/假设 → 确认目标 → 编辑候选/发布 → 节点教学 → 选择题或简答 → 证据/状态 → 自主选择有理由的下一步。只验证知识学习，不执行用户代码或实际 CSV 产物。

### 包含与非目标

包含 B1 目标/图谱、B2 节点学习、B3 作答证据、B4 规则建议的本地 Web 闭环及持久化、相关检查和文档。非目标：上传/检索、沙箱/交互实验、语音/移动端、团队治理、全局概念合并、星级双状态、长期记忆、Skills/MCP 市场、完整 Roadmap 排期、图谱自动发布、模型失败规则假成功。

首版 HTTP 非流式、显式重试；不建 SSE、后台队列、通用 Run 状态机/检查点/自动重放恢复平台。领域中的生成/评价状态只记录本业务事实，Trace 仍只观察。

### 工作区基线与保护

2026-10-09 11:46，HEAD `dadf3a9`；`git status --short` 为 **19 个 tracked 修改、7 个 untracked 文件、无 staged 差异**。`git diff --stat` 为 219 additions / 43 deletions。这些是接手前已有内容，不属于本计划的实现证据：

```text
M README.md
M docs/ARCHITECTURE.md
M docs/CICD.md
M docs/QUALITY_SCORE.md
M docs/design-docs/index.md
M docs/exec-plans/tech-debt-tracker.md
M docs/releases/feature-release-notes.md
M mini_learngraph/config.py
M mini_learngraph/loop.py
M mini_learngraph/runner.py
M mini_learngraph/tools.py
M pyproject.toml
M scripts/ci.cjs
M scripts/create-project.cjs
M scripts/lib/checks.cjs
M scripts/lib/scaffold.cjs
M scripts/release-package.cjs
M tests/tooling.test.cjs
M uv.lock
?? .markdownlint-cli2.jsonc
?? docs/PHASE_A_STATUS.md
?? docs/design-docs/learning-business-handoff.md
?? docs/exec-plans/completed/phase-a-closeout.md
?? docs/histories/2026-10/20261009-1013-phase-a-closeout.md
?? docs/histories/2026-10/20261009-1102-learning-business-handoff.md
?? docs/learnings/2026-10/source-package-document-links.md
```

不用 checkout/reset/stash 覆盖已有工作；新增本计划、契约、history，仅在现有设计索引追加入口。后续每次实施先复查 status/diff，不把并行改动归为自己的工作；提交由派单人另行安排。

### 技术决定及理由

| 决定 | 理由与边界 |
| --- | --- |
| FastAPI + 现有 Pydantic 2；Uvicorn 单进程 | 与 Python 内核及严格 Schema 复用；单本机服务不需额外网关。B1 实施锁定兼容依赖到 `uv.lock`，不在本次文档交付安装依赖 |
| SQLite + 标准库 `sqlite3`，少量领域仓储函数 | 单学习者无需图数据库/ORM。同步数据库短操作在工作线程执行，不阻塞 async 模型请求；外键/唯一约束、显式短事务、条件 revision 更新。模型调用时不持写事务 |
| React + TypeScript + Vite，`web/` 独立 package/lock | 前端类型和构建独立可复查，不破坏根目录无 npm 运行依赖的工具骨架；具体兼容版本在 B1 lockfile 落定 |
| 领域用例在 `mini_learngraph/learning/`，HTTP 在 `mini_learngraph/api/` | API/教学工具调用同一用例；领域不依赖 HTTP/React，Runner 不读数据库。按真实代码创建文件，不预建插件层 |
| 专用结构化请求复用 `ModelProvider.chat(messages, tools=[])` | 当前无 `generate_json`。完整 JSON 对象严格解析、Pydantic 和领域二次校验；绝不截取代码围栏片段、造通用图谱或启发式评价假成功 |
| 一目标一图谱资产、修订快照 | 缩小 B1 选择歧义；候选整图替换/正式整图确认修订。graph ID 稳定，revision 是并发令牌；node_version 独立于关系/排版/优先级修订 |
| 非流式同步 HTTP + 已保存失败状态 | 无须轮询平台；页面自行等待，再 GET 查询。请求/进程中断只标记本业务 interrupted，不自动重放模型/工具 |

B1 [接口契约](../../design-docs/learning-b1-api-contract.md) 是前后端唯一事实源；设计示例不是已实现的 OpenAPI。B1 实现应导出 `/openapi.json`，由严审核对字段、错误及快照；不偷偷改约定，有变动先更新契约并同步阿岚。

### 风险及缓解

| 风险 | 缓解与复核点 |
| --- | --- |
| 本机未认证服务被网页跨源写入 | 默认 `127.0.0.1`；限定 Host/Origin，拒绝不允许的 Origin/null Origin；JSON 写入、体积上限、无 CORS `*`。这不是多人认证方案 |
| 模型非法/截断 JSON、注入或超时 | strict 全文 JSON、extra forbid、ID/引用校验、无发布工具；数据作为数据；失败落状态，用户显式重试。请求/错误不含密钥或原始模型文本 |
| 并发覆盖、结构坏图、证据失效 | 每个写操作 expected_revision 事务 CAS；联合 DAG/归属校验；不可变历史、节点版本精确失效，不因无关关系/排版改动清空全部证据 |
| SQLite 事务跨模型请求，异步阻塞 | 快照读 → 释放事务 → await → CAS 短提交；busy 返回可重试错误，线程内连接，不跨线程共享连接 |
| 写工具已成功但回答失败 | 业务独立保存；稳定业务 operation key 去重；响应显示业务效果，不以最终回答判断事实 |
| 状态被刷题/参与记录推高 | 固定 assessment 规则，当前版本有效证据、同题最新一条、服务端提示/重试计数；浏览/提问不产生掌握证据 |
| 重启后工具链不完整 | 只重建 completed 且工具配对完整轮次；执行中轮次 interrupted，不自动重放 |
| 验证无模型配置/预算 | 离线完成实现与桩测；真实检查明确 skipped/未验证，不冒充完成真实效果验收 |

### 数据与迁移边界

B1 创建 `schema_version=1` 的本地 SQLite：Goal（完整回答/假设/生成状态）、Graph（当前指针/状态/revision）、GraphRevision（发布/编辑快照、before/after、actor、reason）、NodeVersion（内容及历史引用）。快照中的边属于该 graph revision；约束一目标一图、IDs 归属、revision 唯一。JSON 列用于小规模完整快照，不另建图存储。

B2 增加 Session/Turn/Message；B3 增加 Exercise/Attempt/Evaluation/Evidence；B4 优先按读取快照计算状态/行动，不建设独立调度平台。每阶段持久化约束/迁移测试必须完成后才进入下一阶段。

每次 schema 升级前关闭服务并备份 DB（包含 WAL 时用 SQLite backup API 一致备份），记录 schema_version；回滚采用“旧应用 + 备份恢复”，不承诺丢失新增列的逆迁移。新库初始化可删测试库重建；有真实资产时不删除数据、不直接不可逆迁移，先交派单人回滚方案并获确认。历史设计阶段没有创建/修改数据库；B1 实施验证仅使用临时测试库，不修改真实资产。

## 进度与决定

- [x] 核查工作区、读取交接/阶段 A/架构/计划模板及代码、协作、安全、Windows、CI 约定。
- [x] 记录用户授权的六项产品决定，建立唯一 B1→B4 计划和可独立开发的 B1 契约。
- [x] 本轮文档骨架、链接、Markdown、差异检查并填证据。
- [x] 周经理、严审复核计划和契约；已派 B1 后端实施（delegation `10f0f66e-2d07-4dd1-a807-05d67beacf4c`）。
- [x] B1 目标与图谱实现、检查、前后端软件契约验收（本机固定Provider；真实效果未验）。
- [x] B2 契约/持久化/Agent接入设计落盘（仅文档，设计复核待派单人/严审）。
- [ ] 周经理与严审复核B2合同，同步阿岚后派#8后端/#9Web/#10独立验收实现任务。
- [ ] B2 节点学习实现、检查、前后端验收。
- [ ] B3 作答证据实现、检查、前后端验收。
- [ ] B4 下一步行动实现、检查、完整闭环验收。

### 增量依赖、职责与门禁

每个增量：先冻结相关接口 → 后端/前端并行 → 严审独立复验 → 周经理验收 → 更新本计划。B1→B2→B3→B4 顺序依赖，不跳过未解决的数据/事务问题。

| 增量 | 后端（老秦） | 前端（阿岚） | 测试/门禁（严审） |
| --- | --- | --- | --- |
| B1 | FastAPI/SQLite、严格 JSON adapter、Goal/Graph 用例和 revision 快照、契约测试、模型 smoke 入口 | 目标列表/向导、动态选项/自定义/跳过、假设审阅、候选节点关系编辑、发布/正式修订、409/422/重试处理 | 跳过假设可见；过期 revision 不覆盖；坏结构 422 定位；模型失败可 GET/重试且不假成功；正式修改有明确确认；重启读取 |
| B2，依赖 published B1 | 学习会话、选区归属/版本快照、Loop 工厂及 Runner 复用、成功配对历史重建、消息业务去重 | 工作台选区、顺序聊天、等待/失败、业务效果摘要、历史快照可查看 | loop→csv 当前上下文切换但旧快照保留；失败不混入有效历史；写工具后模型失败事实仍可查；重启 interrupted 不重放 |
| B3，依赖 B1 node_version/B2 上下文 | 单选/简答、固定题目标准、提示/重试、提交幂等、严格 rubric 评价、短事务 Evidence、评估规则 v1 | 独立作答、待评/失败答案保留、重评/反馈/缺失点、状态与证据（无数值掌握分） | private 答案提交前不可见；部分正确 2/3；同键同答案复用/不同答案409；评价失败无 Evidence；重评替代不累加；旧内容版本不参与当前评估 |
| B4，依赖 B3 状态 | 规则推荐、前置检查、稳定排序、同一输入快照/版本/时钟、无模型越权推荐 | 下一步直接可见、理由/blocked_by、用户选择节点/继续学习 | weak 前置阻塞、review 时钟边界、排序相同确定；阻塞可自主访问；重启后贯穿闭环继续 |

每阶段离线必需：相关 pytest、Ruff/Pyright 全应用、Web 类型/单元/构建及流程测试、`npm.cmd run ci`。将新增 Web/API 检查纳入现有 `scripts/ci.cjs`，不另起绕过默认流水线的门禁。远端矩阵与本机结果分别报告，未发布不得写已发布。

### B1 最低验收矩阵

1. 真实或模型桩生成动态问题（含非固定 key）；选项、自定义、跳过逐题守卫；确认时完整保存问题、答案、自动采用假设和人工假设。
2. 模型缺配置/超时/空文本/截断/非法 JSON/非法 refs 均为明确失败；已有 Goal 不丢，Graph 不能假装 candidate/published；GET 后显式重试。
3. 唯一 root、非根≥1、ID/边合法、contains 唯一父/根可达、contains+prerequisite 联合无环；关联 node IDs/edge indexes 进入 422 details。
4. 两次 expected_revision=同值的修改恰一成功一409；发布/正式修订同样 CAS；失败不产生半个快照。
5. 候选整图修改节点/边；删除不得留孤儿；正式图不得调用候选编辑路由，需 `confirmed=true` + reason；历史修订可读。
6. 内容变动只升级相应 node_version，位置/权重/关系变动不升级；删节点保留旧来源，不能复用已删除 ID；新节点服务端赋 ID。
7. 未允许 Origin/Host、未知字段/资源归属、过大 body 等有安全错误；请求不接收 learner_id。
8. 刷新和服务重启后目标、失败状态、候选/正式图谱、修订均可读；已有 CLI 行为和阶段 A 测试不回退。

### B2 设计/实施检查点与完整验收矩阵

2026-10-09，周经理在delegation `d3693fda-6704-43d3-a7fa-c6704ceeaf2e` 明确接受B1软件契约（#2/#4后端、#3Web），进入B2 **先设计后实施**。接受依据是严审独立完整默认CI：锁定安装退出0、Python474、B1定向242/新增14、Node测试24、Web单元14/Mock16/实际API3、Ruff/Pyright零、文档lint67文件零；不是本轮重跑，真实模型仍SKIPPED。保护测试配置隔离 `tests/conftest.py` / `web/tests/api_fixture.py`，不得退回读取个人dotenv/环境的旧夹具。

新增 [B2契约与接入方案](../../design-docs/learning-b2-api-contract.md) 是复核后的前后端事实源：8条非流式路由、strict请求/响应、明确非root的1..5节点选区/主节点顺序、当前图revision与逐轮node_version、会话/轮次/角色链与独立业务效果查询。B1路由和冻结正文保持不变；B2明确增加错误resource_type=session/turn，复核时同步TS/OpenAPI，不能默改既有含义。

关键选择：会话绑定稳定goal/graph，不固定永久图版本；每条消息显式所见revision，接受时取不可变快照，修订后的新轮用新图而旧轮不变。同submission同正文仅查既存结果（失败也是结果），不重新执行；新键是新提问，不是失败工具续跑。session锁覆盖获取选区→接受→Loop/Runner→最终保存，模型await不持事务。恢复只装配completed且配对完整历史；坏成功链拒绝调用模型而非静默拼接。B2生产仅get_selected_node/calculate，无练习/证据写工具；“写成功最终回答失败”用临时DB/安全工厂注入fixture_write验证，不冒充B3已实现。

后端#8、Web#9、独立验收#10已由周经理建任务；当前只改契约/计划/设计索引/同一history，无业务实现、依赖/CLI改动、模型调用、DB升级/个人资产操作。schema v2及离线v1→v2备份/事务失败回滚方案在契约第7节；真实库必须停止服务、先备份方案与派单人确认，本轮不迁移。远端矩阵、Starlettewarning、npm镜像audit404继续留债，不把本机绿灯写成上线/安全审计或真实模型通过。

| 检查点 | 实施步骤与可核验门禁 | 当前状态 |
| --- | --- | --- |
| B2-D | 契约/严格Schema/错误映射/工具清单/迁移方案/下列矩阵落盘；docs/links/lint/diff；周经理和严审复核，同步阿岚 | 初审R1–R4已修订送针对复核（#5）；尚未冻结/设计验收，不派#8/#9实现、不提交未通过方案 |
| B2-S | 临时库v2初始化、显式v1→v2迁移入口与备份/故障回滚测试；B1快照不变，旧CLI/reset不变 | 待复核后派#8实施 |
| B2-A | Session/Turn/Message用例、submission唯一键/条件状态、互斥、快照/历史配对守卫、Loop工厂/只读工具、安全夹具事实去重；先定向失败测试再实现 | 待复核后派#8实施 |
| B2-H/W | 8路由/OpenAPI与TS核对，工作台明确选区/多节点/等待/错误/同键查询/独立效果/历史快照；Web Mock+实际API临时库/固定Provider | 待复核后并行#8/#9 |
| B2-V | 默认npm.cmd run ci、专项矩阵、严审#10独立复验、周经理验收；真实教学smoke单独标软件桩或opt-in效果 | 业务验收未执行；真实效果未验 |

以下每行均为**未来B2必须通过的验收**，当前未实现/未执行；#10应逐项登记实现位置、固定输入、实际断言/命令和输出，不能仅抄最终回答：

| ID / 层 | 场景/操作 | 必须结果 |
| --- | --- | --- |
| B2-01 API/域 | confirmed/published同所属创建/发消息；分别goal未confirmed、graph未published、两者均坏、版本过期与状态同时坏；他目标或他学习者、未知UUID/字段/learner_id | 合法创建201；绑定422、不所属404、strict422；无模型调用/隐式选区。409精确断言完整details：invalid_state为{resource_type:实际goal或graph,resource_id:该ID,expected_revision:null,current_revision:null,failure_reason:null,issues:[]}；两状态均坏先goal。revision_conflict为{resource_type:graph,resource_id:实际graph ID,expected_revision:提交值,current_revision:真实值,failure_reason:null,issues:[]}且优先于状态；两code均retryable=false，接受前不占key/新turn；B1原路由和错误骨架不变 |
| B2-02 API/域/Web | 空/root/重复/>5/已删除/他图选区；concept/practice/assessment；多个节点顺序/第一主节点 | 非法422精确path/node_ids且零轮次；合法1..5按顺序，页面明确全部选区，不扩展前置/子节点、不生成练习 |
| B2-03 Agent/存储/Web | 先loop，再csv，后多选；模型固定桩捕获真实请求并刷新查历史 | 当前context仅本轮选区/主节点，旧user块/ContextSnapshot/节点内容版本逐字不变，历史仍可展开解释 |
| B2-04 域/API/Web | 图内容升级、关系/布局修订、删当前节点；旧revision发送/刷新最新图续接；模型await期间再次修订 | 旧revision409不占key；新轮取精确最新revision/node_version；删节点重选；等待中本轮保持接受时快照而下一轮取新图，无旧证据/伪掌握 |
| B2-05 存储/API | 同session/submission/body重复，trim等价；改content/revision/选区或顺序；旧图删节点后同键查询 | 原终态同id/index/messages/快照200，无额外模型/工具；不同正文409指原turn；历史同键结果不因新图失效 |
| B2-06 并发/API | 同键executing重复、不同键同会话同时；在取选区/构建context/最终保存阶段人为暂停并抢发 | 只有一条executing/序号/user/Provider执行；第二个409/operation_in_progress且不入队；锁覆盖全边界，非只包await |
| B2-07 并发/Agent | 同goal/graph的两会话同时loop与csv，嵌套参数/快照修改探针 | 两个Provider请求和工具闭包只见自己的选区/历史；不可变副本不串会话，无共享current_node/Loop/history |
| B2-08 Agent | direct completed、单/多工具、已知工具错误→模型修正→最终回答；同session两个独立用户轮各返回原始call_1→最终回答，重启续接 | 两轮均completed，Provider共4次/工具共2次；各轮映射为不同ltc_<turn_uuid_hex>_1且assistant/tool两端相等，历史服务端ID重启不变；捕获第二轮实际Provider输入含第一轮完整配对及当轮新增链，原始ID跨轮复用不误杀；预装配user等于实际当前user，final_text不重复，completed守卫通过 |
| B2-09 Agent/API | model_error、截断/过滤/空/无效响应、step_limit、意外tool_error、context_error、缺配置/意外异常；缺配置时哨兵计Provider/工具 | 失败stop_reason/error映射稳定、answer=null；首次ApiError带已接受turn；GET可查部分未完成消息；后轮有效历史无失败链。缺配置先接受合法输入/快照/预装配user→failed/configuration_error，Provider/工具0、未发送；不妨碍其他读取，不以保存user宣称已发模型 |
| B2-10 历史/安全 | completed旧轮坏JSON（快照/messages/tool_calls/error字段）、缺tool、孤儿/重复服务端ID、跨轮配对、角色错误、快照user不一致、answer不匹配；伪造completed但eligible=false；合法failed/interrupted排除 | 先原子接受新合法请求/精确快照/messages[0]再读所有completed、不筛eligible；坏历史使新轮failed/history_error且HTTP500 history_invalid指新turn，Provider/工具/模型配置读取均0。GET turn及submission200查同一新failed/id/index/快照/user；同键原正文重发200原failed、零重执行。completed falseeligible也拒绝，不跳坏轮/补现图，错误不泄露原内容；正常DB CHECK拒绝该伪造值，读取守卫用受控损坏副本独立验证；合法failed/interrupted整轮排除 |
| B2-11 工具/安全 | node查询选区外/他图/伪身份/version、未知工具/SQL/写练习名；受限calculate正常/除零/AST攻击 | 生产定义恰get_selected_node/calculate，strict参数/作用域错误、安全tool结果；零代码/文件/网络/发布/练习/证据写入 |
| B2-12 Agent/安全 | finish异常、带工具的length/content_filter；同批call_1重复、同执行先call_1后另一响应call_1；独立用户轮call_1复用对照；完整ModelResponse含usage/arguments，UTF-8 ASCII/中文恰262144/262145字节、深度32/33、16/17调用；转换前/后预算 | 合法跨用户轮均completed（见08），同批重复工具0；同执行重复为invalid_response，Provider2/工具1（只执行首批，拒绝批0），不能每响应换prefix/slot掩盖重复。精确口径见契约6.1.2：256KiB/32层/16调用等值合法，超1字节/层/调用或usage单独撑大完整体均拒绝、该响应工具0；转换前后均检查。length/filter保留既有停止原因/零工具，其他非法invalid_response、失败可查；不削弱内核、不读私有推理 |
| B2-13 夹具/域/API/Web | 安全注入fixture_write提交合成事实后最终模型失败/取消；同领域operation key重试/换call_id/不同参数 | 独立GET效果可查已提交事实，回答失败不回滚事实；相同key参数同id，冲突无第二写；同HTTP submission不重执行；生产无fixture注册，明确不等于练习已实现 |
| B2-14 事务/故障 | 输入保存、事实+operation、最终消息/状态保存分别注入异常/SQLitebusy；模型await时另一会话写DB | 无半个接受/业务事实/成功历史；已接受失败指turn，最终落库失败仍可GETexecuting，不假成功/不重调模型；await期间独立DB写成功，连接不跨线程 |
| B2-15 重启/恢复 | 执行中进程杀停、工具提交后杀停、正常成功/失败后重启、重复恢复；无模型配置启动 | 仅executing转interrupted且index不回退，未丢事实/快照；不补造消息、不自动重放；成功配对历史可重建；启动/GET不读模型配置/不联网 |
| B2-16 API/Web | 丢POST响应按submission查；同键failed/interrupted重发200；人工重新提问新键；404未接受后同键重发 | 持续保留原key/body，已接受不自动POST；HTTP200仍按failed显示；新键是新轮快照不是旧工具续跑，业务效果不被最终文本覆盖 |
| B2-17 列表/API | 多会话/多轮/相同时刻，过滤不匹配、分页边界/limit1/100/101、重复未知query、cursor与序号上限 | Session稳定created_at降/ID升，Turn索引升；无错误会话泄露/同轮重复，合法next字段；坏query422、极限session409而非整数溢出；详情提供精确消息/快照 |
| B2-18 迁移/存储 | 空库v2；合成v1带B1历史/节点/WAL；一致备份→事务升级；已v2重复；未知/坏schema/未标非空库；两不同turn都selected_index=0、同turn两节点同index | B1 IDs/快照/计数逐字一致，新约束/索引/外键有效；UNIQUE(turn_id,selected_index)允许跨轮0、拒绝轮内重复，不做全表selected_index唯一；备份含WAL已提交值、可用旧应用读取；非法库拒绝且源资产不变、不覆写备份 |
| B2-19 迁移/故障 | 备份失败、每步DDL/约束/最终version提交注错；从受控一致备份恢复到新路径/旧应用 | 备份失败零DDL；中途失败仍v1无半表，备份保留；恢复不混旧sidecar，旧API可读B1；明确回滚损失B2新增数据，不操作个人DB/自动逆迁移 |
| B2-20 安全/隔离 | Host/Origin/null/chunk/JSON/strict输入/B2脱敏；dotenv打开哨兵+污染server/model环境、临时DB/Provider断言 | 复用B1安全强度、无密钥/原输入/模型异常泄漏；沿用严审环境隔离成果，B2 API/Web子进程不读个人dotenv/环境配置、不联网/触及个人库 |
| B2-21 Web/回归 | 工作台明确选区、会话继续、等待冲突、失败/效果独立显示、图刷新409、历史展开、刷新/重启；CLI/reset/B1全回归 | Web Mock及实际FastAPI/临时SQLite流程均通过；无SSE/队列/隐藏重放；CLI/reset不清学习DB；根默认CI包含全部门禁且B1不回退 |
| B2-22 效果/文档 | 扩展既有smoke --stage b2，缺授权默认；可选获准合成教学调用 | 默认SKIPPED非零/不读配置/不联网；opt-in才记录模型ID/UTC/安全结果；离线桩与真实效果分开。同期更新契约/OpenAPI/README/架构/安全/CI/history，未经效果检查不标真实通过 |

合同复核项（属于技术方案，不替用户新增产品目标）：最多5个非root与主节点顺序、同键只查不重执行、修订后显式新图续接、两项只读生产工具、SQLite离线升级回滚。没有需用户补选的产品问题；需周经理/严审合同门禁及后续真实库迁移/真实模型调用授权。B2验收不以等待这些授权为由空等或扩大到B3。已尝试向阿岚直接同步契约，仅请求只读收悉而非提前实施；delegate权限拒绝 `Your delegation permissions do not allow this target`，请周经理转发本契约及B2错误枚举/同键失败200语义，不绕过成员权限。

#### B2 设计复核 R1–R4 修订（#5，待针对复核）

2026-10-09，严审初审 `dbef8234` 对合同SHA256 `97470c6ee159e4b9f46d4569f4670af469b318a71bd93289a44af90f943df649` 暂不冻结；周经理以delegation `19c0b486-2e09-42f0-8918-dea81166311e` 派仅文档修订。原设计文档检查绿灯不等于设计正确；下列是本轮修正及未来验收要求，不是B2业务通过：

| 复核项 | 原缺口 → 修订落点/理由 | 对应矩阵 |
| --- | --- | --- |
| R1 | 契约原213–221要求全历史原始call ID唯一，与Runner历史used_ids冲突；现6.1.1由B2 Provider边界固定turn命名空间/整执行raw映射，输入历史保留服务端配对ID，输出整批检重后映射，Runner守卫不改。两个独立轮call_1可行，同执行/批重复仍拒绝；该ID不作领域operation key | B2-08/12捕获实际Provider输入和assistant/tool同映射；合法跨轮与非法同执行计数分开 |
| R2 | 原先取历史再保存输入不能承诺500有新failed；现3、4.1/4.2、5.2先短事务保存合法请求/精确快照/预装配user，提交后才验历史，再加载配置/执行。坏历史可定位新failed，预装配不等于已发送 | B2-09/10查GET turn/submission及同键200原failed；坏JSON/配对时Provider/工具/配置读取0 |
| R3 | 原completed且eligible预筛会跳坏成功；现6.1读取全部completed，先逐一验状态/eligible/快照/消息再装配；DB CHECK与读取守卫并存，合法failed/interrupted全轮排除 | B2-10伪造completed/eligible=false拒绝且三类调用0 |
| R4 | 原409合并行错误要求invalid_state有revision；现3、5.3分开invalid_state的实际goal/graph与空revision，revision_conflict填真实图版本；明确冲突先于状态、两状态坏先goal，B1路由不改 | B2-01完整六键details与retryable精确断言，不只查code |
| 附建议 | 6.1.2完整ModelResponse含usage/arguments、确定JSON/UTF-8与根容器深度口径，原始/转换后均限额；7表格明确UNIQUE(turn_id,selected_index)，避免误作全表唯一 | B2-12等值/超1边界，B2-18轮内冲突/跨轮同index合法 |

本轮改动只限B2合同、本唯一计划、设计索引和既有history；保护B1实现及严审测试隔离成果，不改内核/接口实现。方案尚未设计验收，不stage/commit；周经理收到本轮证据后派针对复核，确认通过再授权清晰差异提交（不git add .，不夹带用户内容）。#8/#9仍未获实施派单；无个人DB迁移、dotenv读取、联网或部署。请周经理将6.1.1服务端消息ID、4.1预装配非送达与5.3/B2-01精确错误details转发阿岚收悉，不自行越过委派权限。

本轮设计检查（退出0；无B2 pytest/Web/类型检查/默认全量CI，因为尚无B2实现）：

| 实际检查 | 输出/边界 |
| --- | --- |
| `npm.cmd run check:docs` / 既有checkMarkdownLinks经Node stdin | `文档骨架检查通过` / `Markdown local links check passed` |
| `npx.cmd --offline --loglevel=error markdownlint-cli2@0.22.0 "**/*.md"` | 68 files /0 errors；固定缓存版本，未联网 |
| 只读Python stdin文档/差异检查 | `B2 DOCUMENT DIFF CHECK: 8 unique routes; 22 unique matrix rows; changed rows=01/08/09/10/12/18; B1/B3/B4 evidence byte-identical; implementation pending (NOT API/business tests)`；四文档全文空白/冲突标记检查，覆盖untracked而非只git diff |
| 接手时145个相关文件逐字节SHA256对比 | `BASELINE PROTECTION: 4 authorized documents changed; 141 other baseline files byte-identical`；B1契约保持`1923c1ac95e9e4ee177bdb36bdaae7671825f7a66add9d4af812f663047baac0`，Runner及测试配置隔离均未改 |
| 无模型只读ID/预算/约束设计演算，`.venv\Scripts\python.exe -B -` | `B2 READ-ONLY DESIGN PROBE: 30 assertions passed (NOT B2 API/business implementation tests; no dotenv/network/DB files)`；映射只在stdin夹具存在，不写入业务/测试文件；约束仅`:memory:`合成表 |
| `git diff --check` / `git diff --cached --stat` | 退出0/空；未stage/commit，不把自动checkpoint当业务提交 |

演算原Runner复现为turn1=completed、turn2=invalid_response、Provider3/工具1；拟议固定turn命名空间后两个独立call_1轮均completed、Provider4/工具2，捕获实际_message_payload中的assistant/tool服务端ID相等且稳定。同批重复invalid_response/Provider1/工具0，同执行后续重复invalid_response/Provider2/工具1。完整JSON的ASCII/中文样本各恰262144及262145 UTF-8字节；usage/arguments计入，容器深度32/33与16/17调用计数口径可复算；合成约束允许跨轮index=0、拒绝轮内重复及completed/eligible=false。**这些只证明设计可演算，不证明B2 API、历史失败落库/查询、真实Provider服务或教学效果通过**；上述R2/R3/R4必须在#8/#10转为业务/API断言。

检查工具初次PowerShell内联引号失败未执行门禁，改stdin后通过；演算最初网络哨兵阻断Windows asyncio自管道socketpair，尚未执行模型/工具，用不需要事件循环的立即返回协程演算重跑通过，保留dotenv/socket.connect禁止哨兵。没有放行外部连接，也没有将失败尝试计为通过。

可复查旧版来自自动checkpoint `8119207471edb02f379d9e5445f926cbb9e47913`：已核对四文档旧字节与接手时快照相等，合同旧SHA为本节首列`97470c6ee159...`，修订后合同SHA256为 **`85f763751ff54c2aef70bfbf57d374887dafd0e0a9f307d314a435f8f9063770`**。合同差异+48/-21行，索引+1/-1、history+1/-0；矩阵只变01/08/09/10/12/18，其余16行、8路由、B1/B3/B4历史内容未改。因四文档有untracked，普通git diff不是本轮完整差异；可用以下只读命令逐文件复算（不创建文件、不stage）：

```powershell
@'
from pathlib import Path
import difflib, subprocess
base = '8119207471edb02f379d9e5445f926cbb9e47913'
paths = ['docs/design-docs/learning-b2-api-contract.md',
         'docs/exec-plans/active/learning-loop-web.md',
         'docs/design-docs/index.md',
         'docs/histories/2026-10/20261009-1146-learning-loop-web-plan.md']
for path in paths:
    old = subprocess.check_output(['git', 'show', base + ':' + path]).decode('utf-8')
    new = Path(path).read_text(encoding='utf-8')
    diff = difflib.unified_diff(old.splitlines(), new.splitlines(),
                                fromfile=base + ':' + path, tofile=path, lineterm='')
    print('\n'.join(diff))
'@ | .venv\Scripts\python.exe -B -X utf8 -
```

### B3 固定评估：mini-assessment-v1

此规则选用交接第 5.6 节建议，不复制原项目星级。只选服务端 `local-user`、当前 node_version、有效已评价 Evidence。作答顺序与评价版本必须分开：

- 同题作答：服务端在保存新 Attempt 的事务内分配递增且唯一的 `attempt_index`（作用域 learner_id/exercise_id），重发同一submission_id不增加序号；submitted_at在首次保存时由UTC时钟生成且不可变。每题仅取有有效评价的Attempt中attempt_index最大的一个；不得按evaluated_at、重评完成时刻或客户端时间选择。唯一约束排除同序号，查询可用submitted_at/ID做防御性稳定排序但不能覆盖序号优先级。
- 同一Attempt评价：`evaluation_version`为该Attempt内服务端递增版本，成功重评只替代该Attempt当前有效评价/Evidence，旧版本保留。有效指针通过条件更新指向最新成功版本，迟到的旧评价版本不能覆盖新版本。重评不改变attempt_index/submitted_at，不把旧作答变成新作答，也不增加有效题数。
- 评价失败不产生新能力证据；如果该Attempt已有成功评价，失败重评保留之前有效版本并记录失败，不将历史成功伪装成重评成功。若较新的Attempt尚未评价成功，暂用较旧的有效作答并明确较新答案待评/失败，成功后才按作答序号替换。错误/部分正确同样参与。
- 复习时钟采用被选中作答的不可变submitted_at，`last_evidence_at=max(选中Attempt.submitted_at)`；评价/重评只是处理记录，其evaluated_at不刷新学习证据年龄。所有时间判定用同一个注入UTC as_of，避免延迟评价制造“刚学习过”的假象。

- difficulty：easy=0.3、medium=0.5、hard=0.7；reliability：规则=1、有效模型=0.8；模型不可传入可靠性。
- assistance：提供提示 `min(0.9, 0.4 + 0.2 × (hint_count - 1))`；无提示但重试=0.25；首次无提示=0。查看答案取0.9；与提示/重试取最大值。由服务端操作计数，不信任客户端自报。
- `w = reliability × (1 + difficulty) × (1 - assistance)`；内部 score 为有效证据 score 的加权均值；充分度 `min(1, sum(w)/5)`。
- 顺序：无证据 unassessed（内部 score=null）；score<0.5 weak；score≥0.85 且充分度≥0.7 且不同题≥3 且首次无提示全对≥2 mastered；其余 score≥0.65 familiar；其余 learning。
- familiar/mastered 距last_evidence_at **≥14天** 转needs_review，保留基础状态/分/依据；读取时用注入UTC时钟，无计划任务。推荐到期与状态过期是两个不同条件：基础状态mastered的review_due_at=last_evidence_at+14天，familiar/learning为+3天；weak立即补学（不被review覆盖），unassessed无review_due_at。needs_review沿用基础状态的review_due_at。到期条件as_of≥review_due_at，不到14天也可推荐review，但不提前把familiar改成needs_review或阻塞其后续节点。
- 仅参与不算证据。API 对 Web 隐藏内部 mastery_score/充分度数字，返回状态、证据引用、题数、辅助说明、评价来源/规则版本/时间；反馈可展示评分点覆盖，不把数值掌握分当能力概率。

固定测试：一题首次无提示medium规则全对w=1.5、充分度0.3→familiar；三不同题w合计4.5→mastered；再刷同题不得增加题数；第一题0分→weak；三点覆盖二点→partial/2/3；节点新版本→unassessed、旧证据仍可读。补充可复查的顺序/时钟案例（将来B3/B4测试必须覆盖，本轮仅规则演算）：

| 场景 | 固定操作/边界 | 预期 |
| --- | --- | --- |
| 旧作答重评 | 同题A(index=1)全对，B(index=2)错答已有效；之后成功重评A | 同题仍选B，状态weak；仅A评价版本替代，不掩盖B错误 |
| 旧作答延迟评价 | A先提交但延迟，B后提交且错答评价先完成，最后A评价全对完成 | 仍选B；按作答序号而非评价到达顺序选择 |
| 新作答待评/失败 | A有有效评价，B已保存但评价失败 | 暂选A并展示B未完成；B后来成功才替换；不新增失败Evidence |
| 重评时钟 | 在A提交后第13天重评A，其他选中作答时间均不更晚 | last_evidence_at仍是原submitted_at；第14天不因重评延后复习 |
| familiar三天边界 | 无新增作答，as_of为last_evidence_at+3天-1秒 / 恰3天 / 第4天 | 状态均familiar；建议依次learn / review / review，3天到期不阻塞下游 |
| learning三天边界 | concept为learning，时刻为3天-1秒 / 恰3天 | 建议learn / review；状态仍learning |
| mastered十四天边界 | 时刻为last_evidence_at+14天-1秒 / 恰14天 | mastered且未到期 / needs_review且推荐review，保留原分和依据 |
| familiar十四天边界 | 时刻为14天-1秒 / 恰14天 | familiar且已推荐review / needs_review且推荐review；仅后者阻塞下游前置 |
| weak优先补学 | weak在第4天或第14天 | concept推荐learn，不用review掩盖补学需求 |

### B4 固定推荐：mini-actions-v1

同一 published graph revision/状态快照/UTC as_of：根不推荐；prerequisite 的源节点须 familiar/mastered 且非 needs_review，否则返回 blocked_by。可执行前置优先，被阻塞建议仍可见，用户可自主访问，不硬禁学习。

类型按固定优先级：weak→concept的learn / practice类型的practice / assessment类型的assessment；否则needs_review或已到review_due_at→review（含familiar/learning第3天、mastered第14天）；否则practice/assessment按节点类型、concept→learn。unassessed不生成复习到期。返回review_due_at/last_evidence_at及到期理由，与B3使用同一个as_of/证据快照。仅3天推荐到期不等于needs_review，前置检查仍按状态执行。不会因“行动完成”改变掌握。

排序内部 priority 采用 `round(100 × (0.30×importance + 0.24×mastery_gap + 0.18×urgency + 0.14×evidence_gap + 0.10×deadline_urgency + 0.04×preference_match))`，夹在0..100；round 用十进制 half-up，避免语言差异：

- importance=`goal_weight/100 × node_weight/100`；mastery_gap=`1-score`（无证据1）；evidence_gap=`1-充分度`。
- urgency按顺序：weak=1、needs_review或已到review_due_at=0.9、unassessed=0.5、其余0.1。
- deadline：无0、已过期1、剩余≤1/7/14/30天为0.95/0.75/0.55/0.35、更远0.15；均按 UTC 秒数边界，不猜 time_limit_text。
- preference_match：与目标已声明的 preferred action types 匹配为1，否则0；同分按 node_weight降序、节点创建时间升序、node ID字典升序。先可执行、后阻塞。

返回 action type、节点/内容版本、reason、blocked_by、证据引用、rule_version/as_of/graph_revision；前端不展示内部掌握数字。输入快照在领域服务结果中保留供测试/解释，无完整排期、无虚构时间承诺。规则解释模板即可，非必要不额外调用模型。

### 真实模型验证入口与证据纪律

B1 已提供 `uv run --locked python scripts/verify_learning_model.py --stage b1`；B2/B3/B4 后续分别扩展 `--stage b2|b3|b4|all`，尚未实现。入口在历史设计阶段尚不存在；当前默认运行 SKIPPED/退出2，不读取配置、不联网；只有获准才加 `--allow-configured-model`，不得将入口存在或离线桩测写成真实模型通过。

入口使用现有配置名/Provider、一次性临时 SQLite、合成 CSV 目标（无个人资料），分别验证澄清 JSON/候选图谱 JSON/教学 Runner/固定 rubric 简答评价；不自动 publish 正式图、不部署。记录 UTC 日期、模型 ID、阶段、成功/失败类别和校验结果，不记录密钥、完整请求/答案/原始响应。先缺配置检查：输出 `SKIPPED: model configuration unavailable` 且非零退出，计划标注未验证；网络/权限/预算问题同样明确报告，不自动更换供应商。已有获准配置/网络调用范围之外先请派单人确认。

真实样例至少验证动态 questions/skip、CSV 合法候选、切换节点教学、三点评价（含 partial）、非法结构失败路径；桩/HTTP 模拟只证明软件契约，不证明真实模型效果。真实结果写在本计划，必要时链接较长证据，不存敏感原始日志。

### 文档更新职责

| 时点 | 责任人及文档 |
| --- | --- |
| 本轮设计 | 老秦：本计划、B1契约、设计索引、history；现有 handoff/阶段A状态保留历史事实 |
| B1 落地 | 老秦：ARCHITECTURE（实际领域/API/持久化目录）、SECURITY（回环/Origin/输入/脱敏）、README/.env.example（DB/API配置）；阿岚：Web 安装/启动/页面/错误约定；共同：CICD/WINDOWS（检查入口）、契约/OpenAPI一致性 |
| B2/B3/B4 | 老秦更新会话/证据/规则/真实检查和契约；阿岚更新交互/运行；严审更新 QUALITY_SCORE 的实际证据及未验证项；周经理检查 PRODUCT_SENSE 范围和 release notes（未发布不能写发布） |
| 阶段交付 | 在本计划即时登记结果；完成 B4 后归档 completed 并留 history 索引；暂缓风险进 tech-debt-tracker；代码涉及≥2项学习触发时按 learnings 指南写记录 |

## 验收与交接

### B1 后端实施检查点

2026-10-09 老秦接单后核对现有差异；冻结契约不变。实现分为 strict Schema/模型 adapter、SQLite/CAS 领域用例、FastAPI 安全边界三块，前端 `web/**` 不在后端编辑范围。持久化采用 SQLite 外键表与 JSON 完整快照：ID/归属/revision/节点历史由关系约束保护，小图无需 ORM。启动只初始化新库或读取 schema_version=1，不升级已有未知版本数据库；无真实资产删改。模型配置仅在生成入口加载，离线启动/查询不读取模型设置。下一检查点为领域、持久化与安全/API测试；未进行真实模型调用。

#### B1 历史续接核查：编辑锁阻断，尚未交付

2026-10-09 delegation `9791ce08-0cde-4f09-8222-ca05f08e3282` 续接上游通道失败的 `10f0f66e`；没有重建、安装、reset/stash/stage/commit 或修改真实 DB。核查发现 `mini_learngraph/api/`、`learning/`、4组后端测试、模型 smoke 入口和根 CI/Web 接入已落盘，12路由齐备，但实现不等于通过验收。冻结契约未改。

- 首跑 `uv run --locked pytest -q`：434 passed、4 failed、4 errors。failed来自 Origin=null 的脱敏断言错误（把契约要求的 JSON null 误认为泄漏）；errors来自两个巨大 param ID 在 Windows 超过环境变量32767字符限制。需保留检查强度，修正断言目标与显式短测试 ID。
- `uv run --locked ruff check mini_learngraph`：10条诊断，未通过；Pyright为0 errors /0 warnings /0 informations。
- 新增 `tests/test_learning_contract.py`：直接从冻结文档核对真实 OpenAPI 的12组方法/路径，strict额外字段禁用与所有可空字段必需；复现HTTP确认错误码缺陷。6项中4 passed、2 failed：Pydantic的 `duplicate_question` / `invalid_answer` 被HTTP层错误映射成 `constraint`，需修复，不能修改冻结约定绕过。
- `uv run --locked python scripts/verify_learning_model.py --stage b1`：输出 `SKIPPED: model configuration unavailable or not authorized (no configuration read, no network)`；PowerShell `$LASTEXITCODE=2`。未读模型配置、未调用真实模型，效果未验证。
- `npm.cmd run ci`：文档/仓库/Action及Node语法检查已走过，Node回归21 passed /1 failed；源码复制读到正在由并行Web流程写删的 `web/test-results/.playwright-artifacts-0/` 后ENOENT。根分发排除规则尚未排除此类生成物，需要精确排除并补工具回归，不能关闭门禁。Python/Web门禁未在这次CI中执行，整体未通过。
- 续接中已修 `scripts/lib/common.cjs`、`.gitignore`、`docs/CICD.md`：精确排除上述浏览器生成目录、保留源码测试/lock/配置；`tests/tooling.test.cjs`新增排除规则回归。新测试先RED（test-results未排除），修复后通过。Node全回归复跑22 passed /1 failed，剩余失败是初始化模板中的 `web/README.md:6` 链接到已被正常裁剪的具体计划文档；应由阿岚将链接改为计划目录（契约已用此方式），不更改裁剪/检查。对阿岚直接委派受权限拒绝，请周经理转发。根CI仍未通过，后端修复后需再次全跑。
- `git diff --check`退出0。

修复尝试被工具层锁阻止：`mini_learngraph/api/app.py` 与 `tests/test_learning_validation.py` 均报 `Workspace busy ... is being edited by 老秦 (released when their turn ends)`，120秒等待仍失败。未绕过锁或覆盖文件；修复patch没有写入。已请严审只读复核并转告周经理释放前次会话/Run的锁。必须解锁后补齐修复、Python全回归/Ruff、根CI和文档证据；当前不能认定B1完成或验收通过。

补充文档骨架与本地Markdown链接检查均退出0；缓存离线Markdownlint 0.22.0检查65个文件、0错误；最终git diff --check退出0，cached diff为空。本轮自测失败/阻断证据与上次设计阶段的全绿文档证据分开，未自证B1完成。接续待办：解锁→修HTTP固定issue映射/Windows测试参数及Ruff→阿岚修Web初始化文档链接→全部离线门禁→严审独立复验。真实模型仍SKIPPED；B2–B4未开始。

#### B1 重启恢复检查点：锁已释放，修复已落盘

2026-10-09 delegation `50287dd8-3ab4-489f-906b-3090fce04d0d`，用户重启后授权继续。先核对 `git status --short; git diff --stat`：24个tracked修改及已落盘API/learning/Python测试/web等团队成果均保留，没有重建。对 `mini_learngraph/api/app.py` 正常受保护 apply_patch 成功，确认前次编辑锁已释放；未绕过锁，无stage/commit/reset/stash或真实DB操作。

- HTTP校验显式白名单映射 `duplicate_question` / `invalid_answer`，使用固定安全摘要；不透传Pydantic input/ctx。冻结契约文件不改。
- 安全测试脱敏递归检查解码后所有JSON键与文本，合法JSON null不再误报Origin泄漏；新增回归确保真正的字符串null/私有值回显仍失败。
- 超大模型输出两个param采用显式短ID，保持ASCII/UTF-8字节限制样本及断言，不降低输入大小、不跳过Windows测试。
- Ruff10项修复：import/endswith/IGNORECASE/UTC/条件合并、错误类型与对应捕获；HTTP/Provider安全边界仅沿用仓库逐行BLE001说明，取消/退出仍传播，无全局忽略。
- 根CI加入顺序 `test:flow` → `test:api-flow`，严格typecheck/lint/test/build仍保留；新增执行顺序回归。已有Playwright生成物排除及源码保留回归不削弱。
- 定向 `uv run --locked pytest -q tests/test_learning_contract.py tests/test_learning_validation.py tests/test_learning_security.py`：192 passed、1个Starlette TestClient弃用warning；`uv run --locked ruff check mini_learngraph`：All checks passed；`node --test tests/tooling.test.cjs`：24 passed/0 failed/0 skipped。Windows大param及Origin=null既有复现均关闭，冻结OpenAPI/HTTP确认6项通过。
- 周经理提供的当前Web独立验收（严审#3）：typecheck/lint/build通过，unit14/14、Mock16/16、真实FastAPI/CORS/临时SQLite3/3，README悬空链接已由阿岚修复；Provider为固定桩，不是真实模型。后端没有编辑web/**。随后本轮完整根CI再次全部通过，详见下一节；待周经理派严审#4整体独立复验，B1未验收、B2–B4未开始。

#### B1 完整工程自测证据与交接

2026-10-09 Windows / Python3.11.11 / Node22.17.0，本轮实际执行结果如下。先前空日志的后台工具返回没有完整测试输出，不采信为验证证据；改用前台完整 `npm.cmd run ci`，保留原始临时日志供派单人/严审复核。无部署、提交、真实模型或真实库修改。

| 命令/默认CI子步骤 | 本轮实际输出与结论 |
| --- | --- |
| `npm.cmd run ci` | 退出0，97.2秒；末行 `基础 CI 检查通过` / `CI_EXIT=0` |
| CI文档/仓库/Action及全部Node语法 | 均通过；没有跳过/降级已有检查 |
| `node --test tests/tooling.test.cjs` | tests24 /pass24 /fail0 /skipped0，含DB/浏览器生成物排除与完整源包/模板回归及新增Web流程顺序回归 |
| `uv run --locked ruff check mini_learngraph` | `All checks passed!` |
| `uv run --locked pyright mini_learngraph` | `0 errors, 0 warnings, 0 informations` |
| `uv run --locked pytest` | collected460；`460 passed, 1 warning in 14.22s`，无failed/errors/skipped |
| 五组B1矩阵 `uv run --locked pytest -q tests/test_learning_contract.py tests/test_learning_api.py tests/test_learning_security.py tests/test_learning_storage.py tests/test_learning_validation.py` | `228 passed, 1 warning in 11.90s`；contract6/API23/security102/storage13/validation84 |
| Web锁定安装/typecheck/lint | `npm ci`成功；`tsc --noEmit` / `eslint . --max-warnings 0`退出0 |
| Web单元/构建 | Vitest5 files /14 passed；Vite33 modules /built582ms，退出0 |
| Web `test:flow` | `16 passed (13.6s)`；HTTP Mock，不是真实后端/模型 |
| Web `test:api-flow` | `3 passed (8.1s)`；实际FastAPI/CORS、临时SQLite、并发409/联合环422、进程重启/失败恢复；模型固定Provider桩 |
| `uv run --locked python scripts/verify_learning_model.py --stage b1` | `SKIPPED: model configuration unavailable or not authorized (no configuration read, no network)`，退出2；明确未验证真实效果 |

补齐矩阵：动态非固定3题choice/custom/skip与全部三种假设来源完整保存、重启GET一致；禁用custom/skip的目录守卫；Goal/Graph空输出/截断JSON/非法Schema或refs/联合环/超时/transport/缺配置失败、GET可恢复并显式重试；两类资产最后提交busy保留可查询generating而非假成功；编辑/发布/正式修订CAS同值恰一成功一409；位置/重要性/关系修改不升级node_version，内容改动仅升级对应节点；删除保留历史且不可复用ID；未知库/版本不改资产。当前HTTP固定issue/OpenAPI12路由、strict必需null字段、Host/Origin/体积/chunk/非法JSON/资源输入/脱敏均通过。

本轮未编辑 `docs/design-docs/learning-b1-api-contract.md` 或web源码。当前契约文件SHA256为 `1923c1ac95e9e4ee177bdb36bdaae7671825f7a66add9d4af812f663047baac0`，与上方历史设计复核摘要不同；真实OpenAPI与当前文档12组方法/路径一致。不能把旧摘要写成当前文件校验值；严审#4需核对当前契约内容及复核版本来源，不自行覆盖已落盘契约。

本轮修复/补验文件：`mini_learngraph/api/{app,security,settings}.py`、`mini_learngraph/learning/{generation,schemas}.py`、`tests/test_learning_{api,security,storage,validation}.py`、`tests/tooling.test.cjs`、`scripts/ci.cjs`；保留已落盘的 `tests/test_learning_contract.py` 和其余B1领域/持久化实现。前次生成物排除修复在 `scripts/lib/common.cjs` / `.gitignore`，本轮回归仍通过。根依赖/lock已有团队成果保留，本轮没有额外升级；修改共享使用/CI/质量文档、此唯一计划及同一history，并新增[安全校验速记](../../learnings/2026-10/20261009-safe-validation-contract.md)。文档最终检查另见末尾收口记录。

启动：`uv sync --locked` 后 `uv run --locked python -m mini_learngraph.api`（默认127.0.0.1:8000，OpenAPI `/openapi.json`）；Web按 `web/README.md` 安装启动在127.0.0.1:5173。安全/失败回归不要求模型配置；正式生成只有显式操作才创建模型Settings并联网。迁移仍只有新库schema1初始化，未知/真实旧库需备份与明确迁移授权，回滚为旧应用+一致备份恢复。

遗留与验收状态：Starlette TestClient提示未来httpx2替换的一个弃用warning，当前兼容栈锁定测试通过，不临时升级依赖或关闭warning；npm安装镜像audit请求404、上游依赖弃用提示，不能当作漏洞审计通过。远端Windows/Ubuntu/macOS矩阵未执行，LAN/公网/多人未支持，真实B1模型未验证。工程自测通过不等于严审#4或周经理已验收；B1勾选保持未完成，B2–B4不提前。

文档收口中，本地骨架/链接/Markdown66文件0错误通过；再次Node源码包/初始化回归发现新增QUALITY_SCORE链接指向会被初始化裁剪的具体计划文件（23 passed/1 failed）。已按同一规则改为计划目录链接+正文路径，不削弱链接门禁或恢复历史任务分发。修复后最终完整 `npm.cmd run ci` 再跑退出0/94.0秒，Node24 passed、Ruff All checks passed、Pyright0errors、Python `460 passed, 1 warning in 13.87s`、Web14 passed/构建571ms/Mock16 passed13.0s/API3 passed8.1s，末行 `基础 CI 检查通过` / `CI_EXIT=0`。这是新文档后的最终结果；上述97.2秒表格为前一次完整工程自测，计数一致。

最终文档与差异收口：`npm.cmd run check:docs`输出 `文档骨架检查通过`；仓库本地链接检查输出 `Markdown local links check passed`；缓存离线固定版本 `npx.cmd --offline --loglevel=error markdownlint-cli2@0.22.0 "**/*.md"` 为66文件/0错误；`git diff --check`退出0、cached diff仍为空。历史设计阶段的“没有业务实现”仅保留在历史章节，不再作为本轮结论。交付仅表示老秦工程自测完成，严审#4/周经理验收仍待派单人安排。

### 历史设计阶段文件

- `docs/exec-plans/active/learning-loop-web.md`：唯一实施计划/证据事实源。
- `docs/design-docs/learning-b1-api-contract.md`：B1可复查路由、Schema、状态、错误及模型协议。
- `docs/design-docs/index.md`：追加契约入口，不覆盖接手前内容。
- `docs/histories/2026-10/20261009-1146-learning-loop-web-plan.md`：本轮完成记录索引。

### B1 严审#4整体独立复验

2026-10-09，delegation `7cd2af29-1afc-43a2-bf44-52fc8ecf0812`。结论：**B1本机、固定Provider、离线软件契约范围可以交付；八项矩阵通过，无剩余必须修复项。最终接受由周经理执行，本记录不勾选B1完成、不提前B2。** 不以老秦自测或#3Web结论替代本次实际执行。正确性、安全输入/归属/脱敏、模块依赖方向及仓库风格已独立审查；领域不依赖HTTP，Runner未承担持久化职责，无模型发布权限。

#### 版本和合同SHA追溯

工作区仍基于HEAD `dadf3a9b881e93b967a5a4b4669910210d51f134`，团队业务实现未提交，cached diff为空；不能把HEAD单独当作B1源码版本。现合同全文已按第1–8节对照Schema、状态机、用例、HTTP、前端类型与实际测试复核，不仅比较路由：strict/显式null/长度与数量、动态目录、假设来源、用户确认、Graph联合DAG、版本/历史、错误定位、JSON协议及非目标均与已确认边界一致。

- 只读`git log --all -- docs/design-docs/learning-b1-api-contract.md`与`git show <checkpoint>:<path>`恢复了设计冻结原始字节：checkpoint `652a1e011fa5631cb3b83ca24ab5acda88b4ca11`，SHA256 **`c9a2d8720c739f801f74b1ee7fb07c0fd7a9dd30bca7915d9c89cc5f1be36a09`**，27516字节。
- 当前合同SHA256 **`1923c1ac95e9e4ee177bdb36bdaae7671825f7a66add9d4af812f663047baac0`**，27623字节。两版365行、CRLF计数均0、LF均365；`changed_lines=[3]`，移除第3行后的全部原始字节完全相等，不是换行规范化造成摘要变化。
- 第3行状态由“待周经理/严审复核的实施契约，尚无业务实现”改为“已获周经理/严审复核，B1后端实施中，尚未验收”；具体计划文件链接改为保留具体路径文字、链接计划目录，并说明初始化裁剪原因。**首段进度/链接有变，正文Schema/路由/错误/事务/语义条款无漂移**；不能表述为“文件没变”。
- 可用checkpoint中最早出现当前SHA的是`4520b4fafca70861880025a4713dea5e94bce2df`（2026-10-09T04:20:27Z）。这些是Enso自动checkpoint、不是业务提交；它们证明字节版本与出现时间，不足以单独归因编辑者或证明审批。审批依据仍为本计划历史复核及派单记录。此次未修改合同。

复验源码SHA256前12（可用`Get-FileHash <path> -Algorithm SHA256`重新定位）：

| 文件 | 摘要前12 |
| --- | --- |
| `mini_learngraph/api/app.py` / `security.py` / `settings.py` | `bf390bea9ca0` / `4c740de4dfeb` / `794b52741266` |
| `mini_learngraph/learning/schemas.py` / `generation.py` | `5f365c3a20a3` / `cbce236a5617` |
| `mini_learngraph/learning/service.py` / `storage.py` / `validation.py` | `02394eae3556` / `ac944a71cc62` / `8e08d30938af` |
| `scripts/ci.cjs` / `scripts/lib/common.cjs` | `c14392fbbed7` / `c837bdb80d09` |
| `tests/test_learning_acceptance.py` / `tests/conftest.py` / `web/tests/api_fixture.py` | `29dcbeef2124` / `1198e88820f3` / `ec09017d061b` |

#### 验收环境隔离缺陷与本次测试侧收尾

发现并关闭一项**阻断验收环境、非业务逻辑缺陷**：`tests/test_learning_api.py:25`的create_app及原`web/tests/api_fixture.py`主入口未禁用`ServerSettings`默认dotenv源（`mini_learngraph/api/settings.py:30`）；security/contract模块自己的fixture不覆盖其他模块。复现：安装阻止仓库`.env`打开的哨兵后，将ServerSettings.env_file恢复默认并实例化，会命中“Repository dotenv must not be read”；哨兵在真实读取前阻断，没有读取个人配置。期望固定Provider测试不读取个人dotenv/不继承server设置，原行为却会尝试读取并可能被非本机Host等环境值污染，不能据此宣称验证资源完全隔离。

仅修改测试侧：新增`tests/conftest.py:8`对所有`test_learning_*`模块禁dotenv、清除四项server环境值；`web/tests/api_fixture.py:70–75`同样隔离浏览器测试server。新增`tests/test_learning_acceptance.py:202`同时验证默认源负对照、哨兵保护下API启动/查询和浏览器入口在合成host污染下仍使用临时DB/固定Provider。已有配置模块的临时dotenv测试及生产配置行为未改变。其余新增风险测试共14例；不改业务代码、断言不放宽、无stage/commit/reset/stash，无真实DB操作。

#### 八项矩阵逐项证据

表内位置均指本次工作区版本；复现入口为六组B1 pytest及Web两个流程。预期和实际一致，均**通过**：

| 项 | 实现位置、复现/断言与结果 |
| --- | --- |
| 1 动态问题与透明假设 | `schemas.py:145–235`、`service.py:140–191`；`tests/test_learning_api.py:141`三种非固定key分别choice/custom/skip，确认后questions/answers及suggested/skip/user假设完整且重启GET一致；`:171/:215`目录能力/未知选项守卫422且Goal不变。确认Goal仍graph_id=null，Graph生成后仅candidate；Web `api-flow.spec.ts:67`实际向导/确认/候选/发布独立动作。 |
| 2 严格模型失败与资产重试 | `generation.py:56–179`、`service.py:84–138`；`test_learning_validation.py:348–449`全文JSON/重复键/围栏/非法数字/256KiB与32层/工具调用/finish/取消/超时/refs守卫；`test_learning_api.py:92/:113/:186`Goal/Graph失败HTTP502/504/503→GET完整失败资产→显式重试，同ID且无半图/自动成功；`test_learning_storage.py:221`两类最终提交busy保持可查询generating。 |
| 3 联合DAG与定位 | `validation.py:27–156`、`service.py:194–216/:257–271`；`test_learning_validation.py:235–285`唯一root/最少节点/ID边重复/端点/contains父与可达/全部可确定issues；`test_learning_storage.py:90`联合环422中refs及edge_indexes准确、Graph及下一revision不写；Web `api-flow.spec.ts:98`实际422节点/边高亮且DB revision未动。 |
| 4 CAS竞争与无半写 | `storage.py:61–80/:165–220`；`test_learning_storage.py:70`三种真实工作线程竞争；新增`test_learning_acceptance.py:42`三种HTTP双线程同revision同步发起，恰一200一409/current_revision+1，恰一历史快照/无额外NodeVersion；`:75`注入历史保存失败覆盖create/edit/publish/revise，500且Graph、Goal绑定、历史、NodeVersion全部回滚。 |
| 5 候选/正式路径与历史 | `service.py:194–271`、`schemas.py:254–280`；`test_learning_api.py:61`覆盖读/候选编辑/发布/正式修订/历史，published PUT及重生成409；`test_learning_storage.py:108`删除完整处理边，历史保留/不能复用ID；`test_learning_validation.py:122`explicit true拒绝false/缺失/数字；Web `api-flow.spec.ts:67`正式reason/确认及历史只读、刷新继续。 |
| 6 精确内容版本 | `service.py:218–235`、`storage.py:179–190`；`test_learning_storage.py:31/:108`position/target_weight/关系不升级，删除旧来源保留，新ID由服务端分配；新增`test_learning_acceptance.py:131`逐一修改label/node_type/description/teaching_strategy只升对应节点、NodeVersion恰增1，trim等价不升级，旧GraphRevision完整不变。 |
| 7 安全边界与错误 | `api/security.py:106–237`、`api/app.py:78–167`、`storage.py:103–142`；security102例覆盖Host/Origin/null/重复头/预检/512KiB每chunk/JSON/strict/未知字段与查询/错误脱敏；新增`test_learning_acceptance.py:109`跨图真实已有Node ID为422 foreign_node定位，双方快照/历史不变。`test_learning_contract.py:48`duplicate_question/invalid_answer固定HTTP映射通过；`test_learning_security.py:67`JSON null允许但实际字符串null/私有值泄漏仍断言失败。 |
| 8 刷新重启与阶段A | `storage.py:222–237`、`api/app.py:118–127`；storage恢复测试与新增`test_learning_acceptance.py:156`Graph模型await时独立写入成功，取消继续传播且interrupted可查、重复恢复不重放；Web `api-flow.spec.ts:129`实际杀停/重启临时server，生成中断GET/显式retry、已发布图及历史保留，页面无自动POST；完整474例包含原阶段A回归，无failed/errors/skipped。 |

#### 独立执行输出与默认门禁

Windows / Python3.11.11 / Node22.17.0 / uv0.8.13。首次后台工具只给0秒/空日志且目标日志不存在，明确不计执行证据；改用前台保留完整输出实际执行。

- `npm.cmd run ci`：**退出0，91.9秒，末行“基础 CI 检查通过”**。Node24/24；Ruff `All checks passed!`；Pyright `0 errors, 0 warnings, 0 informations`；pytest **474 passed, 1 warning in 15.65s**；Web锁定安装/typecheck/lint/build成功，unit14/14、Mock16/16、实际FastAPI/CORS/临时SQLite/固定Provider浏览器3/3。完整临时日志文件名`b1-independent-ci.log`（不作为仓库链接，不存敏感原文）。
- `uv run --locked pytest -q tests/test_learning_contract.py tests/test_learning_api.py tests/test_learning_security.py tests/test_learning_storage.py tests/test_learning_validation.py tests/test_learning_acceptance.py`：**242 passed, 1 warning in 13.50s**。其中新增acceptance14项独立运行14 passed；CI后仅给同一哨兵测试加默认源负对照，再定向14 passed/2.03s，未影响业务/默认流程。
- `scripts/ci.cjs:34–39`实际顺序仍strict检查→build→Chromium→`test:flow`→`test:api-flow`；`tests/tooling.test.cjs:31`执行顺序回归通过。`scripts/lib/common.cjs:8–19`按生成目录/SQLite精确排除，`:21`对应测试保留tests/e2e/src/package-lock/Playwright配置；完整源包、初始化与提取后CLI回归亦通过，没有排除源码或关闭门禁。
- Windows巨大param只改为`ascii-byte-overflow`/`utf8-byte-overflow`短ID（`test_learning_validation.py:344–345`），仍分别使用原256KiB+1字符和UTF-8超限样本，无skip或减小数据。Ruff原10项现全应用零诊断，局部BLE001保持明确安全边界说明而非全局关闭。
- `uv run --locked python scripts/verify_learning_model.py --stage b1`：**SKIPPED，退出2**，明确no configuration read/no network；不计真实模型通过。
- 验收记录及学习沉淀写入后文档骨架/本地链接检查退出0，离线Markdownlint0.22.0检查67文件/0错误，`git diff --check`退出0，cached diff仍为空。

本次无剩余阻断。建议/未验证保持分层：真实模型目标澄清与图谱效果未验证；远端平台矩阵未执行；Starlette TestClient弃用warning仍1条；npm镜像audit两个接口返回404，依赖安装成功不等于漏洞审计通过。后两项沿用既有技术债，不据软件契约绿灯宣称已完成安全审计、上线准备或B2–B4。

### B2 文档交付检查记录

本次仅改四个文档：`docs/design-docs/learning-b2-api-contract.md`、`docs/exec-plans/active/learning-loop-web.md`、`docs/design-docs/index.md`、`docs/histories/2026-10/20261009-1146-learning-loop-web-plan.md`。B1软件验收勾选依据派单人的接受，不重写历史待接受记录，不更改B1冻结契约；无B2业务代码/模型/迁移。

2026-10-09本轮文档检查实际输出（均退出0，最终收口按相同命令复查）：

| 检查 | 输出/边界 |
| --- | --- |
| `npm.cmd run check:docs` | `文档骨架检查通过` |
| 既有checkMarkdownLinks仓库全文本地链接检查 | `Markdown local links check passed` |
| `npx.cmd --offline --loglevel=error markdownlint-cli2@0.22.0 "**/*.md"` | `Linting: 68 file(s)` / `Summary: 0 error(s)`；沿用缓存固定版本、不联网 |
| 只读Node stdin文档条款检查 | `B2 DOCUMENT CHECK: 4 files whitespace/conflicts; 8 unique routes; 22 unique matrix rows; B1 software complete/B2 implementation pending; index/contract link targets retained by projectPath (not API/business tests)`；包含新增未tracked文件，不只检查git tracked差异 |
| `git diff --check` / `git diff --cached --stat` | 无输出/退出0；无stage/commit/reset/stash |
| B1冻结文件SHA256 | `1923c1ac95e9e4ee177bdb36bdaae7671825f7a66add9d4af812f663047baac0`，与经理已追溯版本相同，本轮未改 |

条款检查首次使用PowerShell stdin内中文匹配时因编码出现假失败，改为ASCII阶段前缀及真实projectPath裁剪规则后通过；不是API/业务测试失败或绕过文档校验。没有运行B2 pytest/Web/类型检查/全量CI，因为本轮无B2实现；上方B1独立474等为已有证据，不能算本轮重跑。B2设计交付待周经理/严审复核，B2业务完成勾选保持未完成，真实模型/个人DB迁移仍未授权执行。

### 历史设计阶段已执行检查

基线命令 `git status --short; git diff --stat; git diff --cached --stat` 均退出0；Node v22.17.0、npm10.9.2、uv0.8.13。

2026-10-09 本轮文档检查（均退出0）：

```text
npm.cmd run check:docs
文档骨架检查通过

node -e "require('./scripts/lib/checks.cjs').checkMarkdownLinks(process.cwd()); console.log('Markdown local links check passed')"
Markdown local links check passed

npx.cmd --yes --loglevel=error markdownlint-cli2@0.22.0 "**/*.md"
markdownlint-cli2 v0.22.0 (markdownlint v0.40.0)
Linting: 63 file(s)
Summary: 0 error(s)

git diff --check
无输出，退出0
```

补充用PowerShell here-string将只读Node检查经stdin运行：契约内4个JSON例子均可解析、12组method/path无重复；全文链接/骨架/Markdown/差异再次通过。早先临时检查命令曾因shell引号/换行转义失败（未改文件），改用stdin后退出0；不是业务或文档校验失败。

严审只读复核完成（delegation `05c6b012-6270-4f1b-be53-a9ed2d5af42d`）：B1契约无必须阻断前端独立实现的问题；计划指出两项阻断——旧作答重评可按evaluated_at抢占新作答、3天复习建议未进入B4行动。2026-10-09已修正文档：分开attempt_index与evaluation_version，证据年龄按submitted_at；统一review_due_at与行动优先级，补延迟评价/重评及3天/14天边界案例。修正后文档骨架、链接、Markdown（63文件/0错误）、git diff --check均退出0；经stdin运行一次性Node规则演算，输出 `DOCUMENT RULE SIMULATION: 20 assertions passed (not API/business tests)`，覆盖旧作答重评/迟到、评价版本、新作答失败与复习边界。演算不等于API/业务测试，仍由周经理/严审最终验收。给阿岚的直接提前同步受成员委派权限拒绝，需周经理转发上述契约入口；未启动前端实现。

2026-10-09严审针对复核完成（delegation `92da0177-6107-4496-80b0-0e9732e21bdd`）：确认上述两项阻断均可撤销，本范围无剩余必须修复项；history与计划一致。独立文档条款核对/规则演算31断言通过，git diff --check通过（检查命令管道编码问题改用ASCII转义后通过）。这些不是业务/API测试，不代表B3/B4已实现或验收。B3/B4实施必须将本计划顺序/时钟案例及评价版本乱序、失败重评保留成功版本转为持久化/API回归；业务完成仍由派单人/独立测试确认。

### 历史设计阶段未执行与复验

历史设计阶段没有业务实现、依赖安装、迁移、模型调用、Web/API/领域测试、全量 CI 或部署；这些不是当前B1实施轮次的结论。阶段 A 历史测试不是当前重跑证据。计划/契约已获周经理和严审复核，实施后仍须独立验收。文档复验用 `npm.cmd run check:docs`、固定版本 Markdownlint、仓库链接检查、`git diff --check`；代码各阶段按上方门禁执行并记录具体输出。
