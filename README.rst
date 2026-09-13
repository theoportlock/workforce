=========
workforce
=========

.. image:: https://img.shields.io/pypi/v/workforce.svg
   :target: https://pypi.python.org/pypi/workforce

.. image:: https://readthedocs.org/projects/workforce/badge/?version=latest
   :target: https://workforce.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status

Workforce creates and runs shell commands in the order of a directed GraphML
graph. It supports multiuser editing and running through a Flask + Socket.IO
server, a React Flow web frontend, and an equivalent CLI. Like Galaxy, QIIME
plugin workflows, AnADAMA2, Snakemake, Nextflow, and Make, it represents work
as connected commands; unlike a DAG-only workflow engine, Workforce also
supports loops.

.. image:: images/small.png
   :alt: Small pipeline example
   :align: center
   :width: 800px

* Free software: MIT license
* Documentation: https://workforce-documentation.readthedocs.io

Quick start
-----------

Install Workforce and launch the default ``Workfile``:

.. code-block:: bash

   pip install workforce
   workforce

``workforce`` starts (or connects to) the server at ``127.0.0.1:5049``, loads
the default workfile, and launches the web app. Use ``workforce start`` to run
the server in the background, ``workforce start --foreground`` to run it in the
foreground, and ``workforce stop`` to request shutdown.

Use ``workforce edit <workfile>`` to load a workfile into the server and
``workforce load <workfile>`` to add one to the server as a worksession. Set
``WORKFORCE_URL`` or ``WORKFORCE_WORKSESSION`` to override the default URL or
worksession.

Running a graph
---------------

Run a worksession from the web frontend by selecting its starting nodes (or no
nodes for the default selection) and pressing ``r``. Run the same worksession
from the CLI with:

.. code-block:: bash

   workforce run <worksession>
   workforce run <worksession> --nodes node1
   workforce run <worksession> --group <groupid>
   workforce run <worksession> --wrapper 'docker run image bash -c "{}"'

A selected subset runs as an induced subgraph. Without a subset, selected nodes
are start nodes; without a selection, failed nodes are selected; if none have
failed, Workforce starts nodes with in-degree zero. Execution and readiness are
strictly confined to the active run subgraph.

On success, a node records its PID, exit code, stdout, and stderr, changes to
``ran``, and marks its outgoing edges ``ready``. A target runs after all of its
incoming blocking edges are ready. Non-blocking edges do not add another
prerequisite and can re-trigger work, including in loops. Workforce supports
loops; design loop commands and edges with an intended stopping condition.

Editing
-------

In the web editor, double-click empty canvas to add a node and double-click a
node to edit it. Drag from a right handle to a left handle to create a blocking
edge. Shift-right-drag creates a non-blocking edge. Press ``r`` to run, ``d``
to delete selected nodes, ``w`` to edit the wrapper, ``e`` to edit a node,
``c`` to clear, and ``o`` to open a ``.wf`` workfile named in a selected
command.

The CLI exposes the same operations, including ``workforce node add``,
``workforce edge add``, ``workforce group add``, ``workforce wrapper edit``,
``workforce save``, ``workforce ls``, ``workforce ps``, and ``workforce top``.

.. image:: images/complex.png
   :alt: Complex pipeline editor view
   :align: center
   :width: 800px

Architecture
------------

The server is authoritative. Every graph mutation goes through
``ServerContext.enqueue()`` and the serialized queue in ``server/queue.py``;
clients are projections of that state. Node statuses use the state machine
``""`` → ``run`` → ``running`` → ``ran``, with ``running`` → ``fail`` and
``fail`` → ``run`` as the failure and retry transitions. A wrapper is applied
deterministically with ``wrapper.replace("{}", cmd)`` or, without a placeholder,
by concatenation.
