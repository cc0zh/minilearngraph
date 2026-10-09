import type { Answer, Assumption, GoalRead, GoalValues, GraphInput, GraphRead, Question } from './types';

export function loadDraft<T>(key: string): T | null {
  try { const raw = sessionStorage.getItem(key); return raw ? JSON.parse(raw) as T : null; }
  catch { return null; }
}
export function keepDraft(key: string, value: unknown) {
  try { sessionStorage.setItem(key, JSON.stringify(value)); } catch { /* Forms still work if storage is unavailable. */ }
}
export function forgetDraft(key: string) {
  try { sessionStorage.removeItem(key); } catch { /* No persistent storage available. */ }
}

export type GoalDraft = {
  baseRevision: number; values: GoalValues; answers: Answer[]; accepted: string[]; assumptions: Assumption[];
};
export function goalDraft(goal: GoalRead): GoalDraft {
  return { baseRevision: goal.revision, values: structuredClone(goal.suggested_values!), answers: [], accepted: [], assumptions: [] };
}
export function validAnswer(question: Question, answer?: Answer): boolean {
  if (!answer || answer.key !== question.key) return false;
  if (answer.kind === 'choice') return question.options.some(option => option.id === answer.value);
  if (answer.kind === 'skip') return question.allow_skip && answer.value === null;
  return answer.kind === 'custom' && question.allow_custom && !!answer.value?.trim();
}
export type GraphDraft = { baseRevision: number; input: GraphInput; reason: string };
export function graphDraft(graph: GraphRead): GraphDraft {
  const refs = new Map(graph.nodes.map((node, i) => [node.id, `n${i + 1}`]));
  return {
    baseRevision: graph.revision, reason: '',
    input: {
      nodes: graph.nodes.map(node => ({
        ref: refs.get(node.id)!, id: node.id, label: node.label, node_type: node.node_type,
        description: node.description, teaching_strategy: node.teaching_strategy,
        target_weight: node.target_weight, position: node.position,
      })),
      edges: graph.edges.map(edge => ({ source_ref: refs.get(edge.source)!, target_ref: refs.get(edge.target)!, relation: edge.relation })),
    },
  };
}
