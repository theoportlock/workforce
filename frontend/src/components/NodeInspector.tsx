import { ChangeEvent } from 'react';
import { Node } from 'reactflow';
import { WorkflowNodeData } from '../graph/types';

interface NodeInspectorProps {
  node?: Node<WorkflowNodeData>;
  onUpdate: (updates: Partial<WorkflowNodeData>) => void;
}

export function NodeInspector({ node, onUpdate }: NodeInspectorProps) {
  if (!node) {
    return <div style={{ color: '#9ca3af' }}>Select a node to inspect its command details.</div>;
  }

  const handleText =
    (field: keyof Pick<WorkflowNodeData, 'command' | 'prefix' | 'suffix'>) =>
    (event: ChangeEvent<HTMLTextAreaElement>) => {
      onUpdate({ [field]: event.target.value });
    };

  return (
    <div style={{ display: 'grid', gap: 10 }}>
      <h3 style={{ margin: 0 }}>Node Inspector</h3>
      <div style={{ fontSize: 12, color: '#9ca3af' }}>Node ID: {node.id}</div>

      <label>
        <div>Command</div>
        <textarea rows={4} value={node.data.command} onChange={handleText('command')} style={{ width: '100%' }} />
      </label>

      <label>
        <div>Prefix</div>
        <textarea rows={2} value={node.data.prefix} onChange={handleText('prefix')} style={{ width: '100%' }} />
      </label>

      <label>
        <div>Suffix</div>
        <textarea rows={2} value={node.data.suffix} onChange={handleText('suffix')} style={{ width: '100%' }} />
      </label>
    </div>
  );
}
