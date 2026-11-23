"""A small generic max-flow primitive (Edmonds-Karp: BFS augmenting paths),
used by `routes.py` for `MG-7`'s "vertex-capacitated max-flow >= 2 (node
splitting, two BFS augmentations)".

Deliberately generic over opaque, hashable node identifiers -- it knows
nothing about cells, directions, or the transit graph. `routes.py` is
responsible for building a network out of those concepts; this module only
answers "what is the max flow from `source` to `sink`, stopping once it
reaches `target`".
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, Hashable, List, Optional, Set, Tuple


class FlowNetwork:
    """A directed capacitated graph with on-demand reverse residual edges."""

    def __init__(self) -> None:
        self._cap: Dict[Tuple[Hashable, Hashable], int] = defaultdict(int)
        self._adj: Dict[Hashable, Set[Hashable]] = defaultdict(set)

    def add_edge(self, u: Hashable, v: Hashable, capacity: int = 1) -> None:
        """Adds `capacity` to the existing u->v capacity (edges between the
        same pair accumulate, matching how a caller may legitimately
        discover the same logical edge more than once while building a
        network from several predecessors)."""
        if capacity < 0:
            raise ValueError("capacity must be non-negative")
        self._cap[(u, v)] += capacity
        self._cap.setdefault((v, u), 0)  # ensure a residual slot exists
        self._adj[u].add(v)
        self._adj[v].add(u)

    def _bfs_augmenting_path(self, source: Hashable, sink: Hashable) -> Optional[List[Hashable]]:
        if source == sink:
            return [source]
        parent: Dict[Hashable, Optional[Hashable]] = {source: None}
        queue: deque = deque([source])
        while queue:
            u = queue.popleft()
            if u == sink:
                break
            for v in self._adj.get(u, ()):
                if v in parent:
                    continue
                if self._cap[(u, v)] <= 0:
                    continue
                parent[v] = u
                queue.append(v)
        if sink not in parent:
            return None
        path = [sink]
        node = sink
        while parent[node] is not None:
            node = parent[node]  # type: ignore[assignment]
            path.append(node)
        path.reverse()
        return path

    def max_flow_at_least(self, source: Hashable, sink: Hashable, target: int) -> int:
        """Runs Edmonds-Karp (BFS augmenting paths), stopping as soon as
        `target` units of flow have been pushed. Returns the flow actually
        achieved, which equals the true max-flow whenever that max-flow is
        below `target` (i.e. the caller only gets a value `< target` when
        that value really is the ceiling, never a false "stopped early").
        `MG-7` only ever needs `target=2`, hence "two BFS augmentations".
        """
        if source == sink:
            return target  # degenerate: trivially satisfied, no edges needed
        flow = 0
        while flow < target:
            path = self._bfs_augmenting_path(source, sink)
            if path is None:
                break
            bottleneck = min(self._cap[(path[i], path[i + 1])] for i in range(len(path) - 1))
            for i in range(len(path) - 1):
                u, v = path[i], path[i + 1]
                self._cap[(u, v)] -= bottleneck
                self._cap[(v, u)] += bottleneck
            flow += bottleneck
        return flow
