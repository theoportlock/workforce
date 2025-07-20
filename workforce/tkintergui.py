import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
import networkx as nx
import subprocess
import os

class WorkflowApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Workforce (Tkinter Edition)")
        self.canvas = tk.Canvas(master, width=1000, height=600, bg='white')
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.graph = nx.DiGraph()
        self.node_widgets = {}
        self.selected_nodes = []

        self.prefix = "bash -c"
        self.suffix = ""

        self.create_toolbar()
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.scale = 1.0

        self.origin = (0, 0)
        self.canvas.bind("<MouseWheel>", self.on_zoom)  # Windows
        self.canvas.bind("<Button-4>", self.on_zoom)    # Linux scroll up
        self.canvas.bind("<Button-5>", self.on_zoom)    # Linux scroll down

        self.canvas.bind("<ButtonPress-3>", self.on_pan_start)
        self.canvas.bind("<B3-Motion>", self.on_pan_move)

        self.pan_x = 0
        self.pan_y = 0
        self.drag_data = {"item": None, "x": 0, "y": 0}


    def create_toolbar(self):
        toolbar = tk.Frame(self.master)
        toolbar.pack(fill=tk.X)

        tk.Button(toolbar, text="Load", command=self.load_graph).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Save", command=self.save_graph).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Add", command=self.add_node).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Remove", command=self.remove_node).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Connect", command=self.connect_nodes).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Update", command=self.update_node).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Run Node", command=self.run_selected).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Run Pipeline", command=self.run_pipeline).pack(side=tk.LEFT)
        tk.Button(toolbar, text="Clear", command=self.clear_all).pack(side=tk.LEFT)

    def on_canvas_click(self, event):
        self.clear_selection()

    def add_node(self):
        cmd = simpledialog.askstring("Add Node", "Enter bash command:")
        if not cmd: return
        node_id = f"node{len(self.graph.nodes)}"
        self.graph.add_node(node_id, label=cmd, x=100+len(self.graph.nodes)*50, y=100)
        self.draw_node(node_id)

    def draw_node(self, node_id):
        data = self.graph.nodes[node_id]
        x, y = data.get('x', 100), data.get('y', 100)
        oval = self.canvas.create_oval(x, y, x+60, y+40, fill="lightgray")
        text = self.canvas.create_text(x+30, y+20, text=data.get('label', node_id), width=60)

        self.node_widgets[node_id] = (oval, text)

        for item in (oval, text):
            self.canvas.tag_bind(item, "<Button-1>", lambda e, nid=node_id: self.on_node_click(nid))

    def on_node_click(self, node_id):
        if node_id in self.selected_nodes:
            self.selected_nodes.remove(node_id)
            self.canvas.itemconfig(self.node_widgets[node_id][0], fill="lightgray")
        else:
            self.selected_nodes.append(node_id)
            self.canvas.itemconfig(self.node_widgets[node_id][0], fill="gray")

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
        x1, y1 = self.graph.nodes[src]['x'] + 30, self.graph.nodes[src]['y'] + 20
        x2, y2 = self.graph.nodes[tgt]['x'] + 30, self.graph.nodes[tgt]['y'] + 20
        self.canvas.create_line(x1, y1, x2, y2, arrow=tk.LAST, fill='gray')

    def update_node(self):
        if len(self.selected_nodes) == 1:
            new_cmd = simpledialog.askstring("Update Node", "Enter new bash command:")
            if new_cmd:
                node_id = self.selected_nodes[0]
                self.graph.nodes[node_id]['label'] = new_cmd
                self.canvas.itemconfig(self.node_widgets[node_id][1], text=new_cmd)

    def run_selected(self):
        for node_id in self.selected_nodes:
            cmd = self.graph.nodes[node_id]['label']
            full_cmd = f"{self.prefix} \"{cmd}\" {self.suffix}"
            subprocess.call(full_cmd, shell=True)

    def run_pipeline(self):
        for node_id in nx.topological_sort(self.graph):
            cmd = self.graph.nodes[node_id]['label']
            full_cmd = f"{self.prefix} \"{cmd}\" {self.suffix}"
            subprocess.call(full_cmd, shell=True)

    def load_graph(self):
        filename = filedialog.askopenfilename(filetypes=[("GraphML files", "*.graphml")])
        if filename:
            self.graph = nx.read_graphml(filename)
            self.canvas.delete("all")
            self.node_widgets.clear()
            self.selected_nodes.clear()
            for node_id, data in self.graph.nodes(data=True):
                data['x'], data['y'] = float(data.get('x', 100)), float(data.get('y', 100))
                self.draw_node(node_id)
            for src, tgt in self.graph.edges():
                self.draw_edge(src, tgt)

    def save_graph(self):
        filename = filedialog.asksaveasfilename(defaultextension=".graphml", filetypes=[("GraphML files", "*.graphml")])
        if filename:
            for node_id in self.graph.nodes():
                x1, y1, x2, y2 = self.canvas.coords(self.node_widgets[node_id][0])
                self.graph.nodes[node_id]['x'] = x1
                self.graph.nodes[node_id]['y'] = y1
            self.graph.graph['prefix'] = self.prefix
            self.graph.graph['suffix'] = self.suffix
            nx.write_graphml(self.graph, filename)

    def clear_selection(self):
        for node_id in self.selected_nodes:
            self.canvas.itemconfig(self.node_widgets[node_id][0], fill="lightgray")
        self.selected_nodes.clear()

    def clear_all(self):
        self.graph.clear()
        self.canvas.delete("all")
        self.node_widgets.clear()
        self.selected_nodes.clear()

    def on_zoom(self, event):
        factor = 1.1 if event.delta > 0 or getattr(event, 'num', 0) == 4 else 0.9
        self.scale *= factor
        self.canvas.scale("all", event.x, event.y, factor, factor)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_pan_start(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def on_pan_move(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def on_drag_start(self, event):
    x = self.canvas.canvasx(event.x)
    y = self.canvas.canvasy(event.y)
    item = self.canvas.find_closest(x, y)
    if "node" in self.canvas.gettags(item):
        self.drag_data["item"] = item
        self.drag_data["x"] = x
        self.drag_data["y"] = y

    def on_drag_motion(self, event):
        if self.drag_data["item"]:
            x = self.canvas.canvasx(event.x)
            y = self.canvas.canvasy(event.y)
            dx = (x - self.drag_data["x"])
            dy = (y - self.drag_data["y"])
            self.canvas.move(self.drag_data["item"], dx, dy)
            self.drag_data["x"] = x
            self.drag_data["y"] = y


if __name__ == "__main__":
    root = tk.Tk()
    app = WorkflowApp(root)
    root.mainloop()
