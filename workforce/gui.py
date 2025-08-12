#!/usr/bin/env python
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from tkinter.scrolledtext import ScrolledText
import networkx as nx
import subprocess
import os
import threading
import sys
import uuid

class WorkflowApp:
    def __init__(self, master):
        self.master = master
        self.master.grid_rowconfigure(0, weight=0)  # Toolbar row (fixed)
        self.master.grid_rowconfigure(1, weight=1)  # Canvas row (expands)
        self.master.grid_rowconfigure(2, weight=0)  # Terminal row (hidden or fixed)
        self.master.grid_columnconfigure(0, weight=1)
        self.master.grid_columnconfigure(1, weight=0)
        self.terminal_visible = False
        self.terminal_height = 180

        self.create_toolbar()
        self.canvas = tk.Canvas(master, width=1000, height=600, bg='white')
        self.canvas.grid(row=1, column=0, sticky="nsew")

        self.zoom_slider = tk.Scale(
            master,
            from_=0.1,
            to=3.0,
            orient=tk.VERTICAL,
            resolution=0.1,
            command=self.on_zoom_scroll,
            showvalue=False,
            tickinterval=0,     # no ticks
            sliderlength=20,    # shorter slider
            width=10            # thinner bar
        )
        self.zoom_slider.set(1.0)
        self.zoom_slider.grid(row=1, column=1, sticky="ns")

        self.terminal_frame = tk.Frame(master)
        self.terminal_text = ScrolledText(self.terminal_frame, height=10, font=("TkFixedFont", 10), bg="#181818", fg="#e0e0e0", insertbackground="#e0e0e0")
        self.terminal_text.pack(fill=tk.BOTH, expand=True)
        self.terminal_text.config(state=tk.DISABLED)
        self.terminal_frame.grid(row=2, column=0, sticky="nsew")
        self.terminal_frame.grid_remove()

        self.graph = nx.DiGraph()
        self.node_widgets = {}
        self.selected_nodes = []

        self.prefix = ""
        self.suffix = ""

        self.filename = None
        self.last_mtime = None
        self.reload_interval = 1000  # ms

        # Selection rectangle state
        self._select_rect_id = None
        self._select_rect_start = None
        self._select_rect_active = False

        # Click vs Pan state
        self._potential_deselect = False
        self._press_x = 0
        self._press_y = 0

        # Bind keys only when main window is focused
        self.master.bind('<Control-s>', lambda event: self.save_to_current_file())
        self.master.bind('r', lambda event: self.run_selected())
        self.master.bind('<Shift-R>', lambda event: self.run_pipeline())
        self.master.bind('<Shift-C>', lambda event: self.clear_all())
        self.master.bind('d', lambda event: self.remove_node())
        self.master.bind('c', lambda event: self.clear_selected_status())
        self.master.bind('e', lambda event: self.connect_nodes())
        self.master.bind('E', lambda event: self.delete_edges_from_selected())
        self.master.bind('p', lambda event: self.prefix_suffix_popup())
        self.master.bind('q', lambda event: self.save_and_exit())
        self.master.bind('o', lambda event: self.load_graph())
        self.master.bind('t', lambda event: self.toggle_terminal())
        self.master.bind('<Control-Up>', lambda event: self.zoom_in())
        self.master.bind('<Control-Down>', lambda event: self.zoom_out())

        # Zoom and pan
        self.scale = 1.0
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<Button-4>", self.on_zoom)
        self.canvas.bind("<Button-5>", self.on_zoom)
        self.canvas.bind("<ButtonPress-3>", self.on_right_press)
        self.canvas.bind("<ButtonPress-1>", self.on_left_press)
        self.canvas.bind("<B1-Motion>", self.on_left_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Shift-ButtonPress-1>", self.on_shift_left_press)
        self.canvas.bind("<Shift-B1-Motion>", self.on_shift_left_motion)
        self.canvas.bind("<Shift-ButtonRelease-1>", self.on_shift_left_release)

        self.canvas.bind("<Double-Button-1>", self.on_canvas_double_click)
        self.dragging_node = None
        self.drag_offset = (0, 0)

        self.base_font_size = 10
        self.base_edge_width = 2
        self.scale = 1.0

        # Defer loading 'Workfile' until after window is initialized
        self.master.after_idle(self.try_load_workfile)
        self.master.title("Workforce")

        # Get the absolute path to the directory where the script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up one directory to get to the project root
        root_dir = os.path.abspath(os.path.join(script_dir, '..'))

        # Determine the platform and load the correct icon file
        if sys.platform.startswith('win'):
            # Windows and WSL2: Use the multi-size .ico file
            icon_path = os.path.join(root_dir, 'docs', 'images', 'icon.ico')
            if os.path.exists(icon_path):
                self.master.iconbitmap(icon_path)
        elif sys.platform.startswith('darwin'):
            # macOS: Use the .icns file
            icon_path = os.path.join(root_dir, 'docs', 'images', 'icon.icns')
            if os.path.exists(icon_path):
                self.master.iconphoto(True, tk.PhotoImage(file=icon_path))
        else:
            # Linux: Use a .png for full color, or fallback to .xbm
            png_icon_path = os.path.join(root_dir, 'docs', 'images', 'icon-32.png')
            xbm_icon_path = os.path.join(root_dir, 'docs', 'images', 'icon.xbm')

            if os.path.exists(png_icon_path):
                try:
                    icon = tk.PhotoImage(file=png_icon_path)
                    self.master.iconphoto(False, icon)
                except tk.TclError:
                    print("Warning: Could not load PNG icon. Falling back to XBM.")
                    if os.path.exists(xbm_icon_path):
                        self.master.iconbitmap('@' + xbm_icon_path)
            elif os.path.exists(xbm_icon_path):
                self.master.iconbitmap('@' + xbm_icon_path)

        # For edge dragging
        self._edge_drag_start_node = None
        self._edge_drag_line = None

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

    def on_right_press(self, event):
        # Check if right-clicked on a node
        item = self.canvas.find_withtag(tk.CURRENT)
        for node_id, (rect, text) in self.node_widgets.items():
            if item and item[0] in (rect, text):
                self._edge_drag_start_node = node_id
                x1, y1, x2, y2 = self.canvas.coords(rect)
                start_x = (x1 + x2) / 2
                start_y = (y1 + y2) / 2
                self._edge_drag_line = self.canvas.create_line(
                    start_x, start_y, start_x, start_y, fill='gray', dash=(2,2), width=2, tags="edge_drag"
                )
                self.canvas.bind("<B3-Motion>", self.on_right_motion)
                self.canvas.bind("<ButtonRelease-3>", self.on_right_release)
                return
        # If not on a node, fallback to pan
        self.on_pan_start(event)

    def on_right_motion(self, event):
        if self._edge_drag_start_node and self._edge_drag_line:
            # Update the dragging line to current mouse position
            x1, y1, x2, y2 = self.canvas.coords(self.node_widgets[self._edge_drag_start_node][0])
            start_x = (x1 + x2) / 2
            start_y = (y1 + y2) / 2
            end_x = self.canvas.canvasx(event.x)
            end_y = self.canvas.canvasy(event.y)
            self.canvas.coords(self._edge_drag_line, start_x, start_y, end_x, end_y)

    def on_right_release(self, event):
        if self._edge_drag_start_node and self._edge_drag_line:
            # Use event coordinates to check if released over a node
            x = self.canvas.canvasx(event.x)
            y = self.canvas.canvasy(event.y)
            target_node = None
            for node_id, (rect, text) in self.node_widgets.items():
                rx1, ry1, rx2, ry2 = self.canvas.coords(rect)
                if rx1 <= x <= rx2 and ry1 <= y <= ry2:
                    target_node = node_id
                    break
            if target_node and target_node != self._edge_drag_start_node:
                self.graph.add_edge(self._edge_drag_start_node, target_node)
                self.draw_edge(self._edge_drag_start_node, target_node)
            # Remove the dragging line
            self.canvas.delete(self._edge_drag_line)
            self._edge_drag_line = None
            self._edge_drag_start_node = None
            self.canvas.unbind("<B3-Motion>")
            self.canvas.unbind("<ButtonRelease-3>")
    
    def save_and_exit(self, event=None):
        if self.filename:
            self.save_to_current_file()
        self.master.quit()

    def add_node_at(self, x, y, label=None):
        # Store node positions as virtual (unscaled) coordinates
        def on_save(lbl):
            if not lbl.strip():
                return
            node_id = str(uuid.uuid4())
            vx = x / self.scale
            vy = y / self.scale
            self.graph.add_node(node_id, label=lbl, x=vx, y=vy)
            self.draw_node(node_id)
        if label is not None:
            on_save(label)
        else:
            self.node_label_popup("", on_save)

    def delete_edges_from_selected(self):
        # Remove all edges connected to selected nodes (in or out)
        to_remove = []
        for u, v in list(self.graph.edges()):
            if u in self.selected_nodes or v in self.selected_nodes:
                to_remove.append((u, v))
        for u, v in to_remove:
            self.graph.remove_edge(u, v)
        # Redraw edges
        self.canvas.delete("edge")
        for src, tgt in self.graph.edges():
            self.draw_edge(src, tgt)

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

    def draw_node(self, node_id, font_size=None):
        data = self.graph.nodes[node_id]
        # Use virtual coordinates, apply scale for display
        vx, vy = data.get('x', 100), data.get('y', 100)
        x = vx * self.scale
        y = vy * self.scale
        label = data.get('label', node_id)

        # Node color by status
        status_colors = {'running': 'lightblue', 'run': 'lightcyan', 'ran': 'lightgreen', 'fail': 'lightcoral'}
        status = data.get('status', '').lower()
        fill_color = status_colors.get(status, 'lightgray')

        # Use passed font_size, or the instance's current_font_size, or fallback to base
        if font_size is None:
            font_size = getattr(self, 'current_font_size', self.base_font_size)
        font_tuple = ("TkDefaultFont", font_size)

        # Temporary text to measure size
        temp_text = self.canvas.create_text(0, 0, text=label, anchor='nw', font=font_tuple)
        bbox = self.canvas.bbox(temp_text)
        self.canvas.delete(temp_text)

        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Padding should also scale with zoom for consistent appearance
        padding_x, padding_y = 10 * self.scale, 6 * self.scale
        box_width = text_width + 2 * padding_x
        box_height = text_height + 2 * padding_y

        outline_kwargs = {'outline': ''}
        if node_id in self.selected_nodes:
            outline_kwargs['outline'] = "black"
            outline_kwargs['width'] = 1

        # Draw rectangle at scaled virtual coordinates
        rect = self.canvas.create_rectangle(x, y, x + box_width, y + box_height, fill=fill_color, **outline_kwargs)

        # Draw left-aligned text inside the rectangle at scaled virtual coordinates
        text = self.canvas.create_text(x + padding_x, y + padding_y, text=label, anchor='nw', justify='left', font=font_tuple)

        self.node_widgets[node_id] = (rect, text)
        for item in (rect, text):
            # Rebind events as new items are created
            self.canvas.tag_bind(item, "<Button-1>", lambda e, nid=node_id: self.handle_node_click(e, nid))
            self.canvas.tag_bind(item, "<ButtonPress-1>", lambda e, nid=node_id: self.on_node_press(e, nid))
            self.canvas.tag_bind(item, "<B1-Motion>", lambda e, nid=node_id: self.on_node_drag(e, nid))
            self.canvas.tag_bind(item, "<ButtonRelease-1>", lambda e: self.on_node_release(e))
            self.canvas.tag_bind(item, "<Double-Button-1>", lambda e, nid=node_id: self.edit_node_label(nid))
        self.canvas.tag_lower(rect)  # Ensure rectangle is behind text

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

    def load_recent_files(self):
        try:
            with open(self.recent_file_path, 'r') as f:
                files = [line.strip() for line in f if line.strip() and os.path.exists(line.strip())]
            return files
        except Exception:
            return []

    def save_recent_files(self):
        try:
            with open(self.recent_file_path, 'w') as f:
                for file in self.recent_files:
                    f.write(file + '\n')
        except Exception:
            pass

    def add_recent_file(self, filename):
        if filename:
            if filename in self.recent_files:
                self.recent_files.remove(filename)
            self.recent_files.insert(0, filename)
            if len(self.recent_files) > 10:
                self.recent_files = self.recent_files[:10]
            self.save_recent_files()
        self.update_recent_menu()

    def update_recent_menu(self):
        self.recent_menu.delete(0, tk.END)
        if not self.recent_files:
            self.recent_menu.add_command(label="(No recent files)", state=tk.DISABLED)
        else:
            for f in self.recent_files:
                self.recent_menu.add_command(label=f, command=lambda fn=f: self.open_recent_file(fn))

    def open_recent_file(self, filename):
        # Change working directory to the file's base directory
        base_dir = os.path.dirname(os.path.abspath(filename))
        try:
            os.chdir(base_dir)
        except Exception as e:
            print(f"[Warning] Could not change directory to {base_dir}: {e}")
        self.filename = filename
        self.last_mtime = os.path.getmtime(filename)
        self._reload_graph()
        self.master.title(f"Workforce - {os.path.basename(filename)}")
        self.add_recent_file(filename)

    def save_graph(self):
        initialfile = None
        if not self.filename:
            initialfile = "Workfile"
        filename = filedialog.asksaveasfilename(
            initialfile=initialfile,
        )
        if filename:
            self.filename = filename # Store the chosen filename
            self.master.title(f"Workforce - {os.path.basename(filename)}") # Update window title
            self.save_to_current_file() # Now save to the newly chosen file
            self.add_recent_file(filename)

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

    def clear_selected_status(self):
        # Remove status from selected nodes only
        status_colors = {'running': 'lightblue', 'run': 'lightcyan', 'ran': 'lightgreen', 'fail': 'lightcoral'}
        for node_id in self.selected_nodes:
            if 'status' in self.graph.nodes[node_id]:
                del self.graph.nodes[node_id]['status']
            status = self.graph.nodes[node_id].get('status', '').lower()
            fill_color = status_colors.get(status, 'lightgray')
            self.canvas.itemconfig(self.node_widgets[node_id][0], fill=fill_color)

    def on_canvas_double_click(self, event):
        # Only add node if double-clicked on empty space (not on a node)
        item = self.canvas.find_withtag(tk.CURRENT)
        is_on_node = False
        for node_id, (rect, text) in self.node_widgets.items():
            if item and item[-1] in (rect, text):
                is_on_node = True
                break
        if not is_on_node:
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

    def save_to_current_file(self):
        # If a filename is already set, save to it directly
        if self.filename:
            # Save virtual coordinates
            for node_id in self.graph.nodes():
                # Ensure 'x' and 'y' are stored as floats
                vx, vy = self.graph.nodes[node_id].get('x', 100), self.graph.nodes[node_id].get('y', 100)
                self.graph.nodes[node_id]['x'] = float(vx)
                self.graph.nodes[node_id]['y'] = float(vy)
            self.graph.graph['prefix'] = self.prefix
            self.graph.graph['suffix'] = self.suffix
            try:
                nx.write_graphml(self.graph, self.filename)
                print(f"[Saved] {self.filename}")
                self.last_mtime = os.path.getmtime(self.filename) # Update mtime after saving
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save {self.filename}:\n{e}")
        else:
            # If no filename is set, call save_graph to prompt the user
            self.save_graph()

    def try_load_workfile(self):
        default_file = "Workfile"
        if os.path.exists(default_file):
            self.filename = os.path.abspath(default_file)
            self.last_mtime = os.path.getmtime(default_file)
            try:
                self._reload_graph()
                self.master.title(f"Workforce - {self.filename}")
                print(f"[Auto-loaded] {self.filename}")
            except Exception as e:
                messagebox.showerror("Load Error", f"Failed to auto-load {default_file}:\n{e}")
                self.master.title("Workforce")

        # Start periodic file check
        self.master.after(self.reload_interval, self.check_reload)

    def edit_node_label(self, node_id):
        current_label = self.graph.nodes[node_id].get('label', '')
        def on_save(new_label):
            self.graph.nodes[node_id]['label'] = new_label
            self.save_to_current_file()
            if self.filename:
                self._reload_graph()
        self.node_label_popup(current_label, on_save)

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

    def handle_node_click(self, event, node_id):
        self.on_node_click(node_id)
        return "break"

    def on_node_click(self, node_id):
        print(f"Node clicked: {node_id}")
        if node_id in self.selected_nodes:
            self.selected_nodes.remove(node_id)
        else:
            self.selected_nodes.append(node_id)
        # Redraw only the clicked node to update its color
        if node_id in self.node_widgets:
            for item in self.node_widgets[node_id]:
                self.canvas.delete(item)
            del self.node_widgets[node_id]
        self.draw_node(node_id, font_size=getattr(self, 'current_font_size', self.base_font_size))

    def remove_node(self):
        for node_id in self.selected_nodes:
            self.graph.remove_node(node_id)
            for item in self.node_widgets[node_id]:
                self.canvas.delete(item)
            del self.node_widgets[node_id]
        self.selected_nodes.clear()
        self.save_to_current_file()
        if self.filename:
            self._reload_graph()

    def connect_nodes(self):
        if len(self.selected_nodes) >= 2:
            for i in range(len(self.selected_nodes) - 1):
                self.graph.add_edge(self.selected_nodes[i], self.selected_nodes[i+1])
                self.draw_edge(self.selected_nodes[i], self.selected_nodes[i+1])
            self.clear_selection()

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

    def update_node(self):
        if len(self.selected_nodes) == 1:
            new_cmd = simpledialog.askstring("Update Node", "Enter new bash command:")
            if new_cmd:
                node_id = self.selected_nodes[0]
                self.graph.nodes[node_id]['label'] = new_cmd
                self.canvas.itemconfig(self.node_widgets[node_id][1], text=new_cmd)

    def run_selected(self):
        if not self.filename:
            self.save_graph()
        if self.filename:
            self.save_to_current_file()
            for node_id in self.selected_nodes:
                self.run_in_terminal([
                    sys.executable, "-m", "workforce", "run_node", self.filename, node_id,
                    "--prefix", self.prefix, "--suffix", self.suffix
                ], title=f"Run Node: {node_id}")

    def run_pipeline(self):
        if not self.filename:
            self.save_graph()
        if self.filename:
            self.save_to_current_file()
            self.run_in_terminal([
                sys.executable, "-m", "workforce", "run", self.filename,
                "--prefix", self.prefix, "--suffix", self.suffix
            ], title="Run Pipeline")

    def run_in_terminal(self, cmd, title=None):
        import queue
        q = queue.Queue()
        # Write initial command info to terminal (main thread)
        if title:
            self.terminal_write(f"\n=== {title} ===\n")
        else:
            self.terminal_write(f"\n$ {cmd}\n")

        def run():
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                for line in proc.stdout:
                    q.put(line)
                proc.wait()
            except Exception as e:
                q.put(f"\n[Error running command: {e}]\n")
        threading.Thread(target=run, daemon=True).start()

        def poll_queue():
            try:
                while True:
                    line = q.get_nowait()
                    self.terminal_write(line)
            except queue.Empty:
                pass
            # If the thread is still alive or queue not empty, keep polling
            if threading.active_count() > 1 or not q.empty():
                self.master.after(50, poll_queue)
        poll_queue()

    def load_graph(self):
        filename = filedialog.askopenfilename()
        if filename:
            self.filename = filename
            self.last_mtime = os.path.getmtime(filename)
            self._reload_graph()
            self.add_recent_file(filename)

    def _reload_graph(self):
        selected_ids = list(self.selected_nodes)

        self.graph = nx.read_graphml(self.filename)
        self.prefix = self.graph.graph.get('prefix', self.prefix)
        self.suffix = self.graph.graph.get('suffix', self.suffix)

        # Filter selected_ids to only include nodes that still exist
        self.selected_nodes = [nid for nid in selected_ids if nid in self.graph.nodes]

        self.canvas.delete("all")
        self.node_widgets.clear()
        
        for node_id, data in self.graph.nodes(data=True):
            data['x'], data['y'] = float(data.get('x', 100)), float(data.get('y', 100))
            self.draw_node(node_id)
        for src, tgt in self.graph.edges():
            self.draw_edge(src, tgt)

    def add_node(self):
        def on_save(label):
            if not label.strip():
                return
            node_id = str(uuid.uuid4())
            x = 100 + len(self.graph.nodes) * 50
            y = 100
            self.graph.add_node(node_id, label=label, x=x, y=y)
            self.draw_node(node_id)
        self.node_label_popup("", on_save)

    def on_zoom(self, event):
        factor = 1.1 if getattr(event, 'delta', 0) > 0 or getattr(event, 'num', 0) == 4 else 1 / 1.1
        self.zoom(factor, mouse_pos=(event.x, event.y))

    def on_zoom_scroll(self, value):
        new_scale = float(value)
        if abs(new_scale - self.scale) > 1e-9: # Compare floats with a tolerance
            factor = new_scale / self.scale
            self.zoom(factor, from_scroll=True, mouse_pos=(self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2))

    def zoom_in(self):
        self.zoom(1.1, mouse_pos=(self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2))

    def zoom_out(self):
        self.zoom(1/1.1, mouse_pos=(self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2))

    def save_graph(self):
        # Use 'Workfile' as the default filename for first-time save
        initialfile = None
        if not self.filename:
            initialfile = "Workfile"
        filename = filedialog.asksaveasfilename(
            initialfile=initialfile,
        )
        if filename:
            self.filename = filename # Store the chosen filename
            self.master.title(f"Workforce - {os.path.basename(filename)}") # Update window title
            self.save_to_current_file() # Now save to the newly chosen file

    def clear_selection(self):
        nodes_to_redraw = list(self.selected_nodes)
        self.selected_nodes.clear()
        for node_id in nodes_to_redraw:
            if node_id in self.node_widgets:
                for item in self.node_widgets[node_id]:
                    self.canvas.delete(item)
                del self.node_widgets[node_id]
            self.draw_node(node_id, font_size=getattr(self, 'current_font_size', self.base_font_size))

    def clear_all(self):
        # Remove status from all nodes and edges, but do not clear the graph or canvas
        for node_id in list(self.graph.nodes):
            if 'status' in self.graph.nodes[node_id]:
                del self.graph.nodes[node_id]['status']
        for u, v in list(self.graph.edges):
            if 'status' in self.graph.edges[u, v]:
                del self.graph.edges[u, v]['status']
        # Redraw all nodes to update their color
        for node_id in self.graph.nodes:
            rect, text = self.node_widgets[node_id]
            label = self.graph.nodes[node_id].get('label', node_id)
            status_colors = {'running': 'lightblue', 'run': 'lightcyan', 'ran': 'lightgreen', 'fail': 'lightcoral'}
            status = self.graph.nodes[node_id].get('status', '').lower()
            fill_color = status_colors.get(status, 'lightgray')
            self.canvas.itemconfig(rect, fill=fill_color)
            self.canvas.itemconfig(text, text=label)
        # Save and reload
        self.save_to_current_file()
        if self.filename:
            self._reload_graph()

    def zoom(self, factor, from_scroll=False, mouse_pos=None):
        old_scale = self.scale
        new_scale = self.scale * factor
        new_scale = max(0.1, min(new_scale, 3.0))

        if abs(new_scale - old_scale) < 1e-9:
            return

        self.scale = new_scale

        # Update slider only if not triggered by it
        if not from_scroll:
            self.zoom_slider.set(self.scale)

        # Calculate new font size and edge width based on new scale
        new_font = max(1, int(self.base_font_size * self.scale))
        new_width = max(1, int(self.base_edge_width * self.scale))

        # Store the current font size for draw_node to use
        self.current_font_size = new_font

        # Clear existing nodes and edges
        self.canvas.delete("all")
        self.node_widgets.clear()

        # Redraw all nodes with the new scale and font size
        for node_id, data in self.graph.nodes(data=True):
            self.draw_node(node_id)

        # Redraw all edges with the new scale and line width
        for src, tgt in self.graph.edges():
            self.draw_edge(src, tgt)

    def on_pan_start(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def on_pan_move(self, event):
        if self.dragging_node is None:
            self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _get_node_bounds(self, node_id):
        rect, _ = self.node_widgets[node_id]
        return self.canvas.coords(rect)  # [x1, y1, x2, y2]

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

    def check_reload(self):
        if self.filename and os.path.exists(self.filename):
            mtime = os.path.getmtime(self.filename)
            if self.last_mtime and mtime > self.last_mtime:
                self.last_mtime = mtime
                try:
                    self._reload_graph()
                    print(f"[Auto-reloaded] {self.filename}")
                except Exception as e:
                    messagebox.showerror("Reload Error", str(e))
        self.master.after(self.reload_interval, self.check_reload)

    def on_node_press(self, event, node_id):
        self.dragging_node = node_id
        x1, y1, x2, y2 = self._get_node_bounds(node_id)
        self.drag_offset = (event.x - x1, event.y - y1)
        # Store initial positions for all selected nodes (virtual coordinates)
        self._multi_drag_initial = {}
        for nid in self.selected_nodes:
            vx = self.graph.nodes[nid].get('x', 100)
            vy = self.graph.nodes[nid].get('y', 100)
            self._multi_drag_initial[nid] = (vx, vy)

    def on_node_drag(self, event, node_id):
        if self.dragging_node:
            dx, dy = self.drag_offset
            # Convert mouse event to virtual coordinates
            new_x = (event.x - dx) / self.scale
            new_y = (event.y - dy) / self.scale

            # Calculate movement delta in virtual coordinates
            x0, y0 = self._multi_drag_initial.get(node_id, (new_x, new_y))
            delta_x = new_x - x0
            delta_y = new_y - y0

            # Move all selected nodes in virtual coordinates
            for nid in self.selected_nodes:
                ix, iy = self._multi_drag_initial.get(nid, (new_x, new_y))
                nx_ = ix + delta_x
                ny_ = iy + delta_y
                self.graph.nodes[nid]['x'] = nx_
                self.graph.nodes[nid]['y'] = ny_

            # Redraw all nodes and edges
            for node_id2 in list(self.node_widgets.keys()):
                for item in self.node_widgets[node_id2]:
                    self.canvas.delete(item)
            self.node_widgets.clear()
            self.canvas.delete("edge")
            for node_id2 in self.graph.nodes:
                self.draw_node(node_id2, font_size=max(1, int(self.base_font_size * self.scale)))
            for src, tgt in self.graph.edges():
                self.draw_edge(src, tgt)

    def on_node_release(self, event):
        self.dragging_node = None
        self._multi_drag_initial = {}

    def on_canvas_pan(self, event):
        if self.dragging_node is None:
            self.canvas.scan_dragto(event.x, event.y, gain=1)

    def on_canvas_release(self, event):
        if getattr(self, '_potential_deselect', False):
            self.clear_selection()
        self._potential_deselect = False
        self._panning = False

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

if __name__ == "__main__":
    root = tk.Tk()
    app = WorkflowApp(root)
    root.mainloop()
