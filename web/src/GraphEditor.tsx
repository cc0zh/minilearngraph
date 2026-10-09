import { useEffect, useState } from 'react';
import { api } from './api';
import { graphDraft, keepDraft, loadDraft, type GraphDraft } from './drafts';
import type { GraphInput, GraphRead, Issue, NodeInput, NodeType, Relation } from './types';

const nodeTypes: NodeType[] = ['root', 'concept', 'practice', 'assessment'];
const relations: Relation[] = ['contains', 'prerequisite', 'related', 'contrast', 'application'];
const relationLabels = { contains: '包含（父→子）', prerequisite: '前置（基础→依赖）', related: '相关', contrast: '对比', application: '应用' };

export function GraphSnapshot({ graph }: { graph: GraphRead }) {
  return <div><p>{graph.status} · r{graph.revision} · {graph.last_revision_reason ?? '无修订说明'}</p>
    <ul>{graph.nodes.map(node => <li key={node.id}><strong>{node.label}</strong> · {node.node_type} · 内容 v{node.node_version}<p>{node.description}</p><small>教学策略：{node.teaching_strategy}</small>
      <p>重要性：{node.target_weight} · 位置：{node.position ? `x=${node.position.x}，y=${node.position.y}` : '未设定'}</p><code>{node.id}</code></li>)}</ul>
    <h4>关系</h4><ul>{graph.edges.map((edge, index) => <li key={index}>{graph.nodes.find(n => n.id === edge.source)?.label} → {graph.nodes.find(n => n.id === edge.target)?.label} · {relationLabels[edge.relation]}<br /><code>{edge.source} → {edge.target}</code></li>)}</ul>
  </div>;
}

function GraphHistory({ graph }: { graph: GraphRead }) {
  const [revision, setRevision] = useState(1);
  const [snapshot, setSnapshot] = useState<GraphRead | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  return <details className="panel"><summary>历史修订（只读，不回滚）</summary>
    <form className="row" onSubmit={async e => { e.preventDefault(); setBusy(true); setError('');
      try { setSnapshot(await api.graph(graph.id, revision)); } catch (err) { setError(err instanceof Error ? err.message : '读取失败'); } finally { setBusy(false); }
    }}><label>历史修订号<input type="number" min={1} max={graph.revision} required value={revision} onChange={e => setRevision(Number(e.target.value))} /></label><button disabled={busy}>读取历史</button></form>
    {error && <p role="alert">{error}</p>}{busy && <p role="status">正在读取历史…</p>}
    {snapshot && <GraphSnapshot graph={snapshot} />}
  </details>;
}

export function GraphEditor({ graph, busy, issues, onSave, onPublish, onRefresh }: {
  graph: GraphRead; busy: boolean; issues: Issue[];
  onSave: (input: GraphInput, reason?: string) => Promise<GraphRead | null>;
  onPublish: () => Promise<GraphRead | null>; onRefresh: () => void;
}) {
  const key = `b1:graph:${graph.id}`;
  const [draft, setDraft] = useState<GraphDraft>(() => loadDraft<GraphDraft>(key) ?? graphDraft(graph));
  const [confirmed, setConfirmed] = useState(false);
  const [publishConfirmed, setPublishConfirmed] = useState(false);
  const [message, setMessage] = useState('');
  useEffect(() => { keepDraft(key, draft); }, [key, draft]);
  const stale = draft.baseRevision !== graph.revision;
  const dirty = JSON.stringify(draft.input) !== JSON.stringify(graphDraft(graph).input);
  const update = (next: GraphDraft) => { setDraft(next); setConfirmed(false); setPublishConfirmed(false); setMessage(''); };
  const changeNode = (index: number, patch: Partial<NodeInput>) => update({ ...draft, input: { ...draft.input, nodes: draft.input.nodes.map((node, i) => i === index ? { ...node, ...patch } : node) } });
  function nodeIssues(node: NodeInput, index: number) {
    return issues.filter(issue => issue.node_ids.includes(node.ref) || (!!node.id && issue.node_ids.includes(node.id)) || (issue.path[1] === 'nodes' && issue.path[2] === index));
  }
  function edgeIssues(index: number) {
    return issues.filter(issue => {
      if (issue.path[0] !== 'graph') return issue.edge_indexes.includes(index) || (issue.path[1] === 'edges' && issue.path[2] === index);
      const edge = draft.input.edges[index];
      return issue.edge_indexes.some(i => {
        const stored = graph.edges[i];
        return stored && draft.input.nodes.find(n => n.ref === edge.source_ref)?.id === stored.source && draft.input.nodes.find(n => n.ref === edge.target_ref)?.id === stored.target && edge.relation === stored.relation;
      });
    });
  }
  return <>
    <section className="panel"><div className="section-title"><h2>{graph.status === 'published' ? '正式图谱修订' : '候选图谱审核'}</h2><span className="badge">{graph.status} · r{graph.revision}</span></div>
      <p>整图保存；节点与关系的改挂、增删必须在同一图内完成。允许暂时的无效编辑，服务端会校验结构，未通过不会部分保存。</p>
      {graph.status === 'published' && <p className="notice">正式图谱已发布。修改需填写理由并明确确认，历史内容不会被清除。</p>}
      <button type="button" className="secondary" disabled={busy} onClick={onRefresh}>读取最新图谱（保留本地编辑）</button>
      {stale && <div className="notice" role="status"><h3>修订冲突：保留本地编辑供合并</h3><p>编辑基于 r{draft.baseRevision}，最新 r{graph.revision}。不自动覆盖，也不自动重试保存。</p>
        <details><summary>对照最新已保存图谱</summary><GraphSnapshot graph={graph} /></details>
        <p>请在下面人工调整节点/关系。已被删除的旧 ID 不可复用，移除后可新增节点。</p>
        <button type="button" disabled={busy} onClick={() => { update({ ...draft, baseRevision: graph.revision }); setMessage('已采用最新修订作为基线，请重新审阅并确认保存。'); }}>已人工合并，采用最新修订号</button>
        <button type="button" className="secondary" disabled={busy} onClick={() => update(graphDraft(graph))}>放弃本地编辑，使用最新图谱</button>
      </div>}
      <form onSubmit={async e => { e.preventDefault();
        if (stale || (graph.status === 'published' && (!confirmed || !draft.reason.trim()))) return;
        const result = await onSave(draft.input, graph.status === 'published' ? draft.reason.trim() : undefined);
        if (result) { update(graphDraft(result)); setMessage('完整图谱已保存。'); }
      }}>
        <fieldset disabled={busy}><legend>节点与关系编辑</legend>
          <div className="section-title"><h3>节点 ({draft.input.nodes.length}/100)</h3><button type="button" className="secondary" disabled={draft.input.nodes.length >= 100} onClick={() => update({ ...draft, input: { ...draft.input, nodes: [...draft.input.nodes, { ref: `new_${crypto.randomUUID().replaceAll('-', '')}`, id: null, label: '', node_type: 'concept', description: '', teaching_strategy: '', target_weight: 50, position: null }] } })}>添加节点</button></div>
          <div className="node-grid">{draft.input.nodes.map((node, index) => {
            const errors = nodeIssues(node, index);
            return <fieldset key={node.ref} className={`node-card ${errors.length ? 'invalid' : ''}`} data-testid={`node-${index}`}><legend>节点 {index + 1} · {node.id ? '已有' : '新增'}</legend>
              <small><code>{node.ref}</code>{node.id && <> · 内容 v{graph.nodes.find(n => n.id === node.id)?.node_version ?? '已不在最新图谱'}<br /><code>{node.id}</code></>}</small>
              {errors.map((issue, i) => <p key={i} className="error-text">{issue.code}：{issue.message}</p>)}
              <label>节点 {index + 1} 名称<input required maxLength={200} value={node.label} onChange={e => changeNode(index, { label: e.target.value })} /></label>
              <label>节点 {index + 1} 类型<select aria-label={`节点 ${index + 1} 类型`} value={node.node_type} onChange={e => changeNode(index, { node_type: e.target.value as NodeType })}>{nodeTypes.map(type => <option key={type}>{type}</option>)}</select></label>
              <label>节点 {index + 1} 描述<textarea aria-label={`节点 ${index + 1} 描述`} required maxLength={4000} value={node.description} onChange={e => changeNode(index, { description: e.target.value })} /></label>
              <label>节点 {index + 1} 教学策略<textarea aria-label={`节点 ${index + 1} 教学策略`} required maxLength={4000} value={node.teaching_strategy} onChange={e => changeNode(index, { teaching_strategy: e.target.value })} /></label>
              <label>节点 {index + 1} 重要性<input type="number" min={1} max={100} required value={node.target_weight} onChange={e => changeNode(index, { target_weight: Number(e.target.value) })} /></label>
              <label className="check"><input type="checkbox" checked={node.position !== null} onChange={e => changeNode(index, { position: e.target.checked ? { x: 0, y: 0 } : null })} />节点 {index + 1} 设置位置</label>
              {node.position && <div className="form-grid">{(['x', 'y'] as const).map(axis => <label key={axis}>节点 {index + 1} {axis}<input type="number" step="any" min={-100000} max={100000} required value={node.position![axis]} onChange={e => changeNode(index, { position: { ...node.position!, [axis]: Number(e.target.value) } })} /></label>)}</div>}
              <button type="button" className="danger" onClick={() => update({ ...draft, input: { nodes: draft.input.nodes.filter((_, i) => i !== index), edges: draft.input.edges.filter(edge => edge.source_ref !== node.ref && edge.target_ref !== node.ref) } })}>移除节点 {index + 1} 及关联边</button>
              <small>子节点不会隐式删除。移除父节点后，请把子节点改挂到其他父节点。</small>
            </fieldset>;
          })}</div>
          <div className="section-title"><h3>关系 ({draft.input.edges.length}/500)</h3><button type="button" className="secondary" disabled={draft.input.nodes.length < 2 || draft.input.edges.length >= 500} onClick={() => update({ ...draft, input: { ...draft.input, edges: [...draft.input.edges, { source_ref: draft.input.nodes[0].ref, target_ref: draft.input.nodes[1].ref, relation: 'contains' }] } })}>添加关系</button></div>
          <p className="muted">contains 父→子；prerequisite 前置→依赖。每个非根需要一个 contains 父；二者联合不可成环。</p>
          {draft.input.edges.map((edge, index) => {
            const errors = edgeIssues(index);
            return <fieldset className={`edge-row ${errors.length ? 'invalid' : ''}`} key={index} data-testid={`edge-${index}`}><legend>关系 {index + 1}</legend>
              <div className="form-grid">{(['source_ref', 'target_ref'] as const).map((field, i) => <label key={field}>关系 {index + 1} {i === 0 ? '来源' : '目标'}<select aria-label={`关系 ${index + 1} ${i === 0 ? '来源' : '目标'}`} required value={edge[field]} onChange={e => update({ ...draft, input: { ...draft.input, edges: draft.input.edges.map((item, j) => j === index ? { ...item, [field]: e.target.value } : item) } })}>
                {!draft.input.nodes.some(node => node.ref === edge[field]) && <option value={edge[field]}>缺失端点：{edge[field]}</option>}
                {draft.input.nodes.map(node => <option value={node.ref} key={node.ref}>{node.label || '未命名'} · {node.ref}</option>)}
              </select></label>)}
                <label>关系 {index + 1} 类型<select aria-label={`关系 ${index + 1} 类型`} value={edge.relation} onChange={e => update({ ...draft, input: { ...draft.input, edges: draft.input.edges.map((item, j) => j === index ? { ...item, relation: e.target.value as Relation } : item) } })}>{relations.map(relation => <option value={relation} key={relation}>{relationLabels[relation]}</option>)}</select></label>
              </div>
              {errors.map((issue, i) => <p key={i} className="error-text">{issue.code}：{issue.message}</p>)}
              <button className="secondary" type="button" onClick={() => update({ ...draft, input: { ...draft.input, edges: draft.input.edges.filter((_, i) => i !== index) } })}>移除关系 {index + 1}</button>
            </fieldset>;
          })}
          {graph.status === 'published' && <><label>正式修订理由<textarea aria-label="正式修订理由" required maxLength={2000} value={draft.reason} onChange={e => update({ ...draft, reason: e.target.value })} /></label>
            <label className="check confirmation"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />我已审阅全部节点与关系，明确确认此次正式修订</label></>}
          <button disabled={stale || (graph.status === 'published' && (!confirmed || !draft.reason.trim()))}>{graph.status === 'published' ? '确认正式修订' : '保存候选图谱'}</button>
          <span className="muted">{dirty ? ' 有未保存的图谱编辑' : ' 当前图谱内容已保存'}</span>
        </fieldset>
      </form>
      {graph.status === 'candidate' && <fieldset disabled={busy || dirty || stale}><legend>审核发布</legend>
        <p>发布仅针对已保存的完整候选。请先保存编辑；发布不会重新调用模型。</p>
        <label className="check confirmation"><input type="checkbox" checked={publishConfirmed} onChange={e => setPublishConfirmed(e.target.checked)} />我已审核已保存图谱，明确确认发布</label>
        <button type="button" disabled={!publishConfirmed} onClick={async () => { const published = await onPublish(); if (published) update(graphDraft(published)); }}>确认发布图谱</button>
      </fieldset>}
      {message && <p role="status">{message}</p>}
    </section>
    <GraphHistory graph={graph} />
  </>;
}
