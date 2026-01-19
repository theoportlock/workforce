.. _architecture:

============
Architecture
============

This page describes the internal architecture and design of Workforce.

Overview
--------

Workforce uses a client-server architecture to manage workflow execution. The system is built around a Flask API server that maintains workflow state and coordinates execution across multiple clients.

**Backward Compatibility Note**: Workforce 2.0 introduces :ref:`non-blocking edges <non-blocking-edge>` for more flexible workflow execution. Existing workflows remain fully compatible—all edges default to :ref:`blocking edges <blocking-edge>`, preserving the strict dependency semantics of earlier versions. New workflows can optionally mix blocking and non-blocking edges for advanced execution patterns.

Core Components
---------------

Server
~~~~~~

The server component is the heart of Workforce's execution engine. A single machine-wide server manages multiple workflows through isolated workspace contexts. It manages:

* **Workflow State** - Tracks node and edge status during execution
* **Event System** - Pub/sub event broadcasting for real-time updates
* **Execution Queue** - Schedules nodes based on dependency resolution
* **Client Coordination** - Handles multiple simultaneous clients
* **Workspace Contexts** - Isolated execution environments per workfile

Server Startup Process
^^^^^^^^^^^^^^^^^^^^^^

When starting a server (typically automatic when running ``wf`` commands):

1. **Singleton Check**: The system checks the PID file registry to detect any existing server

2. **Server Discovery**: If a server is already running:
   
   * The system logs the existing server location
   * Exits without starting a duplicate server
   * Enforces single machine-wide server policy

3. **Port Configuration**: If no server exists:
   
   * Uses explicitly configured port (default: 5049)
   * Port can be overridden via command-line argument or environment variable
   * Server fails if port is already in use

4. **Server Initialization**: Flask + Socket.IO server starts:
   
   * Listens on discovered port
   * Ready to accept workspace connections
   * Creates workspace contexts on-demand as clients connect

5. **Server Ready**: The server begins accepting API requests and client connections

Server Operations
^^^^^^^^^^^^^^^^^

Once running, the server exposes workspace-scoped APIs at ``http://host:port/workspace/{workspace_id}/...``:

* **Edit API**: Modifies the Workfile structure (add/remove nodes and edges)
* **Run API**: Initiates workflow execution with parameters:
  
  * ``nodes``: Specific nodes to include in execution
  * ``wrapper``: Command prefix/suffix wrapper

* **Status API**: Provides real-time status of nodes and edges via Socket.IO
* **Logs API**: Returns stdout/stderr from completed nodes

Each workspace operates independently with isolated state and event streams.

Server Shutdown
^^^^^^^^^^^^^^^

Servers automatically shut down when idle (no clients and no active runs):

1. All running processes are gracefully terminated
2. Node statuses are updated to reflect termination
3. Workspace contexts are destroyed
4. Resources are cleaned up (Socket.IO connections closed)
5. Server process exits cleanly

Manual shutdown via ``wf server stop`` is also supported.

Client
~~~~~~

Clients connect to workspace-scoped URLs to interact with workflows. Multiple types of clients exist:

* **GUI Client** - Tkinter-based visual editor
* **Run Client** - CLI-based workflow executor
* **Edit Client** - Programmatic workflow modifier

All clients communicate with the server via:

* HTTP API calls for workflow modifications (workspace-scoped endpoints)
* Socket.IO connections for real-time status updates (workspace-specific rooms)

Multiple clients can connect to the same workspace context simultaneously, sharing state and receiving synchronized updates.

Workspace Management
~~~~~~~~~~~~~~~~~~~~

Workforce uses a single machine-wide server that manages multiple workflows through isolated workspace contexts.

**Server Discovery**:

* PID file registry tracks running server location and process ID
* Detects existing server before attempting to start new one
* Returns server URL for client connections (default: http://127.0.0.1:5049)

**Workspace Identification**:

* Each workfile gets a deterministic workspace ID via ``compute_workspace_id()``
* Workspace ID is SHA256 hash of absolute file path
* Ensures consistent identification across multiple sessions

**Workspace Contexts**:

* Server maintains dict of ``ServerContext`` objects keyed by workspace_id
* Each context created on-demand when first client connects
* Context includes:
  
  * ``mod_queue`` - Serialized graph modification queue
  * ``EventBus`` - Domain event system for that workspace
  * Worker thread - Dedicated queue processor
  * Socket.IO room - Isolated event broadcasting
  * Active runs tracking - Per-run node sets and metadata

**Context Lifecycle**:

* Created: When first client connects to workspace
* Destroyed: When last client disconnects from workspace
* Isolation: Each workspace operates independently

This architecture allows:

* Multiple workflows to run simultaneously on one server
* Automatic workspace context creation and cleanup
* Complete isolation between different workflows
* Connection sharing across multiple GUI/CLI instances for same workflow

Execution Model
---------------

Workforce employs a unified execution model where every run is treated as a subset run.

Unified Subset Execution
~~~~~~~~~~~~~~~~~~~~~~~~~

**Philosophy**: Whether running the entire workflow or just a few nodes, the system treats all execution as subset operations. This provides consistency and prevents edge cases.

Node Selection Logic
^^^^^^^^^^^^^^^^^^^^

When a workflow run is initiated:

1. **Explicit Selection**: If specific nodes are selected (via CLI ``--nodes`` flag or GUI selection):
   
   * Those nodes form an induced subgraph for execution
   * All edges and dependencies within this subgraph are preserved

2. **Failed Node Selection**: If no nodes are explicitly selected:
   
   * The system checks for nodes in a ``failed`` state
   * All failed nodes are automatically selected for re-execution
   * This enables the "resume" functionality

3. **Full Workflow Selection**: If no nodes are selected and none have failed:
   
   * All nodes with zero in-degree in the full workflow are selected
   * This effectively runs the entire workflow from the beginning

Execution Initialization
^^^^^^^^^^^^^^^^^^^^^^^^^

Upon starting a run, the scheduler:

1. **Subgraph Extraction**: Extracts the target subset from the main workflow graph

2. **Dependency Analysis**: Identifies all nodes within the subset that have:
   
   * Zero in-degree relative only to that subset
   * (Not zero in-degree in the full graph)

3. **Initial Scheduling**: Transitions these zero-in-degree nodes to ``run`` state

4. **Boundary Enforcement**: Ensures nodes start immediately if their dependencies in the master workfile are omitted from the current run scope

Subgraph Boundary Enforcement
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To prevent execution from bleeding into the rest of the workfile:

* The scheduler strictly enforces subnetwork boundaries
* Propagation is confined entirely to the active selection
* When a node completes:
  
  * Only outgoing edges within the filtered subnetwork are evaluated
  * Edges leading to nodes outside the original subset are **ignored**
  * This effectively "caps" the execution at the subset boundary

Execution Loop
~~~~~~~~~~~~~~

The execution loop follows this pattern:

1. **Node Execution**
   
   * Node command is executed via subprocess
   * stdout and stderr are captured in real-time
   * Outputs are stored as node attributes in the graph
   * Logs are viewable from GUI (press 's')

2. **Event Emission**
   
   * Upon completion, a ``NODE_FINISHED`` event is emitted (or ``NODE_FAILED`` on error)
   * Event includes client ID for multi-client coordination
   * Server broadcasts event to all connected clients via WebSocket

3. **Scheduler Update**
   
   * Emission triggers the scheduler to retrieve the filtered subnetwork map
   * All valid outgoing edges (within the subnetwork) are updated to ``to_run`` status
   * A ``GRAPH_UPDATED`` event is broadcast

4. **Dependency Check**
   
   * Status change prompts target nodes to check dependencies
   * Node transitions to ``run`` state only if:
     
     * **ALL** incoming edges (within the subnetwork context) are marked ``to_run``
   
   * Once satisfied:
     
     * Node clears the statuses from incoming edges
     * Begins execution
     * Loop returns to step 1

This mechanism ensures the engine only advances when subset-specific dependencies are fully met.

Dependency Resolution
^^^^^^^^^^^^^^^^^^^^^

The dependency resolution system is the core of Workforce's scheduling logic. It determines which nodes are ready to execute based on their incoming :ref:`edge-type` attributes and the current status of those edges.

**Edge Types in Dependency Resolution**:

Workforce supports two edge types that affect dependency checking:

* **Blocking Edges** (:ref:`blocking-edge`) - The target node waits for ALL incoming blocking edges to be ``to_run``
* **Non-Blocking Edges** (:ref:`non-blocking-edge`) - The target node runs immediately when ANY incoming non-blocking edge becomes ``to_run``

**Resolution Algorithm**:

When an upstream node completes (status becomes ``ran``), the scheduler:

1. Marks all outgoing edges as ``to_run``
2. For each downstream node, checks its incoming edges:

   **If the incoming edge is BLOCKING**:
   
   * Check if ALL incoming blocking edges are ``to_run``
   * Only if true: Set target node status to ``run``
   * Non-blocking edges do not affect blocking edge checks
   
   **If the incoming edge is NON-BLOCKING**:
   
   * Immediately set target node status to ``run``
   * Do not wait for other incoming edges
   * Allows target to execute (or re-execute) from this single trigger

3. All propagation respects :ref:`subset-run` boundaries:

   * Only edges within the active subset are processed
   * Edges leading to nodes outside the subset are ignored
   * Ensures execution remains confined to selected scope

**Visual Representation**:

Here's how blocking and non-blocking edges interact during execution::

    Initial State:
    ┌─────┐         ┌─────┐
    │ A   │ (ran)   │ B   │ (waiting)
    └─────┘         └─────┘
      │ blocked
      │ to_run

    With all blocking edges to_run and no non-blocking incoming:
    ┌─────┐         ┌─────┐
    │ A   │ (ran)   │ B   │ (run) ──> executes once
    └─────┘         └─────┘
      │ blocked
      │ to_run

    With non-blocking edge triggering:
    ┌─────┐         ┌─────┐
    │ A   │ (ran)   │ B   │ (run) ──> re-executes
    └─────┘         └─────┘
      │ non-blocked
      │ to_run

**Mixed Dependencies Example**:

Consider a node C with one blocking edge from A and one non-blocking edge from B::

    ┌─────┐      ┌─────┐
    │ A   │      │ B   │
    └─────┘      └─────┘
      │ (blocking)  │ (non-blocking)
      └────┬────────┘
           │
         ┌─────┐
         │ C   │
         └─────┘

Execution sequence:

1. A completes: A→C marked ``to_run``, C checks dependencies
   
   * A→C is blocking and ``to_run`` ✓
   * Need to wait for B (no edges from B are ``to_run`` yet)
   * C status remains waiting

2. B completes: B→C marked ``to_run``
   
   * B→C is non-blocking, immediately set C to ``run``
   * C executes (does not wait for A→C to be ``to_run``)

3. If B runs again: B→C marked ``to_run`` again
   
   * C immediately runs again (re-triggers)
   * A→C status does not affect re-triggering

**Cycle Detection**:

Before execution begins, Workforce checks for cycles using only :ref:`blocking-edge` edges:

* Constructs a subgraph containing only blocking edges
* Checks if the subgraph is a directed acyclic graph (DAG)
* Non-blocking edges are ignored for cycle detection
* This allows workflows with non-blocking cycles (safe, no infinite loops)
* Blocking cycles cause an error before run initiation

**Subset Run Propagation**:

During dependency resolution, the system:

* Maintains an active set of nodes for the current run (the subset)
* Only propagates edges where both endpoints are in the subset
* Ignores edges leading to nodes outside the subset
* Prevents execution from "leaking" beyond the intended scope
* Enables safe subset runs and node recovery without side effects

Resume Functionality
~~~~~~~~~~~~~~~~~~~~

The resume feature (Shift+R in GUI, or re-running failed nodes) handles workflow recovery:

**How Resume Works**:

1. **Failed Node Detection**: System identifies nodes in ``failed`` state

2. **Status Reset**: Failed node status is replaced with ``run``

3. **Event Loop Trigger**: Status change re-triggers the event loop

4. **Dependency Re-check**: Scheduler re-evaluates dependencies for the failed node

5. **Queue for Execution**: If dependencies are met, node is queued for execution

6. **Pipeline Continuation**: Remainder of pipeline proceeds through normal dependency checking

**Boundary Enforcement**:

* Resume is strictly bounded by the original subset
* Resume never propagates to nodes outside the original selection
* Ensures nodes do not remain in a running state indefinitely
* Clean status management prevents zombie processes

Event System
------------

Workforce uses a publish-subscribe event system for coordinating workflow execution.

Event Types
~~~~~~~~~~~

**Node Events**:

* ``NODE_READY`` - Node is ready to execute (all dependencies met, status set to ``run``)
* ``NODE_STARTED`` - Node execution has begun (status set to ``running``)
* ``NODE_FINISHED`` - Node finished successfully (status set to ``ran``)
* ``NODE_FAILED`` - Node execution failed (status set to ``fail``)

**Workflow Events**:

* ``RUN_COMPLETE`` - All nodes in the run have completed or failed
* ``GRAPH_UPDATED`` - Graph structure or attributes were modified

Event Flow
~~~~~~~~~~

1. **Event Generation**: Server generates events during workflow execution

2. **Event Broadcasting**: Events are broadcast via WebSocket to all connected clients

3. **Client Handling**: Each client receives events and updates its local state

4. **Client ID Tagging**: Events are tagged with originating client ID to prevent conflicts

5. **State Synchronization**: All clients maintain synchronized view of workflow state

Multi-User Support
~~~~~~~~~~~~~~~~~~

The event system enables true multi-user collaboration:

* Multiple GUI clients can connect to the same workspace context simultaneously
* Changes made in one client are broadcast to all others in real-time via Socket.IO rooms
* Execution initiated by one client is visible to all connected clients
* Each workspace maintains isolated event streams preventing cross-workspace interference
* Client connections are workspace-scoped, ensuring proper event routing

Data Flow
---------

Workflow File (GraphML)
~~~~~~~~~~~~~~~~~~~~~~~

The workflow is stored as a GraphML file with:

* **Nodes**: Represent bash commands with attributes (``id``, ``label``, ``status``, ``log``, ``x``, ``y``)
  
  * ``id`` - UUID for the node
  * ``label`` - The bash command to execute
  * ``status`` - Current state: ``""`` (empty), ``run``, ``running``, ``ran``, ``fail``
  * ``log`` - Combined stdout/stderr from execution
  * ``x``, ``y`` - Position coordinates (stored as strings)

* **Edges**: Represent dependencies with attributes (``id``, ``status``)
  
  * ``id`` - UUID for the edge
  * ``status`` - Either ``""`` (empty) or ``to_run`` (source completed)

* **Graph**: Graph-level attributes
  
  * ``wrapper`` - Command template with ``{}`` placeholder (e.g., ``bash -c '{}'``)

File Loading and Saving
^^^^^^^^^^^^^^^^^^^^^^^^

* ``load_graph(path)``: Loads GraphML into NetworkX DiGraph
* ``save_graph(graph, path)``: Writes NetworkX DiGraph to GraphML using atomic temp file + os.replace
* Graph operations like ``add_node_to_graph()`` automatically save changes
* **Concurrency Safety**: All graph mutations are serialized through the server's single-threaded queue worker (one per workspace), preventing concurrent writes
* **Crash Safety**: Atomic file replacement (temp file + os.replace) ensures files are never partially written
* The singleton server architecture with queue-based serialization eliminates the need for file locking

Network Communication
~~~~~~~~~~~~~~~~~~~~~

**HTTP API**:

* RESTful endpoints for workflow modification
* JSON request/response format
* Workspace-scoped URLs: ``/workspace/{workspace_id}/...``
* Server URL discovered via ``find_running_server()``

**Socket.IO**:

* Real-time bidirectional communication
* Event broadcasting from server to clients via workspace-specific rooms
* Status updates and log streaming
* Persistent connection during workflow execution
* Room-based isolation ensures events only reach relevant clients

Process Management
------------------

Command Execution
~~~~~~~~~~~~~~~~~

* Commands run via Python's ``subprocess`` module
* Separate process for each node
* stdout/stderr captured in real-time
* Exit codes determine success/failure

Process Lifecycle
^^^^^^^^^^^^^^^^^

1. **Spawn**: Process created when node transitions to ``run`` state
2. **Monitor**: Output streams monitored via threads
3. **Complete**: Process terminates, exit code checked
4. **Cleanup**: Resources released, status updated

Parallel Execution
~~~~~~~~~~~~~~~~~~

* Multiple nodes can run simultaneously
* Limited only by available system resources
* Dependency constraints prevent invalid parallelism
* No explicit parallelism limit (user-controlled via workflow design)

Error Handling
--------------

Node Failures
~~~~~~~~~~~~~

When a node fails:

1. Node status set to ``failed``
2. Error information captured in stderr attribute
3. ``NODE_FAILED`` event broadcast to clients
4. Execution continues for independent branches
5. Failed node prevents downstream execution

Workflow Failures
~~~~~~~~~~~~~~~~~

* Failed nodes do not stop the entire workflow
* Independent branches continue executing
* Workflow completes when all executable nodes finish
* Resume functionality allows recovery from failures

Server Failures
~~~~~~~~~~~~~~~

* Server auto-discovery detects running servers via health checks
* Idle servers automatically shut down (no clients + no active runs)
* Deferred shutdown with 1-second delay prevents race conditions
* Clients detect disconnection and notify user
* Manual cleanup via ``wf server stop`` if needed

Security Considerations
-----------------------

* Commands execute with user's shell permissions
* No authentication currently implemented (local use)
* Registry file permissions control access
* WebSocket connections not encrypted (localhost)
* Command injection risks if workflow files untrusted

Performance Considerations
--------------------------

* Graph size limited by memory
* NetworkX provides efficient graph operations
* WebSocket events add minimal overhead
* Subprocess spawning has system-dependent limits
* Large stdout/stderr captured in memory (consider log rotation)
