import tkinter as tk
from tkinter import messagebox
import logging
import subprocess
import sys
import os
from .core import WorkflowApp

log = logging.getLogger(__name__)

def launch(url: str, background: bool = True):
    # Background mode: spawn a new process
    if background and sys.platform != "emscripten":
        cmd = [
            sys.executable,
            "-m", "workforce",
            "gui",
            url,
            "--foreground"
        ]
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=os.getcwd(),
        )
        print(f"GUI launched in background for {url}")
        return
    
    # Foreground mode: run GUI directly
    log.info(f"Launching GUI in foreground for {url}")
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
