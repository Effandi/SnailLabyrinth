"""A tile is one byte: its 4-bit opening mask. Spec: TM-3, TM-4, TM-5.

Shape and rotation are derived from the mask, never stored, so there is only
one source of truth (TM-3).
"""

from __future__ import annotations

from enum import Enum

from .directions import N, E, S, W, cw, ccw, popcount

STRAIGHT_MASKS = (5, 10)  # N|S, E|W


class Shape(Enum):
    ROCK = "ROCK"
    DEAD_END = "DEAD_END"
    STRAIGHT = "STRAIGHT"
    ELBOW = "ELBOW"
    TEE = "TEE"
    CROSS = "CROSS"


# TM-3: mask -> (shape, distinct rotation count), given for documentation and
# for exhaustive bijection tests. Not used at runtime; shape() is the single
# source of truth.
MASKS_BY_SHAPE: dict[Shape, tuple[int, ...]] = {
    Shape.ROCK: (0,),
    Shape.DEAD_END: (N, E, S, W),
    Shape.STRAIGHT: STRAIGHT_MASKS,
    Shape.ELBOW: (3, 6, 12, 9),
    Shape.TEE: (7, 14, 13, 11),
    Shape.CROSS: (15,),
}


def shape(m: int) -> Shape:
    """TM-3: derive shape from a 4-bit opening mask."""
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
    # p == 2: either the two bits are opposite (STRAIGHT) or adjacent (ELBOW).
    return Shape.STRAIGHT if m in STRAIGHT_MASKS else Shape.ELBOW


def is_rotation_noop(m: int) -> bool:
    """TM-5: rotation is a no-op on Rock (mask 0) and on Cross (mask 15)."""
    return cw(m) == m


def cw_ccw_are_same_card(m: int) -> bool:
    """TM-5: on a Straight, CW and CCW produce the same result."""
    return cw(m) == ccw(m)
