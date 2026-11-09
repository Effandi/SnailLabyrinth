"""Tile shape derivation. Spec: TM-3, TM-5. See §12.1 "Tile algebra" rows."""

import unittest

from snail_labyrinth.directions import N, E, S, W, cw, ccw
from snail_labyrinth.tile import Shape, MASKS_BY_SHAPE, shape, is_rotation_noop, cw_ccw_are_same_card


class TestTileShape(unittest.TestCase):
    def test_mask_to_shape_matches_spec_table_TM3(self):
        for sh, masks in MASKS_BY_SHAPE.items():
            for m in masks:
                with self.subTest(mask=m, shape=sh):
                    self.assertEqual(shape(m), sh)

    def test_mask_to_shape_is_a_bijection_over_all_16_masks_TM3(self):
        # Every mask 0..15 appears in exactly one shape's bucket, and the
        # buckets partition the full 16-mask space (1+4+2+4+4+1 == 16).
        all_masks = [m for masks in MASKS_BY_SHAPE.values() for m in masks]
        self.assertEqual(sorted(all_masks), list(range(16)))
        self.assertEqual(len(all_masks), 16)
        for m in range(16):
            matches = [sh for sh, masks in MASKS_BY_SHAPE.items() if m in masks]
            self.assertEqual(len(matches), 1, f"mask {m} must map to exactly one shape")

    def test_rotation_noop_on_rock_and_cross_TM5(self):
        self.assertTrue(is_rotation_noop(0))
        self.assertTrue(is_rotation_noop(15))
        for m in range(16):
            if m not in (0, 15):
                with self.subTest(m=m):
                    self.assertFalse(is_rotation_noop(m))

    def test_cw_ccw_identical_on_straight_TM5(self):
        for m in (5, 10):
            with self.subTest(m=m):
                self.assertTrue(cw_ccw_are_same_card(m))
                self.assertEqual(cw(m), ccw(m))

    def test_cw_ccw_differ_off_straight_rock_cross(self):
        for m in range(16):
            if m in (0, 5, 10, 15):
                continue
            with self.subTest(m=m):
                self.assertFalse(cw_ccw_are_same_card(m))

    def test_shape_ignores_bits_above_mask_width(self):
        # shape() masks its input to 4 bits; a stray high bit must not change
        # the result (defensive, not a numbered rule, but TM-3 defines the
        # tile as strictly a 4-bit value).
        self.assertEqual(shape(0b10101), shape(0b0101))


if __name__ == "__main__":
    unittest.main()
