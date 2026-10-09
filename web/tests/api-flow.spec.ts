import { test, expect, type Page } from '@playwright/test';
import type { GoalRead, GraphRead } from '../src/types';
import { graphDraft } from '../src/drafts';
import { spawn, type ChildProcess } from 'node:child_process';
import { once } from 'node:events';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const base = 'http://127.0.0.1:8000/api/v1';
let server: ChildProcess | undefined;
let directory: string;
let generationWaiting: Promise<void>;
async function startServer(pause = false) {
  const python = process.env.B1_API_PYTHON;
  if (!python) throw new Error('Use npm run test:api-flow to resolve the locked Python environment.');
  server = spawn(python, [fileURLToPath(new URL('./api_fixture.py', import.meta.url)), '--db', join(directory, 'browser.sqlite3')], {
    env: { ...process.env, B1_TEST_PAUSE_GENERATION: pause ? '1' : '0' }, stdio: ['ignore', 'pipe', 'pipe'],
  });
  const child = server;
  generationWaiting = new Promise(resolve => { child.stdout!.on('data', data => { if (String(data).includes('B1_TEST_GENERATION_WAITING')) resolve(); }); });
  await new Promise<void>((resolve, reject) => {
    let output = '';
    child.stderr!.on('data', data => { output += String(data); if (output.includes('Uvicorn running on')) resolve(); });
    child.once('error', reject); child.once('exit', code => reject(new Error(`API fixture exited ${code}: ${output}`)));
  });
}
async function stopServer() {
  if (server && server.exitCode === null && server.signalCode === null) {
    const exited = once(server, 'exit'); server.kill('SIGKILL'); await exited;
  }
  server = undefined;
}
test.beforeAll(async () => { directory = await mkdtemp(join(tmpdir(), 'mini-web-b1-')); await startServer(); });
test.afterAll(async () => { await stopServer(); if (directory) await rm(directory, { recursive: true, force: true }); });
async function createAndConfirm(page: Page, prompt: string, checkInvalidDeadline = false) {
  await page.goto('/'); await page.getByLabel('你想学什么，最终能做到什么？').fill(prompt);
  await page.getByRole('button', { name: '创建并生成澄清问题' }).click();
  if (prompt.includes('FAIL_CLARIFY_ONCE')) {
    await expect(page.getByRole('heading', { name: '目标澄清 · generation_failed' })).toBeVisible();
    await page.reload(); await page.getByRole('button', { name: '显式重试澄清' }).click();
  }
  await page.getByLabel('跳过并采用默认假设', { exact: true }).check();
  await page.getByRole('group', { name: '你使用什么工具？', exact: true }).getByLabel('自定义回答', { exact: true }).check();
  await page.getByLabel('自定义：你使用什么工具？', { exact: true }).fill('VS Code');
  await page.getByLabel('清理后的 CSV 文件', { exact: true }).check();
  await page.getByLabel('接受这条建议假设', { exact: true }).check();
  if (checkInvalidDeadline) {
    // Date.parse normalizes February 30; the strict API must still reject it
    // and Web must locate the returned issue without discarding the answers.
    await page.getByLabel('明确截止时间（带时区）').fill('2026-02-30T18:00:00+08:00');
    await page.getByLabel('我已审阅回答、目标事实及采用的假设，明确确认目标').check();
    const invalid = page.waitForResponse(r => r.url().endsWith('/confirm'));
    await page.getByRole('button', { name: '确认目标', exact: true }).click(); expect((await invalid).status()).toBe(422);
    await expect(page.getByRole('alert')).toContainText('body.values.deadline_at');
    await expect(page.getByLabel('明确截止时间（带时区）')).toHaveAttribute('aria-invalid', 'true');
    await page.getByLabel('明确截止时间（带时区）').fill('');
  }
  await page.getByLabel('我已审阅回答、目标事实及采用的假设，明确确认目标').check();
  const response = page.waitForResponse(r => r.url().endsWith('/confirm'));
  await page.getByRole('button', { name: '确认目标', exact: true }).click();
  const confirmed = await response; expect(confirmed.status()).toBe(200);
  return confirmed.json() as Promise<GoalRead>;
}

test('实际HTTP/SQLite：CSV向导、编辑/发布、正式修订、历史和刷新（模型为固定桩）', async ({ page, request }) => {
  const goal = await createAndConfirm(page, '学习 Python，最终能独立处理 CSV 数据');
  expect(goal.assumptions.map(item => item.key)).toEqual(['suggested:headers', 'skip:loop_background']);
  const generation = page.waitForResponse(r => r.url().endsWith(`/goals/${goal.id}/graphs`));
  await page.getByRole('button', { name: '生成候选图谱', exact: true }).click();
  const generated = await generation; expect(generated.status()).toBe(201);
  let graph: GraphRead = await generated.json();
  const loopIndex = graph.nodes.findIndex(node => node.label === '循环');
  await page.getByLabel(`节点 ${loopIndex + 1} 名称`, { exact: true }).fill('循环与边界');
  const save = page.waitForResponse(r => r.url() === `${base}/graphs/${graph.id}` && r.request().method() === 'PUT');
  await page.getByRole('button', { name: '保存候选图谱', exact: true }).click();
  const saved = await save; expect(saved.status()).toBe(200); graph = (await saved.json()).graph;
  expect(graph.nodes.find(n => n.label === '循环与边界')!.node_version).toBe(2);
  await page.getByLabel('我已审核已保存图谱，明确确认发布').check();
  const publish = page.waitForResponse(r => r.url().endsWith('/publish')); await page.getByRole('button', { name: '确认发布图谱' }).click();
  const published = await publish; expect(published.status()).toBe(200); graph = await published.json();
  await page.getByLabel('正式修订理由', { exact: true }).fill('复核节点重要性');
  await page.getByLabel(`节点 ${loopIndex + 1} 重要性`, { exact: true }).fill('90');
  await page.getByLabel('我已审阅全部节点与关系，明确确认此次正式修订').check();
  const revise = page.waitForResponse(r => r.url().endsWith('/revise')); await page.getByRole('button', { name: '确认正式修订' }).click();
  const revised = await revise; expect(revised.status()).toBe(200);
  const current: GraphRead = (await revised.json()).graph;
  expect(current.nodes.find(n => n.label === '循环与边界')!.node_version).toBe(2);
  expect(current.last_revision_reason).toBe('复核节点重要性');
  await page.getByText('历史修订（只读，不回滚）', { exact: true }).click();
  await page.getByLabel('历史修订号').fill(String(graph.revision)); await page.getByRole('button', { name: '读取历史' }).click();
  await expect(page.getByText(`published · r${graph.revision} · 无修订说明`, { exact: true })).toBeVisible();
  await page.reload(); await expect(page.getByRole('heading', { name: '正式图谱修订', exact: true })).toBeVisible();
  const stored = await request.get(`${base}/graphs/${current.id}`); expect(await stored.json()).toEqual(current);
});

test('实际HTTP/SQLite：失败GET/手动retry、真实CAS409合并、联合环422定位', async ({ page, request }) => {
  const goal = await createAndConfirm(page, 'FAIL_CLARIFY_ONCE FAIL_GRAPH_ONCE 学习 Python CSV', true);
  await page.getByRole('button', { name: '生成候选图谱', exact: true }).click();
  await expect(page.getByRole('heading', { name: '图谱 · generation_failed' })).toBeVisible();
  await page.reload();
  const generation = page.waitForResponse(r => r.url().endsWith('/generate'));
  await page.getByRole('button', { name: '显式重试图谱生成' }).click();
  const generated = await generation; expect(generated.status()).toBe(200);
  let graph: GraphRead = await generated.json();
  const input = graphDraft(graph).input;
  const rootIndex = input.nodes.findIndex(node => node.node_type === 'root'); const childIndex = input.nodes.findIndex(node => node.node_type !== 'root');
  const competing = await request.put(`${base}/graphs/${graph.id}`, { data: { ...input, expected_revision: graph.revision } }); expect(competing.status()).toBe(200);
  await page.getByLabel(`节点 ${childIndex + 1} 名称`, { exact: true }).fill('保留的本地节点编辑');
  await page.getByRole('button', { name: '保存候选图谱', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('HTTP 409');
  await expect(page.getByLabel(`节点 ${childIndex + 1} 名称`, { exact: true })).toHaveValue('保留的本地节点编辑');
  await page.getByRole('button', { name: '已人工合并，采用最新修订号' }).click();
  const save = page.waitForResponse(r => r.request().method() === 'PUT'); await page.getByRole('button', { name: '保存候选图谱', exact: true }).click();
  const saved = await save; expect(saved.status()).toBe(200); graph = (await saved.json()).graph;
  await page.getByRole('button', { name: '添加关系', exact: true }).click();
  await page.getByLabel('关系 4 来源', { exact: true }).selectOption(`n${childIndex + 1}`);
  await page.getByLabel('关系 4 目标', { exact: true }).selectOption(`n${rootIndex + 1}`);
  await page.getByLabel('关系 4 类型', { exact: true }).selectOption('prerequisite');
  await page.getByRole('button', { name: '保存候选图谱', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('HTTP 422');
  await expect(page.getByRole('alert')).toContainText('structural_cycle');
  await expect(page.getByTestId(`node-${rootIndex}`)).toHaveClass(/invalid/); await expect(page.getByTestId('edge-3')).toHaveClass(/invalid/);
  const stored = await request.get(`${base}/graphs/${graph.id}`); expect((await stored.json()).revision).toBe(graph.revision);
  const latestGoal = await request.get(`${base}/goals/${goal.id}`); expect((await latestGoal.json()).status).toBe('confirmed');
});

test('实际进程重启：生成中断可GET并显式retry，已发布图谱/历史继续读取且不重放', async ({ page, request }) => {
  await stopServer(); await startServer(true);
  const goal = await createAndConfirm(page, 'PAUSE_GRAPH 学习 Python CSV');
  let writes = 0; page.on('request', req => { if (req.url().startsWith(base) && req.method() !== 'GET' && req.method() !== 'OPTIONS') writes++; });
  await page.getByRole('button', { name: '生成候选图谱', exact: true }).click();
  await generationWaiting;
  const graphs = await request.get(`${base}/graphs?goal_id=${goal.id}`);
  const pending: GraphRead = (await graphs.json()).items[0]; expect(pending.status).toBe('generating');
  await stopServer(); await startServer();
  await page.reload();
  await expect(page.getByRole('heading', { name: '图谱 · generation_failed' })).toBeVisible();
  await expect(page.getByRole('alert').filter({ hasText: 'interrupted' })).toBeVisible();
  expect(writes).toBe(1);
  const retry = page.waitForResponse(r => r.url().endsWith('/generate'));
  await page.getByRole('button', { name: '显式重试图谱生成' }).click();
  const retried = await retry; expect(retried.status()).toBe(200);
  const candidate: GraphRead = await retried.json(); expect(candidate.id).toBe(pending.id);
  await page.getByLabel('我已审核已保存图谱，明确确认发布').check();
  const publish = page.waitForResponse(r => r.url().endsWith('/publish'));
  await page.getByRole('button', { name: '确认发布图谱' }).click();
  const published: GraphRead = await (await publish).json();
  const count = writes; await stopServer(); await startServer(); await page.reload();
  await expect(page.getByRole('heading', { name: '正式图谱修订', exact: true })).toBeVisible(); expect(writes).toBe(count);
  expect(await (await request.get(`${base}/graphs/${pending.id}`)).json()).toEqual(published);
  await page.getByText('历史修订（只读，不回滚）', { exact: true }).click();
  await page.getByLabel('历史修订号').fill(String(candidate.revision)); await page.getByRole('button', { name: '读取历史' }).click();
  await expect(page.getByText(`candidate · r${candidate.revision} · 无修订说明`, { exact: true })).toBeVisible();
});
