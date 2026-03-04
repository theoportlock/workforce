export interface LaunchContext {
  workspaceId?: string;
  serverRoot: string;
  workfilePath?: string;
}

export interface SocketLike {
  on: (event: string, handler: (...args: any[]) => void) => void;
  off: (event: string, handler?: (...args: any[]) => void) => void;
  emit: (event: string, payload?: unknown) => void;
  disconnect: () => void;
}

declare global {
  interface Window {
    io?: (url: string, options?: Record<string, unknown>) => SocketLike;
    __WORKSPACE_ID__?: string;
    __WORKSPACE_BASE_URL__?: string;
    workforceLaunchContext?: {
      workspaceId?: string;
      workspace_id?: string;
      workfilePath?: string;
      workfile_path?: string;
      serverRoot?: string;
      server_root?: string;
      baseUrl?: string;
      base_url?: string;
    };
  }
}

const SOCKET_IO_SCRIPT_PATH = 'https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.4/socket.io.min.js';

function tryParseWorkspaceId(urlOrPath?: string): string | undefined {
  if (!urlOrPath) return undefined;

  try {
    const asUrl = new URL(urlOrPath, window.location.href);
    const parts = asUrl.pathname.split('/').filter(Boolean);
    const workspaceIndex = parts.findIndex((part) => part === 'workspace');
    if (workspaceIndex >= 0 && parts[workspaceIndex + 1]) {
      return parts[workspaceIndex + 1];
    }
  } catch {
    // Ignore parse errors and fall through.
  }

  const match = urlOrPath.match(/\/workspace\/([^/?#]+)/);
  return match?.[1];
}

export function getLaunchContext(): LaunchContext {
  const launch = window.workforceLaunchContext;
  const shellWorkspaceId = window.__WORKSPACE_ID__;
  const shellBaseUrl = window.__WORKSPACE_BASE_URL__;
  const baseUrl = launch?.baseUrl ?? launch?.base_url ?? shellBaseUrl;
  const explicitRoot = launch?.serverRoot ?? launch?.server_root;
  const queryWorkspace = new URLSearchParams(window.location.search).get('workspace_id') ?? undefined;
  const workfilePath = launch?.workfilePath ?? launch?.workfile_path;

  const workspaceId =
    launch?.workspaceId ??
    launch?.workspace_id ??
    shellWorkspaceId ??
    tryParseWorkspaceId(baseUrl) ??
    tryParseWorkspaceId(window.location.pathname) ??
    queryWorkspace;

  const serverRoot = (() => {
    if (explicitRoot) return explicitRoot.replace(/\/$/, '');
    if (baseUrl) return new URL(baseUrl, window.location.href).origin;
    return window.location.origin;
  })();

  return { workspaceId, serverRoot, workfilePath };
}

let ioLibraryPromise: Promise<Window['io']> | null = null;

async function loadIoLibrary(serverRoot: string): Promise<Window['io']> {
  if (window.io) return window.io;
  if (!ioLibraryPromise) {
    ioLibraryPromise = new Promise((resolve, reject) => {
      const existing = document.querySelector<HTMLScriptElement>(`script[src="${SOCKET_IO_SCRIPT_PATH}"]`);
      if (existing) {
        existing.addEventListener('load', () => resolve(window.io), { once: true });
        existing.addEventListener('error', () => reject(new Error('Unable to load socket.io-client runtime.')), {
          once: true
        });
        return;
      }

      const script = document.createElement('script');
      script.src = new URL(SOCKET_IO_SCRIPT_PATH, serverRoot).toString();
      script.async = true;
      script.onload = () => resolve(window.io);
      script.onerror = () => reject(new Error('Unable to load socket.io-client runtime.'));
      document.head.appendChild(script);
    });
  }

  return ioLibraryPromise;
}

export async function connectWorkspaceSocket(
  onConnect?: (socket: SocketLike, context: LaunchContext) => void
): Promise<SocketLike | null> {
  const context = getLaunchContext();
  
  console.log('[SocketIO] Resolving launch context:', {
    workspaceId: context.workspaceId,
    serverRoot: context.serverRoot,
    workfilePath: context.workfilePath
  });
  
  if (!context.workspaceId) {
    console.error('[SocketIO] No workspaceId found, cannot connect');
    return null;
  }

  const io = await loadIoLibrary(context.serverRoot);
  if (!io) {
    console.error('[SocketIO] Failed to load socket.io-client library');
    return null;
  }

  console.log('[SocketIO] Creating socket connection to:', context.serverRoot);
  console.log('[SocketIO] Workspace ID:', context.workspaceId);
  console.log('[SocketIO] Target room:', `ws:${context.workspaceId}`);

  const socket = io(context.serverRoot, {
    transports: ['websocket', 'polling']
  });

  socket.on('connect', () => {
    console.log('[SocketIO] Connected! SID:', (socket as SocketLike & { id?: string }).id);
    socket.emit('join_room', { room: `ws:${context.workspaceId}` });
    console.log('[SocketIO] Emitted join_room for:', `ws:${context.workspaceId}`);
    onConnect?.(socket, context);
  });

  socket.on('connect_error', (err: any) => {
    console.error('[SocketIO] Connection error:', err?.message || err);
  });

  socket.on('disconnect', (reason: string) => {
    console.log('[SocketIO] Disconnected:', reason);
  });

  return socket;
}
