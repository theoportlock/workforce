import { Node } from 'reactflow';
import { WorkflowNodeData } from '../graph/types';
import { NodeInspector } from './NodeInspector';
import { LogPanel } from './LogPanel';

interface RightPanelProps {
  node?: Node<WorkflowNodeData>;
  nodeLog?: string;
  isNodeLogLoading?: boolean;
  onUpdate: (updates: Partial<WorkflowNodeData>) => void;
}

export function RightPanel({ node, nodeLog, isNodeLogLoading, onUpdate }: RightPanelProps) {
  return (
    <div style={{ display: 'grid', gridTemplateRows: '1fr 1fr', height: '100%', minHeight: 0, overflow: 'hidden' }}>
      <div style={{ padding: 14, borderBottom: '1px solid #1e293b', minHeight: 0, overflow: 'auto' }}>
        <NodeInspector node={node} onUpdate={onUpdate} />
      </div>
      <div style={{ padding: '10px 14px', borderTop: '1px solid #1e293b', minHeight: 0 }}>
        <LogPanel node={node} nodeLog={nodeLog} isLoading={isNodeLogLoading} />
      </div>
    </div>
  );
}
