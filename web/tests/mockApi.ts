import { expect, type Page, type Route } from '@playwright/test';
import { candidateGraph, confirmedGoal, graphId, readyGoal } from '../src/testFixtures';
import type { ApiErrorBody, ConfirmGoal, GoalRead, GraphInput, GraphRead, Issue } from '../src/types';

type Write = { path: string; method: string; body: Record<string, unknown> };
export class MockApi {
  goal: GoalRead | null = null;
  graph: GraphRead | null = null;
  history = new Map<number, GraphRead>();
  writes: Write[] = [];
  createMode: 'ready' | 'failed' | 'lost' = 'ready';
  graphMode: 'ready' | 'failed' = 'ready';
  conflictNext = false;
  invalidNext = false;
  lostConfirm = false;
  lostGraph = false;
  conflictGoalNext = false;
  failReads = false;
  failRecovery = false;
  gets: string[] = [];

  constructor(public page: Page) {}
  async install() { await this.page.route('http://127.0.0.1:8000/api/v1/**', route => this.handle(route)); }
  seedGraph() { this.goal = { ...confirmedGoal(), revision: 4, graph_id: graphId }; this.graph = candidateGraph(); this.snapshot(); }
  snapshot() { if (this.graph) this.history.set(this.graph.revision, structuredClone(this.graph)); }
  error(status: number, code: string, resource: 'goal' | 'graph', issues: Issue[] = []): ApiErrorBody {
    return { code, message: status === 422 ? '图谱结构不满足发布条件。' : status === 409 ? '修订冲突，请合并最新图谱。' : '生成失败；资产已保存。', retryable: status === 502,
      details: { resource_type: resource, resource_id: resource === 'goal' ? this.goal!.id : this.graph!.id,
        expected_revision: null, current_revision: resource === 'goal' ? this.goal!.revision : this.graph!.revision, failure_reason: status >= 500 ? 'invalid_output' : null, issues } };
  }
  async handle(route: Route) {
    const req = route.request(); const url = new URL(req.url()); const path = url.pathname.replace('/api/v1', '');
    const method = req.method();
    const reply = (body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (method === 'GET') {
      this.gets.push(path);
      if (this.failReads) return route.abort('failed');
      if (path === '/goals') return reply({ items: this.goal ? [this.goal] : [] });
      if (path.startsWith('/goals/')) return reply(this.goal);
      if (path === '/graphs') return reply({ items: this.graph ? [this.graph] : [] });
      if (path.startsWith('/graphs/')) return reply(url.searchParams.has('revision') ? this.history.get(Number(url.searchParams.get('revision'))) : this.graph);
    }
    const body = req.postDataJSON() as Record<string, unknown>;
    expect(req.headers()['content-type']).toBe('application/json');
    expect(body).not.toHaveProperty('learner_id'); expect(body).not.toHaveProperty('actor');
    this.writes.push({ path, method, body });
    if (path === '/goals' && method === 'POST') {
      expect(Object.keys(body)).toEqual(['prompt']); this.goal = readyGoal(); this.goal.raw_prompt = String(body.prompt);
      if (this.createMode === 'failed') { this.goal = { ...this.goal, clarification_status: 'generation_failed', suggested_values: null, questions: [], suggested_assumptions: [], clarification_failure: { code: 'model_not_configured', message: '模型未配置', reason: 'configuration', retryable: false } }; return reply(this.error(503, 'model_not_configured', 'goal'), 503); }
      if (this.createMode === 'lost') { this.failReads = this.failRecovery; return route.abort('failed'); }
      return reply(this.goal, 201);
    }
    if (path.endsWith('/clarify')) { this.goal = { ...readyGoal(), revision: this.goal!.revision + 2 }; return reply(this.goal); }
    if (path.endsWith('/confirm')) {
      if (this.conflictGoalNext) { this.conflictGoalNext = false; this.goal!.revision++; return reply(this.error(409, 'revision_conflict', 'goal'), 409); }
      const confirm = body as unknown as ConfirmGoal;
      expect(confirm.expected_revision).toBe(this.goal!.revision); expect(confirm.confirmed).toBe(true);
      expect(confirm.answers.map(a => a.key)).toEqual(this.goal!.questions.map(q => q.key));
      this.goal = { ...this.goal!, status: 'confirmed', revision: this.goal!.revision + 1, values: confirm.values, answers: confirm.answers,
        accepted_suggested_assumption_keys: confirm.accepted_suggested_assumption_keys,
        assumptions: [...this.goal!.suggested_assumptions.filter(a => confirm.accepted_suggested_assumption_keys.includes(a.key)), ...this.goal!.questions.filter(q => confirm.answers.some(a => a.key === q.key && a.kind === 'skip')).map(q => ({ key: `skip:${q.key}`, field: null, value: q.default_assumption, reason: q.reason })), ...confirm.user_assumptions], confirmed_at: '2026-10-09T04:01:00Z' };
      if (this.lostConfirm) return route.abort('failed'); return reply(this.goal);
    }
    if (path.startsWith('/goals/') && path.endsWith('/graphs')) {
      expect(body.expected_revision).toBe(this.goal!.revision);
      this.graph = candidateGraph(); this.goal = { ...this.goal!, revision: this.goal!.revision + 1, graph_id: this.graph.id };
      if (this.graphMode === 'failed') { this.graph = { ...this.graph, status: 'generation_failed', nodes: [], edges: [], generation_failure: { code: 'generation_failed', message: '图谱生成失败', reason: 'invalid_output', retryable: true } }; this.snapshot(); return reply(this.error(502, 'generation_failed', 'graph'), 502); }
      this.snapshot(); if (this.lostGraph) return route.abort('failed'); return reply(this.graph, 201);
    }
    if (path.endsWith('/generate')) { this.graph = { ...candidateGraph(), revision: this.graph!.revision + 2 }; this.snapshot(); return reply(this.graph); }
    if (this.conflictNext) {
      this.conflictNext = false; this.graph!.revision += 1; this.graph!.nodes[1].description = '其他页面已补充循环边界'; this.snapshot();
      return reply(this.error(409, 'revision_conflict', 'graph'), 409);
    }
    if (this.invalidNext) {
      this.invalidNext = false;
      return reply(this.error(422, 'graph_invalid', 'graph', [{ path: ['body', 'edges'], code: 'structural_cycle', message: 'contains 与 prerequisite 组成有向环。', node_ids: ['n1', 'n2'], edge_indexes: [0, 3] }]), 422);
    }
    expect(body.expected_revision).toBe(this.graph!.revision);
    if (path.endsWith('/publish')) {
      expect(body.confirmed).toBe(true); this.graph = { ...this.graph!, status: 'published', revision: this.graph!.revision + 1, published_at: '2026-10-09T04:01:00Z' }; this.snapshot(); return reply(this.graph);
    }
    if (method === 'PUT' || path.endsWith('/revise')) {
      if (path.endsWith('/revise')) { expect(body.confirmed).toBe(true); expect(String(body.reason).trim().length).toBeGreaterThan(0); }
      const input = body as unknown as GraphInput;
      const refs: Record<string, string> = {};
      const nodes = input.nodes.map(node => { const id = node.id ?? crypto.randomUUID(); refs[node.ref] = id;
        expect(node).not.toHaveProperty('node_version');
        return { id, label: node.label, node_type: node.node_type, description: node.description, teaching_strategy: node.teaching_strategy, target_weight: node.target_weight, position: node.position, node_version: 1, created_at: '2026-10-09T04:00:00Z' }; });
      this.graph = { ...this.graph!, revision: this.graph!.revision + 1, nodes, edges: input.edges.map(edge => ({ source: refs[edge.source_ref], target: refs[edge.target_ref], relation: edge.relation })), last_revision_reason: path.endsWith('/revise') ? String(body.reason) : null };
      this.snapshot(); return reply({ graph: this.graph, ref_map: refs });
    }
    throw new Error(`Unexpected mock request ${method} ${path}`);
  }
}
