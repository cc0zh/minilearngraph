# B1 目标与图谱 HTTP 契约

状态：2026-10-09，**已获周经理/严审复核，B1 后端实施中，尚未验收**。唯一实施计划为 `docs/exec-plans/active/learning-loop-web.md`，见[计划目录](../exec-plans/active/)（初始化新项目会裁剪任务记录，故不创建悬空文件链接）；产品输入见[业务交接](learning-business-handoff.md)。后端老秦、前端阿岚按此独立实现；变更先同步，不能静默改变已用接口。B2→B4只有计划，不在本契约伪造已冻结接口。

## 1. 传输、身份和兼容性

- Base path `/api/v1`，JSON UTF-8，字段 snake_case；非流式。成功返回所列对象本身，不包 data；无204写响应。所有写请求必须 `Content-Type: application/json`（允许 charset），GET无body。
- 服务默认 `127.0.0.1:8000`，Web开发 `127.0.0.1:5173`。首版服务端固定 `local-user`，请求不得含 learner_id/actor/model config；目标/图谱始终按该学习者隔离。ID不可猜测不等于授权。
- API数据查询/候选编辑/发布不依赖模型可用性；模型Settings在模型操作入口加载并校验，缺配置不阻止本机服务启动和已存资产读取，按第5节返回明确错误。
- Host限定本机服务地址；Origin仅明确允许的本地 Web地址，默认 `http://127.0.0.1:5173` 和 `http://localhost:5173`，生产同源本机地址按配置添加。无 `*`、无cookie认证。明确带未知/null Origin请求403；无Origin的本地CLI允许。仅CORS预检不够，写入前检查Origin，JSON防简单跨站表单写入。多人/LAN/公网不在首版。
- write body上限512 KiB；过大413。不上传文件。不解析客户端提供的SQL、路径、模型地址或指令权限。密钥不进Schema/响应/日志，错误不得回显完整用户输入/模型响应/请求头。
- UUID v4小写字符串作为 Goal/Graph/Node服务端ID；临时 ref不是ID。时间是RFC3339带时区字符串，服务端返回UTC `Z`。revision/node_version为正整数，绝不接收bool代替int。
- Schema所有对象 `extra=forbid`、strict；非空文本trim后计Unicode字符数，拒绝NUL；可空字段显式null，不把缺失默认为用户确认。无NaN/Infinity/重复JSON键；非法JSON400。数组数量/字符串长度先校验再模型/DB调用。
- 全量替换请求所有列出的字段必需，包括允许null的字段。没有PATCH式“缺失表示不变”。下文如无标“可选/默认”即必需。Read类型字段固定、可空显式null；前端可忽略将来新增的响应字段，新写字段和枚举变化必须先协商。`/api/v1`下不悄改字段含义/枚举。

## 2. 路由索引

全部path ID按UUID校验；引用未找到或不属于当前学习者为404（不泄露别人的资产）。列表不分页，首版本机少量资产；固定排序created_at降序、ID升序。列表 items为完整Read对象，便于前端无额外摘要Schema。查询参数未知为422。

| 方法与路径（省略 `/api/v1`） | 请求 | 成功 | 主要失败 |
| --- | --- | --- | --- |
| GET `/goals` | query `status?: draft\|confirmed` | 200 `{items: GoalRead[]}` | 422 |
| POST `/goals` | CreateGoal | 201 GoalRead（澄清ready） | 422/503；模型失败502/504，持久化draft可GET |
| GET `/goals/{goal_id}` | 无 | 200 GoalRead | 404 |
| POST `/goals/{goal_id}/clarify` | RevisionRequest | 200 GoalRead | 404/409/503/502/504；仅失败/中断澄清可重试 |
| POST `/goals/{goal_id}/confirm` | ConfirmGoal | 200 GoalRead（confirmed） | 404/409/422 |
| GET `/graphs` | query `goal_id?: UUID, status?: generating\|generation_failed\|candidate\|published` | 200 `{items: GraphRead[]}` | 404/422 |
| POST `/goals/{goal_id}/graphs` | RevisionRequest（Goal revision） | 201 GraphRead（candidate） | 404/409/503/502/504 |
| GET `/graphs/{graph_id}` | query `revision?: positive-int`，缺省当前 | 200 GraphRead | 404/422；历史revision不存在404 |
| POST `/graphs/{graph_id}/generate` | RevisionRequest（Graph revision） | 200 GraphRead（candidate） | 404/409/503/502/504；仅generation_failed可重试 |
| PUT `/graphs/{graph_id}` | EditCandidate | 200 GraphWriteResult | 404/409/422；只candidate |
| POST `/graphs/{graph_id}/publish` | PublishGraph | 200 GraphRead（published） | 404/409/422；只candidate |
| POST `/graphs/{graph_id}/revise` | ReviseGraph | 200 GraphWriteResult（仍published） | 404/409/422；只published且明确确认 |

同步生成不返回202、不轮询job。前端设置等待态，失败/连接断开先GET列表/详情，读取持久化状态后再重试；不得无条件重发创建请求。B1不承诺POST创建的通用幂等键：若创建响应丢失，目标列表找回已有draft，不自动重复创建；一目标一Graph用唯一约束防重复生成资产。

## 3. 基础和目标 Schema

为缩短契约，下表类型可直接转换为Pydantic/TS类型；不是现成代码。所有数组保留用户顺序。

### 3.1 可复用类型

| 类型 | 字段、范围 |
| --- | --- |
| RevisionRequest | `{expected_revision: int>=1}` |
| Availability | `{minutes_per_day: int 1..1440, days_per_week: int 1..7}` |
| Preferences | `{session_minutes: int 1..1440, preferred_action_types: (learn\|practice\|review\|assessment)[]}`，类型无重复，可空数组 |
| GoalValues | `title: str 1..200; intent: str 1..100或null; prior_knowledge: str 1..4000或null; desired_outcome: str 1..4000; time_limit_text: str 1..1000或null; deadline_at: RFC3339或null; target_weight: int 1..100; availability: Availability或null; preferences: Preferences或null` |
| Assumption | `{key: str 1..120, field: str 1..100或null, value: str 1..2000或null, reason: str 1..2000}`；key唯一，field若有只能为GoalValues字段 |
| QuestionOption | `{id: str 1..80, label: str 1..500}`，同题ID唯一 |
| ClarificationQuestion | `key: str 1..80（匹配 [a-z][a-z0-9_]*）; prompt: str 1..2000; options: QuestionOption[0..8]; reason: str 1..2000; graph_impact: scope\|nodes\|relations\|teaching\|schedule; allow_custom: bool; allow_skip: bool; default_assumption: str 1..2000或null` |
| ClarificationAnswer | `{key: str 1..80, kind: choice\|custom\|skip, value: str 1..4000或null}`；choice value为已存option.id，custom value为文本，skip value必须null |
| Failure | `{code: str, message: str, reason: configuration\|timeout\|transport\|invalid_output\|interrupted, retryable: bool}`，仅安全摘要；不是原始模型异常 |

Question动态key不限定为intent/time_limit。每题至少有一种可用回答：有选项/allow_custom/allow_skip之一；allow_skip=true必须有非空default_assumption，false必须null。模型Question数组1..8、key唯一。人工Assumption key必须以 `user:` 起始，模型建议以 `suggested:` 起始；跳过采用 `skip:{question.key}`。模型suggested_assumptions为0..8条，最终assumptions最多32条，每条不得含用户未声明的时间承诺。

Availability和Preferences若均存在，session_minutes≤minutes_per_day；deadline_at仅接受用户明确提交的带时区时间，不从time_limit_text自动推导。GoalValues是用户审阅后的事实，不表示已掌握。

### 3.2 请求

```typescript
type CreateGoal = { prompt: string }; // 1..8000字符
type ConfirmGoal = {
  expected_revision: number;
  values: GoalValues;
  answers: ClarificationAnswer[]; // 必须覆盖所有已存questions，一题一次
  accepted_suggested_assumption_keys: string[]; // 0..8，用户审阅后接受的已存suggested: keys
  user_assumptions: Assumption[]; // 0..16，只能user:前缀
  confirmed: true;
};
```

Confirm时以服务端已存question catalog校验，不接收客户端重写问题/默认假设。choice值须属于该题options；custom须allow_custom；skip须allow_skip。未知key、漏答、重复key、互斥不符为422。`confirmed=false`或缺失为422，不把模型建议自动确认。

accepted_suggested_assumption_keys必须无重复且全部属于已存suggested_assumptions；未知/重复为422，空数组表示不接受任何模型额外假设。确认结果assumptions = 用户选择接受的suggested assumptions + 每个skip的服务端default_assumption（`field=null, reason=该问题reason`）+ user_assumptions，保留来源key可审阅；未接受的模型假设只留在suggested_assumptions供追溯，不当用户事实。values由用户修改后完整提交，其他新增/修正假设应在user_assumptions显式声明；模型建议不能代替用户值。跳过的默认假设若不接受，用户须改为该题允许的具体回答，不能边跳过边隐藏默认假设。确认后B1不提供目标编辑/重新澄清，避免已发布图谱目标漂移；确有后续需求另设明确修订。

### 3.3 响应

```typescript
type GoalRead = {
  id: string;
  learner_id: "local-user"; // 只读，不是请求字段
  raw_prompt: string;
  status: "draft" | "confirmed";
  revision: number;
  clarification_status: "generating" | "ready" | "generation_failed";
  suggested_values: GoalValues | null;
  values: GoalValues | null; // draft为null；confirmed为用户确认值
  questions: ClarificationQuestion[]; // generating/failed为[]
  answers: ClarificationAnswer[]; // 未确认为[]
  accepted_suggested_assumption_keys: string[]; // 未确认为[]
  suggested_assumptions: Assumption[];
  assumptions: Assumption[]; // 未确认展示suggested；确认后加入skip/user
  clarification_failure: Failure | null;
  graph_id: string | null;
  created_at: string;
  updated_at: string;
  confirmed_at: string | null;
};
```

创建先保存draft revision=1/generating，再请求模型。合法问题/建议全部校验后保存ready（通常revision=2）；失败保存generation_failed+Failure（通常revision=2），HTTP错误details带goal_id和current_revision，GET可恢复。缺模型配置也保存draft并报503。前端不假设revision步长，只使用最近GET/写响应值。

retry在事务校验expected_revision、draft且generation_failed，标generating/revision+1；释放事务调用模型；CAS落ready/failed并推进revision。运行期间重复请求409 `operation_in_progress`。服务启动把遗留generating标generation_failed、reason=interrupted并推进revision，只供手动重试，不自动重放。确认只接受draft/ready并事务CAS；更新values/answers/assumptions/status/confirmed_at和revision，一次完成。

## 4. 图谱 Schema、编辑与版本

### 4.1 读取类型

```typescript
type NodeType = "root" | "concept" | "practice" | "assessment";
type Relation = "contains" | "prerequisite" | "related" | "contrast" | "application";
type Position = { x: number; y: number }; // 有限数字，-100000..100000
type NodeContent = {
  label: string; // 1..200
  node_type: NodeType;
  description: string; // 1..4000
  teaching_strategy: string; // 1..4000
  target_weight: number; // int 1..100
};
type NodeRead = NodeContent & {
  id: string;
  node_version: number;
  position: Position | null;
  created_at: string;
};
type EdgeRead = { source: string; target: string; relation: Relation };
type GraphRead = {
  id: string;
  goal_id: string;
  status: "generating" | "generation_failed" | "candidate" | "published";
  revision: number;
  nodes: NodeRead[]; // 2..100；生成/失败为[]
  edges: EdgeRead[]; // 0..500；生成/失败为[]
  generation_failure: Failure | null;
  created_at: string;
  updated_at: string;
  published_at: string | null; // 首次发布时刻，修订不改
  last_revision_reason: string | null;
};
type GraphWriteResult = {
  graph: GraphRead;
  ref_map: Record<string, string>; // 本次全部ref → 服务端Node ID
};
```

生成/失败不得保留半图：nodes/edges空，Failure仅generation_failed时非空。candidate/published时图谱必须完整有效且generation_failure=null。Read数组节点按created_at/ID升序、边按source/target/relation字典序；边无独立ID，用三元组标识，方向按source→target。

### 4.2 完整图谱写入

前端只维护本地未保存状态；保存一次全图，不逐边产生半个服务端状态。非法临时结构允许停留在页面，保存时422、不落库。

```typescript
type NodeInput = NodeContent & {
  ref: string; // 1..80, [A-Za-z][A-Za-z0-9_-]*，本次唯一
  id: string | null; // 已有节点ID；新增null，服务端分配
  position: Position | null;
};
type EdgeInput = { source_ref: string; target_ref: string; relation: Relation };
type GraphInput = { nodes: NodeInput[]; edges: EdgeInput[] };
type EditCandidate = GraphInput & { expected_revision: number };
type PublishGraph = { expected_revision: number; confirmed: true };
type ReviseGraph = GraphInput & {
  expected_revision: number;
  confirmed: true;
  reason: string; // 1..2000，明确本次正式修订说明
};
```

- NodeInput禁止node_version/created_at，不能伪造旧证据版本；ref仅本次请求使用。id非null必须为本graph**当前修订存在**的Node，不得借入其他图或恢复已删除ID。同一已有id出现两次422。遗漏的旧Node表示删除；保留它的边/子节点必须由提交方同时处理，服务端不隐式删子树。
- GraphInput与Model图谱相同数量上限：nodes为2..100、edges为0..500。EdgeInput的两个ref采用NodeInput.ref相同格式/长度限制，且必须引用本次提交中的ref。
- 两种编辑路径互斥：candidate用PUT保存；published用revise完整审阅后`confirmed=true`/reason。published调用PUT为409，模型无发布/修订权。没有静默修改正式图谱，也没有撤销物理删除历史记录。
- 所有写入先Schema → 归属/revision/状态 → 引用/结构 → 事务重新revision CAS/保存完整快照。非法图即使candidate也不保存。发布重新结构校验、只改变状态/发布时间并revision+1。
- 正式修订同graph ID、revision+1、status仍published；保存前后快照、服务端actor=`local-user`/reason/时刻。GET `?revision=N`返回该时刻不可变快照（其status可以是candidate），只读不能拿旧revision覆盖当前。历史Generating/Failed快照也可读用于复查；不提供额外删除/回滚功能。
- candidate保存或published revise逐节点比较 `label/node_type/description/teaching_strategy`：任一实际文本/值改变node_version+1；只改position/target_weight/边关系不升级node_version。新增node_version=1，未变节点保持。不作模型“语义相同”猜测；trim后的内容比较。关系变动用graph_revision快照解释，不全图清空能力证据。
- 删除节点保留NodeVersion/旧图谱/未来题目证据引用。B3只接受当前内容版本证据，不可把graph revision变化等同所有node_version变化。无变化的保存允许revision+1以保持简单CAS，node_version不增。

### 4.3 生成状态机

POST goal/graphs先验证Goal confirmed和Goal expected_revision，再短事务创建唯一Graph generating/revision=1并绑定graph_id；绑定也推进Goal revision。第二次创建409 `graph_already_exists`，details给现存graph_id，前端GET继续。不支持同目标多候选图并行。

释放事务后将已确认Goal/完整回答/透明假设作为模型数据；模型输出完整合法图才分配真实Node ID、node_version=1并保存candidate/revision+1。模型失败或结构非法保存generation_failed/revision+1、返回错误带graph_id；不生成通用fallback、不开发布权限。

POST graph/generate仅generation_failed且expected_revision匹配：标generating/revision+1，释放事务调用，CAS保存candidate或失败/revision+1。generating期间重复为409。重启遗留generating转generation_failed reason=interrupted并revision+1，用户显式重试。候选/正式图不允许“重生成覆盖”，只能编辑/修订。

### 4.4 结构守卫

1. 恰好一个root，至少一个非root（2..100 nodes）。ref/Node ID唯一；边≤500、端点存在于本图；拒绝同三元组重复和任何自环。
2. contains方向父→子，root不可有contains父；每个非root恰好一个contains父，root沿contains可达全部节点。
3. prerequisite方向前置→依赖；contains和prerequisite合并后的**有向图无环**。例如root contains A、A prerequisite root必须拒绝。
4. related/contrast/application不参与DAG检查，但仍检查归属、重复和自环；方向保留请求，不自动补反向边。
5. 无边时节点≥2会触发contains父/可达错误；删除/改挂时同一次完整请求必须保持以上约束。结构失败一次返回全部可确定issues，不写入任何部分。

## 5. 错误结构、409与422定位

API错误统一结构，无FastAPI默认`detail`/原始validation input/stack trace。无匹配路由/方法也经边界规范化（404/405）。HTTP错误、Failure资源状态和retryable语义区分：HTTP失败并不意味着草稿/Graph没有保存。

```typescript
type Issue = {
  path: (string | number)[]; // 例如["body","edges",0,"target_ref"]
  code: string;
  message: string; // 安全简短，不回显完整输入
  node_ids: string[]; // 结构定位：已有ID或本次临时ref
  edge_indexes: number[]; // body路径指提交edges；graph路径指当前GraphRead.edges
};
type ErrorDetails = {
  resource_type: "goal" | "graph" | null;
  resource_id: string | null;
  expected_revision: number | null;
  current_revision: number | null;
  failure_reason: "configuration" | "timeout" | "transport" | "invalid_output" | "interrupted" | null;
  issues: Issue[];
};
type ApiError = {
  code: string;
  message: string;
  details: ErrorDetails;
  retryable: boolean;
};
```

Details所有键始终存在，未适用null/[]；资源生成失败时resource_id/current_revision必填，创建图谱失败指Graph不是Goal。一次请求没有有效资源时resource_type/resource_id null。校验优先顺序：JSON/Schema→资源/归属→expected_revision（过期统一409）→状态→领域结构→短事务重新CAS；防止第一次检查后并发写入覆盖。模型回传结构非法是生成错误502 `generation_failed` reason=invalid_output，不是把模型缺陷归为用户输入422。

| HTTP | code | retryable与处理 |
| --- | --- | --- |
| 400 | `invalid_json` | false；全文JSON/重复键/非法数字，修正后再发 |
| 403 | `origin_not_allowed` / `host_not_allowed` | false；修正本机入口，不开启公网绕过 |
| 404 | `resource_not_found` / `route_not_found` | false |
| 405 | `method_not_allowed` | false |
| 409 | `revision_conflict` | false；GET最新后人工合并/再次确认，不能盲重试 |
| 409 | `invalid_state` | false；GET资源选择正确操作 |
| 409 | `graph_already_exists` | false；resource_id指已有Graph，GET继续 |
| 409 | `operation_in_progress` | false；当前请求正在执行，稍后GET，不发重复生成 |
| 413/415 | `payload_too_large` / `unsupported_media_type` | false |
| 422 | `validation_failed` / `graph_invalid` | false；逐项issues修正 |
| 502 | `generation_failed` | true；reason=transport/invalid_output，先GET失败资产，再显式retry |
| 504 | `generation_failed` | true；reason=timeout，处理同上 |
| 503 | `model_not_configured` | false；reason=configuration，配置修正后资源可显式retry |
| 503 | `storage_busy` | true；未提交此次写；GET最新后显式重试，非生成业务失败 |
| 500 | `internal_error` | false；安全摘要、无原始堆栈，GET确认事实后报告 |

`retryable=true`仅表示相同业务可再次尝试，不表示自动HTTP重放或完成保证。配置修复后也可手动重试generation_failed，不能因Failure.retryable=false永久锁住资产。取消/网络断开不能返回错误时，GET和启动中断标记用于查事实，不建自动恢复。

生成取消时尽力将已保存资产标generation_failed/interrupted并推进revision；取消继续传播。若最终结果/失败状态因storage_busy无法提交，503 details仍给resource_id和可查询revision，资产可能仍generating；不伪称成功，不重复模型调用。服务重启时按本契约转为中断失败，再由用户显式重试。尚未创建资源的storage_busy才使用null资源字段。

Issue code固定起点：Schema `required/type/extra/constraint/unknown_question/duplicate_question/invalid_answer`；图谱 `root_count/min_nodes/duplicate_node/foreign_node/unknown_endpoint/duplicate_edge/self_loop/root_has_parent/contains_parent_count/unreachable/structural_cycle`。前端按path/node_ids/edge_indexes高亮，其他未知issue仍显示message。整图写请求的path以body起始，已有ID和临时ref区分由本次NodeInput映射得知，edge_indexes指提交数组。publish重新校验已存图时path以graph起始，node_ids是真实ID、edge_indexes指当前GraphRead.edges的规范排序下标。结构错误不能仅给“发布失败”。

409示例（详情所有字段齐全）：

```json
{
  "code": "revision_conflict",
  "message": "图谱已更新，请读取最新修订后重新确认。",
  "details": {
    "resource_type": "graph", "resource_id": "31fdc0ab-3c53-41cb-a95e-97b19ea2d1ad",
    "expected_revision": 2, "current_revision": 3,
    "failure_reason": null, "issues": []
  },
  "retryable": false
}
```

422联合结构环示例（节点为本次refs，edges下标指请求）：

```json
{
  "code": "graph_invalid", "message": "图谱结构不满足发布条件。",
  "details": {
    "resource_type": "graph", "resource_id": "31fdc0ab-3c53-41cb-a95e-97b19ea2d1ad",
    "expected_revision": 2, "current_revision": 2, "failure_reason": null,
    "issues": [{
      "path": ["body", "edges"], "code": "structural_cycle",
      "message": "contains 与 prerequisite 组成有向环。",
      "node_ids": ["root", "loop"], "edge_indexes": [0, 1]
    }]
  },
  "retryable": false
}
```

## 6. 前端可直接复现的写入样例

确认动态题（以服务端确实返回该Question为前提）：

```json
{
  "expected_revision": 2,
  "values": {
    "title": "Python CSV 数据处理", "intent": "项目",
    "prior_knowledge": null,
    "desired_outcome": "能说明读取、逐行转换和写出的步骤",
    "time_limit_text": "希望两周入门", "deadline_at": null,
    "target_weight": 80,
    "availability": {"minutes_per_day": 30, "days_per_week": 5},
    "preferences": {"session_minutes": 30, "preferred_action_types": []}
  },
  "answers": [{"key": "loop_background", "kind": "skip", "value": null}],
  "accepted_suggested_assumption_keys": [], "user_assumptions": [], "confirmed": true
}
```

`loop_background`若allow_skip=true/default_assumption="按需要补充循环基础设计路线"，响应assumptions必须加入key=`skip:loop_background`/该文本，前端审阅和确认后均展示；不能把skip显示成用户回答“会循环”。更多Question须全部加入answers，不能只传示例一题。

候选新增节点/关系完整替换（两个已有ID必须在本图当前修订）：

```json
{
  "expected_revision": 2,
  "nodes": [
    {
      "ref": "root", "id": "c358bfe9-d3aa-41bc-89ba-e2cb15a5ea4d",
      "label": "CSV 数据处理", "node_type": "root",
      "description": "读取、转换、写出", "teaching_strategy": "说明完整流程",
      "target_weight": 80, "position": null
    },
    {
      "ref": "loop", "id": "0c1bf6e0-a462-4b8f-9ffb-4baa6e00a713",
      "label": "循环", "node_type": "concept",
      "description": "逐项处理", "teaching_strategy": "用逐行处理解释边界",
      "target_weight": 70, "position": {"x": 100, "y": 200}
    },
    {
      "ref": "csv", "id": null,
      "label": "CSV 读取", "node_type": "concept",
      "description": "表头与数据行", "teaching_strategy": "先预测读取结果再解释",
      "target_weight": 90, "position": null
    }
  ],
  "edges": [
    {"source_ref": "root", "target_ref": "loop", "relation": "contains"},
    {"source_ref": "root", "target_ref": "csv", "relation": "contains"},
    {"source_ref": "loop", "target_ref": "csv", "relation": "prerequisite"}
  ]
}
```

成功ref_map含root/loop原ID和csv新ID；使用返回graph.revision发布 `{"expected_revision":3,"confirmed":true}`（3仅示例，以实际返回为准）。正式修改以同样完整nodes/edges再加confirmed=true/reason送revise，不送PUT。

## 7. 结构化模型请求协议

业务adapter组装system（任务规则+JSON Schema）/user（明确标记的输入数据），调用现有 `ModelProvider.chat(messages, tools=[])`。不改Runner职责，不假设供应商已支持response_format/generate_json。教学B2仍走Loop/Runner，非这个adapter。

### 7.1 输出形状

澄清输出仅 `{suggested_values: GoalValues, questions: ClarificationQuestion[], suggested_assumptions: Assumption[]}`，Schema字段/限制同第3节，不允许id/status/answers/confirmed。问题动态key及默认假设必校验。

图谱输出仅 `{nodes: ModelNode[], edges: EdgeInput[]}`；ModelNode为NodeContent加ref，不得含id/node_version/position/created_at。临时refs唯一，edges必须引用refs；节点2..100、边≤500，并做第4.4节完整结构校验。服务端校验后赋ID/初始版本、position=null。模型不决定数据库状态/学习者/发布。

### 7.2 严格解析守卫

1. 仅正常finish_reason=`stop`、无tool_calls、非空content；length/content_filter/空回答/意外工具都失败，不执行任何工具。
2. content UTF-8编码≤256 KiB、JSON嵌套深度≤32；解析**整个**文本（允许JSON首尾空白），必须唯一顶层object；拒绝重复键、NaN/Infinity、代码围栏、前后说明、截取/自动补齐、字符串化内嵌JSON。
3. Pydantic strict/extra forbid与范围校验，随后领域校验（questions一致、refs/联合DAG等）；全部通过才短事务保存ready/candidate。模型输出private/任意额外字段同样拒绝。
4. 请求限时复用现有Settings.request_timeout_seconds（默认60秒），另有connect/read预算；不在SQLite写事务中await。首版无自动模型重试；失败reason稳定映射、原始异常脱敏。
5. Goal prompt/回答/节点描述仅作为数据，不提高权限、不能注册工具。不给模型发布或修改正式图谱的工具。供应商JSON Schema支持若后续增加须单独适配/测试，不能降低全文验证。

## 8. 实施验证与交接要求

此契约本轮只能做文档验证，不代表API/模型已通过。B1开发需：

- 服务端Pydantic生成OpenAPI、离线导出Schema；前端TS与实际Schema核对。HTTP测试固定模型桩，不依赖`.env`；错误统一处理/422不回显输入、Host/Origin/413/415、资源归属均有断言。
- 临时DB测试创建/ready失败/retry/确认/生成/编辑/发布/正式修订/历史读取，重启中断和CAS竞争；非法结构不写；新ID映射/版本变化可查；所有不在本契约的暗箱fallback禁止。
- Web使用样例/mock先行：动态题选项/自定义/skip、假设可见、等待失败可GET、409提示刷新合并、422节点边高亮、发布/修订确认，刷新继续。
- 固定模型桩必须覆盖非JSON/重复键/截断/非法refs/联合环等，不能仅测最终回答。全量阶段A回归不得倒退。
- 真实入口在计划中约定 `scripts/verify_learning_model.py --stage b1`，待B1实现；配置缺失明确SKIPPED/非零退出，记录模型ID/日期/结果与未验证项，桩不冒充真实效果。前后端任何契约变更先通知周经理/阿岚、更新本文件及测试。
