"""Tests for snail_labyrinth.tiles: TM-1 .. TM-10.

Every test cites the spec rule(s) it verifies in its docstring or name.
"""

import unittest

from snail_labyrinth.tiles import (
    ALL_DIRS,
    Board,
    E,
    GridPos,
    N,
    S,
    Shape,
    TileFlags,
    W,
    ccw,
    cw,
    delta,
    opp,
    orbit,
    popcount,
    shape_of,
)

ALL_MASKS = range(16)


class TileAlgebraTests(unittest.TestCase):
    """TM-2: direction bits and the rotation/opposite operators."""

    def test_TM2_cw_worked_example_from_spec(self):
        # "Verification against GDD §5 verbatim: cw(0b0101 /*N-S*/) = 0b1010 /*E-W*/."
        self.assertEqual(cw(0b0101), 0b1010)

    def test_TM2_cw_is_order_4(self):
        for m in ALL_MASKS:
            self.assertEqual(cw(cw(cw(cw(m)))), m, msg=f"cw^4({m}) != {m}")

    def test_TM2_ccw_is_inverse_of_cw(self):
        for m in ALL_MASKS:
            self.assertEqual(ccw(cw(m)), m)
            self.assertEqual(cw(ccw(m)), m)

    def test_TM2_opp_is_involution_on_single_bit_dirs(self):
        for d in ALL_DIRS:
            self.assertEqual(opp(opp(d)), d)

    def test_TM2_opp_maps_to_the_geometric_opposite(self):
        self.assertEqual(opp(N), S)
        self.assertEqual(opp(S), N)
        self.assertEqual(opp(E), W)
        self.assertEqual(opp(W), E)

    def test_TM2_delta_matches_direction_semantics(self):
        # TM-1: x increases East, y increases South.
        self.assertEqual(delta(N), GridPos(0, -1))
        self.assertEqual(delta(S), GridPos(0, 1))
        self.assertEqual(delta(E), GridPos(1, 0))
        self.assertEqual(delta(W), GridPos(-1, 0))

    def test_popcount_invariant_under_rotation(self):
        """HT-1 tile-algebra row; the assertable form of CD-7's shape-preserving claim."""
        for m in ALL_MASKS:
            self.assertEqual(popcount(cw(m)), popcount(m))
            self.assertEqual(popcount(ccw(m)), popcount(m))

    def test_TM5_rotation_is_a_noop_on_rock_and_cross(self):
        self.assertEqual(cw(0), 0)
        self.assertEqual(ccw(0), 0)
        self.assertEqual(cw(15), 15)
        self.assertEqual(ccw(15), 15)

    def test_TM5_cw_and_ccw_are_identical_on_a_straight(self):
        self.assertEqual(cw(5), ccw(5))
        self.assertEqual(cw(5), 10)
        self.assertEqual(cw(10), ccw(10))
        self.assertEqual(cw(10), 5)


class ShapeBijectionTests(unittest.TestCase):
    """TM-3: mask <-> (shape, rotation) is a bijection over the 16 masks."""

    def test_TM3_shape_of_rock(self):
        self.assertEqual(shape_of(0), Shape.ROCK)

    def test_TM3_shape_of_dead_ends(self):
        for m in (1, 2, 4, 8):
            self.assertEqual(shape_of(m), Shape.DEAD_END)

    def test_TM3_shape_of_straights(self):
        for m in (5, 10):
            self.assertEqual(shape_of(m), Shape.STRAIGHT)

    def test_TM3_shape_of_elbows(self):
        for m in (3, 6, 12, 9):
            self.assertEqual(shape_of(m), Shape.ELBOW)

    def test_TM3_shape_of_tees(self):
        for m in (7, 14, 13, 11):
            self.assertEqual(shape_of(m), Shape.TEE)

    def test_TM3_shape_of_cross(self):
        self.assertEqual(shape_of(15), Shape.CROSS)

    def test_TM3_every_mask_is_classified_and_counts_match_the_table(self):
        counts = {}
        for m in ALL_MASKS:
            counts.setdefault(shape_of(m), 0)
            counts[shape_of(m)] += 1
        self.assertEqual(counts[Shape.ROCK], 1)
        self.assertEqual(counts[Shape.DEAD_END], 4)
        self.assertEqual(counts[Shape.STRAIGHT], 2)
        self.assertEqual(counts[Shape.ELBOW], 4)
        self.assertEqual(counts[Shape.TEE], 4)
        self.assertEqual(counts[Shape.CROSS], 1)
        self.assertEqual(sum(counts.values()), 16)

    def test_TM3_orbit_sizes_match_distinct_rotation_counts(self):
        # mask -> shape table's "distinct rotations" column.
        expected = {
            0: 1,
            1: 4, 2: 4, 4: 4, 8: 4,
            5: 2, 10: 2,
            3: 4, 6: 4, 12: 4, 9: 4,
            7: 4, 14: 4, 13: 4, 11: 4,
            15: 1,
        }
        for m, count in expected.items():
            self.assertEqual(len(orbit(m)), count, msg=f"orbit({m}) size mismatch")

    def test_TM3_orbit_members_share_a_shape(self):
        for m in ALL_MASKS:
            base_shape = shape_of(m)
            for o in orbit(m):
                self.assertEqual(shape_of(o), base_shape)


class ConnectivityTests(unittest.TestCase):
    """TM-6, TM-8, TM-9, TM-10."""

    def test_TM6_mutation_bumps_version(self):
        b = Board(4)
        p = GridPos(1, 1)
        self.assertEqual(b.version_at(p), 0)
        b.set_mask(p, 5)
        self.assertEqual(b.version_at(p), 1)
        b.set_mask(p, 10)
        self.assertEqual(b.version_at(p), 2)

    def test_TM6_mask_is_authoritative_and_masked_to_4_bits(self):
        b = Board(3)
        p = GridPos(0, 0)
        b.set_mask(p, 0xFF)
        self.assertEqual(b.mask_at(p), 0xF)

    def test_TM8_mutual_openness_required(self):
        # A opens East toward B, but B does not open West toward A: a wall.
        b = Board(2)
        a, nb = GridPos(0, 0), GridPos(1, 0)
        b.set_mask(a, E)
        b.set_mask(nb, 0)
        self.assertFalse(b.connected(a, E))

    def test_TM8_both_sides_open_connects(self):
        b = Board(2)
        a, nb = GridPos(0, 0), GridPos(1, 0)
        b.set_mask(a, E)
        b.set_mask(nb, W)
        self.assertTrue(b.connected(a, E))

    def test_TM8_connectivity_is_symmetric(self):
        """connected(a,d) <=> connected(a+delta(d), opp(d)) for any pair of masks."""
        b = Board(3)
        centre = GridPos(1, 1)
        for m_centre in range(16):
            for d in ALL_DIRS:
                nb = centre + delta(d)
                for m_nb in range(16):
                    b.set_mask(centre, m_centre)
                    b.set_mask(nb, m_nb)
                    self.assertEqual(
                        b.connected(centre, d),
                        b.connected(nb, opp(d)),
                        msg=f"asymmetry at centre={m_centre} nb={m_nb} d={d}",
                    )

    def test_TM8_usable_exits_is_or_of_connected_directions(self):
        b = Board(3)
        centre = GridPos(1, 1)
        b.set_mask(centre, 15)
        for d in ALL_DIRS:
            b.set_mask(centre + delta(d), opp(d))
        self.assertEqual(b.usable_exits(centre), 15)

    def test_TM9_off_grid_is_rock(self):
        b = Board(4)
        self.assertEqual(b.mask_at(GridPos(-1, 0)), 0)
        self.assertEqual(b.mask_at(GridPos(0, -1)), 0)
        self.assertEqual(b.mask_at(GridPos(4, 0)), 0)
        self.assertEqual(b.mask_at(GridPos(0, 4)), 0)

    def test_TM9_border_ring_never_connects_outward(self):
        """Exhaustive on the border ring: an outward opening never connects,
        whatever the border tile's mask (up to and including Cross)."""
        n = 4
        b = Board(n)
        for p in b.all_cells():
            on_border = p.x in (0, n - 1) or p.y in (0, n - 1)
            if not on_border:
                continue
            for m in ALL_MASKS:
                b.set_mask(p, m)
                for d in ALL_DIRS:
                    nb = p + delta(d)
                    if b.in_bounds(nb):
                        continue
                    self.assertFalse(
                        b.connected(p, d),
                        msg=f"cell {p} mask {m} dir {d} connects off-grid",
                    )

    def test_TM10_rotating_a_border_tile_changes_the_mask_even_when_the_outward_opening_stays_uncrossable(self):
        """TM-10: rotating a border tile is legal whenever the mask changes,
        even if effective connectivity does not -- an outward-facing opening
        is never traversable (TM-9) regardless of which direction it faces."""
        n = 4
        b = Board(n)
        corner = GridPos(0, 0)  # both N and W point off-grid here.
        b.set_mask(corner, N)  # opens only outward (off-grid).
        before_exits = b.usable_exits(corner)
        b.set_mask(corner, W)  # a different mask, still only an outward opening.
        after_exits = b.usable_exits(corner)
        self.assertNotEqual(N, W)
        self.assertEqual(before_exits, 0)
        self.assertEqual(after_exits, 0)
        self.assertEqual(b.mask_at(corner), W)

    def test_TM6_flags_round_trip(self):
        b = Board(2)
        p = GridPos(0, 0)
        self.assertEqual(b.flags_at(p), TileFlags.NONE)
        b.add_flags(p, TileFlags.SPAWN_PAD)
        self.assertTrue(b.flags_at(p) & TileFlags.SPAWN_PAD)
        b.add_flags(p, TileFlags.ROCK_PROTECTED)
        self.assertTrue(b.flags_at(p) & TileFlags.SPAWN_PAD)
        self.assertTrue(b.flags_at(p) & TileFlags.ROCK_PROTECTED)


if __name__ == "__main__":
    unittest.main()
