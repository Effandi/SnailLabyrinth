"""Tests for snail_labyrinth.transit: TM-11, TM-12.

Every test cites the spec rule(s) it verifies. See reference/OPEN_QUESTIONS.md
for the interpretive note on `first_departures` vs. the spec's literal
`source()` formula.
"""

import unittest
from collections import deque

from snail_labyrinth.tiles import ALL_DIRS, Board, E, GridPos, N, S, W, delta, opp
from snail_labyrinth.transit import (
    ACT_MILLI,
    STEP_MILLI,
    SolveCost,
    TransitGraph,
    TransitNode,
    carries,
    tau_milli,
)

# The 12 ordered pairs of distinct single-bit directions, split by TM-11's
# "straight-through" vs. "turn" classification.
COLLINEAR_PAIRS = [(N, S), (S, N), (E, W), (W, E)]
TURN_PAIRS = [
    (N, E), (E, N), (N, W), (W, N),
    (S, E), (E, S), (S, W), (W, S),
]
ALL_ORDERED_PAIRS = COLLINEAR_PAIRS + TURN_PAIRS


class CarriesTableTests(unittest.TestCase):
    """TM-11: carries() must match the shape/interior-cell table exactly,
    exhaustively over all 6 shapes x 12 ordered direction pairs (HT-1)."""

    def test_TM11_rock_carries_nothing(self):
        for a, b in ALL_ORDERED_PAIRS:
            self.assertFalse(carries(0, a, b))

    def test_TM11_dead_end_carries_nothing_at_any_rotation(self):
        """"a Dead End carries no pair" -- exhaustive over all 4 dead-end masks."""
        for m in (N, E, S, W):
            for a, b in ALL_ORDERED_PAIRS:
                self.assertFalse(carries(m, a, b), msg=f"mask {m} carries {a}->{b}")

    def test_TM11_straight_carries_only_collinear(self):
        """"a Straight carries only collinear" -- never a turn."""
        for m in (5, 10):
            for a, b in COLLINEAR_PAIRS:
                self.assertTrue(carries(m, a, b), msg=f"mask {m} should carry {a}->{b}")
            for a, b in TURN_PAIRS:
                self.assertFalse(carries(m, a, b), msg=f"mask {m} should not carry {a}->{b}")

    def test_TM11_elbow_carries_only_a_turn(self):
        """"an Elbow carries only turns" -- never straight-through."""
        for m in (3, 6, 12, 9):
            for a, b in TURN_PAIRS:
                self.assertTrue(carries(m, a, b), msg=f"mask {m} should carry {a}->{b}")
            for a, b in COLLINEAR_PAIRS:
                self.assertFalse(carries(m, a, b), msg=f"mask {m} should not carry {a}->{b}")

    def test_TM11_tee_carries_every_pair(self):
        for m in (7, 14, 13, 11):
            for a, b in ALL_ORDERED_PAIRS:
                self.assertTrue(carries(m, a, b), msg=f"mask {m} should carry {a}->{b}")

    def test_TM11_cross_carries_every_pair(self):
        for a, b in ALL_ORDERED_PAIRS:
            self.assertTrue(carries(15, a, b))

    def test_TM12_carries_depends_only_on_shape_not_current_orientation(self):
        """Both Straight masks (and all 4 masks of each other multi-rotation
        shape) must agree on every pair -- carries is a function of shape."""
        for group in [(5, 10), (3, 6, 12, 9), (7, 14, 13, 11), (1, 2, 4, 8)]:
            for a, b in ALL_ORDERED_PAIRS:
                results = {carries(m, a, b) for m in group}
                self.assertEqual(len(results), 1, msg=f"group {group} disagrees on {a}->{b}")


def _naive_open_cell_bfs(board: Board, start: GridPos, hub) -> bool:
    """The naive reachability test TM-11 explicitly warns against: any two
    adjacent non-Rock cells are treated as connected, ignoring shape and
    orientation entirely. Used only to demonstrate the gap it leaves."""
    hub = set(hub)
    if start in hub:
        return True
    if board.mask_at(start) == 0:
        return False
    seen = {start}
    queue = deque([start])
    while queue:
        cell = queue.popleft()
        for d in ALL_DIRS:
            nb = cell + delta(d)
            if board.mask_at(nb) == 0 or nb in seen:
                continue
            if nb in hub:
                return True
            seen.add(nb)
            queue.append(nb)
    return False


class TransitGraphReachabilityTests(unittest.TestCase):
    """TM-12: BFS over G_T, the primitive behind MG-6, AS-2 and CD-13 condition 6."""

    def test_TM12_straight_corridor_is_reachable(self):
        b = Board(5)
        start, hub_cell = GridPos(0, 2), GridPos(4, 2)
        b.set_mask(start, E)  # a dead-end origin facing the corridor.
        for x in (1, 2, 3):
            b.set_mask(GridPos(x, 2), 10)  # E-W straight.
        b.set_mask(hub_cell, 15)
        g = TransitGraph(b)
        self.assertTrue(g.reachable_to_hub(start, {hub_cell}))

    def test_MG6_a_rock_on_the_corridor_makes_the_hub_unreachable(self):
        b = Board(5)
        start, hub_cell = GridPos(0, 2), GridPos(4, 2)
        b.set_mask(start, E)
        b.set_mask(GridPos(1, 2), 10)
        b.set_mask(GridPos(2, 2), 0)  # Rock Blocker in the middle of the corridor.
        b.set_mask(GridPos(3, 2), 10)
        b.set_mask(hub_cell, 15)
        g = TransitGraph(b)
        self.assertFalse(g.reachable_to_hub(start, {hub_cell}))

    def test_TM11_a_straight_that_must_turn_is_unsolvable_even_though_naive_connectivity_passes_it(self):
        """This is TM-11's central claim, made concrete: plain open-cell
        connectivity says this board is fine; G_T says it needs a Wildcard.
        """
        b = Board(3)
        start, turn_cell, hub_cell = GridPos(0, 0), GridPos(1, 0), GridPos(1, 1)
        b.set_mask(start, E)
        b.set_mask(turn_cell, 10)  # a Straight: can never turn, at any rotation.
        b.set_mask(hub_cell, 15)

        self.assertTrue(
            _naive_open_cell_bfs(b, start, {hub_cell}),
            msg="test setup: naive connectivity should see all three cells as linked",
        )
        g = TransitGraph(b)
        self.assertFalse(
            g.reachable_to_hub(start, {hub_cell}),
            msg="a Straight can never carry a turn, at any rotation (TM-11)",
        )

    def test_TM11_the_same_layout_is_solvable_with_an_elbow_at_the_turn(self):
        b = Board(3)
        start, turn_cell, hub_cell = GridPos(0, 0), GridPos(1, 0), GridPos(1, 1)
        b.set_mask(start, E)
        b.set_mask(turn_cell, 3)  # an Elbow: some rotation carries W->S.
        b.set_mask(hub_cell, 15)
        g = TransitGraph(b)
        self.assertTrue(g.reachable_to_hub(start, {hub_cell}))

    def test_TM12_a_dead_end_can_be_an_origin_but_never_an_interior_cell(self):
        """A Dead End the snail is *standing on* can still depart (TM-12
        source semantics); the same Dead End reached mid-route cannot be
        passed through (TM-11's "never -- it is a soft rock")."""
        # Case 1: the snail's own cell is a Dead End immediately adjacent to
        # the Hub -- departure needs no paired "entry" side.
        b1 = Board(2)
        start, hub_cell = GridPos(0, 0), GridPos(1, 0)
        b1.set_mask(start, E)
        b1.set_mask(hub_cell, 15)
        g1 = TransitGraph(b1)
        self.assertTrue(g1.reachable_to_hub(start, {hub_cell}))

        # Case 2: the same Dead End shape sits between the source and the
        # Hub -- now it must be entered along a real edge, and carries()
        # never holds for a Dead End, so it is a dead stop.
        b2 = Board(3)
        source, dead_end_cell, hub_cell2 = GridPos(0, 0), GridPos(1, 0), GridPos(2, 0)
        b2.set_mask(source, E)
        b2.set_mask(dead_end_cell, W)  # a Dead End, entered from the west.
        b2.set_mask(hub_cell2, 15)
        g2 = TransitGraph(b2)
        self.assertFalse(g2.reachable_to_hub(source, {hub_cell2}))

    def test_TM12_off_grid_neighbour_never_yields_an_edge(self):
        b = Board(2)
        corner = GridPos(0, 0)
        b.set_mask(corner, N)  # only opens off-grid.
        g = TransitGraph(b)
        self.assertEqual(g.first_departures(corner), [])

    def test_TM12_edges_from_never_reverses_into_the_entry_direction(self):
        """carries() requires a != b (TM-12); a node can never "carry" straight
        back the way it came."""
        b = Board(3)
        centre = GridPos(1, 1)
        b.set_mask(centre, 15)
        for d in ALL_DIRS:
            b.set_mask(centre + delta(d), 15)
        g = TransitGraph(b)
        for d in ALL_DIRS:
            node = TransitNode(centre, d)
            for _next_node, via in g.edges_from(node):
                self.assertNotEqual(via, d)

    def test_TM12_reachable_set_includes_the_hub_neighbourhood(self):
        b = Board(3)
        start, hub_cell = GridPos(0, 1), GridPos(2, 1)
        b.set_mask(start, E)
        b.set_mask(GridPos(1, 1), 10)
        b.set_mask(hub_cell, 15)
        g = TransitGraph(b)
        reached_cells = {node.cell for node in g.reachable_node_set(start)}
        self.assertIn(GridPos(1, 1), reached_cells)
        self.assertIn(hub_cell, reached_cells)

    def test_TM12_start_cell_already_in_hub_is_trivially_reachable(self):
        b = Board(2)
        p = GridPos(0, 0)
        b.set_mask(p, 15)
        g = TransitGraph(b)
        self.assertTrue(g.reachable_to_hub(p, {p}))


class WeightedCostModelTests(unittest.TestCase):
    """MG-2, MG-3: the weighted cost model (`TAU`, `ACT`, `SolveCost`) laid
    on top of G_T. See OPEN_QUESTIONS.md OQ-3 and OQ-4 for the two
    interpretive notes this part of the spec required."""

    def test_MG2_tau_milli_is_none_exactly_when_carries_is_false(self):
        """TAU must be infinite exactly where carries() is false, and finite
        exactly where it's true -- exhaustive over all 16 masks x 12 ordered
        direction pairs."""
        for m in range(16):
            for a, b in ALL_ORDERED_PAIRS:
                is_finite = tau_milli(m, a, b) is not None
                self.assertEqual(is_finite, carries(m, a, b), f"mask={m} a={a} b={b}")

    def test_MG2_tau_milli_is_symmetric(self):
        for m in range(16):
            for a, b in ALL_ORDERED_PAIRS:
                self.assertEqual(tau_milli(m, a, b), tau_milli(m, b, a))

    def test_MG2_tau_milli_is_zero_when_the_pair_is_already_open(self):
        """If both openings are already present on the current mask, no
        rotation card is needed at all (ACT[0] == 0)."""
        for m in range(16):
            for a, b in ALL_ORDERED_PAIRS:
                if (m & a) and (m & b):
                    self.assertEqual(tau_milli(m, a, b), 0, f"mask={m} a={a} b={b}")

    def test_MG2_cross_never_needs_a_rotation(self):
        """A Cross (mask 15) already carries every pair at every rotation,
        so TAU is always 0 -- cheapest possible, matching ACT[0]."""
        for a, b in ALL_ORDERED_PAIRS:
            self.assertEqual(tau_milli(15, a, b), 0)

    def test_MG2_straight_needs_exactly_one_card_to_flip_axis(self):
        """TM-5: cw(5) == ccw(5) == 10 -- a Straight needs exactly one
        rotation card (either CW or CCW, same result) to go from N-S to
        E-W, so TAU for the off-axis pair is ACT[1], not ACT[2] or ACT[3]."""
        self.assertEqual(tau_milli(5, N, S), 0)  # already N-S
        self.assertEqual(tau_milli(5, W, E), ACT_MILLI[1])
        self.assertEqual(tau_milli(10, W, E), 0)  # already E-W
        self.assertEqual(tau_milli(10, N, S), ACT_MILLI[1])

    def test_MG2_elbow_worked_example(self):
        """Elbow mask 3 (N,E). The opposite corner pair (S,W) is only ever
        open after exactly 2 quarter-turns (mask 12), and no other delta
        reaches a mask with both S and W open, so TAU must be ACT[2]
        (1600), not 2 * ACT[1] (2000)."""
        self.assertEqual(tau_milli(3, N, E), 0)
        self.assertEqual(tau_milli(3, S, W), ACT_MILLI[2])

    def test_MG2_tee_worked_example(self):
        """TEE mask 7 (missing W, i.e. N,E,S open). The pair (N, W) first
        becomes available after 2 turns (mask 13, missing E) and again
        after 3 (mask 11, missing S) -- both carry {N, W}, so TAU must take
        the cheaper of the two (ACT[3] == 1000), not ACT[2] (1600)."""
        self.assertEqual(tau_milli(7, N, E), 0)
        self.assertEqual(tau_milli(7, N, W), ACT_MILLI[3])

    def test_MG6_solve_cost_is_zero_when_already_at_the_hub(self):
        b = Board(2)
        p = GridPos(0, 0)
        b.set_mask(p, 15)
        g = TransitGraph(b)
        self.assertEqual(g.solve_cost(p, {p}), SolveCost(0, 0))

    def test_MG6_solve_cost_is_none_when_unreachable(self):
        b = Board(3)
        start, hub_cell = GridPos(0, 0), GridPos(2, 2)
        b.set_mask(start, 15)
        b.set_mask(hub_cell, 15)
        # Everything else stays mask 0 (Rock): no route at all.
        g = TransitGraph(b)
        self.assertIsNone(g.solve_cost(start, {hub_cell}))

    def test_MG2_solve_cost_decomposes_R_and_L_on_a_corridor_needing_one_rotation(self):
        """A straight-line corridor start -> mid -> hub, 3 cells, travelling
        East each hop. The middle tile is a Straight on the wrong axis
        (mask 5, N-S) -- carrying the required (W, E) pair costs exactly one
        rotation card (see test_MG2_straight_needs_exactly_one_card_to_flip_axis).
        Expected: L = 2 tiles travelled, R = 1 card action, no cheaper route
        exists (it's the only path), so SolveCost is pinned down exactly.
        """
        b = Board(3)
        start, mid, hub_cell = GridPos(0, 0), GridPos(1, 0), GridPos(2, 0)
        b.set_mask(start, 15)
        b.set_mask(mid, 5)  # STRAIGHT, currently N-S; path needs W-E
        b.set_mask(hub_cell, 15)
        g = TransitGraph(b)
        cost = g.solve_cost(start, {hub_cell})
        self.assertIsNotNone(cost)
        self.assertEqual(cost.tiles, 2)
        self.assertEqual(cost.r_milli, ACT_MILLI[1])
        self.assertEqual(cost.l_milli, 2 * STEP_MILLI)
        self.assertEqual(cost.c_milli, 2 * ACT_MILLI[1] + 2 * STEP_MILLI)

    def test_MG2_solve_cost_is_zero_rotation_cost_through_an_all_cross_corridor(self):
        """A Cross never needs a rotation (test_MG2_cross_never_needs_a_rotation),
        so a corridor of N crosses costs R=0 and L=N tiles exactly."""
        n = 6
        b = Board(n)
        for x in range(n):
            b.set_mask(GridPos(x, 0), 15)
        start, hub_cell = GridPos(0, 0), GridPos(n - 1, 0)
        g = TransitGraph(b)
        cost = g.solve_cost(start, {hub_cell})
        self.assertEqual(cost, SolveCost(0, (n - 1) * STEP_MILLI))
        self.assertEqual(cost.tiles, n - 1)

    def test_MG2_solve_cost_prefers_the_cheaper_of_two_equal_length_routes(self):
        """A diamond: start=(0,0), hub=(1,1), two alternate 2-hop routes via
        (1,0) or (0,1). The (1,0) route needs an Elbow rotated 2 quarter-turns
        to carry (W, S) -- ACT[2] == 1600 -- while the (0,1) route is already
        a Cross and carries everything for free. Equal tile length (2 hops
        either way) isolates the rotation cost: Dijkstra over `edgeCost`
        must prefer the free route, not whichever is enumerated first.
        """
        b = Board(2)
        start, hub_cell = GridPos(0, 0), GridPos(1, 1)
        via_elbow, via_cross = GridPos(1, 0), GridPos(0, 1)
        b.set_mask(start, 15)
        b.set_mask(via_elbow, 3)  # ELBOW (N,E); carrying (W,S) costs ACT[2] = 1600
        b.set_mask(via_cross, 15)  # CROSS; carries (N,E) for free
        b.set_mask(hub_cell, 15)
        g = TransitGraph(b)

        # Pin down the elbow route's own cost first, so the test documents
        # *why* the diamond's shortest path must avoid it.
        self.assertEqual(tau_milli(3, W, S), ACT_MILLI[2])

        cost = g.solve_cost(start, {hub_cell})
        self.assertEqual(cost, SolveCost(0, 2 * STEP_MILLI))


if __name__ == "__main__":
    unittest.main()
