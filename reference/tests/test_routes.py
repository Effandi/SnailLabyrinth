"""Tests for snail_labyrinth.routes -- MG-7: two vertex-disjoint routes per
spawn, over G_T, with a shared cell never counted twice.
"""

import unittest

from snail_labyrinth.geometry import hub_cells, spawns, start_pad_inward_neighbour
from snail_labyrinth.generator import generate_board
from snail_labyrinth.repair import repair_dead_ends
from snail_labyrinth.rng import root_key
from snail_labyrinth.routes import exempt_cells, has_two_vertex_disjoint_routes
from snail_labyrinth.tiles import Board, E, GridPos, N, S, W

PRESET_SIZES = (8, 12, 16, 20, 24)


class ExemptCellsTests(unittest.TestCase):
    """MG-7 / GE-2 / GE-8: Hub, Spawn Pads and Start-Pad inward neighbours
    can never carry a Rock, so they need no vertex cap."""

    def test_exempt_set_contains_hub_spawns_and_inward_neighbours(self):
        n = 16
        exempt = exempt_cells(n)
        for c in hub_cells(n):
            self.assertIn(c, exempt)
        for c in spawns(n):
            self.assertIn(c, exempt)
        for k in range(4):
            self.assertIn(start_pad_inward_neighbour(n, k), exempt)

    def test_exempt_set_size_for_16(self):
        # 4 Hub + 4 spawns + 4 inward neighbours = 12, all distinct at N=16.
        self.assertEqual(len(exempt_cells(16)), 12)


class TwoParallelCorridorsTests(unittest.TestCase):
    """Hand-built boards with a known, countable number of vertex-disjoint
    routes, to pin down the flow network's correctness independent of the
    real generator. `exempt=[]` is passed explicitly throughout so these
    small synthetic boards are not accidentally coupled to whatever the
    real GE-1/GE-5/GE-8 geometry formulas happen to compute for a small
    `n` (see `has_two_vertex_disjoint_routes`'s `exempt` override)."""

    def test_two_independent_branches_give_two_routes(self):
        """Spawn (1,1) departs North to Hub cell (1,0) and South to Hub
        cell (1,2) -- two branches sharing no cell but the spawn itself
        (which is never counted against the cap)."""
        n = 3
        board = Board(n)
        board.set_mask(GridPos(1, 1), 15)  # Cross: can depart any direction
        board.set_mask(GridPos(1, 0), 15)
        board.set_mask(GridPos(1, 2), 15)
        for p in (GridPos(0, 0), GridPos(2, 0), GridPos(0, 1), GridPos(2, 1), GridPos(0, 2), GridPos(2, 2)):
            board.set_mask(p, 0)
        hub = [GridPos(1, 0), GridPos(1, 2)]
        self.assertTrue(has_two_vertex_disjoint_routes(board, GridPos(1, 1), hub, exempt=[]))

    def test_single_branch_with_only_one_route_fails(self):
        n = 3
        board = Board(n)
        board.set_mask(GridPos(1, 1), N)  # Dead End: only one departure
        board.set_mask(GridPos(1, 0), 15)
        for p in (GridPos(0, 0), GridPos(2, 0), GridPos(0, 1), GridPos(2, 1), GridPos(0, 2), GridPos(1, 2), GridPos(2, 2)):
            board.set_mask(p, 0)
        hub = [GridPos(1, 0)]
        self.assertFalse(has_two_vertex_disjoint_routes(board, GridPos(1, 1), hub, exempt=[]))

    # Shared topology for the next two tests: two genuinely separate
    # branches (row y=1 and row y=3) that only ever meet again at a single
    # choke cell (2,2) before reaching the Hub at (3,2).
    #
    #   (0,1)--(1,1)--(2,1)
    #     |                \
    #   (0,2)             (2,2)---(3,2)=HUB
    #     |                /
    #   (0,3)--(1,3)--(2,3)
    #
    # Every used cell is a Cross (mask 15) so shape never gates which
    # direction pairs are legal -- the only thing under test is the vertex
    # cap itself.
    _N = 4
    _USED = (
        GridPos(0, 2),  # spawn
        GridPos(0, 1), GridPos(1, 1), GridPos(2, 1),  # branch A (row 1)
        GridPos(0, 3), GridPos(1, 3), GridPos(2, 3),  # branch B (row 3)
        GridPos(2, 2),  # choke
        GridPos(3, 2),  # hub
    )

    def _choke_board(self):
        board = Board(self._N)
        for p in self._USED:
            board.set_mask(p, 15)
        return board

    def test_shared_choke_cell_caps_at_one_route_even_with_two_branches(self):
        """Two genuinely separate branches both funnel through a single
        shared cell (2,2) before reaching the Hub: real max-flow is 1, not
        2, because that one cell can only ever carry one route
        (vertex-disjointness). The Hub cell itself is held exempt in both
        this test and the next, so only the choke's own exemption is the
        variable under test."""
        board = self._choke_board()
        hub = [GridPos(3, 2)]
        self.assertFalse(
            has_two_vertex_disjoint_routes(
                board, GridPos(0, 2), hub, exempt=[GridPos(3, 2)]
            )
        )

    def test_exempt_cell_does_not_count_against_the_cap(self):
        """Same topology as above, but the choke cell (2,2) is additionally
        marked exempt (as a Hub cell would be in the real geometry): two
        routes may then legitimately both pass through it, since a cell
        that can never be Rocked needs no disjointness defence."""
        board = self._choke_board()
        hub = [GridPos(3, 2)]
        self.assertTrue(
            has_two_vertex_disjoint_routes(
                board, GridPos(0, 2), hub, exempt=[GridPos(3, 2), GridPos(2, 2)]
            )
        )


class RoutesAgainstTheRealGeneratorTests(unittest.TestCase):
    """MG-7 measured against real (post-repair, pre-accretion) boards. No
    rocks exist on these boards yet, so this mostly characterizes how often
    layer 1-2 + MG-18 alone already gives two disjoint routes -- useful as
    a sanity check before layer 3 (which actively relies on this predicate
    to gate every Rock placement) is built on top of it.
    """

    def test_runs_without_error_across_a_small_sweep_and_never_exceeds_g_t(self):
        """A spawn with two vertex-disjoint routes must also be plain-G_T
        reachable (MG-6) -- vertex-disjoint routes imply at least one
        route exists. Checked as an implication, not asserting any
        particular rate (that is this increment's accretion loop's job to
        improve, not layer 1-2 + MG-18's).
        """
        for n in PRESET_SIZES:
            hub = hub_cells(n)
            for seed in range(5):
                rk = root_key(seed, 0, 1)
                board = generate_board(n, rk)
                repair_dead_ends(board, rk)
                for s in spawns(n):
                    with self.subTest(n=n, seed=seed, spawn=s):
                        from snail_labyrinth.transit import TransitGraph

                        reachable = TransitGraph(board).reachable_to_hub(s, hub)
                        two_routes = has_two_vertex_disjoint_routes(board, s, hub)
                        if two_routes:
                            self.assertTrue(reachable)


if __name__ == "__main__":
    unittest.main()
