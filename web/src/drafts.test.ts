import { describe, it, expect, beforeEach } from 'vitest';
import { candidateGraph, readyGoal } from './testFixtures';
import { graphDraft, keepDraft, loadDraft, forgetDraft, validAnswer } from './drafts';

beforeEach(() => sessionStorage.clear());
describe('B1 request drafts', () => {
  it('guards dynamic question permissions and option IDs', () => {
    const [loop, custom, choice] = readyGoal().questions;
    expect(validAnswer(loop, { key: loop.key, kind: 'skip', value: null })).toBe(true);
    expect(validAnswer(loop, { key: loop.key, kind: 'skip', value: 'hidden assumption' })).toBe(false);
    expect(validAnswer(custom, { key: custom.key, kind: 'skip', value: null })).toBe(false);
    expect(validAnswer(custom, { key: custom.key, kind: 'custom', value: '  ' })).toBe(false);
    expect(validAnswer(custom, { key: custom.key, kind: 'choice', value: 'invented' })).toBe(false);
    expect(validAnswer(choice, { key: choice.key, kind: 'custom', value: 'custom' })).toBe(false);
    expect(validAnswer(choice, { key: choice.key, kind: 'choice', value: 'csv' })).toBe(true);
  });
  it('maps graph IDs to same-graph refs without sending read-only fields', () => {
    const graph = candidateGraph(); const draft = graphDraft(graph);
    expect(draft.baseRevision).toBe(graph.revision);
    expect(draft.input.nodes[0]).toEqual({ ref: 'n1', id: graph.nodes[0].id, label: 'CSV 数据处理', node_type: 'root', description: '理解并说明处理步骤', teaching_strategy: '先预测结果再解释', target_weight: 80, position: null });
    expect(draft.input.edges[2]).toEqual({ source_ref: 'n2', target_ref: 'n3', relation: 'prerequisite' });
    for (const node of draft.input.nodes) expect(node).not.toHaveProperty('node_version');
  });
  it('preserves local drafts on refresh and handles invalid JSON safely', () => {
    keepDraft('draft', { revision: 7, input: 'not saved' });
    expect(loadDraft('draft')).toEqual({ revision: 7, input: 'not saved' });
    forgetDraft('draft'); expect(loadDraft('draft')).toBe(null);
    sessionStorage.setItem('draft', '{'); expect(loadDraft('draft')).toBe(null);
  });
});
