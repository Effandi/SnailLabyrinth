"""Determinism and reproducibility primitives.

Implements SNAIL_LABYRINTH_TECHNICAL_SPEC.md section 3.6: MG-24.

The map (and later, per-player card draw) must be a pure function of small
integer seeds -- no wall clock, no engine global RNG, no dictionary/set
iteration order, no float accumulation anywhere in this module. "Labelled
stream splitting, not one sequential PRNG" (MG-24): a single stream would
mean adding one `rng.next()` call anywhere silently reshuffles every
downstream decision.
"""

from __future__ import annotations

MASK64 = 0xFFFFFFFFFFFFFFFF
MASK32 = 0xFFFFFFFF

# SplitMix64's own finalizer constants (Vigna). Used here as a pure mixing
# function of its argument, not as a self-advancing generator -- every use
# in MG-24's formulas is `splitmix64(some 64-bit value)`, always the same
# function of that value.
_GOLDEN_GAMMA = 0x9E3779B97F4A7C15
_MIX1 = 0xBF58476D1CE4E5B9
_MIX2 = 0x94D049BB133111EB

FNV_OFFSET_BASIS_64 = 0xCBF29CE484222325
FNV_PRIME_64 = 0x100000001B3

# MG-24 formula constants, named exactly as the spec's formulas use them.
ROOT_KEY_MIX = 0xA24BAED4963EE407
ATTEMPT_KEY_MIX = 0xD1B54A32D192ED03
CELL_HASH_X_MIX = 0x9E3779B1


def splitmix64(x: int) -> int:
    """MG-24: splitmix64(x), a pure 64-bit avalanche mix of its argument."""
    z = (x + _GOLDEN_GAMMA) & MASK64
    z = ((z ^ (z >> 30)) * _MIX1) & MASK64
    z = ((z ^ (z >> 27)) * _MIX2) & MASK64
    return z ^ (z >> 31)


def fnv1a64(label: str) -> int:
    """MG-24: FNV-1a, 64-bit, over the UTF-8 bytes of `label`."""
    h = FNV_OFFSET_BASIS_64
    for byte in label.encode("utf-8"):
        h ^= byte
        h = (h * FNV_PRIME_64) & MASK64
    return h


def root_key(match_seed: int, settings_hash: int, generator_version: int) -> int:
    """MG-24: `RootKey = splitmix64(MatchSeed ^ splitmix64(SettingsHash ^
    GeneratorVersion * 0xA24BAED4963EE407))`."""
    inner = splitmix64((settings_hash ^ ((generator_version * ROOT_KEY_MIX) & MASK64)) & MASK64)
    return splitmix64((match_seed & MASK64) ^ inner)


def attempt_key(root_key_value: int, attempt_index: int) -> int:
    """MG-24: `AttemptKey(i) = splitmix64(RootKey ^ 0xD1B54A32D192ED03*(i+1))`."""
    mixed = (ATTEMPT_KEY_MIX * (attempt_index + 1)) & MASK64
    return splitmix64((root_key_value & MASK64) ^ mixed)


def stream_seed(root_key_value: int, label: str) -> int:
    """MG-24: the splitmix64-derived seed inside `Stream(label) =
    pcg32(splitmix64(RootKey ^ fnv1a64(label)))` -- call `Pcg32(seed)` on
    the result to get the actual generator object."""
    return splitmix64((root_key_value & MASK64) ^ fnv1a64(label))


def make_stream(root_key_value: int, label: str) -> "Pcg32":
    """MG-24: `Stream(label)`. Streams are per-purpose (`types, orient,
    walls, gems, upgrades, repair`, plus one per player for cards,
    `Stream("cards" ^ playerIndex)`) -- reserved for genuinely sequential
    processes (darts, accretion order, repair), never for anything indexed
    by cell (use `cell_hash` for that instead)."""
    return Pcg32(stream_seed(root_key_value, label))


def cell_hash(root_key_value: int, label: str, x: int, y: int) -> int:
    """MG-24: `CellHash(label,x,y) = splitmix64(RootKey ^ fnv1a64(label) ^
    (x*0x9E3779B1) ^ (y << 32)) >> 32`.

    Stateless hashing for anything indexed by cell (layer 2's `types` and
    `orient` in MG-17): the result depends only on `(label, x, y)`, never on
    call order, so the interior generation is independent of iteration
    order by construction.
    """
    mixed = (
        (root_key_value & MASK64)
        ^ fnv1a64(label)
        ^ ((x * CELL_HASH_X_MIX) & MASK64)
        ^ ((y << 32) & MASK64)
    )
    return splitmix64(mixed & MASK64) >> 32


class Pcg32:
    """A PCG XSH-RR 64/32 generator (O'Neill), a single fixed stream, seeded
    from one 64-bit value -- matching `Stream(label)`'s one-argument
    `pcg32(seed)` call. Used only for genuinely sequential draws; anything
    indexed by cell must use `cell_hash` instead (MG-24).
    """

    _MULT = 6364136223846793005
    _INC = 1442695040888963407  # PCG's conventional default stream increment.

    __slots__ = ("_state",)

    def __init__(self, seed: int) -> None:
        state = 0
        state = (state * self._MULT + self._INC) & MASK64
        state = (state + (seed & MASK64)) & MASK64
        state = (state * self._MULT + self._INC) & MASK64
        self._state = state

    def next_u32(self) -> int:
        old = self._state
        self._state = (old * self._MULT + self._INC) & MASK64
        xorshifted = (((old >> 18) ^ old) >> 27) & MASK32
        rot = (old >> 59) & 0x1F
        return ((xorshifted >> rot) | (xorshifted << ((-rot) & 31))) & MASK32

    def next_below(self, n: int) -> int:
        """Uniform integer in `[0, n)`, via unbiased rejection sampling (no
        modulo bias) -- the standard PCG `bounded_rand` construction."""
        if n <= 0:
            raise ValueError("n must be positive")
        threshold = ((MASK32 + 1) - n) % n
        while True:
            r = self.next_u32()
            if r >= threshold:
                return r % n
