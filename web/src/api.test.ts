import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, api } from './api';
import { candidateGraph, confirmedGoal } from './testFixtures';
import { graphDraft } from './drafts';

afterEach(() => vi.unstubAllGlobals());
describe('B1 HTTP boundary', () => {
  it('sends strict full bodies and no client learner_id', async () => {
    const fetcher = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ graph: candidateGraph(), ref_map: {} }), { status: 200 }));
    vi.stubGlobal('fetch', fetcher);
    const graph = candidateGraph(); await api.save(graph, graphDraft(graph).input);
    const [url, init] = fetcher.mock.calls[0];
    expect(url).toBe(`http://127.0.0.1:8000/api/v1/graphs/${graph.id}`);
    expect(init.method).toBe('PUT');
    expect(JSON.parse(init.body)).not.toHaveProperty('learner_id');
    expect(JSON.parse(init.body)).toMatchObject({ expected_revision: graph.revision, nodes: [{ position: null, id: graph.nodes[0].id }, {}, {}] });
    await api.publish(graph); expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ expected_revision: 2, confirmed: true });
    await api.createGraph(confirmedGoal()); expect(JSON.parse(fetcher.mock.calls[2][1].body)).toEqual({ expected_revision: 3 });
  });
  it('uses POST revise with reason and explicit confirmed for published graphs', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response('{}')); vi.stubGlobal('fetch', fetcher);
    const graph = { ...candidateGraph(), status: 'published' as const }; await api.save(graph, graphDraft(graph).input, '补充读取边界');
    expect(fetcher.mock.calls[0][0]).toContain('/revise');
    expect(fetcher.mock.calls[0][1].method).toBe('POST');
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toMatchObject({ confirmed: true, reason: '补充读取边界' });
  });
  it('exposes structured 422 details without retrying', async () => {
    const body = { code: 'graph_invalid', message: '结构不合法', retryable: false, details: { resource_type: 'graph', resource_id: null, current_revision: 2, expected_revision: 2, failure_reason: null, issues: [{ path: ['body', 'edges'], code: 'structural_cycle', message: '联合环', node_ids: ['n1', 'n2'], edge_indexes: [0, 1] }] } };
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 422 })); vi.stubGlobal('fetch', fetcher);
    try { await api.publish(candidateGraph()); throw new Error('Expected error'); }
    catch (error) { expect(error).toBeInstanceOf(ApiError); expect((error as ApiError).body.details.issues).toEqual(body.details.issues); }
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it('does not replay POST when transport fails', async () => {
    const fetcher = vi.fn().mockRejectedValue(new TypeError('Failed to fetch')); vi.stubGlobal('fetch', fetcher);
    await expect(api.createGoal('CSV')).rejects.toThrow('结果未知'); expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
