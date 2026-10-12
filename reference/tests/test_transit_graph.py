"""Tests for sim.transit_graph: carries(), G_T construction, BFS reachability.

Each test cites the spec rule id(s) it verifies (SNAIL_LABYRINTH_TECHNICAL_SPEC.md).
"""

import itertools
import unittest

from sim.tiles import N, E, S, W, DIRS, Grid
from sim.transit_graph import carries, build_graph, source_nodes, reachable_nodes, is_reachable

ORDERED_PAIRS = [(a, b) for a in DIRS for b in DIRS if a != b]
OPPOSITE_PAIRS = {(N, S), (S, N), (E, W), (W, E)}


class TestCarries(unittest.TestCase):
    """TM-11, TM-12: carries() depends only on shape (via orbit), matching the
    §1.4 table for all 6 shapes x 12 ordered direction pairs (HT-1)."""

    def test_rock_carries_nothing(self):
        for a, b in ORDERED_PAIRS:
            self.assertFalse(carries(0, a, b))

    def test_dead_end_carries_nothing(self):
        # TM-11: Dead End can "never" pass through at any rotation -- it is
        # a soft rock.
        for dead_end_mask in (N, E, S, W):
            for a, b in ORDERED_PAIRS:
                self.assertFalse(carries(dead_end_mask, a, b),
                                  f"dead end {dead_end_mask} wrongly carries {a}->{b}")

    def test_straight_carries_only_collinear(self):
        # TM-11: Straight carries straight-through (yes) but "never" turns.
        for straight_mask in (5, 10):
            for a, b in ORDERED_PAIRS:
                expected = (a, b) in OPPOSITE_PAIRS
                self.assertEqual(carries(straight_mask, a, b), expected,
                                  f"straight {straight_mask}: {a}->{b}")

    def test_elbow_carries_only_turns(self):
        # TM-11: Elbow carries a turn (yes) but "never" straight-through.
        for elbow_mask in (3, 6, 12, 9):
            for a, b in ORDERED_PAIRS:
                expected = (a, b) not in OPPOSITE_PAIRS
                self.assertEqual(carries(elbow_mask, a, b), expected,
                                  f"elbow {elbow_mask}: {a}->{b}")

    def test_tee_carries_everything(self):
        # TM-11: TEE carries both straight-through and turn, "always".
        for tee_mask in (7, 14, 13, 11):
            for a, b in ORDERED_PAIRS:
                self.assertTrue(carries(tee_mask, a, b), f"tee {tee_mask}: {a}->{b}")

    def test_cross_carries_everything(self):
        # TM-11: CROSS carries both straight-through and turn, "always".
        for a, b in ORDERED_PAIRS:
            self.assertTrue(carries(15, a, b), f"cross: {a}->{b}")

    def test_carries_symmetric_in_its_two_args(self):
        # MG-3: TAU[c][a][b] == TAU[c][b][a] relies on carries being symmetric.
        for m in range(16):
            for a, b in ORDERED_PAIRS:
                self.assertEqual(carries(m, a, b), carries(m, b, a))


class TestSourceNodes(unittest.TestCase):
    """TM-12: source(s) = the snail is already on its cell; any direction
    achievable as an opening under rotation is a valid entry label."""

    def test_rock_has_no_source_nodes(self):
        g = Grid(2)
        g.set_mask(0, 0, 0)
        self.assertEqual(source_nodes(g, (0, 0)), [])

    def test_nonzero_mask_has_all_four_source_nodes(self):
        g = Grid(2)
        g.set_mask(0, 0, N)  # a Dead End still yields all 4 virtual entries
        self.assertEqual(set(source_nodes(g, (0, 0))),
                          {((0, 0), N), ((0, 0), E), ((0, 0), S), ((0, 0), W)})


class TestTransitGraphBFS(unittest.TestCase):
    """TM-11, TM-12: plain non-Rock connectivity is not a sufficient
    reachability test; the BFS must run over G_T."""

    def test_dead_end_blocks_even_though_cell_is_not_rock(self):
        # TM-11: "a soft rock" -- naive non-Rock connectivity would call this
        # corridor passable (no cell is Rock); G_T correctly says it is not,
        # because a Dead End carries no pair at any rotation.
        # Source and sink are Cross (carry anything) so the only thing under
        # test is the middle cell's shape.
        g = Grid(3)
        g.set_mask(0, 0, 0xF)    # source: Cross
        g.set_mask(1, 0, N)      # middle: Dead End (any rotation, still 1 opening)
        g.set_mask(2, 0, 0xF)    # sink: Cross
        self.assertFalse(is_reachable(g, (0, 0), [(2, 0)]))

    def test_straight_cannot_turn_even_under_rotation(self):
        # TM-11: a Straight can "never" turn -- the path needs a turn at the
        # middle cell, which no rotation of a Straight can provide.
        g = Grid(2)
        g.set_mask(0, 0, 0xF)     # source: Cross
        g.set_mask(1, 0, 5)       # middle: Straight (N-S or E-W only, never a turn)
        g.set_mask(1, 1, 0xF)     # sink: Cross, South of the middle cell
        # (0,1) is left as Rock (default), so the only candidate route is
        # (0,0) -E-> (1,0) -S-> (1,1), which needs the middle cell to turn.
        self.assertFalse(is_reachable(g, (0, 0), [(1, 1)]))

    def test_elbow_carries_a_turn(self):
        g = Grid(2)
        g.set_mask(0, 0, 0xF)     # source: Cross
        g.set_mask(1, 0, 12)      # middle: Elbow S,W -- entering from W, exits S
        g.set_mask(1, 1, 0xF)     # sink: Cross
        self.assertTrue(is_reachable(g, (0, 0), [(1, 1)]))

    def test_straight_corridor_reachable_via_rotation(self):
        # Orientation is irrelevant to G_T (TM-12): the generator-time mask of
        # the middle cell is a Straight oriented N-S, but carries() still
        # finds the E-W path via orbit(), since rotation cards can fix it.
        g = Grid(3)
        g.set_mask(0, 0, 0xF)
        g.set_mask(1, 0, 5)   # Straight, currently N-S oriented
        g.set_mask(2, 0, 0xF)
        self.assertTrue(is_reachable(g, (0, 0), [(2, 0)]))

    def test_rock_blocks_unconditionally(self):
        g = Grid(3)
        g.set_mask(0, 0, 0xF)
        g.set_mask(1, 0, 0)   # Rock
        g.set_mask(2, 0, 0xF)
        self.assertFalse(is_reachable(g, (0, 0), [(2, 0)]))

    def test_cross_junction_reaches_all_four_sides(self):
        g = Grid(3)
        g.set_mask(1, 1, 15)  # Cross at the centre
        for (dx, dy) in ((1, 0), (2, 1), (1, 2), (0, 1)):
            g.set_mask(dx, dy, 0xF)
        nodes = reachable_nodes(g, [(1, 0)])
        reached_cells = {cell for cell, _ in nodes}
        self.assertIn((1, 2), reached_cells)
        self.assertIn((0, 1), reached_cells)
        self.assertIn((2, 1), reached_cells)

    def test_border_is_never_a_valid_edge_target(self):
        # TM-9 + TM-12: edges require mask[u] != 0; off-grid is mask 0.
        g = Grid(1)
        g.set_mask(0, 0, 0xF)
        graph = build_graph(g)
        # No outgoing edges exist at all: every neighbour is off-grid.
        self.assertEqual(graph.get(((0, 0), N), []), [])


if __name__ == "__main__":
    unittest.main()
