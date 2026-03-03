export type WorkforceStatus = '' | 'run' | 'running' | 'ran' | 'fail';

export interface BackendGraphNode {
  id: string;
  label: string;
  x?: string | number;
  y?: string | number;
  status?: WorkforceStatus;
  command?: string;
  stdout?: string;
  stderr?: string;
  log?: string;
}

export interface BackendGraphLink {
  source: string;
  target: string;
  id?: string;
  status?: string;
  edge_type?: string;
}

export interface BackendNodeLinkGraph {
  nodes: BackendGraphNode[];
  links: BackendGraphLink[];
  graph?: {
    wrapper?: string;
  };
}

export interface WorkflowNodeData {
  label: string;
  command: string;
  status: WorkforceStatus;
  stdout?: string;
  stderr?: string;
  log?: string;
}
