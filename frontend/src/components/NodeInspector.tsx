import { ChangeEvent } from 'react';
import { Node } from 'reactflow';
import { WorkflowNodeData } from '../graph/types';

interface NodeInspectorProps {
  node: Node<WorkflowNodeData>;
  onUpdate: (updates: Partial<WorkflowNodeData>) => void;
}

export function NodeInspector({ node, onUpdate }: NodeInspectorProps) {
  const handleText =
    (field: keyof Pick<WorkflowNodeData, 'command'>) =>
    (event: ChangeEvent<HTMLTextAreaElement>) => {
      onUpdate({ [field]: event.target.value });
    };

  return (
    <div style={{ display: 'grid', gap: 10 }}>
      <div>
        <h3 style={{ margin: 0, fontSize: 18 }}>Node Details</h3>
        <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>Node ID: {node.id}</div>
      </div>

      <label style={{ display: 'grid', gap: 6 }}>
        <div style={{ fontSize: 13, fontWeight: 600 }}>Command</div>
        <textarea
          rows={6}
          value={node.data.command}
          onChange={handleText('command')}
          style={{
            width: '100%',
            resize: 'vertical',
            background: '#0f172a',
            color: '#e2e8f0',
            border: '1px solid #334155',
            borderRadius: 8,
            padding: 10,
            fontFamily: 'inherit'
          }}
        />
      </label>
    </div>
  );
}
