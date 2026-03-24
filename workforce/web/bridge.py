"""JSON-RPC-like bridge for frontend-to-server workflow operations."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from workforce.gui.recent import RecentFileManager
from workforce.utils import _post

PROTOCOL_VERSION = "1.0"
SUPPORTED_PROTOCOL_VERSIONS = {"1", "1.0"}


class BridgeProtocolError(RuntimeError):
    """Raised when a bridge request is invalid."""


@dataclass
class WebBridge:
    """Dispatch bridge method requests to workspace HTTP endpoints."""

    server_url: str
    workspace_id: str

    def __post_init__(self) -> None:
        self.recent_manager = RecentFileManager()

    @property
    def workspace_url(self) -> str:
        return f"{self.server_url.rstrip('/')}/workspace/{self.workspace_id}"

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Handle a request envelope and return a response envelope.

        Request envelope: {id, method, params, protocolVersion}
        Response envelope: {id, ok, result?, error?}
        """
        request_id = request.get("id")
        try:
            method = request.get("method")
            params = request.get("params") or {}
            if not method:
                raise BridgeProtocolError("method is required")
            if not isinstance(params, dict):
                raise BridgeProtocolError("params must be an object")
            self._check_protocol_version(request.get("protocolVersion"))

            handler = self._handlers().get(method)
            if handler is None:
                raise BridgeProtocolError(f"unsupported method: {method}")

            result = handler(params)
            return {"id": request_id, "ok": True, "result": result}
        except Exception as exc:
            return {
                "id": request_id,
                "ok": False,
                "error": {
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                },
            }

    def _check_protocol_version(self, version: Any) -> None:
        """Explicitly check bridge protocol version for backward compatibility.

        Missing version is accepted as a legacy v1 request.
        """
        if version is None:
            return
        version_str = str(version)
        if version_str not in SUPPORTED_PROTOCOL_VERSIONS:
            supported = ", ".join(sorted(SUPPORTED_PROTOCOL_VERSIONS))
            raise BridgeProtocolError(
                f"Unsupported protocolVersion '{version_str}'. Supported versions: {supported}"
            )

    def _handlers(self) -> dict[str, Any]:
        return {
            "getGraph": self._get_graph,
            "clientConnect": self._client_connect,
            "clientDisconnect": self._client_disconnect,
            "addNode": self._add_node,
            "removeNode": self._remove_node,
            "addEdge": self._add_edge,
            "removeEdge": self._remove_edge,
            "updateNodePosition": self._update_node_position,
            "updateNodePositions": self._update_node_positions,
            "updateNodeLabel": self._update_node_label,
            "updateNodeCommand": self._update_node_command,
            "updateStatus": self._update_status,
            "updateStatuses": self._update_statuses,
            "updateWrapper": self._update_wrapper,
            "runWorkflow": self._run_workflow,
            "getNodeLog": self._get_node_log,
            "saveWorkflowAs": self._save_workflow_as,
            "saveWorkflowAsDialog": self._save_workflow_as_dialog,
            "openWorkflow": self._open_workflow,
            "openWorkflowDialog": self._open_workflow_dialog,
            "stopRuns": self._stop_runs,
            "getRuns": self._get_runs,
            "getClients": self._get_clients,
        }

    def _get_graph(self, params: dict[str, Any]) -> dict[str, Any]:
        del params
        return _get_json(self.workspace_url, "/get-graph")

    def _add_node(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_params("addNode", params, "label")
        return _post(self.workspace_url, "/add-node", params)

    def _client_connect(self, params: dict[str, Any]) -> dict[str, Any]:
        socketio_sid = params.get("socketio_sid")
        workfile_path = params.get("workfile_path")
        client_type = params.get("client_type")
        if not socketio_sid:
            raise BridgeProtocolError("clientConnect requires socketio_sid")
        if not workfile_path:
            raise BridgeProtocolError("clientConnect requires workfile_path")
        if client_type != "gui":
            raise BridgeProtocolError("clientConnect requires client_type: gui")
        return _post(
            self.workspace_url,
            "/client-connect",
            {
                "socketio_sid": socketio_sid,
                "workfile_path": workfile_path,
                "client_type": client_type,
            },
        )

    def _client_disconnect(self, params: dict[str, Any]) -> dict[str, Any]:
        client_type = params.get("client_type", "gui")
        client_id = params.get("client_id")
        socketio_sid = params.get("socketio_sid")
        if client_type not in {"gui", "runner"}:
            raise BridgeProtocolError("clientDisconnect requires client_type to be 'gui' or 'runner'")
        payload = {"client_type": client_type, "client_id": client_id, "socketio_sid": socketio_sid}
        return _post(self.workspace_url, "/client-disconnect", payload)

    def _remove_node(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_params("removeNode", params, "node_id")
        return _post(self.workspace_url, "/remove-node", params)

    def _add_edge(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_params("addEdge", params, "source", "target")
        return _post(self.workspace_url, "/add-edge", params)

    def _remove_edge(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_params("removeEdge", params, "source", "target")
        return _post(self.workspace_url, "/remove-edge", params)

    def _update_node_position(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_params("updateNodePosition", params, "node_id", "x", "y")
        return _post(self.workspace_url, "/edit-node-position", params)

    def _update_node_positions(self, params: dict[str, Any]) -> dict[str, Any]:
        positions = params.get("positions")
        if not isinstance(positions, list) or not positions:
            raise BridgeProtocolError("updateNodePositions requires non-empty positions array")
        return _post(self.workspace_url, "/edit-node-positions", params)

    def _update_node_label(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_params("updateNodeLabel", params, "node_id", "label")
        return _post(self.workspace_url, "/edit-node-label", params)

    def _update_node_command(self, params: dict[str, Any]) -> dict[str, Any]:
        node_id = params.get("node_id")
        label = params.get("label", params.get("command"))
        if node_id is None or label is None:
            raise BridgeProtocolError("updateNodeCommand requires node_id and command")
        return _post(self.workspace_url, "/edit-node-label", {"node_id": node_id, "label": label})

    def _update_status(self, params: dict[str, Any]) -> dict[str, Any]:
        element_type, element_id, value = self._coerce_single_status("updateStatus", params)
        payload = {
            "element_type": element_type,
            "element_id": element_id,
            "value": value,
        }
        run_id = params.get("run_id")
        if run_id:
            payload["run_id"] = run_id
        return _post(self.workspace_url, "/edit-status", payload)

    def _update_statuses(self, params: dict[str, Any]) -> dict[str, Any]:
        updates = params.get("updates")
        if not isinstance(updates, list) or not updates:
            raise BridgeProtocolError("updateStatuses requires non-empty updates array")
        normalized_updates = []
        for idx, update in enumerate(updates):
            if not isinstance(update, dict):
                raise BridgeProtocolError(f"updateStatuses update at index {idx} must be an object")
            element_type, element_id, value = self._coerce_single_status("updateStatuses", update)
            normalized_updates.append(
                {
                    "element_type": element_type,
                    "element_id": element_id,
                    "value": value,
                }
            )
        return _post(self.workspace_url, "/edit-statuses", {"updates": normalized_updates})

    def _update_wrapper(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_params("updateWrapper", params, "wrapper")
        return _post(self.workspace_url, "/edit-wrapper", params)

    def _run_workflow(self, params: dict[str, Any]) -> dict[str, Any]:
        wrapper = params.get("wrapper")
        if wrapper is not None and not isinstance(wrapper, str):
            raise BridgeProtocolError("runWorkflow wrapper must be a string")
        nodes = params.get("nodes")
        if nodes is not None and not isinstance(nodes, list):
            raise BridgeProtocolError("runWorkflow nodes must be an array")
        return _post(self.workspace_url, "/run", params)

    def _get_node_log(self, params: dict[str, Any]) -> dict[str, Any]:
        node_id = params.get("node_id")
        if not node_id:
            raise BridgeProtocolError("getNodeLog requires node_id")
        node_id_safe = urllib.parse.quote(str(node_id), safe="")
        return _get_json(self.workspace_url, f"/get-node-log/{node_id_safe}")

    def _save_workflow_as(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_params("saveWorkflowAs", params, "new_path")
        result = _post(self.workspace_url, "/save-as", params)
        self._update_workspace_from_result(result)
        new_path = result.get("new_path")
        if new_path:
            self.recent_manager.add(new_path)
        return result

    def _save_workflow_as_dialog(self, params: dict[str, Any]) -> dict[str, Any]:
        del params
        raise BridgeProtocolError("saveWorkflowAsDialog unsupported in web mode; client must provide new_path")

    def _open_workflow(self, params: dict[str, Any]) -> dict[str, Any]:
        """Register or switch to the workspace associated with a workfile path."""
        path = params.get("path")
        if not path:
            raise BridgeProtocolError("openWorkflow requires path")
        abs_path = os.path.abspath(path)
        result = _post(
            self.server_url,
            "/workspace/register",
            {"path": abs_path},
        )
        self.recent_manager.add(abs_path)
        self._update_workspace_from_result(result)
        return result

    def _open_workflow_dialog(self, params: dict[str, Any]) -> dict[str, Any]:
        del params
        raise BridgeProtocolError("openWorkflowDialog unsupported in web mode; client must provide path")

    def _update_workspace_from_result(self, result: dict[str, Any]) -> None:
        workspace_id = result.get("workspace_id")
        if not workspace_id:
            workspace_id = result.get("new_workspace_id")
        if workspace_id:
            self.workspace_id = workspace_id

    def _stop_runs(self, params: dict[str, Any]) -> dict[str, Any]:
        del params
        return _post(self.workspace_url, "/stop", {})

    def _get_runs(self, params: dict[str, Any]) -> dict[str, Any]:
        del params
        return _get_json(self.workspace_url, "/runs")

    def _get_clients(self, params: dict[str, Any]) -> dict[str, Any]:
        del params
        return _get_json(self.workspace_url, "/clients")

    def _require_params(self, method: str, params: dict[str, Any], *keys: str) -> None:
        missing = [key for key in keys if params.get(key) is None]
        if missing:
            joined = ", ".join(missing)
            raise BridgeProtocolError(f"{method} requires {joined}")

    def _coerce_single_status(self, method: str, payload: dict[str, Any]) -> tuple[str, str, str]:
        element_type = payload.get("element_type", payload.get("kind"))
        element_id = payload.get("element_id", payload.get("id"))
        value = payload.get("value", payload.get("status"))
        if not element_type or not element_id or value is None:
            raise BridgeProtocolError(
                f"{method} requires element_type/kind, element_id/id, and value/status"
            )
        if element_type not in {"node", "edge"}:
            raise BridgeProtocolError(f"{method} element_type/kind must be 'node' or 'edge'")
        return str(element_type), str(element_id), str(value)


def make_event_envelope(event: str, payload: dict[str, Any], workspace_id: str, ts: float) -> dict[str, Any]:
    """Build an event envelope pushed to frontend.

    Event envelope: {event, payload, workspaceId, ts}
    """
    return {
        "event": event,
        "payload": payload,
        "workspaceId": workspace_id,
        "ts": ts,
    }


def _get_json(base_url: str, endpoint: str) -> dict[str, Any]:
    """GET and decode JSON response from workspace endpoints."""
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint
    url = f"{base_url.rstrip('/')}{endpoint}"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
        return json.loads(raw)
    except urllib.error.HTTPError as exc:
        try:
            error_text = exc.read().decode("utf-8")
        except Exception:
            error_text = str(exc)
        raise RuntimeError(f"Failed to GET {url}: HTTP Error {exc.code}. {error_text}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to GET {url}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Server returned non-JSON response from {url}") from exc

