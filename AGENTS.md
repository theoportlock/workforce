Purpose
Workforce is a graph-based workflow system: a GraphML-backed DAG scheduler with a Flask + Socket.IO server (port 5049), React Flow web UI (Vite), local shell execution, and optional {} command wrapper. The Tkinter GUI is being deprecated in favor of the web frontend.

Core Invariants
All graph mutations must go through ServerContext.enqueue() (see server/queue.py); never modify GraphML or in-memory state directly. This guarantees deterministic ordering and consistency across clients. Execution is always scoped to a run-specific induced subgraph (ctx.active_runs[run_id]["nodes"]): only those nodes may change state, only internal edges propagate readiness, and no global side effects are allowed. The node state machine is strict: "" → "run" → "running" → "ran" with "running" → "fail" and "fail" → "run"; all other transitions are invalid. Wrappers must apply deterministically via {} substitution (wrapper.replace("{}", cmd)) or fallback concatenation.

Architecture
The server is authoritative (server/context.py, server/queue.py, server/routes.py, server/sockets.py); clients are projections. The execution layer (run/) handles dependency resolution and shell execution but must enqueue all state changes. The web frontend (frontend/) reflects server state via Socket.IO and is built with ./build-frontend.sh.

Development
Run pytest after changes and rebuild the frontend if modified. Do not commit broken tests, types, or lint.

Principles
Single authoritative graph per workspace, serialized mutations, run-scoped execution, server decides and clients render, prefer simplicity, and keep this file updated.
