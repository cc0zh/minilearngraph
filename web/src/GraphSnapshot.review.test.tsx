import { afterEach, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { GraphSnapshot } from './GraphEditor';
import { candidateGraph } from './testFixtures';

afterEach(cleanup);

it('shows weight bounds, null/zero/signed coordinates and IDs for same-label endpoints', () => {
  const graph = candidateGraph();
  graph.nodes[0] = { ...graph.nodes[0], label: '同名节点', target_weight: 1, position: { x: 0, y: -100000 } };
  graph.nodes[1] = { ...graph.nodes[1], label: '同名节点', target_weight: 100, position: { x: 100000, y: -0.5 } };
  graph.nodes[2] = { ...graph.nodes[2], target_weight: 50, position: null };
  render(<GraphSnapshot graph={graph} />);
  expect(screen.getByText('重要性：1 · 位置：x=0，y=-100000')).toBeTruthy();
  expect(screen.getByText('重要性：100 · 位置：x=100000，y=-0.5')).toBeTruthy();
  expect(screen.getByText('重要性：50 · 位置：未设定')).toBeTruthy();
  for (const edge of graph.edges) {
    expect(screen.getByText(`${edge.source} → ${edge.target}`)).toBeTruthy();
  }
  expect(screen.getByText('同名节点 → 同名节点 · 包含（父→子）')).toBeTruthy();
});
