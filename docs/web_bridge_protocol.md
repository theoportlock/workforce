# Web Bridge Protocol

This document defines the request/response/event envelopes and bridge methods used by the web frontend bridge.

## Protocol versioning

- Current protocol version: `1.0`
- Backward compatibility behavior:
  - Requests without `protocolVersion` are treated as legacy v1 and accepted.
  - Requests with `protocolVersion` set must match an explicitly supported version (`"1"` or `"1.0"`).

## Request envelope

```json
{
  "id": "string-or-number",
  "method": "string",
  "params": {},
  "protocolVersion": "1.0"
}
```

Fields:

- `id`: request correlation ID, echoed in responses.
- `method`: bridge method name.
- `params`: method arguments.
- `protocolVersion`: protocol version for explicit compatibility checks.

## Response envelope

```json
{
  "id": "string-or-number",
  "ok": true,
  "result": {}
}
```

or

```json
{
  "id": "string-or-number",
  "ok": false,
  "error": {
    "type": "ErrorType",
    "message": "Human readable error"
  }
}
```

Fields:

- `id`: same as request ID.
- `ok`: `true` for success, `false` for failures.
- `result`: method result when `ok=true`.
- `error`: error details when `ok=false`.

## Event envelope (pushed to frontend)

```json
{
  "event": "string",
  "payload": {},
  "workspaceId": "ws_xxxxxxxx",
  "ts": 1735689600.123
}
```

Fields:

- `event`: event name.
- `payload`: event data.
- `workspaceId`: workspace identifier.
- `ts`: event timestamp (Unix seconds).

## Supported bridge methods

The bridge maps methods to existing workspace HTTP endpoints.

- `getGraph` → `GET /workspace/<id>/get-graph`
- `addNode` → `POST /workspace/<id>/add-node`
- `removeNode` → `POST /workspace/<id>/remove-node`
- `addEdge` → `POST /workspace/<id>/add-edge`
- `removeEdge` → `POST /workspace/<id>/remove-edge`
- `updateNodePosition` → `POST /workspace/<id>/edit-node-position`
- `updateNodePositions` → `POST /workspace/<id>/edit-node-positions`
- `updateNodeLabel` → `POST /workspace/<id>/edit-node-label`
- `updateNodeCommand` → `POST /workspace/<id>/edit-node-label` (`command` mapped to `label`)
- `updateWrapper` → `POST /workspace/<id>/edit-wrapper`
- `runWorkflow` → `POST /workspace/<id>/run`
- `getNodeLog` → `GET /workspace/<id>/get-node-log/<node_id>`
- `saveWorkflowAs` → `POST /workspace/<id>/save-as`
- `openWorkflow` → `POST /workspace/register`
- `stopRuns` → `POST /workspace/<id>/stop`
