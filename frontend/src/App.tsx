import { MouseEvent, useCallback, useEffect, useMemo, useState } from 'react';
import ReactFlow, {
  addEdge,
  Background,
  Connection,
  Controls,
  Edge,
  Handle,
  MiniMap,
  Node,
  NodeProps,
  Position,
  ReactFlowProvider,
  SelectionMode,
  useEdgesState,
  useNodesState
} from 'reactflow';
import 'reactflow/dist/style.css';
import { adaptBackendGraph, statusColorMap, workforceStatusLabel } from './graph/adapters';
import { BackendNodeLinkGraph, WorkflowNodeData, WorkforceStatus } from './graph/types';
import { NodeInspector } from './components/NodeInspector';
import { LogPanel } from './components/LogPanel';
import { CanvasContextMenu, ContextMenuItem } from './components/CanvasContextMenu';

const seededGraph: BackendNodeLinkGraph = {
  nodes: [
    { id: 'n1', label: 'echo setup', x: 80, y: 80, status: 'ran', stdout: 'setup complete' },
    { id: 'n2', label: 'python job.py', x: 360, y: 200, status: 'running', stdout: 'epoch 1...' },
    { id: 'n3', label: 'echo done', x: 660, y: 80, status: 'run' }
  ],
  links: [
    { source: 'n1', target: 'n2', status: 'to_run' },
    { source: 'n2', target: 'n3' }
  ]
};

type BridgeRequest = { id: string; method: string; params: Record<string, unknown>; protocolVersion: string };
type BridgeResponse<T = Record<string, unknown>> = {
  id: string;
  ok: boolean;
  result?: T;
  error?: { type: string; message: string };
};

declare global {
  interface Window {
    workforceBridge?: {
      handleRequest?: (request: BridgeRequest) => Promise<BridgeResponse> | BridgeResponse;
    };
  }
}

async function bridgeCall<T = Record<string, unknown>>(method: string, params: Record<string, unknown> = {}): Promise<T> {
  const request: BridgeRequest = {
    id: `${method}-${Date.now()}`,
    method,
    params,
    protocolVersion: '1.0'
  };
  const handler = window.workforceBridge?.handleRequest;
  if (!handler) {
    throw new Error('Bridge API is unavailable in this environment.');
  }

  const response = await Promise.resolve(handler(request));
  if (!response.ok) {
    throw new Error(response.error?.message ?? `Bridge request failed for ${method}`);
  }
  return (response.result ?? {}) as T;
}

function WorkflowNode({ data, selected }: NodeProps<WorkflowNodeData>) {
  const color = statusColorMap[data.status];
  return (
    <div
      style={{
        border: selected ? '2px solid #60a5fa' : '1px solid #334155',
        borderRadius: 10,
        background: '#111827',
        color: '#f9fafb',
        minWidth: 190,
        padding: 10
      }}
    >
      <Handle type="target" position={Position.Left} />
      <div style={{ fontWeight: 600 }}>{data.label}</div>
      <div style={{ display: 'inline-flex', marginTop: 8, gap: 6, alignItems: 'center' }}>
        <span style={{ width: 9, height: 9, borderRadius: 9999, background: color }} />
        <span style={{ fontSize: 12, color: '#cbd5e1' }}>{workforceStatusLabel(data.status)}</span>
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

function AppContent() {
  const initial = useMemo(() => adaptBackendGraph(seededGraph), []);
  const [nodes, setNodes, onNodesChange] = useNodesState<WorkflowNodeData>(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);
  const [selectedNodeId, setSelectedNodeId] = useState<string | undefined>();
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; nodeId?: string } | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>('');
  const [currentPath, setCurrentPath] = useState<string | undefined>();

  const refreshGraph = useCallback(async () => {
    try {
      const graph = await bridgeCall<BackendNodeLinkGraph>('getGraph');
      const adapted = adaptBackendGraph(graph);
      setNodes(adapted.nodes);
      setEdges(adapted.edges);
    } catch {
      // Ignore bridge fetch in dev mode; seeded graph remains visible.
    }
  }, [setEdges, setNodes]);

  useEffect(() => {
    void refreshGraph();
  }, [refreshGraph]);

  const selectedNode = useMemo(
    () => nodes.find((node) => node.id === selectedNodeId),
    [nodes, selectedNodeId]
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((existing) => addEdge({ ...connection, animated: false }, existing));
    },
    [setEdges]
  );

  const onNodeContextMenu = useCallback((event: MouseEvent, node: Node<WorkflowNodeData>) => {
    event.preventDefault();
    setSelectedNodeId(node.id);
    setContextMenu({ x: event.clientX, y: event.clientY, nodeId: node.id });
  }, []);

  const onPaneContextMenu = useCallback((event: MouseEvent) => {
    event.preventDefault();
    setContextMenu({ x: event.clientX, y: event.clientY });
  }, []);

  const handleOpenWorkflow = useCallback(async () => {
    try {
      const result = await bridgeCall<{ cancelled?: boolean; path?: string }>('openWorkflowDialog', {
        current_path: currentPath
      });
      if (result.cancelled) return;
      if (result.path) setCurrentPath(result.path);
      await refreshGraph();
      setStatusMessage('Opened workflow successfully.');
    } catch (error) {
      setStatusMessage(`Open failed: ${error instanceof Error ? error.message : 'unknown error'}`);
    }
  }, [currentPath, refreshGraph]);

  const handleSaveWorkflowAs = useCallback(async () => {
    try {
      const result = await bridgeCall<{ cancelled?: boolean; new_path?: string }>('saveWorkflowAsDialog', {
        current_path: currentPath
      });
      if (result.cancelled) return;
      if (result.new_path) setCurrentPath(result.new_path);
      await refreshGraph();
      setStatusMessage('Saved workflow copy successfully.');
    } catch (error) {
      setStatusMessage(`Save As failed: ${error instanceof Error ? error.message : 'unknown error'}`);
    }
  }, [currentPath, refreshGraph]);

  const menuItems: ContextMenuItem[] = useMemo(() => {
    if (!contextMenu) return [];

    if (contextMenu.nodeId) {
      const setNodeStatus = (status: WorkforceStatus) =>
        setNodes((existing) =>
          existing.map((node) =>
            node.id === contextMenu.nodeId ? { ...node, data: { ...node.data, status } } : node
          )
        );

      return [
        { id: 'queued', label: 'Set status: queued', onSelect: () => setNodeStatus('run') },
        { id: 'running', label: 'Set status: running', onSelect: () => setNodeStatus('running') },
        { id: 'complete', label: 'Set status: complete', onSelect: () => setNodeStatus('ran') },
        { id: 'failed', label: 'Set status: failed', onSelect: () => setNodeStatus('fail') },
        {
          id: 'delete-node',
          label: 'Delete node',
          onSelect: () => {
            setNodes((existing) => existing.filter((node) => node.id !== contextMenu.nodeId));
            setEdges((existing) =>
              existing.filter((edge) => edge.source !== contextMenu.nodeId && edge.target !== contextMenu.nodeId)
            );
            if (selectedNodeId === contextMenu.nodeId) setSelectedNodeId(undefined);
          }
        }
      ];
    }

    return [
      {
        id: 'add-node',
        label: 'Add node',
        onSelect: () => {
          const id = crypto.randomUUID();
          setNodes((existing) => [
            ...existing,
            {
              id,
              type: 'workflowNode',
              position: { x: 200, y: 180 },
              data: { label: `node-${existing.length + 1}`, command: '', prefix: '', suffix: '', status: '' }
            }
          ]);
        }
      },
      { id: 'clear-selection', label: 'Clear selection', onSelect: () => setSelectedNodeId(undefined) }
    ];
  }, [contextMenu, selectedNodeId, setEdges, setNodes]);

  return (
    <div style={{ height: '100vh', display: 'grid', gridTemplateRows: '52px 1fr 220px', background: '#020617' }}>
      <header
        style={{
          borderBottom: '1px solid #1e293b',
          color: '#f8fafc',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 16px'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <strong>Workforce Editor (Dev)</strong>
          <div style={{ display: 'inline-flex', gap: 8 }}>
            <button onClick={() => void handleOpenWorkflow()}>File ▸ Open</button>
            <button onClick={() => void handleSaveWorkflowAs()}>File ▸ Save As</button>
          </div>
        </div>
        <span style={{ fontSize: 12, color: '#94a3b8' }}>{statusMessage || 'Drag • Connect • Right click • Multi-select'}</span>
      </header>

      <main style={{ display: 'grid', gridTemplateColumns: '1fr 320px' }}>
        <section style={{ borderRight: '1px solid #1e293b' }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={(_, node) => setSelectedNodeId(node.id)}
            onPaneClick={() => setSelectedNodeId(undefined)}
            onNodeContextMenu={onNodeContextMenu}
            onPaneContextMenu={onPaneContextMenu}
            fitView
            nodeTypes={{ workflowNode: WorkflowNode }}
            panOnDrag
            zoomOnScroll
            selectionOnDrag
            selectionMode={SelectionMode.Partial}
            multiSelectionKeyCode={['Meta', 'Control']}
          >
            <Background gap={18} color="#334155" />
            <Controls />
            <MiniMap pannable zoomable style={{ background: '#0f172a' }} />
          </ReactFlow>
        </section>

        <aside style={{ padding: 14, color: '#e2e8f0' }}>
          <NodeInspector
            node={selectedNode}
            onUpdate={(updates) => {
              if (!selectedNodeId) return;
              setNodes((existing) =>
                existing.map((node) =>
                  node.id === selectedNodeId ? { ...node, data: { ...node.data, ...updates } } : node
                )
              );
            }}
          />
        </aside>
      </main>

      <section style={{ borderTop: '1px solid #1e293b', padding: '10px 14px', color: '#e2e8f0' }}>
        <LogPanel node={selectedNode} />
      </section>

      {contextMenu && <CanvasContextMenu x={contextMenu.x} y={contextMenu.y} items={menuItems} onClose={() => setContextMenu(null)} />}
    </div>
  );
}

export default function App() {
  return (
    <ReactFlowProvider>
      <AppContent />
    </ReactFlowProvider>
  );
}
