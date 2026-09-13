.. _tutorial:

========
Tutorial
========

This tutorial creates a small workflow, runs it, and shows how to use a loop.

Create and connect nodes
------------------------

Launch Workforce with a default ``Workfile``:

.. code-block:: bash

   workforce

In the worksession page, double-click empty canvas space and add these commands
as nodes:

.. code-block:: bash

   echo download > data.txt
   tr a-z A-Z < data.txt > result.txt
   cat result.txt

Drag from the right handle of the first node to the left handle of the second,
then from the second to the third. These are blocking edges by default, so the
nodes run in order. Double-click a node later to change its command.

Press ``r`` with no selection to start the root node. Press ``r`` with nodes
selected to use those nodes as the run start. The node statuses progress from
empty to ``run``, ``running``, and ``ran``; stdout, stderr, PID, and exit code
are retained on each executed node.

Run from the CLI
----------------

The same work can be inspected and run from the CLI:

.. code-block:: bash

   workforce ls Workfile
   workforce run Workfile
   workforce run Workfile --nodes <node-id>
   workforce run Workfile --wrapper 'docker run image bash -c "{}"'

Use ``workforce node add`` and ``workforce edge add`` to create the same graph
without the web editor. ``workforce ls nodes Workfile`` lists node IDs to use
with the edit and run commands.

Create a loop
-------------

Workforce graphs can contain loops. For example, add a node that increments a
counter and connect a non-blocking edge back to a prior node using
Shift-right-drag. A non-blocking loop can re-trigger that node after each
completion. Include a stopping condition in the command (for example, test a
counter and exit without emitting another useful trigger) so the workflow has a
finite result.

Blocking edges still express prerequisites: a target waits for all incoming
blocking edges to be ready. Non-blocking edges do not add another prerequisite,
which is what makes them useful for event-like triggers and loops.

Run a subset safely
-------------------

``workforce run Workfile --nodes node1`` executes only the induced subgraph of
the specified selection. Readiness and status changes cannot cross that run
boundary, so testing or re-running part of a workflow cannot start unrelated
nodes.
