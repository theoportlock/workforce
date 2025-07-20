import tkinter as tk

class ZoomPanCanvas(tk.Canvas):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.bind("<ButtonPress-1>", self.on_left_press)
        self.bind("<B1-Motion>", self.on_left_drag)
        self.bind("<ButtonPress-3>", self.on_right_press)
        self.bind("<B3-Motion>", self.on_right_drag)
        self.bind("<MouseWheel>", self.on_zoom)  # Windows
        self.bind("<Button-4>", self.on_zoom)    # Linux scroll up
        self.bind("<Button-5>", self.on_zoom)    # Linux scroll down
        self.nodes = []
        self.drag_data = {"x": 0, "y": 0, "item": None}
        self.pan_start = (0, 0)

    def add_node(self, x, y, label):
        node = self.create_oval(x-20, y-20, x+20, y+20, fill='lightgray', tags='node')
        text = self.create_text(x, y, text=label, tags='node')
        self.nodes.append((node, text))

    def on_left_press(self, event):
        item = self.find_closest(self.canvasx(event.x), self.canvasy(event.y))
        if "node" in self.gettags(item):
            self.drag_data["item"] = item
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y

    def on_left_drag(self, event):
        if self.drag_data["item"]:
            dx = event.x - self.drag_data["x"]
            dy = event.y - self.drag_data["y"]
            self.move(self.drag_data["item"], dx, dy)
            # move paired text/oval
            tags = self.gettags(self.drag_data["item"])
            for item in self.find_withtag(tags[0]):
                self.move(item, dx, dy)
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y

    def on_right_press(self, event):
        self.pan_start = (event.x, event.y)

    def on_right_drag(self, event):
        dx = event.x - self.pan_start[0]
        dy = event.y - self.pan_start[1]
        self.scan_dragto(-dx, -dy, gain=1)
        self.pan_start = (event.x, event.y)

    def on_zoom(self, event):
        scale = 1.1 if event.delta > 0 or event.num == 4 else 0.9
        self.scale("all", self.canvasx(event.x), self.canvasy(event.y), scale, scale)

class WorkflowApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Workforce (Tkinter Edition)")
        self.canvas = ZoomPanCanvas(master, bg="white", width=800, height=600)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.add_node(100, 100, "echo 'Hello'")
        self.canvas.add_node(300, 200, "ls -l")

if __name__ == "__main__":
    root = tk.Tk()
    app = WorkflowApp(root)
    root.mainloop()

