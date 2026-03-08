# AGENTS.md

## Purpose

Workforce is a **graph-based workflow execution system**:

-   GraphML-backed DAG scheduler
-   Flask + Socket.IO server (port 5049)
-   Tkinter desktop GUI
-   React Flow web frontend (Vite build)
-   Local shell execution engine
-   Optional command wrapper (`{}` substitution)

# Core Invariants (Non-Negotiable)

## 1. All Graph Mutations Go Through the Server Queues

Never: - Modify GraphML files directly - Mutate in-memory graph state
outside `ServerContext.enqueue()`

All mutations **must** be serialized per workspace via:

    server/queue.py

This guarantees: - Deterministic ordering - Cross-client consistency
(Tk + Web) - Safe concurrent edits

## 2. Runs Operate on an Induced Subgraph

Each run defines its allowed node set:

    ctx.active_runs[run_id]["nodes"]

Rules:

-   Only these nodes may transition state
-   Only edges within this induced set may propagate readiness
-   No execution may affect nodes outside the run
-   No global side effects

Execution is always bounded to the run subgraph.

## 3. Node State Machine (Strict)

Valid states:

    "" → "run" → "running" → "ran"
                      ↘
                       "fail"

    "fail" → "run"

No other transitions are allowed.

Invalid transitions must raise errors.

## 4. Wrapper Semantics

If a wrapper is configured, it must contain `{}`:

    wrapper.replace("{}", cmd)

If `{}` is missing, fallback to:

    wrapper + " " + cmd

Wrapper logic must remain deterministic and side-effect free.

# Architecture

## Server (Authoritative)

-   `server/context.py` --- canonical graph state + enqueue
-   `server/queue.py` --- serialized mutation worker
-   `server/routes.py` --- REST API
-   `server/sockets.py` --- Socket.IO bridge

The server owns truth.\
All clients are projections.

## Execution Engine

-   `run/` --- dependency resolution + shell execution

Execution never mutates graph state directly.\
It must enqueue mutations.

## Tkinter GUI

-   `gui/state.py` --- canonical UI state
-   `gui/canvas.py` --- rendering
-   `gui/core.py` --- bootstrap

## Web Frontend

-   `frontend/` --- React Flow app (Vite)

-   Built via:

    ./build-frontend.sh

The web UI is a real-time projection of server state via Socket.IO.

# Development Discipline

Before and after any change, run:

    pytest
    ruff check workforce/
    mypy workforce/

If frontend changes were made:

    ./build-frontend.sh

Never commit broken type checks or lint errors.

# Guiding Principle

-   One authoritative graph per workspace.
-   All mutations serialized.
-   All execution scoped to a run subgraph.
-   Clients render --- server decides.

