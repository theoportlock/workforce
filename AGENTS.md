Purpose
Workforce is a graph-based workflow system: a GraphML-backed scheduler with a Flask + Socket.IO server (port 5049), a React Flow web frontend (Vite), local shell execution, and optional {} command wrapper. The Tkinter GUI (gui/) is being deprecated in favor of the web frontend.

Core Invariants
All graph mutations must go through ServerContext.enqueue() via server/queue.py; never modify GraphML or in-memory state directly. This enforces deterministic ordering, concurrency safety, and cross-client consistency. Execution is strictly scoped to a run-induced subgraph (ctx.active_runs[run_id]["nodes"]): only those nodes may change state, only internal edges propagate readiness, and no external side effects are allowed. Node states follow a strict machine: "" → "run" → "running" → "ran" with "running" → "fail" and "fail" → "run"; all other transitions are invalid. Wrappers must apply deterministically via {} substitution (wrapper.replace("{}", cmd)) or fallback concatenation.

Architecture
The server is authoritative (server/context.py, server/queue.py, server/routes.py, server/sockets.py) and owns all state; clients are projections. The execution layer (run/) handles dependency resolution and shell execution but must enqueue all mutations. The Tkinter GUI (gui/state.py, gui/canvas.py, gui/core.py) is legacy/deprecated. The web frontend (frontend/) is a React Flow app built with Vite and served as a real-time Socket.IO projection of server state; it must be built explicitly via ./build-frontend.sh.

Development
After any change run pytest. If frontend code is modified, rebuild with ./build-frontend.sh. Never commit with failing tests, type errors, or lint issues.

Principles
Single authoritative graph per workspace, serialized mutations, run-scoped execution, server decides and clients render, prefer simplicity, and keep this file updated.
