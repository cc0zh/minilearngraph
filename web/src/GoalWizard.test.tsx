import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { GoalSummary, GoalWizard } from './GoalWizard';
import { confirmedGoal, readyGoal } from './testFixtures';

beforeEach(() => sessionStorage.clear());
afterEach(cleanup);
it('shows dynamic reasons and skip assumption, requires review, rejects disallowed answer controls', async () => {
  const confirm = vi.fn().mockResolvedValue(true); const user = userEvent.setup();
  render(<GoalWizard goal={readyGoal()} busy={false} issues={[]} onConfirm={confirm} />);
  const customQuestion = screen.getByRole('group', { name: '你使用什么工具？' });
  expect(within(customQuestion).queryByLabelText('跳过并采用默认假设')).toBe(null);
  const choiceQuestion = screen.getByRole('group', { name: '目标输出是什么？' });
  expect(within(choiceQuestion).queryByLabelText('自定义回答')).toBe(null);
  await user.click(screen.getByLabelText('跳过并采用默认假设'));
  await user.click(within(customQuestion).getByLabelText('自定义回答'));
  await user.type(screen.getByLabelText('自定义：你使用什么工具？'), 'VS Code');
  await user.click(screen.getByLabelText('清理后的 CSV 文件'));
  expect((screen.getByRole('button', { name: '确认目标' }) as HTMLButtonElement).disabled).toBe(true);
  await user.click(screen.getByLabelText('我已审阅回答、目标事实及采用的假设，明确确认目标'));
  await user.click(screen.getByRole('button', { name: '确认目标' }));
  expect(confirm).toHaveBeenCalledWith(expect.objectContaining({ confirmed: true, expected_revision: 2, answers: [{ key: 'loop_background', kind: 'skip', value: null }, { key: 'csv_tooling', kind: 'custom', value: 'VS Code' }, { key: 'output_format', kind: 'choice', value: 'csv' }], accepted_suggested_assumption_keys: [] }));
});

it('locates a GoalValues 422 issue on its labeled field', () => {
  render(<GoalWizard goal={readyGoal()} busy={false} onConfirm={vi.fn()} issues={[{ path: ['body', 'values', 'deadline_at'], code: 'type', message: '需要有效时间', node_ids: [], edge_indexes: [] }]} />);
  const field = screen.getByLabelText('明确截止时间（带时区）');
  expect(field.getAttribute('aria-invalid')).toBe('true');
  expect(field.closest('label')?.classList.contains('invalid')).toBe(true);
  expect(screen.getByLabelText('目标标题').getAttribute('aria-invalid')).toBe('false');
});

it('shows custom answer text without resolving it as an option ID', () => {
  const goal = confirmedGoal(); goal.answers = [{ key: 'loop_background', kind: 'custom', value: 'yes' }];
  render(<GoalSummary goal={goal} />);
  expect(screen.getByText('yes')).toBeTruthy(); expect(screen.queryByText('可以独立完成')).toBe(null);
});
