## Purpose

Workforce is a graph-based workflow execution system.

- GraphML-backed scheduler (like a DAG)
- Flask + Socket.IO server (port 5049)
- Tkinter GUI
- React Flow frontend (Vite build)
- Local shell execution engine
- Optional execution wrapper (`{}` substitution)

---

## Non-Negotiable Rules

### 1. All Graph Mutations Go Through the Server Queue

Never:
- Write GraphML directly
- Mutate graph state outside `ServerContext.enqueue()`

All mutations are serialized per workspace via `server/queue.py`.

---

### 2. Runs Operate on an Induced Subgraph

Each run defines allowed nodes:

    ctx.active_runs[run_id]["nodes"]

- Only these nodes may transition state
- Only edges within this set may propagate readiness
- No global execution side effects

---

### 3. Node State Machine

Valid states:

    "" ΓåÆ "run" ΓåÆ "running" ΓåÆ "ran"
                            Γåÿ "fail"
    "fail" ΓåÆ "run"

No other transitions allowed.

---

### 4. Wrapper Semantics

Wrapper must contain `{}`:

    wrapper.replace("{}", cmd)

Fallback:

    wrapper + " " + cmd

---

## Architecture

### Server
- `server/context.py` ΓÇö authoritative graph + enqueue
- `server/queue.py` ΓÇö serialized mutation worker
- `server/routes.py` ΓÇö REST API
- `server/sockets.py` ΓÇö Socket.IO bridge

### Execution
- `run/` ΓÇö dependency resolution + shell execution

### GUI (Tkinter)
- `gui/state.py` ΓÇö canonical UI state
- `gui/canvas.py` ΓÇö rendering
- `gui/core.py` ΓÇö bootstrap

### Web Frontend
- `frontend/` ΓÇö React Flow app (Vite)
- Built via `./build-frontend.sh`

---

## Development

Always run before and after changes:

    pytest
    ruff check workforce/
    mypy workforce/

Frontend rebuild:

    ./build-frontend.sh

---

## Key Principle

Single authoritative graph per workspace.
All mutations serialized.
All execution bounded to a run-specific subgraph.

