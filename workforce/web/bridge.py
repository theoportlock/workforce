"""JSON-RPC-like bridge for frontend-to-server workflow operations."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

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
            "addNode": self._add_node,
            "removeNode": self._remove_node,
            "addEdge": self._add_edge,
            "removeEdge": self._remove_edge,
            "updateNodePosition": self._update_node_position,
            "updateNodePositions": self._update_node_positions,
            "updateNodeLabel": self._update_node_label,
            "updateNodeCommand": self._update_node_command,
            "updateWrapper": self._update_wrapper,
            "runWorkflow": self._run_workflow,
            "getNodeLog": self._get_node_log,
            "saveWorkflowAs": self._save_workflow_as,
            "openWorkflow": self._open_workflow,
            "stopRuns": self._stop_runs,
        }

    def _get_graph(self, params: dict[str, Any]) -> dict[str, Any]:
        del params
        return _get_json(self.workspace_url, "/get-graph")

    def _add_node(self, params: dict[str, Any]) -> dict[str, Any]:
        return _post(self.workspace_url, "/add-node", params)

    def _remove_node(self, params: dict[str, Any]) -> dict[str, Any]:
        return _post(self.workspace_url, "/remove-node", params)

    def _add_edge(self, params: dict[str, Any]) -> dict[str, Any]:
        return _post(self.workspace_url, "/add-edge", params)

    def _remove_edge(self, params: dict[str, Any]) -> dict[str, Any]:
        return _post(self.workspace_url, "/remove-edge", params)

    def _update_node_position(self, params: dict[str, Any]) -> dict[str, Any]:
        return _post(self.workspace_url, "/edit-node-position", params)

    def _update_node_positions(self, params: dict[str, Any]) -> dict[str, Any]:
        return _post(self.workspace_url, "/edit-node-positions", params)

    def _update_node_label(self, params: dict[str, Any]) -> dict[str, Any]:
        return _post(self.workspace_url, "/edit-node-label", params)

    def _update_node_command(self, params: dict[str, Any]) -> dict[str, Any]:
        node_id = params.get("node_id")
        label = params.get("label", params.get("command"))
        if node_id is None or label is None:
            raise BridgeProtocolError("updateNodeCommand requires node_id and command")
        return _post(self.workspace_url, "/edit-node-label", {"node_id": node_id, "label": label})

    def _update_wrapper(self, params: dict[str, Any]) -> dict[str, Any]:
        return _post(self.workspace_url, "/edit-wrapper", params)

    def _run_workflow(self, params: dict[str, Any]) -> dict[str, Any]:
        return _post(self.workspace_url, "/run", params)

    def _get_node_log(self, params: dict[str, Any]) -> dict[str, Any]:
        node_id = params.get("node_id")
        if not node_id:
            raise BridgeProtocolError("getNodeLog requires node_id")
        node_id_safe = urllib.parse.quote(str(node_id), safe="")
        return _get_json(self.workspace_url, f"/get-node-log/{node_id_safe}")

    def _save_workflow_as(self, params: dict[str, Any]) -> dict[str, Any]:
        return _post(self.workspace_url, "/save-as", params)

    def _open_workflow(self, params: dict[str, Any]) -> dict[str, Any]:
        """Register or switch to the workspace associated with a workfile path."""
        result = _post(
            self.server_url,
            "/workspace/register",
            {"path": params.get("path") or params.get("workfile_path")},
        )
        workspace_id = result.get("workspace_id")
        if workspace_id:
            self.workspace_id = workspace_id
        return result

    def _stop_runs(self, params: dict[str, Any]) -> dict[str, Any]:
        del params
        return _post(self.workspace_url, "/stop", {})


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
