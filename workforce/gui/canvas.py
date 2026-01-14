import tkinter as tk
from typing import Callable, Dict, Any
import uuid
from .state import THEME

class GraphCanvas:
    def __init__(self, tk_canvas: tk.Canvas, state, callbacks: Dict[str, Callable]):
        """
        callbacks: {
            "on_node_click", "on_node_press", "on_node_drag", "on_node_release",
            "on_node_double_click", "on_node_right_click", "on_node_double_right_click"
        }
        """
        self.canvas = tk_canvas
        self.state = state
        self.node_widgets: Dict[str, tuple] = {}
        self.callbacks = callbacks or {}

    def redraw(self, graph: Dict[str, Any]):
        self.canvas.delete("all")
        self.node_widgets.clear()
        for node in graph.get("nodes", []):
            self.draw_node(node.get("id"), node_data=node)
        for link in graph.get("links", []):
            self.draw_edge(link)

    def draw_node(self, node_id, node_data=None, font_size=None, selected=None):
        data = node_data or {}
        if selected is None:
            selected = node_id in self.state.selected_nodes

        vx = float(data.get("x", 100))
        vy = float(data.get("y", 100))
        x = (vx * self.state.scale) + self.state.pan_x
        y = (vy * self.state.scale) + self.state.pan_y
        label = data.get("label", node_id)
        status = data.get("status", "").lower()
        status_map = THEME["colors"]["node"]
        fill = status_map.get(status, status_map.get("default"))

        font_size = font_size or max(1, int(self.state.base_font_size * self.state.scale))
        temp = self.canvas.create_text(0, 0, text=label, anchor="nw", font=("TkDefaultFont", font_size), fill=THEME["colors"]["text"]) 
        bbox = self.canvas.bbox(temp) or (0, 0, 60, 20)
        self.canvas.delete(temp)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        pad_x, pad_y = 10 * self.state.scale, 6 * self.state.scale
        w = text_w + 2 * pad_x
        h = text_h + 2 * pad_y
        outline_color = THEME["colors"]["node"]["selected_outline"] if selected else ""
        rect = self.canvas.create_rectangle(x, y, x + w, y + h, fill=fill, outline=outline_color, width=1 if selected else 0)
        txt = self.canvas.create_text(x + pad_x, y + pad_y, text=label, anchor="nw", font=("TkDefaultFont", font_size), fill=THEME["colors"]["text"]) 
        self.node_widgets[node_id] = (rect, txt)

        # Bind events to callbacks provided by WorkflowApp
        cb = self.callbacks
        for item in (rect, txt):
            if "on_node_click" in cb:
                self.canvas.tag_bind(item, "<Button-1>", lambda e, nid=node_id: cb["on_node_click"](e, nid))
            if "on_node_press" in cb:
                self.canvas.tag_bind(item, "<ButtonPress-1>", lambda e, nid=node_id: cb["on_node_press"](e, nid))
            if "on_node_drag" in cb:
                self.canvas.tag_bind(item, "<B1-Motion>", lambda e, nid=node_id: cb["on_node_drag"](e, nid))
            if "on_node_release" in cb:
                self.canvas.tag_bind(item, "<ButtonRelease-1>", lambda e: cb["on_node_release"](e))
            if "on_node_double_click" in cb:
                self.canvas.tag_bind(item, "<Double-Button-1>", lambda e, nid=node_id: cb["on_node_double_click"](e, nid))
            if "on_node_right_click" in cb:
                self.canvas.tag_bind(item, "<Button-2>", lambda e, nid=node_id: cb["on_node_right_click"](e, nid))
            if "on_node_double_right_click" in cb:
                self.canvas.tag_bind(item, "<Double-Button-2>", lambda e, nid=node_id: cb["on_node_double_right_click"](e, nid))

    def draw_edge(self, edge_data):
        src = edge_data.get("source") if isinstance(edge_data, dict) else None
        tgt = edge_data.get("target") if isinstance(edge_data, dict) else None
        if not src or not tgt:
            return
        x1, y1 = self.get_node_center(src)
        x2, y2 = self.get_node_center(tgt)
        src_box = self.get_node_bounds(src)
        tgt_box = self.get_node_bounds(tgt)
        x1a, y1a = self.clip_line_to_box(x1, y1, x2, y2, src_box)
        x2a, y2a = self.clip_line_to_box(x2, y2, x1, y1, tgt_box)
        edge_type = edge_data.get("edge_type", "blocking") if isinstance(edge_data, dict) else "blocking"
        scale_width = self.state.base_edge_width * self.state.scale
        width = scale_width * (2.5 if edge_type == "non-blocking" else 1.0)
        dash = (4, 3) if edge_type == "non-blocking" else None
        line = self.canvas.create_line(
            x1a,
            y1a,
            x2a,
            y2a,
            arrow=tk.LAST,
            fill=THEME["colors"]["edge"]["line"],
            tags="edge",
            width=width,
            dash=dash,
        )
        self.canvas.tag_lower(line)

    def get_node_bounds(self, node_id):
        rect, _ = self.node_widgets[node_id]
        return self.canvas.coords(rect)

    def get_node_center(self, node_id):
        x1, y1, x2, y2 = self.get_node_bounds(node_id)
        return (x1 + x2) / 2, (y1 + y2) / 2

    def clip_line_to_box(self, x0, y0, x1, y1, box):
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

    def update_node_position(self, node_id, node_data):
        """Update a single node's position without full redraw."""
        if node_id not in self.node_widgets:
            # Node doesn't exist yet, do full draw
            self.draw_node(node_id, node_data=node_data)
            return
        
        rect, txt = self.node_widgets[node_id]
        
        # Calculate new screen coordinates
        vx = float(node_data.get("x", 100))
        vy = float(node_data.get("y", 100))
        x = (vx * self.state.scale) + self.state.pan_x
        y = (vy * self.state.scale) + self.state.pan_y
        
        # Get current dimensions
        x1, y1, x2, y2 = self.canvas.coords(rect)
        w = x2 - x1
        h = y2 - y1
        
        # Update rectangle position
        self.canvas.coords(rect, x, y, x + w, y + h)
        
        # Update text position
        pad_x, pad_y = 10 * self.state.scale, 6 * self.state.scale
        self.canvas.coords(txt, x + pad_x, y + pad_y)
    
    def update_node_status(self, node_id, node_data):
        """Update a single node's status (color) without full redraw."""
        if node_id not in self.node_widgets:
            # Node doesn't exist yet, do full draw
            self.draw_node(node_id, node_data=node_data)
            return
        
        rect, txt = self.node_widgets[node_id]
        
        # Update fill color based on status
        status = node_data.get("status", "").lower()
        status_map = THEME["colors"]["node"]
        fill = status_map.get(status, status_map.get("default"))
        self.canvas.itemconfig(rect, fill=fill)
    
    def update_node_label(self, node_id, node_data):
        """Update a single node's label without full redraw."""
        if node_id not in self.node_widgets:
            # Node doesn't exist yet, do full draw
            self.draw_node(node_id, node_data=node_data)
            return
        
        rect, txt = self.node_widgets[node_id]
        label = node_data.get("label", node_id)
        
        # Update text content
        font_size = max(1, int(self.state.base_font_size * self.state.scale))
        self.canvas.itemconfig(txt, text=label, font=("TkDefaultFont", font_size))
        
        # Recalculate size and update rectangle
        temp = self.canvas.create_text(0, 0, text=label, anchor="nw", font=("TkDefaultFont", font_size), fill=THEME["colors"]["text"])
        bbox = self.canvas.bbox(temp) or (0, 0, 60, 20)
        self.canvas.delete(temp)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        pad_x, pad_y = 10 * self.state.scale, 6 * self.state.scale
        w = text_w + 2 * pad_x
        h = text_h + 2 * pad_y
        
        # Update rectangle size
        x1, y1, _, _ = self.canvas.coords(rect)
        self.canvas.coords(rect, x1, y1, x1 + w, y1 + h)
        
        # Update text position
        self.canvas.coords(txt, x1 + pad_x, y1 + pad_y)

class Canvas:
    """
    Light compatibility wrapper used by tests: simple add_node + nodes store.
    Not a full replacement for GraphCanvas; intended for unit tests.
    """
    def __init__(self, master):
        # master can be a Tk Canvas or a MagicMock in tests
        self.master = master
        self.gc_state = {
            "scale": 1.0,
            "base_font_size": 10,
            "base_edge_width": 2,
            "selected_nodes": [],
            "graph": {"nodes": [], "links": []}
        }
        self.nodes = {}

    def add_node(self, label, x=0, y=0):
        node_id = str(uuid.uuid4())
        node = {"id": node_id, "label": label, "x": x, "y": y}
        self.nodes[node_id] = node
        self.gc_state["graph"]["nodes"].append(node)
        return node_id
