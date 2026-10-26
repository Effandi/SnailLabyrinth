"""Map generation, layers 1-2: C4-symmetric corridors and the free interior.

Implements SNAIL_LABYRINTH_TECHNICAL_SPEC.md section 3.3: `MG-16`, `MG-17`
layers 1 and 2. Layer 3 (rock accretion, `MG-18`/`MG-19`) and collectible
placement (`MG-20`-`MG-23`) are later increments -- see
`reference/PROGRESS.md`. The board this module produces has every non-Hub
cell assigned a real, open shape: no Rock exists anywhere yet, because
layer 2's type weights are explicitly "over non-rock cells" (`MG-17`) and
rocks are exclusively layer 3's job.

**Layer 1 — spawn corridors and the Apron ring (`MG-17`).** "The 4 corridor
regions (Start Pad + a radius-2 wedge) and the Apron ring are generated
once in a quarter-turn fundamental domain and replicated by the C4 orbit
(`GE-6`)." Operationalised here as: partition every Apron cell and every
canonical-wedge cell into its `rho`-orbit (always size 4 for every even
preset `N`, since `rho` has no fixed point on an even board -- `GE-6`);
generate a mask once for one representative of each orbit via the same
per-cell hash formula layer 2 uses; and replicate it to the other 3 orbit
members with the mask rotated one quarter-turn per `rho` application, so
the whole corridor region is a literal 90-degree image of itself -- a
physical rotation of the board rotates both cell position *and* tile
opening together.

**"Radius-2 wedge" read as Chebyshev distance <= 2** from the spawn cell,
matching the document's own house convention for grid distance (`CD-9`:
"Rock range: Chebyshev 3"). See `reference/OPEN_QUESTIONS.md` OQ-5 for the
reasoning and what would falsify it.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Set, Tuple, TypeVar

from .geometry import apron_cells, hub_cells, rho, spawns
from .rng import cell_hash
from .tiles import Board, GridPos, Shape, cw

T = TypeVar("T")

# MG-17 layer 2's default type weights, "over non-rock cells". Order
# matches the spec table's own listing; total is 100, used as the modulus
# for `weighted_pick` below.
DEFAULT_TYPE_WEIGHTS: Tuple[Tuple[Shape, int], ...] = (
    (Shape.STRAIGHT, 26),
    (Shape.ELBOW, 32),
    (Shape.TEE, 24),
    (Shape.CROSS, 8),
    (Shape.DEAD_END, 10),
)

# One canonical reference mask per shape, used only as a rotation origin
# for `ori(c)` quarter-turns (`type_mask`). Any representative of the
# shape's orbit works equally well as a starting point: rotating it `ori`
# quarter-turns covers the same set of concrete masks regardless of which
# member was picked as "canonical" (TM-2's orbit()). Chosen to match the
# first mask the spec's own TM-3 table lists for each shape.
_CANONICAL_MASK: Dict[Shape, int] = {
    Shape.DEAD_END: 1,  # N
    Shape.STRAIGHT: 5,  # N-S
    Shape.ELBOW: 3,  # N-E
    Shape.TEE: 7,  # missing W
    Shape.CROSS: 15,
}

WEDGE_RADIUS = 2


def weighted_pick(hash_value: int, weighted_items: Sequence[Tuple[T, int]]) -> T:
    """`MG-17`: `type(c) = weighted_pick(CellHash("types", c))`. Generic
    deterministic weighted choice from a single hash value -- no state, no
    redraw, so it is meaningful to call with one fixed `hash_value` (unlike
    `rng.Pcg32.next_below`'s rejection sampling, which needs the ability to
    draw again). `hash_value` is `CellHash`'s 32-bit output (`rng.py`);
    against a weight total this small (100), `hash_value % total`'s bias
    is astronomically negligible (~100/2**32), so plain modulo is used
    rather than rejection sampling.
    """
    total = sum(weight for _, weight in weighted_items)
    if total <= 0:
        raise ValueError("weighted_items must have a positive total weight")
    r = hash_value % total
    acc = 0
    for item, weight in weighted_items:
        acc += weight
        if r < acc:
            return item
    return weighted_items[-1][0]  # unreachable given the invariant above


def type_mask(shape: Shape, ori: int) -> int:
    """`MG-17`: combine a picked `shape` with `ori(c) & 3` quarter-turns
    into a concrete mask. For a shape whose rotation period is less than 4
    (Straight: 2, Cross: 1), distinct `ori` values legitimately collapse
    onto the same mask -- that is `TM-2`'s orbit acting exactly as
    expected, not a bug.
    """
    m = _CANONICAL_MASK[shape]
    for _ in range(ori & 3):
        m = cw(m)
    return m


def cell_mask(root_key: int, x: int, y: int) -> int:
    """`MG-17` layer 2's per-cell formula: `type(c) = weighted_pick(
    CellHash("types", c))`, `ori(c) = CellHash("orient", c) & 3`. Used both
    for the free interior (layer 2) and, once per orbit representative,
    for the symmetric corridor/Apron region (layer 1) -- the two layers
    differ only in *which* cells call this and how many images each result
    is replicated to, never in the formula itself.
    """
    type_hash = cell_hash(root_key, "types", x, y)
    shape = weighted_pick(type_hash, DEFAULT_TYPE_WEIGHTS)
    orient_hash = cell_hash(root_key, "orient", x, y)
    ori = orient_hash & 3
    return type_mask(shape, ori)


def c4_orbit(cell: GridPos, n: int) -> Tuple[GridPos, GridPos, GridPos, GridPos]:
    """`GE-6`: the 4 images of `cell` under repeated `rho`, in rotation
    order `(cell, rho(cell), rho^2(cell), rho^3(cell))`. Always 4 distinct
    cells for every even preset `N`, since `rho` has no fixed point on an
    even board (`GE-6`'s "simply transitively").
    """
    c0 = cell
    c1 = rho(c0, n)
    c2 = rho(c1, n)
    c3 = rho(c2, n)
    return (c0, c1, c2, c3)


def canonical_representative(cell: GridPos, n: int) -> GridPos:
    """The row-major-least cell in `cell`'s `rho`-orbit -- a deterministic,
    arbitrary-but-fixed choice of "the one representative to generate for
    real", independent of which cell happened to be passed in.
    """
    return min(c4_orbit(cell, n), key=lambda p: (p.y, p.x))


def canonical_corridor_wedge(n: int) -> List[GridPos]:
    """`MG-17` layer 1: "Start Pad + a radius-2 wedge" for the canonical
    quadrant anchored at spawn `S0`. Excludes the Start Pad cells
    themselves (`MG-5` already forces every spawn pad before this layer
    runs) and any Hub/Apron cell (generated separately, see
    `layer1_cells`), so this is exactly the *new* ground layer 1 claims
    beyond what `geometry.place_fixed_geometry` already fixed.
    """
    s0 = spawns(n)[0]
    reserved = set(hub_cells(n)) | set(apron_cells(n)) | set(spawns(n))
    result: List[GridPos] = []
    for dx in range(-WEDGE_RADIUS, WEDGE_RADIUS + 1):
        for dy in range(-WEDGE_RADIUS, WEDGE_RADIUS + 1):
            if max(abs(dx), abs(dy)) > WEDGE_RADIUS:
                continue  # Chebyshev radius, not a Manhattan diamond
            p = GridPos(s0.x + dx, s0.y + dy)
            if not (0 <= p.x < n and 0 <= p.y < n):
                continue
            if p in reserved:
                continue
            result.append(p)
    return result


def layer1_cells(n: int) -> Set[GridPos]:
    """Every cell layer 1 is responsible for: the full (8-cell) Apron ring
    plus all 4 rotated images of the canonical corridor wedge.
    """
    cells: Set[GridPos] = set(apron_cells(n))
    for p in canonical_corridor_wedge(n):
        cells.update(c4_orbit(p, n))
    return cells


def generate_layer1(board: Board, root_key: int) -> None:
    """`MG-17` layer 1. Generates one mask per `rho`-orbit representative
    among the Apron ring and the canonical corridor wedge, then writes the
    rotated mask to every member of that orbit -- so the whole region is
    exactly C4-symmetric by construction, which is what makes `MG-11`
    (fairness ratio) and `MG-14` (fairness spread) achievable once layer 3
    and the repair loop (`MG-19`, a later increment) exist to close the
    rest of the gap. (Layer 1 alone does not guarantee `MG-11`/`MG-14` --
    the free interior in layer 2 can still make routes unequal; see
    `reference/PROGRESS.md` for why this increment does not assert them.)
    """
    n = board.n
    seeds = set(apron_cells(n)) | set(canonical_corridor_wedge(n))
    representatives = {canonical_representative(p, n) for p in seeds}
    for rep in representatives:
        mask = cell_mask(root_key, rep.x, rep.y)
        for cell in c4_orbit(rep, n):
            board.set_mask(cell, mask)
            mask = cw(mask)


def generate_layer2(board: Board, root_key: int) -> None:
    """`MG-17` layer 2: every cell not already claimed by the fixed
    geometry (`MG-5`) or layer 1 gets an independently hashed type and
    orientation -- "free", and "stateless per-cell hashing, so the
    interior is independent of iteration order" (`MG-17`).
    """
    n = board.n
    reserved = set(hub_cells(n)) | set(spawns(n)) | layer1_cells(n)
    for p in board.all_cells():
        if p in reserved:
            continue
        board.set_mask(p, cell_mask(root_key, p.x, p.y))


def generate_board(n: int, root_key: int) -> Board:
    """Compose `MG-5`'s fixed geometry with layers 1-2 into a complete
    board. No rocks and no collectibles exist yet (those are layer 3,
    `MG-18`/`MG-19`, and `MG-20`-`MG-23` respectively) -- every non-Hub
    cell has a real, open shape.
    """
    from .geometry import place_fixed_geometry

    board = Board(n)
    place_fixed_geometry(board)
    generate_layer1(board, root_key)
    generate_layer2(board, root_key)
    return board
