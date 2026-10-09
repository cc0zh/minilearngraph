import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { GraphEditor } from './GraphEditor';
import { candidateGraph } from './testFixtures';

beforeEach(() => sessionStorage.clear());
afterEach(cleanup);
const callbacks = () => ({ onSave: vi.fn().mockResolvedValue(null), onPublish: vi.fn().mockResolvedValue(null), onRefresh: vi.fn() });

it('requires saved content and fresh explicit review before publication', async () => {
  const user = userEvent.setup(); const props = callbacks();
  render(<GraphEditor graph={candidateGraph()} busy={false} issues={[]} {...props} />);
  const publish = screen.getByRole('button', { name: '确认发布图谱' }) as HTMLButtonElement;
  expect(publish.disabled).toBe(true);
  await user.click(screen.getByLabelText('我已审核已保存图谱，明确确认发布')); expect(publish.disabled).toBe(false);
  await user.type(screen.getByLabelText('节点 2 名称'), '本地编辑'); expect(publish.disabled).toBe(true);
  await user.click(publish); expect(props.onPublish).not.toHaveBeenCalled();
});

it('keeps edits on a new revision and blocks save until explicit manual merge', async () => {
  const user = userEvent.setup(); const props = callbacks(); const graph = candidateGraph();
  const view = render(<GraphEditor graph={graph} busy={false} issues={[]} {...props} />);
  await user.clear(screen.getByLabelText('节点 2 名称')); await user.type(screen.getByLabelText('节点 2 名称'), '我的循环');
  view.rerender(<GraphEditor graph={{ ...graph, revision: 3 }} busy={false} issues={[]} {...props} />);
  expect((screen.getByLabelText('节点 2 名称') as HTMLInputElement).value).toBe('我的循环');
  expect((screen.getByRole('button', { name: '保存候选图谱' }) as HTMLButtonElement).disabled).toBe(true);
  await user.click(screen.getByRole('button', { name: '已人工合并，采用最新修订号' }));
  await user.click(screen.getByRole('button', { name: '保存候选图谱' }));
  expect(props.onSave).toHaveBeenCalledWith(expect.objectContaining({ nodes: expect.arrayContaining([expect.objectContaining({ label: '我的循环' })]) }), undefined);
});

it('requires formal reason and clears confirmation after changes', async () => {
  const user = userEvent.setup(); const props = callbacks();
  render(<GraphEditor graph={{ ...candidateGraph(), status: 'published' }} busy={false} issues={[]} {...props} />);
  const save = screen.getByRole('button', { name: '确认正式修订' }) as HTMLButtonElement;
  expect(save.disabled).toBe(true);
  await user.type(screen.getByLabelText('正式修订理由'), '补充循环边界');
  await user.click(screen.getByLabelText('我已审阅全部节点与关系，明确确认此次正式修订')); expect(save.disabled).toBe(false);
  await user.type(screen.getByLabelText('节点 2 描述'), '补充'); expect(save.disabled).toBe(true);
  await user.click(screen.getByLabelText('我已审阅全部节点与关系，明确确认此次正式修订')); await user.click(save);
  expect(props.onSave).toHaveBeenCalledWith(expect.any(Object), '补充循环边界'); expect(props.onPublish).not.toHaveBeenCalled();
});
