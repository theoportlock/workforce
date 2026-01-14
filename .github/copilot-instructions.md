# Workforce – AI Coding Agent Guide

- Purpose: GraphML-backed workflow editor/runner; nodes store bash commands and statuses; server exposes REST + Socket.IO; GUI and CLI interact with single machine-wide server managing multiple workspace contexts.
- Primary entrypoints: wf CLI dispatches GUI/RUN/SERVER/EDIT subcommands (workforce/__main__.py); tests live in tests/ and expect pytest.

## Core architecture
- Server discovery: Single machine-wide server discovered via find_running_server() which scans ports 5000-5100 with health checks. resolve_server() finds or auto-starts server. default_workfile() opens ./Workfile if present.
- Workspace contexts: Each workfile gets deterministic workspace ID via compute_workspace_id() (SHA256 hash of absolute path). Server maintains dict of ServerContext objects keyed by workspace ID, created on-demand when first client connects.
- Server start: start_server in workforce/server/__init__.py checks for existing server via find_running_server(), returns early if found. Otherwise sets up Flask + Socket.IO, background option via subprocess, and starts listening on dynamic port (5000-5100).
- REST API: routes in workforce/server/routes.py provide workspace-scoped graph CRUD (URLs: /workspace/{workspace_id}/...), status edits, wrapper updates, node log upload, and /run which seeds run_id and decides roots (failed nodes → otherwise 0 in-degree or selected subset roots).
- Socket layer: workforce/server/sockets.py registers connect/subscribe and translates domain events to Socket.IO events (graph_update, node_ready, status_change, run_complete). Each workspace has dedicated Socket.IO room for event isolation.
- Event bus + graph worker: ServerContext holds mod_queue, active_runs, active_node_run, and dedicated worker thread per workspace. start_graph_worker in workforce/server/queue.py processes queued mutations, emits EventBus events, and enforces subset-only propagation: completed nodes mark outgoing edges to_run (only if target in run set); edges reaching all-ready targets set node status to run; RUN_COMPLETE emitted when no nodes left.
- Graph utilities: workforce/edit/graph.py loads/saves GraphML atomically (temp file + os.replace), adds/removes nodes/edges (UUIDs), edits status/position/labels/wrapper/log. All mutations serialized through server's single-threaded queue worker per workspace; no file locking needed. Graph attributes: node.label command, node.status "", run, running, ran, fail; edge.status "", to_run; graph.wrapper command template.
- Runner: workforce/run/client.py connects via Socket.IO, listens for node_ready, marks status running/ran/fail via /edit-status, sends logs via /save-node-log, wraps commands with wrapper ("{}" placeholder required for interpolation).
- GUI: workforce/gui/app.py launches Tk-based WorkflowApp; GUI background launch spawns python -m workforce gui <url> --foreground.

## Development workflow
- Create or open workflows: wf (opens ./Workfile), wf <file.graphml>, wf gui <path>, wf edit <subcommand> for API edits.
- Run execution: wf run <file|url> [--nodes id1 id2] [--wrapper "docker run -it ubuntu bash -c '{}'"]. Server auto-starts if not running.
- Server admin: wf server start/stop/ls. Server enforces singleton per machine - second start attempt logs existing server location.
- Tests: use pytest from repo root; tests cover scheduler/resume/subset flow (tests/test_runner.py et al.) and multi-workspace isolation (tests/test_integration_multiworkspace.py).
- Packaging: Makefile has PyInstaller/deb/pkg targets; not part of normal dev loop.

## Patterns and cautions
- Always mutate graphs via server queue (ctx.enqueue/enqueue_status) to keep clients in sync and emit events; direct file writes bypass event bus. The queue's single-threaded worker provides concurrency safety without file locking.
- Subset runs: ctx.active_runs tracks allowed nodes per run_id; graph worker skips edges/targets outside the subset. Resume logic prioritizes failed nodes when no explicit selection.
- Status lifecycle: statuses changed via /edit-status; node_ready emits when status set to run; RUN_COMPLETE when no nodes remain run/running for a run_id.
- Wrapper handling: wrapper strings should include "{}" placeholder; Runner falls back to appending command when placeholder absent.
- Workspace isolation: Each workspace has dedicated Socket.IO room, worker thread, mod_queue, and event bus. Operations on one workspace never affect others.
- Context lifecycle: Contexts created on first client connect, destroyed on last disconnect. Workspace IDs deterministic from file paths.
- Logs: node stdout/stderr captured and posted back; GUI log viewer relies on node log attribute.

## When contributing
- **CRITICAL: Run pytest before implementing changes**: Always run `pytest` from repo root and confirm all tests pass before making any code changes. After implementation, run the full suite again to validate.
- Prefer new tests near existing patterns in tests/test_runner.py for scheduler/run changes.
- Keep GraphML compatibility: convert positions to strings and use uuid4 ids for nodes/edges.
- Maintain Socket.IO event names/protocol for GUI compatibility; emit through EventBus rather than direct socket calls.

## Full details
I'll provide a comprehensive breakdown of your Workforce project, which is a visual workflow orchestration and execution system.

## High-Level Architecture

This is a distributed workflow execution system with three main components:
1. **Server** - Central coordinator managing workflow state
2. **GUI** - Visual interface for designing and monitoring workflows
3. **Runner** - Execution engine that runs workflow tasks

---

## Core Modules

### 1. **`workforce/__init__.py`**
Package metadata defining version, author, and email. Standard Python package initialization.

### 2. **`workforce/__main__.py`** - CLI Entry Point
The unified command-line interface that routes all commands:

- **Version handling**: `--version` flag shows package version
- **Default behavior**: Launches GUI with default Workfile in background
- **Subcommands**:
  - `gui`: Launch graphical interface
  - `run`: Execute workflow nodes
  - `server`: Manage background servers (start/stop/list)
  - `edit`: Modify workflow graph via API

**Key pattern**: Uses `resolve_server()` to find or auto-start the single machine-wide server, and `compute_workspace_id()` to convert file paths to workspace IDs.

### 3. **`workforce/utils.py`** - Shared Utilities

**Server Discovery**:
- `find_running_server()`: Scans ports 5000-5100 with /workspaces health checks
- `resolve_server()`: Finds running server or auto-starts one, returns server URL
- `compute_workspace_id()`: Deterministic workspace ID from absolute file path (SHA256 hash)
- `get_workspace_url()`: Constructs workspace URL from workspace ID and server URL

**Network Helpers**:
- `find_free_port()`: Scans 5000-5100 range for available ports
- `is_port_in_use()`: Socket-based port availability check
- `_post()`: HTTP POST wrapper using urllib

**Shell Utilities**:
- `shell_quote_multiline()`: Escapes single quotes for shell safety
- `default_workfile()`: Returns `./Workfile` if it exists

---

## Edit Package (Graph Operations)

### 4. **`workforce/edit/graph.py`** - Graph Persistence

Uses NetworkX DiGraph stored as GraphML files.

**Core Operations**:
- `load_graph(path)`: Reads GraphML, creates empty if missing
- `save_graph(G, path)`: Atomic write using temp file + os.replace

**Node Operations**:
- `add_node_to_graph()`: UUID node ID, stores label/x/y/status attributes
- `remove_node_from_graph()`: Deletes node and all connected edges
- `edit_node_position_in_graph()`: Updates x/y coordinates
- `edit_node_label_in_graph()`: Updates display label
- `save_node_log_in_graph()`: Stores execution output

**Edge Operations**:
- `add_edge_to_graph()`: Creates directed edge with UUID
- `remove_edge_from_graph()`: Deletes specific edge
- `edit_status_in_graph()`: Updates node/edge status (run/running/ran/fail)

**Graph-Level**:
- `edit_wrapper_in_graph()`: Stores command wrapper template in graph metadata

### 5. **`workforce/edit/client.py`** - API Client
Thin wrappers around `utils._post()` for each graph operation. Prints request details and response.

### 6. **`workforce/edit/cli.py`** - Edit CLI
Standalone CLI for graph editing (can be used independently of main CLI).

---

## GUI Package (Visual Interface)

### 7. **`workforce/gui/state.py`** - State Management

**GUIState dataclass** - Single source of truth:
```python
graph: Dict            # Node-link format from server
selected_nodes: List   # Currently selected node IDs
scale: float           # Zoom level (0.1-3.0)
pan_x, pan_y: float    # Pan offset in pixels
wrapper: str           # Command wrapper template
dragging_node: str     # Node being dragged
edge_start: str        # Source node for edge creation
```

Ephemeral UI state for multi-select, panning, etc.

### 8. **`workforce/gui/client.py`** - Server Communication

**ServerClient class**:
- **REST API**: Wraps all graph operations (add/remove nodes, etc.)
- **SocketIO**: Real-time updates from server
  - `connect` event: Logs successful connection
  - `graph_update` event: Full graph refresh
  - `status_change` event: Incremental node status updates
- **Connection management**: Background thread for async connection
- **Error handling**: Graceful degradation if SocketIO fails

### 9. **`workforce/gui/canvas.py`** - Rendering Engine

**GraphCanvas class**:
- Manages Tkinter canvas drawing
- Maintains `node_widgets` dict mapping node IDs to (rectangle, text) tuples

**Core methods**:
- `redraw(graph)`: Full canvas redraw from graph data
- `draw_node()`: Renders single node with:
  - Auto-sized rectangle (based on text + padding)
  - Status-based coloring (running=lightblue, ran=lightgreen, fail=lightcoral)
  - Selection outline (black border)
  - Scaled font size based on zoom
- `draw_edge()`: Draws directed arrows between nodes
  - Clips arrows to node boundaries (not centers)
  - Uses `clip_line_to_box()` for geometric clipping

**Event binding**: Delegates mouse events to callback dict passed from WorkflowApp.

### 10. **`workforce/gui/core.py`** - Main Application

**WorkflowApp class** - The heart of the GUI:

**Initialization**:
- Creates Tkinter canvas + zoom slider
- Sets up menu bar (File/Edit/Run/Tools)
- Establishes server connection (REST + SocketIO)
- Registers event handlers for real-time updates

**Coordinate Systems**:
- **World coordinates**: Logical positions stored in graph (floats)
- **Screen coordinates**: Canvas pixels after scale/pan transform
- `_screen_to_world()`: `(screen - pan) / scale`
- `_world_to_screen()`: `world * scale + pan`

**Mouse Interaction**:
- **Left click**: Select/deselect nodes
- **Left drag**: Move selected nodes (multi-drag supported)
- **Shift+drag**: Selection rectangle
- **Right click**: Middle-click to select single node
- **Right drag**: Create edges between nodes
- **Double-click**: Edit node label
- **Canvas double-click**: Add new node at position

**Zoom Implementation**:
- Mouse wheel or slider controls scale (0.1-3.0)
- Center-anchored: Pan adjusts to keep canvas center fixed
- Formula: `new_pan = center - (center - old_pan) * scale_ratio`

**Keyboard Shortcuts**:
- `r`: Run workflow
- `d`/Delete: Remove selected nodes
- `e`: Connect selected nodes in sequence
- `Shift+E`: Clear edges from selected
- `c`: Clear selected node status
- `Shift+C`: Clear all statuses
- `p`: Edit command wrapper
- `l`: View node log
- `q`: Save and exit

**Run Operations**:
- `run()`: Triggers workflow execution via `/run` endpoint
- Spawns background Runner client thread
- Supports running selected subset or full pipeline

**Status Updates**:
- `on_graph_update()`: Handles server events
  - Partial updates: Only status changes
  - Full updates: Complete graph replacement
- Redraws canvas after state changes

**Node Editing**:
- `node_label_popup()`: Modal dialog for multi-line node labels
- `wrapper_popup()`: Edit command wrapper (uses `{}` placeholder)
- `show_node_log()`: Scrollable text viewer for execution logs

### 11. **`workforce/gui/app.py`** - Launch Logic
- **Background mode**: Spawns subprocess with `--foreground` flag
- **Foreground mode**: Runs Tkinter mainloop directly
- Platform check for `emscripten` (web assembly support)

---

## Run Package (Execution Engine)

### 12. **`workforce/run/client.py`** - Runner Client

**Runner class** - Executes workflow nodes:

**Connection**:
- SocketIO client connects to server
- Listens for `node_ready` events (tells it what to run)
- Filters by `run_id` to handle concurrent runs

**Execution Flow**:
1. Receives `node_ready` event with node_id and label
2. Spawns thread for `execute_node()`
3. Sets status to "running"
4. Executes shell command (with wrapper substitution)
5. Captures stdout/stderr
6. Sets status to "ran" (success) or "fail" (non-zero exit)
7. Sends log output to server

**Command Wrapper**:
- Template with `{}` placeholder: `wrapper.replace('{}', label)`
- Fallback: `wrapper + ' ' + label`
- Uses `shell_quote_multiline()` for escaping

**Lifecycle Events**:
- `run_complete` event: Disconnects when server signals completion
- Handles `run_id` filtering to avoid cross-contamination

### 13. **`workforce/run/cli.py`** - Run CLI
Entry point that resolves target and creates Runner instance.

---

## Server Package (Central Coordinator)

### 14. **`workforce/server/__init__.py`** - Server Orchestration

**start_server() function**:
- **Background mode**: Spawns subprocess (like GUI)
- **Foreground mode**: 
  - Creates Flask app
  - Initializes SocketIO with threading async mode
  - Registers routes and socket handlers
  - Starts graph worker thread
  - Runs SocketIO server (blocking)

**stop_server()**: Sends SIGTERM to PID from registry

**list_servers()**: Pretty-prints active servers from registry

**Server Lifecycle**:
- Registry updated on start/stop
- Cleanup on shutdown (removes registry entry)
- Ping intervals: 30s ping, 90s timeout

### 15. **`workforce/server/context.py`** - Server State

**ServerContext dataclass**:
```python
path: str                          # Workfile path
port: int                          # HTTP/SocketIO port
server_cache_dir: str              # Request cache directory
mod_queue: Queue                   # Serialized graph modifications
socketio: SocketIO                 # Broadcast mechanism
events: EventBus                   # Domain event system
active_runs: Dict[run_id, meta]    # Per-run tracking
active_node_run: Dict[node, run]   # Node→run mapping
```

**Key methods**:
- `enqueue()`: Queues graph mutation, caches to disk
- `enqueue_status()`: Special case for status updates (tracks run associations)

**Run Tracking**:
- Each run gets UUID
- `active_runs[run_id]` stores: `{"nodes": set(), "subset_only": bool}`
- `active_node_run[node_id]` maps nodes to their run_id
- Used to prevent cross-run interference

### 16. **`workforce/server/events.py`** - Event System

**Domain Events** (semantic, not transport):
- `NODE_READY`: Node dependencies satisfied, ready to execute
- `NODE_STARTED`: Node execution began (running status)
- `NODE_FINISHED`: Node completed successfully
- `NODE_FAILED`: Node execution failed
- `RUN_COMPLETE`: All nodes in run finished
- `GRAPH_UPDATED`: Graph structure or state changed

**EventBus class**:
- Pub-sub within server process
- Subscribers register handlers per event type
- `emit()` calls all handlers synchronously
- Error isolation: Handler exceptions don't break others
- **File logging**: Appends JSON lines to `~/.workforce/events.log`
- **Log rotation**: When file exceeds 10MB

**Design principle**: Decouples scheduling logic from transport (SocketIO, REST, etc.)

### 17. **`workforce/server/queue.py`** - Graph Worker

**Worker Thread** (single-threaded serialization):
- Consumes `mod_queue` FIFO
- Executes graph mutations sequentially
- Broadcasts updates via EventBus after each mutation

**Lifecycle Hooks** (inside worker):

**When node becomes "ran"**:
- `_mark_outgoing_edges_ready()`: Sets all outgoing edges to "to_run"
- Only propagates to nodes in the active run (subset awareness)

**When edge becomes "to_run"**:
- `_check_target_node_ready()`: Checks if ALL incoming edges are "to_run"
- If yes: Clears edge statuses, sets target node to "run"
- Emits `NODE_READY` event for runner clients

**Run completion check**:
- After queue drains, spawns thread to check completion
- Marks run complete when no nodes have status "run" or "running"
- Emits `RUN_COMPLETE` event
- Cleans up run tracking dictionaries

**Subset run handling**:
- Filters edge propagation by `active_runs[run_id]["nodes"]`
- Prevents running nodes outside selected subset

### 18. **`workforce/server/routes.py`** - HTTP API

**Graph queries**:
- `GET /get-graph`: Returns node-link JSON with graph metadata
- `GET /get-node-log/<node_id>`: Returns execution log for node

**Graph mutations** (all POST, all enqueued):
- `/add-node`, `/remove-node`
- `/add-edge`, `/remove-edge`
- `/edit-status`, `/edit-node-position`
- `/edit-wrapper`, `/edit-node-label`
- `/save-node-log`

**Client lifecycle**:
- `POST /client-connect`: Increments registry client count
- `POST /client-disconnect`: Decrements, triggers shutdown check

**Run endpoint** (`POST /run`):
- Creates new `run_id`
- **Subset run** (nodes specified):
  - Creates subgraph of selected nodes
  - Finds roots (0 in-degree in subgraph)
  - Tracks only selected nodes
- **Full run** (no nodes specified):
  - Starts from failed nodes (if any)
  - Otherwise starts from root nodes (0 in-degree)
  - Clears status on roots if needed
  - Tracks all nodes
- Queues initial nodes with "run" status

**Status clearing pattern**: Always clears status before setting to "run" to ensure clean state.

### 19. **`workforce/server/sockets.py`** - SocketIO Layer

**Socket handlers**:
- `connect`: Logs connection (doesn't auto-start runs)
- `disconnect`: Logs only (client count managed by REST)
- `subscribe`: Room-based subscriptions (unused currently)

**Event-to-SocketIO bridge**:
- `register_event_handlers()`: Subscribes to EventBus
- Translates domain events to SocketIO messages:
  - `GRAPH_UPDATED` → `graph_update`
  - `NODE_READY` → `node_ready`
  - `NODE_STARTED/FINISHED/FAILED` → `status_change`
  - `RUN_COMPLETE` → `run_complete`

**Shared socketio instance**: Initialized once, shared across modules to avoid multiple instances.

### 20. **`workforce/server/shutdown.py`** - Idle Shutdown

**shutdown_if_idle()**:
- Checks: `clients <= 0` AND `no active_runs`
- Uses deferred shutdown (1s delay in background thread)
- Multiple shutdown methods:
  1. `socketio.stop()`
  2. `os.kill(os.getpid(), SIGTERM)`
  3. `os._exit(0)` as last resort

Called after each client disconnect.

---

## Key Design Patterns

### 1. **Target Resolution**
Any command accepting a file path automatically:
- Checks if server already running
- Launches server if needed
- Returns server URL
- Transparent to user

### 2. **Queue-Based Serialization**
All graph mutations go through single-threaded worker:
- Prevents race conditions
- Ensures atomic file writes
- Provides natural ordering

### 3. **Event-Driven Architecture**
EventBus decouples:
- Graph operations → Status changes → Transport
- Multiple subscribers per event type
- Logging as first-class subscriber

### 4. **Subset Run Isolation**
`active_runs` tracks per-run node sets:
- Edge propagation filtered by run membership
- Prevents cross-contamination
- Supports concurrent independent runs

### 5. **Coordinate Transform Caching**
GUI stores pan/scale in state:
- All geometry operations use helper methods
- Consistent zoom/pan behavior
- Center-anchored zoom feels natural

### 6. **Atomic File Updates**
GraphML writes:
- Write to temp file
- `os.replace()` atomically swaps
- Prevents corruption from crashes

### 7. **Registry-Based Discovery**
Servers register themselves:
- Other processes find servers by file path
- Health checks via port scanning
- Auto-cleanup of dead entries

---

## Data Flow Examples

### Starting a Run:
1. GUI: User clicks "Run" → `POST /run`
2. Server: Creates `run_id`, finds root nodes
3. Server: Queues status changes to "run"
4. Worker: Processes queue, emits `NODE_READY` events
5. Runner: Receives `node_ready`, spawns execution thread
6. Runner: Sets "running", executes command, sets "ran"/"fail"
7. Worker: Detects "ran", marks outgoing edges "to_run"
8. Worker: Checks target nodes, queues next "run" statuses
9. Repeat 4-8 until all nodes complete
10. Worker: Emits `RUN_COMPLETE` when queue empty + no running nodes

### Real-Time GUI Updates:
1. Server: Worker emits `GRAPH_UPDATED` event
2. Server: Event handler calls `socketio.emit('graph_update')`
3. GUI: `ServerClient` receives SocketIO message
4. GUI: Calls `on_graph_update()` callback
5. GUI: Updates `state.graph`, schedules redraw
6. GUI: Canvas redraws all nodes/edges with new data

### Node Position Updates:
1. GUI: User drags node, releases mouse
2. GUI: Calls `update_node_position()` for each selected node
3. GUI: `POST /edit-node-position` for each
4. Server: Enqueues `edit_node_position_in_graph()` tasks
5. Worker: Processes queue, updates GraphML
6. Worker: Emits `GRAPH_UPDATED`
7. All connected GUIs receive update via SocketIO

---

## Concurrency Model

- **Server**: Single worker thread + Flask request threads + SocketIO threads
- **GUI**: Main Tkinter thread + background SocketIO thread + fetch threads
- **Runner**: Main thread + per-node execution threads

**Synchronization**: Queue-based (server), event-driven (GUI), thread-safe (SocketIO)

This architecture enables a distributed, real-time workflow system with visual editing, automatic dependency resolution, and parallel execution.
