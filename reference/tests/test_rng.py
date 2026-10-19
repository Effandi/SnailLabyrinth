"""Tests for snail_labyrinth.rng: MG-24.

Every test cites the spec rule(s) it verifies.
"""

import unittest

from snail_labyrinth.rng import (
    Pcg32,
    attempt_key,
    cell_hash,
    fnv1a64,
    make_stream,
    root_key,
    splitmix64,
    FNV_OFFSET_BASIS_64,
    MASK64,
)


class SplitMix64Tests(unittest.TestCase):
    def test_MG24_splitmix64_is_a_pure_function(self):
        """MG-24: splitmix64(x) must be deterministic and depend on nothing
        but its argument -- calling it repeatedly must not advance any
        hidden state (it is used as a mixing function, not a generator)."""
        x = 123456789
        first = splitmix64(x)
        second = splitmix64(x)
        third = splitmix64(x)
        self.assertEqual(first, second)
        self.assertEqual(second, third)

    def test_MG24_splitmix64_output_fits_in_64_bits(self):
        for x in (0, 1, MASK64, MASK64 // 2, 2**63):
            out = splitmix64(x)
            self.assertGreaterEqual(out, 0)
            self.assertLessEqual(out, MASK64)

    def test_MG24_splitmix64_avalanches_on_adjacent_inputs(self):
        """A one-bit change in the input should not produce a near-identical
        output -- the whole point of mixing before use as a seed."""
        seen = {splitmix64(x) for x in range(64)}
        self.assertEqual(len(seen), 64, "splitmix64 collided on 64 tiny distinct inputs")


class Fnv1a64Tests(unittest.TestCase):
    def test_MG24_fnv1a64_empty_string_is_the_offset_basis(self):
        """By construction (no bytes to fold in), FNV-1a of the empty string
        is exactly its own offset basis -- this is an algebraic certainty of
        the algorithm, not a guess at a published test vector."""
        self.assertEqual(fnv1a64(""), FNV_OFFSET_BASIS_64)

    def test_MG24_fnv1a64_is_deterministic(self):
        self.assertEqual(fnv1a64("types"), fnv1a64("types"))
        self.assertEqual(fnv1a64("cards0"), fnv1a64("cards0"))

    def test_MG24_fnv1a64_distinguishes_stream_labels(self):
        """MG-24 names the stream labels explicitly: types, orient, walls,
        gems, upgrades, repair, plus per-player cards labels. They must not
        collide with each other."""
        labels = ["types", "orient", "walls", "gems", "upgrades", "repair"]
        labels += [f"cards{i}" for i in range(4)]
        hashes = {fnv1a64(label) for label in labels}
        self.assertEqual(len(hashes), len(labels), "two distinct stream labels collided")

    def test_MG24_fnv1a64_output_fits_in_64_bits(self):
        for label in ("", "a", "types", "x" * 100):
            h = fnv1a64(label)
            self.assertGreaterEqual(h, 0)
            self.assertLessEqual(h, MASK64)


class KeyDerivationTests(unittest.TestCase):
    """MG-24: RootKey, AttemptKey(i), Stream(label), CellHash -- all pure
    functions of their arguments, so a map is reproducible from
    (MatchSeed, SettingsHash, GeneratorVersion) alone."""

    def test_MG24_root_key_is_deterministic(self):
        a = root_key(42, 7, 1)
        b = root_key(42, 7, 1)
        self.assertEqual(a, b)

    def test_MG24_root_key_changes_with_any_input(self):
        base = root_key(42, 7, 1)
        self.assertNotEqual(base, root_key(43, 7, 1), "changing MatchSeed must change RootKey")
        self.assertNotEqual(base, root_key(42, 8, 1), "changing SettingsHash must change RootKey")
        self.assertNotEqual(base, root_key(42, 7, 2), "changing GeneratorVersion must change RootKey")

    def test_MG24_settings_hash_excludes_nothing_structurally(self):
        """MG-24: 'Every freeze* key is explicitly excluded [from
        SettingsHash] ... a designer tuning its duration must be able to A/B
        it on one map.' This module does not compute SettingsHash itself (no
        config schema exists yet) -- it only guarantees that two equal
        SettingsHash values reproduce the same RootKey, which is the
        property the exclusion rule depends on."""
        self.assertEqual(root_key(1, 999, 3), root_key(1, 999, 3))

    def test_MG24_attempt_key_differs_per_attempt(self):
        rk = root_key(1, 2, 3)
        keys = {attempt_key(rk, i) for i in range(16)}
        self.assertEqual(len(keys), 16, "AttemptKey(i) collided across attempts")

    def test_MG24_attempt_key_is_deterministic(self):
        rk = root_key(1, 2, 3)
        self.assertEqual(attempt_key(rk, 5), attempt_key(rk, 5))

    def test_MG24_cell_hash_is_a_pure_function_of_its_arguments(self):
        """MG-24: 'the interior is independent of iteration order' -- calling
        cell_hash in any order, interleaved with other calls, must not
        change any individual result."""
        rk = root_key(1, 2, 3)
        direct = cell_hash(rk, "types", 5, 9)
        # Interleave a bunch of unrelated calls in between; must not matter.
        for x in range(10):
            for y in range(10):
                cell_hash(rk, "orient", x, y)
        after = cell_hash(rk, "types", 5, 9)
        self.assertEqual(direct, after)

    def test_MG24_cell_hash_distinguishes_cells_and_labels(self):
        rk = root_key(1, 2, 3)
        values = set()
        for label in ("types", "orient"):
            for x in range(8):
                for y in range(8):
                    values.add(cell_hash(rk, label, x, y))
        # Not a collision-freedom proof, just a sanity floor: 128 cell/label
        # combinations should not collapse onto a handful of values.
        self.assertGreater(len(values), 100)

    def test_MG24_make_stream_returns_an_independent_generator_per_label(self):
        rk = root_key(1, 2, 3)
        cards = make_stream(rk, "cards0")
        types = make_stream(rk, "types")
        self.assertNotEqual(
            [cards.next_u32() for _ in range(5)],
            [types.next_u32() for _ in range(5)],
        )


class Pcg32Tests(unittest.TestCase):
    def test_MG24_same_seed_same_sequence(self):
        a = Pcg32(12345)
        b = Pcg32(12345)
        seq_a = [a.next_u32() for _ in range(20)]
        seq_b = [b.next_u32() for _ in range(20)]
        self.assertEqual(seq_a, seq_b)

    def test_MG24_different_seeds_different_sequences(self):
        a = Pcg32(1)
        b = Pcg32(2)
        self.assertNotEqual(
            [a.next_u32() for _ in range(10)],
            [b.next_u32() for _ in range(10)],
        )

    def test_MG24_next_u32_is_bounded(self):
        gen = Pcg32(7)
        for _ in range(1000):
            v = gen.next_u32()
            self.assertGreaterEqual(v, 0)
            self.assertLessEqual(v, 0xFFFFFFFF)

    def test_MG24_next_below_is_bounded_for_many_n(self):
        gen = Pcg32(99)
        for n in (1, 2, 3, 5, 7, 16, 100, 1000):
            for _ in range(200):
                v = gen.next_below(n)
                self.assertGreaterEqual(v, 0)
                self.assertLess(v, n)

    def test_MG24_next_below_rejects_non_positive_n(self):
        gen = Pcg32(1)
        with self.assertRaises(ValueError):
            gen.next_below(0)

    def test_MG24_next_below_one_is_always_zero(self):
        gen = Pcg32(55)
        for _ in range(50):
            self.assertEqual(gen.next_below(1), 0)

    def test_MG24_sequence_is_not_degenerate(self):
        """Forbidden-practice guard: a broken generator that always returns
        the same value would pass the bounds checks above but is useless."""
        gen = Pcg32(2024)
        values = {gen.next_u32() for _ in range(50)}
        self.assertGreater(len(values), 40)


if __name__ == "__main__":
    unittest.main()
