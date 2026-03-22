import { Node } from 'reactflow';
import { WorkflowNodeData } from '../graph/types';

interface LogPanelProps {
  node: Node<WorkflowNodeData>;
}

export function LogPanel({ node }: LogPanelProps) {
  const output =
    node.data.log ||
    [
      node.data.stdout ? `STDOUT:\n${node.data.stdout}` : '',
      node.data.stderr ? `STDERR:\n${node.data.stderr}` : ''
    ]
      .filter(Boolean)
      .join('\n\n') ||
    'No runtime output yet.';

  return (
    <div style={{ height: '100%', display: 'grid', gridTemplateRows: 'auto 1fr', gap: 8 }}>
      <h3 style={{ margin: 0, fontSize: 18 }}>Node Output</h3>
      <pre
        style={{
          background: '#0f172a',
          color: '#e5e7eb',
          border: '1px solid #334155',
          borderRadius: 8,
          margin: 0,
          padding: 10,
          overflow: 'auto',
          minHeight: 180,
          maxHeight: '40vh',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word'
        }}
      >
        {output}
      </pre>
    </div>
  );
}
