"""Tile model, coordinate system, and mutual connectivity.

Implements spec section 1 (TM-1..TM-10): SNAIL_LABYRINTH_TECHNICAL_SPEC.md.
Pure integer arithmetic on a byte array, no engine types (HT-1).
"""

from enum import IntEnum

# TM-1: cells are (x, y), x increasing East, y increasing South, both in [0, N).
# Index i = y*N + x.

# TM-2: directions are a 4-bit mask, bit order screen-clockwise.
N = 1
E = 2
S = 4
W = 8

DIRS = (N, E, S, W)

DELTA = {
    N: (0, -1),
    E: (1, 0),
    S: (0, 1),
    W: (-1, 0),
}


def cw(m):
    """TM-2: cw(m) = ((m << 1) | (m >> 3)) & 0xF. N->E->S->W->N."""
    return ((m << 1) | (m >> 3)) & 0xF


def ccw(m):
    """TM-2: ccw(m) = ((m >> 1) | (m << 3)) & 0xF."""
    return ((m >> 1) | (m << 3)) & 0xF


def opp(d):
    """TM-2: opp(d) = ((d << 2) | (d >> 2)) & 0xF. Single-bit d only."""
    return ((d << 2) | (d >> 2)) & 0xF


def orbit(m):
    """TM-2: orbit(m) = distinct[m, cw(m), cw^2(m), cw^3(m)]."""
    result = []
    cur = m
    for _ in range(4):
        if cur not in result:
            result.append(cur)
        cur = cw(cur)
    return tuple(result)


def popcount(m):
    return bin(m & 0xF).count("1")


class Shape(IntEnum):
    ROCK = 0
    DEAD_END = 1
    STRAIGHT = 2
    ELBOW = 3
    TEE = 4
    CROSS = 5


def shape(m):
    """TM-3: shape is derived from the mask, never stored."""
    p = popcount(m)
    if p == 0:
        return Shape.ROCK
    if p == 1:
        return Shape.DEAD_END
    if p == 3:
        return Shape.TEE
    if p == 4:
        return Shape.CROSS
    # p == 2
    if m == 5 or m == 10:
        return Shape.STRAIGHT
    return Shape.ELBOW


# TM-6: flags byte. FINISH_LOCKED | SPAWN_PAD | HAS_GEM | HAS_SLOT | ROCK_PROTECTED.
FINISH_LOCKED = 1
SPAWN_PAD = 2
HAS_GEM = 4
HAS_SLOT = 8
ROCK_PROTECTED = 16


class Grid:
    """TM-6: full grid state. mask[N*N], flags[N*N], version[N*N]."""

    def __init__(self, n):
        self.n = n
        self.mask = [0] * (n * n)
        self.flags = [0] * (n * n)
        self.version = [0] * (n * n)

    def idx(self, x, y):
        """TM-1: i = y*N + x."""
        return y * self.n + x

    def in_bounds(self, x, y):
        return 0 <= x < self.n and 0 <= y < self.n

    def mask_at(self, x, y):
        """TM-9: off-grid is Rock (mask 0). No wrapping."""
        if not self.in_bounds(x, y):
            return 0
        return self.mask[self.idx(x, y)]

    def set_mask(self, x, y, m):
        """TM-6: version increments on every mutation (used for concurrency, MP-6)."""
        i = self.idx(x, y)
        self.mask[i] = m & 0xF
        self.version[i] += 1

    def get_flags(self, x, y):
        return self.flags[self.idx(x, y)]

    def set_flags(self, x, y, f):
        self.flags[self.idx(x, y)] = f


def connected(grid, x, y, d):
    """TM-8: two orthogonally adjacent cells are connected iff *both* open
    toward each other. A one-sided opening is a wall."""
    dx, dy = DELTA[d]
    nx, ny = x + dx, y + dy
    return bool(grid.mask_at(x, y) & d) and bool(grid.mask_at(nx, ny) & opp(d))


def usable_exits(grid, x, y):
    """TM-8: usableExits(a) = OR over d in {N,E,S,W} of (connected(a,d) ? d : 0)."""
    result = 0
    for d in DIRS:
        if connected(grid, x, y, d):
            result |= d
    return result
