# AGENTS.md

## Project Overview

Graph-based workflow execution system: Flask/Socket.IO server, Tkinter GUI, GraphML storage. Nodes contain bash commands, edges define dependencies.

- Single server (port 5049) manages multiple workspaces (one per file, SHA256 ID)
- All mutations serialized through per-workspace queue worker
- Subset execution: every run is an induced subgraph

## Commands

### Development
```bash
pip install -e .     # Install dev mode
pytest               # Run tests (ALWAYS before/after changes)
pytest tests/test_runner.py
ruff check workforce/
mypy workforce/
```

### Running
```bash
wf                                    # Launch GUI
wf gui <file.graphml>
wf run <workfile>                     # Run failed/pending
wf run <workfile> --nodes node1       # Run specific nodes
wf run <workfile> --wrapper 'docker run image bash -c "{}"'
```

### Server
```bash
wf server start           # Start (bg)
wf server start --foreground
wf server stop
wf server ls
```

### Edit CLI
```bash
wf edit add-node <file> "cmd" --x 100 --y 200
wf edit add-edge <file> <src> <tgt>
wf edit edit-status <file> node <id> "run"
```

## Critical Patterns

### Testing
Run `pytest` before AND after ANY changes.

### Mutations
Always use server queue: `ctx.enqueue()` or REST API. Never write GraphML directly.

### Subset Boundaries
`ctx.active_runs[run_id]["nodes"]` defines allowed nodes. Edge propagation filtered by this set.

### Wrapper
Template needs `{}` placeholder: `wrapper.replace('{}', cmd)`. Fallback: `wrapper + ' ' + cmd`.

### Status
- `""` (empty): Initial
- `"run"`: Queued → emits NODE_READY
- `"running"`: Executing
- `"ran"`: Success
- `"fail"`: Failed

## Architecture

| Module | Purpose |
|--------|---------|
| `server/context.py` | ServerContext, enqueue methods |
| `server/routes.py` | REST API |
| `server/sockets.py` | Socket.IO + EventBus bridge |
| `server/queue.py` | Per-workspace mutation worker |
| `run/` | Execution engine |
| `gui/` | Tkinter UI (state.py, canvas.py, core.py) |

## Socket Events

`GRAPH_UPDATED` → `graph_update` | `NODE_READY` → `node_ready` | `RUN_COMPLETE` → `run_complete`

## Environment

- `WORKFORCE_SERVER_URL`: http://127.0.0.1:5049
- `WORKFORCE_STARTUP_TIMEOUT`: 30
- `WORKFORCE_LOG_DIR`: ~/.workforce
