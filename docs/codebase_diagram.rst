Codebase Diagram
================

This Mermaid diagram summarizes the main runtime surfaces in Workforce and
how the desktop, CLI, and web clients interact with the authoritative server.

.. code-block:: text

   flowchart TD
       User[User / Operator]

       subgraph Clients[Clients and entry points]
           CLI[CLI entrypoints\nworkforce.__main__\nrun/cli.py\nedit/cli.py]
           Tk[Tk desktop GUI\ngui/core.py\ngui/app.py\ngui/canvas.py\ngui/state.py]
           WebUI[React Flow frontend\nfrontend/src/*\nbuilt into workforce/web/static]
           EditClient[Programmatic edit client\nedit/client.py]
           RunClient[Programmatic run client\nrun/client.py]
       end

       subgraph Server[Authoritative server]
           Launcher[Server launcher\nserver/__init__.py]
           Routes[REST routes\nserver/routes.py]
           Sockets[Socket.IO bridge\nserver/sockets.py]
           Context[ServerContext\nserver/context.py]
           Queue[Serialized mutation queue\nserver/queue.py]
           Events[Event bus and events\nserver/events.py]
       end

       subgraph Execution[Execution engine]
           Runner[Run orchestration\nrun/__init__.py]
           Wrapper[Wrapper application\nwrapper.replace("{}", cmd)]
           Shell[Local shell / subprocess execution]
       end

       subgraph Persistence[Workspace persistence]
           Graph[GraphML Workfile]
           Utils[Workspace + helper utilities\nutils.py]
       end

       subgraph WebSurface[Web packaging]
           Bridge[Web bridge / launcher\nweb/bridge.py\nweb/launcher.py]
           Static[Bundled static assets\nweb/static/*]
       end

       User --> CLI
       User --> Tk
       User --> WebUI

       CLI --> Launcher
       CLI --> EditClient
       CLI --> RunClient
       Tk --> EditClient
       Tk --> RunClient
       WebUI --> Bridge
       Bridge --> Routes
       Bridge --> Sockets
       Static --> WebUI

       EditClient --> Routes
       RunClient --> Routes
       Tk -. realtime .-> Sockets
       WebUI -. realtime .-> Sockets

       Launcher --> Context
       Routes --> Context
       Sockets --> Context
       Context --> Queue
       Context --> Events
       Queue --> Graph
       Context --> Runner
       Runner --> Wrapper
       Wrapper --> Shell
       Shell --> Events
       Events --> Context
       Context --> Graph
       Utils --> Launcher
       Utils --> EditClient
       Utils --> RunClient
       Bridge --> Static

Key ideas
---------

* ``server/context.py`` is the source of truth for a workspace; clients are
  projections of that state.
* All graph mutations are funneled through ``server/queue.py`` so updates are
  serialized per workspace.
* Execution is handled by the ``run`` package and feeds results back to the
  server through events instead of mutating graph state directly.
* The web frontend is shipped as prebuilt assets under ``workforce/web/static``
  and communicates with the same server APIs as the desktop and CLI clients.
