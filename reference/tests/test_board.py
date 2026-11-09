"""Grid state and mutual connectivity. Spec: TM-6, TM-8, TM-9, TM-10.

See §12.1 "Connectivity" rows: mutual connectivity is symmetric, and
off-grid neighbours are never connected, exhaustively on the border ring.
"""

import random
import unittest

from snail_labyrinth.board import Board, FINISH_LOCKED, SPAWN_PAD
from snail_labyrinth.directions import ALL_DIRS, DELTA, opp


def random_board(n: int, seed: int) -> Board:
    rng = random.Random(seed)
    b = Board(n)
    for y in range(n):
        for x in range(n):
            b.set_mask(x, y, rng.randrange(16))
    return b


class TestConnectivity(unittest.TestCase):
    def test_connected_is_symmetric_TM8(self):
        for seed in range(20):
            b = random_board(6, seed)
            for y in range(b.n):
                for x in range(b.n):
                    for d in ALL_DIRS:
                        dx, dy = DELTA[d]
                        nx, ny = x + dx, y + dy
                        if not b.in_bounds(nx, ny):
                            continue
                        with self.subTest(seed=seed, x=x, y=y, d=d):
                            self.assertEqual(
                                b.connected(x, y, d),
                                b.connected(nx, ny, opp(d)),
                            )

    def test_one_sided_opening_is_a_wall_TM8(self):
        b = Board(3)
        b.set_mask(1, 1, 0b0010)  # E only
        b.set_mask(2, 1, 0b0010)  # E only; does not open W back toward (1,1)
        self.assertFalse(b.connected(1, 1, 2))  # E
        self.assertFalse(b.connected(2, 1, 8))  # W

    def test_mutual_opening_connects_TM8(self):
        b = Board(3)
        b.set_mask(1, 1, 0b0010)  # E
        b.set_mask(2, 1, 0b1000)  # W, faces back
        self.assertTrue(b.connected(1, 1, 2))
        self.assertTrue(b.connected(2, 1, 8))

    def test_off_grid_is_rock_TM9(self):
        b = Board(4)
        for x in (-3, -1, 0, 3, 4, 7):
            for y in (-3, -1, 0, 3, 4, 7):
                if b.in_bounds(x, y):
                    continue
                with self.subTest(x=x, y=y):
                    self.assertEqual(b.mask_at(x, y), 0)

    def test_border_ring_never_connects_outward_TM9(self):
        # Exhaustive on the border ring: every cell on the edge of the board,
        # for every direction pointing off-grid, is never connected outward,
        # regardless of the border cell's own mask.
        n = 5
        for m in range(16):
            b = Board(n)
            for y in range(n):
                for x in range(n):
                    b.set_mask(x, y, m)
            for x in range(n):
                with self.subTest(mask=m, x=x, edge="N"):
                    self.assertFalse(b.connected(x, 0, 1))
                with self.subTest(mask=m, x=x, edge="S"):
                    self.assertFalse(b.connected(x, n - 1, 4))
            for y in range(n):
                with self.subTest(mask=m, y=y, edge="W"):
                    self.assertFalse(b.connected(0, y, 8))
                with self.subTest(mask=m, y=y, edge="E"):
                    self.assertFalse(b.connected(n - 1, y, 2))


class TestMutation(unittest.TestCase):
    def test_set_mask_bumps_version_on_change_TM6(self):
        b = Board(3)
        self.assertEqual(b.version[b.idx(1, 1)], 0)
        b.set_mask(1, 1, 5)
        self.assertEqual(b.version[b.idx(1, 1)], 1)
        b.set_mask(1, 1, 5)  # no-op write: same mask, no bump
        self.assertEqual(b.version[b.idx(1, 1)], 1)
        b.set_mask(1, 1, 10)
        self.assertEqual(b.version[b.idx(1, 1)], 2)

    def test_rotating_border_tile_is_legal_even_if_connectivity_unaffected_TM10(self):
        # A fully-walled border tile (Rock) rotated to a Dead End changes the
        # mask (and must be accepted / version-bumped) even though nothing
        # off-grid becomes newly connected.
        b = Board(3)
        b.set_mask(0, 0, 0)  # Rock, corner cell: N and W point off-grid anyway
        before_version = b.version[b.idx(0, 0)]
        b.set_mask(0, 0, 1)  # Dead End facing N (off-grid) — still a legal mask change
        self.assertEqual(b.mask[b.idx(0, 0)], 1)
        self.assertGreater(b.version[b.idx(0, 0)], before_version)
        # Connectivity to any in-bounds neighbour is still false; the mask
        # change is legal independent of that.
        self.assertFalse(b.connected(0, 0, 2))  # E neighbour exists but isn't open

    def test_flags_roundtrip_TM6(self):
        b = Board(2)
        self.assertFalse(b.flag_at(0, 0, FINISH_LOCKED))
        b.set_flag(0, 0, FINISH_LOCKED | SPAWN_PAD)
        self.assertTrue(b.flag_at(0, 0, FINISH_LOCKED))
        self.assertTrue(b.flag_at(0, 0, SPAWN_PAD))
        b.clear_flag(0, 0, SPAWN_PAD)
        self.assertTrue(b.flag_at(0, 0, FINISH_LOCKED))
        self.assertFalse(b.flag_at(0, 0, SPAWN_PAD))


if __name__ == "__main__":
    unittest.main()
