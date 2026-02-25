# Workforce Browser Workflow Editor Plan (React Flow)

This plan defines a browser-based node–edge workflow editor for Workforce that mirrors the existing Tkinter workflow UX while keeping backend execution semantics compatible with current GraphML logic.

## Scope Update

- **No pywebview for now**.
- **No node-level prefix/suffix fields**.
- **Wrapper remains the only command wrapping mechanism** (graph-level setting, as used today).

## Goals

- Use **React Flow** for graph interaction.
- Keep desktop-like layout and interaction model (canvas + property panel + log panel + context menu).
- Preserve existing Python execution and GraphML storage behavior.
- Ship via `pip` with prebuilt frontend static assets served by Workforce backend.

## UX/Feature Requirements

- Drag-and-drop node positioning
- Click-and-drag edge creation
- Zoom and pan
- Node selection and multi-select
- Right-click context menus (canvas + node + edge)
- Editable node properties:
  - `command` (mapped to GraphML node `label`)
- Visual execution state indicators:
  - queued (`run`)
  - running (`running`)
  - complete (`ran`)
  - failed (`fail`)
- Log/output panel for selected node
- Save/load workflow files

## Architecture

### Frontend (React)

Responsible for:
- React Flow graph state (rendering, drag, selection, edge creation)
- Local UI state (active node, panel visibility, context menus)
- Calling backend API for persistence and run control
- Subscribing to realtime server events (Socket.IO)

### Backend (Python)

Responsible for:
- GraphML load/save and mutation endpoints
- DAG scheduling/execution and multiprocessing
- Status transitions and event emission
- Node execution log persistence and retrieval

## Browser Deployment Model

- Build React app during development/CI.
- Copy compiled assets into package path (for example `workforce/web_static/`).
- Workforce Flask server serves static bundle at `/` (or `/web`).
- End users install via `pip`; no Node.js runtime needed.

## Proposed Folder Structure

```text
workforce/
  web/
    __init__.py
    routes.py              # Flask routes to serve SPA + optional API helpers
    static/
      index.html
      assets/...
  server/
    routes.py              # existing workflow APIs
    sockets.py             # existing Socket.IO event transport
frontend/                  # dev-only
  package.json
  src/
    App.tsx
    components/
      WorkflowCanvas.tsx
      NodeInspector.tsx
      LogPanel.tsx
      ContextMenu.tsx
    api/
      client.ts
      events.ts
    model/
      graph.ts
      schema.ts
tests/
  web/
    test_web_static_serving.py
    test_web_schema_mapping.py
    test_web_event_protocol.py
```

## Minimal React Flow Scaffold (MVP)

MVP component behavior:

- `WorkflowCanvas`
  - loads initial graph via `GET /workspace/<id>/get-graph`
  - maps backend node-link graph to React Flow `nodes`/`edges`
  - pushes position updates via `POST /edit-node-positions`
  - creates edges via `POST /add-edge`
  - supports selection + multiselect

- `NodeInspector`
  - edits node command only
  - persists via `POST /edit-node-label`

- `LogPanel`
  - loads selected-node log via `GET /get-node-log/<node_id>`

- Context menu
  - add node (`POST /add-node`)
  - delete node (`POST /remove-node`)
  - delete edge (`POST /remove-edge`)

## JSON Schema (maps cleanly to GraphML)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://workforce.dev/schema/workflow.json",
  "title": "Workforce Workflow",
  "type": "object",
  "required": ["version", "graph", "nodes", "edges"],
  "properties": {
    "version": { "type": "string" },
    "graph": {
      "type": "object",
      "required": ["wrapper"],
      "properties": {
        "wrapper": { "type": "string" }
      },
      "additionalProperties": true
    },
    "nodes": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "command", "x", "y", "status"],
        "properties": {
          "id": { "type": "string" },
          "command": { "type": "string" },
          "x": { "type": "number" },
          "y": { "type": "number" },
          "status": {
            "type": "string",
            "enum": ["", "run", "running", "ran", "fail"]
          },
          "stdout": { "type": "string" },
          "stderr": { "type": "string" },
          "pid": { "type": ["string", "number"] },
          "error_code": { "type": ["string", "number", "null"] }
        },
        "additionalProperties": true
      }
    },
    "edges": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "source", "target", "edge_type", "status"],
        "properties": {
          "id": { "type": "string" },
          "source": { "type": "string" },
          "target": { "type": "string" },
          "edge_type": { "type": "string", "enum": ["blocking", "non-blocking"] },
          "status": { "type": "string" }
        },
        "additionalProperties": true
      }
    }
  },
  "additionalProperties": false
}
```

### GraphML Mapping

- `node.command` ↔ GraphML node `label`
- `node.x`, `node.y`, `node.status` ↔ existing node attrs
- `edge.edge_type`, `edge.status`, `edge.id` ↔ existing edge attrs
- `graph.wrapper` ↔ GraphML graph attr `wrapper`

## Frontend ↔ Backend Event Protocol

### Command/Query channel (HTTP)

Use existing workspace endpoints:
- `GET /workspace/<id>/get-graph`
- `POST /workspace/<id>/add-node`
- `POST /workspace/<id>/remove-node`
- `POST /workspace/<id>/add-edge`
- `POST /workspace/<id>/remove-edge`
- `POST /workspace/<id>/edit-node-label`
- `POST /workspace/<id>/edit-node-positions`
- `POST /workspace/<id>/edit-wrapper`
- `GET /workspace/<id>/get-node-log/<node_id>`
- `POST /workspace/<id>/run`

### Realtime channel (Socket.IO)

Frontend subscribes to workspace room (`ws:<workspace_id>`) and handles:
- `graph_update`
- `status_change`
- `run_complete`

### Suggested frontend event envelope

```json
{
  "type": "graph_update | status_change | run_complete",
  "workspace_id": "ws_...",
  "run_id": "optional",
  "payload": {}
}
```

## Pip Distribution Notes

- Keep Node.js as development-only toolchain.
- Include prebuilt assets in sdist/wheel.
- Runtime dependencies remain Python-only.

## Pytest Coverage Plan

- `test_web_static_serving.py`
  - verifies SPA index and assets are served.
- `test_web_schema_mapping.py`
  - verifies JSON ↔ GraphML round-trip for wrapper/nodes/edges.
- `test_web_event_protocol.py`
  - verifies event names and payload expectations from Socket.IO bridge layer.

