#!/usr/bin/env python3
# Lightweight GUI that talks to the Workforce server for all graph IO and edits.
# - Uses server endpoints: /get-graph, /add-node, /remove-node, /add-edge, /remove-edge,
#   /update-node, /edit-status, /save-graph, /client-connect, /client-disconnect
# - Starts a background server for the Workfile if none is registered.

import logging

import os
import sys
import time
import threading
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from tkinter.scrolledtext import ScrolledText
import requests
import socketio
import atexit
import subprocess

from workforce import utils

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)


class WorkflowApp:
    def __init__(self, master, url: str):
        self.master = master
        self.base_url = url
        self.base_url = ""
        self.graph = {"nodes": [], "links": []}
        self.node_widgets = {}
        self.selected_nodes = []
        self.scale = 1.0
        self.base_font_size = 10
        self.base_edge_width = 2

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

        # Wrapper state
        self.wrapper = "{}"

        # Bindings
        self.canvas.bind("<Double-Button-1>", self.on_canvas_double_click)
        self.canvas.bind("<ButtonPress-1>", self.on_left_press)
        self.canvas.bind("<B1-Motion>", self.on_left_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<ButtonPress-3>", self.on_right_press)
        self.canvas.bind("<B3-Motion>", self.on_right_motion)
        self.canvas.bind("<ButtonRelease-3>", self.on_right_release)
        self.master.bind('r', lambda e: self.run_selected())
        self.master.bind('<Shift-R>', lambda e: self.run_pipeline())
        self.master.bind('<Shift-C>', lambda e: self.clear_all())
        self.master.bind('d', lambda e: self.remove_node())
        self.master.bind('c', lambda e: self.clear_selected_status())
        self.master.bind('e', lambda e: self.connect_nodes())
        self.master.bind('E', lambda e: self.delete_edges_from_selected())
        self.master.bind('l', lambda e: self.show_node_log())
        self.master.bind('p', lambda e: self.wrapper_popup())
        self.master.bind('q', lambda e: self.save_and_exit())
        self.master.bind('<Control-Up>', lambda e: self.zoom_in())
        self.master.bind('<Control-Down>', lambda e: self.zoom_out())
        
        # shouldnt need this
        self.master.bind('<F5>', lambda e: self._reload_graph())

        # Add mouse-wheel zoom bindings
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<Button-4>", self.on_zoom)
        self.canvas.bind("<Button-5>", self.on_zoom)

        # Shift-selection rectangle handlers
        self.canvas.bind("<Shift-ButtonPress-1>", self.on_shift_left_press)
        self.canvas.bind("<Shift-B1-Motion>", self.on_shift_left_motion)
        self.canvas.bind("<Shift-ButtonRelease-1>", self.on_shift_left_release)

        # SocketIO
        self.sio = None
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

        # Set the base_url from the provided URL
        self.base_url = url

        # Try connect socketio and notify server
        self._start_socketio()
        self._client_connect()
        self._reload_graph()

        # cleanup on exit
        atexit.register(self._atexit_disconnect)
        self.master.protocol("WM_DELETE_WINDOW", self._on_close)

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def _start_socketio(self):
        if self.sio is not None:
            return

        # We run this in a thread so the GUI doesn't freeze while connecting
        def connect_worker():
            try:
                # Create the client with logging enabled
                self.sio = socketio.Client(logger=False, engineio_logger=False)

                # --- Define Event Handlers ---
                @self.sio.event
                def connect():
                    log.info(f"Successfully connected to {self.base_url}")

                @self.sio.event
                def connect_error(data):
                    log.warning(f"SocketIO connection failed: {data}")

                @self.sio.event
                def disconnect():
                    log.info("SocketIO disconnected")

                # Register the specific graph update handler
                self.sio.on('graph_update', self.on_graph_update)

                # Attempt connection
                log.debug(f"Attempting background SocketIO connection to {self.base_url}...")
                self.sio.connect(self.base_url, wait_timeout=5)
                
            except Exception as e:
                log.warning(f"SocketIO setup failed: {e}")
                self.sio = None

        # Start the thread
        t = threading.Thread(target=connect_worker, daemon=True)
        t.start()

    def on_graph_update(self, data=None):
        log.debug(f"Graph update received via SocketIO. Payload: {data}")
        # Schedule the visual update on the main GUI thread
        self.master.after(0, self._reload_graph)

    def _client_connect(self):
        if self.client_connected or not self.base_url:
            return
        try:
            utils._post(self.base_url, "/client-connect")
            self.client_connected = True
        except Exception:
            pass

    def _client_disconnect(self):
        if not self.client_connected or not self.base_url:
            return
        try:
            utils._post(self.base_url, "/client-disconnect")
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

    # ----------------------
    # Graph loading / saving
    # ----------------------
    def _reload_graph(self):
        # Fetch authoritative node-link dict from server if possible

        # Simple internal function to fetch and redraw
        def _fetch():
            try:
                # Use a short timeout so we don't freeze the UI
                r = requests.get(self._url("/get-graph"), timeout=1.0)
                if r.status_code == 200:
                    self.graph = r.json()
                    graph_attrs = self.graph.get('graph', {})
                    self.wrapper = graph_attrs.get('wrapper', '{}')

                    # Schedule the drawing on the main thread
                    self.master.after(0, self._redraw_graph)
            except Exception as e:
                log.warning(f"Background graph fetch failed: {e}")

        # Run the network request in a separate thread to avoid freezing GUI
        threading.Thread(target=_fetch, daemon=True).start()

    # New helper: centralized, thread-safe redraw of the current self.graph
    def _redraw_graph(self):
        # Clear canvas and widgets
        self.canvas.delete("all")
        self.node_widgets.clear()
        # Normalize node coordinates and draw
        for node in self.graph.get("nodes", []):
            try:
                node['x'] = float(node.get('x', 100))
                node['y'] = float(node.get('y', 100))
            except Exception:
                node['x'], node['y'] = 100.0, 100.0
            self.draw_node(node.get("id"), node_data=node)
        # Draw links/edges
        for link in self.graph.get("links", []):
            self.draw_edge(link.get("source"), link.get("target"))

    # Add server-backed save (used by run/save actions)
    def _save_graph_on_server(self):
        """Ask the server to persist the current graph (no-op if server saved)."""
        if not self.base_url:
            return
        try:
            utils._post(self.base_url, "/save-graph")
        except Exception:
            # non-fatal; GUI should continue to operate even if server/save is unavailable
            pass

    # ----------------------
    # Node / edge operations (server-mediated)
    # ----------------------
    def add_node_at(self, x, y, label=None):
        def on_save(lbl):
            if not lbl.strip():
                return
            payload = {"label": lbl, "x": x / self.scale, "y": y / self.scale}
            try:
                utils._post(self.base_url, "/add-node", payload)
                # self._reload_graph() # Wait for graph_update event
            except Exception as e:
                messagebox.showerror("Add node failed", str(e))
        if label:
            on_save(label)
        else:
            self.node_label_popup("", on_save)

    def update_node_position(self, node_id: str, x: float, y: float):
        try:
            utils._post(self.base_url, "/edit-node-position", {
                "node_id": node_id,
                "x": x,
                "y": y
            })
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
                utils._post(self.base_url, "/add-node", {"label": label, "x": x, "y": y})
                # self._reload_graph() # Wait for graph_update event
            except Exception as e:
                messagebox.showerror("Add node error", str(e))
        self.node_label_popup("", on_save)

    def remove_node(self):
        for nid in list(self.selected_nodes):
            try:
                utils._post(self.base_url, "/remove-node", {"node_id": nid})
            except Exception as e:
                log.error(f"remove_node failed for {nid}: {e}")
        self.selected_nodes.clear()
        # self._reload_graph() # Wait for graph_update event

    def connect_nodes(self):
        if len(self.selected_nodes) < 2:
            return
        for i in range(len(self.selected_nodes) - 1):
            src = self.selected_nodes[i]
            tgt = self.selected_nodes[i + 1]
            try:
                utils._post(self.base_url, "/add-edge", {"source": src, "target": tgt})
            except Exception as e:
                log.error(f"add-edge failed for {src}->{tgt}: {e}")
        # self._reload_graph() # Wait for graph_update event

    def delete_edges_from_selected(self):
        links = list(self.graph.get("links", []))
        for l in links:
            if l.get("source") in self.selected_nodes or l.get("target") in self.selected_nodes:
                try:
                    utils._post(self.base_url, "/remove-edge", {"source": l.get("source"), "target": l.get("target")})
                except Exception as e:
                    log.error(f"remove-edge failed for {l.get('source')}->{l.get('target')}: {e}")
        # self._reload_graph() # Wait for graph_update event

    def on_node_double_click(self, event, node_id):
        """Handles double-click on a node to edit its label."""
        node_data = next((n for n in self.graph.get("nodes", []) if n.get("id") == node_id), None)
        if not node_data:
            return "break"  # Stop propagation even if node data is not found

        current_label = node_data.get("label", "")

        def on_save(new_label):
            try:
                utils._post(self.base_url, "/edit-node-label", {"node_id": node_id, "label": new_label})
            except Exception as e:
                messagebox.showerror("Update error", str(e))

        self.node_label_popup(current_label, on_save)

        return "break"  # This is crucial to prevent the canvas double-click event


    def update_node(self):
        # This method is removed as the primary way to update a node label is via double-clicking a node
        # which calls node_label_popup and then uses the server's /update-node endpoint.
        # The menu item "Update Node" is also removed.
        pass
    
    def run_selected(self):
        if self.base_url:
            if self.run_remotely_var.get():
                # Remote run: just POST to /run
                payload = {"nodes": self.selected_nodes, "subset_only": True, "run_on_server": True}
                try:
                    utils._post(self.base_url, "/run", payload)
                    messagebox.showinfo("Run Triggered", "Remote run triggered for selected nodes.")
                except Exception as e:
                    messagebox.showerror("Run Error", f"Failed to trigger remote run: {e}")
            else:
                # Local run: spawn a subprocess
                try:
                    cmd = [sys.executable, "-m", "workforce", "run", self.base_url, "--subset-only"]
                    if self.selected_nodes:
                        cmd.extend(["--nodes", *self.selected_nodes])
                    log.info(f"Spawning local runner for subset: {' '.join(cmd)}")
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    messagebox.showinfo("Run Started", "A local background runner has been started for the selected nodes.")
                except Exception as e:
                    messagebox.showerror("Run Error", f"Failed to start local runner: {e}")
    
    def run_pipeline(self): # Renamed from run_pipeline to match CLI
        if self.base_url:
            if self.run_remotely_var.get():
                # Remote run: just POST to /run
                payload = {"nodes": self.selected_nodes if self.selected_nodes else None, "run_on_server": True}
                try:
                    utils._post(self.base_url, "/run", payload)
                    messagebox.showinfo("Run Triggered", "Remote pipeline run triggered.")
                except Exception as e:
                    messagebox.showerror("Run Error", f"Failed to trigger remote run: {e}")
            else:
                # Local run: spawn a subprocess
                try:
                    cmd = [sys.executable, "-m", "workforce", "run", self.base_url]
                    if self.selected_nodes:
                        cmd.extend(["--nodes", *self.selected_nodes])
                    log.info(f"Spawning local runner for pipeline: {' '.join(cmd)}")
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    messagebox.showinfo("Run Started", "A local background runner has been started for the pipeline.")
                except Exception as e:
                    messagebox.showerror("Run Error", f"Failed to start local runner: {e}")

    def clear_selected_status(self):
        for nid in list(self.selected_nodes):
            try:
                utils._post(self.base_url, "/edit-status", {"element_type": "node", "element_id": nid, "value": ""})
            except Exception:
                pass
        # self._reload_graph() # Wait for graph_update event

    def clear_all(self):
        for n in self.graph.get("nodes", []):
            try:
                utils._post(self.base_url, "/edit-status", {"element_type": "node", "element_id": n.get("id"), "value": ""})
            except Exception:
                pass
        for l in self.graph.get("links", []):
            eid = l.get("id")
            if eid:
                try:
                    utils._post(self.base_url, "/edit-status", {"element_type": "edge", "element_id": eid, "value": ""})
                except Exception:
                    pass
        # self._reload_graph() # Wait for graph_update event

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
        wrapper_entry.insert(0, self.wrapper)

        frame.columnconfigure(0, weight=1)

        def save_and_close(event=None):
            self.wrapper = wrapper_entry.get()
            self.save_wrapper() # Save to server
            editor.destroy()

        def cancel_and_close(event=None):
            editor.destroy()

        btn_frame = tk.Frame(editor)
        btn_frame.pack(fill=tk.X, padx=10, pady=(5,10))
        save_btn = tk.Button(btn_frame, text="Save", command=save_and_close)
        save_btn.pack(side=tk.RIGHT, padx=5)
        cancel_btn = tk.Button(btn_frame, text="Cancel", command=cancel_and_close)
        cancel_btn.pack(side=tk.RIGHT, padx=5)

        # Keyboard shortcuts
        editor.bind('<Escape>', cancel_and_close)
        wrapper_entry.bind('<Return>', save_and_close)

        editor.transient(self.master)
        editor.grab_set()
        wrapper_entry.focus_set()

    def save_wrapper(self):
        """Sends the current wrapper to the server to be saved."""
        if not self.base_url:
            return
        try:
            utils._post(self.base_url, "/edit-wrapper", {"wrapper": self.wrapper})
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save wrapper: {e}")

    def show_node_log(self):
        if len(self.selected_nodes) != 1:
            messagebox.showinfo("Show Log", "Please select exactly one node to view its log.")
            return

        node_id = self.selected_nodes[0]
        node_data = next((n for n in self.graph.get("nodes", []) if n.get("id") == node_id), None)

        if not node_data:
            return

        node_label = node_data.get("label", node_id)

        # Create the popup window
        log_window = tk.Toplevel(self.master)
        log_window.title(f"Log for: {node_label}")
        log_window.geometry("800x600")
        log_window.minsize(400, 200)

        # Add Escape key binding to close the window
        log_window.bind('<Escape>', lambda e: log_window.destroy())

        log_display = ScrolledText(log_window, wrap='word', font=("TkFixedFont", 10))
        log_display.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        log_display.insert(tk.END, "Loading log...")
        log_display.config(state=tk.DISABLED)  # Make it read-only

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
    # Drawing and UI helpers
    # ----------------------
    def draw_node(self, node_id, node_data=None, font_size=None, selected=None):
        data = node_data if node_data is not None else next((n for n in self.graph.get("nodes", []) if n.get("id") == node_id), {})
        # Determine selection: explicit param takes precedence, otherwise consult model
        if selected is None:
            selected = node_id in self.selected_nodes

        vx = float(data.get("x", 100))
        vy = float(data.get("y", 100))
        x = vx * self.scale
        y = vy * self.scale
        label = data.get("label", node_id)
        status = data.get("status", "").lower()
        status_colors = {'running': 'lightblue', 'run': 'lightcyan', 'ran': 'lightgreen', 'fail': 'lightcoral'}
        fill = status_colors.get(status, "lightgray")
        
        font_size = font_size or max(1, int(self.base_font_size * self.scale))
        temp = self.canvas.create_text(0, 0, text=label, anchor="nw", font=("TkDefaultFont", font_size))
        bbox = self.canvas.bbox(temp) or (0, 0, 60, 20)
        self.canvas.delete(temp)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        pad_x, pad_y = 10 * self.scale, 6 * self.scale
        w = text_w + 2 * pad_x
        h = text_h + 2 * pad_y
        outline_color = "black" if selected else ""
        rect = self.canvas.create_rectangle(x, y, x + w, y + h, fill=fill, outline=outline_color, width=1 if selected else 0)
        txt = self.canvas.create_text(x + pad_x, y + pad_y, text=label, anchor="nw", font=("TkDefaultFont", font_size))
        self.node_widgets[node_id] = (rect, txt)
        for item in (rect, txt):
            self.canvas.tag_bind(item, "<Button-1>", lambda e, nid=node_id: self.handle_node_click(e, nid))
            self.canvas.tag_bind(item, "<ButtonPress-1>", lambda e, nid=node_id: self.on_node_press(e, nid))
            self.canvas.tag_bind(item, "<B1-Motion>", lambda e, nid=node_id: self.on_node_drag(e, nid))
            self.canvas.tag_bind(item, "<ButtonRelease-1>", lambda e: self.on_node_release(e))
            self.canvas.tag_bind(item, "<Double-Button-1>", lambda e, nid=node_id: self.on_node_double_click(e, nid))


    def draw_edge(self, src, tgt):
        x1, y1 = self._get_node_center(src)
        x2, y2 = self._get_node_center(tgt)
        src_box = self._get_node_bounds(src)
        tgt_box = self._get_node_bounds(tgt)
        x1a, y1a = self._clip_line_to_box(x1, y1, x2, y2, src_box)
        x2a, y2a = self._clip_line_to_box(x2, y2, x1, y1, tgt_box)
        line = self.canvas.create_line(
            x1a, y1a, x2a, y2a,
            arrow=tk.LAST,
            fill='lightgray',
            tags="edge",
            width=self.base_edge_width * self.scale
        )
        self.canvas.tag_lower(line)

    def _get_node_bounds(self, node_id):
        rect, _ = self.node_widgets[node_id]
        return self.canvas.coords(rect)

    def _get_node_center(self, node_id):
        x1, y1, x2, y2 = self._get_node_bounds(node_id)
        return (x1 + x2) / 2, (y1 + y2) / 2

    def _clip_line_to_box(self, x0, y0, x1, y1, box):
        # Compute intersection of line (x0,y0)->(x1,y1) with rectangle box
        x_min, y_min, x_max, y_max = box
        dx = x1 - x0
        dy = y1 - y0

        if dx == 0:  # vertical line
            return x0, y_min if y1 < y0 else y_max

        if dy == 0:  # horizontal line
            return x_min if x1 < x0 else x_max, y0

        # Calculate intersection with all four box sides
        slope = dy / dx

        # Try left and right edges
        if x1 > x0:
            x_edge = x_max
        else:
            x_edge = x_min
        y_edge = y0 + slope * (x_edge - x0)
        if y_min <= y_edge <= y_max:
            return x_edge, y_edge

        # Try top and bottom edges
        if y1 > y0:
            y_edge = y_max
        else:
            y_edge = y_min
        x_edge = x0 + (y_edge - y0) / slope
        return x_edge, y_edge
    
    # ----------------------
    # Mouse/interaction handlers
    # ----------------------
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

        # Keyboard shortcuts
        editor.bind('<Escape>', cancel_and_close)
        text_widget.bind('<Control-Return>', save_and_close)
        text_widget.bind('<Control-KP_Enter>', save_and_close)

        editor.transient(self.master)
        editor.wait_visibility()  # Ensure window is visible before grab_set
        editor.grab_set()
        text_widget.focus_set()

    def on_canvas_double_click(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        # Check if we clicked on an existing item. If so, do nothing.
        # The node's own double-click handler will take care of it.
        items = self.canvas.find_overlapping(x, y, x, y)
        if items:
            return
        self.add_node_at(x, y)

    def on_left_press(self, event):
        # Check if clicked on a node
        item = self.canvas.find_withtag(tk.CURRENT)
        node_clicked = False
        for node_id, (rect, text) in self.node_widgets.items():
            if item and item[0] in (rect, text):
                node_clicked = True
                self._potential_deselect = False # Clicked on a node, so no deselect
                # If node is already selected, do not change selection, just start drag
                if node_id in self.selected_nodes:
                    self.on_node_press(event, node_id)
                else:
                    # Select only this node
                    self.clear_selection()
                    self.selected_nodes.append(node_id)
                    if node_id in self.node_widgets:
                        for item2 in self.node_widgets[node_id]:
                            self.canvas.delete(item2)
                        del self.node_widgets[node_id]
                    self.draw_node(node_id, font_size=getattr(self, 'current_font_size', self.base_font_size))
                    self.on_node_press(event, node_id)
                break
        if not node_clicked:
            # Clicked empty space, prepare to pan and potentially deselect
            self._potential_deselect = True
            self._press_x = event.x
            self._press_y = event.y
            self.canvas.scan_mark(event.x, event.y)
            self.dragging_node = None
            self._panning = True
        else:
            self._panning = False

    def on_left_motion(self, event):
        if self.dragging_node:
            self.on_node_drag(event, self.dragging_node)
        elif getattr(self, '_panning', False):
            # If there is motion, it's a pan, not a deselect click
            if abs(event.x - self._press_x) > 5 or abs(event.y - self._press_y) > 5:
                self._potential_deselect = False
            self.canvas.scan_dragto(event.x, event.y, gain=1)

    def on_canvas_release(self, event):
        # If a drag was in progress, finalize it and send updates.
        if getattr(self, "dragging_node", None):
            self.dragging_node = None
            for n in list(self.selected_nodes):
                node = next((it for it in self.graph.get("nodes", []) if it.get("id") == n), None)
                if node:
                    self.update_node_position(n, node.get("x"), node.get("y"))
        # If a click on empty space occurred, deselect nodes.
        if getattr(self, '_potential_deselect', False):
            self.clear_selection()
        self._potential_deselect = False
        self._panning = False

    def handle_node_click(self, event, node_id):
        if node_id in self.selected_nodes:
            self.selected_nodes.remove(node_id)
        else:
            self.selected_nodes.append(node_id)
        # Redraw the node to update its outline based on selection state
        if node_id in self.node_widgets:
            for item in self.node_widgets[node_id]:
                self.canvas.delete(item)
            del self.node_widgets[node_id]
        self.draw_node(node_id, selected=(node_id in self.selected_nodes))

    # right-click drag to create edge
    def on_right_press(self, event):
        item = self.canvas.find_withtag(tk.CURRENT)
        # start drag from node if clicked on one
        for nid, (rect, txt) in self.node_widgets.items():
            if item and item[0] in (rect, txt):
                self._edge_start = nid
                coords = self.canvas.coords(rect)
                cx = (coords[0] + coords[2]) / 2
                cy = (coords[1] + coords[3]) / 2
                self._edge_line = self.canvas.create_line(cx, cy, cx, cy, dash=(3,2), fill="gray")
                return
        self._edge_start = None

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
        for nid, (rect, txt) in self.node_widgets.items():
            rx1, ry1, rx2, ry2 = self.canvas.coords(rect)
            if rx1 <= x <= rx2 and ry1 <= y <= ry2:
                target = nid
                break
        self.canvas.delete(self._edge_line)
        self._edge_line = None
        if self._edge_start and target and target != self._edge_start:
            # instruct server to add edge
            try:
                utils._post(self.base_url, "/add-edge", {"source": self._edge_start, "target": target})
            except Exception as e:
                log.error(f"add-edge error: {e}")

    # node dragging (move positions locally, then send /update-node on release)
    def on_node_press(self, event, node_id):
        self.dragging_node = node_id
        x1, y1, x2, y2 = self._get_node_bounds(node_id)
        self.drag_offset = (event.x - x1, event.y - y1)
        # Store initial positions for all selected nodes (virtual coordinates)
        self._multi_drag_initial = {}
        for n in self.selected_nodes:
            # find node dict from node-link graph
            nd = next((it for it in self.graph.get("nodes", []) if it.get("id") == n), None)
            if nd:
                try:
                    self._multi_drag_initial[n] = (float(nd.get("x", 100)), float(nd.get("y", 100)))
                except Exception:
                    self._multi_drag_initial[n] = (100.0, 100.0)
            else:
                self._multi_drag_initial[n] = (100.0, 100.0)

    def on_node_drag(self, event, node_id):
        if not getattr(self, "dragging_node", None):
            return
        dx, dy = self.drag_offset
        new_x = (event.x - dx) / self.scale
        new_y = (event.y - dy) / self.scale
        # compute delta for primary node
        x0, y0 = self._multi_drag_initial.get(node_id, (new_x, new_y))
        delta_x = new_x - x0
        delta_y = new_y - y0
        # update selected nodes in-memory
        for n in self.selected_nodes:
            ix, iy = self._multi_drag_initial.get(n, (new_x, new_y))
            nx_ = ix + delta_x
            ny_ = iy + delta_y
            node = next((it for it in self.graph.get("nodes", []) if it.get("id") == n), None)
            if node:
                node['x'], node['y'] = nx_, ny_
        # redraw
        self.canvas.delete("all")
        self.node_widgets.clear()
        for node in self.graph.get("nodes", []):
            self.draw_node(node.get("id"), node_data=node)
        for link in self.graph.get("links", []):
            self.draw_edge(link.get("source"), link.get("target"))

    # ----------------------
    # SocketIO handler
    # ----------------------

    def on_shift_left_press(self, event):
        # Start selection rectangle
        self._select_rect_active = True
        self._select_rect_start = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        self._select_rect_id = self.canvas.create_rectangle(
            self._select_rect_start[0], self._select_rect_start[1],
            self._select_rect_start[0], self._select_rect_start[1],
            outline="gray", dash=(2,2), width=1, tags="select_rect"
        )
    
    def on_shift_left_motion(self, event):
        if (
            not self._select_rect_active or
            self._select_rect_id is None or
            self._select_rect_start is None
        ):
            return
        x0, y0 = self._select_rect_start
        x1, y1 = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.canvas.coords(self._select_rect_id, x0, y0, x1, y1)

    def save_and_exit(self, event=None):
        self._on_close()
                
    def on_shift_left_release(self, event):
        if (
            not self._select_rect_active or
            self._select_rect_id is None or
            self._select_rect_start is None
        ):
            return
        x0, y0 = self._select_rect_start
        x1, y1 = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        x_min, x_max = min(x0, x1), max(x0, x1)
        y_min, y_max = min(y0, y1), max(y0, y1)
        # Select all nodes whose rectangles intersect the selection rectangle
        for node_id, (rect, text) in self.node_widgets.items():
            rx1, ry1, rx2, ry2 = self.canvas.coords(rect)
            # Check for intersection
            if not (rx2 < x_min or rx1 > x_max or ry2 < y_min or ry1 > y_max):
                if node_id not in self.selected_nodes:
                    self.selected_nodes.append(node_id)
                    self.canvas.itemconfig(rect, outline="black", width=1)
        # Remove selection rectangle
        self.canvas.delete(self._select_rect_id)
        self._select_rect_id = None
        self._select_rect_start = None
        self._select_rect_active = False

    # ----------------------
    # Zoom helpers (wheel + slider)
    # ----------------------
    def on_zoom(self, event):
        factor = 1.1 if getattr(event, "delta", 0) > 0 or getattr(event, "num", 0) == 4 else 1 / 1.1
        # Use mouse position for zoom focal point
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
        if abs(new_scale - self.scale) > 1e-9:
            factor = new_scale / self.scale
            self.zoom(factor, from_scroll=True, mouse_pos=(self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2))

    def zoom_in(self):
        self.zoom(1.1, mouse_pos=(self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2))

    def zoom_out(self):
        self.zoom(1 / 1.1, mouse_pos=(self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2))

    def zoom(self, factor, from_scroll=False, mouse_pos=None):
        old_scale = self.scale
        new_scale = self.scale * factor
        new_scale = max(0.1, min(new_scale, 3.0))
        if abs(new_scale - old_scale) < 1e-9:
            return
        self.scale = new_scale
        if not from_scroll:
            try:
                self.zoom_slider.set(self.scale)
            except Exception:
                pass
        # compute new font/edge sizes
        self.current_font_size = max(1, int(self.base_font_size * self.scale))
        # redraw canvas contents at new scale
        self.canvas.delete("all")
        self.node_widgets.clear()
        for node in self.graph.get("nodes", []):
            self.draw_node(node.get("id"), node_data=node)
        for link in self.graph.get("links", []):
            self.draw_edge(link.get("source"), link.get("target"))

    # Selection helper
    def clear_selection(self):
        to_redraw = list(self.selected_nodes)
        self.selected_nodes.clear()
        for nid in to_redraw:
            if nid in self.node_widgets:
                for item in self.node_widgets[nid]:
                    self.canvas.delete(item)
                del self.node_widgets[nid]
            # redraw node to default look
            # try to find node data if available
            nd = next((n for n in self.graph.get("nodes", []) if n.get("id") == nid), None)
            if nd:
                self.draw_node(nid, node_data=nd)

class Gui:
    def __init__(self, url: str):
        self.root = tk.Tk()
        self.app = WorkflowApp(self.root, url)
        try:
            self.app.master.title(f"Workforce - {url}")
        except Exception as e:
            messagebox.showerror("GUI Init Error", f"Failed to initialize GUI for {url}:\n{e}")
        self.root.mainloop()

def main(url: str):
    Gui(url)
