"""Tile model and connectivity.

Implements SNAIL_LABYRINTH_TECHNICAL_SPEC.md section 1: TM-1 .. TM-10.
Engine-agnostic integer arithmetic over a byte array, per the spec's own
framing of this section.
"""

from __future__ import annotations

from enum import IntEnum, IntFlag
from typing import Dict, NamedTuple, Tuple

# TM-2: directions are a 4-bit mask, screen-clockwise bit order.
N: int = 1
E: int = 2
S: int = 4
W: int = 8
ALL_DIRS: Tuple[int, int, int, int] = (N, E, S, W)

_DELTA: Dict[int, Tuple[int, int]] = {
    N: (0, -1),
    E: (1, 0),
    S: (0, 1),
    W: (-1, 0),
}


class GridPos(NamedTuple):
    """TM-1: a cell (x, y), x increasing East, y increasing South."""

    x: int
    y: int

    def __add__(self, other: "GridPos") -> "GridPos":  # type: ignore[override]
        return GridPos(self.x + other.x, self.y + other.y)


def delta(d: int) -> GridPos:
    """TM-1: unit offset for a single-bit direction."""
    return GridPos(*_DELTA[d])


def cw(m: int) -> int:
    """TM-2: bit-rotate clockwise. N->E->S->W->N."""
    return ((m << 1) | (m >> 3)) & 0xF


def ccw(m: int) -> int:
    """TM-2: bit-rotate counter-clockwise."""
    return ((m >> 1) | (m << 3)) & 0xF


def opp(d: int) -> int:
    """TM-2: opposite direction. Defined for single-bit d only."""
    return ((d << 2) | (d >> 2)) & 0xF


def popcount(m: int) -> int:
    return bin(m & 0xF).count("1")


def orbit(m: int) -> Tuple[int, ...]:
    """TM-2: distinct masks in the rotation orbit of m, cw order starting at m."""
    result = []
    cur = m & 0xF
    for _ in range(4):
        if cur not in result:
            result.append(cur)
        cur = cw(cur)
    return tuple(result)


class Shape(IntEnum):
    """TM-3. A T-Junction is named by its missing direction, per the spec."""

    ROCK = 0
    DEAD_END = 1
    STRAIGHT = 2
    ELBOW = 3
    TEE = 4
    CROSS = 5


def shape_of(m: int) -> Shape:
    """TM-3: shape is derived from the mask, never stored alongside it."""
    m &= 0xF
    p = popcount(m)
    if p == 0:
        return Shape.ROCK
    if p == 1:
        return Shape.DEAD_END
    if p == 3:
        return Shape.TEE
    if p == 4:
        return Shape.CROSS
    # p == 2: either the two-opening Straight (collinear) or an Elbow (adjacent).
    return Shape.STRAIGHT if m in (5, 10) else Shape.ELBOW


class TileFlags(IntFlag):
    """TM-6."""

    NONE = 0
    FINISH_LOCKED = 1
    SPAWN_PAD = 2
    HAS_GEM = 4
    HAS_SLOT = 8
    ROCK_PROTECTED = 16


class Board:
    """TM-6: full grid state. `mask` is authoritative; shape/rotation are
    always derived from it (TM-3), never stored separately.
    """

    __slots__ = ("n", "mask", "flags", "version")

    def __init__(self, n: int) -> None:
        self.n = n
        self.mask = [0] * (n * n)
        self.flags = [TileFlags.NONE] * (n * n)
        self.version = [0] * (n * n)

    def in_bounds(self, p: GridPos) -> bool:
        return 0 <= p.x < self.n and 0 <= p.y < self.n

    def index(self, p: GridPos) -> int:
        return p.y * self.n + p.x

    def mask_at(self, p: GridPos) -> int:
        """TM-9: off-grid is Rock (mask 0). No wrapping."""
        if not self.in_bounds(p):
            return 0
        return self.mask[self.index(p)]

    def set_mask(self, p: GridPos, m: int) -> None:
        """TM-6: mutating a cell bumps its version, used for concurrency (MP-6)."""
        i = self.index(p)
        self.mask[i] = m & 0xF
        self.version[i] += 1

    def flags_at(self, p: GridPos) -> TileFlags:
        return self.flags[self.index(p)]

    def set_flags(self, p: GridPos, flags: TileFlags) -> None:
        self.flags[self.index(p)] = flags

    def add_flags(self, p: GridPos, flags: TileFlags) -> None:
        i = self.index(p)
        self.flags[i] = self.flags[i] | flags

    def version_at(self, p: GridPos) -> int:
        return self.version[self.index(p)]

    def connected(self, p: GridPos, d: int) -> bool:
        """TM-8: two orthogonally adjacent cells are connected iff *both*
        open toward each other. A one-sided opening is a wall."""
        if (self.mask_at(p) & d) == 0:
            return False
        neighbour = p + delta(d)
        return (self.mask_at(neighbour) & opp(d)) != 0

    def usable_exits(self, p: GridPos) -> int:
        """TM-8: the only connectivity primitive the rest of the game needs."""
        result = 0
        for d in ALL_DIRS:
            if self.connected(p, d):
                result |= d
        return result

    def all_cells(self):
        for y in range(self.n):
            for x in range(self.n):
                yield GridPos(x, y)
