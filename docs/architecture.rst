.. _architecture:

============
Architecture
============

This page describes the internal architecture and design of Workforce.

Overview
--------

Workforce uses a client-server architecture to manage workflow execution. The system is built around a Flask API server that maintains workflow state and coordinates execution across multiple clients.

Core Components
---------------

Server
~~~~~~

The server component is the heart of Workforce's execution engine. It manages:

* **Workflow State** - Tracks node and edge status during execution
* **Event System** - Pub/sub event broadcasting for real-time updates
* **Execution Queue** - Schedules nodes based on dependency resolution
* **Client Coordination** - Handles multiple simultaneous clients
* **Registry Management** - Maps workflow files to server URLs and ports

Server Startup Process
^^^^^^^^^^^^^^^^^^^^^^

When starting a server using ``wf server start Workfile``:

1. **Registry Check**: The system checks if the Workfile (absolute path) has been assigned a URL in the shared Registry file located in the user's home directory

2. **URL Assignment**: If not already registered:
   
   * A Flask API server starts on a unique URL
   * The server can use a user-specified URL via CLI or auto-assign one
   * Port selection is automatic unless specified

3. **Registration**: The Workfile + URL mapping is stored in the Registry with:
   
   * Initial client count (set to 1)
   * Process ID (PID) for server management
   * Port number for connection
   * Timestamp for last access

4. **Server Ready**: The server begins accepting API requests for workflow editing and execution

Server Operations
^^^^^^^^^^^^^^^^^

Once running, the server exposes several APIs:

* **Edit API**: Modifies the Workfile structure (add/remove nodes and edges)
* **Run API**: Initiates workflow execution with parameters:
  
  * ``subgraph``: Specific nodes to include in execution
  * ``selected``: Explicitly chosen nodes
  * ``wrapper``: Command prefix/suffix wrapper

* **Status API**: Provides real-time status of nodes and edges via WebSocket
* **Logs API**: Returns stdout/stderr from completed nodes

Server Shutdown
^^^^^^^^^^^^^^^

On stop or failure:

1. All running processes are gracefully terminated
2. Node statuses are updated to reflect termination
3. Workfile + URL mapping is removed from Registry
4. Resources are cleaned up (WebSocket connections closed)
5. Heartbeat monitoring stops

Client
~~~~~~

Clients connect to the server to interact with workflows. Multiple types of clients exist:

* **GUI Client** - Tkinter-based visual editor
* **Run Client** - CLI-based workflow executor
* **Edit Client** - Programmatic workflow modifier

All clients communicate with the server via:

* HTTP API calls for workflow modifications
* WebSocket connections for real-time status updates

Registry System
~~~~~~~~~~~~~~~

The Registry is a central file (``$TMPDIR/workforce_servers.json``) that maintains the mapping between:

* Workflow file paths (absolute paths)
* Server URLs and ports
* Server PIDs for process management
* Client connection counts
* Last access timestamps

This allows:

* Multiple workflows to run simultaneously on different ports
* Automatic server discovery when launching clients
* Proper cleanup of orphaned servers
* Connection sharing across multiple GUI/CLI instances

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
   * Logs are viewable from GUI (press 'l')

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

The dependency resolution system works as follows:

* Each node maintains awareness of its incoming edges
* Before a node can run, it checks all incoming edges
* An edge must have ``to_run`` status for the node to proceed
* Edges outside the subset are ignored during checks
* Once all within-subset dependencies are satisfied, the node executes

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

* Multiple GUI clients can connect to the same workflow simultaneously
* Changes made in one client are broadcast to all others in real-time
* Execution initiated by one client is visible to all connected clients
* Client count is tracked in the Registry

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
* ``save_graph(graph, path)``: Writes NetworkX DiGraph to GraphML using atomic temp file
* Graph operations like ``add_node_to_graph()`` automatically save changes
* All modifications go through atomic file replacement for crash safety

Network Communication
~~~~~~~~~~~~~~~~~~~~~

**HTTP API**:

* RESTful endpoints for workflow modification
* JSON request/response format
* Authenticated with server URL from Registry

**WebSocket**:

* Real-time bidirectional communication
* Event broadcasting from server to clients
* Status updates and log streaming
* Persistent connection during workflow execution

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

* Registry tracks server PIDs
* Orphaned servers can be detected and cleaned up
* Heartbeat mechanism monitors server health
* Clients detect disconnection and notify user

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
