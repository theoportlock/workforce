import tkinter as tk
from tkinter import messagebox
import logging
import subprocess
import sys
import os
from .core import WorkflowApp

log = logging.getLogger(__name__)

def launch(base_url: str, wf_path: str = None, workspace_id: str = None, background: bool = True):
    """
    Launch the GUI for a workspace.
    
    Args:
        base_url: Full workspace URL (e.g., http://localhost:5000/workspace/ws_abc123)
        wf_path: Absolute path to workfile
        workspace_id: Workspace ID (e.g., ws_abc123)
        background: If True, spawn in subprocess
    """
    # Background mode: spawn a new process
    if background and sys.platform != "emscripten":
        cmd = [
            sys.executable,
            "-m", "workforce",
            "gui",
            wf_path or ".",
            "--foreground"
        ]
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=os.getcwd(),
        )
        print(f"GUI launched in background for {wf_path}")
        return
    
    # Foreground mode: run GUI directly
    log.info(f"Launching GUI in foreground for {base_url}")
    try:
        root = tk.Tk()
        log.info("Created Tk root")
        app = WorkflowApp(root, base_url, wf_path=wf_path, workspace_id=workspace_id)
        log.info("Created WorkflowApp")
        app.master.title(f"Workforce - {wf_path or 'workspace'}")
        log.info("About to enter mainloop")
        root.mainloop()
        log.info("Exited mainloop")
    except Exception as e:
        log.error(f"GUI launch error: {e}", exc_info=True)
        messagebox.showerror("GUI Init Error", f"Failed to initialize GUI:\n{e}")
