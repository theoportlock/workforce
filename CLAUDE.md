# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Workforce is a graph-based workflow execution system with a Flask/Socket.IO server, Tkinter GUI, and distributed execution engine. Workflows are stored as GraphML files where nodes contain bash commands and edges define dependencies.

**Key concepts:**
- Single machine-wide server manages multiple workspace contexts (one per workfile)
- Workspace IDs are deterministic SHA256 hashes of absolute file paths
- Server enforces singleton per machine (default port 5049)
- All graph mutations serialized through per-workspace queue worker
- Subset execution: every run treated as induced subgraph with strict boundary enforcement

## Common Commands

### Development
```bash
# Install in development mode
pip install -e .

# Run tests (CRITICAL: run before and after any changes)
pytest

# Run specific test file
pytest tests/test_runner.py

# Run with coverage
pytest --cov=workforce

# Code quality
ruff check workforce/
mypy workforce/
```

### Running Workforce
```bash
# Launch GUI with default Workfile (or create temp file)
wf

# Open specific workflow
wf <path/to/workflow.graphml>
wf gui <path/to/workflow.graphml>

# Run workflow (entire pipeline or failed nodes)
wf run <workfile>

# Run specific nodes
wf run <workfile> --nodes node_id1 node_id2

# Run with command wrapper (Docker, SSH, conda, etc.)
wf run <workfile> --wrapper 'docker run -it ubuntu bash -c "{}"'
wf run <workfile> --wrapper 'ssh user@host {}'
wf run <workfile> --wrapper 'bash -lc "conda activate myenv && {}"'
```

### Server Management
```bash
# Start server (background by default)
wf server start

# Start in foreground (for debugging)
wf server start --foreground

# Stop server
wf server stop

# List active workspaces
wf server ls

# Register workspace with server
wf server add <path/to/workfile>

# Remove workspace from server
wf server rm ws_abc12345
```

### Graph Editing via CLI
```bash
# Add node
wf edit add-node <workfile> "echo hello" --x 100 --y 200

# Remove node
wf edit remove-node <workfile> <node_id>

# Add edge (dependency)
wf edit add-edge <workfile> <source_id> <target_id>

# Remove edge
wf edit remove-edge <workfile> <source_id> <target_id>

# Edit node/edge status
wf edit edit-status <workfile> node <node_id> "run"
wf edit edit-status <workfile> edge <edge_id> "to_run"

# Edit command wrapper
wf edit edit-wrapper <workfile> 'bash -c "{}"'
```

## Architecture

### Server (workforce/server/)

**Startup flow:**
1. `resolve_server()` checks PID file registry for existing server on port 5049
2. If found, returns URL and exits
3. If not found, calls `start_server()` to initialize Flask + Socket.IO
4. Server waits for client connections

**Workspace management:**
- Each workfile gets deterministic workspace ID via `compute_workspace_id()` (SHA256 of absolute path)
- Server maintains `Dict[workspace_id, ServerContext]` with per-workspace:
  - `mod_queue`: Serialized graph operations queue
  - `events`: EventBus for domain events
  - Worker thread processing queued mutations
  - Socket.IO room for event isolation
  - `active_runs`: Tracks nodes allowed per run_id
  - `active_node_run`: Maps node_id → run_id for concurrent run safety
- Contexts created on first client connect, destroyed on last disconnect

**Key modules:**
- `context.py`: ServerContext dataclass, enqueue methods
- `routes.py`: REST API for graph CRUD and /run endpoint
- `sockets.py`: Socket.IO handlers and EventBus → Socket.IO bridge
- `events.py`: EventBus pub-sub system with file logging
- `queue.py`: Single-threaded graph worker per workspace

### Execution Model (workforce/run/)

**Unified subset execution:**
- Every run is a subset run (full pipeline = subset of all nodes)
- If nodes selected: those nodes form induced subgraph
- If no nodes selected: failed nodes OR zero in-degree nodes
- Scheduler strictly enforces subset boundaries
- Edge propagation only within active run's node set

**Execution loop:**
1. Server emits `NODE_READY` event when node status set to "run"
2. Runner client receives event, spawns thread for `execute_node()`
3. Sets status to "running", executes bash command with wrapper
4. Captures stdout/stderr, sets status to "ran" or "fail"
5. Posts log to server via `/save-node-log`
6. Server worker marks outgoing edges "to_run" (only targets in subset)
7. When target node has ALL incoming edges "to_run", clears edges and sets node to "run"
8. Loop continues until no nodes remain "run" or "running"
9. Server emits `RUN_COMPLETE` event

**Resume logic:**
- Shift+R in GUI or re-running with failed nodes
- Replaces "fail" status with "run"
- Re-enters event loop for dependency checking
- Strictly bounded by subset selection

### GUI (workforce/gui/)

**Structure:**
- `state.py`: GUIState dataclass (graph, selected_nodes, scale, pan_x, pan_y, wrapper, etc.)
- `client.py`: ServerClient wrapping REST API + Socket.IO real-time updates
- `canvas.py`: GraphCanvas rendering nodes/edges with Tkinter
- `core.py`: WorkflowApp main application with mouse/keyboard handlers
- `app.py`: Launch logic (background vs foreground mode)

**Coordinate systems:**
- World coordinates: Logical positions in graph (floats)
- Screen coordinates: Canvas pixels after scale/pan transform
- `_screen_to_world()`: `(screen - pan) / scale`
- `_world_to_screen()`: `world * scale + pan`

**Keyboard shortcuts:**
- `r`: Run workflow (selected subset or full)
- `Shift+R`: Resume failed nodes
- `d`/Delete: Remove selected nodes
- `e`: Connect selected nodes in sequence
- `Shift+E`: Clear edges from selected
- `c`: Clear selected node status
- `Shift+C`: Clear all statuses
- `p`: Edit command wrapper
- `l`: View node log (stdout/stderr)
- `t`: Open terminal view
- `q`: Save and exit

### Graph Storage (workforce/edit/)

**GraphML format (NetworkX):**
- Nodes: `id`, `label` (bash command), `x`, `y`, `status` ("", "run", "running", "ran", "fail")
- Edges: `source`, `target`, `status` ("", "to_run")
- Graph: `wrapper` (command template with "{}" placeholder)

**Atomic writes:**
- `save_graph()` writes to temp file, uses `os.replace()` for atomic swap
- No file locking needed (queue worker serializes mutations)

**All mutations via server queue:**
- Direct file writes bypass event bus
- Use `ctx.enqueue()` or REST API for all changes
- Queue worker emits events after each mutation

## Critical Development Patterns

### Always Run Tests First
**CRITICAL:** Before implementing ANY changes, run `pytest` from repo root and confirm all tests pass. After implementation, run full suite again to validate. Tests cover:
- Scheduler/resume/subset flow (tests/test_runner.py)
- Multi-workspace isolation (tests/test_integration_multiworkspace.py)
- Edge types and batch operations
- Event emission and status transitions

### Mutation via Queue Only
Never directly call graph.py functions or write GraphML files. Always mutate through:
- Server: `ctx.enqueue()` or `ctx.enqueue_status()`
- Client: REST API (`/add-node`, `/edit-status`, etc.)
- This ensures events emit and clients stay synchronized

### Subset Run Boundaries
- `ctx.active_runs[run_id]["nodes"]` defines allowed node set
- Graph worker filters edge propagation: `if target in ctx.active_runs[run_id]["nodes"]`
- Resume never propagates outside original selection
- Completion check: no nodes with status "run" or "running" in active set

### Wrapper Handling
- Template must include "{}" placeholder for command interpolation
- Runner uses `wrapper.replace('{}', shell_quote_multiline(label))`
- Falls back to `wrapper + ' ' + label` if no placeholder
- Examples: `'docker run -it image bash -c "{}"'`, `'ssh host {}'`

### Status Lifecycle
- "" (empty): Initial state or cleared
- "run": Queued for execution (triggers NODE_READY event)
- "running": Currently executing
- "ran": Completed successfully
- "fail": Non-zero exit code
- Edge status: "" or "to_run"

### Workspace Isolation
Each workspace has:
- Dedicated Socket.IO room (workspace_id)
- Separate worker thread and mod_queue
- Independent EventBus instance
- Own active_runs and active_node_run dicts
Operations on one workspace never affect others

### Context Lifecycle
- Created on first client connect via `/client-connect`
- Destroyed on last disconnect via `/client-disconnect`
- Server auto-shuts down when idle (no clients, no active runs)
- Next connection auto-starts new server instance

## Testing

Test fixtures (tests/conftest.py):
- `temp_graph_file`: Temporary GraphML file path
- `mock_server_context`: ServerContext with mocked Socket.IO

Test patterns:
- Create graph with `edit.add_node_to_graph()`, `edit.add_edge_to_graph()`
- Start worker with `start_graph_worker(ctx)` in background thread
- Use `ctx.enqueue()` to queue mutations
- Mock `socketio.emit()` and assert event emissions
- Check graph state with `edit.load_graph(path)`

## GraphML Compatibility

- Node IDs: Use `uuid.uuid4()` for uniqueness
- Positions: Store as strings (x, y coordinates)
- Multi-line commands: Properly escaped in label attribute
- NetworkX node-link format for JSON serialization

## Socket.IO Event Protocol

Domain events (EventBus) → Socket.IO events:
- `GRAPH_UPDATED` → `graph_update` (full graph or partial status)
- `NODE_READY` → `node_ready` (node_id, label, run_id)
- `NODE_STARTED`/`FINISHED`/`FAILED` → `status_change` (node_id, status, run_id)
- `RUN_COMPLETE` → `run_complete` (run_id)

Emit through EventBus, not direct socketio calls. Handler registration in `sockets.register_event_handlers()`.

## Remote Workspace Access

Workspaces can be accessed remotely via workspace URL:
```bash
# From server machine
wf server ls  # Shows workspace URLs

# From remote machine
wf gui http://server:5049/workspace/ws_abc12345
wf run http://server:5049/workspace/ws_abc12345 --nodes node1
```

Workspace URLs format: `http://host:port/workspace/ws_XXXXXXXX` where ws_XXXXXXXX is the workspace ID.
