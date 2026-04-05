import { Node } from 'reactflow';
import { WorkflowNodeData } from '../graph/types';

interface LogPanelProps {
  node?: Node<WorkflowNodeData>;
  nodeLog?: string;
  isLoading?: boolean;
}

export function LogPanel({ node, nodeLog, isLoading = false }: LogPanelProps) {
  const output = isLoading
    ? 'Loading node output...'
    : nodeLog ||
      node?.data.log ||
    [
      node?.data.stdout ? `STDOUT:\n${node.data.stdout}` : '',
      node?.data.stderr ? `STDERR:\n${node.data.stderr}` : ''
    ]
      .filter(Boolean)
      .join('\n\n') ||
      'Select a node to view runtime output.';

  return (
    <div style={{ height: '100%', display: 'grid', gridTemplateRows: 'auto 1fr', minHeight: 0, gap: 8 }}>
      <h3 style={{ margin: 0 }}>Node Output</h3>
      <pre
        style={{
          background: '#0f172a',
          color: '#e5e7eb',
          borderRadius: 8,
          margin: 0,
          padding: 10,
          overflow: 'auto',
          minHeight: 0,
          height: '100%',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word'
        }}
      >
        {output}
      </pre>
    </div>
  );
}
