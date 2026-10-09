import type { GoalRead, GoalValues, GraphRead } from './types';

export const goalId = 'c94ad071-aa55-4afd-99c1-24d08138ec20';
export const graphId = '31fdc0ab-3c53-41cb-a95e-97b19ea2d1ad';
export const values: GoalValues = {
  title: 'Python CSV 数据处理', intent: '项目', prior_knowledge: null,
  desired_outcome: '能说明读取、逐行转换和写出的步骤', time_limit_text: null,
  deadline_at: null, target_weight: 80, availability: null, preferences: null,
};
const now = '2026-10-09T04:00:00Z';
export function readyGoal(): GoalRead {
  return {
    id: goalId, learner_id: 'local-user', raw_prompt: '学习 Python，最终能独立处理 CSV 数据',
    status: 'draft', revision: 2, clarification_status: 'ready', suggested_values: structuredClone(values), values: null,
    questions: [
      { key: 'loop_background', prompt: '你能独立写循环吗？', reason: '决定是否补充循环基础', graph_impact: 'nodes', options: [{ id: 'yes', label: '可以独立完成' }], allow_custom: true, allow_skip: true, default_assumption: '按需要补充循环基础设计路线' },
      { key: 'csv_tooling', prompt: '你使用什么工具？', reason: '影响教学示例', graph_impact: 'teaching', options: [], allow_custom: true, allow_skip: false, default_assumption: null },
      { key: 'output_format', prompt: '目标输出是什么？', reason: '决定学习范围', graph_impact: 'scope', options: [{ id: 'csv', label: '清理后的 CSV 文件' }, { id: 'report', label: '分析报告' }], allow_custom: false, allow_skip: false, default_assumption: null },
    ],
    answers: [], accepted_suggested_assumption_keys: [],
    suggested_assumptions: [
      { key: 'suggested:headers', field: 'desired_outcome', value: '包含表头处理', reason: 'CSV 读取通常需要区分表头' },
      { key: 'suggested:charts', field: null, value: '暂不包含绘图', reason: '先聚焦数据转换' },
    ],
    assumptions: [], clarification_failure: null, graph_id: null,
    created_at: now, updated_at: now, confirmed_at: null,
  };
}
export function confirmedGoal(): GoalRead {
  return { ...readyGoal(), status: 'confirmed', revision: 3, values: structuredClone(values), confirmed_at: now,
    answers: [{ key: 'loop_background', kind: 'skip', value: null }, { key: 'csv_tooling', kind: 'custom', value: 'VS Code' }, { key: 'output_format', kind: 'choice', value: 'csv' }],
    assumptions: [{ key: 'skip:loop_background', field: null, value: '按需要补充循环基础设计路线', reason: '决定是否补充循环基础' }],
  };
}
export function candidateGraph(): GraphRead {
  const ids = ['c358bfe9-d3aa-41bc-89ba-e2cb15a5ea4d', '0c1bf6e0-a462-4b8f-9ffb-4baa6e00a713', 'e52a2bf7-ee48-4d8d-9035-717ce9a74e54'];
  return { id: graphId, goal_id: goalId, status: 'candidate', revision: 2,
    nodes: ids.map((id, index) => ({ id, label: ['CSV 数据处理', '循环', 'CSV 读取'][index], node_type: index === 0 ? 'root' : 'concept', description: '理解并说明处理步骤', teaching_strategy: '先预测结果再解释', target_weight: 80, node_version: 1, position: null, created_at: now })),
    edges: [{ source: ids[0], target: ids[1], relation: 'contains' }, { source: ids[0], target: ids[2], relation: 'contains' }, { source: ids[1], target: ids[2], relation: 'prerequisite' }],
    generation_failure: null, created_at: now, updated_at: now, published_at: null, last_revision_reason: null,
  };
}
