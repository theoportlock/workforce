import { Node } from 'reactflow';
import { WorkflowNodeData } from '../graph/types';

interface LogPanelProps {
  node?: Node<WorkflowNodeData>;
}

export function LogPanel({ node }: LogPanelProps) {
  const output =
    node?.data.log ||
    [
      node?.data.stdout ? `STDOUT:\n${node.data.stdout}` : '',
      node?.data.stderr ? `STDERR:\n${node.data.stderr}` : ''
    ]
      .filter(Boolean)
      .join('\n\n') ||
    'Select a node to view runtime output.';

  return (
    <div style={{ height: '100%', display: 'grid', gridTemplateRows: 'auto 1fr' }}>
      <h3 style={{ margin: 0 }}>Node Output</h3>
      <pre
        style={{
          background: '#0f172a',
          color: '#e5e7eb',
          borderRadius: 8,
          marginTop: 8,
          padding: 10,
          overflow: 'auto'
        }}
      >
        {output}
      </pre>
    </div>
  );
}
