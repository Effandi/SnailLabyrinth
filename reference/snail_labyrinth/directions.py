"""Direction bits and tile-mask algebra. Spec: TM-2.

Directions are a 4-bit mask, screen-clockwise bit order, so rotation is a
bit-rotate with no lookup table.
"""

from __future__ import annotations

N = 1  # (0, -1)
E = 2  # (+1, 0)
S = 4  # (0, +1)
W = 8  # (-1, 0)

ALL_DIRS = (N, E, S, W)

# TM-2: screen-space delta per single-bit direction.
DELTA: dict[int, tuple[int, int]] = {
    N: (0, -1),
    E: (1, 0),
    S: (0, 1),
    W: (-1, 0),
}


def cw(m: int) -> int:
    """Rotate mask m one quarter-turn clockwise. TM-2: N->E->S->W->N."""
    return ((m << 1) | (m >> 3)) & 0xF


def ccw(m: int) -> int:
    """Rotate mask m one quarter-turn counter-clockwise. TM-2."""
    return ((m >> 1) | (m << 3)) & 0xF


def opp(d: int) -> int:
    """Opposite of a single-bit direction. TM-2: defined for single-bit d only."""
    return ((d << 2) | (d >> 2)) & 0xF


def orbit(m: int) -> tuple[int, ...]:
    """Distinct masks reachable from m by repeated cw(). TM-2: orbit(m) = distinct[m, cw(m), cw^2(m), cw^3(m)]."""
    seen: list[int] = []
    cur = m
    for _ in range(4):
        if cur not in seen:
            seen.append(cur)
        cur = cw(cur)
    return tuple(seen)


def popcount(m: int) -> int:
    return bin(m & 0xF).count("1")
