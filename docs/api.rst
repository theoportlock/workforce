.. _api:

=============
API Reference
=============

The server is authoritative for graph state. Programmatic clients must submit
graph mutations through the server queue rather than modifying GraphML or the
in-memory graph directly. The same operations exposed in the web frontend are
available through the CLI.

Execution requests carry a run identity and operate only on their active,
run-induced subgraph. Node completion records PID, exit code, stdout, and stderr
and emits its status change for that run. Internal edges are marked ``ready`` to
drive dependency checks; edges outside the active run never propagate work.

Core module
-----------

.. automodule:: workforce
   :members:
   :undoc-members:
   :show-inheritance:

Editing
-------

.. automodule:: workforce.edit.graph
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: workforce.edit.cli
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: workforce.edit.client
   :members:
   :undoc-members:
   :show-inheritance:

Running
-------

.. automodule:: workforce.run.client
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: workforce.run.cli
   :members:
   :undoc-members:
   :show-inheritance:

Server
------

.. automodule:: workforce.server.context
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: workforce.server.queue
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: workforce.server.routes
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: workforce.server.sockets
   :members:
   :undoc-members:
   :show-inheritance:

Web bridge
----------

.. automodule:: workforce.web.bridge
   :members:
   :undoc-members:
   :show-inheritance:
