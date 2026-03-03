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
  '': '#6b7280',
  run: '#f59e0b',
  running: '#2563eb',
  ran: '#16a34a',
  fail: '#dc2626'
};

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
    nodes: data.nodes.map((node) => ({
      id: node.id,
      type: 'workflowNode',
      position: { x: toNum(node.x), y: toNum(node.y) },
      data: {
        label: node.label || node.id,
        command: node.command ?? node.label ?? '',
        status: node.status ?? '',
        stdout: node.stdout,
        stderr: node.stderr,
        log: node.log
      }
    })),
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
