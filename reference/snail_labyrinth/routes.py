"""Two vertex-disjoint routes per spawn.

Implements SNAIL_LABYRINTH_TECHNICAL_SPEC.md section 3.2: `MG-7`.

"Two vertex-disjoint routes per spawn in G_T with BLOCK = ROCK union
DEAD_END removed. Vertex-capacitated max-flow >= 2 (node splitting, two BFS
augmentations). This is what survives runtime: rotation cannot remove a
rock, so a spawn on one route can be cut by a single opposing card."

`G_T` (`transit.py`) already excludes Rock and Dead End cells as *interior*
path nodes by construction (`carries()` is false for both at every
rotation, and a Rock's mask is 0 so no edge ever targets or leaves it) --
see `transit.py`'s module docstring and `tests/test_transit.py`. So "with
BLOCK removed" does not change `G_T`'s edge set; the part of `MG-7` that
needs new machinery is the **vertex-disjointness** itself: two routes that
share no common cell, so that one Rock placement (the only mutation that
can ever land on a *generic* cell -- rotation cards don't remove cells)
cannot cut both at once.

## Why a direction-aware node split, not a plain per-cell cap

A naive vertex-capacitated flow over bare *cells* would be wrong here,
because `G_T`'s edges are gated by `carries(mask, entryDir, exitDir)`: a
Straight cell can carry a route North-South or East-West but never a turn,
and which pairing is "available" depends on *which direction the route
entered from*. Capping a cell's total throughput to 1 while still
respecting that per-entry-direction legality needs the cap to sit strictly
*between* "some predecessor arrives at this cell" and "the route resumes
toward a specific exit", with the specific entry direction preserved on
the far side of the cap. This module builds exactly that: for every
not-exempt cell `c`, a single bottleneck edge `arrive_in(c) ->
arrive_out(c)` of capacity 1, with every predecessor edge landing on
`arrive_in(c)` and `arrive_out(c)` fanning back out to the one or more
`(c, entryDir)` nodes a given predecessor's exit direction actually
produces. Since at most 1 unit of flow can ever cross the bottleneck, at
most one `(c, entryDir)` variant ever carries flow in a given max-flow
solution -- which is exactly "this cell is used by at most one route,
entered from exactly one direction in that use."

## Why some cells are exempt from the cap

`HUB` cells (`GE-2`, "untargetable by all six cards"), Spawn Pads (`GE-8`,
likewise untargetable) and each Start-Pad's `ROCK_PROTECTED` inward
neighbour (`GE-8`) can never become a Rock, by rules already stated
elsewhere in the spec (independent of `CD-13`, not yet implemented). A
vertex-disjointness constraint exists only to defend against a single Rock
cutting both routes (`MG-7`'s own stated rationale) -- there is nothing to
defend a cell against if no card can ever place a Rock on it, so these
cells are given unlimited capacity rather than the shared cap, and are
excluded from the cell fraction the generator budgets against (consistent
with `MG-17`'s own "protected from rocks" list, which names exactly this
set). See `reference/OPEN_QUESTIONS.md` for the reasoning recorded as an
explicit choice, since the spec states the cap mechanism ("node splitting")
but not which cells it should or should not apply to.
"""

from __future__ import annotations

from collections import deque
from typing import Iterable, Optional, Set

from .flow import FlowNetwork
from .geometry import hub_cells, spawns, start_pad_inward_neighbour
from .tiles import Board, GridPos
from .transit import TransitGraph, TransitNode

SOURCE = ("SOURCE",)
SINK = ("SINK",)

# Large enough that it is never the binding constraint for any board size
# this project targets (max board is 24x24 = 576 cells); used as a stand-in
# for "unlimited" on exempt cells, rather than a literal unbounded capacity,
# to keep the flow network's capacities plain finite integers throughout.
_UNLIMITED = 10**6


def _arrive_in(cell: GridPos):
    return ("AI", cell)


def _arrive_out(cell: GridPos):
    return ("AO", cell)


def _dir_node(node: TransitNode):
    return ("D", node.cell, node.entry_dir)


def exempt_cells(n: int) -> Set[GridPos]:
    """Cells that can never carry a Rock, so need no vertex cap: Hub cells
    (`GE-2`), Spawn Pads (`GE-8`), and each Start Pad's `ROCK_PROTECTED`
    inward neighbour (`GE-8`). See the module docstring.
    """
    cells: Set[GridPos] = set(hub_cells(n))
    cells.update(spawns(n))
    for k in range(4):
        cells.add(start_pad_inward_neighbour(n, k))
    return cells


def has_two_vertex_disjoint_routes(
    board: Board,
    spawn_cell: GridPos,
    hub_cells_: Iterable[GridPos],
    exempt: Optional[Iterable[GridPos]] = None,
) -> bool:
    """`MG-7`: is there vertex-capacitated max-flow >= 2 from `spawn_cell` to
    any Hub cell over `G_T`, where every not-exempt cell has capacity 1?

    Builds the flow network by walking the same edges `TransitGraph` already
    exposes (`first_departures`, `edges_from`) -- this does not duplicate
    `G_T`'s own BLOCK-exclusion or carries-gating logic, it only wraps each
    destination cell in the direction-aware node-split bottleneck described
    in the module docstring.

    `exempt` defaults to the real `GE-1`/`GE-5`/`GE-8` geometry for
    `board.n` (via `exempt_cells`); a caller may override it with a
    synthetic cell set for focused testing of the flow network in
    isolation, the same pattern `repair.repair_dead_ends` uses for `hub`
    and `spawn_cells`.
    """
    hub_set = set(hub_cells_)
    exempt = set(exempt) if exempt is not None else exempt_cells(board.n)
    net = FlowNetwork()
    tg = TransitGraph(board)

    def arrival_cap(cell: GridPos) -> int:
        return _UNLIMITED if cell in exempt else 1

    seen_arrival: Set[GridPos] = set()
    seen_nodes: Set[TransitNode] = set()
    queue: deque = deque()

    def land(node: TransitNode) -> None:
        """Wire `arrive_in(node.cell) -> arrive_out(node.cell) -> dir_node`
        (creating the bottleneck once per cell) and enqueue `node` for its
        own onward edges, the first time it is seen."""
        if node.cell not in seen_arrival:
            net.add_edge(_arrive_in(node.cell), _arrive_out(node.cell), arrival_cap(node.cell))
            seen_arrival.add(node.cell)
        net.add_edge(_arrive_out(node.cell), _dir_node(node), 1)
        if node not in seen_nodes:
            seen_nodes.add(node)
            if node.cell in hub_set:
                # Reaching the Hub is never itself a shared, limited
                # resource -- the real disjointness decision already
                # happened at the arrival bottleneck one step upstream.
                # Without this, two routes that happen to converge on the
                # exact same (hub_cell, entryDir) for their final hop (a
                # real, legitimate case: the Hub has only 8 outward edges
                # total, GE-4) would be falsely capped at 1 here even when
                # every actually-rockable cell along both routes is
                # distinct.
                net.add_edge(_dir_node(node), SINK, _UNLIMITED)
            else:
                queue.append(node)

    for node, _d in tg.first_departures(spawn_cell):
        net.add_edge(SOURCE, _arrive_in(node.cell), 1)
        land(node)

    while queue:
        node = queue.popleft()
        for nxt, _d in tg.edges_from(node):
            net.add_edge(_dir_node(node), _arrive_in(nxt.cell), 1)
            land(nxt)

    flow = net.max_flow_at_least(SOURCE, SINK, 2)
    return flow >= 2
