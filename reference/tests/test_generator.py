"""Tests for snail_labyrinth.generator -- spec section 3.3, MG-16, MG-17
layers 1-2.
"""

import unittest

from snail_labyrinth.generator import (
    DEFAULT_TYPE_WEIGHTS,
    WEDGE_RADIUS,
    c4_orbit,
    canonical_corridor_wedge,
    canonical_representative,
    cell_mask,
    generate_board,
    generate_layer1,
    generate_layer2,
    layer1_cells,
    type_mask,
    weighted_pick,
)
from snail_labyrinth.geometry import (
    apron_cells,
    hub_cells,
    place_fixed_geometry,
    rho,
    spawn_offset,
    spawns,
    start_pad_mask,
)
from snail_labyrinth.rng import cell_hash, root_key
from snail_labyrinth.tiles import Board, GridPos, Shape, TileFlags, cw, shape_of
from snail_labyrinth.transit import TransitGraph

PRESET_SIZES = (8, 12, 16, 20, 24)


class WeightedPickTests(unittest.TestCase):
    def test_boundaries_exact(self):
        """MG-17: weighted_pick partitions [0, total) into contiguous
        buckets in weight order -- exact boundary behaviour, not sampled.
        """
        items = (("A", 1), ("B", 2), ("C", 3))  # total 6
        expected = {0: "A", 1: "B", 2: "B", 3: "C", 4: "C", 5: "C"}
        for h, exp in expected.items():
            with self.subTest(h=h):
                self.assertEqual(weighted_pick(h, items), exp)
        # modulo wraps: hash 6 behaves exactly like hash 0.
        self.assertEqual(weighted_pick(6, items), "A")

    def test_zero_total_weight_raises(self):
        with self.assertRaises(ValueError):
            weighted_pick(0, (("A", 0), ("B", 0)))

    def test_statistical_convergence_to_default_weights(self):
        """MG-17: over a large sample of cell hashes, the realised shape
        proportions converge to the authored 26/32/24/8/10 weights.
        Statistical, generous tolerance -- analogous in spirit to the
        draw-system statistical tests in HT-1.
        """
        rk = root_key(777, 0, 1)
        counts = {shape: 0 for shape, _ in DEFAULT_TYPE_WEIGHTS}
        n_samples = 0
        for x in range(0, 300):
            for y in range(0, 300):
                h = cell_hash(rk, "stat-test-types", x, y)
                shape = weighted_pick(h, DEFAULT_TYPE_WEIGHTS)
                counts[shape] += 1
                n_samples += 1
        total_weight = sum(w for _, w in DEFAULT_TYPE_WEIGHTS)
        for shape, weight in DEFAULT_TYPE_WEIGHTS:
            expected_frac = weight / total_weight
            observed_frac = counts[shape] / n_samples
            with self.subTest(shape=shape):
                self.assertAlmostEqual(observed_frac, expected_frac, delta=0.01)


class TypeMaskTests(unittest.TestCase):
    def test_ori_zero_is_canonical(self):
        self.assertEqual(type_mask(Shape.DEAD_END, 0), 1)
        self.assertEqual(type_mask(Shape.STRAIGHT, 0), 5)
        self.assertEqual(type_mask(Shape.ELBOW, 0), 3)
        self.assertEqual(type_mask(Shape.TEE, 0), 7)
        self.assertEqual(type_mask(Shape.CROSS, 0), 15)

    def test_shape_of_type_mask_round_trips_for_every_ori(self):
        """Exhaustive 5 shapes x 4 ori: type_mask always produces a mask of
        the requested shape (TM-3's bijection, exercised from this side)."""
        for shape, _ in DEFAULT_TYPE_WEIGHTS:
            for ori in range(4):
                with self.subTest(shape=shape, ori=ori):
                    self.assertEqual(shape_of(type_mask(shape, ori)), shape)

    def test_straight_has_rotation_period_2(self):
        """TM-5: a Straight only has 2 distinct rotations, so ori 0/2 and
        1/3 legitimately collapse onto the same mask."""
        self.assertEqual(type_mask(Shape.STRAIGHT, 0), type_mask(Shape.STRAIGHT, 2))
        self.assertEqual(type_mask(Shape.STRAIGHT, 1), type_mask(Shape.STRAIGHT, 3))
        self.assertNotEqual(type_mask(Shape.STRAIGHT, 0), type_mask(Shape.STRAIGHT, 1))

    def test_cross_has_rotation_period_1(self):
        """TM-5: rotation is a no-op on Cross."""
        for ori in range(4):
            self.assertEqual(type_mask(Shape.CROSS, ori), 15)


class C4OrbitTests(unittest.TestCase):
    def test_orbit_has_four_distinct_members_on_every_preset_size(self):
        """GE-6: rho has no fixed point on an even board, so every orbit
        has exactly 4 distinct cells."""
        for n in PRESET_SIZES:
            sample_cells = [GridPos(1, 1), GridPos(n - 2, 3), spawns(n)[0]]
            for cell in sample_cells:
                with self.subTest(n=n, cell=cell):
                    orbit = c4_orbit(cell, n)
                    self.assertEqual(len(orbit), 4)
                    self.assertEqual(len(set(orbit)), 4)

    def test_fourth_rotation_is_identity(self):
        for n in PRESET_SIZES:
            cell = GridPos(1, 2)
            with self.subTest(n=n):
                c0, c1, c2, c3 = c4_orbit(cell, n)
                self.assertEqual(rho(c3, n), c0)

    def test_canonical_representative_agrees_across_the_whole_orbit(self):
        for n in PRESET_SIZES:
            cell = spawns(n)[0]
            orbit = c4_orbit(cell, n)
            reps = {canonical_representative(c, n) for c in orbit}
            with self.subTest(n=n):
                self.assertEqual(len(reps), 1)
                self.assertIn(next(iter(reps)), orbit)


class CorridorWedgeTests(unittest.TestCase):
    def test_wedge_is_nonempty_and_in_bounds(self):
        for n in PRESET_SIZES:
            wedge = canonical_corridor_wedge(n)
            with self.subTest(n=n):
                self.assertTrue(wedge)
                for p in wedge:
                    self.assertTrue(0 <= p.x < n)
                    self.assertTrue(0 <= p.y < n)

    def test_wedge_stays_within_chebyshev_radius_of_spawn_s0(self):
        for n in PRESET_SIZES:
            s0 = spawns(n)[0]
            for p in canonical_corridor_wedge(n):
                with self.subTest(n=n, p=p):
                    self.assertLessEqual(max(abs(p.x - s0.x), abs(p.y - s0.y)), WEDGE_RADIUS)

    def test_wedge_excludes_hub_apron_and_spawn_cells(self):
        for n in PRESET_SIZES:
            reserved = set(hub_cells(n)) | set(apron_cells(n)) | set(spawns(n))
            wedge = set(canonical_corridor_wedge(n))
            with self.subTest(n=n):
                self.assertEqual(wedge & reserved, set())


class Layer1Tests(unittest.TestCase):
    def test_layer1_cells_disjoint_from_hub_and_spawns(self):
        for n in PRESET_SIZES:
            reserved = set(hub_cells(n)) | set(spawns(n))
            with self.subTest(n=n):
                self.assertEqual(layer1_cells(n) & reserved, set())

    def test_layer1_cells_cover_the_full_apron_ring(self):
        for n in PRESET_SIZES:
            with self.subTest(n=n):
                self.assertTrue(set(apron_cells(n)).issubset(layer1_cells(n)))

    def test_layer1_masks_are_c4_symmetric(self):
        """MG-17 layer 1: the corridor/Apron region is a literal 90-degree
        image of itself -- rotating by rho rotates the mask by cw, exactly
        once per rho application, all the way around the orbit."""
        for n in PRESET_SIZES:
            for seed in (1, 2, 3):
                rk = root_key(seed, 0, 1)
                board = Board(n)
                place_fixed_geometry(board)
                generate_layer1(board, rk)
                seeds = set(apron_cells(n)) | set(canonical_corridor_wedge(n))
                reps = {canonical_representative(p, n) for p in seeds}
                for rep in reps:
                    c0, c1, c2, c3 = c4_orbit(rep, n)
                    m0 = board.mask_at(c0)
                    with self.subTest(n=n, seed=seed, rep=rep):
                        self.assertEqual(board.mask_at(c1), cw(m0))
                        self.assertEqual(board.mask_at(c2), cw(cw(m0)))
                        self.assertEqual(board.mask_at(c3), cw(cw(cw(m0))))

    def test_layer1_never_places_a_rock(self):
        """MG-17: layer 2's (and, by the same formula, layer 1's) type
        weights are defined "over non-rock cells" -- no mask-0 cell should
        ever come out of this layer."""
        for n in PRESET_SIZES:
            rk = root_key(5, 0, 1)
            board = Board(n)
            place_fixed_geometry(board)
            generate_layer1(board, rk)
            with self.subTest(n=n):
                for cell in layer1_cells(n):
                    self.assertNotEqual(board.mask_at(cell), 0)


class GenerateBoardTests(unittest.TestCase):
    def test_no_rock_anywhere_before_layer_3(self):
        """This increment's deliverable: a map with no rocks and no
        collectibles (PROGRESS.md) -- every cell must be a real, open
        shape, since rocks are exclusively layer 3's job."""
        for n in PRESET_SIZES:
            rk = root_key(9, 0, 1)
            board = generate_board(n, rk)
            with self.subTest(n=n):
                for cell in board.all_cells():
                    self.assertNotEqual(board.mask_at(cell), 0, msg=f"rock at {cell}")

    def test_hub_cells_untouched_by_layers_1_and_2(self):
        """MG-5: Hub forced to mask 15 + FINISH_LOCKED before any other
        placement, and nothing after should overwrite it."""
        for n in PRESET_SIZES:
            rk = root_key(9, 0, 1)
            board = generate_board(n, rk)
            with self.subTest(n=n):
                for cell in hub_cells(n):
                    self.assertEqual(board.mask_at(cell), 15)
                    self.assertTrue(board.flags_at(cell) & TileFlags.FINISH_LOCKED)

    def test_spawn_pads_untouched_by_layers_1_and_2(self):
        for n in PRESET_SIZES:
            rk = root_key(9, 0, 1)
            board = generate_board(n, rk)
            with self.subTest(n=n):
                for k, pad in enumerate(spawns(n)):
                    self.assertEqual(board.mask_at(pad), start_pad_mask(k))
                    self.assertTrue(board.flags_at(pad) & TileFlags.SPAWN_PAD)

    def test_deterministic_given_the_same_root_key(self):
        """MG-24: regenerate twice from the same root key, compare state."""
        n = 16
        rk = root_key(42, 0, 1)
        b1 = generate_board(n, rk)
        b2 = generate_board(n, rk)
        self.assertEqual(b1.mask, b2.mask)
        self.assertEqual(list(b1.flags), list(b2.flags))

    def test_different_root_keys_usually_differ(self):
        """Sanity, not a theorem: two different root keys should not
        happen to produce byte-identical interiors."""
        n = 16
        b1 = generate_board(n, root_key(1, 0, 1))
        b2 = generate_board(n, root_key(2, 0, 1))
        self.assertNotEqual(b1.mask, b2.mask)

    def test_statistical_type_distribution_over_the_free_interior(self):
        """Aggregate the free interior's realised shapes across several
        seeds at N=16 and check convergence to the authored weights --
        exercising the full generate_board pipeline, not weighted_pick in
        isolation."""
        n = 16
        counts = {shape: 0 for shape, _ in DEFAULT_TYPE_WEIGHTS}
        total = 0
        reserved = set(hub_cells(n)) | set(spawns(n)) | layer1_cells(n)
        for seed in range(40):
            board = generate_board(n, root_key(seed, 0, 1))
            for cell in board.all_cells():
                if cell in reserved:
                    continue
                counts[shape_of(board.mask_at(cell))] += 1
                total += 1
        total_weight = sum(w for _, w in DEFAULT_TYPE_WEIGHTS)
        for shape, weight in DEFAULT_TYPE_WEIGHTS:
            with self.subTest(shape=shape):
                self.assertAlmostEqual(counts[shape] / total, weight / total_weight, delta=0.02)


class MG6PreRepairCharacterizationTests(unittest.TestCase):
    """MG-6 ("SolveCost(s) < infinity for all 4 spawns") is the map
    generator's real solvability guarantee -- but it is a guarantee about
    the *finished* generator (layers 1-3 plus MG-18's dead-end repair),
    not about layers 1-2 alone. These tests characterize layers 1-2's
    solvability rate honestly instead of asserting a theorem this
    increment cannot yet deliver; see reference/OPEN_QUESTIONS.md OQ-6 and
    reference/PROGRESS.md for why MG-18 (next increment) exists.
    """

    def test_a_concrete_pre_repair_failure_exists(self):
        """A reproducible instance where a spawn is unreachable purely
        from layer 2's free-interior dead-end density, with zero rocks
        anywhere on the board. This is exactly the failure mode MG-18
        ("dead-end repair is mandatory ... a 10% dead-end field alone
        seals spawns") describes, demonstrated with no rock accretion
        involved at all.
        """
        n = 8
        board = generate_board(n, root_key(31, 0, 1))
        tg = TransitGraph(board)
        hub = hub_cells(n)
        s0 = spawns(n)[0]
        self.assertFalse(tg.reachable_to_hub(s0, hub))

    def test_solvability_rate_is_high_but_not_asserted_perfect(self):
        """Fixed, deterministic seed sweep across all 5 preset sizes.
        Observed empirically at ~97.75% (18 unsolved spawns of 800) when
        this test was written; asserting a generous 90% lower bound here
        catches a gross regression without pretending layers 1-2 alone
        reach the spec's actual guarantee (which needs MG-18).
        """
        solved = 0
        total = 0
        for n in PRESET_SIZES:
            hub = hub_cells(n)
            for seed in range(40):
                board = generate_board(n, root_key(seed, 0, 1))
                tg = TransitGraph(board)
                for s in spawns(n):
                    total += 1
                    if tg.reachable_to_hub(s, hub):
                        solved += 1
        self.assertGreaterEqual(solved / total, 0.90)


if __name__ == "__main__":
    unittest.main()
