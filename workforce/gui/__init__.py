from __future__ import annotations
#!/usr/bin/env python3
# Lightweight GUI package entrypoint. Exposes WorkflowApp and main().

import logging
import threading
import tkinter as tk
import atexit

# Use the renamed module: client.py (ServerClient is a client to the server)
from .state import GUIState
from .client import ServerClient
from .canvas import GraphCanvas
from .app import launch as main  # package-level entrypoint
from workforce import utils

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)


class WorkflowApp:
    def __init__(self, master, url: str):
        self.master = master
        # Single source of truth for UI state
        self.state = GUIState()
        self.base_url = url

        # Legacy aliases to avoid changing every reference at once
        # Both refer to the same mutable objects where applicable
        self.graph = self.state.graph
        self.selected_nodes = self.state.selected_nodes
        self.scale = self.state.scale
        self.base_font_size = self.state.base_font_size
        self.base_edge_width = self.state.base_edge_width

        # UI layout
        self.master.title("Workforce")

        # Ensure layout supports a right-side zoom slider
        self.master.grid_rowconfigure(1, weight=1)
        self.master.grid_columnconfigure(0, weight=1)
        self.master.grid_columnconfigure(1, weight=0)

        self.canvas = tk.Canvas(master, width=1000, height=600, bg="white")
        self.canvas.grid(row=1, column=0, sticky="nsew")

        # --- Zoom slider on the right ---
        self.zoom_slider = tk.Scale(
            master,
            from_=0.1,
            to=3.0,
            orient=tk.VERTICAL,
            resolution=0.1,
            command=self.on_zoom_scroll,
            showvalue=False,
            tickinterval=0,
            sliderlength=20,
            width=10
        )
        self.zoom_slider.set(1.0)
        self.zoom_slider.grid(row=1, column=1, sticky="ns")

        # Server client abstracts REST + SocketIO
        self.server = ServerClient(self.base_url, on_graph_update=self.on_graph_update)
        self.client_connected = False

        menubar = tk.Menu(self.master)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Exit", command=self.master.quit, accelerator="Q")
        menubar.add_cascade(label="File", menu=file_menu)

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Add Node", command=self.add_node, accelerator="dbl click canvas")
        edit_menu.add_command(label="Remove Node", command=self.remove_node, accelerator="D")
        edit_menu.add_command(label="Connect Nodes", command=self.connect_nodes, accelerator="E")
        edit_menu.add_command(label="Clear Edges", command=self.delete_edges_from_selected, accelerator="Shift+E")
        edit_menu.add_command(label="Clear Status", command=self.clear_all, accelerator="Shift+C")
        menubar.add_cascade(label="Edit", menu=edit_menu)

        # Run menu
        run_menu = tk.Menu(menubar, tearoff=0)
        run_menu.add_command(label="Run Node", command=self.run_selected, accelerator="R")
        run_menu.add_command(label="Run Pipeline", command=self.run_pipeline, accelerator="Shift+R")
        run_menu.add_command(label="View Log", command=self.show_node_log, accelerator="L")
        run_menu.add_separator()
        self.run_remotely_var = tk.BooleanVar(value=False)
        run_menu.add_checkbutton(label="Run Remotely", variable=self.run_remotely_var, onvalue=True, offvalue=False)
        menubar.add_cascade(label="Run", menu=run_menu)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Wrapper", command=self.wrapper_popup, accelerator="P")
        menubar.add_cascade(label="Tools", menu=tools_menu)

        self.master.config(menu=menubar)

        # initialize wrapper from state
        self.state.wrapper = "{}"

        # Try connect socketio and notify server
        self._client_connect()
        self._reload_graph()

        # cleanup on exit
        atexit.register(self._atexit_disconnect)
        self.master.protocol("WM_DELETE_WINDOW", self._on_close)

        # interaction state initializations (fix AttributeError on first events)
        self.state.dragging_node = None
        self._edge_line = None
        self.state.edge_start = None

        # Canvas view takes ownership of drawing + node widgets
        callbacks = {
            "on_node_click": self.handle_node_click,
            "on_node_press": self.on_node_press,
            "on_node_drag": self.on_node_drag,
            "on_node_release": self.on_node_release,
            "on_node_double_click": self.on_node_double_click,
            "on_node_right_click": self.on_node_right_click,
            "on_node_double_right_click": self.on_node_double_right_click,
        }
        self.canvas_view = GraphCanvas(self.canvas, self.state, callbacks)

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def on_graph_update(self, data=None):
        log.debug(f"Graph update received via SocketIO. Payload: {data}")
        # Schedule the visual update on the main GUI thread
        self.master.after(0, self._reload_graph)

    def _client_connect(self):
        if self.client_connected or not self.base_url:
            return
        try:
            self.server.client_connect()
            self.client_connected = True
        except Exception:
            pass

    def _client_disconnect(self):
        if not self.client_connected or not self.base_url:
            return
        try:
            self.server.client_disconnect()
        except Exception:
            pass
        self.client_connected = False

    def _atexit_disconnect(self):
        try:
            self._client_disconnect()
        except Exception:
            pass

    def _on_close(self):
        try:
            self._client_disconnect()
        except Exception:
            pass
        try:
            self.master.destroy()
        except Exception:
            self.master.quit()

    def _reload_graph(self):
        def _fetch():
            try:
                data = self.server.get_graph(timeout=1.0)
                if data:
                    self.state.graph = data
                    self.graph = self.state.graph  # keep legacy alias in sync
                    graph_attrs = self.state.graph.get('graph', {})
                    self.state.wrapper = graph_attrs.get('wrapper', '{}')
                    self.master.after(0, self._redraw_graph)
            except Exception as e:
                log.warning("Background graph fetch failed: %s", e)
        threading.Thread(target=_fetch, daemon=True).start()

    def _redraw_graph(self):
        for node in self.state.graph.get("nodes", []):
            try:
                node['x'] = float(node.get('x', 100))
                node['y'] = float(node.get('y', 100))
            except Exception:
                node['x'], node['y'] = 100.0, 100.0
        # keep legacy alias in sync
        self.graph = self.state.graph
        self.canvas_view.redraw(self.state.graph)


# Keep __all__ explicit for clarity
__all__ = ["WorkflowApp", "GUIState", "ServerClient", "main"]
