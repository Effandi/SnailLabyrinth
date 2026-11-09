"""Grid state and mutual connectivity. Spec: TM-6, TM-8, TM-9, TM-10.

TM-6's full per-cell state is `mask | flags | version`. Rendering fields
(mesh yaw, TM-7) are out of scope: SimCore has no rendering (HT-1).
"""

from __future__ import annotations

from .directions import ALL_DIRS, DELTA, opp

# TM-6: flags byte. Bit assignment is this implementation's choice; the spec
# names the flags but not their bit order.
FINISH_LOCKED = 1 << 0
SPAWN_PAD = 1 << 1
HAS_GEM = 1 << 2
HAS_SLOT = 1 << 3
ROCK_PROTECTED = 1 << 4

GridPos = tuple[int, int]


class Board:
    """TM-6: `mask[N*N]`, `flags[N*N]`, `version[N*N]`, row-major, `i = y*N + x` (TM-1)."""

    def __init__(self, n: int) -> None:
        self.n = n
        self.mask = [0] * (n * n)
        self.flags = [0] * (n * n)
        self.version = [0] * (n * n)

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.n and 0 <= y < self.n

    def idx(self, x: int, y: int) -> int:
        return y * self.n + x

    def mask_at(self, x: int, y: int) -> int:
        """TM-9: off-grid reads as mask 0 (a virtual solid ring), never wraps."""
        if not self.in_bounds(x, y):
            return 0
        return self.mask[self.idx(x, y)]

    def set_mask(self, x: int, y: int, m: int) -> None:
        """TM-10: rotating/retyping is legal whenever the mask changes; version
        bumps on every mutation (TM-6), independent of whether effective
        connectivity (`usable_exits`) actually changes."""
        i = self.idx(x, y)
        m &= 0xF
        if self.mask[i] != m:
            self.mask[i] = m
            self.version[i] = (self.version[i] + 1) & 0xFFFF

    def flag_at(self, x: int, y: int, flag: int) -> bool:
        return bool(self.flags[self.idx(x, y)] & flag)

    def set_flag(self, x: int, y: int, flag: int) -> None:
        self.flags[self.idx(x, y)] |= flag

    def clear_flag(self, x: int, y: int, flag: int) -> None:
        self.flags[self.idx(x, y)] &= ~flag

    def connected(self, x: int, y: int, d: int) -> bool:
        """TM-8: two orthogonally adjacent cells are connected iff *both*
        open toward each other. A one-sided opening is a wall."""
        if (self.mask_at(x, y) & d) == 0:
            return False
        dx, dy = DELTA[d]
        return (self.mask_at(x + dx, y + dy) & opp(d)) != 0

    def usable_exits(self, x: int, y: int) -> int:
        """TM-8: `usableExits` is the only connectivity primitive the rest
        of the game needs."""
        result = 0
        for d in ALL_DIRS:
            if self.connected(x, y, d):
                result |= d
        return result
