# diagnostics.py
import time
from collections import defaultdict

class Diagnostics:
    def __init__(self):
        self.wait_graph = defaultdict(set)
        self.last_access = {}
        self.alert = ""

    def add_wait(self, waiter, owner):
        self.wait_graph[waiter].add(owner)
        self.check_deadlock()

    def remove_wait(self, waiter):
        self.wait_graph.pop(waiter, None)
        self.check_deadlock()

    def check_deadlock(self):
        visited, path = set(), []

        def dfs(node):
            if node in path:
                cycle = path[path.index(node):] + [node]
                self.alert = f"DEADLOCK: {' → '.join(f'P{p}' for p in cycle)}"
                return True
            if node in visited: return False
            visited.add(node)
            path.append(node)
            for neigh in self.wait_graph.get(node, []):
                if dfs(neigh): return True
            path.pop()
            return False

        self.alert = ""
        for n in list(self.wait_graph.keys()):
            if dfs(n): return

    def update_access(self, pid):
        self.last_access[pid] = time.time()

    def get_bottlenecks(self):
        now = time.time()
        idle = [p for p,t in self.last_access.items() if now-t>2.0]
        return f"Idle: {', '.join(f'P{p}' for p in idle)}" if idle else ""