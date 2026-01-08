.. _tutorial:

========
Tutorial
========

This tutorial will guide you through creating and running your first Workforce workflow.

Getting Started
---------------

Installation
~~~~~~~~~~~~

First, install Workforce:

.. code-block:: bash

    pip install workforce

Verify the installation:

.. code-block:: bash

    wf --help

Your First Workflow
-------------------

Let's create a simple data processing pipeline that:

1. Downloads a dataset
2. Processes the data
3. Generates a report

Step 1: Launch the GUI
~~~~~~~~~~~~~~~~~~~~~~~

Start Workforce:

.. code-block:: bash

    wf

This opens the visual workflow editor.

Step 2: Create Nodes
~~~~~~~~~~~~~~~~~~~~~

**Add the first node:**

1. Double-click on the canvas (empty area)
2. A popup dialog will appear
3. Enter the bash command:
   
   ``echo "Downloading data..." && sleep 2 && echo "Data downloaded" > data.txt``

4. Click "Save" or press Enter

**Add the second node:**

1. Double-click on the canvas again
2. Enter:
   
   ``echo "Processing..." && sleep 1 && cat data.txt | wc -l > processed.txt``

3. Click "Save"

**Add the third node:**

1. Double-click on the canvas
2. Enter:
   
   ``echo "Report: $(cat processed.txt) lines processed" > report.txt``

3. Click "Save"

Step 3: Connect Nodes
~~~~~~~~~~~~~~~~~~~~~~

Create dependencies between nodes using either method:

**Method 1: Right-click and drag**

1. **Right-click** on the first node (download_data) and **hold**
2. **Drag** to the second node (process_data)
3. **Release** to create the edge

Repeat for the second dependency:

1. Right-click on process_data and drag to generate_report
2. Release to create the edge

**Method 2: Select and press 'E'**

1. Click on the first node to select it
2. Hold Shift and click the second node (multi-select)
3. Continue selecting nodes in order
4. Press **'E'** to connect them in sequence

Your workflow should now show:

.. code-block:: text

    [download_data] → [process_data] → [generate_report]

Step 4: Save the Workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~

Save your workflow:

1. Press **Ctrl+S** or use File → Exit (which saves automatically)
2. If this is a new workflow, it will be saved as ``Workfile`` in the current directory
3. Or specify a different path when starting: ``wf myworkflow.graphml``

Step 5: Run the Workflow
~~~~~~~~~~~~~~~~~~~~~~~~~

Execute the workflow:

1. Click the **"Run"** button or press **'R'**
2. Watch as nodes change color:
   
   * **Light gray** → Not started
   * **Light cyan** → Ready to run
   * **Light blue** → Currently running
   * **Light green** → Completed successfully
   * **Light coral** → Failed (if error occurs)

3. The workflow will execute in order:
   
   * First node runs first
   * Second node runs after first completes
   * Third node runs last

Step 6: View Logs
~~~~~~~~~~~~~~~~~

Check the output from any node:

1. **Left-click** a node to select it
2. Press **'S'** to view logs
3. In the log popup, press **'S'** or **Escape** to close it
4. See the combined stdout and stderr from the command execution

Verify your files were created:

.. code-block:: bash

    cat data.txt
    cat processed.txt
    cat report.txt

Working with the CLI
--------------------

The same workflow can be created and run using the command line.

Creating via CLI
~~~~~~~~~~~~~~~~

Create a new workflow file:

.. code-block:: bash

    # Start with the GUI to create graphically
    wf

    # Or create nodes via CLI (requires existing Workfile or path)
    wf edit add-node Workfile "echo 'Downloading...' && sleep 2 && echo 'Data downloaded' > data.txt" --x 100 --y 100
    wf edit add-node Workfile "echo 'Processing...' && cat data.txt | wc -l > processed.txt" --x 200 --y 100
    wf edit add-node Workfile "echo 'Report: \$(cat processed.txt) lines' > report.txt" --x 300 --y 100

Add dependencies (note: requires node UUIDs, easier via GUI):

.. code-block:: bash

    # You'll need the actual node UUIDs from the graph
    # wf edit add-edge Workfile <source-uuid> <target-uuid>
    
    # It's much easier to create edges in the GUI by dragging

Running via CLI
~~~~~~~~~~~~~~~

Execute the complete workflow:

.. code-block:: bash

    wf run Workfile

Run specific nodes only:

.. code-block:: bash

    wf run Workfile --nodes process_data,generate_report

Advanced Tutorial
-----------------

Running Subsets
~~~~~~~~~~~~~~~

Select specific nodes in the GUI:

1. **Left-click** to select a node
2. **Shift + Left-click** to add more nodes to selection
3. Press **'R'** to run only the selected nodes
4. Only selected nodes (and their dependencies within the selection) execute

Resume Failed Nodes
~~~~~~~~~~~~~~~~~~~

If a node fails:

1. Fix the issue (edit the command by double-clicking the node, or fix external resources)
2. Select the failed node(s)
3. Press **'C'** to clear the status (changes ``fail`` to ``""``)
4. Press **'R'** to run again, which will re-execute failed nodes

Using Command Wrappers
~~~~~~~~~~~~~~~~~~~~~~~

**Example: Docker Wrapper**

Run all commands in a Docker container:

.. code-block:: bash

    wf run Workfile --wrapper "docker run -v \$(pwd):/work -w /work ubuntu bash -c '{}'"

**Example: Remote Execution**

Execute workflow on a remote server:

.. code-block:: bash

    wf run Workfile --wrapper 'ssh user@remote-server "{}"'

**Example: Tmux Integration**

Send commands to tmux panes:

.. code-block:: bash

    wf run Workfile --wrapper 'tmux send-keys -t mysession "{}" C-m'

Complex Workflow Example
-------------------------

Let's create a more realistic bioinformatics pipeline.

Scenario
~~~~~~~~

Process multiple sample files through quality control, alignment, and variant calling.

Workflow Structure
~~~~~~~~~~~~~~~~~~

.. code-block:: text

    download_samples → quality_control → trim_adapters → align_to_reference
                                                              ↓
                                                        call_variants → merge_results

Creating the Workflow
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    # Note: These are simplified examples
    # In practice, create nodes in GUI or use UUIDs for edges
    
    # Create nodes with commands
    wf edit add-node Workfile "wget https://example.com/samples.tar.gz && tar -xzf samples.tar.gz"
    wf edit add-node Workfile "fastqc samples/*.fastq -o qc_reports/"
    wf edit add-node Workfile "for f in samples/*.fastq; do trim_galore \$f -o trimmed/; done"
    
    # Connect nodes in GUI or use node UUIDs with add-edge
    # Edges require source and target node IDs (UUIDs)

Running with Conda
~~~~~~~~~~~~~~~~~~

Activate a conda environment for all commands:

.. code-block:: bash

    wf run Workfile --wrapper "conda run -n biotools"

Parallel Processing
~~~~~~~~~~~~~~~~~~~

Process multiple samples in parallel using GNU Parallel:

.. code-block:: bash

    wf run Workfile --wrapper "parallel -j 4" --suffix ":::" --suffix "sample1 sample2 sample3 sample4"

Python API Tutorial
-------------------

You can also work with workflows programmatically.

Loading and Modifying Workflows
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from workforce.edit.graph import (
        load_graph,
        save_graph,
        add_node_to_graph,
        add_edge_to_graph,
        edit_node_label_in_graph
    )

    # Load an existing workflow
    G = load_graph('tutorial_workflow.graphml')

    # Add a new node - returns {'node_id': '<uuid>'}
    result = add_node_to_graph(
        'tutorial_workflow.graphml',
        label='test -f report.txt && echo "Validation passed"',
        x=400,
        y=100
    )
    new_node_id = result['node_id']
    
    # Add an edge (requires UUIDs of source and target)
    # You'd need to get the node UUID from the graph first
    # add_edge_to_graph('tutorial_workflow.graphml', source_uuid, new_node_id)

    # Modify a node's command (requires node UUID)
    # edit_node_label_in_graph(
    #     'tutorial_workflow.graphml',
    #     node_id,
    #     'curl -O https://example.com/data.csv'
    # )
    
    # Note: Each function automatically saves the graph

Programmatic Execution
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from workforce.utils import resolve_target
    
    # Resolve file path to server URL
    # This will auto-start a server if one isn't running
    server_url = resolve_target('tutorial_workflow.graphml')
    print(f"Server URL: {server_url}")
    
    # To run the workflow, use the CLI:
    # wf run tutorial_workflow.graphml
    
    # The run client connects via SocketIO and executes nodes
    # when it receives NODE_READY events from the server

Best Practices
--------------

Workflow Design
~~~~~~~~~~~~~~~

1. **Keep commands atomic**: Each node should do one thing well
2. **Use meaningful names**: Node names should describe their purpose
3. **Check dependencies**: Ensure nodes have proper input/output relationships
4. **Handle errors**: Use ``&&`` chains to fail fast: ``command1 && command2``
5. **Test incrementally**: Run subsets to verify each step works

File Management
~~~~~~~~~~~~~~~

1. **Use absolute paths** or ensure working directory is correct
2. **Create output directories** before running: ``mkdir -p output && ...``
3. **Clean up temporary files** in final nodes
4. **Use Workfile** as the default name for easy discovery

Performance
~~~~~~~~~~~

1. **Parallelize independent nodes**: Design workflows with multiple independent branches
2. **Use wrappers for resource management**: Docker, HPC schedulers, etc.
3. **Monitor resource usage**: Large parallelism may overwhelm the system
4. **Consider subset execution**: Test with small datasets first

Debugging
~~~~~~~~~

1. **Check logs frequently**: Press 'l' in GUI to view node output
2. **Test commands in isolation**: Verify each command works before adding to workflow
3. **Use echo for debugging**: Add ``echo`` statements to track progress
4. **Resume from failures**: Use Shift+R to retry failed nodes after fixes

Next Steps
----------

Now that you've completed the tutorial, you can:

* Read the :doc:`usage` guide for comprehensive CLI reference
* Explore the :doc:`architecture` to understand how Workforce works internally
* Check the :doc:`api` for programmatic workflow manipulation
* Visit the `GitHub repository <https://github.com/theoportlock/workforce>`_ for examples and issues

Happy workflow building!
