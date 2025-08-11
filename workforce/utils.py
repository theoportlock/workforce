import networkx as nx
from filelock import FileLock

class GraphMLAtomic:
    def __init__(self, filename):
        self.filename = filename
        self.lock = FileLock(f"{filename}.lock")
        self._modified = False

    def __enter__(self):
        self.lock.acquire()
        try:
            self.G = nx.read_graphml(self.filename)
        except FileNotFoundError:
            self.G = nx.DiGraph()
        return self

    def mark_modified(self):
        self._modified = True

    def __exit__(self, exc_type, exc_value, traceback):
        if self._modified:
            nx.write_graphml(self.G, self.filename)
        self.lock.release()
