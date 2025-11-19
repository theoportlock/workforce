# workforce/server/tasks.py
import threading

from workforce.run import main as run_full_pipeline
from workforce.run import run_node as run_single_node


def run_pipeline_async(graph_url: str, prefix: str = "", suffix: str = ""):
    def _bg():
        try:
            run_full_pipeline(graph_url, prefix, suffix)
        except Exception as e:
            print("[ERROR] run_pipeline:", e)

    threading.Thread(target=_bg, daemon=True).start()


def run_node_async(graph_url: str, node: str, prefix: str = "", suffix: str = ""):
    def _bg():
        try:
            run_single_node(graph_url, node, prefix, suffix)
        except Exception as e:
            print("[ERROR] run_node:", e)

    threading.Thread(target=_bg, daemon=True).start()
