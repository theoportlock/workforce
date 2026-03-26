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
  useNodesState,
  useOnSelectionChange,
  useUpdateNodeInternals
} from 'reactflow';
import 'reactflow/dist/style.css';
import { adaptBackendGraph, nodeDimensionsForLabel, statusColorMap } from './graph/adapters';
import { BackendNodeLinkGraph, WorkflowNodeData, WorkforceStatus } from './graph/types';
import { RightPanel } from './components/RightPanel';
import { CanvasContextMenu, ContextMenuItem } from './components/CanvasContextMenu';
import { connectWorkspaceSocket, getLaunchContext, SocketLike } from './runtime/socketClient';
import { FrontendOperationQueue } from './runtime/operationQueue';

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
  console.log('[LaunchContext] Resolving base URL from:', {
    __WORKSPACE_BASE_URL__: window.__WORKSPACE_BASE_URL__,
    pathname: window.location.pathname
  });
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
  console.log(`[Bridge] Calling method: ${method}`, params);
  
  const request: BridgeRequest = {
    id: `${method}-${Date.now()}`,
    method,
    params,
    protocolVersion: '1.0'
  };

  const handler = window.workforceBridge?.handleRequest;
  if (!handler) {
    const workspaceBaseUrl = resolveWorkspaceBaseUrl();
    if (!workspaceBaseUrl) {
      throw new Error('Bridge API is unavailable and workspace URL could not be derived.');
    }

    if (method === 'getGraph') {
      const response = await fetch(`${workspaceBaseUrl}/get-graph`);
      if (!response.ok) {
        throw new Error(`Graph fetch failed: ${response.status}`);
      }
      return (await response.json()) as T;
    }

    const fallbackEndpoints: Record<string, { path: string; httpMethod?: 'GET' | 'POST' }> = {
      addNode: { path: '/add-node' },
      removeNode: { path: '/remove-node' },
      addEdge: { path: '/add-edge' },
      removeEdge: { path: '/remove-edge' },
      updateNodePosition: { path: '/edit-node-position' },
      updateNodePositions: { path: '/edit-node-positions' },
      updateNodeLabel: { path: '/edit-node-label' },
      updateNodeCommand: { path: '/edit-node-label' },
      updateStatus: { path: '/edit-status' },
      updateStatuses: { path: '/edit-statuses' },
      updateWrapper: { path: '/edit-wrapper' },
      runWorkflow: { path: '/run' },
      stopRuns: { path: '/stop' },
      saveWorkflowAs: { path: '/save-as' },
      clientConnect: { path: '/client-connect' },
      clientDisconnect: { path: '/client-disconnect' },
      getNodeLog: { path: `/get-node-log/${encodeURIComponent(String(params.node_id ?? ''))}`, httpMethod: 'GET' },
      getRuns: { path: '/runs', httpMethod: 'GET' },
      getClients: { path: '/clients', httpMethod: 'GET' }
    };

    const fallback = fallbackEndpoints[method];
    if (!fallback) {
      throw new Error('Bridge API is unavailable in this environment.');
    }

    if (fallback.httpMethod === 'GET') {
      const response = await fetch(`${workspaceBaseUrl}${fallback.path}`);
      console.log(`[Bridge] GET ${method} response:`, response.status);
      if (!response.ok) {
        throw new Error(`Bridge fallback failed for ${method}: ${response.status}`);
      }
      return (await response.json()) as T;
    }

    const payload = method === 'updateNodeCommand' ? { node_id: params['node_id'], label: params['command'] } : params;
    console.log(`[Bridge] POST ${method} to ${workspaceBaseUrl}${fallback.path}`, payload);
    const response = await fetch(`${workspaceBaseUrl}${fallback.path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    console.log(`[Bridge] POST ${method} response:`, response.status);
    if (!response.ok) {
      throw new Error(`Bridge fallback failed for ${method}: ${response.status}`);
    }
    return (await response.json()) as T;
  }

  const response = await Promise.resolve(handler(request));
  console.log(`[Bridge] ${method} bridge response:`, response);
  if (!response.ok) {
    throw new Error(response.error?.message ?? `Bridge request failed for ${method}`);
  }
  return (response.result ?? {}) as T;
}

function promptWorkflowPath(action: 'open' | 'save', currentPath?: string): string | null {
  const verb = action === 'open' ? 'Open' : 'Save As';
  const promptMessage =
    action === 'open'
      ? 'Enter the workflow file path to open:'
      : 'Enter the workflow file path to save as:';
  const entered = window.prompt(promptMessage, currentPath ?? '');
  if (entered === null) return null;
  const trimmed = entered.trim();
  if (!trimmed) {
    throw new Error(`${verb} cancelled: path is required.`);
  }
  return trimmed;
}

function WorkflowNode({ id, data, selected }: NodeProps<WorkflowNodeData>) {
  const color = statusColorMap[data.status];
  const updateNodeInternals = useUpdateNodeInternals();

  useEffect(() => {
    updateNodeInternals(id);
  }, [data.label, id, updateNodeInternals]);

  return (
    <div
      style={{
        alignItems: 'center',
        border: selected ? '2px solid #FFFFFF' : '1px solid #37474F',
        borderRadius: 6,
        background: color,
        boxSizing: 'border-box',
        color: '#FFFFFF',
        display: 'inline-flex',
        justifyContent: 'center',
        minHeight: 36,
        minWidth: 0,
        padding: '6px 8px',
        width: '100%',
        height: '100%'
      }}
    >
      <Handle type="target" position={Position.Left} />
      <div style={{ fontSize: 13, fontWeight: 600, whiteSpace: 'pre' }}>{data.label || ''}</div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

function AppContent() {
  const initial = useMemo(() => adaptBackendGraph(seededGraph), []);
  const [nodes, setNodes, onNodesChange] = useNodesState<WorkflowNodeData>(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);
  const [selectedNodeIds, setSelectedNodeIds] = useState<string[]>([]);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; nodeId?: string } | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>('');
  const [currentPath, setCurrentPath] = useState<string | undefined>();
  const dragStartPositionsRef = useRef<Record<string, { x: number; y: number }>>({});
  const opQueueRef = useRef(
    new FrontendOperationQueue(
      {
        flushPositions: async (positions) => {
          await bridgeCall('updateNodePositions', { positions });
        },
        flushStatuses: async (updates) => {
          await bridgeCall('updateStatuses', { updates });
        },
        onFlushError: (message) => setStatusMessage(message)
      },
      100
    )
  );

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

  useEffect(
    () => () => {
      opQueueRef.current.dispose();
    },
    []
  );

  const selectedNode = useMemo(
    () => nodes.find((node) => node.id === selectedNodeIds[0]),
    [nodes, selectedNodeIds]
  );

  useOnSelectionChange({
    onChange: ({ nodes: selectedNodes }) => {
      setSelectedNodeIds(selectedNodes.map(n => n.id));
    }
  });

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
    setSelectedNodeIds([node.id]);
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
      opQueueRef.current.enqueuePosition({ node_id: node.id, x: node.position.x, y: node.position.y });
    },
    []
  );

  const onSelectionDragStart = useCallback((_: MouseEvent, draggedNodes: Node<WorkflowNodeData>[]) => {
    draggedNodes.forEach((node) => {
      dragStartPositionsRef.current[node.id] = { x: node.position.x, y: node.position.y };
    });
  }, []);

  const onSelectionDragStop = useCallback(
    (_: MouseEvent, draggedNodes: Node<WorkflowNodeData>[]) => {
      draggedNodes.forEach((node) => {
        opQueueRef.current.enqueuePosition({ node_id: node.id, x: node.position.x, y: node.position.y });
      });
    },
    []
  );

  const handleOpenWorkflow = useCallback(async () => {
    try {
      await opQueueRef.current.flush();
      const selectedPath = promptWorkflowPath('open', currentPath);
      if (!selectedPath) return;
      const result = await bridgeCall<{ path?: string }>('openWorkflow', { path: selectedPath });
      if (result.path) setCurrentPath(result.path);
      await refreshGraph();
      setStatusMessage('Opened workflow successfully.');
    } catch (error) {
      setStatusMessage(`Open failed: ${error instanceof Error ? error.message : 'unknown error'}`);
    }
  }, [currentPath, refreshGraph]);

  const applyGraphUpdate = useCallback(
    (payload: GraphUpdatePayload) => {
      console.log('[App] applyGraphUpdate called with payload:', JSON.stringify(payload));
      payload.nodes?.forEach((node) => {
        if (typeof node.x !== 'undefined' && typeof node.y !== 'undefined') {
          opQueueRef.current.clearPendingPosition(node.id);
        }
        if (typeof node.status === 'string') {
          opQueueRef.current.clearPendingStatus('node', node.id);
        }
      });

      if (payload.links) {
        console.log('[App] Processing links update, nodes count:', payload.nodes?.length);
        const adapted = adaptBackendGraph(payload);
        setNodes(adapted.nodes);
        setEdges(adapted.edges);
        return;
      }

      if (payload.nodes?.length) {
        console.log('[App] Processing nodes update, count:', payload.nodes.length);
        setNodes((existing) =>
          existing.map((node) => {
            const update = payload.nodes.find((entry) => entry.id === node.id);
            if (!update) return node;
            return {
              ...node,
              style: {
                ...(node.style ?? {}),
                ...nodeDimensionsForLabel(update.command ?? update.label ?? node.data.label)
              },
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

    console.log('[App] Setting up socket event handlers');

    const onGraphUpdate = (payload: GraphUpdatePayload) => {
      console.log('[App] Received graph_update:', payload);
      applyGraphUpdate(payload);
    };
    const onInitialState = (payload: BackendNodeLinkGraph) => {
      console.log('[App] Received initial_state:', JSON.stringify(payload));
      const adapted = adaptBackendGraph(payload);
      console.log('[App] Adapted nodes:', adapted.nodes.length, 'edges:', adapted.edges.length);
      setNodes(adapted.nodes);
      setEdges(adapted.edges);
    };
    const onStatusChange = (payload: NodeStatusPayload) => {
      console.log('[App] Received status_change:', payload);
      if (!payload.node_id || !payload.status) return;
      opQueueRef.current.clearPendingStatus('node', payload.node_id);
      setNodes((existing) =>
        existing.map((node) =>
          node.id === payload.node_id ? { ...node, data: { ...node.data, status: payload.status ?? node.data.status } } : node
        )
      );
    };
    const onNodeReady = (payload: NodeReadyPayload) => {
      console.log('[App] Received node_ready:', payload);
      if (!payload.node_id) return;
      opQueueRef.current.clearPendingStatus('node', payload.node_id);
      setNodes((existing) =>
        existing.map((node) =>
          node.id === payload.node_id && node.data.status !== 'running'
            ? { ...node, data: { ...node.data, status: 'run' } }
            : node
        )
      );
    };
    const onRunComplete = (payload: RunCompletePayload) => {
      console.log('[App] Received run_complete:', payload);
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
        console.log('[App] Socket connection aborted - mounted:', mounted, 'socket:', socket);
        socket?.disconnect();
        return;
      }

      console.log('[App] Socket connected, registering event handlers');
      socketRef = socket;
      socket.on('initial_state', onInitialState);
      socket.on('graph_update', onGraphUpdate);
      socket.on('status_change', onStatusChange);
      socket.on('node_ready', onNodeReady);
      socket.on('run_complete', onRunComplete);
      
      // Debug: also listen for ANY event to catch everything
      const socketWithAny = socket as SocketLike & { onAny: (handler: (eventName: string, ...args: any[]) => void) => void };
      if (socketWithAny.onAny) {
        socketWithAny.onAny((eventName, ...args) => {
          console.log('[App] Socket received event:', eventName, args);
        });
      }
      
      console.log('[App] Event handlers registered successfully');
    });

    return () => {
      mounted = false;
      window.removeEventListener('beforeunload', onWindowBeforeUnload);
      disconnectClientBestEffort();
      if (!socketRef) return;
      socketRef.off('initial_state', onInitialState);
      socketRef.off('graph_update', onGraphUpdate);
      socketRef.off('status_change', onStatusChange);
      socketRef.off('node_ready', onNodeReady);
      socketRef.off('run_complete', onRunComplete);
      socketRef.disconnect();
    };
  }, [applyGraphUpdate, refreshGraph, setNodes, setEdges]);

  const handleSaveWorkflowAs = useCallback(async () => {
    try {
      await opQueueRef.current.flush();
      const selectedPath = promptWorkflowPath('save', currentPath);
      if (!selectedPath) return;
      const result = await bridgeCall<{ new_path?: string }>('saveWorkflowAs', { new_path: selectedPath });
      if (result.new_path) setCurrentPath(result.new_path);
      await refreshGraph();
      setStatusMessage('Saved workflow copy successfully.');
    } catch (error) {
      setStatusMessage(`Save As failed: ${error instanceof Error ? error.message : 'unknown error'}`);
    }
  }, [currentPath, refreshGraph]);

  const handleStopRuns = useCallback(async () => {
    try {
      await opQueueRef.current.flush();
      await bridgeCall('stopRuns');
      setStatusMessage('Stop requested for active runs.');
    } catch (error) {
      setStatusMessage(`Stop failed: ${error instanceof Error ? error.message : 'unknown error'}`);
    }
  }, []);

  const handleRunWorkflow = useCallback(async () => {
    try {
      await opQueueRef.current.flush();
      await bridgeCall('runWorkflow', { nodes: selectedNodeIds });
      setStatusMessage(selectedNodeIds.length > 0 ? `Running selected nodes (${selectedNodeIds.length})...` : 'Running full pipeline...');
    } catch (error) {
      setStatusMessage(`Run failed: ${error instanceof Error ? error.message : 'unknown error'}`);
    }
  }, [selectedNodeIds]);

  const menuItems: ContextMenuItem[] = useMemo(() => {
    if (!contextMenu) return [];

    if (contextMenu.nodeId) {
      const setNodeStatus = (status: WorkforceStatus) => {
        const nodeId = contextMenu.nodeId;
        if (!nodeId) return;
        setNodes((existing) =>
          existing.map((node) =>
            node.id === nodeId ? { ...node, data: { ...node.data, status } } : node
          )
        );
        opQueueRef.current.enqueueStatus({ element_type: 'node', element_id: nodeId, value: status });
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
            if (contextMenu.nodeId && selectedNodeIds.includes(contextMenu.nodeId)) setSelectedNodeIds([]);
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
            style: nodeDimensionsForLabel(`node-${nodes.length + 1}`),
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
      { id: 'clear-selection', label: 'Clear selection', onSelect: () => setSelectedNodeIds([]) }
    ];
  }, [contextMenu, edges, nodes, selectedNodeIds, setEdges, setNodes]);

  return (
    <div style={{ height: '100vh', display: 'grid', gridTemplateRows: '52px 1fr', background: '#020617' }}>
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
            <button onClick={() => void handleRunWorkflow()}>Run ▸</button>
            <button onClick={() => void handleStopRuns()}>Stop</button>
          </div>
        </div>
        <span style={{ fontSize: 12, color: '#94a3b8' }}>{statusMessage || 'Click to inspect • Drag • Connect • Right click • Multi-select'}</span>
      </header>

      <main style={{ display: 'grid', gridTemplateColumns: selectedNodeIds.length ? '1fr 320px' : '1fr' }}>
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
            onPaneClick={() => setSelectedNodeIds([])}
            nodeDragThreshold={5}
            onNodeContextMenu={onNodeContextMenu}
            onPaneContextMenu={onPaneContextMenu}
            onKeyDown={(event) => {
              if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
              if (event.key === 'r' || event.key === 'R') {
                event.preventDefault();
                void handleRunWorkflow();
              }
            }}
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

        {selectedNodeIds.length > 0 && (
          <aside style={{ color: '#e2e8f0' }}>
            <RightPanel
              node={selectedNode}
              onUpdate={(updates) => {
                const selectedNodeId = selectedNodeIds[0];
                if (!selectedNodeId) return;
                const previousNode = nodes.find((node) => node.id === selectedNodeId);
                setNodes((existing) =>
                  existing.map((node) =>
                    node.id === selectedNodeId
                      ? {
                          ...node,
                          style:
                            Object.prototype.hasOwnProperty.call(updates, 'label') && typeof updates.label === 'string'
                              ? { ...(node.style ?? {}), ...nodeDimensionsForLabel(updates.label) }
                              : node.style,
                          data: { ...node.data, ...updates }
                        }
                      : node
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
        )}
      </main>

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
