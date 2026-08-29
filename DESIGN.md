# Workforce – Design Documentation

## High-Level Overview

**Workforce** is a graph-based workflow system that creates and runs bash commands in dependency order. It features:

- **GraphML-backed workflows**: Bash commands as nodes in a directed acyclic graph (DAG)
- **Client-server architecture**: Single machine-wide server managing multiple workspace contexts
- **Multi-client support**: Multiple GUIs/CLIs can connect to same workflow simultaneously
- **Real-time event system**: Socket.IO for synchronous updates across clients
- **Subset execution**: Run specific subgraphs or entire workflows with unified execution model
- **Resume capability**: Recover from failed nodes while respecting boundaries
- **Flexible edge types**: Blocking (strict dependency) and non-blocking (soft trigger) edges

---

## Core Architecture

### 1. Server (`workforce/server/`)

**Singleton Pattern**: Single machine-wide server per machine
- **Port**: Default 5049 (configurable)
- **Discovery**: PID file registry for singleton enforcement
- **Startup**: Checks for existing server, returns early if found; otherwise starts Flask + Socket.IO

**Workspace Management**:
- Each workfile gets deterministic workspace ID: `SHA256(absolute_path)`
- Server maintains dict of `ServerContext` objects keyed by workspace_id
- Contexts created on-demand when first client connects
- Contexts destroyed when last client disconnects
- Each context is fully isolated with dedicated:
  - `mod_queue`: Serialized mutation queue
  - `EventBus`: Per-workspace event system
  - Worker thread: Queue processor
  - Socket.IO room: Event broadcasting
  - Active runs tracking: Per-run node sets

**Server Endpoints** (`/workspace/{workspace_id}/...`):
- **Edit API**: Modify graph structure (add/remove nodes, edges)
- **Run API**: Initiate execution with `nodes` (subset) and `wrapper` parameters
- **Status API**: Real-time node/edge status via Socket.IO
- **Logs API**: Retrieve stdout/stderr from completed nodes

**Server Shutdown**:
- Automatic on idle (no clients + no active runs) after 1-second delay
- Manual via `wf server stop`
- Gracefully terminates running processes, updates statuses, cleans up resources

### 2. Workspace Context (`workforce/server/context.py`)

**ServerContext** is the source of truth for a workspace:
- Maintains current graph state in memory
- Serializes all mutations through `mod_queue`
- Tracks active runs: `active_runs[run_id] = set_of_node_ids`
- Emits domain events via `EventBus`

**Single-threaded queue worker**: All graph mutations go through `mod_queue` per workspace
- No file locking needed; concurrency safety via serialization
- Graph saved atomically (temp file + `os.replace`)
- Prevents concurrent writes and corruption

### 3. Event System (`workforce/server/events.py`, `workforce/server/sockets.py`)

**Event Types**:
- `NODE_READY`: All dependencies met, status → `run`
- `NODE_STARTED`: Execution begun, status → `running`
- `NODE_FINISHED`: Success, status → `ran`
- `NODE_FAILED`: Error, status → `fail`
- `RUN_COMPLETE`: All nodes in run finished/failed
- `GRAPH_UPDATED`: Structure or attributes modified

**Broadcasting**:
- Events emitted from server via `EventBus`
- Socket.IO broadcasts to workspace-specific rooms (isolated)
- Each event tagged with client ID for multi-client coordination
- Real-time synchronization across all connected clients

### 4. Graph Mutation Queue (`workforce/server/queue.py`)

**Graph Worker Thread**:
- Single worker per workspace processes `mod_queue`
- Dequeues mutations, applies to in-memory graph, emits events
- Re-saves graph to disk atomically after each batch

**Mutation Operations**:
- Add/remove nodes (UUID-based)
- Add/remove edges (UUID-based)
- Edit node status, position, label, wrapper, log
- Edit edge status

**Critical Constraint**: All graph mutations must route through this queue
- Direct file writes bypass event bus → clients out of sync
- Queue ensures atomicity and consistency

---

## Execution Model

### Unified Subset Execution

Every run is treated as a subset run (unified model):

**Node Selection Logic**:
1. **Explicit**: If specific nodes selected (CLI `--nodes` or GUI selection) → induced subgraph
2. **Resume**: If no explicit selection, check for `failed` nodes → auto-select for re-execution
3. **Full**: If no explicit/failed selection → select all nodes with zero in-degree (full workflow)

**Execution Initialization**:
1. Extract target subset from main graph
2. Find nodes with zero in-degree relative only to subset
3. Transition these to `run` state
4. Nodes start immediately if their master dependencies omitted from subset

**Subgraph Boundary Enforcement**:
- Scheduler strictly confines propagation to active subset
- When node completes: only evaluate outgoing edges within filtered subgraph
- Edges leading outside subset are **ignored** (capped execution)

### Execution Loop

1. **Node Execution**:
   - Subprocess spawned for node command
   - stdout/stderr captured in real-time
   - Outputs stored as node attributes (log)
   - Viewable from GUI (press 's')

2. **Event Emission**:
   - On completion: `NODE_FINISHED` event (or `NODE_FAILED` on error)
   - Event tagged with client ID
   - Broadcast to all connected clients via WebSocket

3. **Scheduler Update**:
   - Event triggers scheduler to retrieve filtered subnetwork map
   - All valid outgoing edges (within subnetwork) → `to_run` status
   - `GRAPH_UPDATED` event broadcast

4. **Dependency Check**:
   - Status change prompts target node to check dependencies
    - Node transitions to `run` state only if:
      - **ALL incoming blocking edges** within subset are `to_run`
      - **AND** at least one incoming edge (blocking or non-blocking) is `to_run`
    - Once satisfied:

     - Clear statuses from incoming edges
     - Begin execution
     - Loop back to step 1

### Dependency Resolution

**Edge Types** determine how dependencies are checked:

**Blocking Edges** (default):
- Strict hard dependency
- Target waits for **ALL** incoming blocking edges to be `to_run`
- Used for enforcing execution order

**Non-Blocking Edges**:
- Soft trigger relationship
- Target transitions to `run` when **ANY** non-blocking edge becomes `to_run`, provided all incoming blocking edges are already satisfied
- Enables re-triggering (node executes multiple times in single run)
- Does not block other incoming edges

**Resolution Algorithm**:
```
When upstream node completes (status → ran):
  1. Mark all outgoing edges as to_run
  2. For each downstream node:
     - If edge is BLOCKING:
       Check if ALL incoming blocking edges are to_run
       → If yes: Set node to run
       → If no: Remain waiting
      - If edge is NON-BLOCKING:
        Check if all incoming blocking edges are to_run
        → If yes: Set node to run
        → If no: Remain waiting

  3. Respect subset boundaries:
     Only process edges with both endpoints in subset
     Ignore edges leading outside subset
```

**Cycle Detection**:
- Only checks **blocking edges** for cycles
- Non-blocking edges ignored (allows safe cycles)
- Detects cycles before execution begins
- Error if blocking edges form cycle

### Resume Functionality

**Resume Logic** (Shift+R in GUI):
1. Identify nodes in `failed` state
2. Replace `failed` status with `run`
3. Re-trigger event loop
4. Scheduler re-checks dependencies
5. If deps met, queue for execution
6. Pipeline continues through normal dependency checking

**Boundary Enforcement**:
- Strictly bounded by original subset
- Never propagates to nodes outside original selection
- Clean status management prevents zombie processes

---

## Data Flow

### GraphML File Format

**Nodes**:
- `id`: UUID
- `label`: Bash command
- `status`: `""` | `run` | `running` | `ran` | `fail`
- `log`: stdout/stderr combined
- `x`, `y`: Position (stored as strings)

**Edges**:
- `id`: UUID
- `status`: `""` | `to_run`
- `edge_type`: `blocking` | `non-blocking` (default: blocking)

**Graph Attributes**:
- `wrapper`: Command template with `{}` placeholder (e.g., `bash -c '{}'`)

### File Persistence

- **Load**: `load_graph(path)` → NetworkX DiGraph
- **Save**: `save_graph(graph, path)` → GraphML via atomic write (temp + `os.replace`)
- **Concurrency**: All mutations serialized through queue worker (one per workspace)
- **Crash-safe**: Atomic file replacement prevents partial writes
- **No file locking**: Singleton server + serialized queue eliminates contention

### Network Communication

**HTTP API** (Flask):
- RESTful endpoints for mutations
- JSON request/response
- Workspace-scoped URLs: `/workspace/{workspace_id}/...`
- Server discovered via `find_running_server()`

**WebSocket** (Socket.IO):
- Bidirectional real-time communication
- Event broadcasting from server to clients
- Workspace-specific rooms (event isolation)
- Persistent connections during execution
- Status updates and log streaming

---

## Process Management

### Command Execution

- Commands run via Python `subprocess` module
- Separate process per node
- stdout/stderr captured in real-time
- Exit codes determine success/failure

### Process Lifecycle

1. **Spawn**: Process created when node transitions to `run`
2. **Monitor**: Output streams monitored via threads
3. **Complete**: Process terminates, exit code checked
4. **Cleanup**: Resources released, status updated

### Parallel Execution

- Multiple nodes run simultaneously
- Limited only by available system resources
- Dependency constraints prevent invalid parallelism
- No explicit parallelism limit

---

## Command Wrapping

**Wrapper Mechanism**:
- Global template with `{}` placeholder
- Applied to all commands in run
- Allows prefixes/suffixes: Docker, SSH, tmux, conda, parallel, nohup, etc.

**Examples**:
```bash
--wrapper 'bash -c "{}"'                      # Standard bash
--wrapper 'docker run -it ubuntu bash -c "{}"'  # Docker
--wrapper 'ssh ADDRESS {}'                    # Remote execution
--wrapper 'conda activate ENV && {}'          # Conda environment
--wrapper 'tmux send-keys {} C-m'             # tmux session
--wrapper 'parallel {} ::: FILES'             # GNU parallel
```

---

## Client Types

### 1. Tkinter GUI (`workforce/gui/`)
- Visual workflow editor
- Real-time node status display
- Interactive execution control
- Background launch: `python -m workforce gui <url> --foreground`

### 2. CLI (`workforce/__main__.py`)
- Entry point: `wf` or `python -m workforce`
- Subcommands:
  - `wf` / `wf edit <subcommand>`: Edit workflows
  - `wf run <file> [--nodes id1 id2] [--wrapper "..."]`: Execute
  - `wf server start/stop/ls`: Server admin
  - `wf gui <path>`: Launch GUI

### 3. Programmatic Clients
- **Edit Client** (`workforce/edit/client.py`): Modify graphs programmatically
- **Run Client** (`workforce/run/client.py`): Execute workflows programmatically

All clients communicate with server via HTTP + Socket.IO.

---

## Codebase Structure

```
workforce/
├── __main__.py              # CLI entry point (dispatch GUI/RUN/SERVER/EDIT)
├── utils.py                 # Workspace utilities, server discovery, config
│
├── server/
│   ├── __init__.py          # Server launcher, singleton check, port config
│   ├── context.py           # ServerContext: source of truth per workspace
│   ├── events.py            # EventBus and event definitions
│   ├── queue.py             # Serialized mutation queue + worker thread
│   ├── routes.py            # REST API endpoints
│   └── sockets.py           # Socket.IO connection handlers
│
├── edit/
│   ├── graph.py             # GraphML load/save, node/edge CRUD
│   ├── client.py            # Edit client (HTTP API caller)
│   └── cli.py               # Edit CLI
│
├── run/
│   ├── __init__.py          # Run orchestration
│   ├── client.py            # Run client (Socket.IO listener, subprocess runner)
│   └── cli.py               # Run CLI
│
├── gui/
│   ├── core.py              # Core GUI logic
│   ├── app.py               # Tk application launcher
│   ├── canvas.py            # Canvas drawing and interaction
│   ├── client.py            # GUI client (Socket.IO listener)
│   └── state.py             # GUI state management
│
├── web/
│   ├── bridge.py            # Web bridge (HTTP proxy to local server)
│   ├── launcher.py          # Web launcher
│   └── static/              # Bundled React Flow frontend
│
└── tests/
    ├── test_runner.py       # Scheduler/resume/subset flow tests
    ├── test_integration_multiworkspace.py  # Multi-workspace isolation
    └── ...
```

---

## Key Design Patterns

### 1. Mutation Queue Serialization
**Why**: Ensures consistency, prevents race conditions
- All graph mutations → `mod_queue` → single worker thread → atomic save
- No file locking needed
- Clients always see consistent state

### 2. Event-Driven Architecture
**Why**: Real-time multi-client sync without polling
- Mutations emit events
- Events broadcast via Socket.IO to workspace rooms
- All clients receive updates simultaneously

### 3. Subset Execution Model
**Why**: Handles edge cases, enables resumption
- Every run is subset run (unified)
- Boundaries strictly enforced
- Supports failed node resumption without side effects

### 4. Deterministic Workspace IDs
**Why**: Consistent identification across sessions
- SHA256 hash of absolute file path
- No user input needed
- Enables stateless server discovery

---

## Security & Performance Notes

### Security
- Commands execute with user shell permissions
- No authentication (local use assumed)
- Registry file permissions control access
- WebSocket connections unencrypted (localhost only)
- Command injection risk if untrusted workfiles used

### Performance
- Graph size limited by memory
- NetworkX provides efficient operations
- WebSocket events minimal overhead
- Subprocess spawning system-dependent
- Large stdout/stderr captured in memory (consider log rotation)

---

## Critical Invariants

1. **Single Queue Per Workspace**: All mutations serialized through `mod_queue`
2. **Workspace Isolation**: No cross-workspace interference
3. **Subset Boundaries**: Execution never leaves active subset
4. **Atomicity**: GraphML writes always atomic (temp + replace)
5. **Event Ordering**: Events tagged with run_id and client_id for coordination
6. **Status Lifecycle**: Statuses changed only via `/edit-status`, triggering events

---

## Development Entry Points

| Task | Command |
|------|---------|
| Create/open workflow | `wf` or `wf <file.graphml>` |
| GUI | `wf gui <path>` |
| Edit workflow | `wf edit <subcommand>` |
| Run workflow | `wf run <file> [--nodes ...] [--wrapper ...]` |
| Server admin | `wf server start/stop/ls` |
| Tests | `pytest` from repo root |

---
