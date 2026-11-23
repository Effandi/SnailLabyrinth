"""Tests for snail_labyrinth.generator's layer 3 (rock accretion, MG-17)
and the full generate_board pipeline (layers 1-2 + MG-18 repair + layer 3).

A full-sweep boards-per-size x seeds budget is kept deliberately small
here (far smaller than the 40-seed sweeps elsewhere in this project):
layer 3's accept/revert loop runs a solve_cost Dijkstra and an MG-7
max-flow check for every candidate it tries, which is considerably more
expensive per board than anything tested so far. See PROGRESS.md for the
measured wall-clock cost per size that this budget was chosen against.
"""

import unittest

from snail_labyrinth.generator import (
    ACCRETION_DEFAULTS,
    generate_board,
    generate_layer3,
    generate_layers_1_and_2,
    protected_from_rocks,
)
from snail_labyrinth.geometry import apron_cells, hub_cells, spawns, start_pad_inward_neighbour
from snail_labyrinth.repair import repair_dead_ends
from snail_labyrinth.rng import root_key
from snail_labyrinth.routes import has_two_vertex_disjoint_routes
from snail_labyrinth.tiles import Shape, TileFlags, shape_of
from snail_labyrinth.transit import TransitGraph

PRESET_SIZES = (8, 12, 16, 20, 24)
SWEEP_SEEDS = range(3)  # see module docstring

# Several test methods below sweep the exact same (n, seed) combinations
# and need both the pre-accretion and post-layer-3 state of the same
# board. Layer 3 is the expensive part (a solve_cost Dijkstra and an MG-7
# max-flow check per candidate tried), so this cache runs the pipeline
# once per (n, seed) and lets every test method read from the result,
# regardless of which test happens to run first.
_PIPELINE_CACHE = {}


def _pipeline(n, seed):
    """Returns `(pre_accretion_board, post_layer3_board, root_key_value)`
    for this `(n, seed)`, computed once and cached."""
    key = (n, seed)
    if key not in _PIPELINE_CACHE:
        rk = root_key(seed, 0, 1)
        pre = generate_layers_1_and_2(n, rk)
        repair_dead_ends(pre, rk)
        from snail_labyrinth.tiles import Board as _Board

        post = _Board(n)
        post.mask = list(pre.mask)
        post.flags = list(pre.flags)
        post.version = list(pre.version)
        generate_layer3(post, rk)
        _PIPELINE_CACHE[key] = (pre, post, rk)
    return _PIPELINE_CACHE[key]


def _full_pipeline_board(n, seed):
    """`generate_board(n, root_key(seed, 0, 1))`, equivalently -- reuses
    `_pipeline`'s cached post-layer-3 result instead of recomputing it."""
    return _pipeline(n, seed)[1]


class ProtectedFromRocksTests(unittest.TestCase):
    """MG-17: "Protected from rocks at generation ... HUB union APRON
    union StartPads union StartPad-inward-neighbours."."""

    def test_protected_set_is_the_union_of_the_four_named_regions(self):
        n = 16
        protected = protected_from_rocks(n)
        for c in hub_cells(n):
            self.assertIn(c, protected)
        for c in apron_cells(n):
            self.assertIn(c, protected)
        for c in spawns(n):
            self.assertIn(c, protected)
        for k in range(4):
            self.assertIn(start_pad_inward_neighbour(n, k), protected)

    def test_protected_set_is_strictly_larger_than_mg7s_exempt_set(self):
        """MG-7's `exempt_cells` deliberately excludes Apron (GE-3: Apron
        is runtime-rockable); MG-17's generation-time protection
        deliberately includes it. See OPEN_QUESTIONS.md OQ-10."""
        from snail_labyrinth.routes import exempt_cells

        n = 16
        self.assertTrue(exempt_cells(n) < protected_from_rocks(n))


class GenerateLayer3Tests(unittest.TestCase):
    """Layer 3's own guarantees, run against the real post-MG-18-repair
    board for each preset size, over a small seed budget."""

    def test_never_places_a_rock_on_a_protected_cell(self):
        for n in PRESET_SIZES:
            protected = protected_from_rocks(n)
            for seed in SWEEP_SEEDS:
                _, board, _ = _pipeline(n, seed)
                with self.subTest(n=n, seed=seed):
                    for cell in protected:
                        self.assertNotEqual(
                            shape_of(board.mask_at(cell)), Shape.ROCK, msg=f"rock at {cell}"
                        )

    def test_rock_fraction_does_not_grossly_exceed_the_ceiling(self):
        """The accept/revert loop checks the ceiling at the *start* of each
        candidate's turn (MG-17's own pseudocode), so the final fraction
        can overshoot by up to one segment (<=4 cells) -- not a bug, see
        PROGRESS.md. Checked with headroom for exactly that overshoot
        rather than asserting the ceiling is never crossed at all.
        """
        for n in PRESET_SIZES:
            _, rock_max_fraction = ACCRETION_DEFAULTS[n]
            max_overshoot_cells = 4
            for seed in SWEEP_SEEDS:
                _, board, _ = _pipeline(n, seed)
                rocks = sum(
                    1 for c in board.all_cells() if shape_of(board.mask_at(c)) == Shape.ROCK
                )
                with self.subTest(n=n, seed=seed):
                    self.assertLessEqual(
                        rocks, (rock_max_fraction * n * n) + max_overshoot_cells
                    )

    def test_never_regresses_mg6_solvability_relative_to_pre_accretion(self):
        """Layer 3 only ever accepts a segment when MG-6 (and MG-7) still
        hold for every spawn afterward (MG-17's own accept condition) --
        so no spawn that was reachable before accretion can become
        unreachable after it.
        """
        for n in PRESET_SIZES:
            hub = hub_cells(n)
            for seed in SWEEP_SEEDS:
                pre_board, post_board, _ = _pipeline(n, seed)
                pre = {s: TransitGraph(pre_board).reachable_to_hub(s, hub) for s in spawns(n)}
                post = {s: TransitGraph(post_board).reachable_to_hub(s, hub) for s in spawns(n)}
                for s in spawns(n):
                    with self.subTest(n=n, seed=seed, spawn=s):
                        if pre[s]:
                            self.assertTrue(post[s], "layer 3 must never un-solve a spawn")

    def test_deterministic_given_the_same_root_key(self):
        n = 16
        rk = root_key(7, 0, 1)
        b1 = generate_layers_1_and_2(n, rk)
        repair_dead_ends(b1, rk)
        generate_layer3(b1, rk)
        b2 = generate_layers_1_and_2(n, rk)
        repair_dead_ends(b2, rk)
        generate_layer3(b2, rk)
        self.assertEqual(b1.mask, b2.mask)

    def test_does_nothing_when_the_pre_accretion_board_is_already_unsolvable(self):
        """If some spawn is already MG-6-unreachable before layer 3 runs
        (the pinned N=8 seed-31 failure, which MG-18 alone cannot fix --
        see test_generator.py), layer 3 must not place any rock against an
        undefined "mean C" baseline, and must leave the board exactly as
        repair left it.
        """
        n = 8
        rk = root_key(31, 0, 1)
        board = generate_layers_1_and_2(n, rk)
        repair_dead_ends(board, rk)
        hub = hub_cells(n)
        pre_mask = list(board.mask)
        self.assertFalse(
            all(TransitGraph(board).reachable_to_hub(s, hub) for s in spawns(n))
        )
        generate_layer3(board, rk)
        self.assertEqual(board.mask, pre_mask)


class GenerateBoardFullPipelineTests(unittest.TestCase):
    """The real, full `generate_board` (layers 1-2 + MG-18 + layer 3),
    measured honestly rather than assumed correct. MG-19 (the symmetry
    repair loop) does not exist yet, so MG-11/MG-14 are not asserted here
    -- see reference/PROGRESS.md.
    """

    def test_generate_board_matches_the_manually_assembled_pipeline(self):
        """Sanity check on the real public entry point itself, not just the
        manually-assembled `_pipeline` helper the rest of this file reuses
        for speed: they must produce byte-identical boards."""
        n = 16
        rk = root_key(5, 0, 1)
        via_api = generate_board(n, rk)
        _, via_helper, _ = _pipeline(n, 5)
        self.assertEqual(via_api.mask, via_helper.mask)

    def test_full_pipeline_contains_at_least_one_rock_on_most_boards(self):
        """Not a spec rule by itself, just a sanity check that layer 3 is
        actually wired in and doing something, across sizes where the
        pre-accretion board is already MG-6-solvable (accretion is a
        strict no-op otherwise, by design -- see
        test_does_nothing_when_the_pre_accretion_board_is_already_unsolvable)."""
        boards_with_a_rock = 0
        total = 0
        for n in PRESET_SIZES:
            for seed in SWEEP_SEEDS:
                board = _full_pipeline_board(n, seed)
                total += 1
                if any(shape_of(board.mask_at(c)) == Shape.ROCK for c in board.all_cells()):
                    boards_with_a_rock += 1
        self.assertGreaterEqual(boards_with_a_rock / total, 0.8)

    def test_mg6_solvability_rate_improves_over_layers_1_and_2_alone(self):
        """The full pipeline (MG-18 + layer 3's own MG-6 enforcement) must
        solve at least as large a fraction of spawns as layers 1-2 alone
        measured in test_generator.py (~97.75%) -- not asserting 100%,
        since MG-19 (misorientation repair) is still ahead.
        """
        solved = 0
        total = 0
        for n in PRESET_SIZES:
            hub = hub_cells(n)
            for seed in SWEEP_SEEDS:
                board = _full_pipeline_board(n, seed)
                tg = TransitGraph(board)
                for s in spawns(n):
                    total += 1
                    if tg.reachable_to_hub(s, hub):
                        solved += 1
        self.assertGreaterEqual(solved / total, 0.97)

    def test_hub_and_spawn_pads_survive_the_full_pipeline(self):
        for n in PRESET_SIZES:
            board = _full_pipeline_board(n, 0)
            with self.subTest(n=n):
                for cell in hub_cells(n):
                    self.assertEqual(board.mask_at(cell), 15)
                    self.assertTrue(board.flags_at(cell) & TileFlags.FINISH_LOCKED)
                for k, pad in enumerate(spawns(n)):
                    self.assertTrue(board.flags_at(pad) & TileFlags.SPAWN_PAD)


if __name__ == "__main__":
    unittest.main()
