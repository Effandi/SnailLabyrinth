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

import heapq
from collections import deque
from typing import Dict, Iterable, List, NamedTuple, Optional, Set, Tuple

from .tiles import ALL_DIRS, Board, GridPos, cw, delta, opp, orbit


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

    def weighted_edges_from(self, node: TransitNode) -> List[Tuple[TransitNode, int, int]]:
        """MG-2: `edgeCost = TAU[v][a][b] + STEP_MILLI`, for an interior node.

        Same edge set as `edges_from` (every edge here is `carries`-gated,
        exactly like the unweighted graph), but each candidate is reported
        with its two cost components kept apart, in milli-units:
        `(next_node, tau_milli, STEP_MILLI)`. `tau_milli` is the cheapest
        rotation-card cost, if any rotation of this tile can expose both the
        entry (`a`) and exit (`b`) openings at once; a tile whose shape can
        never carry that pair contributes no edge at all, same as `carries`
        gates the unweighted graph.
        """
        v, a = node.cell, node.entry_dir
        mask_v = self.board.mask_at(v)
        result: List[Tuple[TransitNode, int, int]] = []
        for b in ALL_DIRS:
            if b == a:
                continue
            cost = tau_milli(mask_v, a, b)
            if cost is None:
                continue
            u = v + delta(b)
            if self.board.mask_at(u) == 0:
                continue
            result.append((TransitNode(u, opp(b)), cost, STEP_MILLI))
        return result

    def solve_cost(self, spawn_cell: GridPos, hub_cells: Iterable[GridPos]) -> Optional["SolveCost"]:
        """MG-2/MG-3: `SolveCost(s)`, the shortest-path distance in `G_T` from
        `spawn_cell`'s departures to any Hub cell (`sink = any (c, .) with c
        in HUB`), decomposed into the `(R, L)` pair the spec defines (kept as
        integer milli-units throughout, per MG-2: "all generator arithmetic
        is integer").

        The very first hop uses `first_departures` (`TM-12 source()`,
        OPEN_QUESTIONS.md OQ-1) and is treated as free in `R`: the snail is
        departing its own resting cell, not passing through it under a fixed
        rotation, so there is no entry/exit pair on that cell to price. Every
        hop after that is `weighted_edges_from`'s literal `TAU + STEP_MILLI`.

        This runs one Dijkstra per spawn rather than MG-3's "one reverse
        Dijkstra from the Hub yields all four spawn costs simultaneously" --
        that is a performance optimisation for the generation loop (`§3.3`),
        not a correctness requirement; see `reference/PROGRESS.md`.

        Returns `None` if no route exists (`MG-6` fails for this spawn).
        """
        hub = set(hub_cells)
        if spawn_cell in hub:
            return SolveCost(0, 0)

        # node -> (priority_milli, r_milli, l_milli) of the best entry found so far.
        best: Dict[TransitNode, Tuple[int, int, int]] = {}
        heap: List[Tuple[int, TransitNode, int, int]] = []

        def offer(node: TransitNode, priority: int, r_milli: int, l_milli: int) -> None:
            prior = best.get(node)
            if prior is not None and prior[0] <= priority:
                return
            best[node] = (priority, r_milli, l_milli)
            heapq.heappush(heap, (priority, node, r_milli, l_milli))

        for node, _d in self.first_departures(spawn_cell):
            if node.cell in hub:
                return SolveCost(0, STEP_MILLI)
            offer(node, STEP_MILLI, 0, STEP_MILLI)

        while heap:
            priority, node, r_milli, l_milli = heapq.heappop(heap)
            if best.get(node) != (priority, r_milli, l_milli):
                continue  # stale entry superseded by a cheaper one
            if node.cell in hub:
                return SolveCost(r_milli, l_milli)
            for nxt, tau_cost, step_cost in self.weighted_edges_from(node):
                offer(nxt, priority + tau_cost + step_cost, r_milli + tau_cost, l_milli + step_cost)
        return None


# MG-2: "milli-card-actions for a Delta-quarter-turn; Delta=2 costs 1.6
# because ANY does it in one card." These are authored constants from the
# spec table, not derived.
ACT_MILLI: Dict[int, int] = {0: 0, 1: 1000, 2: 1600, 3: 1000}

# MG-2: "one tile = 1 cost unit".
STEP_MILLI: int = 1000


def tau_milli(mask: int, a: int, b: int) -> Optional[int]:
    """MG-2: `TAU[c][a][b] = min over o of ACT[(o - ori(c)) mod 4] where
    MASK[shape(c)][o] ⊇ {a,b}`, re-expressed directly over quarter-turn
    deltas from the cell's *current* mask.

    This is exactly the literal formula, not an approximation of it: for any
    `o`, `MASK[shape(c)][o] == cw^o(canonical reference mask)`, and `ori(c)`
    is defined by `cw^ori(c)(canonical) == mask[c]`; substituting, `MASK[
    shape(c)][o]` evaluated at `Delta = (o - ori(c)) mod 4` is `cw^Delta(
    mask[c])` for every `o`, so letting `Delta` itself range over `0..3`
    (instead of `o`) requires no canonical-orientation or `ori()` bookkeeping
    at all. See `reference/OPEN_QUESTIONS.md` OQ-3 for the full derivation.

    Returns `None` if the shape can never carry `{a, b}` (`carries(mask, a,
    b)` is false at every rotation) -- `TAU` is infinite in exactly that case.
    """
    best: Optional[int] = None
    cur = mask & 0xF
    for delta_turns in range(4):
        if (cur & a) and (cur & b):
            cost = ACT_MILLI[delta_turns]
            if best is None or cost < best:
                best = cost
        cur = cw(cur)
    return best


class SolveCost(NamedTuple):
    """MG-2: the `(R, L)` pair -- card-actions and tiles -- plus the derived
    scalar `C = 2*R + L`. Kept in integer milli-units throughout so every
    comparison in `MG-8`/`MG-11`/`MG-14` (a later increment) stays exact,
    per MG-2's "all generator arithmetic is integer"; nothing here is a
    float. `MG-4` warns `C` is *never* reported as seconds -- it is a
    relative fairness measure.
    """

    r_milli: int
    l_milli: int

    @property
    def c_milli(self) -> int:
        """MG-2: scalar `C = 2*R + L`, in integer milli cost units."""
        return 2 * self.r_milli + self.l_milli

    @property
    def tiles(self) -> int:
        """`L`, as a plain tile count (`l_milli` is always a multiple of
        `STEP_MILLI`)."""
        return self.l_milli // STEP_MILLI
