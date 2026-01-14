=====
Usage
=====

Workforce provides several ways to create and run workflows. You can use the GUI for visual editing, or the CLI for programmatic control.

Command Line Interface
----------------------

Launching the GUI
~~~~~~~~~~~~~~~~~

To launch the Workforce GUI:

.. code-block:: bash

    wf

or:

.. code-block:: bash

    python -m workforce

To open a specific workflow file:

.. code-block:: bash

    wf path/to/workflow.graphml

If a ``Workfile`` exists in the current directory, it will be opened automatically:

.. code-block:: bash

    wf

Running Workflows
~~~~~~~~~~~~~~~~~

Execute a complete workflow:

.. code-block:: bash

    wf run Workfile

Execute specific nodes only:

.. code-block:: bash

    wf run Workfile --nodes node1,node2,node3

Use command wrappers (prefix/suffix):

.. code-block:: bash

    wf run Workfile --wrapper "docker run -it ubuntu"

Server Management
~~~~~~~~~~~~~~~~~

Start a server for a workflow:

.. code-block:: bash

    wf server start Workfile

Stop a server:

.. code-block:: bash

    wf server stop Workfile

List all running servers:

.. code-block:: bash

    wf server list

Editing Workflows via CLI
~~~~~~~~~~~~~~~~~~~~~~~~~~

Add a node to a workflow:

.. code-block:: bash

    wf edit add-node Workfile "node_name" "command to run"

Remove a node:

.. code-block:: bash

    wf edit remove-node Workfile "node_name"

Add an edge (dependency):

.. code-block:: bash

    wf edit add-edge Workfile "source_node" "target_node"

Remove an edge:

.. code-block:: bash

    wf edit remove-edge Workfile "source_node" "target_node"

Edit node command:

.. code-block:: bash

    wf edit edit-node Workfile "node_name" "new command"

Edit node position (for GUI layout):

.. code-block:: bash

    wf edit edit-node-position Workfile "node_name" x y

GUI Usage
---------

The Workforce GUI provides an interactive visual editor for workflows.

Keyboard Shortcuts
~~~~~~~~~~~~~~~~~~

* **Q** - Save and exit
* **R** - Run the workflow (or run selected nodes)
* **D** / **Delete** / **Backspace** - Delete selected node(s)
* **E** - Connect selected nodes in sequence (creates edges)
* **Shift+E** - Clear edges from selected nodes
* **C** - Clear status of selected nodes
* **Shift+C** - Clear all statuses in workflow
* **S** - View logs for selected node
* **P** - Edit command wrapper
* **O** - Load/open Workfile
* **Ctrl+S** - Save workflow
* **Ctrl+Up** / **Ctrl+Down** - Zoom in/out
* **Double-Click Canvas** - Add new node at cursor position
* **Double-Click Node** - Edit node command
* **Right-Click + Drag** - Create edge from source to target node
* **Middle-Click Node** - Select node
* **Left-Click + Drag Node** - Move node(s)
* **Shift + Left-Click + Drag Canvas** - Rectangle selection

Edge Types
~~~~~~~~~~

Workforce supports two types of edges that define how nodes depend on each other. See the :ref:`glossary` for detailed definitions.

**Blocking Edges** (:ref:`blocking-edge`)

Blocking edges are the default edge type and enforce strict dependencies. When a node has blocking edges as inputs, it only transitions to ``run`` state after **all** incoming blocking edges are ready. This enforces sequential execution.

To create a blocking edge (default behavior):

1. Right-click on a source node
2. Drag to the target node
3. Release to create the edge
4. The edge will appear as a solid line

Via CLI:

.. code-block:: bash

    wf edit add-edge Workfile "source_node" "target_node"

This creates a blocking edge by default.

Via REST API (blocking edge):

.. code-block:: bash

    curl -X POST http://localhost:5000/workspace/workspace_id/add-edge \
      -H "Content-Type: application/json" \
      -d '{"source_id": "node-uuid-1", "target_id": "node-uuid-2", "edge_type": "blocking"}'

Via Python client:

.. code-block:: python

    from workforce.gui.client import ServerClient
    
    client = ServerClient(server_url)
    client.add_edge(source_id="node-uuid-1", target_id="node-uuid-2", edge_type="blocking")

**Non-Blocking Edges** (:ref:`non-blocking-edge`)

Non-blocking edges are soft triggers that allow immediate execution without waiting for other dependencies. When a non-blocking edge becomes ready, the target node immediately transitions to ``run`` state, allowing for flexible triggering and re-execution patterns.

To create a non-blocking edge:

1. Hold **Ctrl+Shift**
2. Right-click and drag from source node to target node
3. Release to create the non-blocking edge
4. The edge will appear as a dashed line

Via CLI:

.. code-block:: bash

    wf edit add-edge Workfile "source_node" "target_node" --edge_type non-blocking

Via REST API (non-blocking edge):

.. code-block:: bash

    curl -X POST http://localhost:5000/workspace/workspace_id/add-edge \
      -H "Content-Type: application/json" \
      -d '{"source_id": "node-uuid-1", "target_id": "node-uuid-2", "edge_type": "non-blocking"}'

Via Python client:

.. code-block:: python

    from workforce.gui.client import ServerClient
    
    client = ServerClient(server_url)
    client.add_edge(source_id="node-uuid-1", target_id="node-uuid-2", edge_type="non-blocking")

**Updating Edge Types**

Change an existing edge type:

Via CLI:

.. code-block:: bash

    wf edit edit-edge-type Workfile "source_node" "target_node" "non-blocking"

Via REST API:

.. code-block:: bash

    curl -X POST http://localhost:5000/workspace/workspace_id/edit-edge-type \
      -H "Content-Type: application/json" \
      -d '{"source_id": "node-uuid-1", "target_id": "node-uuid-2", "edge_type": "non-blocking"}'

**Use Cases**

**Blocking Edges** are appropriate for:

* Sequential pipelines where each step must complete before the next starts
* Workflows that conform to directed acyclic graph (DAG) structure
* Ensuring all prerequisites are satisfied before proceeding
* Traditional data processing pipelines (extract → transform → load)

**Non-Blocking Edges** are appropriate for:

* Fan-out patterns where a single node triggers multiple independent branches
* Workflows requiring node re-execution (e.g., error recovery, data reprocessing)
* Event-driven execution where triggers are more important than strict ordering
* Flexible workflows that don't conform to strict DAG structure
* Monitoring or signal nodes that notify multiple consumers

**Mixed Edge Workflows**

Workflows can combine both edge types for sophisticated execution patterns. For example:

* A node with both blocking edges (ensuring prerequisites) and non-blocking edges (allowing immediate re-execution on external triggers)
* Multiple independent branches triggered by a single source (blocking to first node, then non-blocking to branch starts)
* See :ref:`dependency-resolution` in the architecture documentation for detailed execution semantics

Creating Workflows
~~~~~~~~~~~~~~~~~~

1. Launch the GUI with ``wf``
2. Double-click on the canvas to add a new node
3. Enter the bash command in the popup dialog
4. To create dependencies:
   
   * Right-click and drag from source node to target node, OR
   * Select multiple nodes and press 'E' to connect them in sequence

5. Save the workflow (press Ctrl+S or use File menu)

Running Workflows
~~~~~~~~~~~~~~~~~

From the GUI:

1. Click the 'Run' button or press 'R'
2. If nodes are selected, only those nodes (and their dependencies) will run
3. Otherwise, the entire workflow executes
4. Node colors indicate status:
   
   * Light gray - Not started (empty status)
   * Light cyan - Ready to run (status: ``run``)
   * Light blue - Currently running (status: ``running``)
   * Light green - Completed successfully (status: ``ran``)
   * Light coral/red - Failed (status: ``fail``)

Viewing Logs
~~~~~~~~~~~~

To view output from a node:

1. Select the node (left-click)
2. Press 'S' to open the log viewer
3. In the log popup, press 'S' or Escape to close it
4. View combined stdout/stderr from the command execution

Workflow File Format
--------------------

Workforce uses GraphML format to store workflows. Each node represents a bash command, and edges represent dependencies.

Example GraphML Structure
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: xml

    <?xml version="1.0" encoding="UTF-8"?>
    <graphml xmlns="http://graphml.graphdrawing.org/xmlns">
      <key id="label" for="node" attr.name="label" attr.type="string"/>
      <key id="status" for="node" attr.name="status" attr.type="string"/>
      <key id="log" for="node" attr.name="log" attr.type="string"/>
      <key id="x" for="node" attr.name="x" attr.type="string"/>
      <key id="y" for="node" attr.name="y" attr.type="string"/>
      <key id="wrapper" for="graph" attr.name="wrapper" attr.type="string"/>
      <graph id="G" edgedefault="directed">
        <node id="abc-123-uuid">
          <data key="label">wget https://example.com/data.csv</data>
          <data key="status"></data>
          <data key="x">100</data>
          <data key="y">100</data>
        </node>
        <node id="def-456-uuid">
          <data key="label">python process.py data.csv</data>
          <data key="status"></data>
          <data key="x">300</data>
          <data key="y">100</data>
        </node>
        <edge id="edge-789-uuid" source="abc-123-uuid" target="def-456-uuid">
          <data key="status"></data>
        </edge>
      </graph>
    </graphml>

Node Attributes
~~~~~~~~~~~~~~~

* **id** - Unique identifier (UUID)
* **label** - The bash command to execute
* **status** - Current execution status ("", run, running, ran, fail)
* **log** - Combined stdout/stderr from command execution
* **x, y** - Node position in GUI canvas (stored as strings)

Edge Attributes
~~~~~~~~~~~~~~~

* **id** - Unique identifier (UUID)
* **status** - Edge status used for dependency tracking ("", to_run)

Command Wrappers
----------------

Workforce allows you to wrap commands with a template that includes a ``{}`` placeholder. This is useful for running commands in different environments.

The wrapper is a command template where ``{}`` is replaced with the actual node command.

Wrapper Examples
~~~~~~~~~~~~~~~~

**tmux Integration**

Send commands to tmux sessions:

.. code-block:: bash

    wf run Workfile --wrapper 'tmux send-keys -t mysession "{}" C-m'

**Remote Execution via SSH**

Execute commands on a remote server:

.. code-block:: bash

    wf run Workfile --wrapper 'ssh user@remote-server "{}"'

**Docker Containers**

Run commands inside Docker containers:

.. code-block:: bash

    wf run Workfile --wrapper 'docker run -it ubuntu bash -c "{}"'

**Conda Environments**

Activate a conda environment before running:

.. code-block:: bash

    wf run Workfile --wrapper 'conda run -n myenv bash -c "{}"'

**Slurm Job Submission**

Submit each command as a Slurm job:

.. code-block:: bash

    wf run Workfile --wrapper 'sbatch --wrap="{}"'

**Export to Bash Script**

Generate a bash script without executing:

.. code-block:: bash

    wf run Workfile --wrapper 'echo "{}" >> commands.sh'

**Adding Sleep/Delay**

Add delay before each command:

.. code-block:: bash

    wf run Workfile --wrapper 'bash -c "sleep 1; {}"'

Python API
----------

You can also use Workforce programmatically:

.. code-block:: python

    import workforce
    from workforce.edit.graph import load_graph, add_node_to_graph, save_graph
    
    # Load an existing workflow
    G = load_graph('workflow.graphml')
    
    # Add a new node (returns dict with node_id)
    result = add_node_to_graph('workflow.graphml', 'echo "Hello World"', x=100, y=200)
    print(f"Created node: {result['node_id']}")
    
    # Note: Most graph operations save automatically
    # Individual functions like add_node_to_graph() handle save internally

For running workflows programmatically, connect to the server:

.. code-block:: python

    from workforce import utils
    
    # Compute workspace ID from file path
    workspace_id = utils.compute_workspace_id('workflow.graphml')
    
    # Get workspace URL (auto-discovers or starts server)
    workspace_url = utils.get_workspace_url(workspace_id)
    
    # Runner client connects to workspace URL and waits for node_ready events
    # This is typically done by the run command, not manually

Remote GUI over LAN
-------------------

You can run the GUI from a different machine and connect to a remote server.

- Start the server with LAN binding on the host machine:

.. code-block:: bash

    wf server stop
    wf server start --host 0.0.0.0

- List access URLs and share the workspace URL:

.. code-block:: bash

    wf server ls

This shows both Local and LAN URLs. Use the LAN URL format:

.. code-block:: text

    http://<server_ip>:<port>/workspace/<workspace_id>

- From the remote machine, launch the GUI directly to that URL:

.. code-block:: bash

    wf gui http://<server_ip>:<port>/workspace/<workspace_id>

Notes:

- Do not use any 127.* addresses across machines; those are loopback only.
- macOS: Allow the Python process through the firewall when prompted.
- Termux/Android: Ensure the app has network permissions and the device is on the same subnet.

WSL (Windows Subsystem for Linux)
---------------------------------

WSL2 uses NAT and assigns a private IP to the Linux VM. Services bound inside WSL are reachable from the Windows host, but not automatically from other LAN machines.

Options to access the Workforce server from other machines:

1) Run the server on Windows (outside WSL)

.. code-block:: bash

    # In Windows Python environment
    wf server start --host 0.0.0.0

Then use the Windows host LAN IP in the URL.

2) Port forward from Windows host to WSL

- Find the current WSL IP (inside WSL):

.. code-block:: bash

    ip addr | grep 'inet '

- Add a Windows port proxy to forward port 5000 to WSL (run in an elevated PowerShell or cmd):

.. code-block:: text

    netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=5000 connectaddress=<WSL_IP> connectport=5000

- Open firewall for inbound TCP 5000:

.. code-block:: text

    netsh advfirewall firewall add rule name="Workforce 5000" dir=in action=allow protocol=TCP localport=5000

- Verify:

.. code-block:: text

    netsh interface portproxy show all

- Use the Windows host LAN IP in the GUI URL:

.. code-block:: bash

    wf gui http://<windows_host_ip>:5000/workspace/<workspace_id>

Note: WSL IP can change after restart. Recreate the portproxy if needed.

Security
--------

For LAN use, Workforce enables CORS for Socket.IO in development. If exposing beyond LAN, use a reverse proxy (e.g., Nginx) with TLS and restrict allowed origins.
