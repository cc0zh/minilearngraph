import { useEffect, useState } from 'react';
import type { ActionType, Answer, Assumption, ConfirmGoal, GoalRead, GoalValues, Issue } from './types';
import { forgetDraft, goalDraft, keepDraft, loadDraft, validAnswer, type GoalDraft } from './drafts';

const valueLabels: Record<keyof GoalValues, string> = {
  title: '目标标题', intent: '用途', prior_knowledge: '已有基础', desired_outcome: '预期成果',
  time_limit_text: '时间描述', deadline_at: '明确截止时间（带时区）', target_weight: '目标重要性',
  availability: '可用时间', preferences: '学习偏好',
};
const actions: ActionType[] = ['learn', 'practice', 'review', 'assessment'];
const actionLabels = { learn: '学习', practice: '练习', review: '复习', assessment: '测评' };

function ValuesForm({ values, change, issues }: { values: GoalValues; change: (value: GoalValues) => void; issues: Issue[] }) {
  const invalid = (field: keyof GoalValues) => issues.some(issue => issue.path[1] === 'values' && issue.path[2] === field);
  const textFields = ['title', 'intent', 'prior_knowledge', 'desired_outcome', 'time_limit_text', 'deadline_at'] as const;
  const max = { title: 200, intent: 100, prior_knowledge: 4000, desired_outcome: 4000, time_limit_text: 1000, deadline_at: 80 };
  return <fieldset><legend>审阅并修改目标事实</legend>
    <p className="muted">模型建议不等于你的承诺。留空的可选字段以 null 保存；不会从时间描述推断截止日期。</p>
    <div className="form-grid">{textFields.map(field => <label key={field} className={invalid(field) ? 'invalid' : undefined}>{valueLabels[field]}
      <textarea aria-label={valueLabels[field]} rows={field === 'desired_outcome' || field === 'prior_knowledge' ? 3 : 1}
        required={field === 'title' || field === 'desired_outcome'} maxLength={max[field]} aria-invalid={invalid(field)}
        value={values[field] ?? ''} onChange={event => change({ ...values, [field]: event.target.value || (field === 'title' || field === 'desired_outcome' ? '' : null) })} />
      {field === 'deadline_at' && <small>例如 2026-11-01T18:00:00+08:00；仅填写你明确选择的时间。</small>}
    </label>)}</div>
    <label className={invalid('target_weight') ? 'invalid' : undefined}>目标重要性<input type="number" min={1} max={100} required aria-invalid={invalid('target_weight')} value={values.target_weight} onChange={e => change({ ...values, target_weight: Number(e.target.value) })} /></label>
    <label className="check"><input type="checkbox" checked={values.availability !== null} onChange={e => change({ ...values, availability: e.target.checked ? { minutes_per_day: 30, days_per_week: 5 } : null })} />我明确提供可用时间</label>
    {values.availability && <div className={`form-grid ${invalid('availability') ? 'invalid' : ''}`}>
      <label>每天可用分钟<input type="number" min={1} max={1440} required value={values.availability.minutes_per_day} onChange={e => change({ ...values, availability: { ...values.availability!, minutes_per_day: Number(e.target.value) } })} /></label>
      <label>每周可用天数<input type="number" min={1} max={7} required value={values.availability.days_per_week} onChange={e => change({ ...values, availability: { ...values.availability!, days_per_week: Number(e.target.value) } })} /></label>
    </div>}
    <label className="check"><input type="checkbox" checked={values.preferences !== null} onChange={e => change({ ...values, preferences: e.target.checked ? { session_minutes: Math.min(30, values.availability?.minutes_per_day ?? 30), preferred_action_types: [] } : null })} />我明确提供学习偏好</label>
    {values.preferences && <div className={invalid('preferences') ? 'invalid' : undefined}>
      <label>每次学习分钟<input type="number" min={1} max={values.availability?.minutes_per_day ?? 1440} required value={values.preferences.session_minutes} onChange={e => change({ ...values, preferences: { ...values.preferences!, session_minutes: Number(e.target.value) } })} /></label>
      <div className="row">{actions.map(action => <label className="check" key={action}><input type="checkbox" checked={values.preferences!.preferred_action_types.includes(action)} onChange={e => change({ ...values, preferences: { ...values.preferences!, preferred_action_types: e.target.checked ? [...values.preferences!.preferred_action_types, action] : values.preferences!.preferred_action_types.filter(item => item !== action) } })} />偏好{actionLabels[action]}</label>)}</div>
    </div>}
  </fieldset>;
}

export function Assumptions({ items }: { items: Assumption[] }) {
  return items.length ? <ul className="assumptions">{items.map(item => <li key={item.key}>
    <strong>{item.value ?? '未设定'}</strong> <code>{item.key}</code>
    {item.field && <span> · {valueLabels[item.field]}</span>}<p>依据：{item.reason}</p>
  </li>)}</ul> : <p className="muted">没有采用额外假设。</p>;
}

export function GoalSummary({ goal }: { goal: GoalRead }) {
  return <section className="panel"><h2>已确认目标 · r{goal.revision}</h2>
    <dl className="summary">{goal.values && Object.entries(goal.values).map(([key, value]) => <div key={key}><dt>{valueLabels[key as keyof GoalValues]}</dt><dd>{typeof value === 'object' && value !== null ? JSON.stringify(value) : String(value ?? '未设定')}</dd></div>)}</dl>
    <h3>完整回答与理由</h3>{goal.questions.map(question => {
      const answer = goal.answers.find(item => item.key === question.key);
      return <div key={question.key}><strong>{question.prompt}</strong><p>{answer?.kind === 'skip' ? `跳过；采用：${question.default_assumption}` : answer?.kind === 'choice' ? question.options.find(option => option.id === answer.value)?.label ?? answer.value : answer?.value}</p><small>理由：{question.reason} · 影响：{question.graph_impact}</small></div>;
    })}
    <h3>已采用的透明假设</h3><Assumptions items={goal.assumptions} />
    <details><summary>模型原始建议（未接受的不作为事实）</summary><Assumptions items={goal.suggested_assumptions} /></details>
  </section>;
}

export function GoalWizard({ goal, busy, issues, onConfirm }: {
  goal: GoalRead; busy: boolean; issues: Issue[]; onConfirm: (body: ConfirmGoal) => Promise<boolean>;
}) {
  const key = `b1:goal:${goal.id}`;
  const [draft, setDraft] = useState<GoalDraft>(() => loadDraft<GoalDraft>(key) ?? goalDraft(goal));
  const [confirmed, setConfirmed] = useState(false);
  const [validation, setValidation] = useState('');
  useEffect(() => { keepDraft(key, draft); }, [key, draft]);
  const stale = draft.baseRevision !== goal.revision;
  const update = (value: GoalDraft) => { setDraft(value); setConfirmed(false); setValidation(''); };
  const answerQuestion = (answer: Answer) => update({ ...draft, answers: [...draft.answers.filter(item => item.key !== answer.key), answer] });
  const skipAssumptions = goal.questions.filter(q => draft.answers.some(a => a.key === q.key && a.kind === 'skip')).map(q => ({ key: `skip:${q.key}`, field: null, value: q.default_assumption, reason: q.reason }));
  const missing = goal.questions.some(question => !validAnswer(question, draft.answers.find(answer => answer.key === question.key)));
  return <form className="panel" onSubmit={async e => {
    e.preventDefault();
    if (stale || missing || !confirmed) return;
    if (draft.values.deadline_at && (!/T.*(?:Z|[+-]\d\d:\d\d)$/.test(draft.values.deadline_at) || Number.isNaN(Date.parse(draft.values.deadline_at)))) {
      setValidation('截止时间必须是有效的带时区 RFC3339 时间。'); return;
    }
    const success = await onConfirm({ expected_revision: draft.baseRevision, values: draft.values,
      answers: goal.questions.map(question => draft.answers.find(answer => answer.key === question.key)!),
      accepted_suggested_assumption_keys: draft.accepted, user_assumptions: draft.assumptions, confirmed: true });
    if (success) forgetDraft(key);
  }}>
    <h2>澄清与目标审阅</h2><p>逐题回答，再审阅目标事实。未保存编辑暂存在此标签页，刷新仍可继续。</p>
    <fieldset disabled={busy}>
      {stale && <div className="notice"><h3>目标已更新，本地回答仍保留</h3><p>本地基于 r{draft.baseRevision}，最新 r{goal.revision}。请对照最新问题后人工合并。</p>
        <button type="button" onClick={() => update({ ...draft, baseRevision: goal.revision, answers: draft.answers.filter(answer => goal.questions.some(q => validAnswer(q, answer))), accepted: draft.accepted.filter(id => goal.suggested_assumptions.some(a => a.key === id)) })}>已对照最新问题，保留并合并回答</button>
        <button type="button" className="secondary" onClick={() => update(goalDraft(goal))}>放弃本地回答，采用最新建议</button>
      </div>}
      {goal.questions.map(question => {
        const answer = draft.answers.find(item => item.key === question.key);
        const issue = issues.some(item => item.path.includes(question.key) || (item.path.includes('answers') && item.path.includes(goal.questions.indexOf(question))));
        return <fieldset key={question.key} className={issue ? 'invalid' : ''}><legend>{question.prompt}</legend>
          <small>理由：{question.reason} · 图谱影响：{question.graph_impact} · <code>{question.key}</code></small>
          {question.options.map(option => <label className="check" key={option.id}><input type="radio" name={question.key} checked={answer?.kind === 'choice' && answer.value === option.id} onChange={() => answerQuestion({ key: question.key, kind: 'choice', value: option.id })} />{option.label}</label>)}
          {question.allow_custom && <><label className="check"><input type="radio" name={question.key} checked={answer?.kind === 'custom'} onChange={() => answerQuestion({ key: question.key, kind: 'custom', value: '' })} />自定义回答</label>
            {answer?.kind === 'custom' && <label>自定义：{question.prompt}<textarea required maxLength={4000} value={answer.value ?? ''} onChange={e => answerQuestion({ ...answer, value: e.target.value })} /></label>}</>}
          {question.allow_skip && <><label className="check"><input type="radio" name={question.key} checked={answer?.kind === 'skip'} onChange={() => answerQuestion({ key: question.key, kind: 'skip', value: null })} />跳过并采用默认假设</label><p className="assumption-note">跳过将采用：{question.default_assumption}</p></>}
          {!validAnswer(question, answer) && <small>请选择一种允许的回答方式。</small>}
        </fieldset>;
      })}
      <ValuesForm values={draft.values} change={values => update({ ...draft, values })} issues={issues} />
      <fieldset><legend>透明假设审阅</legend><h3>模型建议：默认不接受，可逐条接受或拒绝</h3>
        {goal.suggested_assumptions.map(assumption => <div className="assumption-card" key={assumption.key}><Assumptions items={[assumption]} />
          <label className="check"><input type="checkbox" checked={draft.accepted.includes(assumption.key)} onChange={e => update({ ...draft, accepted: e.target.checked ? [...draft.accepted, assumption.key] : draft.accepted.filter(key => key !== assumption.key) })} />接受这条建议假设</label>
        </div>)}
        <h3>跳过问题将自动采用（不接受时请改为具体回答）</h3><Assumptions items={skipAssumptions} />
        <h3>你补充的人工假设</h3>
        {draft.assumptions.map((assumption, index) => <fieldset key={assumption.key}><legend>人工假设 {index + 1}</legend>
          <label>关联目标字段<select aria-label={`人工假设 ${index + 1} 关联目标字段`} value={assumption.field ?? ''} onChange={e => update({ ...draft, assumptions: draft.assumptions.map((item, i) => i === index ? { ...item, field: (e.target.value || null) as Assumption['field'] } : item) })}><option value="">无关联字段</option>{Object.entries(valueLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label>假设内容<textarea maxLength={2000} value={assumption.value ?? ''} onChange={e => update({ ...draft, assumptions: draft.assumptions.map((item, i) => i === index ? { ...item, value: e.target.value || null } : item) })} /></label>
          <label>假设理由<textarea required maxLength={2000} value={assumption.reason} onChange={e => update({ ...draft, assumptions: draft.assumptions.map((item, i) => i === index ? { ...item, reason: e.target.value } : item) })} /></label>
          <button type="button" className="secondary" onClick={() => update({ ...draft, assumptions: draft.assumptions.filter((_, i) => i !== index) })}>移除人工假设 {index + 1}</button>
        </fieldset>)}
        <button type="button" className="secondary" disabled={draft.assumptions.length >= 16} onClick={() => update({ ...draft, assumptions: [...draft.assumptions, { key: `user:${crypto.randomUUID()}`, field: null, value: null, reason: '' }] })}>添加人工假设</button>
      </fieldset>
      {validation && <p role="alert">{validation}</p>}
      <label className="check confirmation"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />我已审阅回答、目标事实及采用的假设，明确确认目标</label>
      <button disabled={!confirmed || missing || stale}>确认目标</button>
      {missing && <p className="muted">所有动态问题都需回答；跳过只在题目允许时可选。</p>}
    </fieldset>
  </form>;
}
