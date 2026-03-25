import { Edge, Node } from 'reactflow';
import { BackendNodeLinkGraph, WorkforceStatus, WorkflowNodeData } from './types';

const statusLabelMap: Record<WorkforceStatus, string> = {
  '': 'idle',
  run: 'queued',
  running: 'running',
  ran: 'complete',
  fail: 'failed'
};

export const statusColorMap: Record<WorkforceStatus, string> = {
  '': '#37474F',
  run: '#0D47A1',
  running: '#0D47A1',
  ran: '#1B5E20',
  fail: '#B71C1C'
};

export function nodeWidthForLabel(label: string): number {
  const textWidth = Math.ceil(label.length * 7.2);
  return Math.max(42, textWidth + 16);
}

const toNum = (value: string | number | undefined) => {
  if (typeof value === 'number') return value;
  if (typeof value === 'string') {
    const parsed = parseFloat(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
};

export function adaptBackendGraph(data: BackendNodeLinkGraph): {
  nodes: Node<WorkflowNodeData>[];
  edges: Edge[];
} {
  return {
    nodes: data.nodes.map((node) => {
      const label = node.command ?? node.label ?? node.id;
      return {
        id: node.id,
        type: 'workflowNode',
        position: { x: toNum(node.x), y: toNum(node.y) },
        style: { width: nodeWidthForLabel(label) },
        data: {
          label,
          command: node.command ?? node.label ?? '',
          status: node.status ?? '',
          stdout: node.stdout,
          stderr: node.stderr,
          log: node.log
        }
      };
    }),
    edges: data.links.map((link, index) => ({
      id: link.id ?? `${link.source}-${link.target}-${index}`,
      source: String(link.source),
      target: String(link.target),
      animated: link.status === 'to_run'
    }))
  };
}

export function workforceStatusLabel(status: WorkforceStatus): string {
  return statusLabelMap[status];
}
