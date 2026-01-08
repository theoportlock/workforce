import logging
import os
import threading
import tkinter as tk
from tkinter import messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
import requests
import atexit

from workforce import utils
from .state import GUIState
from .client import ServerClient
from .canvas import GraphCanvas
from .recent import RecentFileManager

log = logging.getLogger(__name__)


class WorkflowApp:
    def __init__(self, master, base_url: str, wf_path: str = None, workspace_id: str = None):
        self.master = master
        # Single source of truth for UI state
        self.state = GUIState()
        self.base_url = base_url
        self.wf_path = wf_path
        self.workspace_id = workspace_id

        # UI layout
        self.master.title(f"Workforce - {wf_path}" if wf_path else "Workforce")

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
        self.server = ServerClient(self.base_url, workspace_id=workspace_id, workfile_path=wf_path, on_graph_update=self.on_graph_update)
        self.client_connected = False

        # Initialize recent files manager
        self.recent_manager = RecentFileManager()
        
        # Add current workfile to recent list on startup
        if wf_path:
            self.recent_manager.add(wf_path)

        menubar = tk.Menu(self.master)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open...", command=self.open_file_dialog, accelerator="O")
        # Recent files submenu (populated dynamically)
        self.recent_submenu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="Open Recent", menu=self.recent_submenu)
        file_menu.add_separator()
        file_menu.add_command(label="Save As...", command=self.save_as_dialog, accelerator="Ctrl+Shift+S")
        file_menu.add_command(label="Exit", command=self.master.quit, accelerator="Q")
        menubar.add_cascade(label="File", menu=file_menu)
        # Set postcommand to rebuild recent submenu on each File menu open
        file_menu.config(postcommand=self._rebuild_recent_submenu)
        # Populate initial state (will also be called on each File menu open via postcommand)
        self._rebuild_recent_submenu()

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Add Node", command=self.add_node, accelerator="dbl click canvas")
        edit_menu.add_command(label="Remove Node", command=self.remove_node, accelerator="D/Del/⌫")
        edit_menu.add_command(label="Connect Nodes", command=self.connect_nodes, accelerator="E")
        edit_menu.add_command(label="Clear Edges", command=self.delete_edges_from_selected, accelerator="Shift+E")
        edit_menu.add_command(label="Clear Status", command=self.clear_all, accelerator="Shift+C")
        menubar.add_cascade(label="Edit", menu=edit_menu)

        # Run menu
        run_menu = tk.Menu(menubar, tearoff=0)
        run_menu.add_command(label="Run", command=self.run, accelerator="r")
        run_menu.add_command(label="View Log", command=self.show_node_log, accelerator="S")
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
        self.master.bind('q', lambda e: self.save_and_exit())
        self.master.bind('r', lambda e: self.run())
        self.master.bind('<Shift-C>', lambda e: self.clear_all())
        self.master.bind('d', lambda e: self.remove_node())
        self.master.bind('<Delete>', lambda e: self.remove_node())
        self.master.bind('<BackSpace>', lambda e: self.remove_node())
        self.master.bind('c', lambda e: self.clear_selected_status())
        self.master.bind('e', lambda e: self.connect_nodes())
        self.master.bind('E', lambda e: self.delete_edges_from_selected())
        self.master.bind('w', lambda e: self.wrapper_popup())
        self.master.bind('s', lambda e: self.show_node_log())
        self.master.bind('o', lambda e: self.open_file_dialog())
        self.master.bind('<Control-s>', lambda e: self._save_graph_on_server())
        self.master.bind('<Control-Shift-S>', lambda e: self.save_as_dialog())
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

        # ephemeral pan-drag state
        self._pan_start = (0.0, 0.0)

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
        """Disconnect from server workspace and clean up."""
        if not self.base_url:
            log.debug("Not disconnecting: no base_url")
            return
        
        try:
            log.info(f"Disconnecting client from workspace {self.workspace_id}")
            # Always attempt to disconnect, regardless of client_connected flag
            # (flag might not be set if connection failed initially)
            self.server.client_disconnect()
            log.info(f"Successfully disconnected from workspace {self.workspace_id}")
        except Exception as e:
            log.error(f"Error disconnecting: {e}")
        finally:
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
            try:
                # `x`/`y` are world coordinates.
                self.server.add_node(lbl, x, y)
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
            count = len(self.state.graph.get("nodes", []))
            x = 100 + count * 50
            y = 100
            try:
                self.server.add_node(label, x, y)
            except Exception as e:
                messagebox.showerror("Add node error", str(e))
        self.node_label_popup("", on_save)

    def remove_node(self):
        for nid in list(self.state.selected_nodes):
            try:
                self.server.remove_node(nid)
            except Exception as e:
                log.error(f"remove_node failed for {nid}: {e}")
        self.state.selected_nodes.clear()

    def connect_nodes(self):
        if len(self.state.selected_nodes) < 2:
            return
        for i in range(len(self.state.selected_nodes) - 1):
            src = self.state.selected_nodes[i]
            tgt = self.state.selected_nodes[i + 1]
            try:
                self.server.add_edge(src, tgt)
            except Exception as e:
                log.error(f"add-edge failed for {src}->{tgt}: {e}")

    def delete_edges_from_selected(self):
        links = list(self.state.graph.get("links", []))
        for link in links:
            if (link.get("source") in self.state.selected_nodes or
                    link.get("target") in self.state.selected_nodes):
                try:
                    self.server.remove_edge(link.get("source"), link.get("target"))
                except Exception as e:
                    log.error(f"remove-edge failed for {link.get('source')}->{link.get('target')}: {e}")

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
                log.info(f"Saving node label: node_id={node_id}, new_label={new_label}, base_url={self.base_url}")
                utils._post(self.base_url, "/edit-node-label", {"node_id": node_id, "label": new_label})
                log.info(f"Node label update request sent successfully")
            except Exception as e:
                log.exception(f"Failed to update node label: {e}")
                messagebox.showerror("Update error", str(e))

        self.node_label_popup(current_label, on_save)
        return "break"

    def node_label_popup(self, initial_value, on_save):
        editor = tk.Toplevel(self.master)
        editor.title("Node Label")
        editor.geometry("600x300")
        editor.minsize(600, 300)
        text_widget = tk.Text(editor, wrap='word', font=("TkDefaultFont", 10), height=6)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))
        text_widget.insert("1.0", initial_value)

        def save_and_close(event=None):
            new_label = text_widget.get("1.0", "end-1c")
            on_save(new_label)
            editor.destroy()

        def cancel_and_close(event=None):
            editor.destroy()

        btn_frame = tk.Frame(editor)
        btn_frame.pack(fill=tk.X, padx=10, pady=(5, 10))
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
        btn_frame.pack(fill=tk.X, padx=10, pady=(5, 10))
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

    def save_as_dialog(self):
        """Prompt user for new filename and switch to new workspace."""
        if not self.wf_path:
            messagebox.showerror("Save As Error", "No workflow file is currently open.")
            return
        
        # Determine initial directory and filename
        initial_dir = os.path.dirname(self.wf_path) if self.wf_path else os.getcwd()
        initial_file = os.path.basename(self.wf_path) if self.wf_path else "Workfile.wf"
        
        new_path = filedialog.asksaveasfilename(
            initialdir=initial_dir,
            initialfile=initial_file,
            title="Save Workflow As",
            filetypes=[("Workflow files", "*.wf"), ("All files", "*.*")],
            defaultextension=".wf"
        )
        
        if not new_path:
            return  # User cancelled
        
        try:
            # Call server to save graph to new file
            result = self.server.save_as(new_path)
            
            # Check if result is a dict (success) or if we got an error
            if isinstance(result, dict) and "error" in result:
                if "Cannot save during active workflow execution" in result.get("error", ""):
                    messagebox.showerror(
                        "Save As Blocked",
                        "Cannot save while workflow is running. Please wait for completion."
                    )
                else:
                    messagebox.showerror("Save As Error", f"Failed to save workflow:\n{result['error']}")
                return
            
            # Disconnect from old workspace
            self._client_disconnect()
            
            # Update to new workspace
            self.wf_path = result["new_path"]
            self.workspace_id = result["new_workspace_id"]
            self.base_url = result["new_base_url"]
            
            # Create new server client for new workspace
            self.server = ServerClient(
                self.base_url,
                workspace_id=self.workspace_id,
                workfile_path=self.wf_path,
                on_graph_update=self.on_graph_update
            )
            
            # Connect to new workspace
            self._client_connect()
            self._reload_graph()
            
            # Update window title
            self.master.title(f"Workforce - {self.wf_path}")
            
            messagebox.showinfo("Save As", f"Workflow saved to:\n{new_path}")
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 409:
                messagebox.showerror(
                    "Save As Blocked",
                    "Cannot save while workflow is running. Please wait for completion."
                )
            else:
                messagebox.showerror("Save As Error", f"Failed to save workflow:\n{e}")
        except Exception as e:
            messagebox.showerror("Save As Error", f"Failed to save workflow:\n{e}")

    def open_file_dialog(self):
        """
        Show file picker dialog to open a workflow file.
        Opens selected file in a new GUI/workspace and updates recent list.
        """
        # Determine initial directory
        initial_dir = os.path.dirname(self.wf_path) if self.wf_path else os.path.expanduser("~")
        
        file_path = filedialog.askopenfilename(
            initialdir=initial_dir,
            title="Open Workflow",
            filetypes=[("All files", "*"), ("Workflow files", "*.wf"), ("GraphML files", "*.graphml")],
        )
        
        if not file_path:
            return  # User cancelled
        
        # Convert to absolute path
        abs_path = os.path.abspath(file_path)
        
        # Update recent list
        self.recent_manager.add(abs_path)
        
        # Launch new GUI for this file in background
        self._launch_gui_for_file(abs_path)
    
    def _launch_gui_for_file(self, file_path: str):
        """
        Launch a new GUI instance for the given file path.
        
        Args:
            file_path: Absolute path to workflow file.
        """
        try:
            # Import launch from gui/app.py to spawn new process
            from .app import launch
            
            # Compute workspace ID and URL for the file
            workspace_id = utils.compute_workspace_id(file_path)
            base_url = utils.get_workspace_url(workspace_id)
            
            # Launch in background
            launch(base_url, wf_path=file_path, workspace_id=workspace_id, background=True)
        except Exception as e:
            messagebox.showerror("Launch Error", f"Failed to launch GUI for file:\n{e}")
    
    def _rebuild_recent_submenu(self):
        """
        Rebuild the File → Open Recent submenu.
        Called as postcommand on File menu to refresh on each open.
        Validates paths exist and removes missing entries.
        """
        # Clear existing items
        self.recent_submenu.delete(0, tk.END)
        
        # Get validated recent files list
        recent_files = self.recent_manager.get_list()
        
        if not recent_files:
            self.recent_submenu.add_command(label="(No recent files)", state=tk.DISABLED)
            return
        
        # Add each recent file to submenu
        for file_path in recent_files[:20]:  # Limit display to 20
            # Create menu item with full file path as label
            self.recent_submenu.add_command(
                label=file_path,
                command=lambda fp=file_path: self._open_recent_file(fp)
            )
    
    def _open_recent_file(self, file_path: str):
        """
        Open a file from recent list.
        Moves file to top of recent list and launches new GUI.
        
        Args:
            file_path: Path to file to open.
        """
        # Verify file still exists
        if not os.path.isfile(file_path):
            messagebox.showwarning(
                "File Not Found",
                f"The file no longer exists:\n{file_path}\n\nIt will be removed from recent list."
            )
            self.recent_manager.remove(file_path)
            self._rebuild_recent_submenu()
            return
        
        # Move to top of recent list
        self.recent_manager.move_to_top(file_path)
        
        # Launch new GUI for this file
        self._launch_gui_for_file(file_path)

    def show_node_log(self):
        if len(self.state.selected_nodes) != 1:
            messagebox.showinfo("Show Log", "Please select exactly one node to view its log.")
            return
        node_id = self.state.selected_nodes[0]
        node_data = next((n for n in self.state.graph.get("nodes", []) if n.get("id") == node_id), None)
        if not node_data:
            return
        node_label = node_data.get("label", node_id)
        log_window = tk.Toplevel(self.master)
        log_window.title(f"Log for: {node_label}")
        log_window.geometry("800x600")
        log_window.minsize(400, 200)
        log_window.bind('<Escape>', lambda e: log_window.destroy())
        log_window.bind('s', lambda e: log_window.destroy())
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
    def run(self):
        """Run workflow from selected nodes or from roots if none selected."""
        try:
            nodes = list(self.state.selected_nodes) if self.state.selected_nodes else None

            # Spawn a runner client in a background thread to execute nodes
            def spawn_runner():
                try:
                    from workforce.run.client import Runner
                    wrapper = self.state.wrapper or "{}"
                    log.info(f"GUI spawning runner with base_url={self.base_url}, workspace_id={self.workspace_id}, nodes={nodes}")
                    runner = Runner(self.base_url, workspace_id=self.workspace_id, workfile_path=self.wf_path, wrapper=wrapper)
                    runner.start(initial_nodes=nodes)
                except Exception as e:
                    log.exception(f"Error in spawn_runner: {e}")
                    raise

            thread = threading.Thread(target=spawn_runner, daemon=False)
            thread.start()

        except Exception as e:
            log.exception(f"Run Error: {e}")
            messagebox.showerror("Run Error", f"Failed to trigger run: {e}")

    def clear_selected_status(self):
        for nid in list(self.state.selected_nodes):
            try:
                utils._post(
                    self.base_url,
                    "/edit-status",
                    {"element_type": "node", "element_id": nid, "value": ""}
                )
            except Exception:
                pass

    def clear_all(self):
        for n in self.state.graph.get("nodes", []):
            try:
                utils._post(
                    self.base_url,
                    "/edit-status",
                    {"element_type": "node", "element_id": n.get("id"), "value": ""}
                )
            except Exception:
                pass
        for link in self.state.graph.get("links", []):
            eid = link.get("id")
            if eid:
                try:
                    utils._post(
                        self.base_url,
                        "/edit-status",
                        {"element_type": "edge", "element_id": eid, "value": ""}
                    )
                except Exception:
                    pass
        # Server will emit graph_update via SocketIO, no need to fetch here

    # ----------------------
    # Geometry helpers (delegate to canvas_view)
    # ----------------------
    def _screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        """Convert from screen/canvas coordinates to world coordinates.

        We store `pan_x/pan_y` in screen-space units (pixels). With:
            screen = world * scale + pan
        the inverse is:
            world = (screen - pan) / scale
        """
        return ((sx - self.state.pan_x) / self.state.scale, (sy - self.state.pan_y) / self.state.scale)

    def _world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        """Convert from world coordinates to screen/canvas coordinates."""
        return (wx * self.state.scale + self.state.pan_x, wy * self.state.scale + self.state.pan_y)

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
        x, y = self._screen_to_world(event.x, event.y)
        # Hit-test at the click location (screen/canvas coords).
        items = self.canvas.find_overlapping(event.x, event.y, event.x, event.y)
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
                    node_data = next(
                        n for n in self.state.graph["nodes"] if n.get("id") == node_id
                    )
                    self.canvas_view.draw_node(node_id, node_data=node_data)
                    self.on_node_press(event, node_id)
                break
        if not node_clicked:
            self.state._potential_deselect = True
            self.state._press_x = event.x
            self.state._press_y = event.y
            self.state.dragging_node = None
            self.state._panning = True
            self._pan_start = (float(self.state.pan_x), float(self.state.pan_y))
        else:
            self.state._panning = False

    def on_left_motion(self, event):
        if self.state.dragging_node:
            self.on_node_drag(event, self.state.dragging_node)
        else:
            if getattr(self.state, '_panning', False):
                dx = event.x - self.state._press_x
                dy = event.y - self.state._press_y
                if abs(dx) > 5 or abs(dy) > 5:
                    self.state._potential_deselect = False
                self.state.pan_x = self._pan_start[0] + dx
                self.state.pan_y = self._pan_start[1] + dy
                self.canvas_view.redraw(self.state.graph)

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
        node_data = next(
            (n for n in self.state.graph.get("nodes", []) if n.get("id") == node_id),
            {}
        )
        selected = node_id in self.state.selected_nodes
        self.canvas_view.draw_node(node_id, node_data=node_data, selected=selected)

    # right-click drag to create edge
    def on_right_press(self, event):
        item = self.canvas.find_withtag(tk.CURRENT)
        for nid, (rect, txt) in self.canvas_view.node_widgets.items():
            if item and item[0] in (rect, txt):
                self.state.edge_start = nid
                coords = self.canvas.coords(rect)
                cx = (coords[0] + coords[2]) / 2
                cy = (coords[1] + coords[3]) / 2
                self._edge_line = self.canvas.create_line(
                    cx, cy, cx, cy, dash=(3, 2), fill="gray"
                )
                return
        self.state.edge_start = None

    def on_right_motion(self, event):
        if getattr(self, "_edge_line", None):
            coords = self.canvas.coords(self._edge_line)
            self.canvas.coords(
                self._edge_line,
                coords[0],
                coords[1],
                event.x,
                event.y
            )

    def on_right_release(self, event):
        if not getattr(self, "_edge_line", None):
            return
        # Hit-test target node using screen/canvas coordinates.
        x = event.x
        y = event.y
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
        new_x, new_y = self._screen_to_world(event.x - dx, event.y - dy)
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
        world_x, world_y = self._screen_to_world(event.x, event.y)
        self.state._select_rect_start = (world_x, world_y)
        screen_x, screen_y = self._world_to_screen(world_x, world_y)
        self.state._select_rect_id = self.canvas.create_rectangle(
            screen_x,
            screen_y,
            screen_x,
            screen_y,
            outline="gray",
            dash=(2, 2),
            width=1,
            tags="select_rect"
        )

    def on_shift_left_motion(self, event):
        if (not self.state._select_rect_active or
                self.state._select_rect_id is None or
                self.state._select_rect_start is None):
            return
        world_x0, world_y0 = self.state._select_rect_start
        world_x1, world_y1 = self._screen_to_world(event.x, event.y)
        screen_x0, screen_y0 = self._world_to_screen(world_x0, world_y0)
        screen_x1, screen_y1 = self._world_to_screen(world_x1, world_y1)
        self.canvas.coords(self.state._select_rect_id, screen_x0, screen_y0, screen_x1, screen_y1)

    def on_shift_left_release(self, event):
        if (not self.state._select_rect_active or
                self.state._select_rect_id is None or
                self.state._select_rect_start is None):
            return
        world_x0, world_y0 = self.state._select_rect_start
        world_x1, world_y1 = self._screen_to_world(event.x, event.y)
        x_min, y_min = self._world_to_screen(min(world_x0, world_x1), min(world_y0, world_y1))
        x_max, y_max = self._world_to_screen(max(world_x0, world_x1), max(world_y0, world_y1))
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
        delta = getattr(event, "delta", 0)
        num = getattr(event, "num", 0)
        factor = 1.1 if delta > 0 or num == 4 else 1 / 1.1
        try:
            mouse_pos = (event.x, event.y)
        except Exception:
            mouse_pos = (
                self.canvas.winfo_width() / 2,
                self.canvas.winfo_height() / 2
            )
        self.zoom(factor, mouse_pos=mouse_pos)

    def on_zoom_scroll(self, value):
        try:
            new_scale = float(value)
        except Exception:
            return
        if abs(new_scale - self.state.scale) > 1e-9:
            factor = new_scale / self.state.scale
            mouse_pos = (
                self.canvas.winfo_width() / 2,
                self.canvas.winfo_height() / 2
            )
            self.zoom(factor, from_scroll=True, mouse_pos=mouse_pos)

    def zoom_in(self):
        mouse_pos = (
            self.canvas.winfo_width() / 2,
            self.canvas.winfo_height() / 2
        )
        self.zoom(1.1, mouse_pos=mouse_pos)

    def zoom_out(self):
        mouse_pos = (
            self.canvas.winfo_width() / 2,
            self.canvas.winfo_height() / 2
        )
        self.zoom(1 / 1.1, mouse_pos=mouse_pos)

    def zoom(self, factor, from_scroll=False, mouse_pos=None):
        old_scale = self.state.scale
        new_scale = self.state.scale * factor
        new_scale = max(0.1, min(new_scale, 3.0))
        if abs(new_scale - old_scale) < 1e-9:
            return
        
        # Calculate scale ratio for pan adjustment
        scale_ratio = new_scale / old_scale
        
        # Center-anchored zoom: adjust pan so the canvas center stays fixed.
        center_x = self.canvas.winfo_width() / 2
        center_y = self.canvas.winfo_height() / 2
        # Formula: new_pan = center - (center - old_pan) * scale_ratio
        self.state.pan_x = center_x - (center_x - self.state.pan_x) * scale_ratio
        self.state.pan_y = center_y - (center_y - self.state.pan_y) * scale_ratio
        
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
        # Middle-click (Button-2) on a node selects it (legacy behavior).
        self.clear_selection()
        self.state.selected_nodes.append(node_id)
        nd = next((n for n in self.state.graph.get("nodes", []) if n.get("id") == node_id), None)
        if nd:
            if node_id in self.canvas_view.node_widgets:
                for item in self.canvas_view.node_widgets[node_id]:
                    self.canvas.delete(item)
                del self.canvas_view.node_widgets[node_id]
            self.canvas_view.draw_node(node_id, node_data=nd, selected=True)
        return "break"

    def save_and_exit(self, event=None):
        self._on_close()

    def _atexit_disconnect(self):
        try:
            log.info("atexit handler: attempting graceful disconnection")
            self._client_disconnect()
        except Exception as e:
            log.error(f"Error in atexit handler: {e}")

    def _on_close(self):
        try:
            log.info("Window close handler: attempting graceful disconnection")
            self._client_disconnect()
            # Small delay to ensure disconnect POST completes
            self.master.after(100, self._destroy_window)
        except Exception as e:
            log.error(f"Error during close: {e}")
            self._destroy_window()
    
    def _destroy_window(self):
        try:
            self.master.destroy()
        except Exception:
            try:
                self.master.quit()
            except Exception:
                pass

    def on_graph_update(self, data=None):
        if not data:
            log.debug("on_graph_update called with empty data")
            return
        # Handle partial status_change events (lightweight update)
        if "node_id" in data and "status" in data:
            # Partial update: only update node status
            node_id = data.get("node_id")
            status = data.get("status")
            log.debug(f"Status update: node_id={node_id}, status={status}")
            for node in self.state.graph.get("nodes", []):
                if node.get("id") == node_id:
                    log.debug(f"Found node {node_id}, updating status from {node.get('status')} to {status}")
                    node["status"] = status
                    break
            self.master.after(0, self._redraw_graph)
        elif "nodes" in data or "links" in data:
            # Full graph update from server
            log.info(f"Full graph update received via SocketIO with {len(data.get('nodes', []))} nodes")
            log.debug(f"Updated node labels: {[(n.get('id'), n.get('label')) for n in data.get('nodes', [])]}")
            self.state.graph = data
            self.master.after(0, self._redraw_graph)
        else:
            log.debug(f"Ignoring unexpected graph update format: {list(data.keys())}")
