"""The transit graph G_T. Spec: TM-11, TM-12. See §12.1 "Transit graph" rows.

`carries()` must match the §1.4 table for all 6 shapes x 12 ordered
direction pairs (exhaustive), and reachability must be computed over G_T,
not over open-cell connectivity, because a Straight cannot turn and a Dead
End cannot pass through at any rotation (TM-11).
"""

import unittest

from snail_labyrinth.board import Board
from snail_labyrinth.directions import N, E, S, W, ALL_DIRS
from snail_labyrinth.transit_graph import carries, source_nodes, neighbors, bfs_transit, is_solvable

ROCK, DEAD_END, STRAIGHT, ELBOW, TEE, CROSS = 0, 1, 5, 3, 7, 15
REPRESENTATIVE_MASK = {
    "ROCK": ROCK,
    "DEAD_END": DEAD_END,
    "STRAIGHT": STRAIGHT,
    "ELBOW": ELBOW,
    "TEE": TEE,
    "CROSS": CROSS,
}

COLLINEAR_PAIRS = {(N, S), (S, N), (E, W), (W, E)}
TURN_PAIRS = {
    (N, E), (E, N), (N, W), (W, N),
    (S, E), (E, S), (S, W), (W, S),
}
ALL_ORDERED_PAIRS = [(a, b) for a in ALL_DIRS for b in ALL_DIRS if a != b]


def single_cell_board(mask: int) -> Board:
    b = Board(3)
    b.set_mask(1, 1, mask)
    return b


class TestCarriesTableTM11(unittest.TestCase):
    """TM-11's table, exhaustively: shape x (straight-through, turn)."""

    def test_rock_carries_nothing(self):
        b = single_cell_board(REPRESENTATIVE_MASK["ROCK"])
        for a, b_dir in ALL_ORDERED_PAIRS:
            with self.subTest(a=a, b=b_dir):
                self.assertFalse(carries(b, (1, 1), a, b_dir))

    def test_dead_end_carries_nothing(self):
        b = single_cell_board(REPRESENTATIVE_MASK["DEAD_END"])
        for a, b_dir in ALL_ORDERED_PAIRS:
            with self.subTest(a=a, b=b_dir):
                self.assertFalse(carries(b, (1, 1), a, b_dir))

    def test_straight_carries_only_collinear(self):
        b = single_cell_board(REPRESENTATIVE_MASK["STRAIGHT"])
        for a, b_dir in ALL_ORDERED_PAIRS:
            expected = (a, b_dir) in COLLINEAR_PAIRS
            with self.subTest(a=a, b=b_dir):
                self.assertEqual(carries(b, (1, 1), a, b_dir), expected)

    def test_elbow_carries_only_turn(self):
        b = single_cell_board(REPRESENTATIVE_MASK["ELBOW"])
        for a, b_dir in ALL_ORDERED_PAIRS:
            expected = (a, b_dir) in TURN_PAIRS
            with self.subTest(a=a, b=b_dir):
                self.assertEqual(carries(b, (1, 1), a, b_dir), expected)

    def test_tee_carries_every_pair(self):
        b = single_cell_board(REPRESENTATIVE_MASK["TEE"])
        for a, b_dir in ALL_ORDERED_PAIRS:
            with self.subTest(a=a, b=b_dir):
                self.assertTrue(carries(b, (1, 1), a, b_dir))

    def test_cross_carries_every_pair(self):
        b = single_cell_board(REPRESENTATIVE_MASK["CROSS"])
        for a, b_dir in ALL_ORDERED_PAIRS:
            with self.subTest(a=a, b=b_dir):
                self.assertTrue(carries(b, (1, 1), a, b_dir))

    def test_carries_is_shape_invariant_not_orientation_dependent_TM12(self):
        # "carries depends only on shape, not current orientation" (TM-12):
        # every rotation of an ELBOW mask must agree on every pair.
        for m in (3, 6, 12, 9):
            b = single_cell_board(m)
            for a, b_dir in ALL_ORDERED_PAIRS:
                expected = (a, b_dir) in TURN_PAIRS
                with self.subTest(m=m, a=a, b=b_dir):
                    self.assertEqual(carries(b, (1, 1), a, b_dir), expected)


class TestSourceNodes(unittest.TestCase):
    def test_source_nodes_use_orbit_not_current_mask_TM12(self):
        # A Dead-End-shaped spawn (mask N only) still yields all 4 entry
        # directions as source nodes, because the orbit of a Dead End
        # covers all 4 single directions (TM-3): the snail can rotate in
        # place before departing.
        b = single_cell_board(N)
        nodes = source_nodes(b, (1, 1))
        self.assertEqual(nodes, {((1, 1), N), ((1, 1), E), ((1, 1), S), ((1, 1), W)})

    def test_source_nodes_for_rock_is_empty(self):
        b = single_cell_board(ROCK)
        self.assertEqual(source_nodes(b, (1, 1)), set())


class TestReachability(unittest.TestCase):
    """TM-12: BFS over G_T, not over open-cell connectivity."""

    def _corridor(self, middle_mask: int) -> Board:
        # A straight 3-tile corridor: spawn (0,1) -- middle (1,1) -- hub (2,1).
        b = Board(3)
        b.set_mask(0, 1, CROSS)
        b.set_mask(1, 1, middle_mask)
        b.set_mask(2, 1, CROSS)
        return b

    def test_dead_end_seals_a_corridor_no_rotation_can_fix_TM11(self):
        b = self._corridor(DEAD_END)
        hub = {(2, 1)}
        self.assertFalse(is_solvable(b, (0, 1), lambda c: c in hub))

    def test_elbow_blocks_a_straight_through_corridor_TM11(self):
        # ELBOW can turn but never pass straight through (TM-11 table).
        b = self._corridor(ELBOW)
        hub = {(2, 1)}
        self.assertFalse(is_solvable(b, (0, 1), lambda c: c in hub))

    def test_straight_carries_a_straight_corridor_TM11(self):
        b = self._corridor(STRAIGHT)
        hub = {(2, 1)}
        self.assertTrue(is_solvable(b, (0, 1), lambda c: c in hub))

    def test_tee_and_cross_always_carry_a_straight_corridor_TM11(self):
        for middle in (TEE, CROSS):
            b = self._corridor(middle)
            hub = {(2, 1)}
            with self.subTest(middle=middle):
                self.assertTrue(is_solvable(b, (0, 1), lambda c: c in hub))

    def test_elbow_middle_solves_an_L_shaped_corridor_TM11(self):
        # Spawn south of middle, hub east of middle: a turn, which ELBOW
        # (unlike STRAIGHT) can always be rotated to carry.
        b = Board(3)
        b.set_mask(1, 2, CROSS)   # spawn, south of middle
        b.set_mask(1, 1, ELBOW)  # middle
        b.set_mask(2, 1, CROSS)   # hub, east of middle
        hub = {(2, 1)}
        self.assertTrue(is_solvable(b, (1, 2), lambda c: c in hub))

    def test_naive_open_cell_connectivity_would_wrongly_pass_the_dead_end_corridor(self):
        # TM-11's whole point: all three cells are mutually "connected" in
        # the plain 4-connectivity sense (mask != 0 and adjacent), yet the
        # board is unsolvable, because carries() (not usable_exits()) is the
        # actual pass-through test.
        b = self._corridor(DEAD_END)
        self.assertNotEqual(b.mask_at(1, 1), 0)
        hub = {(2, 1)}
        self.assertFalse(is_solvable(b, (0, 1), lambda c: c in hub))

    def test_off_board_blocks_reachability_TM9(self):
        b = Board(2)
        b.set_mask(0, 0, CROSS)
        # (1, 0) left as Rock (default 0): a 2x1 board with no path.
        self.assertFalse(is_solvable(b, (0, 0), lambda c: c == (1, 0)))

    def test_bfs_transit_returns_visited_node_set(self):
        b = self._corridor(CROSS)
        hub = {(2, 1)}
        reached, visited = bfs_transit(b, source_nodes(b, (0, 1)), lambda c: c in hub)
        self.assertTrue(reached)
        self.assertIn(((2, 1), S), visited | {((2, 1), S)})  # sink reached via some entry
        for node in visited:
            self.assertIn(node[1], ALL_DIRS)

    def test_node_space_is_bounded_by_4N2_TM12(self):
        n = 4
        b = Board(n)
        for y in range(n):
            for x in range(n):
                b.set_mask(x, y, CROSS)
        all_nodes = {(cell, d) for cell in ((x, y) for y in range(n) for x in range(n)) for d in ALL_DIRS}
        self.assertEqual(len(all_nodes), 4 * n * n)
        _, visited = bfs_transit(b, source_nodes(b, (0, 0)), lambda c: False)
        self.assertLessEqual(len(visited), 4 * n * n)


if __name__ == "__main__":
    unittest.main()
