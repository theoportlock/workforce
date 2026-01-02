import tkinter as tk
from tkinter import messagebox
import logging
from .core import WorkflowApp

log = logging.getLogger(__name__)

def launch(url: str):
    log.info(f"Launching GUI for {url}")
    try:
        root = tk.Tk()
        log.info("Created Tk root")
        app = WorkflowApp(root, url)
        log.info("Created WorkflowApp")
        app.master.title(f"Workforce - {url}")
        log.info("About to enter mainloop")
        root.mainloop()
        log.info("Exited mainloop")
    except Exception as e:
        log.error(f"GUI launch error: {e}", exc_info=True)
        messagebox.showerror("GUI Init Error", f"Failed to initialize GUI for {url}:\n{e}")
