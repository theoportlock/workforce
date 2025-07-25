#!/usr/bin/env python
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
import networkx as nx
import subprocess
import os
import sys

class WorkflowApp:
    def __init__(self, master):
        self.master = master
        self.canvas = tk.Canvas(master, width=1000, height=600, bg='white')
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.graph = nx.DiGraph()
        self.node_widgets = {}
        self.selected_nodes = []

        self.prefix = "bash -c"
        self.suffix = ""

        self.filename = None
        self.last_mtime = None
        self.reload_interval = 1000  # ms

        self.create_toolbar()

        # Bind keys only when main window is focused
        self.master.bind('<Control-s>', lambda event: self.save_to_current_file())
        self.master.bind('r', lambda event: self.run_selected())
        self.master.bind('<Shift-R>', lambda event: self.run_pipeline())
        self.master.bind('<Shift-C>', lambda event: self.clear_all())
        self.master.bind('d', lambda event: self.remove_node())
        self.master.bind('c', lambda event: self.clear_selected_status())

        # Zoom and pan
        self.scale = 1.0
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<Button-4>", self.on_zoom)
        self.canvas.bind("<Button-5>", self.on_zoom)
        self.canvas.bind("<ButtonPress-3>", self.on_pan_start)
        self.canvas.bind("<ButtonPress-1>", self.on_left_press)
        self.canvas.bind("<B1-Motion>", self.on_left_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Double-Button-1>", self.on_canvas_double_click)
        self.dragging_node = None
        self.drag_offset = (0, 0)
        
        self.base_font_size = 10
        self.base_edge_width = 2
        self.scale = 1.0

        # Defer loading 'Workfile' until after window is initialized
        self.master.after_idle(self.try_load_workfile)
        self.master.title("Workforce")

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

        # Use current font size for both text and rectangle
        if font_size is None:
            font_size = getattr(self, 'current_font_size', self.base_font_size)
        font_tuple = ("TkDefaultFont", font_size)

        # Temporary text to measure size
        temp_text = self.canvas.create_text(0, 0, text=label, anchor='nw', font=font_tuple)
        bbox = self.canvas.bbox(temp_text)
        self.canvas.delete(temp_text)

        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        padding_x, padding_y = 10 * self.scale, 6 * self.scale
        box_width = text_width + 2 * padding_x
        box_height = text_height + 2 * padding_y

        # Draw rectangle
        rect = self.canvas.create_rectangle(x, y, x + box_width, y + box_height, fill=fill_color, outline="")

        # Draw left-aligned text inside the rectangle
        text = self.canvas.create_text(x + padding_x, y + padding_y, text=label, anchor='nw', justify='left', font=font_tuple)

        self.node_widgets[node_id] = (rect, text)
        for item in (rect, text):
            self.canvas.tag_bind(item, "<Button-1>", lambda e, nid=node_id: self.handle_node_click(e, nid))
            self.canvas.tag_bind(item, "<ButtonPress-1>", lambda e, nid=node_id: self.on_node_press(e, nid))
            self.canvas.tag_bind(item, "<B1-Motion>", lambda e, nid=node_id: self.on_node_drag(e, nid))
            self.canvas.tag_bind(item, "<ButtonRelease-1>", lambda e: self.on_node_release(e))
            self.canvas.tag_bind(item, "<Double-Button-1>", lambda e, nid=node_id: self.edit_node_label(nid))

    def create_toolbar(self):
        toolbar = tk.Frame(self.master)
        toolbar.pack(fill=tk.X)

        tk.Button(toolbar, text="Load", command=self.load_graph).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Save", command=self.save_graph).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Add", command=self.add_node).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Remove", command=self.remove_node).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Connect", command=self.connect_nodes).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Update", command=self.update_node).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Prefix/Suffix", command=self.prefix_suffix_popup).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Run Node", command=self.run_selected).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Run Pipeline", command=self.run_pipeline).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Clear", command=self.clear_all).pack(side=tk.LEFT)

    def prefix_suffix_popup(self):
        editor = tk.Toplevel(self.master)
        editor.title("Prefix/Suffix")
        editor.geometry("500x180")
        editor.minsize(500, 180)

        frame = tk.Frame(editor)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Prefix
        prefix_label = tk.Label(frame, text="Prefix:")
        prefix_label.grid(row=0, column=0, sticky="w")
        prefix_text = tk.Text(frame, wrap='word', font=("TkDefaultFont", 10), height=4, width=25)
        prefix_text.grid(row=1, column=0, sticky="nsew", padx=(0,10))
        prefix_text.insert("1.0", self.prefix)

        # Suffix
        suffix_label = tk.Label(frame, text="Suffix:")
        suffix_label.grid(row=0, column=1, sticky="w")
        suffix_text = tk.Text(frame, wrap='word', font=("TkDefaultFont", 10), height=4, width=25)
        suffix_text.grid(row=1, column=1, sticky="nsew")
        suffix_text.insert("1.0", self.suffix)

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        def save_and_close():
            self.prefix = prefix_text.get("1.0", "end-1c")
            self.suffix = suffix_text.get("1.0", "end-1c")
            editor.destroy()

        def cancel_and_close():
            editor.destroy()

        btn_frame = tk.Frame(editor)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0,10))
        save_btn = tk.Button(btn_frame, text="Save", command=save_and_close)
        save_btn.pack(side=tk.LEFT, padx=5)
        cancel_btn = tk.Button(btn_frame, text="Cancel", command=cancel_and_close)
        cancel_btn.pack(side=tk.LEFT, padx=5)

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

    def add_node_at(self, x, y):
        # Store node positions as virtual (unscaled) coordinates
        def on_save(label):
            if not label.strip():
                return
            node_id = f"node{len(self.graph.nodes)}"
            vx = x / self.scale
            vy = y / self.scale
            self.graph.add_node(node_id, label=label, x=vx, y=vy)
            self.draw_node(node_id)
        self.node_label_popup("", on_save)

    def on_left_press(self, event):
        # Check if clicked on a node
        item = self.canvas.find_withtag(tk.CURRENT)
        node_clicked = False
        for node_id, (rect, text) in self.node_widgets.items():
            if item and item[0] in (rect, text):
                node_clicked = True
                self.on_node_click(node_id)
                self.on_node_press(event, node_id)
                break
        if not node_clicked:
            # Clicked empty space, clear selection and prepare to pan
            self.clear_selection()
            self.canvas.scan_mark(event.x, event.y)
            self.dragging_node = None
            self._panning = True
        else:
            self._panning = False

    def on_left_motion(self, event):
        if self.dragging_node:
            self.on_node_drag(event, self.dragging_node)
        elif getattr(self, '_panning', False):
            self.canvas.scan_dragto(event.x, event.y, gain=1)

    def save_to_current_file(self):
        if self.filename:
            # Save virtual coordinates
            for node_id in self.graph.nodes():
                vx, vy = self.graph.nodes[node_id].get('x', 100), self.graph.nodes[node_id].get('y', 100)
                self.graph.nodes[node_id]['x'] = vx
                self.graph.nodes[node_id]['y'] = vy
            self.graph.graph['prefix'] = self.prefix
            self.graph.graph['suffix'] = self.suffix
            nx.write_graphml(self.graph, self.filename)
            print(f"[Saved] {self.filename}")
        else:
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
            self.canvas.itemconfig(self.node_widgets[node_id][1], text=new_label)
        self.node_label_popup(current_label, on_save)

    def node_label_popup(self, initial_value, on_save):
        editor = tk.Toplevel(self.master)
        editor.title("Node Label")
        editor.geometry("400x200")
        editor.minsize(400, 200)
        text_widget = tk.Text(editor, wrap='word', font=("TkDefaultFont", 10), height=6)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10,0))
        text_widget.insert("1.0", initial_value)

        def save_and_close():
            new_label = text_widget.get("1.0", "end-1c")
            on_save(new_label)
            editor.destroy()

        def cancel_and_close():
            editor.destroy()

        btn_frame = tk.Frame(editor)
        btn_frame.pack(fill=tk.X, padx=10, pady=(5,10))
        save_btn = tk.Button(btn_frame, text="Save", command=save_and_close)
        save_btn.pack(side=tk.LEFT, padx=5)
        cancel_btn = tk.Button(btn_frame, text="Cancel", command=cancel_and_close)
        cancel_btn.pack(side=tk.LEFT, padx=5)

        editor.transient(self.master)
        editor.wait_visibility()  # Ensure window is visible before grab_set
        editor.grab_set()
        text_widget.focus_set()

    def handle_node_click(self, event, node_id):
        self.on_node_click(node_id)
        return "break"

    def on_node_click(self, node_id):
        print(node_id)
        status_colors = {'running': 'lightblue', 'run': 'lightcyan', 'ran': 'lightgreen', 'fail': 'lightcoral'}
        status = self.graph.nodes[node_id].get('status', '').lower()
        fill_color = status_colors.get(status, 'lightgray')
        if node_id in self.selected_nodes:
            self.selected_nodes.remove(node_id)
            self.canvas.itemconfig(self.node_widgets[node_id][0], fill=fill_color)
        else:
            self.selected_nodes.append(node_id)
            self.canvas.itemconfig(self.node_widgets[node_id][0], fill="#555555")

    def remove_node(self):
        for node_id in self.selected_nodes:
            self.graph.remove_node(node_id)
            for item in self.node_widgets[node_id]:
                self.canvas.delete(item)
            del self.node_widgets[node_id]
        self.selected_nodes.clear()

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
            fill='gray',
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
                subprocess.Popen([
                    sys.executable, "-m", "workforce", "run_node", self.filename, node_id,
                    "--prefix", self.prefix, "--suffix", self.suffix
                ])

    def run_pipeline(self):
        if not self.filename:
            self.save_graph()
        if self.filename:
            self.save_to_current_file()
            print(self.prefix, self.suffix) # THEO ADDED
            subprocess.Popen([
                sys.executable, "-m", "workforce", "run", self.filename,
                "--prefix", self.prefix, "--suffix", self.suffix
            ])

    def load_graph(self):
        filename = filedialog.askopenfilename()
        if filename:
            self.filename = filename
            self.last_mtime = os.path.getmtime(filename)
            self._reload_graph()

    def _reload_graph(self):
        # Save current canvas view and zoom
        if not hasattr(self, '_last_canvas_state'):
            self._last_canvas_state = {
                'xview': self.canvas.xview(),
                'yview': self.canvas.yview(),
                'scale': self.scale
            }
        xview = self._last_canvas_state['xview']
        yview = self._last_canvas_state['yview']
        prev_scale = self._last_canvas_state['scale']

        # Reload graph
        self.graph = nx.read_graphml(self.filename)
        self.prefix = self.graph.graph.get('prefix', self.prefix)
        self.suffix = self.graph.graph.get('suffix', self.suffix)
        self.canvas.delete("all")
        self.node_widgets.clear()
        self.selected_nodes.clear()
        for node_id, data in self.graph.nodes(data=True):
            data['x'], data['y'] = float(data.get('x', 100)), float(data.get('y', 100))
            self.draw_node(node_id, font_size=max(1, int(self.base_font_size * prev_scale)))
        for src, tgt in self.graph.edges():
            self.draw_edge(src, tgt)

        # Restore zoom (scale) and font/edge style
        if abs(self.scale - prev_scale) > 1e-6:
            factor = prev_scale / self.scale
            self.zoom(factor)

        # Ensure canvas is updated before restoring scroll position
        self.canvas.update_idletasks()
        self.canvas.xview_moveto(xview[0])
        self.canvas.yview_moveto(yview[0])

    def add_node(self):
        def on_save(label):
            if not label.strip():
                return
            node_id = f"node{len(self.graph.nodes)}"
            x = 100 + len(self.graph.nodes) * 50
            y = 100
            self.graph.add_node(node_id, label=label, x=x, y=y)
            self.draw_node(node_id)
        self.node_label_popup("", on_save)

    def on_zoom(self, event):
        factor = 1.1 if getattr(event, 'delta', 0) > 0 or getattr(event, 'num', 0) == 4 else 1 / 1.1
        self.zoom(factor)

    def save_graph(self):
        filename = filedialog.asksaveasfilename()
        if filename:
            # Save virtual coordinates
            for node_id in self.graph.nodes():
                vx, vy = self.graph.nodes[node_id].get('x', 100), self.graph.nodes[node_id].get('y', 100)
                self.graph.nodes[node_id]['x'] = vx
                self.graph.nodes[node_id]['y'] = vy
            self.graph.graph['prefix'] = self.prefix
            self.graph.graph['suffix'] = self.suffix
            nx.write_graphml(self.graph, filename)

    def clear_selection(self):
        status_colors = {'running': 'lightblue', 'run': 'lightcyan', 'ran': 'lightgreen', 'fail': 'lightcoral'}
        for node_id in self.selected_nodes:
            status = self.graph.nodes[node_id].get('status', '').lower()
            fill_color = status_colors.get(status, 'lightgray')
            self.canvas.itemconfig(self.node_widgets[node_id][0], fill=fill_color)
        self.selected_nodes.clear()

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

    def zoom(self, factor):
        self.scale *= factor
        self.canvas.scale("all", 0, 0, factor, factor)

        # Style updates only
        new_font = max(1, int(self.base_font_size * self.scale))
        new_width = max(1, int(self.base_edge_width * self.scale))

        for node_id, (rect, text) in self.node_widgets.items():
            self.canvas.itemconfig(rect, width=new_width)
            self.canvas.itemconfig(text, font=("Arial", new_font))

        for edge in self.canvas.find_withtag("edge"):
            self.canvas.itemconfig(edge, width=new_width)

    def on_mousewheel(self, event):
        factor = 1.1 if getattr(event, 'delta', 0) > 0 or getattr(event, 'num', 0) == 4 else 1 / 1.1
        self.zoom(factor)

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
        # Nothing special needed here for pan
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

if __name__ == "__main__":
    root = tk.Tk()
    app = WorkflowApp(root)
    root.mainloop()

