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
        base_url: Full workspace URL (e.g., http://127.0.0.1:5042/workspace/ws_abc123)
        wf_path: Absolute path to workfile or remote placeholder
        workspace_id: Workspace ID (e.g., ws_abc123)
        background: If True, spawn in subprocess
    """
    # Background mode: spawn a new process
    if background and sys.platform != "emscripten":
        # Ensure workforce package is in PYTHONPATH for subprocess
        env = os.environ.copy()
        
        # Find the parent directory containing the workforce package
        # workforce.__file__ gives us .../workforce/__init__.py
        # We want the parent of the workforce directory
        import workforce
        package_root = os.path.dirname(os.path.dirname(os.path.abspath(workforce.__file__)))
        
        # Add to PYTHONPATH if not already there
        pythonpath = env.get('PYTHONPATH', '')
        if package_root not in pythonpath.split(os.pathsep):
            env['PYTHONPATH'] = f"{package_root}{os.pathsep}{pythonpath}" if pythonpath else package_root
        
        # For remote workspaces, pass the full workspace URL instead of placeholder path
        if wf_path and wf_path.startswith('<remote:'):
            # Extract workspace ID and construct URL from base_url
            arg = base_url
        else:
            arg = wf_path or "."
        
        cmd = [
            sys.executable,
            "-m", "workforce",
            "gui",
            arg,
            "--foreground"
        ]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=os.getcwd(),
            text=True,
            env=env,
        )
        # Give the child a brief moment to surface immediate errors
        try:
            ret = proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            print(f"GUI launched in background for {wf_path}")
            return

        # If the child exited immediately, surface its output
        output = proc.stdout.read() if proc.stdout else ""
        msg = output.strip() or f"GUI process exited with code {ret}"
        print(f"GUI failed to launch for {wf_path}: {msg}")
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
