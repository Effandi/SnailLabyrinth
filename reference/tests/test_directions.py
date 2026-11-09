"""Tile-mask algebra invariants. Spec: TM-2. See §12.1 "Tile algebra" rows."""

import unittest

from snail_labyrinth.directions import N, E, S, W, cw, ccw, opp, orbit, popcount

ALL_MASKS = range(16)
SINGLE_DIRS = (N, E, S, W)


class TestDirectionAlgebra(unittest.TestCase):
    def test_cw_quadruple_is_identity_TM2(self):
        for m in ALL_MASKS:
            with self.subTest(m=m):
                self.assertEqual(cw(cw(cw(cw(m)))), m)

    def test_ccw_undoes_cw_TM2(self):
        for m in ALL_MASKS:
            with self.subTest(m=m):
                self.assertEqual(ccw(cw(m)), m)
                self.assertEqual(cw(ccw(m)), m)

    def test_opp_is_involution_TM2(self):
        for d in SINGLE_DIRS:
            with self.subTest(d=d):
                self.assertEqual(opp(opp(d)), d)

    def test_opp_pairs_match_spec_TM2(self):
        self.assertEqual(opp(N), S)
        self.assertEqual(opp(S), N)
        self.assertEqual(opp(E), W)
        self.assertEqual(opp(W), E)

    def test_cw_rotates_NESW_order_TM2(self):
        self.assertEqual(cw(N), E)
        self.assertEqual(cw(E), S)
        self.assertEqual(cw(S), W)
        self.assertEqual(cw(W), N)

    def test_spec_worked_example_TM2(self):
        # "Verification against GDD §5 verbatim: cw(0b0101 /*N-S*/) = 0b1010 /*E-W*/."
        self.assertEqual(cw(0b0101), 0b1010)

    def test_popcount_invariant_under_cw_ccw_CD7(self):
        # "popcount is invariant under cw/ccw — the assertable form of CD-7"
        for m in ALL_MASKS:
            with self.subTest(m=m):
                self.assertEqual(popcount(cw(m)), popcount(m))
                self.assertEqual(popcount(ccw(m)), popcount(m))

    def test_orbit_sizes_match_distinct_rotation_counts_TM3(self):
        # TM-3 table: rock=1, dead end=4, straight=2, elbow=4, tee=4, cross=1.
        expected = {
            0: 1,
            1: 4, 2: 4, 4: 4, 8: 4,
            5: 2, 10: 2,
            3: 4, 6: 4, 12: 4, 9: 4,
            7: 4, 14: 4, 13: 4, 11: 4,
            15: 1,
        }
        for m, n in expected.items():
            with self.subTest(m=m):
                self.assertEqual(len(orbit(m)), n)

    def test_orbit_contains_only_cw_closure_of_m(self):
        for m in ALL_MASKS:
            with self.subTest(m=m):
                cur = m
                seen = set()
                for _ in range(4):
                    seen.add(cur)
                    cur = cw(cur)
                self.assertEqual(set(orbit(m)), seen)


if __name__ == "__main__":
    unittest.main()
