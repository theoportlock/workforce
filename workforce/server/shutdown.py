import logging
import threading
import os
import signal
from workforce import utils

log = logging.getLogger(__name__)


def shutdown_if_idle(ctx):
    """Stop the server when no clients are connected and no runs are active."""
    try:
        if not getattr(ctx, "socketio", None):
            log.debug("No socketio instance available for shutdown check")
            return
        
        entry = utils.get_registry_entry(ctx.path) or {}
        clients = int(entry.get("clients", 0) or 0)
        has_runs = bool(getattr(ctx, "active_runs", {}))
        
        log.info(f"Shutdown check: clients={clients}, active_runs={has_runs}")
        
        if clients <= 0 and not has_runs:
            log.info("No clients and no active runs; scheduling server shutdown in 1s")
            # Use background thread to defer shutdown, avoiding issues with stopping from request context
            def _deferred_stop():
                import time
                time.sleep(1.0)  # Brief grace period for response to complete
                log.info("Executing deferred server shutdown")
                try:
                    # Try multiple shutdown methods for reliability
                    log.info("Attempting socketio.stop()...")
                    ctx.socketio.stop()
                    time.sleep(0.5)
                    
                    # If still running, use signal
                    log.info("Sending SIGTERM to self...")
                    os.kill(os.getpid(), signal.SIGTERM)
                except Exception as e:
                    log.error(f"Shutdown failed: {e}, forcing exit")
                    os._exit(0)
            
            thread = threading.Thread(target=_deferred_stop, daemon=False)
            thread.start()
        else:
            log.info("Server still needed: clients or runs active")
    except Exception:
        log.exception("Failed to evaluate idle shutdown condition")
