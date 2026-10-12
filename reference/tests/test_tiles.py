"""Tests for sim.tiles: tile algebra, grid state, mutual connectivity.

Each test cites the spec rule id(s) it verifies (SNAIL_LABYRINTH_TECHNICAL_SPEC.md).
"""

import unittest

from sim.tiles import (
    N, E, S, W, DIRS, DELTA,
    cw, ccw, opp, orbit, popcount, shape, Shape,
    Grid, connected, usable_exits,
)

ALL_MASKS = range(16)


class TestDirectionBits(unittest.TestCase):
    """TM-2: directions are a 4-bit mask, bit order screen-clockwise."""

    def test_verbatim_example(self):
        # TM-2: "Verification against GDD §5 verbatim: cw(0b0101 /*N-S*/) = 0b1010 /*E-W*/."
        self.assertEqual(cw(0b0101), 0b1010)

    def test_cw_is_order_4(self):
        # HT-1 §12.1: cw^4(m) == m, property over all 16 masks.
        for m in ALL_MASKS:
            c = m
            for _ in range(4):
                c = cw(c)
            self.assertEqual(c, m, f"cw^4({m}) != {m}")

    def test_ccw_undoes_cw(self):
        # HT-1 §12.1: ccw(cw(m)) == m, property over all 16 masks.
        for m in ALL_MASKS:
            self.assertEqual(ccw(cw(m)), m)
            self.assertEqual(cw(ccw(m)), m)

    def test_opp_is_involution(self):
        # HT-1 §12.1: opp(opp(d)) == d, for single-bit d.
        for d in DIRS:
            self.assertEqual(opp(opp(d)), d)

    def test_opp_values(self):
        # TM-2: opp(d) = ((d << 2) | (d >> 2)) & 0xF.
        self.assertEqual(opp(N), S)
        self.assertEqual(opp(S), N)
        self.assertEqual(opp(E), W)
        self.assertEqual(opp(W), E)

    def test_popcount_invariant_under_rotation(self):
        # HT-1 §12.1: popcount is invariant under cw/ccw -- the assertable
        # form of CD-7.
        for m in ALL_MASKS:
            self.assertEqual(popcount(cw(m)), popcount(m))
            self.assertEqual(popcount(ccw(m)), popcount(m))

    def test_rotation_no_ops(self):
        # TM-5: cw(0) = 0, cw(15) = 15 -- rotation is a no-op on Rock and Cross.
        self.assertEqual(cw(0), 0)
        self.assertEqual(cw(15), 15)

    def test_straight_cw_ccw_identical(self):
        # TM-5: cw(5) = ccw(5) = 10 -- on a Straight, CW and CCW are the same card.
        self.assertEqual(cw(5), 10)
        self.assertEqual(ccw(5), 10)


class TestOrbit(unittest.TestCase):
    """TM-2: orbit(m) = distinct[m, cw(m), cw^2(m), cw^3(m)]."""

    def test_orbit_sizes_match_distinct_rotations_table(self):
        # TM-3 table: distinct-rotation counts per shape.
        expected_size = {
            0: 1,                      # Rock
            1: 4, 2: 4, 4: 4, 8: 4,     # Dead End
            5: 2, 10: 2,                # Straight
            3: 4, 6: 4, 12: 4, 9: 4,    # Elbow
            7: 4, 14: 4, 13: 4, 11: 4,  # T-Junction
            15: 1,                      # Cross
        }
        for m, n in expected_size.items():
            self.assertEqual(len(orbit(m)), n, f"orbit({m}) has wrong size")

    def test_orbit_closed_under_rotation(self):
        for m in ALL_MASKS:
            for member in orbit(m):
                self.assertIn(cw(member), orbit(m))


class TestShape(unittest.TestCase):
    """TM-3: a tile is fully described by its 4-bit opening mask; shape is derived."""

    def test_shape_table_exhaustive(self):
        expected = {
            0: Shape.ROCK,
            1: Shape.DEAD_END, 2: Shape.DEAD_END, 4: Shape.DEAD_END, 8: Shape.DEAD_END,
            5: Shape.STRAIGHT, 10: Shape.STRAIGHT,
            3: Shape.ELBOW, 6: Shape.ELBOW, 12: Shape.ELBOW, 9: Shape.ELBOW,
            7: Shape.TEE, 14: Shape.TEE, 13: Shape.TEE, 11: Shape.TEE,
            15: Shape.CROSS,
        }
        for m in ALL_MASKS:
            self.assertEqual(shape(m), expected[m], f"shape({m}) wrong")

    def test_mask_shape_rotation_is_bijection(self):
        # HT-1 §12.1: mask <-> (shape, rotation) is a bijection over all 16 masks.
        # rotation is "how many cw() steps from this shape's canonical
        # (lowest-valued) orbit member", which is the only rotation index
        # that doesn't trivially collapse (orbit(m) always lists m first).
        def canonical(m):
            return min(orbit(m))

        def rotation_index(m):
            canon = canonical(m)
            cur = canon
            for k in range(4):
                if cur == m:
                    return k
                cur = cw(cur)
            raise AssertionError(f"{m} not reachable by rotating its own canonical form")

        seen = set()
        for m in ALL_MASKS:
            key = (shape(m), canonical(m), rotation_index(m))
            self.assertNotIn(key, seen, f"mask {m} collides with an earlier mask")
            seen.add(key)
        self.assertEqual(len(seen), 16)

    def test_rock_is_mask_zero(self):
        # TM-4: Rock Blocker is mask 0, not a separate type.
        self.assertEqual(shape(0), Shape.ROCK)


class TestGrid(unittest.TestCase):
    """TM-6: full grid state (mask, flags, version)."""

    def test_index_formula(self):
        # TM-1: i = y*N + x.
        g = Grid(4)
        self.assertEqual(g.idx(2, 1), 1 * 4 + 2)

    def test_off_grid_is_rock(self):
        # TM-9: off-grid is mask = 0. No wrapping.
        g = Grid(4)
        self.assertEqual(g.mask_at(-1, 0), 0)
        self.assertEqual(g.mask_at(4, 0), 0)
        self.assertEqual(g.mask_at(0, -1), 0)
        self.assertEqual(g.mask_at(0, 4), 0)

    def test_version_increments_on_mutation(self):
        # TM-6: version increments on every mutation.
        g = Grid(4)
        self.assertEqual(g.version[g.idx(1, 1)], 0)
        g.set_mask(1, 1, 5)
        self.assertEqual(g.version[g.idx(1, 1)], 1)
        g.set_mask(1, 1, 10)
        self.assertEqual(g.version[g.idx(1, 1)], 2)

    def test_set_mask_masks_to_4_bits(self):
        # TM-6: mask field uses 4 bits.
        g = Grid(2)
        g.set_mask(0, 0, 0xFF)
        self.assertEqual(g.mask_at(0, 0), 0xF)


class TestConnectivity(unittest.TestCase):
    """TM-8: connectivity is mutual."""

    def test_one_sided_opening_is_a_wall(self):
        g = Grid(2)
        g.set_mask(0, 0, E)       # (0,0) opens East
        g.set_mask(1, 0, 0)       # (1,0) is Rock, does not open West
        self.assertFalse(connected(g, 0, 0, E))

    def test_mutual_opening_connects(self):
        g = Grid(2)
        g.set_mask(0, 0, E)
        g.set_mask(1, 0, W)
        self.assertTrue(connected(g, 0, 0, E))

    def test_connected_is_symmetric(self):
        # HT-1 §12.1: connected(a,d) <=> connected(a+delta(d), opp(d)), property
        # over random boards.
        import random
        rng = random.Random(1234)
        n = 6
        g = Grid(n)
        for y in range(n):
            for x in range(n):
                g.set_mask(x, y, rng.randrange(16))
        for y in range(n):
            for x in range(n):
                for d in DIRS:
                    dx, dy = DELTA[d]
                    nx, ny = x + dx, y + dy
                    if not g.in_bounds(nx, ny):
                        continue
                    self.assertEqual(
                        connected(g, x, y, d),
                        connected(g, nx, ny, opp(d)),
                    )

    def test_off_grid_neighbours_never_connected(self):
        # HT-1 §12.1: off-grid neighbours are never connected (TM-9),
        # exhaustive on the border ring.
        n = 4
        g = Grid(n)
        for y in range(n):
            for x in range(n):
                g.set_mask(x, y, 0xF)  # fully open everywhere
        for x in range(n):
            self.assertFalse(connected(g, x, 0, N))
            self.assertFalse(connected(g, x, n - 1, S))
        for y in range(n):
            self.assertFalse(connected(g, 0, y, W))
            self.assertFalse(connected(g, n - 1, y, E))

    def test_usable_exits_is_mutual_or(self):
        g = Grid(3)
        g.set_mask(1, 1, 0xF)  # Cross, wants to open all 4
        g.set_mask(1, 0, S)    # N neighbour opens back South: mutual
        g.set_mask(2, 1, 0)    # E neighbour is Rock: not mutual
        g.set_mask(1, 2, 0)    # S neighbour is Rock: not mutual
        g.set_mask(0, 1, 0)    # W neighbour is Rock: not mutual
        self.assertEqual(usable_exits(g, 1, 1), N)


if __name__ == "__main__":
    unittest.main()
