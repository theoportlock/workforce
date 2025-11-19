# workforce/server/queue.py
import threading
import queue
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class Task:
    op: str
    args: Dict


class GraphWorker(threading.Thread):
    """Worker that serializes graph modifications.

    Enqueue operations by name (op) and keyword args. Worker will call
    corresponding method on graph_store (e.g. graph_store.add_node(...)).
    """
    def __init__(self, graph_store, socketio, room, daemon=True):
        super().__init__(daemon=daemon)
        self.graph_store = graph_store
        self.socketio = socketio
        self.room = room
        self._queue = queue.Queue()
        self._stopped = threading.Event()


    def enqueue(self, op: str, **kwargs):
        self._queue.put(Task(op=op, args=kwargs))


    def stop(self):
        self._stopped.set()
        self._queue.put(None)


    def run(self):
        print("Graph worker thread started for", self.graph_store.path)
        while not self._stopped.is_set():
            task = self._queue.get()
            if task is None:
                self._queue.task_done()
                break
            try:
                if not hasattr(self.graph_store, task.op):
                    raise AttributeError(f"GraphStore has no op '{task.op}'")
                fn = getattr(self.graph_store, task.op)
                result = fn(**task.args)
                # emit update to connected clients (room == file path)
                try:
                    self.socketio.emit("graph_updated", result, room=self.room)
                except Exception:
                    # don't fail the worker for socket issues
                    pass
            except Exception as e:
                print(f"[ERROR] Graph worker op={task.op}: {e}")
            finally:
                self._queue.task_done()
