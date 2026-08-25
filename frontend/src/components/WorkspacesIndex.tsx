import React, { useEffect, useState } from 'react';

type Workspace = {
  workspace_id: string;
  workfile_path: string;
  client_count: number;
  clients: Record<string, number>;
  created_at: string;
};

type WorkspacesResponse = {
  server: {
    host: string;
    port: number;
    lan_enabled: boolean;
  };
  workspaces: Workspace[];
};

interface WorkspacesIndexProps {
  onSelectWorkspace: (id: string) => void;
  fetchWorkspaces: () => Promise<WorkspacesResponse>;
}

export function WorkspacesIndex({ onSelectWorkspace, fetchWorkspaces }: WorkspacesIndexProps) {
  const [data, setData] = useState<WorkspacesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        const result = await fetchWorkspaces();
        setData(result);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to fetch workspaces');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <div style={{ color: '#94a3b8', padding: 20 }}>Loading workspaces...</div>;
  if (error) return <div style={{ color: '#ef4444', padding: 20 }}>Error: {error}</div>;

  return (
    <div style={{ 
      padding: '40px', 
      color: '#f8fafc', 
      fontFamily: 'inherit', 
      display: 'flex', 
      flexDirection: 'column', 
      gap: 24,
      maxWidth: '800px',
      margin: '0 auto'
    }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 24 }}>Active Workspaces</h1>
        <p style={{ color: '#94a3b8', marginTop: 8 }}>
          Server: {data?.server.host}:{data?.server.port} 
          {data?.server.lan_enabled ? ' (LAN enabled)' : ' (Localhost)'}
        </p>
      </div>

      {data?.workspaces.length === 0 ? (
        <div style={{ padding: 20, background: '#1e293b', borderRadius: 8, color: '#94a3b8' }}>
          No active workspaces found. Start a workflow to see it here.
        </div>
      ) : (
        <div style={{ display: 'grid', gap: 12 }}>
          {data?.workspaces.map((ws) => (
            <div 
              key={ws.workspace_id}
              onClick={() => onSelectWorkspace(ws.workspace_id)}
              style={{
                background: '#1e293b',
                padding: '16px',
                borderRadius: 8,
                border: '1px solid #334155',
                cursor: 'pointer',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                transition: 'border-color 0.2s',
                userSelect: 'none'
              }}
              onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#3b82f6')}
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#334155')}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <span style={{ fontWeight: 'bold', fontSize: 14 }}>{ws.workspace_id}</span>
                <span style={{ fontSize: 12, color: '#94a3b8', fontFamily: 'monospace' }}>{ws.workfile_path}</span>
              </div>
              <div style={{ 
                background: '#334155', 
                padding: '2px 8px', 
                borderRadius: 12, 
                fontSize: 11, 
                color: '#e2e8f0' 
              }}>
                {ws.client_count} clients
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
