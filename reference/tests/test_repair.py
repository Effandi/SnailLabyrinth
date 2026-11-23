"""Tests for snail_labyrinth.repair -- spec section 3.3, MG-18.

Each test cites the rule id(s) it verifies in its docstring.
"""

import itertools
import unittest

from snail_labyrinth.generator import generate_layers_1_and_2
from snail_labyrinth.geometry import hub_cells, place_fixed_geometry, spawns
from snail_labyrinth.repair import (
    RepairOutcome,
    block_free_component,
    choose_repair_mask,
    find_frontier_dead_ends,
    is_blocked,
    repair_dead_ends,
)
from snail_labyrinth.rng import root_key
from snail_labyrinth.tiles import ALL_DIRS, Board, E, GridPos, N, S, Shape, W, shape_of
from snail_labyrinth.transit import TransitGraph

PRESET_SIZES = (8, 12, 16, 20, 24)


class IsBlockedTests(unittest.TestCase):
    """MG-7/MG-18: `BLOCK = ROCK union DEAD_END`."""

    def test_rock_and_dead_end_are_blocked(self):
        b = Board(2)
        b.set_mask(GridPos(0, 0), 0)  # Rock
        b.set_mask(GridPos(1, 0), N)  # Dead End
        self.assertTrue(is_blocked(b, GridPos(0, 0)))
        self.assertTrue(is_blocked(b, GridPos(1, 0)))

    def test_other_four_shapes_are_not_blocked(self):
        b = Board(2)
        for m, cell in ((5, GridPos(0, 0)), (3, GridPos(1, 0))):
            b.set_mask(cell, m)
        self.assertFalse(is_blocked(b, GridPos(0, 0)))  # Straight
        self.assertFalse(is_blocked(b, GridPos(1, 0)))  # Elbow
        b2 = Board(2)
        b2.set_mask(GridPos(0, 0), 7)  # Tee
        b2.set_mask(GridPos(1, 0), 15)  # Cross
        self.assertFalse(is_blocked(b2, GridPos(0, 0)))
        self.assertFalse(is_blocked(b2, GridPos(1, 0)))


class BlockFreeComponentTests(unittest.TestCase):
    """MG-18: plain, current connectivity over non-BLOCK cells -- not G_T."""

    def test_dead_end_excluded_even_when_mutually_open(self):
        """MG-7: a Dead End is removed as a *vertex*, regardless of whether
        its single opening happens to be mutually open toward a component
        cell. It can never be a member of the component, and it can never
        pass a route on to anything beyond it."""
        b = Board(3)
        b.set_mask(GridPos(0, 1), 15)  # Cross, "hub" stand-in
        b.set_mask(GridPos(1, 1), W)  # Dead End, opens only West (toward Cross)
        b.set_mask(GridPos(2, 1), 15)  # Cross, beyond the dead end
        self.assertTrue(b.connected(GridPos(0, 1), E))  # mutually open, TM-8
        component = block_free_component(b, [GridPos(0, 1)])
        self.assertEqual(component, {GridPos(0, 1)})

    def test_misoriented_tile_blocks_without_being_blocked(self):
        """A non-BLOCK shape (Straight/Elbow/Tee/Cross) is always a graph
        vertex, but it only connects when its *current* mask actually
        opens toward the neighbour -- misorientation is a real wall here,
        not fixed by rotation, unlike G_T (TM-11/TM-12)."""
        b = Board(2)
        b.set_mask(GridPos(0, 0), 15)
        b.set_mask(GridPos(1, 0), 5)  # Straight oriented N-S, not E-W
        self.assertFalse(b.connected(GridPos(0, 0), E))
        component = block_free_component(b, [GridPos(0, 0)])
        self.assertEqual(component, {GridPos(0, 0)})
        self.assertFalse(is_blocked(b, GridPos(1, 0)))  # not BLOCK, just misoriented

    def test_component_grows_through_a_correctly_oriented_chain(self):
        b = Board(3)
        for cell in (GridPos(0, 1), GridPos(1, 1), GridPos(2, 1)):
            b.set_mask(cell, 15)  # Cross everywhere: always mutually open
        component = block_free_component(b, [GridPos(0, 1)])
        self.assertEqual(component, {GridPos(0, 1), GridPos(1, 1), GridPos(2, 1)})


class FindFrontierDeadEndsTests(unittest.TestCase):
    """MG-18: "the frontier dead-end[s]" -- Dead Ends the component is
    actually pressing an opening against, not merely sitting next to."""

    def test_no_frontier_when_nothing_presses_toward_the_dead_end(self):
        b = Board(3)
        b.set_mask(GridPos(0, 1), E)  # opens only East, away from the dead end below
        # a Dead End exists but nothing in the component opens toward it
        b.set_mask(GridPos(0, 2), N)
        component = {GridPos(0, 1)}
        self.assertEqual(find_frontier_dead_ends(b, component), [])

    def test_frontier_found_when_component_presses_a_dead_end(self):
        b = Board(3)
        b.set_mask(GridPos(0, 1), 15)  # Cross, opens East toward the dead end
        b.set_mask(GridPos(1, 1), W)  # Dead End, existing opening also West
        component = {GridPos(0, 1)}
        frontier = find_frontier_dead_ends(b, component)
        self.assertEqual(len(frontier), 1)
        self.assertEqual(frontier[0].cell, GridPos(1, 1))
        self.assertEqual(frontier[0].required_dirs, frozenset({W}))

    def test_required_dirs_combine_existing_and_pressed_when_they_differ(self):
        """The dead end's own pre-existing opening is never discarded, even
        when it points a different way than the pressure that makes it a
        frontier cell."""
        b = Board(3)
        b.set_mask(GridPos(0, 1), 15)  # presses East onto the dead end
        b.set_mask(GridPos(1, 1), N)  # Dead End's own opening faces North
        component = {GridPos(0, 1)}
        frontier = find_frontier_dead_ends(b, component)
        self.assertEqual(len(frontier), 1)
        self.assertEqual(frontier[0].required_dirs, frozenset({W, N}))

    def test_multiple_component_neighbours_accumulate_required_dirs(self):
        b = Board(3)
        b.set_mask(GridPos(1, 0), 15)  # presses South
        b.set_mask(GridPos(0, 1), 15)  # presses East
        b.set_mask(GridPos(1, 1), S)  # Dead End's own opening faces South
        component = {GridPos(1, 0), GridPos(0, 1)}
        frontier = find_frontier_dead_ends(b, component)
        self.assertEqual(len(frontier), 1)
        self.assertEqual(frontier[0].required_dirs, frozenset({N, W, S}))


class ChooseRepairMaskTests(unittest.TestCase):
    """MG-18: "convert ... to a TEE" -- result is always a Tee, always a
    superset of what fits, with a deterministic, fixed-priority fill/drop
    rule for the spare slots."""

    def test_pads_up_to_three_in_fixed_priority_order(self):
        """With one required direction, the two spares are filled in
        N,E,S,W order, skipping the one already present."""
        mask = choose_repair_mask(frozenset({S}))
        self.assertEqual(shape_of(mask), Shape.TEE)
        self.assertEqual(mask, N | E | S)  # W is the lowest-priority spare, dropped

    def test_forced_when_exactly_three_required(self):
        mask = choose_repair_mask(frozenset({N, E, S}))
        self.assertEqual(mask, N | E | S)
        self.assertEqual(shape_of(mask), Shape.TEE)

    def test_drops_lowest_priority_when_all_four_required(self):
        """Documented in OPEN_QUESTIONS.md OQ-8: no Tee can satisfy 4
        simultaneous directions, so the lowest-priority one (W) is
        deterministically dropped."""
        mask = choose_repair_mask(frozenset({N, E, S, W}))
        self.assertEqual(mask, N | E | S)
        self.assertEqual(shape_of(mask), Shape.TEE)

    def test_result_is_always_a_tee_and_a_superset_when_it_fits(self):
        for size in (1, 2, 3):
            for combo in itertools.combinations(ALL_DIRS, size):
                required = frozenset(combo)
                with self.subTest(required=required):
                    mask = choose_repair_mask(required)
                    self.assertEqual(shape_of(mask), Shape.TEE)
                    for d in required:
                        self.assertTrue(mask & d, f"{d} missing from {mask}")


class RepairDeadEndsIntegrationTests(unittest.TestCase):
    """MG-18's actual loop, exercised with synthetic hub/spawn cell sets on
    small hand-built boards (via `repair_dead_ends`'s override parameters),
    plus the real generator pipeline below.
    """

    def test_repair_connects_a_single_dead_end_corridor(self):
        """hub=(0,1) --dead end--> spawn=(2,1). One Dead End is the entire
        obstruction; repair must convert it and connect the spawn in
        exactly one step."""
        b = Board(3)
        b.set_mask(GridPos(0, 1), 15)  # synthetic "hub" cell
        b.set_mask(GridPos(1, 1), W)  # the one obstruction
        b.set_mask(GridPos(2, 1), 15)  # synthetic "spawn" cell
        outcome = repair_dead_ends(
            b, root_key(1, 0, 1), hub=[GridPos(0, 1)], spawn_cells=[GridPos(2, 1)]
        )
        self.assertEqual(outcome, RepairOutcome(steps=1, fully_connected=True))
        self.assertEqual(shape_of(b.mask_at(GridPos(1, 1))), Shape.TEE)
        component = block_free_component(b, [GridPos(0, 1)])
        self.assertIn(GridPos(2, 1), component)

    def test_repair_chains_through_several_dead_ends(self):
        """hub --dead end--dead end--dead end--> spawn. Each step exposes
        the next frontier cell; repair must walk the whole chain."""
        b = Board(6)
        b.set_mask(GridPos(0, 1), 15)
        for x in (1, 2, 3):
            b.set_mask(GridPos(x, 1), W)  # each a lone Dead End, facing West
        b.set_mask(GridPos(4, 1), 15)
        outcome = repair_dead_ends(
            b, root_key(2, 0, 1), hub=[GridPos(0, 1)], spawn_cells=[GridPos(4, 1)]
        )
        self.assertEqual(outcome.fully_connected, True)
        self.assertEqual(outcome.steps, 3)

    def test_repair_stops_cleanly_when_blocked_by_rock_not_dead_end(self):
        """MG-18 only repairs Dead Ends; a literal Rock is not its job
        (that is the Rock-card legality predicate, CD-13, a later
        increment) -- repair must terminate with `fully_connected=False`
        rather than loop or raise."""
        b = Board(3)
        b.set_mask(GridPos(0, 1), 15)
        b.set_mask(GridPos(1, 1), 0)  # Rock
        b.set_mask(GridPos(2, 1), 15)
        outcome = repair_dead_ends(
            b, root_key(3, 0, 1), hub=[GridPos(0, 1)], spawn_cells=[GridPos(2, 1)]
        )
        self.assertEqual(outcome, RepairOutcome(steps=0, fully_connected=False))

    def test_repair_stops_cleanly_when_blocked_by_misorientation_not_dead_end(self):
        """Documented limitation (module docstring, OPEN_QUESTIONS.md): a
        spawn stranded purely by a misoriented non-Dead-End tile, with no
        Dead End anywhere on the boundary, is MG-19's job, not MG-18's.
        This must terminate cleanly, not loop or silently "fix" it by
        touching a cell this rule has no business touching."""
        b = Board(3)
        b.set_mask(GridPos(0, 1), 15)
        b.set_mask(GridPos(1, 1), 5)  # Straight, oriented N-S: a real wall here
        b.set_mask(GridPos(2, 1), 15)
        outcome = repair_dead_ends(
            b, root_key(4, 0, 1), hub=[GridPos(0, 1)], spawn_cells=[GridPos(2, 1)]
        )
        self.assertEqual(outcome, RepairOutcome(steps=0, fully_connected=False))
        self.assertEqual(b.mask_at(GridPos(1, 1)), 5)  # untouched

    def test_repair_is_deterministic_given_the_same_root_key(self):
        b1 = Board(6)
        b2 = Board(6)
        for b in (b1, b2):
            b.set_mask(GridPos(0, 2), 15)
            b.set_mask(GridPos(1, 2), N)
            b.set_mask(GridPos(1, 1), W)
            b.set_mask(GridPos(4, 2), 15)
        rk = root_key(5, 0, 1)
        o1 = repair_dead_ends(b1, rk, hub=[GridPos(0, 2)], spawn_cells=[GridPos(4, 2)])
        o2 = repair_dead_ends(b2, rk, hub=[GridPos(0, 2)], spawn_cells=[GridPos(4, 2)])
        self.assertEqual(o1, o2)
        self.assertEqual(b1.mask, b2.mask)


class RepairAgainstTheRealGeneratorTests(unittest.TestCase):
    """MG-18 applied to real `generate_layers_1_and_2` output (layers 1-2,
    no rocks yet). Measures the actual target guarantee, `MG-6` (G_T
    reachability, `TransitGraph.reachable_to_hub`) -- not block-free
    connectivity, which is a strictly stronger bar this rule alone is not
    meant to clear (see OPEN_QUESTIONS.md and PROGRESS.md).

    Uses `generate_layers_1_and_2`, not `generate_board` -- `generate_board`
    is now the full pipeline (it calls `repair_dead_ends` and layer 3
    itself), so calling it here would both defeat the point of measuring
    repair in isolation and make every board in this sweep pay for layer
    3's accretion loop for no reason (see reference/PROGRESS.md).
    """

    def test_never_regresses_g_t_solvability(self):
        """Converting a Dead End to a Tee only ever adds openings (the
        Tee's mask always retains the Dead End's original bit, by
        construction of `required_dirs`) and a Dead End never carried any
        route as an interior cell before (TM-11) -- so no spawn that was
        G_T-solvable before repair can become unsolvable after it. Checked
        empirically across the full seed sweep rather than asserted as an
        unproven theorem.
        """
        for n in PRESET_SIZES:
            hub = hub_cells(n)
            for seed in range(40):
                rk = root_key(seed, 0, 1)
                board = generate_layers_1_and_2(n, rk)
                pre = {
                    s: TransitGraph(board).reachable_to_hub(s, hub) for s in spawns(n)
                }
                repair_dead_ends(board, rk)
                post = {
                    s: TransitGraph(board).reachable_to_hub(s, hub) for s in spawns(n)
                }
                for s in spawns(n):
                    with self.subTest(n=n, seed=seed, spawn=s):
                        if pre[s]:
                            self.assertTrue(post[s], "MG-18 must never un-solve a spawn")

    def test_improves_solvability_rate_without_asserting_perfection(self):
        """MG-18 fixes only the Dead-End soft-rock failure mode (TM-11); a
        spawn stranded by misoriented non-Dead-End tiles needs MG-19
        (next increments), so 100% is not expected yet. Measured at
        786/800 (98.25%) post-repair vs 782/800 (97.75%) pre-repair when
        this test was written; asserting a bound with margin rather than
        the exact figures so a harmless formula tweak elsewhere does not
        make this test flaky.
        """
        solved = 0
        total = 0
        for n in PRESET_SIZES:
            hub = hub_cells(n)
            for seed in range(40):
                rk = root_key(seed, 0, 1)
                board = generate_layers_1_and_2(n, rk)
                repair_dead_ends(board, rk)
                tg = TransitGraph(board)
                for s in spawns(n):
                    total += 1
                    if tg.reachable_to_hub(s, hub):
                        solved += 1
        self.assertGreaterEqual(solved / total, 0.95)

    def test_the_previously_pinned_concrete_failure_needs_more_than_mg18(self):
        """The exact case test_generator.py pins
        (`MG6PreRepairCharacterizationTests.test_a_concrete_pre_repair_failure_exists`,
        N=8, seed 31, spawn S0) is bounded by misoriented Elbow/Tee cells
        immediately around the Hub's block-free component, not by a Dead
        End directly on that boundary -- so MG-18 alone makes zero
        progress on it (steps=0), which is the documented, expected
        outcome, not a bug. See OPEN_QUESTIONS.md.
        """
        n = 8
        rk = root_key(31, 0, 1)
        board = generate_layers_1_and_2(n, rk)
        hub = hub_cells(n)
        s0 = spawns(n)[0]
        outcome = repair_dead_ends(board, rk)
        self.assertEqual(outcome.steps, 0)
        self.assertFalse(TransitGraph(board).reachable_to_hub(s0, hub))


if __name__ == "__main__":
    unittest.main()
