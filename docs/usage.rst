=====
Usage
=====

Workforce stores commands and their connections in a GraphML workfile. A server
hosts one or more loaded workfiles as worksessions; the web editor and CLI are
equivalent ways to operate on them. The default server URL is ``127.0.0.1:5049``
and can be changed with ``WORKFORCE_URL``. Set ``WORKFORCE_WORKSESSION`` to
choose the default workfile or worksession.

Starting and loading work
-------------------------

``workforce`` starts (or connects to) the server, loads the default
``Workfile``, and launches the web application. Use ``workforce start`` to
start the server in the background, or ``workforce start --foreground`` to run
it in the foreground. ``workforce stop`` sends a shutdown request.

Load a workfile with ``workforce load Workfile``. Other forms include
``workforce load -r workfiles.txt`` for a recursive load list,
``workforce load Workfile --autounload`` to unload when signalled by a run, and
``workforce load Workfile -name test_work`` to name a new worksession.
``workforce edit Workfile`` loads a workfile into the server, while
``workforce unload <worksession>`` removes a loaded worksession.

Inspect work with:

.. code-block:: bash

   workforce ls
   workforce ls <worksession>
   workforce ls nodes <worksession>
   workforce ls edges <worksession>
   workforce ls nodes --id filtering_of_data <worksession>
   workforce ls groups <worksession>
   workforce ls wrapper <worksession>

Running workflows
-----------------

Run a worksession with either ``workforce run <worksession>`` or the shorthand
``workforce <worksession>``. A run may select nodes, use a wrapper, or target a
group:

.. code-block:: bash

   workforce run <worksession> --nodes node1
   workforce run <worksession> --group <groupid>
   workforce run <worksession> --wrapper 'docker run image bash -c "{}"'

If a subset is supplied, Workforce runs its induced subgraph. Otherwise,
selected nodes are the starting nodes. If there is no selection, failed nodes
are selected; if none have failed, nodes with in-degree zero are started. Only
nodes and edges inside the active run subgraph participate in scheduling.

The wrapper substitutes ``{}`` with the node command. When no placeholder is
present, the wrapper is concatenated with the command.

Editing from the CLI
--------------------

All web-editor operations are available on the CLI. The principal commands are:

.. code-block:: bash

   workforce new <workfile>
   workforce save <worksession> <workfile>
   workforce node add <worksession> <cmd> -x 100 -y 200
   workforce node add <worksession> <cmd> --id filtering_of_data --after quality_check -x +100
   workforce edge add <worksession> <source> <target> --blocking
   workforce edge edit type <worksession> <edgeid> --nonblocking
   workforce group add <worksession> <nodeIDs>
   workforce wrapper edit <worksession> 'docker run image bash -c "{}"'
   workforce node edit status <worksession> <id> run
   workforce node edit command <worksession> <id> 'echo test'
   workforce node edit name <worksession> <id> new_name
   workforce node cp <worksession> <group-or-node-ids> <worksession>
   workforce ps
   workforce top <worksession> -n 2

Edges are blocking by default. Use ``--nonblocking`` when adding or editing an
edge to create a non-blocking edge.

Web editor
----------

Each worksession page is a React Flow node-and-edge editor. Double-click an
empty part of the canvas to add a node and double-click a node to edit its
command. Drag from a node's right handle to another node's left handle to add a
blocking edge. Shift-right-drag adds a non-blocking edge; an edge's type can
also be changed by double-clicking or right-clicking it.

Keyboard shortcuts include:

* ``r`` — run the selected nodes, or the default starting nodes when none are selected.
* ``d`` — delete the selected nodes.
* ``w`` — edit the command wrapper.
* ``e`` — edit the selected node.
* ``c`` — clear.
* ``o`` — find ``.wf`` paths in the selected node command and open them as workfiles.

Execution and loops
-------------------

When a node is run, Workforce captures its PID, exit code, stdout, and stderr
as node attributes. On success it changes the node status to ``ran`` and marks
its outgoing active-subgraph edges ``ready``. A target runs when all of its
incoming blocking edges are ready; the consumed ready flags are then cleared.
Non-blocking edges do not add a prerequisite, so they can trigger a target
without waiting for other non-blocking inputs.

Workflows may contain loops. A loop can deliberately re-trigger nodes,
particularly through non-blocking edges. Make the loop's stopping condition part
of the commands or graph design; Workforce does not require the workfile to be
a DAG.
