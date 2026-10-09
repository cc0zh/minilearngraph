import type { ApiErrorBody, ConfirmGoal, GoalRead, GraphInput, GraphRead, GraphWriteResult } from './types';

export class ApiError extends Error {
  constructor(public status: number, public body: ApiErrorBody) { super(body.message); }
}

const base = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1';

export async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, {
      method, headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      signal: AbortSignal.timeout(120_000), credentials: 'omit',
    });
  } catch {
    throw new Error('连接失败或等待超时；结果未知。请先读取已保存资产，不要重复创建。');
  }
  if (!response.ok) {
    let payload: ApiErrorBody;
    try { payload = await response.json() as ApiErrorBody; }
    catch { throw new Error(`服务返回 HTTP ${response.status}；请读取资产确认结果。`); }
    if (!payload.details || !Array.isArray(payload.details.issues)) {
      throw new Error(`服务错误格式不符合 B1 契约（HTTP ${response.status}）。`);
    }
    throw new ApiError(response.status, payload);
  }
  return response.json() as Promise<T>;
}

export const api = {
  goals: () => request<{ items: GoalRead[] }>('/goals'),
  goal: (id: string) => request<GoalRead>(`/goals/${id}`),
  createGoal: (prompt: string) => request<GoalRead>('/goals', 'POST', { prompt }),
  clarify: (goal: GoalRead) => request<GoalRead>(`/goals/${goal.id}/clarify`, 'POST', { expected_revision: goal.revision }),
  confirm: (id: string, body: ConfirmGoal) => request<GoalRead>(`/goals/${id}/confirm`, 'POST', body),
  graphs: (goalId: string) => request<{ items: GraphRead[] }>(`/graphs?goal_id=${encodeURIComponent(goalId)}`),
  graph: (id: string, revision?: number) => request<GraphRead>(`/graphs/${id}${revision === undefined ? '' : `?revision=${revision}`}`),
  createGraph: (goal: GoalRead) => request<GraphRead>(`/goals/${goal.id}/graphs`, 'POST', { expected_revision: goal.revision }),
  generate: (graph: GraphRead) => request<GraphRead>(`/graphs/${graph.id}/generate`, 'POST', { expected_revision: graph.revision }),
  save: (graph: GraphRead, input: GraphInput, reason?: string) => request<GraphWriteResult>(
    `/graphs/${graph.id}${graph.status === 'published' ? '/revise' : ''}`,
    graph.status === 'published' ? 'POST' : 'PUT',
    { ...input, expected_revision: graph.revision, ...(graph.status === 'published' ? { confirmed: true, reason } : {}) },
  ),
  publish: (graph: GraphRead) => request<GraphRead>(`/graphs/${graph.id}/publish`, 'POST', { expected_revision: graph.revision, confirmed: true }),
};
