import tkinter as tk
from tkinter import messagebox
from .core import WorkflowApp

def launch(url: str):
    root = tk.Tk()
    app = WorkflowApp(root, url)
    try:
        app.master.title(f"Workforce - {url}")
    except Exception as e:
        messagebox.showerror("GUI Init Error", f"Failed to initialize GUI for {url}:\n{e}")
    root.mainloop()
