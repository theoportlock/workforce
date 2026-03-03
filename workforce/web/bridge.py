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
            "addNode": self._add_node,
            "removeNode": self._remove_node,
            "addEdge": self._add_edge,
            "removeEdge": self._remove_edge,
            "updateNodePosition": self._update_node_position,
            "updateNodePositions": self._update_node_positions,
            "updateNodeLabel": self._update_node_label,
            "updateNodeCommand": self._update_node_command,
            "updateStatus": self._update_status,
            "updateWrapper": self._update_wrapper,
            "runWorkflow": self._run_workflow,
            "getNodeLog": self._get_node_log,
            "saveWorkflowAs": self._save_workflow_as,
            "saveWorkflowAsDialog": self._save_workflow_as_dialog,
            "openWorkflow": self._open_workflow,
            "openWorkflowDialog": self._open_workflow_dialog,
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

    def _update_status(self, params: dict[str, Any]) -> dict[str, Any]:
        return _post(self.workspace_url, "/edit-status", params)

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
        result = _post(self.workspace_url, "/save-as", params)
        self._update_workspace_from_result(result)
        new_path = result.get("new_path")
        if new_path:
            self.recent_manager.add(new_path)
        return result

    def _save_workflow_as_dialog(self, params: dict[str, Any]) -> dict[str, Any]:
        initial_path = params.get("current_path") or params.get("path")
        new_path = _choose_save_graphml_path(initial_path)
        if not new_path:
            return {"cancelled": True}
        result = self._save_workflow_as({"new_path": new_path})
        return {"cancelled": False, **result}

    def _open_workflow(self, params: dict[str, Any]) -> dict[str, Any]:
        """Register or switch to the workspace associated with a workfile path."""
        path = params.get("path") or params.get("workfile_path")
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
        initial_path = params.get("current_path") or params.get("path")
        file_path = _choose_open_graphml_path(initial_path)
        if not file_path:
            return {"cancelled": True}
        result = self._open_workflow({"path": file_path})
        return {"cancelled": False, **result}

    def _update_workspace_from_result(self, result: dict[str, Any]) -> None:
        workspace_id = result.get("workspace_id")
        if not workspace_id:
            workspace_id = result.get("new_workspace_id")
        if workspace_id:
            self.workspace_id = workspace_id

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


def _choose_open_graphml_path(current_path: str | None = None) -> str | None:
    initial_dir = os.path.dirname(os.path.abspath(current_path)) if current_path else os.path.expanduser("~")
    return _run_dialog(
        "askopenfilename",
        initialdir=initial_dir,
        title="Open Workflow",
        filetypes=[("GraphML files", "*.graphml"), ("All files", "*.*")],
    )


def _choose_save_graphml_path(current_path: str | None = None) -> str | None:
    if current_path:
        initial_dir = os.path.dirname(os.path.abspath(current_path))
        initial_file = os.path.basename(current_path)
    else:
        initial_dir = os.path.expanduser("~")
        initial_file = "workflow.graphml"
    return _run_dialog(
        "asksaveasfilename",
        initialdir=initial_dir,
        initialfile=initial_file,
        title="Save Workflow As",
        filetypes=[("GraphML files", "*.graphml"), ("All files", "*.*")],
        defaultextension=".graphml",
    )


def _run_dialog(method_name: str, **kwargs: Any) -> str | None:
    """Run a Tk file dialog in a hidden root window."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        raise RuntimeError(f"File dialog is unavailable: {exc}") from exc

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        chooser = getattr(filedialog, method_name)
        selected = chooser(**kwargs)
    finally:
        root.destroy()
    if not selected:
        return None
    return os.path.abspath(selected)
