# B2 节点学习 HTTP、持久化与 Agent 接入契约

状态：2026-10-09，**R1–R4设计修订已送复核，尚未冻结、未实现、未做 B2 业务验收**。B1 已由周经理接受本机固定 Provider 软件契约验收，真实模型效果仍未验证。唯一实施计划为 `docs/exec-plans/active/learning-loop-web.md`，见[计划目录](../exec-plans/active/)（初始化会裁剪任务记录，不链接具体文件）。产品输入见[业务交接](learning-business-handoff.md)第3、5.2、6、6.3、7节；基础类型、安全与错误格式沿用 [B1 契约](learning-b1-api-contract.md)。前后端复核本文件后独立实现，不从示例猜未列字段。

## 1. 范围、兼容性与选择理由

- B2 只做明确节点选区、教学对话、逐轮快照、消息/失败保存和安全历史恢复。提问/讲解不产生 Exercise、Attempt、Evidence 或掌握状态；不执行用户代码，不生成实际 CSV 文件。
- 复用 `AgentLoop.process` / `AgentRunner.run` / `ModelProvider.chat` / `ToolRegistry`，不另写教学模型循环。领域调用层负责 SQLite 与历史装配；Runner 不读 DB、不算学习业务，Trace/Hook 不成为事实源。
- Base path `/api/v1`，本机单 worker、固定服务端 `local-user`、非流式同步请求。沿用 B1 Host/Origin、512 KiB body、strict/extra forbid、全文 JSON、UUID v4 小写、UTC `Z`、安全摘要等守卫。请求不得提供身份、actor、模型配置、工具注册信息、SQL/文件路径。
- B1 的12条路由及其成功/错误字段含义不变。B2 新增路由和读取类型；统一 ApiError 的 `details.resource_type` **增加** `session|turn`，只在 B2 路由返回。其他 details 键和 B1 `failure_reason` 枚举不变。此响应枚举增量须阿岚/严审同步 TS、OpenAPI、错误解析测试，不修改冻结 B1 正文来掩盖差异。
- 会话绑定稳定 goal/graph ID，**不永久钉住创建时修订**：每条新消息显式提交用户所见 `expected_graph_revision`，必须是当前 published 修订；服务端取其中的 node_version。理由：修订后可继续同一会话，但旧轮次不被新图重解释。
- 每个 submission 只执行一次。相同键是查询式重发，不重新调用模型/工具；失败后的新提问必须用新键，属于新业务请求。理由：先做到确定的事实保存与去重，不假装能安全续跑失败工具链。
- 不提供 SSE、队列、取消路由、会话删除/reset、自动摘要、后台重试、执行检查点或通用 Run 恢复。CLI `/reset` 仍只清空 CLI 内存历史，不能删学习资产；需要新的教学历史就创建新会话。

## 2. 路由与查询约定

所有 path ID 按 UUID v4 校验，包括 submission_id。未知/重复 query 为422；GET 无 body。不匹配/非所属的会话、轮次、目标或图谱为404，不区分别人的资产。会话下查询必须同时匹配 session_id，不能仅凭 turn_id 读另一会话。

| 方法与路径（省略 `/api/v1`） | 输入 | 成功 | 主要失败 |
| --- | --- | --- | --- |
| POST `/sessions` | CreateSession | 201 SessionRead | 404/409/422/503 |
| GET `/sessions` | `goal_id?: UUID, graph_id?: UUID, limit?: int, offset?: int` | 200 SessionPage | 404/422 |
| GET `/sessions/{session_id}` | 无 | 200 SessionRead | 404 |
| POST `/sessions/{session_id}/messages` | SubmitMessage | 201 TurnRead（首次 completed）；200 TurnRead（同键已终态） | 404/409/422/502/503/500；已保存失败可查 |
| GET `/sessions/{session_id}/turns` | `after_turn_index?: int, limit?: int` | 200 TurnPage | 404/422 |
| GET `/sessions/{session_id}/turns/{turn_id}` | 无 | 200 TurnRead（含历史快照/消息） | 404 |
| GET `/sessions/{session_id}/submissions/{submission_id}` | 无 | 200 TurnRead | 404 |
| GET `/sessions/{session_id}/turns/{turn_id}/business-effects` | 无 | 200 BusinessEffectsRead | 404 |

- SessionPage：`{items: SessionRead[], next_offset: int|null}`；limit 默认20、1..100；offset 默认0、0..1000000。按 created_at 降序、id 升序，无删除；有新建会话时 offset 页会移动，Web 以 ID 去重，刷新从0开始，不承诺列表快照隔离。goal_id/graph_id 若给出均先验证所属，两者都给出但不匹配为422。
- TurnPage：`{items: TurnSummary[], next_after_turn_index: int|null}`；limit 默认20、1..100；after_turn_index 默认0、0..2147483647。按 turn_index 升序，只返回大于 cursor 的轮次；有下一页时 cursor 为本页最后 index，否则null。用服务端序号而非模型/客户端时间排序，无重复轮次。轮次到达2147483647后409 `session_limit_reached`，提示新建会话，不溢出/覆盖。
- Session 查询不调用模型，不要求配置可用。创建会话不执行教学、不隐式选择 root/上次节点。POST 创建没有通用创建幂等键：页面禁双击，响应丢失先从列表找回，不自动重发；稳定提交标识从发送消息开始。
- 每条消息必须显式提供选区；不写“当前节点”共享状态，不使用上一轮选区作为默认。等待时页面禁同会话并行发送，但后端仍独立互斥防守。

## 3. 严格请求与选区/版本守卫

下列字段全部必需；不接受 bool 当 int、数字当字符串、未知字段或 NUL。content trim 后1..8000 Unicode字符；服务端保存/比较 trim 后文本。UUID不能 trim 成另一个有效 ID。所有正整数上限2147483647；查询只接受规范十进制数字，不接受浮点、负数或 bool 文本。

```typescript
type CreateSession = {
  goal_id: string;
  graph_id: string;
  expected_graph_revision: number;
};
type SubmitMessage = {
  submission_id: string; // Web首次发送前生成，直到查到结果都保持不变
  expected_graph_revision: number;
  selected_node_ids: string[]; // 1..5，顺序有意义，不重复
  content: string;
};
```

首次接受消息前，校验顺序为：JSON/Schema → 会话/身份 → 已有 submission 键比较 → 同会话执行互斥 → goal/graph归属与绑定 → 图修订 → goal/graph状态 → 选区 → 短事务重验并保存。语法非法即使同键也422。事务是首次接受时点，不保证图在整个模型等待期间不再修订。成功历史的解码/校验/装配和模型配置读取均在新轮接受提交之后，详见5.2、6.1。

1. 创建必须 Goal confirmed、Graph published、Graph.goal_id等于goal_id、Goal.graph_id等于graph_id，且 expected_graph_revision等于当前revision；资源间绑定不匹配422 `validation_failed`，错误版本409 `revision_conflict`。版本合法后先检查Goal confirmed、再检查Graph published：未确认409 `invalid_state`指实际goal，未发布则指实际graph（同时不合法先指goal）；两种状态错误的expected/current_revision均null，不能冒充版本冲突。消息同样重验这些前置；此处只定义B2，不修改B1路由错误语义。
2. 消息继承会话 goal/graph，禁止重新绑定。选区是当前修订中的1..5个非root节点，concept/practice/assessment均可教学；root作为范围介绍，不是独立学习选区。空选区、root、重复节点、超过5个、他图/已删除节点均422，定位 selected_node_ids。选区不自动扩展后代或前置，不以未掌握前置硬禁自主学习。
3. 多节点请求按输入顺序教学，第一项是主节点，全部为本轮授权范围。顺序也参与同键内容比较；不排序去重掩盖用户意图。页面明确显示全部选中节点，不能看似单节点却提交多个。
4. 请求不接收 node_version；服务端从锁内读到的 graph_revision复制 NodeRead，绑定精确版本。前端用当前 GraphRead渲染并提交revision，不能把旧缓存标签和新revision拼成请求。
5. 正式图修订后：新轮使用最新revision；旧revision发送409，GET最新图、重新展示/选择后以**未被接受的键**再发。删掉的选区需重新选择；内容升级取新node_version；仅布局/权重/关系变化取新graph_revision但相应node_version不变。所有旧ContextSnapshot/消息永久保持当时值。
6. 模型等待中图变更：本轮仍用已保存修订完成/失败，工具只能读该快照；不追读当前图、不改写快照、不把旧教学冒充新内容。业务效果响应绑定原graph_revision/node_version，页面对比最新图提示历史版本。B3写证据将另加当前版本有效性守卫，B2不能先生成证据。

## 4. 读取类型、状态与消息事实

引用的 GoalRead/NodeRead/EdgeRead 是 B1 类型。Read 所列字段全部存在，可空显式null；成功直接返回对象，无 data envelope。服务端 ID 是UUID v4，created_at/finished_at为UTC。以下TS为契约说明，不是已实现文件。

```typescript
type SessionRead = {
  id: string;
  learner_id: "local-user";
  goal_id: string;
  graph_id: string;
  created_graph_revision: number;
  current_graph_revision: number; // 查询时当前图修订，不用它改写旧快照
  last_turn_index: number; // 无轮次为0；包括失败/执行中轮次
  in_progress_turn_id: string | null;
  created_at: string;
  updated_at: string;
};
type ContextSnapshot = {
  schema_version: 1;
  goal: GoalRead; // 接受时完整confirmed值/回答/假设
  graph_id: string;
  graph_revision: number;
  selected_node_ids: string[];
  selected_nodes: NodeRead[]; // 与选区顺序相同，包含版本/教学策略
  selected_edges: EdgeRead[]; // 当时两端均在选区中的边，沿用B1稳定排序
};
type TurnStatus = "executing" | "completed" | "failed" | "interrupted";
type TurnStopReason =
  | "completed" | "model_error" | "invalid_response" | "output_truncated"
  | "content_filtered" | "empty_response" | "step_limit" | "tool_error" | "context_error"
  | "configuration_error" | "history_error" | "internal_error" | "interrupted";
type TurnError = {
  code: string;
  message: string; // 服务端安全常量摘要，不是原始异常或模型文本
  reason: "configuration" | "transport" | "invalid_output" | "context"
    | "history" | "execution" | "interrupted";
  retryable: boolean; // 允许修复后新提问，不表示本键会重执行
};
type TurnSummary = {
  id: string;
  session_id: string;
  submission_id: string;
  turn_index: number;
  graph_revision: number;
  selected_node_ids: string[];
  content: string; // 用户原文trim后的输入，不拼domain_context
  status: TurnStatus;
  stop_reason: TurnStopReason | null;
  answer: string | null; // 只有completed非空
  error: TurnError | null;
  history_eligible: boolean;
  created_at: string;
  finished_at: string | null;
};
type StoredToolCall = { id: string; name: string; arguments: Record<string, unknown> }; // id为6.1.1服务端轮次命名空间ID
type StoredMessage = {
  index: number; // 本轮0起连续，不是客户端ID
  role: "user" | "assistant" | "tool";
  content: string | null;
  tool_calls: StoredToolCall[];
  tool_call_id: string | null;
};
type TurnRead = TurnSummary & {
  context_snapshot: ContextSnapshot;
  context_text: string; // 当时注入的精确序列化数据，不重算
  instruction_version: "learning-teacher-v1";
  messages: StoredMessage[]; // 接受时预装配保存的user + Runner实际返回的新增消息；保存不等于发送
  business_effects: BusinessEffectRead[]; // 查询已提交的独立领域事实
};
type BusinessEffectRead = {
  operation_id: string;
  kind: string; // 安全领域操作名1..80；B2生产无写操作，数组永远空
  resource_id: string;
  node_id: string;
  node_version: number;
  summary: string; // 安全摘要1..1000，不含模型参数、私有答案或密钥
  committed_at: string;
};
type BusinessEffectsRead = {
  session_id: string;
  turn_id: string;
  items: BusinessEffectRead[]; // committed_at升序、operation_id升序
};
```

### 4.1 状态不变量

| 状态 | stop_reason / answer / error / finished_at / history_eligible |
| --- | --- |
| executing | null / null / null / null / false |
| completed | completed / 非空 / null / 非空 / true；必须同时通过配对守卫 |
| failed | 除completed/interrupted外的停止原因 / null / 非空 / 非空 / false |
| interrupted | interrupted / null / reason=interrupted的error / 非空 / false |

合法输入、精确上下文与预装配user在同一接受事务保存后进入executing。系统教学指令只保存固定版本，在装配时单独放system，不冒充用户消息。StoredMessage[0]是接受时用 `build_messages(instructions, [], content, context_text)[-1]` 预装配的user（含当轮 `<domain_context>`）；真正执行时用已校验历史重建请求，当前user须逐字相等。随后只放AgentResult.messages，不重复追加final_text。仅最终completed的answer用于正常回答显示。

**预装配保存不是实际已发送**：history_error或configuration_error可只有这一条user，Provider尚未被调用。messages不是模型送达/收妥证明，HTTP或页面不得把“已保存输入”宣称为“模型已接收”；即使调用Provider也不凭messages承诺网络送达。不为此新增传输状态/重放平台。

失败的部分assistant文本仍可在messages中查询并标注“未完成”，但answer=null，不作为成功教学或下一轮模型历史。已知工具参数/查找/超时错误若Runner返回一个配对完整的tool错误消息，随后正常最终回答可completed；工具错误不代表业务写成功。意外工具异常或模型失败为failed。

持久化层不编造崩溃前丢失的assistant/tool消息。进程在工具提交后、最终消息保存前中断，轮次可以只有user，工具业务事实仍独立可查；这不满足成功历史装配条件。

### 4.2 HTTP失败与资源查询

首次接受后Runner或前置历史/配置失败返回统一ApiError而非伪造201/200成功；details.resource_type=turn、resource_id为已保存turn_id。history_invalid对应新轮failed/history_error，model_not_configured对应failed/configuration_error；均保留合法请求、精确快照和预装配user，不表示已发送。Web据此GET TurnRead；连接丢失且无turn_id时使用已保留的submission_id查询。GET turn及GET submission均200返回同一新failed轮次，读取不解码其他坏历史、不加载模型配置。GET executing仍200，不触发模型；仅用户刷新/等待后的GET查事实，不建设服务端轮询任务。

同键终态重发一律200返回原TurnRead，包括failed/interrupted：这是幂等结果查询，不把旧失败变成功；页面必须按status/error渲染，而非仅看HTTP200。首次请求失败与重发200的差别需在Web/API测试中明确覆盖。

## 5. 提交去重、互斥与错误定位

### 5.1 submission不重执行

- 唯一键 `(learner_id, session_id, submission_id)`；在首次接受事务里保存规范请求JSON及其SHA256（不依靠hash单独判等）。比较 content、expected_graph_revision、selected_node_ids及顺序。相同正文终态返回原结果；正文不同409 `submission_conflict`，既存turn_id可查询，绝不覆盖。
- 已存在的键比较优先于当前图校验：图后来修订/节点被删，旧键同正文仍可取旧结果，不能因为过期图让查询失败。已存在executing同键为409 `operation_in_progress`，details指该turn；不同键抢占正在执行的会话也409，指正在执行的turn，不写第二个user/轮次。
- Schema/资源/归属/revision/选区失败或首次写入busy时**未接受**，不占submission键。修正后可用原键。已经接受的failed/interrupted键不能更改正文或重新运行；修复配置/重新提问用新键，保存新的选区快照，之前业务事实继续可查。
- 新键不是旧工具操作的幂等续跑；页面先展示已保存效果，不提供“重新执行已成功工具”的暗示。B3将以Exercise/Attempt领域稳定标识保护新的写请求，不能用模型call_id或自然语言相似度代替。

### 5.2 单会话互斥与事务范围

服务工厂持有按session_id隔离的async锁，**非等待式拒绝冲突**。从获取会话/选区/图快照、接受保存输入与预装配user、读取并校验成功历史、创建独立Loop/闭包、执行Runner，到最终消息及状态保存/失败处理完成，一直持有；finally释放，取消不吞掉。输入Schema可在锁外校验，互斥不只包模型await。

DB另用 `UNIQUE(session_id, turn_index)`、submission唯一键、每会话executing部分唯一索引与条件状态更新防守。锁内接受必须在同一短事务重验graph revision并分配turn_index；严格顺序如下：

1. 短接受事务只处理本次合法规范请求、当前goal/graph/选区及其精确ContextSnapshot/context_text，预装配user，原子保存executing新turn、messages[0]及会话序号。**此事务不取/解码/装配成功历史、不读取模型配置**；提交失败不占键，不能伪造已保存turn。
2. 提交后仍持session锁，读取所有既有completed轮次，严格解码JSON并校验状态/eligible/快照/消息；全部通过才装配Loop.history。坏JSON、配对或任一成功不变量损坏，以新的短终态事务将已接受新turn设failed/history_error，返回500 history_invalid；Provider调用、工具执行、模型配置读取均0。旧坏资料不改写，不因过滤eligible跳过。
3. 只有历史校验完成后才加载教学模型配置/构造该轮Provider边界、Runner与Loop。缺配置使已接受轮次failed/configuration_error并503；Provider/工具仍0，预装配user保留但未发送。再调用Loop.process，当前user必须与预装配值一致，使用已保存context_text，不补读当前图。

模型await期间无读/写事务、无跨线程共享连接。不同会话并行不共享选区/Loop/history，即使同goal/graph也不串上下文。单worker是官方边界，不宣称支持多进程协调或执行租约。先接受后读历史使500能精确定位一个可查询的新失败请求，避免旧历史坏JSON在新turn创建前抛错却宣称已保存失败。

最终事务按 `status=executing` CAS写messages/answer/error/finished_at/history_eligible和会话updated_at，成功完整配对与终态一次提交。取消尽力标interrupted并继续传播；失败不得把本轮Loop的内存历史复用于下一次请求。最后落库busy/存储错误不返回成功，保留已接受turn的ID；可能仍executing，当前服务拒绝后续同会话执行，停止/重启后才能标interrupted。不能为了清锁偷偷再调模型。

### 5.3 ApiError映射

完全沿用B1 `code/message/details/retryable` 和 Issue所有字段；details每个键始终存在。expected/current_revision仅图版本冲突时填，对session/turn不冒造revision。configuration/transport/invalid_output/interrupted才填对应failure_reason；context/history/execution没有B1对应值时null，以GET TurnError细分，不扩展B1枚举或泄露异常。

| HTTP / code | 定位与处理 |
| --- | --- |
| 400/403/404/405/413/415/422 | 复用B1规范；Schema为validation_failed；不匹配资源404 |
| 409 `revision_conflict` | 指实际graph，expected_revision=本次expected_graph_revision、current_revision=当前真实图revision；failure_reason=null、issues=[]、retryable=false；刷新图再确认，不盲重发 |
| 409 `invalid_state` | 指未confirmed的实际goal或未published的实际graph（顺序见第3节）；expected_revision/current_revision/failure_reason均null、issues=[]、retryable=false；GET资源确认正确操作，不伪造版本冲突 |
| 409 `operation_in_progress` | 指正在executing的turn；retryable=false，GET等待结果 |
| 409 `submission_conflict` | 指已保存turn；retryable=false，不能把同键换内容 |
| 409 `session_limit_reached` | 指session；retryable=false，创建新会话 |
| 502 `learning_turn_failed` | 对应Runner受控非成功；已保存turn可查，安全stop_reason映射；retryable=true表示可新提问 |
| 503 `model_not_configured` | turn已failed/configuration_error，failure_reason=configuration；retryable=false，修配置后新提问 |
| 503 `storage_busy` | 未接受时资源可null；接受后指turn，无假成功，GET/必要时重启，不重新执行 |
| 500 `history_invalid` / `internal_error` | 配对/快照损坏或意外异常；retryable=false；指已保存turn，禁止污染模型历史 |

Runner现有model_error不区分Provider网络/超时，因此HTTP502、TurnError.reason=transport，**不承诺504/精确timeout**，不从错误文案猜分类；若未来Provider提供安全类型需先改契约。context_error为502/reason=context，其余invalid_response/output_truncated/content_filtered/empty_response为invalid_output，step_limit/tool_error为execution。意外异常500/internal_error，取消/重启为interrupted，均无原始错误内容。

新增固定Issue code：`empty_selection/selection_limit/duplicate_node/root_selected/foreign_node/session_graph_mismatch`；路径 `['body','selected_node_ids',index]` 或数组整体，node_ids仅本次提交的合法UUID，edge_indexes=[]。绑定问题定位goal_id/graph_id，过期revision先409再查选区，避免用新图错误指责旧页面。其他Schema issue沿用B1 required/type/extra/constraint；不回显额外字段名或内容。

## 6. Agent装配、工具清单与业务事实边界

### 6.1 逐轮装配，不共享可变绑定

领域会话用例在 `mini_learngraph/learning/` 实现；HTTP只解析Schema/调用用例，SQLite短同步操作沿用worker线程。每次接受轮次后用工厂新建该轮的Loop、Runner、ToolRegistry；Provider可复用无可变会话状态的HTTP客户端，但不能共享Loop/history或“当前节点”字段。

`instructions=learning-teacher-v1`固定教学/权限规则；`context_provider`无参闭包只返回已保存的context_text副本。快照在锁内复制并持久化，不在await中读最新节点。上下文作为数据块，当前快照指导本轮，历史快照只解释当时事实；模型文本/节点描述不能扩权或注册工具。

新轮已接受后，先读取本session **所有status=completed的轮次，不以history_eligible过滤**，按turn_index/messages.index升序逐项严格解码/校验，全部通过再深拷贝装配Loop.history。任一completed但history_eligible=false也属于坏成功轮，不能静默跳过。DB状态不变量CHECK与此读取守卫同时保留：CHECK防正常写入，读取守卫防旧库/导入/损坏，不把数据库约束当作读取校验的替代。合法failed/interrupted轮次全轮排除，不修补半条工具链。每个completed必须满足：

1. status=completed、history_eligible=true、stop_reason=completed、answer非空、error=null、finished_at非空，且快照/请求/选区归属及版本一致；user仅第一条且正好等于保存content + 当轮context_text经现有build_messages装配的文本。
2. message角色只能user/assistant/tool，无system混入；普通user/assistant不带tool_call_id，只有assistant可带tool_calls，tool不能带tool_calls且须有对应ID。
3. assistant每批tool_calls的ID为6.1.1的本轮服务端ID、名称非空、arguments为严格JSON对象；本轮及全部成功历史的**服务端ID**唯一，不能要求独立用户轮的Provider原始ID全局唯一。该批每个调用恰有一个随后tool结果，assistant.id/tool.tool_call_id使用同一映射，按调用顺序完整配对，禁止缺失/孤儿/重复/跨轮配对；工具内容非空。
4. 最后一条是无tool_calls、非空文本的assistant，且等于answer；所有tool调用在最终回答前结束。messages索引0起连续，节点归属/版本来自本轮不可变快照。
5. 任一标成功的轮次损坏，包括坏JSON、completed/eligible=false：**停止装配，不静默删一半链/跳过坏轮次/拼当前图补旧数据**，已保存新轮failed/history_error，HTTP500 history_invalid且Provider/工具/模型配置读取均零；GET新turn/新submission及同键重发200均得到该原failed对象。旧数据留存供诊断，用户可另开新会话。合法失败/interrupted轮次即使有部分配对也全轮排除。

completed在写入前也跑同一守卫；失败不读取Loop内存的“已更新历史”来绕过终态事务。上下文过长时沿用Provider/Runner失败，提示新建会话，不自动截断配对或摘要。以下边界均只在B2领域工厂实现，不改Runner、CLI或B1 Provider协议。

### 6.1.1 调用ID：Provider边界与历史职责

现OpenAIProvider响应守卫仅校验单响应批内原始ID合法/唯一，ModelProvider接口不承诺独立用户轮全局唯一；Runner却把输入历史ID纳入used_ids（runner.py:65），并在119/172–175守卫重复。直接将两个用户轮的call_1写入历史会使第二轮合法调用被拒绝。保留该内核守卫，由B2教学Provider边界承担命名空间转换：

- 每个已接受turn固定一个命名空间，使用服务端UUID的32位小写hex；本次Runner执行整个生命周期复用一个映射 `raw_id → ltc_<turn_uuid_hex>_<slot>`，slot是此轮首次遇到合法原始ID时分配的1起整数。批内按原顺序分配；前缀不按响应/步骤重建。ID只是消息配对标识，不作6.3领域操作幂等键。
- 每次输出先验证整个原始响应，批内重复或原始ID已在**本次执行**出现均抛InvalidResponseError；验证整批后才分配/记入映射并深拷贝替换assistant.tool_calls[].id。不得给同一raw_id另分slot、每响应换prefix或靠覆盖字典掩盖重复。此轮先执行call_1、后续响应再次call_1仍invalid_response；拒绝批本身执行0工具，已执行的旧批不撤销。
- Runner接收服务端ID，原样生成对应tool.tool_call_id；领域层持久化AgentResult中的同一组服务端ID，历史读取验证ID的turn归属/唯一性/配对后原样装配，**不将旧ID回译成raw_id**。同一独立新用户轮可重新使用原始call_1，新的turn命名空间不同，因此不会撞Runner历史used_ids。
- 对下层Provider的每次输入，边界深拷贝Runner给出的完整messages，历史和当前执行已有的assistant/tool均保留服务端ID，二者不单边改写。provider.py的_message_payload原样序列化这两个字段；支持的OpenAI兼容消息协议用请求内相等ID关联assistant调用与tool结果，并不要求历史ID必须是旧响应的原始拼写。因此不需要跨重启保存raw映射或反解旧ID，既可给Provider完整配对输入，又可让Runner守住全历史服务端ID唯一。
- raw映射仅属于这一轮边界，不共享会话/Provider客户端；新键新turn才有新命名空间，同键重发不执行也不重映射。历史服务端ID稳定不重写。B2-08/12必须捕获边界输出、Runner输入/新增消息和下层Provider实际请求的assistant/tool两端；仅测最终回答不足以证明转换兼容。

### 6.1.2 完整响应预算的精确口径

B2教学边界对每个ModelResponse完整序列化对象设置256 KiB（262144 UTF-8字节）、最多32层容器、每批最多16个tool calls（**等于上限合法**）。对象恰为 `{content, tool_calls: [{id, name, arguments}], finish_reason, usage}`，所有字段都存在，null/空数组也计入；usage及arguments完整计入，不只检查content或工具参数，不读取/新增私有推理字段。值只能是严格JSON（对象键为字符串，有限数值，无自定义对象/非JSON容器），使用 `json.dumps(..., ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':')).encode('utf-8', errors='strict')` 计字节；不能用字符数、HTTP压缩体或ensure_ascii转义后的长度代替。

深度按JSON对象/数组容器计：根对象为第1层，每进入子对象/数组加1，标量不加层；tool_calls数组为第2层、其中call对象第3层、arguments对象第4层，usage对象第2层。根usage包31层对象的整体深度为32（合法），包32层为33（拒绝）；空容器也计一层。实现应有有界遍历，循环结构/不可序列化/无效UTF-8及超限均InvalidResponseError，不使RecursionError变500。

上述完整预算对命名空间转换前的原始对象和转换后交给Runner的对象**都检查**，避免长raw ID或重写开销绕过限额；其他字段/工具顺序不改写。不合法在该响应任何工具执行前转invalid_response，合法响应仍由Runner检查finish_reason、调用ID与step_limit，length/content_filter仍走既有截断/过滤终态并零工具，不削弱内核守卫。B2-12分别验证ASCII及中文UTF-8恰262144/超1字节、usage或arguments将完整体推过限、深度32/33及16/17调用，不能把这些设计演算当成已实现测试。

### 6.2 B2生产注册清单

此表是**B2实施目标清单，不代表当前已接入**。不直接把CLI default_tools整包注册给Web学习会话。

| 工具 | strict实参 | 绑定与输出 |
| --- | --- | --- |
| `get_selected_node` | `{node_id: UUID}`，extra forbid | 只读该轮选区中的节点；返回当时NodeRead、graph_revision，JSON文本；他图/未选节点为安全工具错误，不追读最新DB |
| `calculate` | `{expression: str 1..256}`，extra forbid/strict/无NUL | 复用已有受限AST实现与数量/有限数值/除零守卫；无代码/文件/网络，输出受限计算结果 |

不注册get_current_time（教学不需时间工具）、发布/修订/任意SQL/文件/网络工具，也不注册练习生成、提交、评价、Evidence或状态修改工具。节点工具绑定服务端learner/goal/session/turn及选区；参数不得提供learner_id、graph_id或node_version扩权。工具默认10秒预算足够只读/计算，B3内含模型的工具超时另行设计，不先宣称练习可用。

### 6.3 已提交业务事实与去重

`business-effects`通过领域仓储独立读取已提交业务操作，不从自然语言answer、Trace、Loop.history或仅终态messages推断。B2生产工具无写入，所以TurnRead.business_effects及独立查询items均为[]；“生成练习”等自然语言不能显示为已保存练习。B3实际写能力由B3契约另行开放。

为验证交接要求的“写成功、最终回答失败”，B2仅在安全工厂依赖注入中提供**测试专用夹具写工具**，合成事实落临时DB，工具名/kind为fixture_write，生产注册/OpenAPI无该工具，无HTTP开关。不能把夹具测试通过写成练习/证据已实现。

仅学习领域的操作结果表保存已经提交的事实：稳定键 `(learner_id, session_id, submission_id, action_name, operation_slot)`。slot由领域工具闭包定义，不由模型call_id/任意实参生成；夹具单一动作固定 `fixture:primary`。同键同规范参数返回原operation_id/resource_id，同键不同参数为领域冲突、无第二次写入。事实与操作结果在**同一个短事务**提交；返回给Runner的文本失败或最终模型失败不能撤销成功事实。生产B2此表无行，未来B3的slot/同题多操作规则必须在B3冻结，不能拿“第N个模型调用”做稳定身份。

测试注入只证明领域事务/去重/独立查询边界：重复相同submission的HTTP查询零重执行，直接重复夹具领域操作返回同事实，换tool_call_id也不重复；冲突参数不覆盖。新submission是新业务请求，不在B2伪造跨消息语义去重。无pending/replay/租约/自动补偿/跨进程工具重放平台。

## 7. SQLite schema v2与启动/迁移设计

以下是实施方案，不是已执行DDL。B1现有四表/快照/CLI保持不变；沿用标准库sqlite3、线程内短连接、foreign_keys开启、BEGIN IMMEDIATE、busy安全错误。新库初始化v2，已有v1 **拒绝自动升级**，由服务停止后的显式本地迁移入口升级，启动/读取均不依赖模型Settings。

| 新表/约束 | 字段与用途 |
| --- | --- |
| `learning_sessions` | id PK；learner_id CHECK local-user；goal_id FK goals、graph_id FK graphs（用例重验两者绑定）；created_graph_revision与graph_id联合FK graph_revisions；last_turn_index>=0；created_at/updated_at。无共享当前选区、无级联删除 |
| `learning_turns` | id PK；session_id FK；learner_id CHECK；submission_id；turn_index>0；request_json/request_sha256；graph_id/graph_revision联合FK历史修订；context_snapshot_json/context_text；instruction_version；status/stop_reason/answer/error_json/history_eligible；created_at/finished_at。UNIQUE(session_id,submission_id)、UNIQUE(session_id,turn_index)，部分UNIQUE(session_id) WHERE status='executing'，状态不变量CHECK |
| `learning_messages` | turn_id FK、message_index>=0，联合PK；role/content/tool_calls_json/tool_call_id。存接受时预装配user及Runner实际返回链，调用ID是服务端轮次命名空间ID；不表示user已发送。用例守卫配对完整，DB检查角色/字段基本组合 |
| `learning_turn_nodes` | turn_id/node_id联合PK；selected_index>=0、UNIQUE(turn_id,selected_index)（仅轮内唯一，不做全表唯一）；node_version>0；graph_id；FK(node_id,node_version)→node_versions。图归属与快照一致在接受事务校验，旧内容/删除节点引用仍保留 |
| `learning_tool_operations` | operation_id PK；learner/session/submission/action_name/operation_slot唯一；turn_id FK；input_json/input_sha256；resource_id/node_id/node_version/kind/summary/committed_at/result_json；FK节点历史。只记录原子提交成功事实，无通用执行状态；夹具的synthetic事实表只在测试创建 |

列表索引：sessions(learner_id,created_at,id)、sessions(goal_id,graph_id)、turns(session_id,turn_index)、operations(turn_id,committed_at,operation_id)。node_versions现有主键可直接引用；node的graph_id由用例对历史表和快照双重校验，不能只凭FK允许跨图。turns的session/graph/learner一致性在同一用例事务检查，并测试直接伪造不被历史装配接受。SQL值参数化、表名固定，JSON strict解码不接受损坏资料作为正常消息。

### 7.1 离线升级与回滚检查点

1. 拟新增显式入口 `python -m mini_learngraph.learning.migrate --database <db> --backup <backup>`（尚不存在，不是当前可运行命令）。仅支持v1→v2；不调用模型、不读模型配置、不默认选择个人DB，服务必须停止。真实DB迁移先向周经理提交备份/回滚方案并获确认，本轮不创建/修改个人库。
2. 识别user_version及B1真实schema/外键/数据；未知版本、未标版本非空库、缺表/坏schema或完整性检查失败拒绝，不能仅看整数就套DDL。已v2返回无需升级，不覆盖备份/重复DDL；未来版本拒绝且资产不变。
3. 使用SQLite backup API生成**新的、不覆盖已有文件**的一致备份，覆盖WAL中已提交数据；备份quick_check/foreign_key_check成功且version=1后才升级。备份失败源库不改；只复制主文件不是有效WAL备份。
4. 全部新增DDL/索引/约束在单事务完成；迁移后核对B1快照/计数/ID不变、外键及v2结构，最后设置user_version=2并提交。不用隐式提交的executescript破坏原子性；任一点故障回滚到v1、无半表，备份保留。
5. 回滚方案是停止新应用 → 保留失败/升级后库副本供诊断 → 用一致v1备份恢复到新的受控路径 → 旧应用指向恢复库；与原WAL/SHM隔离，验证版本/快照/旧API后再恢复使用。不提供删除B2表的逆迁移；备份后新会话数据不随回滚保留，必须明确这个损失窗口。真实资产路径切换/恢复仍须派单人确认，不自动覆盖个人文件。
6. v2启动恢复只把遗留executing轮次设interrupted/error安全摘要/finished_at/history_eligible=false，保持原请求/消息/业务事实；last_turn_index不回退，不重放模型或工具，重复启动幂等。读取失败/历史快照/业务事实不构造Provider，不要求密钥。

## 8. 前端流程与交接门禁

1. 获取published graph；从会话列表继续或创建；明确选1..5个非root节点（首项主节点），空选区禁发，展示节点标签及版本。切loop→csv时发送新选区，旧轮次可以展开查看原快照而非当前图标签。
2. 发送前生成submission_id，保留完整请求直到查询到接受结果；等待时禁同会话第二次发送。收到ApiError带turn_id后GET详情/业务效果；连接丢失先按submission_id GET，404才允许用同键原正文重发，409则GET既存轮次，不换键撞在执行中的轮次。
3. completed展示answer；failed/interrupted展示安全error/stop_reason，部分消息标未完成；**独立显示业务事实**，即使answer为空也可查。相同键重发返回200失败对象时仍失败展示；重新提问用新键且明确这是新轮次。
4. 图revision_conflict刷新图并重新展示选区再发；不静默替用户改选区。同键submission_conflict展示已保存消息，不覆盖。刷新/服务重启后Session/Turn/ContextSnapshot/角色工具链可读，interrupted只提示重新提问，页面不能自动POST重放。
5. 唯一计划登记完整B2离线验收矩阵，前后端实施后跑相关pytest、全应用Ruff/Pyright、Web typecheck/lint/unit/build/Mock/API流程及默认`npm.cmd run ci`；保护严审已修的 `tests/conftest.py` / `web/tests/api_fixture.py` 环境隔离，扩展B2固定Provider而不是读取dotenv/个人模型或DB。测试工厂显式注入Provider、预算和临时DB；禁止偷偷退回生产Settings，清除相关继承环境，读配置前哨兵和受控污染负对照覆盖API/Web子进程。生产启动查询不得构造模型Settings，只有首次明确教学执行才加载配置。真实教学效果另行授权opt-in记录，桩不证明模型能教会CSV。

仍需复核而非新增产品决策：root不允许独立选区、最多5个/主节点顺序、同键只查终态不重执行、修订后显式最新图续接、只读工具清单和v1离线升级方案。它们是现有目标内的技术守卫；周经理/严审复核无阻断后才派实现。尚未获得真实模型调用/个人DB迁移/部署授权，不为等这些授权而扩大B2。
