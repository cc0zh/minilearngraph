export type ActionType = 'learn' | 'practice' | 'review' | 'assessment';
export type GoalValues = {
  title: string; intent: string | null; prior_knowledge: string | null;
  desired_outcome: string; time_limit_text: string | null; deadline_at: string | null;
  target_weight: number;
  availability: { minutes_per_day: number; days_per_week: number } | null;
  preferences: { session_minutes: number; preferred_action_types: ActionType[] } | null;
};
export type Assumption = { key: string; field: keyof GoalValues | null; value: string | null; reason: string };
export type Question = {
  key: string; prompt: string; options: { id: string; label: string }[]; reason: string;
  graph_impact: 'scope' | 'nodes' | 'relations' | 'teaching' | 'schedule';
  allow_custom: boolean; allow_skip: boolean; default_assumption: string | null;
};
export type Answer = { key: string; kind: 'choice' | 'custom' | 'skip'; value: string | null };
export type FailureReason = 'configuration' | 'timeout' | 'transport' | 'invalid_output' | 'interrupted';
export type Failure = { code: string; message: string; reason: FailureReason; retryable: boolean };
export type GoalRead = {
  id: string; learner_id: 'local-user'; raw_prompt: string; status: 'draft' | 'confirmed'; revision: number;
  clarification_status: 'generating' | 'ready' | 'generation_failed';
  suggested_values: GoalValues | null; values: GoalValues | null; questions: Question[];
  answers: Answer[]; accepted_suggested_assumption_keys: string[];
  suggested_assumptions: Assumption[]; assumptions: Assumption[]; clarification_failure: Failure | null;
  graph_id: string | null; created_at: string; updated_at: string; confirmed_at: string | null;
};
export type ConfirmGoal = {
  expected_revision: number; values: GoalValues; answers: Answer[];
  accepted_suggested_assumption_keys: string[]; user_assumptions: Assumption[]; confirmed: true;
};
export type NodeType = 'root' | 'concept' | 'practice' | 'assessment';
export type Relation = 'contains' | 'prerequisite' | 'related' | 'contrast' | 'application';
export type Position = { x: number; y: number };
export type NodeContent = {
  label: string; node_type: NodeType; description: string; teaching_strategy: string; target_weight: number;
};
export type NodeRead = NodeContent & { id: string; node_version: number; position: Position | null; created_at: string };
export type EdgeRead = { source: string; target: string; relation: Relation };
export type GraphRead = {
  id: string; goal_id: string; status: 'generating' | 'generation_failed' | 'candidate' | 'published';
  revision: number; nodes: NodeRead[]; edges: EdgeRead[]; generation_failure: Failure | null;
  created_at: string; updated_at: string; published_at: string | null; last_revision_reason: string | null;
};
export type NodeInput = NodeContent & { ref: string; id: string | null; position: Position | null };
export type EdgeInput = { source_ref: string; target_ref: string; relation: Relation };
export type GraphInput = { nodes: NodeInput[]; edges: EdgeInput[] };
export type GraphWriteResult = { graph: GraphRead; ref_map: Record<string, string> };
export type Issue = { path: (string | number)[]; code: string; message: string; node_ids: string[]; edge_indexes: number[] };
export type ErrorDetails = {
  resource_type: 'goal' | 'graph' | null; resource_id: string | null;
  expected_revision: number | null; current_revision: number | null;
  failure_reason: FailureReason | null; issues: Issue[];
};
export type ApiErrorBody = { code: string; message: string; details: ErrorDetails; retryable: boolean };
