"""The transit graph G_T: reachability over (cell, entryDir) pairs.

Implements spec section 1.4 (TM-11, TM-12): SNAIL_LABYRINTH_TECHNICAL_SPEC.md.

Plain 4-connectivity over non-Rock cells is NOT a sufficient reachability
test: a Straight can never turn and a Dead End can never pass through at any
rotation (it is a soft rock). Every reachability guarantee elsewhere in the
spec (MG-6, AS-2, CD-13) is a BFS over this graph, not over the open-cell
grid.
"""

from collections import defaultdict, deque

from .tiles import DIRS, DELTA, opp, orbit


def carries(mask, a, b):
    """TM-12: carries(c, a, b) = exists m in orbit(mask[c]) : (m & a) and (m & b).
    a != b, both single-bit directions. Depends only on shape (via orbit), not
    on current orientation -- orientation is always fixable by rotation cards."""
    for m in orbit(mask):
        if (m & a) and (m & b):
            return True
    return False


def build_graph(grid):
    """TM-12: nodes are (cell, entryDir); 4*N^2 nodes.

    edge (v,a) --b--> (u, opp(b))  for u = v + delta(b), mask[u] != 0, carries(v,a,b)

    Returns dict[(cell, entryDir)] -> list[(cell, entryDir)].
    """
    adjacency = defaultdict(list)
    for y in range(grid.n):
        for x in range(grid.n):
            mv = grid.mask_at(x, y)
            if mv == 0:
                # A Rock never carries any pair (orbit(0) == (0,)); no edges
                # ever leave it, so skip the cell entirely.
                continue
            for a in DIRS:
                for b in DIRS:
                    if a == b:
                        continue
                    if not carries(mv, a, b):
                        continue
                    dx, dy = DELTA[b]
                    ux, uy = x + dx, y + dy
                    if grid.mask_at(ux, uy) == 0:
                        # TM-12 requires mask[u] != 0. Off-grid is mask 0 (TM-9),
                        # so the border is never a valid edge target either.
                        continue
                    adjacency[((x, y), a)].append(((ux, uy), opp(b)))
    return adjacency


def source_nodes(grid, cell):
    """TM-12: source(s) = { (s.cell, d) : exists m in orbit(mask[s.cell]) with (m & d) }.
    The snail is already on its cell; any direction achievable as an opening
    under some rotation is a valid virtual entry label."""
    x, y = cell
    m = grid.mask_at(x, y)
    return [(cell, d) for d in DIRS if any(mm & d for mm in orbit(m))]


def reachable_nodes(grid, source_cells):
    """BFS over G_T from the union of source_nodes(cell) for cell in source_cells.
    Returns the set of visited (cell, entryDir) nodes."""
    graph = build_graph(grid)
    start = []
    for cell in source_cells:
        start.extend(source_nodes(grid, cell))
    visited = set(start)
    queue = deque(start)
    while queue:
        node = queue.popleft()
        for nxt in graph.get(node, ()):
            if nxt not in visited:
                visited.add(nxt)
                queue.append(nxt)
    return visited


def is_reachable(grid, source_cell, sink_cells):
    """TM-12: sink = any (c, ...) with c in sink_cells. One BFS over G_T answers
    "is this board still solvable by rotation cards alone?" (MG-6, AS-2, CD-13)."""
    sink_set = set(sink_cells)
    visited = reachable_nodes(grid, [source_cell])
    return any(cell in sink_set for cell, _ in visited)
