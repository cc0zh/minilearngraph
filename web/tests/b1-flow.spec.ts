import { expect, test, type Page } from '@playwright/test';
import { MockApi } from './mockApi';
import { candidateGraph, confirmedGoal, goalId } from '../src/testFixtures';

async function answerQuestions(page: Page) {
  await page.getByLabel('跳过并采用默认假设', { exact: true }).check();
  await page.getByRole('group', { name: '你使用什么工具？', exact: true }).getByLabel('自定义回答', { exact: true }).check();
  await page.getByLabel('自定义：你使用什么工具？', { exact: true }).fill('VS Code');
  await page.getByLabel('清理后的 CSV 文件', { exact: true }).check();
  await page.getByLabel('我已审阅回答、目标事实及采用的假设，明确确认目标', { exact: true }).check();
}
async function createGoal(page: Page) {
  await page.goto('/');
  await page.getByLabel('你想学什么，最终能做到什么？').fill('学习 Python，最终能独立处理 CSV 数据');
  await page.getByRole('button', { name: '创建并生成澄清问题' }).click();
}

test('CSV目标 → 动态澄清/透明假设 → 整图增改关系 → 发布/正式修订/历史 → 刷新', async ({ page }) => {
  const mock = new MockApi(page); await mock.install(); await createGoal(page);
  await expect(page.getByText('决定是否补充循环基础', { exact: false }).first()).toBeVisible();
  await expect(page.getByRole('group', { name: '你使用什么工具？', exact: true }).getByLabel('跳过并采用默认假设')).toHaveCount(0);
  await expect(page.getByRole('group', { name: '目标输出是什么？', exact: true }).getByLabel('自定义回答')).toHaveCount(0);
  await answerQuestions(page);
  await page.getByLabel('接受这条建议假设').first().check();
  await page.getByLabel('目标标题', { exact: true }).fill('CSV 独立处理目标');
  // Changing values invalidates the previous confirmation.
  await expect(page.getByRole('button', { name: '确认目标', exact: true })).toBeDisabled();
  await page.getByLabel('我已审阅回答、目标事实及采用的假设，明确确认目标').check();
  await page.getByRole('button', { name: '确认目标', exact: true }).click();
  await expect(page.getByRole('heading', { name: '已确认目标 · r3' })).toBeVisible();
  expect(mock.goal!.accepted_suggested_assumption_keys).toEqual(['suggested:headers']);
  expect(mock.goal!.assumptions.map(a => a.key)).toEqual(['suggested:headers', 'skip:loop_background']);
  expect(mock.goal!.values!.deadline_at).toBe(null);
  await page.getByRole('button', { name: '生成候选图谱', exact: true }).click();
  await page.getByLabel('节点 2 名称', { exact: true }).fill('循环与边界');
  await page.getByRole('button', { name: '添加节点', exact: true }).click();
  await page.getByLabel('节点 4 名称', { exact: true }).fill('CSV 转换练习');
  await page.getByLabel('节点 4 类型', { exact: true }).selectOption('practice');
  await page.getByLabel('节点 4 描述', { exact: true }).fill('转换每一行并输出');
  await page.getByLabel('节点 4 教学策略', { exact: true }).fill('独立解释并复查边界');
  await page.getByRole('button', { name: '添加关系', exact: true }).click();
  await page.getByLabel('关系 4 来源', { exact: true }).selectOption('n3');
  await page.getByLabel('关系 4 目标', { exact: true }).selectOption({ label: await page.getByLabel('关系 4 目标', { exact: true }).locator('option').last().innerText() });
  await page.getByRole('button', { name: '保存候选图谱', exact: true }).click();
  await expect(page.getByText('完整图谱已保存。', { exact: true })).toBeVisible();
  expect(mock.graph!.nodes).toHaveLength(4); expect(mock.graph!.edges).toHaveLength(4);
  await page.getByLabel('我已审核已保存图谱，明确确认发布', { exact: true }).check();
  await page.getByRole('button', { name: '确认发布图谱', exact: true }).click();
  await expect(page.getByRole('heading', { name: '正式图谱修订', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: '修订冲突：保留本地编辑供合并' })).toHaveCount(0);
  await page.getByLabel('节点 3 描述', { exact: true }).fill('明确区分表头与数据行');
  await expect(page.getByRole('button', { name: '确认正式修订', exact: true })).toBeDisabled();
  await page.getByLabel('正式修订理由', { exact: true }).fill('补充表头边界说明');
  await page.getByLabel('我已审阅全部节点与关系，明确确认此次正式修订', { exact: true }).check();
  await page.getByRole('button', { name: '确认正式修订', exact: true }).click();
  await expect(page.getByText('完整图谱已保存。', { exact: true })).toBeVisible();
  expect(mock.graph!.last_revision_reason).toBe('补充表头边界说明');
  await page.getByText('历史修订（只读，不回滚）', { exact: true }).click();
  await page.getByLabel('历史修订号', { exact: true }).fill('3');
  await page.getByRole('button', { name: '读取历史', exact: true }).click();
  await expect(page.getByText('candidate · r3 · 无修订说明', { exact: true })).toBeVisible();
  const writes = mock.writes.length; await page.reload();
  await expect(page.getByRole('heading', { name: '正式图谱修订', exact: true })).toBeVisible();
  expect(mock.writes).toHaveLength(writes); await expect(page).toHaveURL(new RegExp(`goal=${goalId}`));
});

test('409保留未保存编辑/刷新，人工合并后使用最新revision而非盲覆盖', async ({ page }) => {
  const mock = new MockApi(page); mock.seedGraph(); await mock.install(); await page.goto(`/?goal=${goalId}`);
  await page.getByLabel('节点 2 名称', { exact: true }).fill('本地循环编辑'); mock.conflictNext = true;
  await page.getByRole('button', { name: '保存候选图谱', exact: true }).click();
  await expect(page.getByRole('heading', { name: '修订冲突：保留本地编辑供合并' })).toBeVisible();
  await expect(page.getByLabel('节点 2 名称', { exact: true })).toHaveValue('本地循环编辑');
  await expect(page.getByRole('button', { name: '保存候选图谱', exact: true })).toBeDisabled();
  await page.reload();
  await expect(page.getByLabel('节点 2 名称', { exact: true })).toHaveValue('本地循环编辑');
  await page.getByText('对照最新已保存图谱', { exact: true }).click();
  await expect(page.getByText('其他页面已补充循环边界', { exact: true })).toBeVisible();
  await page.getByLabel('节点 2 描述', { exact: true }).fill('其他页面已补充循环边界');
  await page.getByRole('button', { name: '已人工合并，采用最新修订号' }).click();
  await page.getByRole('button', { name: '保存候选图谱', exact: true }).click();
  await expect(page.getByText('完整图谱已保存。', { exact: true })).toBeVisible();
  expect(mock.writes.map(w => w.body.expected_revision)).toEqual([2, 3]);
});

test('422显示结构ref与边下标，节点/关系高亮且无局部保存', async ({ page }) => {
  const mock = new MockApi(page); mock.seedGraph(); await mock.install(); await page.goto(`/?goal=${goalId}`);
  await page.getByRole('button', { name: '添加关系', exact: true }).click();
  await page.getByLabel('关系 4 来源', { exact: true }).selectOption('n2');
  await page.getByLabel('关系 4 目标', { exact: true }).selectOption('n1');
  await page.getByLabel('关系 4 类型', { exact: true }).selectOption('prerequisite'); mock.invalidNext = true;
  await page.getByRole('button', { name: '保存候选图谱', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('HTTP 422');
  await expect(page.getByTestId('node-0')).toHaveClass(/invalid/);
  await expect(page.getByTestId('node-1')).toHaveClass(/invalid/);
  await expect(page.getByTestId('edge-3')).toHaveClass(/invalid/);
  expect(mock.graph!.edges).toHaveLength(3);
  await page.getByRole('button', { name: '移除关系 4', exact: true }).click();
  await page.getByRole('button', { name: '保存候选图谱', exact: true }).click();
  await expect(page.getByText('完整图谱已保存。', { exact: true })).toBeVisible();
});

test('创建响应丢失先GET列表恢复draft，刷新不重发创建', async ({ page }) => {
  const mock = new MockApi(page); mock.createMode = 'lost'; await mock.install(); await createGoal(page);
  await expect(page.getByRole('alert')).toContainText('结果未知');
  await expect(page.getByRole('button', { name: '创建并生成澄清问题' })).toBeDisabled();
  await page.reload();
  await expect(page.getByRole('button', { name: '创建并生成澄清问题' })).toBeDisabled();
  expect(mock.writes.filter(w => w.path === '/goals')).toHaveLength(1);
  await page.getByRole('button', { name: /Python CSV 数据处理.*draft/ }).click();
  await expect(page.getByRole('heading', { name: '澄清与目标审阅' })).toBeVisible();
  expect(mock.gets).toContain('/goals');
});

test('配置失败保留goal并显式retry；图谱失败先GET资产后显式retry', async ({ page }) => {
  const mock = new MockApi(page); mock.createMode = 'failed'; mock.graphMode = 'failed'; await mock.install(); await createGoal(page);
  await expect(page.getByRole('heading', { name: '目标澄清 · generation_failed' })).toBeVisible();
  expect(mock.gets).toContain(`/goals/${goalId}`);
  await page.getByRole('button', { name: '显式重试澄清', exact: true }).click();
  await answerQuestions(page); await page.getByRole('button', { name: '确认目标', exact: true }).click();
  await page.getByRole('button', { name: '生成候选图谱', exact: true }).click();
  await expect(page.getByRole('heading', { name: '图谱 · generation_failed' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: '图谱 · generation_failed' })).toBeVisible();
  await page.getByRole('button', { name: '显式重试图谱生成', exact: true }).click();
  await expect(page.getByRole('heading', { name: '候选图谱审核', exact: true })).toBeVisible();
  expect(mock.writes.filter(w => w.path === '/goals')).toHaveLength(1);
  expect(mock.writes.filter(w => w.path.endsWith('/graphs'))).toHaveLength(1);
  expect(mock.writes.filter(w => w.path.endsWith('/generate'))).toHaveLength(1);
});

test('确认响应丢失可GET恢复confirmed，移动窄屏无水平溢出/基本键盘可达', async ({ page }) => {
  const mock = new MockApi(page); mock.lostConfirm = true; await mock.install(); await createGoal(page); await answerQuestions(page);
  await page.getByRole('button', { name: '确认目标', exact: true }).click();
  await expect(page.getByRole('heading', { name: '已确认目标 · r3' })).toBeVisible();
  expect(mock.writes.filter(w => w.path.endsWith('/confirm'))).toHaveLength(1);
  await page.setViewportSize({ width: 375, height: 812 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.reload(); await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: '跳到主要内容' })).toBeFocused();
});

test('恢复GET失败暂停写入，成功读取后才能显式另建；不无条件重发POST', async ({ page }) => {
  const mock = new MockApi(page); mock.createMode = 'lost'; mock.failRecovery = true; await mock.install(); await createGoal(page);
  await expect(page.getByRole('status').filter({ hasText: '写操作已暂停' })).toBeVisible();
  await page.getByRole('button', { name: '我已检查列表，仍要另建一个目标' }).click();
  await expect(page.getByRole('button', { name: '创建并生成澄清问题' })).toBeDisabled();
  expect(mock.writes).toHaveLength(1);
  mock.failReads = false; await page.getByRole('button', { name: '读取最新资产', exact: true }).click();
  await expect(page.getByRole('button', { name: /Python CSV 数据处理.*draft/ })).toBeVisible();
  await page.getByRole('button', { name: /Python CSV 数据处理.*draft/ }).click();
  await expect(page.getByRole('heading', { name: '澄清与目标审阅' })).toBeVisible();
  expect(mock.writes).toHaveLength(1);
});

test('候选生成响应丢失GET恢复已有graph，不再创建；删节点关联边同图处理', async ({ page }) => {
  const mock = new MockApi(page); mock.lostGraph = true; await mock.install(); await createGoal(page); await answerQuestions(page);
  await page.getByRole('button', { name: '确认目标', exact: true }).click();
  await page.getByRole('button', { name: '生成候选图谱', exact: true }).click();
  await expect(page.getByRole('heading', { name: '候选图谱审核', exact: true })).toBeVisible();
  expect(mock.writes.filter(w => w.path.endsWith('/graphs'))).toHaveLength(1);
  await page.getByRole('button', { name: '移除节点 2 及关联边', exact: true }).click();
  await expect(page.getByRole('group', { name: '关系 2', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: '保存候选图谱', exact: true }).click();
  await expect(page.getByText('完整图谱已保存。', { exact: true })).toBeVisible();
  expect(mock.graph!.nodes).toHaveLength(2); expect(mock.graph!.edges).toHaveLength(1);
});

test('目标确认409保留GoalValues及答案，读取最新后人工合并再确认', async ({ page }) => {
  const mock = new MockApi(page); await mock.install(); await createGoal(page); await answerQuestions(page);
  await page.getByLabel('目标标题', { exact: true }).fill('保留本地目标标题');
  await page.getByLabel('我已审阅回答、目标事实及采用的假设，明确确认目标').check(); mock.conflictGoalNext = true;
  await page.getByRole('button', { name: '确认目标', exact: true }).click();
  await expect(page.getByRole('heading', { name: '目标已更新，本地回答仍保留' })).toBeVisible();
  await expect(page.getByLabel('目标标题', { exact: true })).toHaveValue('保留本地目标标题');
  await expect(page.getByRole('button', { name: '确认目标', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: '已对照最新问题，保留并合并回答' }).click();
  await page.getByLabel('我已审阅回答、目标事实及采用的假设，明确确认目标').check();
  await page.getByRole('button', { name: '确认目标', exact: true }).click();
  await expect(page.getByRole('heading', { name: '已确认目标 · r4' })).toBeVisible();
  expect(mock.goal!.values!.title).toBe('保留本地目标标题');
  expect(mock.writes.filter(w => w.path.endsWith('/confirm')).map(w => w.body.expected_revision)).toEqual([2, 3]);
});

test('图谱表单375/768/1024/1440响应式与所有控件标签可达', async ({ page }) => {
  const mock = new MockApi(page); mock.seedGraph(); await mock.install(); await page.goto(`/?goal=${goalId}`);
  await expect(page.getByRole('heading', { name: '候选图谱审核', exact: true })).toBeVisible();
  for (const width of [375, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
  expect(await page.evaluate(() => Array.from(document.querySelectorAll('input,textarea,select')).every(control => control.hasAttribute('aria-label') || control.closest('label') !== null))).toBe(true);
});

test('最新资产GET失败暂停写入，切换到新目标不能绕过，成功GET后恢复', async ({ page }) => {
  const mock = new MockApi(page); mock.seedGraph(); await mock.install(); await page.goto(`/?goal=${goalId}`);
  await page.getByLabel('节点 2 名称', { exact: true }).fill('暂停期间保留编辑');
  mock.failReads = true; await page.getByRole('button', { name: '读取最新资产', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: '写操作已暂停' })).toBeVisible();
  await expect(page.getByRole('button', { name: '保存候选图谱' })).toBeDisabled();
  await page.getByRole('button', { name: '创建新目标', exact: true }).click();
  await page.getByLabel('你想学什么，最终能做到什么？').fill('不要重复创建');
  await expect(page.getByRole('button', { name: '创建并生成澄清问题' })).toBeDisabled(); expect(mock.writes).toHaveLength(0);
  mock.failReads = false; await page.getByRole('button', { name: '读取最新资产', exact: true }).click();
  await expect(page.getByRole('button', { name: '创建并生成澄清问题' })).toBeEnabled();
  await page.getByRole('button', { name: /Python CSV 数据处理.*confirmed/ }).click();
  await expect(page.getByLabel('节点 2 名称', { exact: true })).toHaveValue('暂停期间保留编辑');
});

test('已有子节点改挂，删除父节点后显式重新连接，不隐式删子树', async ({ page }) => {
  const mock = new MockApi(page); mock.seedGraph(); await mock.install(); await page.goto(`/?goal=${goalId}`);
  await page.getByLabel('关系 2 来源', { exact: true }).selectOption('n2');
  await page.getByRole('button', { name: '保存候选图谱' }).click();
  await expect(page.getByText('完整图谱已保存。', { exact: true })).toBeVisible();
  expect(mock.graph!.edges[1].source).toBe(mock.graph!.nodes[1].id);
  await page.getByRole('button', { name: '移除节点 2 及关联边', exact: true }).click();
  await expect(page.getByLabel('节点 2 名称', { exact: true })).toHaveValue('CSV 读取');
  await page.getByRole('button', { name: '添加关系', exact: true }).click();
  await page.getByRole('button', { name: '保存候选图谱' }).click();
  await expect(page.getByText('完整图谱已保存。', { exact: true })).toBeVisible();
  expect(mock.graph!.nodes.map(node => node.label)).toEqual(['CSV 数据处理', 'CSV 读取']);
  expect(mock.graph!.edges).toEqual([{ source: mock.graph!.nodes[0].id, target: mock.graph!.nodes[1].id, relation: 'contains' }]);
});

for (const action of ['切换目标', '读取更新修订'] as const) {
  test(`生成后的迟到目标GET不覆盖${action}后的资产`, async ({ page }) => {
    const mock = new MockApi(page); mock.goal = confirmedGoal(); await mock.install();
    const otherId = 'f6ec7f49-7c36-4bb4-ab12-662c79a3b743';
    const otherGraph = candidateGraph(); otherGraph.id = 'df9a278a-d3d3-4a20-bfcb-d64f3e6f3567'; otherGraph.goal_id = otherId; otherGraph.nodes[0].label = 'Graph B';
    const otherGoal = { ...confirmedGoal(), id: otherId, graph_id: otherGraph.id, values: { ...confirmedGoal().values!, title: 'Goal B' } };
    let release!: () => void; const gate = new Promise<void>(resolve => { release = resolve; });
    let started!: () => void; const waiting = new Promise<void>(resolve => { started = resolve; });
    let delayed = false;
    await page.route('http://127.0.0.1:8000/api/v1/**', async route => {
      const url = new URL(route.request().url()); const path = url.pathname.replace('/api/v1', '');
      const reply = (body: unknown) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
      if (route.request().method() !== 'GET') return route.fallback();
      if (path === '/goals') return reply({ items: [mock.goal, otherGoal] });
      if (path === `/goals/${otherId}`) return reply(otherGoal);
      if (path === '/graphs' && url.searchParams.get('goal_id') === otherId) return reply({ items: [otherGraph] });
      if (path === `/goals/${goalId}` && mock.graph && !delayed) {
        delayed = true; const snapshot = structuredClone(mock.goal); started(); await gate; return reply(snapshot);
      }
      return route.fallback();
    });
    await page.goto(`/?goal=${goalId}`);
    await page.getByRole('button', { name: '生成候选图谱', exact: true }).click(); await waiting;
    await expect(page.getByRole('button', { name: '读取最新资产', exact: true })).toBeEnabled();
    let expectedId = otherId;
    if (action === '切换目标') {
      await page.getByRole('button', { name: /Goal B.*confirmed/ }).click();
      await expect(page.getByLabel('节点 1 名称', { exact: true })).toHaveValue('Graph B');
    } else {
      expectedId = goalId; mock.goal!.revision = 5; mock.goal!.values!.title = 'Goal A 最新修订';
      await page.getByRole('button', { name: '读取最新资产', exact: true }).click();
      await expect(page.getByRole('heading', { name: '已确认目标 · r5', exact: true })).toBeVisible();
    }
    const response = page.waitForResponse(r => r.url().endsWith(`/goals/${goalId}`)); release(); await response;
    // Wait for the delivered response and React render, not an arbitrary sleep.
    await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
    await expect(page.locator('.breadcrumb code')).toHaveText(expectedId);
    await expect(page).toHaveURL(new RegExp(`goal=${expectedId}`));
    if (action === '切换目标') {
      await expect(page.locator('.summary')).toContainText('Goal B');
      await expect(page.getByLabel('节点 1 名称', { exact: true })).toHaveValue('Graph B');
    } else {
      await expect(page.getByRole('heading', { name: '已确认目标 · r5', exact: true })).toBeVisible();
      await expect(page.locator('.summary')).toContainText('Goal A 最新修订');
    }
  });
}

test('409对照与历史展示重要性和完整位置，人工合并不会覆盖远端字段', async ({ page }) => {
  const mock = new MockApi(page); mock.seedGraph(); await mock.install(); await page.goto(`/?goal=${goalId}`);
  await page.getByLabel('节点 2 描述', { exact: true }).fill('保留本地描述');
  mock.graph!.nodes[1].target_weight = 99; mock.graph!.nodes[1].position = { x: 1234, y: 5678 }; mock.conflictNext = true;
  await page.getByRole('button', { name: '保存候选图谱', exact: true }).click();
  await page.getByText('对照最新已保存图谱', { exact: true }).click();
  const latest = page.locator('details').filter({ has: page.getByText('对照最新已保存图谱', { exact: true }) });
  await expect(latest).toContainText('重要性：99'); await expect(latest).toContainText('位置：x=1234，y=5678');
  await expect(latest).toContainText('位置：未设定');
  await expect(page.getByLabel('节点 2 描述', { exact: true })).toHaveValue('保留本地描述');
  await page.getByLabel('节点 2 重要性', { exact: true }).fill('99'); await page.getByLabel('节点 2 设置位置', { exact: true }).check();
  await page.getByLabel('节点 2 x', { exact: true }).fill('1234'); await page.getByLabel('节点 2 y', { exact: true }).fill('5678');
  await page.getByRole('button', { name: '已人工合并，采用最新修订号' }).click();
  await page.getByRole('button', { name: '保存候选图谱', exact: true }).click();
  await expect(page.getByText('完整图谱已保存。', { exact: true })).toBeVisible();
  expect(mock.graph!.nodes[1]).toMatchObject({ description: '保留本地描述', target_weight: 99, position: { x: 1234, y: 5678 } });
  await page.getByText('历史修订（只读，不回滚）', { exact: true }).click();
  await page.getByLabel('历史修订号', { exact: true }).fill('3'); await page.getByRole('button', { name: '读取历史', exact: true }).click();
  const history = page.locator('details').filter({ has: page.getByText('历史修订（只读，不回滚）', { exact: true }) });
  await expect(history).toContainText('重要性：99'); await expect(history).toContainText('位置：x=1234，y=5678');
});

test('独立复验：生成后迟到GET不能退出创建新目标页面或抹去新输入', async ({ page }) => {
  const mock = new MockApi(page); mock.goal = confirmedGoal(); await mock.install();
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let started!: () => void;
  const waiting = new Promise<void>(resolve => { started = resolve; });
  let delayed = false;
  await page.route('http://127.0.0.1:8000/api/v1/**', async route => {
    if (route.request().method() === 'GET' && route.request().url().endsWith(`/goals/${goalId}`) && mock.graph && !delayed) {
      delayed = true; const snapshot = structuredClone(mock.goal); started(); await gate;
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify(snapshot) });
    }
    return route.fallback();
  });
  await page.goto(`/?goal=${goalId}`);
  await page.getByRole('button', { name: '生成候选图谱', exact: true }).click(); await waiting;
  await page.getByRole('button', { name: '创建新目标', exact: true }).click();
  await page.getByLabel('你想学什么，最终能做到什么？').fill('保留下一目标输入');
  const response = page.waitForResponse(r => r.url().endsWith(`/goals/${goalId}`));
  release(); await (await response).finished();
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  await expect(page.getByRole('heading', { name: '创建学习目标', exact: true })).toBeVisible();
  await expect(page.getByLabel('你想学什么，最终能做到什么？')).toHaveValue('保留下一目标输入');
  await expect(page.locator('.breadcrumb')).toHaveCount(0);
  expect(new URL(page.url()).searchParams.has('goal')).toBe(false);
  expect(mock.writes).toHaveLength(1);
});
