.. _api:

=============
API Reference
=============

This section provides detailed API documentation for all Workforce modules.

REST API Overview
-----------------

Workforce exposes a Flask-based REST API for workflow management and execution. All endpoints are scoped to a specific workspace using the workspace ID (deterministic SHA256 hash of the workflow file path).

Edge Type Parameters
~~~~~~~~~~~~~~~~~~~~

Many REST endpoints accept an ``edge_type`` parameter to specify the type of edge:

* **blocking** (default) - :ref:`Blocking edge <blocking-edge>` that enforces strict dependencies
* **non-blocking** - :ref:`Non-blocking edge <non-blocking-edge>` that acts as a soft trigger

**Adding Edges with Type Specification**

To add a blocking edge (default):

.. code-block:: bash

    curl -X POST http://localhost:5000/workspace/abc123def456/add-edge \
      -H "Content-Type: application/json" \
      -d '{
        "source_id": "node-uuid-1",
        "target_id": "node-uuid-2",
        "edge_type": "blocking"
      }'

To add a non-blocking edge:

.. code-block:: bash

    curl -X POST http://localhost:5000/workspace/abc123def456/add-edge \
      -H "Content-Type: application/json" \
      -d '{
        "source_id": "node-uuid-1",
        "target_id": "node-uuid-2",
        "edge_type": "non-blocking"
      }'

Python client example (blocking edge):

.. code-block:: python

    import requests
    
    response = requests.post(
        "http://localhost:5000/workspace/abc123def456/add-edge",
        json={
            "source_id": "node-uuid-1",
            "target_id": "node-uuid-2",
            "edge_type": "blocking"
        }
    )
    print(response.json())

Python client example (non-blocking edge):

.. code-block:: python

    import requests
    
    response = requests.post(
        "http://localhost:5000/workspace/abc123def456/add-edge",
        json={
            "source_id": "node-uuid-1",
            "target_id": "node-uuid-2",
            "edge_type": "non-blocking"
        }
    )
    print(response.json())

**Updating Edge Types**

To change an existing edge's type from blocking to non-blocking:

.. code-block:: bash

    curl -X POST http://localhost:5000/workspace/abc123def456/edit-edge-type \
      -H "Content-Type: application/json" \
      -d '{
        "source_id": "node-uuid-1",
        "target_id": "node-uuid-2",
        "edge_type": "non-blocking"
      }'

Python client example:

.. code-block:: python

    import requests
    
    response = requests.post(
        "http://localhost:5000/workspace/abc123def456/edit-edge-type",
        json={
            "source_id": "node-uuid-1",
            "target_id": "node-uuid-2",
            "edge_type": "non-blocking"
        }
    )
    print(response.json())

**Graph Queries**

When retrieving the workflow graph, the ``edge_type`` attribute is included in edge data:

.. code-block:: bash

    curl http://localhost:5000/workspace/abc123def456/get-graph

Response includes edges with type information:

.. code-block:: json

    {
      "nodes": [
        {"id": "node-1", "label": "wget data.csv", "status": ""},
        {"id": "node-2", "label": "python process.py", "status": ""}
      ],
      "edges": [
        {
          "id": "edge-1",
          "source": "node-1",
          "target": "node-2",
          "edge_type": "blocking",
          "status": ""
        }
      ]
    }

See :ref:`glossary` for detailed definitions of edge type semantics and :ref:`dependency-resolution` in the architecture documentation for execution behavior.

Core Module
-----------

.. automodule:: workforce
   :members:
   :undoc-members:
   :show-inheritance:

Utils
~~~~~

.. automodule:: workforce.utils
   :members:
   :undoc-members:
   :show-inheritance:

Edit Module
-----------

The edit module provides functions for manipulating workflow graphs.

Graph Functions
~~~~~~~~~~~~~~~

.. automodule:: workforce.edit.graph
   :members:
   :undoc-members:
   :show-inheritance:

Edit CLI
~~~~~~~~

.. automodule:: workforce.edit.cli
   :members:
   :undoc-members:
   :show-inheritance:

Edit Client
~~~~~~~~~~~

.. automodule:: workforce.edit.client
   :members:
   :undoc-members:
   :show-inheritance:

Run Module
----------

The run module handles workflow execution.

Run Client
~~~~~~~~~~

.. automodule:: workforce.run.client
   :members:
   :undoc-members:
   :show-inheritance:

Run CLI
~~~~~~~

.. automodule:: workforce.run.cli
   :members:
   :undoc-members:
   :show-inheritance:

Server Module
-------------

The server module manages the Flask API and workflow execution engine.

Server Context
~~~~~~~~~~~~~~

.. automodule:: workforce.server.context
   :members:
   :undoc-members:
   :show-inheritance:

Events System
~~~~~~~~~~~~~

.. automodule:: workforce.server.events
   :members:
   :undoc-members:
   :show-inheritance:

Queue Management
~~~~~~~~~~~~~~~~

.. automodule:: workforce.server.queue
   :members:
   :undoc-members:
   :show-inheritance:

API Routes
~~~~~~~~~~

.. automodule:: workforce.server.routes
   :members:
   :undoc-members:
   :show-inheritance:

WebSocket Handlers
~~~~~~~~~~~~~~~~~~

.. automodule:: workforce.server.sockets
   :members:
   :undoc-members:
   :show-inheritance:

GUI Module
----------

The GUI module provides the Tkinter-based visual workflow editor.

Main Application
~~~~~~~~~~~~~~~~

.. automodule:: workforce.gui.app
   :members:
   :undoc-members:
   :show-inheritance:

Canvas
~~~~~~

.. automodule:: workforce.gui.canvas
   :members:
   :undoc-members:
   :show-inheritance:

GUI Client
~~~~~~~~~~

.. automodule:: workforce.gui.client
   :members:
   :undoc-members:
   :show-inheritance:

Core GUI
~~~~~~~~

.. automodule:: workforce.gui.core
   :members:
   :undoc-members:
   :show-inheritance:

State Management
~~~~~~~~~~~~~~~~

.. automodule:: workforce.gui.state
   :members:
   :undoc-members:
   :show-inheritance:
