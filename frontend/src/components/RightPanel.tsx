import { Node } from 'reactflow';
import { WorkflowNodeData } from '../graph/types';
import { NodeInspector } from './NodeInspector';
import { LogPanel } from './LogPanel';

interface RightPanelProps {
  node?: Node<WorkflowNodeData>;
  onUpdate: (updates: Partial<WorkflowNodeData>) => void;
}

export function RightPanel({ node, onUpdate }: RightPanelProps) {
  return (
    <div style={{ display: 'grid', gridTemplateRows: '1fr 1fr', height: '100%' }}>
      <div style={{ padding: 14, borderBottom: '1px solid #1e293b' }}>
        <NodeInspector node={node} onUpdate={onUpdate} />
      </div>
      <div style={{ padding: '10px 14px', borderTop: '1px solid #1e293b' }}>
        <LogPanel node={node} />
      </div>
    </div>
  );
}