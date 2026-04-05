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

const NODE_CHAR_WIDTH = 7.2;
const NODE_LINE_HEIGHT = 16;
const NODE_HORIZONTAL_PADDING = 16;
const NODE_VERTICAL_PADDING = 12;
const NODE_MIN_WIDTH = 42;
const NODE_MIN_HEIGHT = 36;

function normalizeLabelLines(label: string): string[] {
  const normalized = label.replace(/\r\n?/g, '\n');
  const lines = normalized.split('\n');
  return lines.length > 0 ? lines : [''];
}

export function nodeDimensionsForLabel(label: string): { width: number; height: number } {
  const lines = normalizeLabelLines(label);
  const longestLineLength = lines.reduce((max, line) => Math.max(max, line.length), 0);
  const width = Math.max(NODE_MIN_WIDTH, Math.ceil(longestLineLength * NODE_CHAR_WIDTH) + NODE_HORIZONTAL_PADDING);
  const height = Math.max(NODE_MIN_HEIGHT, lines.length * NODE_LINE_HEIGHT + NODE_VERTICAL_PADDING);
  return { width, height };
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
        style: nodeDimensionsForLabel(label),
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
