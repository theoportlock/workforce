import logging
import threading
import tkinter as tk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText
import requests
import atexit
import time  # Add this import at the top

from workforce import utils
from .state import GUIState
from .client import ServerClient
from .canvas import GraphCanvas

log = logging.getLogger(__name__)

class WorkflowApp:
    def __init__(self, master, url: str):
        self.master = master
        # Single source of truth for UI state
        self.state = GUIState()
        self.base_url = url

        # Legacy aliases for compatibility
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
        run_menu.add_command(label="Run Subset", command=self.run_selected, accelerator="r")
        run_menu.add_command(label="Run Pipeline", command=self.run_pipeline, accelerator="R")
        run_menu.add_command(label="View Log", command=self.show_node_log, accelerator="L")
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
        # Don't fetch graph immediately; let SocketIO deliver it or use fallback
        self.master.after(2000, self._try_load_graph_via_http)

        # cleanup on exit
        atexit.register(self._atexit_disconnect)
        self.master.protocol("WM_DELETE_WINDOW", self._on_close)

        # interaction state initializations
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

        # After setting up menus and canvas, add logging for bindings
        log.info("Binding shortcuts: q for quit, r for subset run, R for pipeline run")
        self.master.bind('q', lambda e: self.save_and_exit())
        self.master.bind('r', lambda e: self.run_selected())
        self.master.bind('R', lambda e: self.run_pipeline())
        self.master.bind('<Shift-C>', lambda e: self.clear_all())
        self.master.bind('d', lambda e: self.remove_node())
        self.master.bind('c', lambda e: self.clear_selected_status())
        self.master.bind('e', lambda e: self.connect_nodes())
        self.master.bind('E', lambda e: self.delete_edges_from_selected())
        self.master.bind('p', lambda e: self.wrapper_popup())
        self.master.bind('l', lambda e: self.show_node_log())
        self.master.bind('o', lambda e: self.load_workfile())
        self.master.bind('<Control-s>', lambda e: self._save_graph_on_server())
        self.master.bind('<Control-Up>', lambda e: self.zoom_in())
        self.master.bind('<Control-Down>', lambda e: self.zoom_out())

        # Canvas bindings for interaction
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<Button-4>", self.on_zoom)
        self.canvas.bind("<Button-5>", self.on_zoom)
        self.canvas.bind("<ButtonPress-3>", self.on_right_press)
        self.canvas.bind("<B3-Motion>", self.on_right_motion)
        self.canvas.bind("<ButtonRelease-3>", self.on_right_release)
        self.canvas.bind("<ButtonPress-1>", self.on_left_press)
        self.canvas.bind("<B1-Motion>", self.on_left_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_release)
        self.canvas.bind("<Shift-ButtonPress-1>", self.on_shift_left_press)
        self.canvas.bind("<Shift-B1-Motion>", self.on_shift_left_motion)
        self.canvas.bind("<Shift-ButtonRelease-1>", self.on_shift_left_release)
        self.canvas.bind("<Double-Button-1>", self.on_canvas_double_click)

    # --- Network helpers ---
    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def _client_connect(self):
        if self.client_connected or not self.base_url:
            return
        try:
            # Establish SocketIO connection for live updates
            self.server.connect()
            # Also notify server via REST API
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

    # ----------------------
    # Graph loading / saving
    # ----------------------
    def _reload_graph(self):
        # Fetch authoritative node-link dict from server if possible
        def _fetch():
            # Try once with a longer timeout, don't retry multiple times
            try:
                data = self.server.get_graph(timeout=10.0)
                if data:
                    self.state.graph = data
                    # keep legacy alias in sync
                    self.graph = self.state.graph
                    graph_attrs = self.state.graph.get('graph', {})
                    self.state.wrapper = graph_attrs.get('wrapper', '{}')
                    self.master.after(0, self._redraw_graph)
                return
            except Exception as e:
                log.debug(f"Graph fetch failed (this is OK if using SocketIO): {e}")
        threading.Thread(target=_fetch, daemon=True).start()

    def _try_load_graph_via_http(self):
        """Try to load graph via HTTP as fallback if SocketIO hasn't delivered it yet."""
        # Only try if we don't have a graph yet
        if not self.state.graph.get("nodes"):
            self._reload_graph()

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

    def _save_graph_on_server(self):
        if not self.base_url:
            return
        try:
            utils._post(self.base_url, "/save-graph")
        except Exception:
            pass

    def load_workfile(self):
        """Reload the graph from server."""
        self._reload_graph()

    # ----------------------
    # Node / edge operations (server-mediated)
    # ----------------------
    def add_node_at(self, x, y, label=None):
        def on_save(lbl):
            if not lbl.strip():
                return
            payload = {"label": lbl, "x": x / self.state.scale, "y": y / self.state.scale}
            try:
                self.server.add_node(lbl, payload["x"], payload["y"])
            except Exception as e:
                messagebox.showerror("Add node failed", str(e))
        if label:
            on_save(label)
        else:
            self.node_label_popup("", on_save)

    def update_node_position(self, node_id: str, x: float, y: float):
        try:
            self.server.edit_node_position(node_id, x, y)
        except Exception as e:
            log.error(f"Failed to update node position for {node_id}: {e}")

    def add_node(self):
        def on_save(label):
            if not label.strip():
                return
            count = len(self.graph.get("nodes", []))
            x = 100 + count * 50
            y = 100
            try:
                self.server.add_node(label, x, y)
            except Exception as e:
                messagebox.showerror("Add node error", str(e))
        self.node_label_popup("", on_save)

    def remove_node(self):
        for nid in list(self.selected_nodes):
            try:
                self.server.remove_node(nid)
            except Exception as e:
                log.error(f"remove_node failed for {nid}: {e}")
        # clear selection via state alias
        self.selected_nodes.clear()

    def connect_nodes(self):
        if len(self.selected_nodes) < 2:
            return
        for i in range(len(self.selected_nodes) - 1):
            src = self.selected_nodes[i]
            tgt = self.selected_nodes[i + 1]
            try:
                self.server.add_edge(src, tgt)
            except Exception as e:
                log.error(f"add-edge failed for {src}->{tgt}: {e}")

    def delete_edges_from_selected(self):
        links = list(self.state.graph.get("links", []))
        for l in links:
            if l.get("source") in self.state.selected_nodes or l.get("target") in self.state.selected_nodes:
                try:
                    self.server.remove_edge(l.get("source"), l.get("target"))
                except Exception as e:
                    log.error(f"remove-edge failed for {l.get('source')}->{l.get('target')}: {e}")

    # ----------------------
    # Node Editing
    # ----------------------
    def on_node_double_click(self, event, node_id):
        node_data = next((n for n in self.state.graph.get("nodes", []) if n.get("id") == node_id), None)
        if not node_data:
            return "break"
        current_label = node_data.get("label", "")
        def on_save(new_label):
            try:
                utils._post(self.base_url, "/edit-node-label", {"node_id": node_id, "label": new_label})
            except Exception as e:
                messagebox.showerror("Update error", str(e))
        self.node_label_popup(current_label, on_save)
        return "break"

    def node_label_popup(self, initial_value, on_save):
        editor = tk.Toplevel(self.master)
        editor.title("Node Label")
        editor.geometry("600x300")
        editor.minsize(600, 300)
        text_widget = tk.Text(editor, wrap='word', font=("TkDefaultFont", 10), height=6)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10,0))
        text_widget.insert("1.0", initial_value)

        def save_and_close(event=None):
            new_label = text_widget.get("1.0", "end-1c")
            on_save(new_label)
            editor.destroy()

        def cancel_and_close(event=None):
            editor.destroy()

        btn_frame = tk.Frame(editor)
        btn_frame.pack(fill=tk.X, padx=10, pady=(5,10))
        save_btn = tk.Button(btn_frame, text="Save", command=save_and_close)
        save_btn.pack(side=tk.LEFT, padx=5)
        cancel_btn = tk.Button(btn_frame, text="Cancel", command=cancel_and_close)
        cancel_btn.pack(side=tk.LEFT, padx=5)

        editor.bind('<Escape>', cancel_and_close)
        text_widget.bind('<Control-Return>', save_and_close)
        text_widget.bind('<Control-KP_Enter>', save_and_close)

        editor.transient(self.master)
        editor.wait_visibility()
        editor.grab_set()
        text_widget.focus_set()

    def wrapper_popup(self):
        editor = tk.Toplevel(self.master)
        editor.title("Command Wrapper")
        editor.geometry("600x150")
        editor.minsize(400, 150)
        frame = tk.Frame(editor)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        label = tk.Label(frame, text="Enter the command wrapper. Use {} as a placeholder for the node's command.")
        label.pack(pady=(0, 5), anchor="w")
        wrapper_entry = tk.Entry(frame, font=("TkDefaultFont", 10))
        wrapper_entry.pack(fill=tk.X, expand=True)
        wrapper_entry.insert(0, self.state.wrapper)
        frame.columnconfigure(0, weight=1)
        def save_and_close(event=None):
            self.state.wrapper = wrapper_entry.get()
            self.save_wrapper()
            editor.destroy()
        def cancel_and_close(event=None):
            editor.destroy()
        btn_frame = tk.Frame(editor)
        btn_frame.pack(fill=tk.X, padx=10, pady=(5,10))
        save_btn = tk.Button(btn_frame, text="Save", command=save_and_close)
        save_btn.pack(side=tk.RIGHT, padx=5)
        cancel_btn = tk.Button(btn_frame, text="Cancel", command=cancel_and_close)
        cancel_btn.pack(side=tk.RIGHT, padx=5)
        editor.bind('<Escape>', cancel_and_close)
        wrapper_entry.bind('<Return>', save_and_close)
        editor.transient(self.master)
        editor.grab_set()
        wrapper_entry.focus_set()

    def save_wrapper(self):
        if not self.base_url:
            return
        try:
            utils._post(self.base_url, "/edit-wrapper", {"wrapper": self.state.wrapper})
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save wrapper: {e}")

    def show_node_log(self):
        if len(self.selected_nodes) != 1:
            messagebox.showinfo("Show Log", "Please select exactly one node to view its log.")
            return
        node_id = self.selected_nodes[0]
        node_data = next((n for n in self.state.graph.get("nodes", []) if n.get("id") == node_id), None)
        if not node_data:
            return
        node_label = node_data.get("label", node_id)
        log_window = tk.Toplevel(self.master)
        log_window.title(f"Log for: {node_label}")
        log_window.geometry("800x600")
        log_window.minsize(400, 200)
        log_window.bind('<Escape>', lambda e: log_window.destroy())
        log_display = ScrolledText(log_window, wrap='word', font=("TkFixedFont", 10))
        log_display.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        log_display.insert(tk.END, "Loading log...")
        log_display.config(state=tk.DISABLED)
        def fetch_log_worker():
            try:
                r = requests.get(self._url(f"/get-node-log/{node_id}"), timeout=3.0)
                r.raise_for_status()
                log_text = r.json().get("log", "[Failed to parse log from server]")
            except Exception as e:
                log_text = f"[Failed to fetch log from server]\n\n{e}"
            def update_ui():
                log_display.config(state=tk.NORMAL)
                log_display.delete("1.0", tk.END)
                log_display.insert(tk.END, log_text)
                log_display.config(state=tk.DISABLED)
            self.master.after(0, update_ui)
        threading.Thread(target=fetch_log_worker, daemon=True).start()

    # ----------------------
    # Run operations
    # ----------------------
    def run_selected(self):
        """Run a subset of selected nodes. Lowercase 'r' key."""
        if not self.state.selected_nodes:
            return
        try:
            resp = self.server.run(nodes=self.state.selected_nodes, subset_only=True)
            run_id = (resp or {}).get("run_id")
        except Exception as e:
            messagebox.showerror("Run Error", f"Failed to trigger subset run: {e}")

    def run_pipeline(self):
        """Run pipeline from selected nodes or from in-degree 0. Uppercase 'R' key."""
        try:
            resp = self.server.run(nodes=self.state.selected_nodes if self.state.selected_nodes else None, start_failed=(not self.state.selected_nodes))
            run_id = (resp or {}).get("run_id")
        except Exception as e:
            messagebox.showerror("Run Error", f"Failed to trigger pipeline run: {e}")

    def clear_selected_status(self):
        for nid in list(self.selected_nodes):
            try:
                utils._post(self.base_url, "/edit-status", {"element_type": "node", "element_id": nid, "value": ""})
            except Exception:
                pass

    def clear_all(self):
        for n in self.state.graph.get("nodes", []):
            try:
                utils._post(self.base_url, "/edit-status", {"element_type": "node", "element_id": n.get("id"), "value": ""})
            except Exception:
                pass
        for l in self.state.graph.get("links", []):
            eid = l.get("id")
            if eid:
                try:
                    utils._post(self.base_url, "/edit-status", {"element_type": "edge", "element_id": eid, "value": ""})
                except Exception:
                    pass
        # Server will emit graph_update via SocketIO, no need to fetch here

    # ----------------------
    # Geometry helpers (delegate to canvas_view)
    # ----------------------
    def _get_node_bounds(self, node_id):
        rect, _ = self.canvas_view.node_widgets[node_id]
        return self.canvas.coords(rect)

    def _get_node_center(self, node_id):
        x1, y1, x2, y2 = self._get_node_bounds(node_id)
        return (x1 + x2) / 2, (y1 + y2) / 2

    def _clip_line_to_box(self, x0, y0, x1, y1, box):
        x_min, y_min, x_max, y_max = box
        dx = x1 - x0
        dy = y1 - y0
        if dx == 0:
            return x0, y_min if y1 < y0 else y_max
        if dy == 0:
            return (x_min if x1 < x0 else x_max), y0
        slope = dy / dx
        if x1 > x0:
            x_edge = x_max
        else:
            x_edge = x_min
        y_edge = y0 + slope * (x_edge - x0)
        if y_min <= y_edge <= y_max:
            return x_edge, y_edge
        if y1 > y0:
            y_edge = y_max
        else:
            y_edge = y_min
        x_edge = x0 + (y_edge - y0) / slope
        return x_edge, y_edge

    # ----------------------
    # Mouse/interaction handlers
    # ----------------------
    def on_canvas_double_click(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        items = self.canvas.find_overlapping(x, y, x, y)
        if items:
            return
        self.add_node_at(x, y)

    def on_left_press(self, event):
        item = self.canvas.find_withtag(tk.CURRENT)
        node_clicked = False
        for node_id, (rect, text) in self.canvas_view.node_widgets.items():
            if item and item[0] in (rect, text):
                node_clicked = True
                self.state._potential_deselect = False
                if node_id in self.state.selected_nodes:
                    self.on_node_press(event, node_id)
                else:
                    self.clear_selection()
                    self.state.selected_nodes.append(node_id)
                    if node_id in self.canvas_view.node_widgets:
                        for item2 in self.canvas_view.node_widgets[node_id]:
                            self.canvas.delete(item2)
                        del self.canvas_view.node_widgets[node_id]
                    self.canvas_view.draw_node(node_id, node_data=next(n for n in self.state.graph["nodes"] if n.get("id")==node_id))
                    self.on_node_press(event, node_id)
                break
        if not node_clicked:
            self.state._potential_deselect = True
            self.state._press_x = event.x
            self.state._press_y = event.y
            self.canvas.scan_mark(event.x, event.y)
            self.state.dragging_node = None
            self.state._panning = True
        else:
            self.state._panning = False

    def on_left_motion(self, event):
        if self.state.dragging_node:
            self.on_node_drag(event, self.state.dragging_node)
        elif getattr(self.state, '_panning', False):
            if abs(event.x - self.state._press_x) > 5 or abs(event.y - self.state._press_y) > 5:
                self.state._potential_deselect = False
            self.canvas.scan_dragto(event.x, event.y, gain=1)

    def on_node_release(self, event):  # Renamed from on_canvas_release to match callback
        if getattr(self.state, "dragging_node", None):
            self.state.dragging_node = None
            for n in list(self.state.selected_nodes):
                node = next((it for it in self.state.graph.get("nodes", []) if it.get("id") == n), None)
                if node:
                    self.update_node_position(n, node.get("x"), node.get("y"))
        if getattr(self.state, '_potential_deselect', False):
            self.clear_selection()
        self.state._potential_deselect = False
        self.state._panning = False

    def on_left_release(self, event):
        """Handle left button release - delegates to on_node_release."""
        self.on_node_release(event)

    def handle_node_click(self, event, node_id):
        if node_id in self.state.selected_nodes:
            self.state.selected_nodes.remove(node_id)
        else:
            self.state.selected_nodes.append(node_id)
        if node_id in self.canvas_view.node_widgets:
            for item in self.canvas_view.node_widgets[node_id]:
                self.canvas.delete(item)
            del self.canvas_view.node_widgets[node_id]
        self.canvas_view.draw_node(node_id, node_data=next((n for n in self.state.graph.get("nodes", []) if n.get("id")==node_id), {}), selected=(node_id in self.state.selected_nodes))

    # right-click drag to create edge
    def on_right_press(self, event):
        item = self.canvas.find_withtag(tk.CURRENT)
        for nid, (rect, txt) in self.canvas_view.node_widgets.items():
            if item and item[0] in (rect, txt):
                self.state.edge_start = nid
                coords = self.canvas.coords(rect)
                cx = (coords[0] + coords[2]) / 2
                cy = (coords[1] + coords[3]) / 2
                self._edge_line = self.canvas.create_line(cx, cy, cx, cy, dash=(3,2), fill="gray")
                return
        self.state.edge_start = None

    def on_right_motion(self, event):
        if getattr(self, "_edge_line", None):
            coords = self.canvas.coords(self._edge_line)
            self.canvas.coords(self._edge_line, coords[0], coords[1], self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))

    def on_right_release(self, event):
        if not getattr(self, "_edge_line", None):
            return
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        target = None
        for nid, (rect, txt) in self.canvas_view.node_widgets.items():
            rx1, ry1, rx2, ry2 = self.canvas.coords(rect)
            if rx1 <= x <= rx2 and ry1 <= y <= ry2:
                target = nid
                break
        self.canvas.delete(self._edge_line)
        self._edge_line = None
        if self.state.edge_start and target and target != self.state.edge_start:
            try:
                self.server.add_edge(self.state.edge_start, target)
            except Exception as e:
                log.error(f"add-edge error: {e}")

    def on_node_press(self, event, node_id):
        self.state.dragging_node = node_id
        x1, y1, x2, y2 = self._get_node_bounds(node_id)
        self.drag_offset = (event.x - x1, event.y - y1)
        self.state._multi_drag_initial = {}
        for n in self.state.selected_nodes:
            nd = next((it for it in self.state.graph.get("nodes", []) if it.get("id") == n), None)
            if nd:
                try:
                    self.state._multi_drag_initial[n] = (float(nd.get("x", 100)), float(nd.get("y", 100)))
                except Exception:
                    self.state._multi_drag_initial[n] = (100.0, 100.0)
            else:
                self.state._multi_drag_initial[n] = (100.0, 100.0)

    def on_node_drag(self, event, node_id):
        if not getattr(self.state, "dragging_node", None):
            return
        dx, dy = self.drag_offset
        new_x = (event.x - dx) / self.state.scale
        new_y = (event.y - dy) / self.state.scale
        x0, y0 = self.state._multi_drag_initial.get(node_id, (new_x, new_y))
        delta_x = new_x - x0
        delta_y = new_y - y0
        for n in list(self.state.selected_nodes):
            ix, iy = self.state._multi_drag_initial.get(n, (new_x, new_y))
            nx_ = ix + delta_x
            ny_ = iy + delta_y
            node = next((it for it in self.state.graph.get("nodes", []) if it.get("id") == n), None)
            if node:
                node['x'], node['y'] = nx_, ny_
        self.canvas_view.redraw(self.state.graph)

    # selection rectangle handlers
    def on_shift_left_press(self, event):
        self.state._select_rect_active = True
        self.state._select_rect_start = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        self.state._select_rect_id = self.canvas.create_rectangle(self.state._select_rect_start[0], self.state._select_rect_start[1], self.state._select_rect_start[0], self.state._select_rect_start[1], outline="gray", dash=(2,2), width=1, tags="select_rect")

    def on_shift_left_motion(self, event):
        if not self.state._select_rect_active or self.state._select_rect_id is None or self.state._select_rect_start is None:
            return
        x0, y0 = self.state._select_rect_start
        x1, y1 = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.canvas.coords(self.state._select_rect_id, x0, y0, x1, y1)

    def on_shift_left_release(self, event):
        if not self.state._select_rect_active or self.state._select_rect_id is None or self.state._select_rect_start is None:
            return
        x0, y0 = self.state._select_rect_start
        x1, y1 = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        x_min, x_max = min(x0, x1), max(x0, x1)
        y_min, y_max = min(y0, y1), max(y0, y1)
        for node_id, (rect, text) in self.canvas_view.node_widgets.items():
            rx1, ry1, rx2, ry2 = self.canvas.coords(rect)
            if not (rx2 < x_min or rx1 > x_max or ry2 < y_min or ry1 > y_max):
                if node_id not in self.state.selected_nodes:
                    self.state.selected_nodes.append(node_id)
                    self.canvas.itemconfig(rect, outline="black", width=1)
        self.canvas.delete(self.state._select_rect_id)
        self.state._select_rect_id = None
        self.state._select_rect_start = None
        self.state._select_rect_active = False

    # ----------------------
    # Zoom helpers (wheel + slider)
    # ----------------------
    def on_zoom(self, event):
        factor = 1.1 if getattr(event, "delta", 0) > 0 or getattr(event, "num", 0) == 4 else 1 / 1.1
        try:
            mouse_pos = (event.x, event.y)
        except Exception:
            mouse_pos = (self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2)
        self.zoom(factor, mouse_pos=mouse_pos)

    def on_zoom_scroll(self, value):
        try:
            new_scale = float(value)
        except Exception:
            return
        if abs(new_scale - self.state.scale) > 1e-9:
            factor = new_scale / self.state.scale
            self.zoom(factor, from_scroll=True, mouse_pos=(self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2))

    def zoom_in(self):
        self.zoom(1.1, mouse_pos=(self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2))

    def zoom_out(self):
        self.zoom(1 / 1.1, mouse_pos=(self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2))

    def zoom(self, factor, from_scroll=False, mouse_pos=None):
        old_scale = self.state.scale
        new_scale = self.state.scale * factor
        new_scale = max(0.1, min(new_scale, 3.0))
        if abs(new_scale - old_scale) < 1e-9:
            return
        self.state.scale = new_scale
        self.scale = self.state.scale  # keep legacy alias
        if not from_scroll:
            try:
                self.zoom_slider.set(self.state.scale)
            except Exception:
                pass
        self.current_font_size = max(1, int(self.state.base_font_size * self.state.scale))
        self.canvas_view.redraw(self.state.graph)

    # Selection helper
    def clear_selection(self):
        to_redraw = list(self.state.selected_nodes)
        self.state.selected_nodes.clear()
        for nid in to_redraw:
            if nid in self.canvas_view.node_widgets:
                for item in self.canvas_view.node_widgets[nid]:
                    self.canvas.delete(item)
                del self.canvas_view.node_widgets[nid]
            nd = next((n for n in self.state.graph.get("nodes", []) if n.get("id") == nid), None)
            if nd:
                self.canvas_view.draw_node(nid, node_data=nd)

    def on_node_double_right_click(self, event, node_id):
        self.clear_selection()
        self.state.selected_nodes.append(node_id)
        self.show_node_log()
        return "break"

    def on_node_right_click(self, event, node_id):
        self.clear_selection()
        self.state.selected_nodes.append(node_id)
        nd = next((n for n in self.state.graph.get("nodes", []) if n.get("id") == node_id), None)
        if nd:
            if node_id in self.canvas_view.node_widgets:
                for item in self.canvas_view.node_widgets[node_id]:
                    self.canvas.delete(item)
                del self.canvas_view.node_widgets[node_id]
            self.canvas_view.draw_node(node_id, node_data=nd, selected=True)

    def save_and_exit(self, event=None):
        self._on_close()

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

    def on_graph_update(self, data=None):
        log.debug(f"Graph update received via SocketIO. Payload: {data}")
        self.master.after(0, self._reload_graph)
