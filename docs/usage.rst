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
* **L** - View logs for selected node
* **P** - Edit command wrapper
* **O** - Load/open Workfile
* **Ctrl+S** - Save workflow
* **Ctrl+Up** / **Ctrl+Down** - Zoom in/out
* **Double-Click Canvas** - Add new node at cursor position
* **Double-Click Node** - Edit node command
* **Right-Click + Drag** - Create edge from source to target node
* **Middle-Click Node** - Select node
* **Double Middle-Click Node** - View node log
* **Left-Click + Drag Node** - Move node(s)
* **Shift + Left-Click + Drag Canvas** - Rectangle selection

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
2. Press 'L' to open the log viewer, OR
3. Double middle-click (double Button-2) on the node
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

For running workflows programmatically, connect to the server via SocketIO:

.. code-block:: python

    from workforce.run.client import WorkforceClient
    from workforce.utils import resolve_target
    
    # Resolve file path to server URL (auto-starts if needed)
    server_url = resolve_target('workflow.graphml')
    
    # Runner client connects and waits for node_ready events
    # This is typically done by the run command, not manually
