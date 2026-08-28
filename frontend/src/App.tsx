import { ChangeEvent, CSSProperties, KeyboardEvent, MouseEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactFlow, {
  addEdge,
  Background,
  Connection,
  Controls,
  Edge,
  EdgeProps,
  getBezierPath,
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
  useReactFlow,
  useUpdateNodeInternals
} from 'reactflow';
import 'reactflow/dist/style.css';
import { adaptBackendGraph, nodeDimensionsForLabel, statusColorMap } from './graph/adapters';
import { BackendNodeLinkGraph, WorkflowNodeData, WorkforceStatus } from './graph/types';
import { RightPanel } from './components/RightPanel';
import { CanvasContextMenu, ContextMenuItem } from './components/CanvasContextMenu';
import { MenuBar } from './components/MenuBar';
import { WorkspacesIndex } from './components/WorkspacesIndex';
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

type GetNodeLogResult = {
  log?: string;
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
       editEdgeType: { path: '/edit-edge-type' },
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
      getClients: { path: '/clients', httpMethod: 'GET' },
      listWorkspaces: { path: '/workspaces', httpMethod: 'GET' }
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

const nodeWrapperBaseStyle: CSSProperties = {
  padding: '10px 15px',
  border: '1px solid #555',
  background: 'white',
  minWidth: 150,
  textAlign: 'left',
  boxSizing: 'border-box',
  color: '#111827',
  position: 'relative'
};

function NonBlockingEdge({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, style = {}, markerEnd }: EdgeProps) {
  const [edgePath] = getBezierPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition });

  return (
    <path
      id={id}
      fill="none"
      style={{
        ...style,
        strokeWidth: 2,
        strokeDasharray: '5,5',
        stroke: '#94a3b8'
      }}
      d={edgePath}
      markerEnd={markerEnd}
    />
  );
}

const textDisplayStyle: CSSProperties = {
  padding: 5,
  cursor: 'text',
  whiteSpace: 'pre-wrap'
};

const inputStyle: CSSProperties = {
  width: 'auto',
  minWidth: '100%',
  display: 'inline-block',
  boxSizing: 'border-box',
  padding: 5,
  border: 'none',
  outline: 'none',
  background: 'transparent',
  font: 'inherit',
  color: 'inherit',
  resize: 'none',
  overflow: 'hidden'
};

function parsePixelValue(value: string): number {
  const parsed = parseFloat(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function adjustTextareaSize(element: HTMLTextAreaElement): { width: number; height: number } {
  element.style.height = 'auto';
  element.style.height = `${element.scrollHeight}px`;

  const computed = window.getComputedStyle(element);
  const tempSpan = document.createElement('span');
  tempSpan.style.visibility = 'hidden';
  tempSpan.style.position = 'absolute';
  tempSpan.style.whiteSpace = 'pre';
  tempSpan.style.font = computed.font;
  tempSpan.textContent = element.value || ' ';
  document.body.appendChild(tempSpan);

  const horizontalPadding = parsePixelValue(computed.paddingLeft) + parsePixelValue(computed.paddingRight);
  const horizontalBorder = parsePixelValue(computed.borderLeftWidth) + parsePixelValue(computed.borderRightWidth);
  const width = Math.ceil(tempSpan.offsetWidth + horizontalPadding + horizontalBorder + 2);

  document.body.removeChild(tempSpan);
  element.style.width = 'auto';
  element.style.width = `${width}px`;

  return { width, height: element.scrollHeight };
}

function WorkflowNode({ id, data, selected }: NodeProps<WorkflowNodeData>) {
  const statusColor = statusColorMap[data.status];
  const updateNodeInternals = useUpdateNodeInternals();
  const { setNodes } = useReactFlow<WorkflowNodeData>();
  const [isEditing, setIsEditing] = useState(false);
  const [draftLabel, setDraftLabel] = useState(data.label || '');
  const previousLabelRef = useRef(data.label || '');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const lastEditRequestRef = useRef<number | undefined>(data.editRequestId);

  const resizeTextarea = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const { width, height } = adjustTextareaSize(textarea);
    const wrapperHorizontalPadding = 30;
    const wrapperVerticalPadding = 20;
    const wrapperBorderWidth = 8;
    const nextDimensions = {
      width: Math.max(150, width + wrapperHorizontalPadding + wrapperBorderWidth),
      height: height + wrapperVerticalPadding + 2
    };
    setNodes((existingNodes) =>
      existingNodes.map((node) =>
        node.id === id
          ? {
              ...node,
              style: { ...(node.style ?? {}), ...nextDimensions }
            }
          : node
      )
    );
  }, [draftLabel, id, setNodes]);

  const updateNodeLabelLocally = useCallback(
    (nextLabel: string) => {
      setNodes((existingNodes) =>
        existingNodes.map((node) =>
          node.id === id
            ? {
                ...node,
                style: { ...(node.style ?? {}), ...nodeDimensionsForLabel(nextLabel) },
                data: { ...node.data, label: nextLabel, command: nextLabel }
              }
            : node
        )
      );
    },
    [id, setNodes]
  );

  const commitLabel = useCallback(() => {
    const nextLabel = draftLabel;
    const previousLabel = previousLabelRef.current;
    setIsEditing(false);

    if (nextLabel === previousLabel) return;

    updateNodeLabelLocally(nextLabel);
    previousLabelRef.current = nextLabel;

    void bridgeCall('updateNodeLabel', { node_id: id, label: nextLabel }).catch((error) => {
      updateNodeLabelLocally(previousLabel);
      previousLabelRef.current = previousLabel;
      setDraftLabel(previousLabel);
      console.error(`Label update failed for ${id}:`, error);
    });
  }, [draftLabel, id, updateNodeLabelLocally]);

  const cancelEdit = useCallback(() => {
    setDraftLabel(previousLabelRef.current);
    setIsEditing(false);
  }, []);

  useEffect(() => {
    if (typeof data.editRequestId === 'undefined' || data.editRequestId === lastEditRequestRef.current) return;
    lastEditRequestRef.current = data.editRequestId;
    setIsEditing(true);
  }, [data.editRequestId]);

  useEffect(() => {
    if (isEditing) return;
    previousLabelRef.current = data.label || '';
    setDraftLabel(data.label || '');
  }, [data.label, isEditing]);

  useEffect(() => {
    updateNodeInternals(id);
  }, [data.label, draftLabel, id, isEditing, updateNodeInternals]);

  useEffect(() => {
    if (!isEditing) return;
    resizeTextarea();
  }, [isEditing, resizeTextarea]);

  useEffect(() => {
    if (!isEditing) return;
    textareaRef.current?.focus();
    textareaRef.current?.select();
  }, [isEditing]);

  const handleDraftChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    adjustTextareaSize(event.target);
    setDraftLabel(event.target.value);
  };

  const handleStartEditing = (event: MouseEvent<HTMLElement>) => {
    event.stopPropagation();
    setIsEditing(true);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      cancelEdit();
      return;
    }

    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault();
      commitLabel();
    }
  };

  return (
    <div
      style={{
        ...nodeWrapperBaseStyle,
        border: selected ? '2px solid #111827' : nodeWrapperBaseStyle.border,
        borderLeft: `6px solid ${statusColor}`,
        background: statusColor
      }}
      onDoubleClick={handleStartEditing}
    >
      <Handle type="target" position={Position.Left} />
      {isEditing ? (
        <>
          <textarea
            ref={textareaRef}
            className="nodrag nowheel"
            value={draftLabel}
            aria-label="Node label"
            rows={1}
            spellCheck={false}
            style={inputStyle}
            onBlur={commitLabel}
            onChange={handleDraftChange}
            onKeyDown={handleKeyDown}
            onMouseDown={(event) => event.stopPropagation()}
            onDoubleClick={(event) => event.stopPropagation()}
          />
        </>
      ) : (
        <div
          role="button"
          tabIndex={0}
          title="Double click to edit node label"
          style={textDisplayStyle}
          onDoubleClick={handleStartEditing}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              setIsEditing(true);
            }
          }}
        >
          {data.label || ''}
        </div>
      )}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

const nodeTypes = { workflowNode: WorkflowNode };
const edgeTypes = { nonBlockingEdge: NonBlockingEdge };

function AppContent() {
  const workspaceBaseUrl = resolveWorkspaceBaseUrl();
  const isHomeView = !workspaceBaseUrl;

  const initial = useMemo(() => adaptBackendGraph(seededGraph), []);
  const [nodes, setNodes, onNodesChange] = useNodesState<WorkflowNodeData>(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);
  const [selectedNodeIds, setSelectedNodeIds] = useState<string[]>([]);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; nodeId?: string; edgeId?: string } | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>('');
  const [currentPath, setCurrentPath] = useState<string | undefined>();
  const [selectedNodeLog, setSelectedNodeLog] = useState<string>();
  const [isSelectedNodeLogLoading, setIsSelectedNodeLogLoading] = useState(false);
  const [wrapper, setWrapper] = useState<string>('{}');
  const [isEditingWrapper, setIsEditingWrapper] = useState(false);
  const [draftWrapper, setDraftWrapper] = useState('{}');
  const { screenToFlowPosition } = useReactFlow();
  const cursorFlowPosRef = useRef<{ x: number; y: number }>({ x: 200, y: 180 });
  const dragStartPositionsRef = useRef<Record<string, { x: number; y: number }>>({});
  const editRequestCounterRef = useRef(0);
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
      const graph = await bridgeCall<BackendNodeLinkGraph & { graph?: { wrapper?: string } }>('getGraph');
      const adapted = adaptBackendGraph(graph);
      setNodes(adapted.nodes);
      setEdges(adapted.edges);
      if (graph.graph?.wrapper) {
        setWrapper(graph.graph.wrapper);
      }
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
      if (selectedNodes.length === 0) return;
      const nextSelectedNodeIds = selectedNodes.map((node) => node.id);
      setSelectedNodeIds((currentSelectedNodeIds) => {
        if (
          currentSelectedNodeIds.length === nextSelectedNodeIds.length &&
          currentSelectedNodeIds.every((nodeId, idx) => nodeId === nextSelectedNodeIds[idx])
        ) {
          return currentSelectedNodeIds;
        }
        return nextSelectedNodeIds;
      });
    }
  });

  useEffect(() => {
    const selectedNodeId = selectedNodeIds[0];
    if (!selectedNodeId) {
      setSelectedNodeLog(undefined);
      setIsSelectedNodeLogLoading(false);
      return;
    }

    let ignore = false;
    setIsSelectedNodeLogLoading(true);

    void bridgeCall<GetNodeLogResult>('getNodeLog', { node_id: selectedNodeId })
      .then((result) => {
        if (ignore) return;
        setSelectedNodeLog(result.log ?? '[No log available for this node]');
      })
      .catch(() => {
        if (ignore) return;
        setSelectedNodeLog('[Failed to load node output]');
      })
      .finally(() => {
        if (ignore) return;
        setIsSelectedNodeLogLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, [selectedNodeIds[0]]);

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

  const onEdgeContextMenu = useCallback((event: MouseEvent, edge: Edge) => {
    event.preventDefault();
    setContextMenu({ x: event.clientX, y: event.clientY, edgeId: edge.id });
  }, []);

  const onPaneContextMenu = useCallback((event: MouseEvent) => {
    event.preventDefault();
    setContextMenu({ x: event.clientX, y: event.clientY });
  }, []);

  const onNodeDragStart = useCallback((_: MouseEvent, node: Node<WorkflowNodeData>) => {
    dragStartPositionsRef.current[node.id] = { x: node.position.x, y: node.position.y };
    setSelectedNodeIds([node.id]);
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

  const handleSelectWorkspace = useCallback((id: string) => {
    window.location.href = `/workspace/${id}`;
  }, []);

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

  const handleUpdateWrapper = useCallback(async () => {
    try {
      await bridgeCall('updateWrapper', { wrapper: draftWrapper });
      setWrapper(draftWrapper);
      setIsEditingWrapper(false);
      setStatusMessage('Wrapper updated successfully.');
    } catch (error) {
      setStatusMessage(`Wrapper update failed: ${error instanceof Error ? error.message : 'unknown error'}`);
    }
  }, [draftWrapper]);

  const handleAddNodeAtPosition = useCallback(
    (position: { x: number; y: number }) => {
      const id = crypto.randomUUID();
      const dims = nodeDimensionsForLabel(`node-${nodes.length + 1}`);
      const node = {
        id,
        type: 'workflowNode',
        position: { x: position.x - dims.width / 2, y: position.y - dims.height / 2 },
        style: dims,
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
    },
    [nodes.length, setNodes]
  );

  const startInlineEditingNode = useCallback(
    (nodeId: string) => {
      editRequestCounterRef.current += 1;
      const editRequestId = editRequestCounterRef.current;
      setSelectedNodeIds([nodeId]);
      setNodes((existing) =>
        existing.map((node) =>
          node.id === nodeId ? { ...node, data: { ...node.data, editRequestId } } : node
        )
      );
    },
    [setNodes]
  );

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

    if (contextMenu.edgeId) {
      const edge = edges.find((e) => e.id === contextMenu.edgeId);
      if (!edge) return [];
      
      const currentType = (edge.data?.edge_type as string) || 'blocking';
      const nextType = currentType === 'blocking' ? 'non-blocking' : 'blocking';

      return [
        {
          id: 'toggle-edge-type',
          label: `Edge type: ${currentType === 'blocking' ? 'Blocking' : 'Non-blocking'}`,
          onSelect: () => {
            setEdges((existing) =>
              existing.map((e) =>
                e.id === edge.id ? { ...e, data: { ...e.data, edge_type: nextType } } : e
              )
            );
            void bridgeCall('editEdgeType', { 
              source: edge.source, 
              target: edge.target, 
              edge_type: nextType 
            }).catch((error) => {
              setEdges((existing) =>
                existing.map((e) =>
                  e.id === edge.id ? { ...e, data: { ...e.data, edge_type: currentType } } : e
                )
              );
              setStatusMessage(`Edge type update failed: ${error instanceof Error ? error.message : 'unknown error'}`);
            });
          }
        }
      ];
    }

    return [
      {
        id: 'add-node',
        label: 'Add node',
        onSelect: () => handleAddNodeAtPosition(cursorFlowPosRef.current)
      },
      { id: 'clear-selection', label: 'Clear selection', onSelect: () => setSelectedNodeIds([]) }
    ];
  }, [contextMenu, edges, handleAddNodeAtPosition, nodes, selectedNodeIds, setEdges, setNodes]);

    if (isHomeView) {
      return (
        <WorkspacesIndex 
          onSelectWorkspace={handleSelectWorkspace} 
          fetchWorkspaces={() => bridgeCall('listWorkspaces')} 
        />
      );
    }

    return (
      <div style={{ width: '100vw', height: '100vh', display: 'grid', gridTemplateRows: '52px 1fr', background: '#0f172a' }}>
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
          <a href="/" style={{ color: '#f8fafc', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}>
              <span>←</span>
              <strong>Home</strong>
            </a>
          <MenuBar
            menus={[
              {
                label: 'File',
                items: [
                  { label: 'New', action: () => setStatusMessage('New not yet implemented') },
                  { label: 'Open...', action: () => void handleOpenWorkflow() },
                  { label: 'Save As...', action: () => void handleSaveWorkflowAs() }
                ]
              }
            ]}
          />
          <div style={{ display: 'flex', gap: 8, marginLeft: 8 }}>
            <button
              onClick={() => void handleRunWorkflow()}
              style={{
                background: '#334155',
                border: 'none',
                color: '#e2e8f0',
                cursor: 'pointer',
                padding: '4px 12px',
                borderRadius: 4,
                fontSize: 13,
                fontFamily: 'inherit'
              }}
            >
              Run
            </button>
            <button
              onClick={() => void handleStopRuns()}
              style={{
                background: '#334155',
                border: 'none',
                color: '#e2e8f0',
                cursor: 'pointer',
                padding: '4px 12px',
                borderRadius: 4,
                fontSize: 13,
                fontFamily: 'inherit'
              }}
            >
              Stop
            </button>
            <button
              onClick={() => {
                setDraftWrapper(wrapper);
                setIsEditingWrapper(true);
              }}
              style={{
                background: '#334155',
                border: 'none',
                color: '#e2e8f0',
                cursor: 'pointer',
                padding: '4px 12px',
                borderRadius: 4,
                fontSize: 13,
                fontFamily: 'inherit'
              }}
            >
              Wrapper
            </button>
          </div>


        </div>
        <span style={{ fontSize: 12, color: '#94a3b8' }}>{statusMessage || 'Double click to add • Drag • Connect • Right click • Multi-select'}</span>
      </header>

      <main
        style={{
          display: 'grid',
          gridTemplateColumns: selectedNodeIds.length ? '1fr 320px' : '1fr',
          minHeight: 0,
          overflow: 'hidden'
        }}
      >
        <section
          style={{ borderRight: '1px solid #1e293b', minHeight: 0, overflow: 'hidden' }}
          onDoubleClick={(event) => {
            const target = event.target as HTMLElement;
            if (target.closest('.react-flow__node') || target.closest('.react-flow__edge')) return;
            const flowPos = screenToFlowPosition({ x: event.clientX, y: event.clientY });
            handleAddNodeAtPosition(flowPos);
          }}
        >
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
            onNodeClick={(_, node) => setSelectedNodeIds([node.id])}
            onNodeDoubleClick={(event, node) => {
              event.stopPropagation();
              startInlineEditingNode(node.id);
            }}
            nodeDragThreshold={0}
            onPaneClick={() => setSelectedNodeIds([])}
            onNodeContextMenu={onNodeContextMenu}
            onEdgeContextMenu={onEdgeContextMenu}
            onPaneContextMenu={onPaneContextMenu}
            edgeTypes={edgeTypes}
            onMouseMove={(event) => {
              if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
              const flowPos = screenToFlowPosition({ x: event.clientX, y: event.clientY });
              cursorFlowPosRef.current = flowPos;
            }}
            onKeyDown={(event) => {
              if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
              if (event.key === 'r' || event.key === 'R') {
                event.preventDefault();
                void handleRunWorkflow();
              }
            }}
            fitView
            nodeTypes={nodeTypes}
            panOnDrag
            zoomOnScroll
            zoomOnDoubleClick={false}
            minZoom={0.01}
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
          <aside style={{ color: '#e2e8f0', minHeight: 0, overflow: 'hidden' }}>
            <RightPanel
              node={selectedNode}
              nodeLog={selectedNodeLog}
              isNodeLogLoading={isSelectedNodeLogLoading}
            />
          </aside>
        )}
      </main>

       {contextMenu && <CanvasContextMenu x={contextMenu.x} y={contextMenu.y} items={menuItems} onClose={() => setContextMenu(null)} />}
       {isEditingWrapper && (
         <div
           style={{
             position: 'fixed',
             top: 0,
             left: 0,
             right: 0,
             bottom: 0,
             background: 'rgba(0,0,0,0.7)',
             display: 'flex',
             alignItems: 'center',
             justifyContent: 'center',
             zIndex: 2000
           }}
         >
           <div
             style={{
               background: '#1e293b',
               padding: '20px',
               borderRadius: 8,
               border: '1px solid #334155',
               color: '#e2e8f0',
               width: '600px',
               maxWidth: '90vw',
               display: 'flex',
               flexDirection: 'column',
               gap: 16
             }}
           >
             <h3 style={{ margin: 0 }}>Edit Graph Wrapper</h3>
             <textarea
               value={draftWrapper}
               onChange={(e) => setDraftWrapper(e.target.value)}
               style={{
                 width: '100%',
                 height: '300px',
                 background: '#0f172a',
                 color: '#e2e8f0',
                 border: '1px solid #334155',
                 borderRadius: 4,
                 padding: 10,
                 fontFamily: 'monospace',
                 fontSize: 13,
                 resize: 'vertical'
               }}
             />
             <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
               <button
                 onClick={() => setIsEditingWrapper(false)}
                 style={{
                   background: 'transparent',
                   border: '1px solid #334155',
                   color: '#94a3b8',
                   cursor: 'pointer',
                   padding: '6px 12px',
                   borderRadius: 4,
                   fontSize: 13
                 }}
               >
                 Close
               </button>
               <button
                 onClick={() => void handleUpdateWrapper()}
                 style={{
                   background: '#3b82f6',
                   border: 'none',
                   color: 'white',
                   cursor: 'pointer',
                   padding: '6px 12px',
                   borderRadius: 4,
                   fontSize: 13
                 }}
               >
                 Update
               </button>
             </div>
           </div>
         </div>
       )}
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
