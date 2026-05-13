import { Node } from 'reactflow';
import { WorkflowNodeData } from '../graph/types';
import { LogPanel } from './LogPanel';

interface RightPanelProps {
  node?: Node<WorkflowNodeData>;
  nodeLog?: string;
  isNodeLogLoading?: boolean;
}

export function RightPanel({ node, nodeLog, isNodeLogLoading }: RightPanelProps) {
  return (
    <div style={{ height: '100%', minHeight: 0, overflow: 'hidden', padding: '10px 14px' }}>
      <LogPanel node={node} nodeLog={nodeLog} isLoading={isNodeLogLoading} />
    </div>
  );
}
