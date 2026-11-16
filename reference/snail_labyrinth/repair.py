"""Dead-end repair.

Implements SNAIL_LABYRINTH_TECHNICAL_SPEC.md section 3.3: `MG-18`.

"A 10% dead-end field alone seals spawns, because a Dead End is a soft rock
(TM-11). While any spawn is disconnected in the BLOCK-free graph, convert
the frontier dead-end nearest the Hub component (deterministic hash order)
to a TEE. Repeat."

The "BLOCK-free graph" here (`BLOCK = ROCK union DEAD_END`, `MG-7`) is
deliberately plain, *current* 4-connectivity (`Board.connected`, `TM-8`) over
non-BLOCK cells -- not `TransitGraph`/`G_T`. This is not an oversight: it
measures whether the board is connected *as currently oriented*, ignoring
whether a misoriented Straight/Elbow/Tee/Cross could later be rotated into
place. That is a *stronger* requirement than `MG-6`'s `G_T` reachability,
and it is also why this repair can legitimately fail to fully connect a
board on its own -- a spawn stranded purely behind misoriented (but not
Dead-End) tiles needs `MG-19`'s re-orientation repair, not this rule. See
`reference/PROGRESS.md` and `reference/OPEN_QUESTIONS.md` (OQ-7, OQ-8).
"""

from __future__ import annotations

from collections import deque
from typing import Dict, FrozenSet, Iterable, List, NamedTuple, Optional, Set

from .geometry import hub_cells, spawns
from .rng import cell_hash
from .tiles import ALL_DIRS, Board, GridPos, Shape, delta, opp, shape_of

# MG-7/MG-18: "BLOCK = ROCK union DEAD_END". A Dead End is excluded as a
# vertex of this graph exactly like a Rock -- "a soft rock" (TM-11) -- no
# matter which single direction it happens to open in right now.
BLOCKED_SHAPES = (Shape.ROCK, Shape.DEAD_END)

# MG-20's "never an unbounded loop" ethos, applied here: a hard cap on
# repair steps so a pathological board cannot spin this loop forever. One
# repair step strictly grows the Hub component by at least one cell, so
# n*n steps is already far more generous than any real board needs.
_MAX_REPAIR_STEPS_FACTOR = 1


def is_blocked(board: Board, cell: GridPos) -> bool:
    """MG-7/MG-18: is `cell` excluded as a vertex of the BLOCK-free graph?"""
    return shape_of(board.mask_at(cell)) in BLOCKED_SHAPES


def block_free_component(board: Board, sources: Iterable[GridPos]) -> Set[GridPos]:
    """MG-18: the set of cells reachable from `sources` by plain, *current*
    mutual connectivity (`TM-8`), over non-BLOCK cells only. Deliberately
    not `TransitGraph`/`G_T` -- see module docstring.
    """
    component: Set[GridPos] = set()
    queue: deque = deque()
    for s in sources:
        if is_blocked(board, s):
            continue
        if s not in component:
            component.add(s)
            queue.append(s)
    while queue:
        cell = queue.popleft()
        for d in ALL_DIRS:
            if not board.connected(cell, d):
                continue
            neighbour = cell + delta(d)
            if is_blocked(board, neighbour):
                continue
            if neighbour not in component:
                component.add(neighbour)
                queue.append(neighbour)
    return component


class FrontierDeadEnd(NamedTuple):
    """A Dead End cell that is the actual boundary of `component`: at least
    one member of `component` already has an opening pointing at this cell
    (a one-sided opening, `TM-8`) that the Dead End does not reciprocate.
    `required_dirs` is every direction the repaired Tee must open to honour
    both that pressure and the Dead End's own pre-existing single opening.
    """

    cell: GridPos
    required_dirs: FrozenSet[int]


def find_frontier_dead_ends(board: Board, component: Set[GridPos]) -> List[FrontierDeadEnd]:
    """MG-18's "frontier dead-end[s]": Dead End cells adjacent to
    `component` where a component member already opens toward them. A Dead
    End merely *sitting* next to the component, with no neighbour actually
    pressing an opening against it, is not a frontier cell -- there would be
    nothing yet for converting it to connect to.
    """
    required: Dict[GridPos, Set[int]] = {}
    for u in component:
        mask_u = board.mask_at(u)
        for d in ALL_DIRS:
            if not (mask_u & d):
                continue
            neighbour = u + delta(d)
            if not board.in_bounds(neighbour):
                continue
            if neighbour in component:
                continue
            if shape_of(board.mask_at(neighbour)) != Shape.DEAD_END:
                continue
            # u opens toward `neighbour`; from the dead end's own side, the
            # direction pointing back at u is opp(d).
            required.setdefault(neighbour, set()).add(opp(d))

    result: List[FrontierDeadEnd] = []
    for cell, dirs in required.items():
        existing = board.mask_at(cell)  # a Dead End's single-bit mask
        result.append(FrontierDeadEnd(cell, frozenset(dirs | {existing})))
    return result


def choose_repair_mask(required_dirs: FrozenSet[int]) -> int:
    """MG-18: "convert ... to a TEE" -- a Tee has exactly 3 openings.

    `required_dirs` holds the Dead End's own pre-existing opening plus every
    direction some component neighbour already presses toward it (0 to 4
    directions; see `find_frontier_dead_ends`).

    - Fewer than 3 required: the spare opening(s) are filled in fixed
      N,E,S,W priority order (deterministic, independent of the hash order
      used to pick *which* cell to repair).
    - Exactly 3 required: the result is forced.
    - All 4 required (every side already presses on this one cell -- rare,
      but possible): no Tee can satisfy all 4, so the lowest-priority
      direction in N,E,S,W order is dropped. See OPEN_QUESTIONS.md OQ-8.
    """
    chosen = [d for d in ALL_DIRS if d in required_dirs]
    if len(chosen) > 3:
        chosen = chosen[:3]
    else:
        for d in ALL_DIRS:
            if len(chosen) >= 3:
                break
            if d not in chosen:
                chosen.append(d)
    mask = 0
    for d in chosen:
        mask |= d
    return mask


class RepairOutcome(NamedTuple):
    """`steps`: how many Dead Ends were converted. `fully_connected`: did
    every spawn end up in the Hub's BLOCK-free component? `False` is a
    legitimate outcome, not a bug -- see `repair_dead_ends`'s docstring.
    """

    steps: int
    fully_connected: bool


def repair_dead_ends(
    board: Board,
    root_key: int,
    hub: Optional[Iterable[GridPos]] = None,
    spawn_cells: Optional[Iterable[GridPos]] = None,
) -> RepairOutcome:
    """MG-18. Mutates `board` in place.

    Loop: compute the Hub's BLOCK-free component; if every spawn is in it,
    stop (success). Otherwise collect every frontier Dead End, order them
    deterministically by `CellHash("repair", x, y)` (MG-18's "deterministic
    hash order" -- see OPEN_QUESTIONS.md OQ-7 for why a stateless per-cell
    hash was used here rather than MG-24's sequential "repair" stream), and
    convert the lowest-hash one to a Tee (`choose_repair_mask`). Repeat.

    Every frontier Dead End found here is, by construction, exactly one
    step away from `component` (`find_frontier_dead_ends` only looks at
    `component`'s immediate neighbours) -- so every candidate is tied for
    "nearest" and the hash order is the whole selection rule, matching the
    spec's own parenthetical.

    If no frontier Dead End remains and some spawn is still outside the
    component, the loop stops there and reports `fully_connected=False`:
    that spawn is stranded by misoriented non-Dead-End tiles, which is
    `MG-19`'s job, not this rule's (module docstring).

    `hub` and `spawn_cells` default to the real `GE-1`/`GE-5` geometry for
    `board.n`; a caller may override either with a synthetic cell set for
    focused testing of the repair loop in isolation.
    """
    n = board.n
    if hub is None:
        hub = hub_cells(n)
    if spawn_cells is None:
        spawn_cells = spawns(n)
    hub = list(hub)
    spawn_cells = list(spawn_cells)
    max_steps = n * n * _MAX_REPAIR_STEPS_FACTOR
    steps = 0

    while steps < max_steps:
        component = block_free_component(board, hub)
        if all(s in component for s in spawn_cells):
            return RepairOutcome(steps, True)
        frontier = find_frontier_dead_ends(board, component)
        if not frontier:
            return RepairOutcome(steps, False)
        frontier.sort(key=lambda f: cell_hash(root_key, "repair", f.cell.x, f.cell.y))
        target = frontier[0]
        board.set_mask(target.cell, choose_repair_mask(target.required_dirs))
        steps += 1

    component = block_free_component(board, hub)
    return RepairOutcome(steps, all(s in component for s in spawn_cells))
