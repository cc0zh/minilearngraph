import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, api } from './api';
import { forgetDraft, keepDraft, loadDraft } from './drafts';
import { GoalSummary, GoalWizard } from './GoalWizard';
import { GraphEditor } from './GraphEditor';
import type { GoalRead, GraphRead, Issue } from './types';

type Notice = { message: string; code?: string; status?: number; issues: Issue[] };
const selectedId = () => new URLSearchParams(window.location.search).get('goal');

export function App() {
  const [goals, setGoals] = useState<GoalRead[]>([]);
  const [goal, setGoal] = useState<GoalRead | null>(null);
  const assetReadEpoch = useRef(0);
  const [graph, setGraph] = useState<GraphRead | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [recoveryRequired, setRecoveryRequired] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [prompt, setPrompt] = useState(() => loadDraft<string>('b1:prompt') ?? '');
  const [createUncertain, setCreateUncertain] = useState(() => loadDraft<boolean>('b1:create-uncertain') ?? false);
  const invalidateAssetReads = useCallback(() => { assetReadEpoch.current++; }, []);

  useEffect(() => { keepDraft('b1:prompt', prompt); }, [prompt]);
  useEffect(() => { keepDraft('b1:create-uncertain', createUncertain); }, [createUncertain]);

  const fetchAsset = useCallback(async (id: string) => {
    const current = await api.goal(id);
    const graphs = await api.graphs(id);
    return { goal: current, graph: graphs.items[0] ?? null };
  }, []);
  const selectGoal = useCallback(async (id: string | null) => {
    invalidateAssetReads();
    setLoading(true); setNotice(null);
    try {
      const asset = id ? await fetchAsset(id) : { goal: null, graph: null };
      setGoal(asset.goal); setGraph(asset.graph);
      if (id) setRecoveryRequired(false);
      const url = new URL(window.location.href); if (id) url.searchParams.set('goal', id); else url.searchParams.delete('goal');
      window.history.replaceState({}, '', url);
    } catch (err) { setRecoveryRequired(true); setNotice({ message: err instanceof Error ? err.message : '读取失败', issues: [] }); }
    finally { setLoading(false); }
  }, [fetchAsset, invalidateAssetReads]);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const list = await api.goals();
        if (!active) return;
        setGoals(list.items);
        const id = selectedId();
        if (id) { const asset = await fetchAsset(id); if (active) { setGoal(asset.goal); setGraph(asset.graph); } }
      } catch (err) { if (active) { setRecoveryRequired(true); setNotice({ message: err instanceof Error ? err.message : '读取失败', issues: [] }); } }
      finally { if (active) setLoading(false); }
    })();
    return () => { active = false; invalidateAssetReads(); };
  }, [fetchAsset, invalidateAssetReads]);

  async function refresh() {
    invalidateAssetReads();
    setBusy(true); setNotice(null);
    try { setGoals((await api.goals()).items); const id = goal?.id ?? selectedId(); if (id) { const asset = await fetchAsset(id); setGoal(asset.goal); setGraph(asset.graph); } setRecoveryRequired(false); }
    catch (err) { setRecoveryRequired(true); setNotice({ message: err instanceof Error ? err.message : '读取失败', issues: [] }); }
    finally { setBusy(false); }
  }

  async function write<T>(operation: () => Promise<T>, success: (value: T) => void, creating = false): Promise<T | null> {
    if (recoveryRequired) { setNotice({ message: '保存状态尚未查明。请先成功读取最新资产，再显式提交。', issues: [] }); return null; }
    setBusy(true); setNotice(null);
    try {
      const value = await operation(); success(value);
      // Refresh the list separately: a failed GET must not turn a known successful write into a failed one.
      try { setGoals((await api.goals()).items); } catch { setNotice({ message: '操作成功，但目标列表刷新失败。可手动读取最新。', issues: [] }); }
      return value;
    } catch (err) {
      const error = err instanceof ApiError ? err : null;
      let message = err instanceof Error ? err.message : '操作失败';
      if (creating) setCreateUncertain(true);
      try {
        const list = await api.goals(); setGoals(list.items);
        const resourceId = error?.body.details.resource_type === 'goal' ? error.body.details.resource_id : goal?.id;
        if (resourceId) { const asset = await fetchAsset(resourceId); setGoal(asset.goal); setGraph(asset.graph);
          const url = new URL(window.location.href); url.searchParams.set('goal', resourceId); window.history.replaceState({}, '', url); }
        else if (error?.body.details.resource_type === 'graph' && error.body.details.resource_id) {
          const recovered = await api.graph(error.body.details.resource_id); const asset = await fetchAsset(recovered.goal_id); setGoal(asset.goal); setGraph(asset.graph);
        }
        message += ' 已读取保存状态；本地编辑保留。请查看资产后显式操作。';
      } catch { setRecoveryRequired(true); message += ' 保存状态读取也失败。请稍后点击“读取最新资产”，不要重复创建。'; }
      setNotice({ message, code: error?.body.code, status: error?.status, issues: error?.body.details.issues ?? [] });
      return null;
    } finally { setBusy(false); }
  }

  function acceptGoal(current: GoalRead) {
    invalidateAssetReads();
    setGoal(current); setGraph(null); setCreateUncertain(false); forgetDraft('b1:prompt'); setPrompt('');
    const url = new URL(window.location.href); url.searchParams.set('goal', current.id); window.history.replaceState({}, '', url);
  }

  function acceptGeneratedGraph(current: GraphRead) {
    setGraph(current);
    const epoch = assetReadEpoch.current;
    // Generation also updates the goal. A delayed read belongs only to this
    // selection/read lifecycle and may never regress an already newer goal.
    void api.goal(current.goal_id).then(latest => {
      if (assetReadEpoch.current !== epoch) return;
      setGoal(selected => selected?.id === latest.id && latest.revision >= selected.revision ? latest : selected);
    }).catch(() => {});
  }

  return <div className="app-shell">
    <a className="skip-link" href="#main">跳到主要内容</a>
    <header><div><span className="eyebrow">MINI LEARNGRAPH / B1</span><h1>从目标出发，审核你的学习图谱</h1><p>模型提出建议，你确认范围与假设。所有发布和正式修订由你决定。</p></div><span className="badge">本机个人 · local-user</span></header>
    <div className="workspace">
      <aside className="panel"><h2>学习目标</h2>
        <button className="secondary" disabled={busy || loading} onClick={() => void selectGoal(null)}>创建新目标</button>
        <button className="secondary" disabled={busy || loading} onClick={() => void refresh()}>读取最新资产</button>
        {!loading && !goals.length && <p className="muted">还没有目标。从你想达成的成果开始。</p>}
        <ul className="goal-list">{goals.map(item => <li key={item.id}><button disabled={busy || loading} aria-current={goal?.id === item.id ? 'page' : undefined} onClick={() => void selectGoal(item.id)}>{item.values?.title ?? item.suggested_values?.title ?? item.raw_prompt}<small>{item.status} · 澄清 {item.clarification_status} · r{item.revision}</small></button></li>)}</ul>
        <p className="muted">资产由服务端保存。URL 保留当前目标，刷新后读取已有资产，不重放生成请求。</p>
      </aside>
      <main id="main" tabIndex={-1} aria-busy={busy || loading}>
        {notice && <section className="error-banner" role="alert"><h2>{notice.status ? `HTTP ${notice.status} · ` : ''}{notice.code ?? '操作提示'}</h2><p>{notice.message}</p>
          {notice.status === 409 && <p>不要盲目覆盖。读取最新后，保留未保存编辑并人工合并，再明确确认。</p>}
          {notice.issues.length > 0 && <ul>{notice.issues.map((issue, index) => <li key={index}><strong>{issue.code}</strong>：{issue.message} <code>{issue.path.join('.')}</code><br />节点/ref：{issue.node_ids.join(', ') || '无'} · 关系下标：{issue.edge_indexes.join(', ') || '无'}</li>)}</ul>}
        </section>}
        {(busy || loading) && <p className="waiting" role="status">{loading ? '正在读取已保存资产…' : '正在等待服务端… 不要重复提交；完成或失败后会读取保存状态。'}</p>}
        {recoveryRequired && <p className="notice" role="status">尚未查明已保存资产，写操作已暂停。请先点击“读取最新资产”。</p>}
        {!loading && !goal && <form className="panel" onSubmit={e => { e.preventDefault(); if (!createUncertain) void write(() => api.createGoal(prompt.trim()), acceptGoal, true); }}>
          <h2>创建学习目标</h2><label>你想学什么，最终能做到什么？<textarea required maxLength={8000} rows={5} placeholder="例如：学习 Python，最终能独立处理 CSV 数据" disabled={busy} value={prompt} onChange={e => setPrompt(e.target.value)} /></label>
          {createUncertain && <div className="notice"><p>上次创建未收到确定结果。先查看左侧目标列表，继续已保存的草稿；不会自动重发。</p><button type="button" className="secondary" disabled={busy} onClick={() => setCreateUncertain(false)}>我已检查列表，仍要另建一个目标</button></div>}
          <button disabled={busy || recoveryRequired || createUncertain || !prompt.trim()}>创建并生成澄清问题</button><p className="muted">不会上传资料；暂不包含教学、练习或推荐。</p>
        </form>}
        {!loading && goal && <>
          <p className="breadcrumb">当前目标 · <code>{goal.id}</code> · r{goal.revision}</p>
          {goal.status === 'confirmed' ? <GoalSummary goal={goal} /> : goal.clarification_status === 'ready' && goal.suggested_values ? <GoalWizard key={goal.id} goal={goal} busy={busy || recoveryRequired} issues={notice?.issues ?? []} onConfirm={async body => !!await write(() => api.confirm(goal.id, body), setGoal)} /> : <section className="panel"><h2>目标澄清 · {goal.clarification_status}</h2>
            <p>{goal.raw_prompt}</p>{goal.clarification_failure && <p role="alert">{goal.clarification_failure.message} · {goal.clarification_failure.reason}</p>}
            {goal.clarification_status === 'generating' ? <p>服务端仍在生成。请稍后读取最新资产；服务重启后中断状态可显式重试。</p> : <><p>草稿已保存。修复配置/连接等问题后，可以手动重试，不创建第二个目标。</p><button disabled={busy || recoveryRequired} onClick={() => void write(() => api.clarify(goal), setGoal)}>显式重试澄清</button></>}
          </section>}
          {goal.status === 'confirmed' && (!graph ? <section className="panel"><h2>生成候选图谱</h2><p>根据已确认目标、完整回答和透明假设生成。不会自动发布。</p><button disabled={busy || recoveryRequired} onClick={() => void write(() => api.createGraph(goal), acceptGeneratedGraph)}>生成候选图谱</button></section> : graph.status === 'candidate' || graph.status === 'published' ? <GraphEditor key={graph.id} graph={graph} busy={busy || recoveryRequired} issues={notice?.issues ?? []}
            onRefresh={() => void refresh()}
            onSave={async (input, reason) => { const result = await write(() => api.save(graph, input, reason), value => setGraph(value.graph)); return result?.graph ?? null; }}
            onPublish={() => write(() => api.publish(graph), setGraph)} /> : <section className="panel"><h2>图谱 · {graph.status}</h2>
              {graph.generation_failure && <p role="alert">{graph.generation_failure.message} · {graph.generation_failure.reason}</p>}
              {graph.status === 'generating' ? <p>生成尚在进行，请稍后读取最新。不会发起重复生成。</p> : <><p>生成失败但资产已保存；修复原因后显式重试。</p><button disabled={busy || recoveryRequired} onClick={() => void write(() => api.generate(graph), setGraph)}>显式重试图谱生成</button></>}
            </section>)}
        </>}
      </main>
    </div>
    <footer>本机学习工作区 · 建议不代表掌握；目标确认不代表图谱发布。</footer>
  </div>;
}
