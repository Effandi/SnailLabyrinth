"""The transit graph G_T. Spec: TM-11, TM-12.

Plain 4-connectivity over non-Rock cells is not a sufficient reachability
test: a Straight cannot turn and a Dead End cannot pass through at any
rotation, so naive open-cell connectivity passes boards that are actually
unsolvable by rotation cards alone. Every reachability guarantee in the
spec (MG-6, AS-2, CD-13 condition 6) is instead a BFS over G_T.

Nodes are `(cell, entryDir)` pairs: `entryDir` is the opening direction a
snail would be using to be present at `cell` (either the opening it just
arrived through, or, for a `source` node, an opening the cell could be
rotated to present). This module is deliberately independent of board
geometry (GE-*/MG-*): callers supply the board and a `is_sink` predicate.
"""

from __future__ import annotations

from collections import deque
from typing import Callable, Iterable

from .board import Board, GridPos
from .directions import ALL_DIRS, DELTA, opp, orbit

Node = tuple[GridPos, int]  # (cell, entryDir)


def carries(board: Board, cell: GridPos, a: int, b: int) -> bool:
    """TM-12: does some rotation of the tile at `cell` have both `a` and `b`
    open simultaneously? `a != b`, both single-bit directions. Depends only
    on shape, not current orientation: orientation is always fixable by
    rotation cards, topology is not."""
    x, y = cell
    m = board.mask_at(x, y)
    return any((o & a) and (o & b) for o in orbit(m))


def source_nodes(board: Board, cell: GridPos) -> set[Node]:
    """TM-12: `source(s) = {(s.cell, d) : exists m in orbit(mask[s.cell]) with (m & d)}`.
    The snail is already on its cell; every direction some rotation of that
    cell could open is a valid starting node."""
    x, y = cell
    m = board.mask_at(x, y)
    o = orbit(m)
    return {(cell, d) for d in ALL_DIRS if any(om & d for om in o)}


def neighbors(board: Board, node: Node) -> Iterable[Node]:
    """TM-12: `edge (v,a) --b--> (u, opp(b))` for `u = v + delta(b)`,
    `mask[u] != 0`, `carries(v, a, b)`."""
    v, a = node
    vx, vy = v
    for b in ALL_DIRS:
        if b == a:
            continue
        if not carries(board, v, a, b):
            continue
        dx, dy = DELTA[b]
        u = (vx + dx, vy + dy)
        if board.mask_at(*u) == 0:
            continue
        yield (u, opp(b))


def bfs_transit(
    board: Board,
    starts: Iterable[Node],
    is_sink: Callable[[GridPos], bool],
) -> tuple[bool, set[Node]]:
    """One BFS over G_T. Returns `(reached_sink, visited_nodes)`.

    `is_sink(cell)` should be true for any cell counted as the goal (e.g.
    Hub cells, GE-2); any `entryDir` at such a cell counts as reaching it,
    since the Hub is forced to mask 15 (always fully passable).
    """
    visited: set[Node] = set(starts)
    queue: deque[Node] = deque(starts)
    for node in starts:
        if is_sink(node[0]):
            return True, visited
    while queue:
        node = queue.popleft()
        for nxt in neighbors(board, node):
            if nxt in visited:
                continue
            visited.add(nxt)
            if is_sink(nxt[0]):
                return True, visited
            queue.append(nxt)
    return False, visited


def is_solvable(board: Board, spawn_cell: GridPos, is_sink: Callable[[GridPos], bool]) -> bool:
    """`MG-6`: `SolveCost(s) < infinity`, as a boolean reachability check —
    "is this board still solvable by rotation cards alone?" (TM-12)."""
    reached, _ = bfs_transit(board, source_nodes(board, spawn_cell), is_sink)
    return reached
