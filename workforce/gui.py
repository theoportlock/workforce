#!/usr/bin/env python3
# Lightweight GUI that talks to the Workforce server for all graph IO and edits.
# - Uses server endpoints: /get-graph, /add-node, /remove-node, /add-edge, /remove-edge,
#   /update-node, /edit-status, /save-graph, /client-connect, /client-disconnect
# - Starts a background server for the Workfile if none is registered.

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

from workforce.utils import load_registry, default_workfile, resolve_port
from workforce.server import start_server

class WorkflowApp:
    def __init__(self, master, filename: str | None = None):
        self.master = master
        self.filename = filename or default_workfile()
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

        self.create_toolbar()
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

        self.terminal_frame = tk.Frame(master)
        self.terminal_text = ScrolledText(self.terminal_frame, height=8, bg="#181818", fg="#e0e0e0")
        self.terminal_text.pack(fill=tk.BOTH, expand=True)
        self.terminal_text.config(state=tk.DISABLED)
        self.terminal_frame.grid(row=2, column=0, sticky="nsew")
        self.terminal_frame.grid_remove()

        # Terminal & prefix/suffix state
        self.prefix = ""
        self.suffix = ""
        self.terminal_visible = False
        self.terminal_height = 180

        # Place terminal_frame (hidden by default)
        self.terminal_frame.grid(row=2, column=0, sticky="nsew")
        self.terminal_frame.grid_remove()

        # Bindings
        self.canvas.bind("<Double-Button-1>", self.on_canvas_double_click)
        self.canvas.bind("<ButtonPress-1>", self.on_left_press)
        self.canvas.bind("<B1-Motion>", self.on_left_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<ButtonPress-3>", self.on_right_press)
        self.canvas.bind("<B3-Motion>", self.on_right_motion)
        self.canvas.bind("<ButtonRelease-3>", self.on_right_release)
        self.master.bind('<Control-s>', lambda e: self.save_to_current_file())
        self.master.bind('r', lambda e: self.run_selected())
        self.master.bind('<Shift-R>', lambda e: self.run_pipeline())
        self.master.bind('<Shift-C>', lambda e: self.clear_all())
        self.master.bind('d', lambda e: self.remove_node())
        self.master.bind('c', lambda e: self.clear_selected_status())
        self.master.bind('e', lambda e: self.connect_nodes())
        self.master.bind('E', lambda e: self.delete_edges_from_selected())
        self.master.bind('p', lambda e: self.prefix_suffix_popup())
        self.master.bind('q', lambda e: self.save_and_exit())
        self.master.bind('o', lambda e: self.open_file())
        self.master.bind('t', lambda e: self.toggle_terminal())
        self.master.bind('<Control-Up>', lambda e: self.zoom_in())
        self.master.bind('<Control-Down>', lambda e: self.zoom_out())

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

        # Recent files
        self.recent_file_path = os.path.join(os.path.expanduser('~'), '.workforce_recent')
        self.recent_files = self.load_recent_files()
        menubar = tk.Menu(self.master)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open", command=self.load_graph, accelerator="O")
        file_menu.add_command(label="Save", command=self.save_graph, accelerator="Ctrl+S")
        self.recent_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="Open Recent", menu=self.recent_menu)
        self.update_recent_menu()
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.save_and_exit, accelerator="Q")
        menubar.add_cascade(label="File", menu=file_menu)

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Add Node", command=self.add_node, accelerator="dbl click canvas")
        edit_menu.add_command(label="Remove Node", command=self.remove_node, accelerator="D")
        edit_menu.add_command(label="Update Node", command=self.update_node, accelerator="dbl click node")
        edit_menu.add_command(label="Connect Nodes", command=self.connect_nodes, accelerator="E")
        edit_menu.add_command(label="Clear Edges", command=self.delete_edges_from_selected, accelerator="Shift+E")
        edit_menu.add_command(label="Clear Status", command=self.clear_all, accelerator="Shift+C")
        menubar.add_cascade(label="Edit", menu=edit_menu)

        # Run menu
        run_menu = tk.Menu(menubar, tearoff=0)
        run_menu.add_command(label="Run Node", command=self.run_selected, accelerator="R")
        run_menu.add_command(label="Run Pipeline", command=self.run_pipeline, accelerator="Shift+R")
        menubar.add_cascade(label="Run", menu=run_menu)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Prefix/Suffix", command=self.prefix_suffix_popup, accelerator="P")
        tools_menu.add_command(label="Show/Hide Terminal", command=self.toggle_terminal, accelerator="T")
        menubar.add_cascade(label="Tools", menu=tools_menu)

        self.master.config(menu=menubar)

        # Ensure server for file and load
        if self.filename:
            try:
                self._ensure_server_for_file(self.filename)
            except Exception as e:
                print(f"[Warning] server ensure failed: {e}")
        # Try connect socketio and notify server
        self._start_socketio()
        self._client_connect()
        self._reload_graph()

        self.master.after_idle(self.try_load_workfile)

        # cleanup on exit
        atexit.register(self._atexit_disconnect)
        self.master.protocol("WM_DELETE_WINDOW", self._on_close)


    def _ensure_server_for_file(self, filename: str, timeout: float = 6.0):
        abs_path = os.path.abspath(filename)
        reg = load_registry()
        if abs_path in reg:
            port = reg[abs_path]["port"]
            self.base_url = f"http://127.0.0.1:{port}"
            return
        # start background server
        start_server(abs_path, background=True)
        # wait until registry updated and responsive
        start = time.time()
        while time.time() - start < timeout:
            reg = load_registry()
            if abs_path in reg:
                port = reg[abs_path]["port"]
                self.base_url = f"http://127.0.0.1:{port}"
                # quick probe
                try:
                    r = requests.get(self._url("/get-graph"), timeout=1.0)
                    if r.status_code == 200:
                        return
                except Exception:
                    pass
            time.sleep(0.2)
        raise RuntimeError(f"Server for '{filename}' not available after {timeout}s")

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def _start_socketio(self):
        if self.sio is not None:
            return
        try:
            self.sio = socketio.Client()
            self.sio.on('graph_update', self.on_graph_update)
            # connect (use base_url)
            # socketio wants ws/http root (no path)
            self.sio.connect(self.base_url, wait_timeout=1)
        except Exception as e:
            # non-fatal; fallback to polling
            print(f"[Warning] SocketIO connect failed: {e}")
            self.sio = None

    def _client_connect(self):
        if self.client_connected or not self.base_url:
            return
        try:
            r = requests.post(self._url("/client-connect"), timeout=1.0)
            if r.status_code == 200:
                self.client_connected = True
        except Exception:
            pass

    def _client_disconnect(self):
        if not self.client_connected or not self.base_url:
            return
        try:
            requests.post(self._url("/client-disconnect"), timeout=1.0)
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
        if not self.filename:
            self.graph = {"nodes": [], "links": []}
            return
        try:
            # ensure we have base_url for this file
            # try resolve_port to set base_url if possible
            try:
                abs_path, port = resolve_port(self.filename)
                self.base_url = f"http://127.0.0.1:{port}"
            except SystemExit:
                # resolve_port may call sys.exit; ignore
                pass
            r = requests.get(self._url("/get-graph"), timeout=2.0)
            r.raise_for_status()
            self.graph = r.json() or {"nodes": [], "links": []}
        except Exception:
            # fallback: if the file exists, read GraphML locally for display only
            try:
                import networkx as nx
                if os.path.exists(self.filename):
                    G = nx.read_graphml(self.filename)
                    from networkx.readwrite import json_graph
                    self.graph = json_graph.node_link_data(G)
                else:
                    self.graph = {"nodes": [], "links": []}
            except Exception:
                self.graph = {"nodes": [], "links": []}

        # redrawing must be done on the Tk main thread
        self.master.after(0, self._redraw_graph)

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
    def save_to_current_file(self):
        """Ask the server to persist the current graph for the active file (no-op if server saved)."""
        if not self.filename:
            return
        try:
            requests.post(self._url("/save-graph"), timeout=1.0)
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
                requests.post(self._url("/add-node"), json=payload, timeout=2.0).raise_for_status()
                # self._reload_graph() # Wait for graph_update event
            except Exception as e:
                messagebox.showerror("Add node failed", str(e))
        if label:
            on_save(label)
        else:
            self.node_label_popup("", on_save)

    def update_node_position(self, node_id: str, x: float, y: float):
        url = self._url("/edit-node-position")
        try:
            requests.post(url, json={
                "node_id": node_id,
                "x": x,
                "y": y
            }, timeout=2.0)
        except Exception as e:
            print(f"Failed to update node position for {node_id}: {e}")

    def add_node(self):
        def on_save(label):
            if not label.strip():
                return
            count = len(self.graph.get("nodes", []))
            x = 100 + count * 50
            y = 100
            try:
                requests.post(self._url("/add-node"), json={"label": label, "x": x, "y": y}, timeout=2.0).raise_for_status()
                # self._reload_graph() # Wait for graph_update event
            except Exception as e:
                messagebox.showerror("Add node error", str(e))
        self.node_label_popup("", on_save)

    def remove_node(self):
        for nid in list(self.selected_nodes):
            try:
                requests.post(self._url("/remove-node"), json={"node_id": nid}, timeout=2.0)
            except Exception as e:
                print(f"remove_node error: {e}")
        self.selected_nodes.clear()
        # self._reload_graph() # Wait for graph_update event

    def connect_nodes(self):
        if len(self.selected_nodes) < 2:
            return
        for i in range(len(self.selected_nodes) - 1):
            src = self.selected_nodes[i]
            tgt = self.selected_nodes[i + 1]
            try:
                requests.post(self._url("/add-edge"), json={"source": src, "target": tgt}, timeout=2.0)
            except Exception as e:
                print(f"add-edge error: {e}")
        # self._reload_graph() # Wait for graph_update event

    def delete_edges_from_selected(self):
        links = list(self.graph.get("links", []))
        for l in links:
            if l.get("source") in self.selected_nodes or l.get("target") in self.selected_nodes:
                try:
                    requests.post(self._url("/remove-edge"), json={"source": l.get("source"), "target": l.get("target")}, timeout=2.0)
                except Exception as e:
                    print(f"remove-edge error: {e}")
        # self._reload_graph() # Wait for graph_update event

    def edit_node_label(self, node_id):
        current = ""
        for n in self.graph.get("nodes", []):
            if n.get("id") == node_id:
                current = n.get("label", "")
                break

        def on_save(new_label):
            try:
                requests.post(self._url("/update-node"), json={"id": node_id, "label": new_label}, timeout=2.0)
                # self._reload_graph() # Wait for graph_update event
            except Exception as e:
                messagebox.showerror("Update error", str(e))

        self.node_label_popup(current, on_save)

    def update_node(self):
        if len(self.selected_nodes) != 1:
            return
        node_id = self.selected_nodes[0]
        new_label = simpledialog.askstring("Update Node", "New label/command:")
        if new_label:
            try:
                requests.post(self._url("/update-node"), json={"id": node_id, "label": new_label}, timeout=2.0)
                # self._reload_graph() # Wait for graph_update event
            except Exception as e:
                messagebox.showerror("Update error", str(e))
    
    def run_selected(self):
        if self.filename:
            for node_id in self.selected_nodes:
                self.run_in_terminal([
                    sys.executable, "-m", "workforce", "run", "node", self.filename, node_id,
                    "--prefix", self.prefix, "--suffix", self.suffix
                ], title=f"Run Node: {node_id}")
    
    def run_pipeline(self):
        if self.filename:
            self.run_in_terminal([
                sys.executable, "-m", "workforce", "run", self.filename,
                "--prefix", self.prefix, "--suffix", self.suffix
            ], title="Run Pipeline")

    def clear_selected_status(self):
        for nid in list(self.selected_nodes):
            try:
                requests.post(self._url("/edit-status"), json={"element_type": "node", "element_id": nid, "value": ""}, timeout=2.0)
            except Exception:
                pass
        # self._reload_graph() # Wait for graph_update event

    def clear_all(self):
        for n in self.graph.get("nodes", []):
            try:
                requests.post(self._url("/edit-status"), json={"element_type": "node", "element_id": n.get("id"), "value": ""}, timeout=2.0)
            except Exception:
                pass
        for l in self.graph.get("links", []):
            eid = l.get("id")
            if eid:
                try:
                    requests.post(self._url("/edit-status"), json={"element_type": "edge", "element_id": eid, "value": ""}, timeout=2.0)
                except Exception:
                    pass
        # self._reload_graph() # Wait for graph_update event
    
    def toggle_terminal(self):
        if self.terminal_visible:
            self.terminal_frame.grid_remove()
            self.terminal_visible = False
        else:
            self.terminal_frame.grid(row=2, column=0, sticky="nsew")
            self.terminal_visible = True
    
    def terminal_write(self, text):
        self.terminal_text.config(state=tk.NORMAL)
        self.terminal_text.insert(tk.END, text)
        self.terminal_text.see(tk.END)
        self.terminal_text.config(state=tk.DISABLED)

    def prefix_suffix_popup(self):
        editor = tk.Toplevel(self.master)
        editor.title("Prefix/Suffix")
        editor.geometry("800x300")
        editor.minsize(800, 380)

        frame = tk.Frame(editor)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Prefix
        prefix_label = tk.Label(frame, text="Prefix:")
        prefix_label.grid(row=0, column=0, sticky="w")
        prefix_text = tk.Text(frame, wrap='word', font=("TkDefaultFont", 10), height=4)
        prefix_text.grid(row=1, column=0, sticky="nsew", padx=(0,10))
        prefix_text.insert("1.0", self.prefix)

        # Suffix
        suffix_label = tk.Label(frame, text="Suffix:")
        suffix_label.grid(row=0, column=1, sticky="w")
        suffix_text = tk.Text(frame, wrap='word', font=("TkDefaultFont", 10), height=4)
        suffix_text.grid(row=1, column=1, sticky="nsew")
        suffix_text.insert("1.0", self.suffix)

        # Allow the text areas to expand
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(1, weight=1)

        def save_and_close(event=None):
            self.prefix = prefix_text.get("1.0", "end-1c")
            self.suffix = suffix_text.get("1.0", "end-1c")
            editor.destroy()

        def cancel_and_close(event=None):
            editor.destroy()

        btn_frame = tk.Frame(editor)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0,10))
        save_btn = tk.Button(btn_frame, text="Save", command=save_and_close)
        save_btn.pack(side=tk.LEFT, padx=5)
        cancel_btn = tk.Button(btn_frame, text="Cancel", command=cancel_and_close)
        cancel_btn.pack(side=tk.LEFT, padx=5)

        # Keyboard shortcuts
        editor.bind('<Escape>', cancel_and_close)
        editor.bind('<Control-Return>', save_and_close)
        editor.bind('<Control-KP_Enter>', save_and_close)

        editor.transient(self.master)
        editor.grab_set()
        prefix_text.focus_set()

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
                requests.post(self._url("/add-edge"), json={"source": self._edge_start, "target": target}, timeout=2.0)
            except Exception as e:
                print(f"add-edge error: {e}")

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

    # ----------------------
    # SocketIO handler
    # ----------------------
    def on_graph_update(self, data=None):
        """
        Called from background SocketIO thread — must not touch Tkinter directly.
        Receives graph data from the server and schedules a redraw on the main UI thread.
        """
        print("[SocketIO] Graph update event received.")
        if data:
            # Replace local graph object
            self.graph = data
            # Schedule UI update on Tkinter's main thread
            self.master.after(0, self._redraw_graph)

    # ----------------------
    # Toolbar / menus / small helpers
    # ----------------------
    def create_toolbar(self):
        self.recent_file_path = os.path.join(os.path.expanduser('~'), '.workforce_recent')
        self.recent_files = self.load_recent_files()
        menubar = tk.Menu(self.master)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open", command=self.load_graph, accelerator="O")
        file_menu.add_command(label="Save", command=self.save_graph, accelerator="Ctrl+S")
        self.recent_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="Open Recent", menu=self.recent_menu)
        self.update_recent_menu()
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.save_and_exit, accelerator="Q")
        menubar.add_cascade(label="File", menu=file_menu)

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Add Node", command=self.add_node, accelerator="dbl click canvas")
        edit_menu.add_command(label="Remove Node", command=self.remove_node, accelerator="D")
        edit_menu.add_command(label="Update Node", command=self.update_node, accelerator="dbl click node")
        edit_menu.add_command(label="Connect Nodes", command=self.connect_nodes, accelerator="E")
        edit_menu.add_command(label="Clear Edges", command=self.delete_edges_from_selected, accelerator="Shift+E")
        edit_menu.add_command(label="Clear Status", command=self.clear_all, accelerator="Shift+C")
        menubar.add_cascade(label="Edit", menu=edit_menu)

        # Run menu
        run_menu = tk.Menu(menubar, tearoff=0)
        run_menu.add_command(label="Run Node", command=self.run_selected, accelerator="R")
        run_menu.add_command(label="Run Pipeline", command=self.run_pipeline, accelerator="Shift+R")
        menubar.add_cascade(label="Run", menu=run_menu)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Prefix/Suffix", command=self.prefix_suffix_popup, accelerator="P")
        tools_menu.add_command(label="Show/Hide Terminal", command=self.toggle_terminal, accelerator="T")
        menubar.add_cascade(label="Tools", menu=tools_menu)

        self.master.config(menu=menubar)

    # Recent files helpers
    def load_recent_files(self):
        try:
            with open(self.recent_file_path, "r") as f:
                files = [line.strip() for line in f if line.strip() and os.path.exists(line.strip())]
            return files
        except Exception:
            return []

    def save_recent_files(self):
        try:
            with open(self.recent_file_path, "w") as f:
                for p in self.recent_files:
                    f.write(p + "\n")
        except Exception:
            pass

    def add_recent_file(self, filename):
        if not filename:
            return
        if filename in self.recent_files:
            self.recent_files.remove(filename)
        self.recent_files.insert(0, filename)
        if len(self.recent_files) > 10:
            self.recent_files = self.recent_files[:10]
        self.save_recent_files()
        self.update_recent_menu()

    def update_recent_menu(self):
        try:
            self.recent_menu.delete(0, tk.END)
            if not self.recent_files:
                self.recent_menu.add_command(label="(No recent files)", state=tk.DISABLED)
            else:
                for f in self.recent_files:
                    self.recent_menu.add_command(label=f, command=lambda fn=f: self.open_recent_file(fn))
        except Exception:
            pass

    def open_recent_file(self, filename):
        # change cwd to file's directory (as in new code)
        base_dir = os.path.dirname(os.path.abspath(filename))
        try:
            os.chdir(base_dir)
        except Exception:
            pass
        self.filename = filename
        try:
            self._ensure_server_for_file(self.filename)
        except Exception:
            pass
        try:
            self._reload_graph()
        except Exception:
            pass
        self.master.title(f"Workforce - {os.path.basename(filename)}")
        self.add_recent_file(filename)

    def open_file(self):
        fn = filedialog.askopenfilename()
        if fn:
            self.filename = fn
            try:
                self._ensure_server_for_file(self.filename)
            except Exception:
                pass
            self.add_recent_file(fn)
            self._reload_graph()

    def load_graph(self):
        # wrapper that mirrors previous "open_file" behavior but named load_graph for toolbar compatibility
        fn = filedialog.askopenfilename()
        if fn:
            self.filename = fn
            try:
                self._ensure_server_for_file(self.filename)
            except Exception:
                pass
            self.add_recent_file(fn)
            self._reload_graph()

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

    # Save as prompt (sets filename then delegates to save_to_current_file)
    def save_graph(self):
        initialfile = None
        if not self.filename:
            initialfile = "Workfile"
        filename = filedialog.asksaveasfilename(initialfile=initialfile)
        if filename:
            self.filename = filename
            self.master.title(f"Workforce - {os.path.basename(filename)}")
            self.add_recent_file(filename)
    
    def save_and_exit(self, event=None):
        self.master.quit()
                
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
    # Replace run_in_terminal to ensure subprocess is imported locally
    def run_in_terminal(self, cmd, title=None):
        """Run command in background and stream stdout -> terminal panel."""
        import queue
        import subprocess
        q = queue.Queue()

        if title:
            self.terminal_write(f"\n=== {title} ===\n")
        else:
            self.terminal_write(f"\n$ {' '.join(cmd)}\n")

        def _reader():
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                for line in proc.stdout:
                    q.put(line)
                proc.wait()
            except Exception as e:
                q.put(f"\n[Error running command: {e}]\n")
        threading.Thread(target=_reader, daemon=True).start()

        def _poll():
            try:
                while True:
                    line = q.get_nowait()
                    self.terminal_write(line)
            except Exception:
                pass
            # continue polling while threads exist
            if threading.active_count() > 1 or not q.empty():
                self.master.after(50, _poll)
        # ensure terminal visible
        if not self.terminal_visible:
            self.toggle_terminal()
        _poll()

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

    # Workfile auto-load
    def try_load_workfile(self):
        default_file = default_workfile()
        if os.path.exists(default_file) and not self.filename:
            self.filename = os.path.abspath(default_file)
            try:
                self._ensure_server_for_file(self.filename)
                self._reload_graph()
                self.master.title(f"Workforce - {self.filename}")
            except Exception:
                pass

class Gui:
    def __init__(self, filename=None):
        self.root = tk.Tk()
        self.app = WorkflowApp(self.root)
        if filename:
            self.app.filename = filename
            try:
                self.app._reload_graph()
                self.app.master.title(f"Workforce - {filename}")
            except Exception as e:
                messagebox.showerror("Load Error", f"Failed to load {filename}:\n{e}")
        self.root.mainloop()

def main(args):
    Gui(args.filename)
