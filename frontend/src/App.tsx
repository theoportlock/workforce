import { MouseEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
import { connectWorkspaceSocket, getLaunchContext, SocketLike } from './runtime/socketClient';

type GraphUpdatePayload = BackendNodeLinkGraph & {
  op?: string;
};

type NodeStatusPayload = {
  node_id?: string;
  status?: WorkforceStatus;
};

type NodeReadyPayload = {
  node_id?: string;
};

type RunCompletePayload = {
  run_id?: string;
};

type ClientConnectResult = {
  client_id?: string;
};

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
    __WORKSPACE_BASE_URL__?: string;
    workforceBridge?: {
      handleRequest?: (request: BridgeRequest) => Promise<BridgeResponse> | BridgeResponse;
    };
  }
}

function resolveWorkspaceBaseUrl(): string | null {
  if (window.__WORKSPACE_BASE_URL__) {
    return window.__WORKSPACE_BASE_URL__.replace(/\/$/, '');
  }

  const pathMatch = window.location.pathname.match(/^\/workspace\/[^/]+/);
  if (pathMatch) {
    return pathMatch[0];
  }

  return null;
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
    if (method === 'getGraph') {
      const workspaceBaseUrl = resolveWorkspaceBaseUrl();
      if (!workspaceBaseUrl) {
        throw new Error('Bridge API is unavailable and workspace URL could not be derived.');
      }

      const response = await fetch(`${workspaceBaseUrl}/get-graph`);
      if (!response.ok) {
        throw new Error(`Graph fetch failed: ${response.status}`);
      }
      return (await response.json()) as T;
    }

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
  const dragStartPositionsRef = useRef<Record<string, { x: number; y: number }>>({});

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
      if (!connection.source || !connection.target) return;
      const optimisticEdge: Edge = {
        id: `${connection.source}-${connection.target}`,
        source: connection.source,
        target: connection.target,
        sourceHandle: connection.sourceHandle,
        targetHandle: connection.targetHandle,
        animated: false
      };
      setEdges((existing) => addEdge(optimisticEdge, existing));
      void bridgeCall('addEdge', { source: connection.source, target: connection.target }).catch((error) => {
        setEdges((existing) => existing.filter((edge) => !(edge.source === optimisticEdge.source && edge.target === optimisticEdge.target)));
        setStatusMessage(`Connect failed: ${error instanceof Error ? error.message : 'unknown error'}`);
      });
    },
    [setEdges]
  );

  const onEdgesDelete = useCallback(
    (deletedEdges: Edge[]) => {
      deletedEdges.forEach((edge) => {
        void bridgeCall('removeEdge', { source: edge.source, target: edge.target }).catch((error) => {
          setEdges((existing) => addEdge({ ...edge, animated: false }, existing));
          setStatusMessage(`Disconnect failed: ${error instanceof Error ? error.message : 'unknown error'}`);
        });
      });
    },
    [setEdges]
  );

  const onNodesDelete = useCallback(
    (deletedNodes: Node<WorkflowNodeData>[]) => {
      deletedNodes.forEach((node) => {
        void bridgeCall('removeNode', { node_id: node.id }).catch((error) => {
          setNodes((existing) => [...existing, node]);
          setStatusMessage(`Delete failed: ${error instanceof Error ? error.message : 'unknown error'}`);
        });
      });
    },
    [setNodes]
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

  const onNodeDragStart = useCallback((_: MouseEvent, node: Node<WorkflowNodeData>) => {
    dragStartPositionsRef.current[node.id] = { x: node.position.x, y: node.position.y };
  }, []);

  const onNodeDragStop = useCallback(
    (_: MouseEvent, node: Node<WorkflowNodeData>) => {
      const previous = dragStartPositionsRef.current[node.id];
      void bridgeCall('updateNodePosition', {
        node_id: node.id,
        x: node.position.x,
        y: node.position.y
      }).catch((error) => {
        if (!previous) {
          void refreshGraph();
        } else {
          setNodes((existing) =>
            existing.map((entry) =>
              entry.id === node.id ? { ...entry, position: { x: previous.x, y: previous.y } } : entry
            )
          );
        }
        setStatusMessage(`Move failed: ${error instanceof Error ? error.message : 'unknown error'}`);
      });
    },
    [refreshGraph, setNodes]
  );

  const onSelectionDragStart = useCallback((_: MouseEvent, draggedNodes: Node<WorkflowNodeData>[]) => {
    draggedNodes.forEach((node) => {
      dragStartPositionsRef.current[node.id] = { x: node.position.x, y: node.position.y };
    });
  }, []);

  const onSelectionDragStop = useCallback(
    (_: MouseEvent, draggedNodes: Node<WorkflowNodeData>[]) => {
      const updates = draggedNodes.map((node) => ({ node_id: node.id, x: node.position.x, y: node.position.y }));
      void bridgeCall('updateNodePositions', { updates }).catch((error) => {
        setNodes((existing) =>
          existing.map((node) => {
            const previous = dragStartPositionsRef.current[node.id];
            if (!previous) return node;
            return { ...node, position: { x: previous.x, y: previous.y } };
          })
        );
        setStatusMessage(`Batch move failed: ${error instanceof Error ? error.message : 'unknown error'}`);
      });
    },
    [setNodes]
  );

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

  const applyGraphUpdate = useCallback(
    (payload: GraphUpdatePayload) => {
      if (payload.links) {
        const adapted = adaptBackendGraph(payload);
        setNodes(adapted.nodes);
        setEdges(adapted.edges);
        return;
      }

      if (payload.nodes?.length) {
        setNodes((existing) =>
          existing.map((node) => {
            const update = payload.nodes.find((entry) => entry.id === node.id);
            if (!update) return node;
            return {
              ...node,
              position: {
                x: typeof update.x === 'undefined' ? node.position.x : Number(update.x),
                y: typeof update.y === 'undefined' ? node.position.y : Number(update.y)
              },
              data: {
                ...node.data,
                label: update.label ?? node.data.label,
                command: update.command ?? node.data.command,
                status: update.status ?? node.data.status,
                stdout: update.stdout ?? node.data.stdout,
                stderr: update.stderr ?? node.data.stderr,
                log: update.log ?? node.data.log
              }
            };
          })
        );
      }
    },
    [setEdges, setNodes]
  );

  useEffect(() => {
    let mounted = true;
    let socketRef: SocketLike | null = null;
    let clientId: string | undefined;
    let disconnectRequested = false;

    const onGraphUpdate = (payload: GraphUpdatePayload) => applyGraphUpdate(payload);
    const onStatusChange = (payload: NodeStatusPayload) => {
      if (!payload.node_id || !payload.status) return;
      setNodes((existing) =>
        existing.map((node) =>
          node.id === payload.node_id ? { ...node, data: { ...node.data, status: payload.status ?? node.data.status } } : node
        )
      );
    };
    const onNodeReady = (payload: NodeReadyPayload) => {
      if (!payload.node_id) return;
      setNodes((existing) =>
        existing.map((node) =>
          node.id === payload.node_id && node.data.status !== 'running'
            ? { ...node, data: { ...node.data, status: 'run' } }
            : node
        )
      );
    };
    const onRunComplete = (payload: RunCompletePayload) => {
      setStatusMessage(payload.run_id ? `Run ${payload.run_id} complete.` : 'Run complete.');
      void refreshGraph();
    };

    const disconnectClientBestEffort = () => {
      if (disconnectRequested || !clientId) return;
      disconnectRequested = true;
      void bridgeCall('clientDisconnect', { client_type: 'gui', client_id: clientId }).catch(() => {
        // Best-effort disconnect path during app shutdown.
      });
    };

    const onWindowBeforeUnload = () => {
      disconnectClientBestEffort();
    };

    window.addEventListener('beforeunload', onWindowBeforeUnload);

    void connectWorkspaceSocket(async (socket) => {
      const context = getLaunchContext();
      const socketSid = (socket as SocketLike & { id?: string }).id;
      if (!context.workfilePath || !socketSid) return;

      try {
        const response = await bridgeCall<ClientConnectResult>('clientConnect', {
          socketio_sid: socketSid,
          workfile_path: context.workfilePath,
          client_type: 'gui'
        });
        clientId = response.client_id;
      } catch {
        // Keep websocket active even if bridge registration fails.
      }
    }).then((socket) => {
      if (!mounted || !socket) {
        socket?.disconnect();
        return;
      }

      socketRef = socket;
      socket.on('graph_update', onGraphUpdate);
      socket.on('status_change', onStatusChange);
      socket.on('node_ready', onNodeReady);
      socket.on('run_complete', onRunComplete);
    });

    return () => {
      mounted = false;
      window.removeEventListener('beforeunload', onWindowBeforeUnload);
      disconnectClientBestEffort();
      if (!socketRef) return;
      socketRef.off('graph_update', onGraphUpdate);
      socketRef.off('status_change', onStatusChange);
      socketRef.off('node_ready', onNodeReady);
      socketRef.off('run_complete', onRunComplete);
      socketRef.disconnect();
    };
  }, [applyGraphUpdate, refreshGraph, setNodes]);

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
      const setNodeStatus = (status: WorkforceStatus) => {
        const previousNode = nodes.find((node) => node.id === contextMenu.nodeId);
        setNodes((existing) =>
          existing.map((node) =>
            node.id === contextMenu.nodeId ? { ...node, data: { ...node.data, status } } : node
          )
        );
        void bridgeCall('updateStatus', { kind: 'node', id: contextMenu.nodeId, status }).catch((error) => {
          if (previousNode) {
            setNodes((existing) =>
              existing.map((node) =>
                node.id === previousNode.id ? { ...node, data: { ...node.data, status: previousNode.data.status } } : node
              )
            );
          }
          setStatusMessage(`Status update failed: ${error instanceof Error ? error.message : 'unknown error'}`);
        });
      };

      return [
        { id: 'queued', label: 'Set status: queued', onSelect: () => setNodeStatus('run') },
        { id: 'running', label: 'Set status: running', onSelect: () => setNodeStatus('running') },
        { id: 'complete', label: 'Set status: complete', onSelect: () => setNodeStatus('ran') },
        { id: 'failed', label: 'Set status: failed', onSelect: () => setNodeStatus('fail') },
        {
          id: 'delete-node',
          label: 'Delete node',
          onSelect: () => {
            const previousNodes = nodes;
            const previousEdges = edges;
            setNodes((existing) => existing.filter((node) => node.id !== contextMenu.nodeId));
            setEdges((existing) =>
              existing.filter((edge) => edge.source !== contextMenu.nodeId && edge.target !== contextMenu.nodeId)
            );
            if (selectedNodeId === contextMenu.nodeId) setSelectedNodeId(undefined);
            void bridgeCall('removeNode', { node_id: contextMenu.nodeId }).catch((error) => {
              setNodes(previousNodes);
              setEdges(previousEdges);
              setStatusMessage(`Delete failed: ${error instanceof Error ? error.message : 'unknown error'}`);
            });
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
          const node = {
            id,
            type: 'workflowNode',
            position: { x: 200, y: 180 },
            data: { label: `node-${nodes.length + 1}`, command: '', status: '' as WorkforceStatus }
          };
          setNodes((existing) => [...existing, node]);
          void bridgeCall('addNode', {
            node_id: id,
            label: node.data.label,
            x: node.position.x,
            y: node.position.y
          }).catch((error) => {
            setNodes((existing) => existing.filter((entry) => entry.id !== id));
            setStatusMessage(`Add node failed: ${error instanceof Error ? error.message : 'unknown error'}`);
          });
        }
      },
      { id: 'clear-selection', label: 'Clear selection', onSelect: () => setSelectedNodeId(undefined) }
    ];
  }, [contextMenu, edges, nodes, selectedNodeId, setEdges, setNodes]);

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
            onEdgesDelete={onEdgesDelete}
            onNodesDelete={onNodesDelete}
            onNodeDragStart={onNodeDragStart}
            onNodeDragStop={onNodeDragStop}
            onSelectionDragStart={onSelectionDragStart}
            onSelectionDragStop={onSelectionDragStop}
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
              const previousNode = nodes.find((node) => node.id === selectedNodeId);
              setNodes((existing) =>
                existing.map((node) =>
                  node.id === selectedNodeId ? { ...node, data: { ...node.data, ...updates } } : node
                )
              );

              if (Object.prototype.hasOwnProperty.call(updates, 'label')) {
                void bridgeCall('updateNodeLabel', { node_id: selectedNodeId, label: updates.label }).catch((error) => {
                  if (previousNode) {
                    setNodes((existing) =>
                      existing.map((node) =>
                        node.id === selectedNodeId
                          ? { ...node, data: { ...node.data, label: previousNode.data.label } }
                          : node
                      )
                    );
                  }
                  setStatusMessage(`Label update failed: ${error instanceof Error ? error.message : 'unknown error'}`);
                });
              }

              if (Object.prototype.hasOwnProperty.call(updates, 'command')) {
                void bridgeCall('updateNodeCommand', { node_id: selectedNodeId, command: updates.command }).catch((error) => {
                  if (previousNode) {
                    setNodes((existing) =>
                      existing.map((node) =>
                        node.id === selectedNodeId
                          ? { ...node, data: { ...node.data, command: previousNode.data.command } }
                          : node
                      )
                    );
                  }
                  setStatusMessage(`Command update failed: ${error instanceof Error ? error.message : 'unknown error'}`);
                });
              }
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
