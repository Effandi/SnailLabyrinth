"""Board geometry: the Hub, the Apron, the four spawns, and Start Pads.

Implements SNAIL_LABYRINTH_TECHNICAL_SPEC.md section 2: GE-1 .. GE-8.

Under D2 (DECISIONS.md) there are no teams: four spawns, exactly one per
side, and `playerSlot k` occupies `S[k]` with the side <-> player mapping
being the identity. This module only computes the geometry; wiring the
untargetable-by-all-cards and finished-on-entry rules (GE-2) is a `CD-*` /
`MV-*` concern for a later increment.
"""

from __future__ import annotations

from typing import List, Tuple

from .tiles import ALL_DIRS, Board, E, GridPos, N, S, TileFlags, W, delta, opp

# GE-5: side k's outward direction, in spawn order S0..S3 (north, east,
# south, west).
OUTWARD_DIR: Tuple[int, int, int, int] = (N, E, S, W)


def hub_cells(n: int) -> List[GridPos]:
    """GE-1: the Hub is one logical goal node -- 4 cells for even N (every
    preset size is even), 1 cell for odd N."""
    if n % 2 == 0:
        half = n // 2
        return [
            GridPos(half - 1, half - 1),
            GridPos(half, half - 1),
            GridPos(half - 1, half),
            GridPos(half, half),
        ]
    c = (n - 1) // 2
    return [GridPos(c, c)]


def apron_cells(n: int) -> List[GridPos]:
    """GE-1 / GE-3: orthogonal neighbours of HUB, outside HUB. 8 cells for
    even N, 4 for odd N. Ordered deterministically (row-major) rather than by
    hub-cell iteration order, so this is reproducible regardless of how
    `hub_cells` happens to be listed."""
    hub = set(hub_cells(n))
    apron = set()
    for cell in hub:
        for d in ALL_DIRS:
            neighbour = cell + delta(d)
            if neighbour in hub:
                continue
            if not (0 <= neighbour.x < n and 0 <= neighbour.y < n):
                continue
            apron.add(neighbour)
    return sorted(apron, key=lambda p: (p.y, p.x))


def spawn_offset(n: int) -> int:
    """GE-5: `m = clamp(round(N/4), 1, N/2 - 2)`. Every preset size (8, 12,
    16, 20, 24) divides evenly by 4, so `round` never needs tie-breaking in
    practice; `round()` is used as-is rather than a custom rounding rule."""
    m = round(n / 4)
    lo, hi = 1, n // 2 - 2
    return max(lo, min(hi, m))


def spawns(n: int) -> List[GridPos]:
    """GE-5: the four spawns, one per side, `playerSlot k` occupies `S[k]`."""
    m = spawn_offset(n)
    return [
        GridPos(m, 0),  # S0, North
        GridPos(n - 1, m),  # S1, East
        GridPos(n - 1 - m, n - 1),  # S2, South
        GridPos(0, n - 1 - m),  # S3, West
    ]


def rho(pos: GridPos, n: int) -> GridPos:
    """GE-6: the 90-degree rotation `rho(x,y) = (N-1-y, x)` under which the
    spawn set is the single C4 orbit of `(m, 0)`."""
    return GridPos(n - 1 - pos.y, pos.x)


def start_pad_mask(k: int) -> int:
    """GE-8: Start Pad `S[k]` is an immutable T-Junction open on the three
    non-outward directions -- i.e. missing exactly the outward direction."""
    return 0xF & ~OUTWARD_DIR[k]


def start_pad_inward_neighbour(n: int, k: int) -> GridPos:
    """GE-8: `S[k] + inward` -- the cell one step into the board from the
    spawn, which carries ROCK_PROTECTED (still rotatable)."""
    inward = opp(OUTWARD_DIR[k])
    return spawns(n)[k] + delta(inward)


def place_fixed_geometry(board: Board) -> None:
    """MG-5: "Hub forced to mask 15 + FINISH_LOCKED, Start Pads forced to
    T-Junction + SPAWN_PAD, before any other placement." This function is
    that forcing step; it is the seam the map generator (`MG-*`) builds on
    top of.
    """
    n = board.n
    for cell in hub_cells(n):
        board.set_mask(cell, 15)
        board.add_flags(cell, TileFlags.FINISH_LOCKED)
    for k, pad in enumerate(spawns(n)):
        board.set_mask(pad, start_pad_mask(k))
        board.add_flags(pad, TileFlags.SPAWN_PAD)
        board.add_flags(start_pad_inward_neighbour(n, k), TileFlags.ROCK_PROTECTED)
