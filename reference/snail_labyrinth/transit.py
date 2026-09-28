"""The transit graph.

Implements SNAIL_LABYRINTH_TECHNICAL_SPEC.md section 1.4: TM-11, TM-12.

Plain 4-connectivity over non-Rock cells (`Board.usable_exits`) is not a
sufficient reachability test (TM-11): a Straight can never turn and a Dead
End can never be passed through, at any rotation. The transit graph G_T
answers "is this board still solvable by rotation cards alone?" by making
nodes out of (cell, entryDir) pairs rather than bare cells.

See reference/OPEN_QUESTIONS.md for the one interpretive decision this
module had to make (how `source(s)` feeds into the edge rule for a Dead
End origin).
"""

from __future__ import annotations

from collections import deque
from typing import Dict, Iterable, List, NamedTuple, Set, Tuple

from .tiles import ALL_DIRS, Board, GridPos, delta, opp, orbit


class TransitNode(NamedTuple):
    """A node of G_T: `cell` entered through the opening facing `entry_dir`."""

    cell: GridPos
    entry_dir: int


def carries(mask: int, a: int, b: int) -> bool:
    """TM-12: true iff some rotation of `mask` carries a path between the two
    distinct single-bit directions `a` and `b`.

    Depends only on shape, not on the tile's current orientation: orientation
    is always fixable by rotation cards, topology is not (TM-12).
    """
    for m in orbit(mask):
        if (m & a) and (m & b):
            return True
    return False


class TransitGraph:
    """TM-12. Built lazily against a `Board`; `carries` reads the board's
    mask at query time, so no explicit rebuild is needed after a mutation.
    """

    def __init__(self, board: Board) -> None:
        self.board = board

    def first_departures(self, cell: GridPos) -> List[Tuple[TransitNode, int]]:
        """TM-12 `source(s)`: the snail is already on `cell`, not having
        entered it along a graph edge, so departure needs no `carries` pairing
        with an "entry" side -- only that *some* rotation of this tile opens
        toward the chosen direction. See OPEN_QUESTIONS.md for why this
        differs from feeding `source()`'s bare (cell, d) pairs into the same
        carries-gated rule used for interior nodes.

        Returns [(node_after_the_hop, direction_taken)].
        """
        m = self.board.mask_at(cell)
        dirs: Set[int] = set()
        for rotated in orbit(m):
            for d in ALL_DIRS:
                if rotated & d:
                    dirs.add(d)
        result: List[Tuple[TransitNode, int]] = []
        for d in dirs:
            u = cell + delta(d)
            if self.board.mask_at(u) == 0:
                continue
            result.append((TransitNode(u, opp(d)), d))
        return result

    def edges_from(self, node: TransitNode) -> List[Tuple[TransitNode, int]]:
        """TM-12 `edge (v,a) --b--> (u, opp(b))`, for an interior node already
        carrying a real entry direction `a`.

        Returns [(next_node, direction_taken)].
        """
        v, a = node.cell, node.entry_dir
        mask_v = self.board.mask_at(v)
        result: List[Tuple[TransitNode, int]] = []
        for b in ALL_DIRS:
            if b == a:
                continue
            if not carries(mask_v, a, b):
                continue
            u = v + delta(b)
            if self.board.mask_at(u) == 0:
                continue
            result.append((TransitNode(u, opp(b)), b))
        return result

    def reachable_to_hub(self, start_cell: GridPos, hub_cells: Iterable[GridPos]) -> bool:
        """MG-6 / CD-13 condition 6: BFS over G_T from `start_cell` to any Hub
        cell. `sink = any (c, .) with c in HUB` (TM-12): reaching any node
        whose cell is in HUB, regardless of entry direction, is success.
        """
        hub = set(hub_cells)
        if start_cell in hub:
            return True
        seen: Set[TransitNode] = set()
        queue: deque = deque()
        for node, _via in self.first_departures(start_cell):
            if node.cell in hub:
                return True
            if node not in seen:
                seen.add(node)
                queue.append(node)
        while queue:
            node = queue.popleft()
            for nxt, _via in self.edges_from(node):
                if nxt.cell in hub:
                    return True
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return False

    def reachable_node_set(self, start_cell: GridPos) -> Set[TransitNode]:
        """All G_T nodes reachable from `start_cell`'s departures. Exposed for
        tests and for future callers (e.g. k-shortest-path guarantees, MG-9)
        that need the full reachable set rather than a single yes/no.
        """
        seen: Set[TransitNode] = set()
        queue: deque = deque()
        for node, _via in self.first_departures(start_cell):
            if node not in seen:
                seen.add(node)
                queue.append(node)
        while queue:
            node = queue.popleft()
            for nxt, _via in self.edges_from(node):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return seen
