.. _architecture:

============
Architecture
============

Workforce is a graph-based workflow system. A Flask and Socket.IO server is
authoritative for a loaded GraphML workfile; the React Flow web frontend and the
CLI are clients of that server. Multiple users can edit and run the same
worksession.

Authoritative state
-------------------

``ServerContext`` owns the in-memory graph, active runs, and client updates.
Every graph mutation is queued through ``ServerContext.enqueue()`` and processed
by ``server/queue.py``. This serializes mutations, keeps clients consistent,
and prevents direct GraphML or in-memory edits from bypassing the server.

The server runs on port 5049 by default. It hosts worksessions loaded from
GraphML workfiles and broadcasts graph changes to connected clients.

Execution model
---------------

Every execution has an active, run-induced subgraph stored with its run ID.
Only nodes in that subgraph may change state, and only edges whose two endpoints
are in it can propagate scheduling. This prevents a subset run from affecting
the rest of the workfile.

Starting nodes are chosen as follows:

1. A supplied subset is run as its induced subgraph.
2. Without a subset, selected nodes are used as the starting nodes.
3. With no selection, failed nodes are selected.
4. If no nodes have failed, nodes with in-degree zero in the relevant graph are
   started.

The state machine is ``""`` → ``run`` → ``running`` → ``ran``. A running node
may move to ``fail``; a failed node may move back to ``run``. Other transitions
are invalid.

Scheduling
----------

Changing a node to ``run`` starts it. Workforce records its PID, exit code,
stdout, and stderr as node attributes. On success the server emits a ``ran``
change for that run and marks outgoing active-subgraph edges ``ready``.

Each ready edge prompts a check of its target. The target becomes ``run`` when
all incoming blocking edges are ready. The ready flags on the consumed incoming
edges are then cleared and the same cycle continues. Non-blocking edges are not
prerequisites: all incoming *blocking* edges must be ready, but an arriving
non-blocking edge need not wait for other non-blocking edges.

Loops
-----

The graph need not be acyclic. Workforce supports loops, including loops that
re-trigger work through non-blocking edges. Because repeated triggers can
continue indefinitely, termination belongs to the workflow's commands or graph
design. Loop support does not relax run boundaries: an edge outside the active
subgraph never causes state changes or execution.

Command wrappers
----------------

Before local shell execution, a wrapper is applied deterministically. A wrapper
containing ``{}`` uses ``wrapper.replace("{}", cmd)``; otherwise the wrapper is
concatenated with the command.

Frontend
--------

The Vite-built React Flow frontend is a projection of server state. It edits
nodes and edges, launches runs, and receives real-time changes through
Socket.IO. Rebuild it explicitly with ``./build-frontend.sh`` after frontend
changes.
