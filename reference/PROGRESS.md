# Progress

Read this file first if you are resuming this build. It records exactly
what is implemented, what is tested, and what the next increment should be.

## Status: increment 3 of N — the weighted cost model and determinism scaffolding

> **Note on process — read this before opening another PR.** As of this
> increment there were **three open, unmerged PRs on GitHub, all duplicating
> increment 1** (`reference: tile model, connectivity, transit graph`),
> built by three different scheduled runs that each started from `main`
> without checking for prior unmerged work: #1 (`reference/tile-model-transit-graph`),
> #2 (`reference: board geometry and spawns`, stacked on top of #1's
> branch — the most advanced of the three, since it also includes `GE-*`),
> and #3 (`reference/tile-model-and-transit-graph`, an independent redo that
> never saw #1 or #2). **#1's and #3's transit-graph implementations both
> have the same real bug**: they feed `TM-12`'s bare `source()` output
> straight into the same `carries`-gated `edge` rule used for interior
> nodes, which makes a snail resting on a Dead End permanently unable to
> reach the Hub in `G_T` — contradicting `AS-3`'s liveness theorem (see
> `OPEN_QUESTIONS.md` OQ-1). Only the lineage behind #2
> (`reference/tile-model-transit-graph` -> `reference/board-geometry-spawns`)
> catches and fixes this. **This run built on top of that lineage** (the
> correct one), consolidated it into one branch based directly on `main`
> (`reference/map-generation`), and is opening **one PR against `main`**
> containing the cumulative, correct state of increments 1-3 together,
> rather than adding a fourth competing PR. #1 and #3 should be closed as
> superseded (duplicated, and the less-correct implementation) once this
> PR is reviewed; #2 should be closed too, since its content is now fully
> included here against the right base.
>
> **If you are the next scheduled run: before writing any code, run `git
> fetch origin` and check for open `reference/*` branches/PRs — do not
> assume `main` reflects all prior work.** This file only reflects what has
> been *written* to the branch it lives on, not what every other open PR
> contains. If you find more than one plausible branch to build on, run
> each one's test suite and prefer the one that passes the most tests /
> has no known open correctness bug recorded in its own `OPEN_QUESTIONS.md`
> — do not just pick the most recently pushed one.

### Implemented

**`snail_labyrinth/tiles.py`** — spec section 1.1-1.3:

- `TM-1` — `GridPos`, index convention, direction deltas.
- `TM-2` — direction bit layout (N=1,E=2,S=4,W=8), `cw`, `ccw`, `opp`,
  `orbit`, `popcount`.
- `TM-3` — `Shape` enum and `shape_of(mask)`; shape is always derived from
  the mask, never stored.
- `TM-5` — consequences (rotation no-op on Rock/Cross; CW==CCW on Straight)
  are covered as tests of `cw`/`ccw`, not separate functions (there is
  nothing to implement beyond the algebra already giving the right answer).
- `TM-6` — `Board`: `mask`, `flags` (`TileFlags`), `version` arrays; `set_mask`
  bumps `version`.
- `TM-8` — `Board.connected`, `Board.usable_exits` (mutual openness).
- `TM-9` — `Board.mask_at` treats off-grid as Rock (mask 0); border ring
  tested exhaustively.
- `TM-10` — covered as a test of the underlying fact (mask can change while
  an outward opening stays uncrossable); the actual *legality* half of this
  rule belongs with `CD-8`'s no-op rule, not yet implemented — see
  `OPEN_QUESTIONS.md` OQ-2.

**`snail_labyrinth/transit.py`** — spec section 1.4:

- `TM-11` — `carries()`; the table (Straight=collinear-only, Elbow=turn-only,
  Tee/Cross=always, DeadEnd/Rock=never) is verified exhaustively for all 6
  shapes x 12 ordered direction pairs.
- `TM-12` — `TransitGraph`: nodes are `(cell, entryDir)` pairs;
  `reachable_to_hub` is the one-BFS-answers-solvability primitive that
  `MG-6`, `AS-2` and `CD-13` condition 6 will all reuse. See
  `OPEN_QUESTIONS.md` OQ-1 for the one place this module diverges from a
  fully literal reading of the spec's `source()` formula, and why.

**`snail_labyrinth/geometry.py`** — spec section 2:

- `GE-1` — `hub_cells(n)` (4 cells for even N, 1 for odd N) and
  `apron_cells(n)` (orthogonal Hub neighbours outside Hub; 8 cells even, 4
  odd), cross-checked against the section 3.5 defaults table for all five
  preset sizes.
- `GE-2` — `place_fixed_geometry` forces every Hub cell to mask 15 +
  `FINISH_LOCKED`. (The "untargetable by all six cards" and "entering sets
  `Finished`" halves of `GE-2` are `CD-*` / `MV-*` concerns, not yet wired
  up — there is no card system or movement state machine yet for them to
  attach to.)
- `GE-3` — satisfied by construction: Apron cells get no special flags, so
  they stay ordinary, rotatable, rockable cells.
- `GE-5` — `spawn_offset(n)` (the clamped `m`) and `spawns(n)` (`S0..S3`),
  matching the section 3.5 table for all five preset sizes.
- `GE-6` — `rho(pos, n)`, the 90-degree rotation; tested as `rho: S[k] ->
  S[k+1 mod 4]` for every preset size, and that the orbit has exactly 4
  distinct members (simple transitivity).
- `GE-7` — antipodal pairing (`S0+S2 == S1+S3 == (N-1, N-1)`) tested
  directly rather than left as a geometric claim.
- `GE-8` — `start_pad_mask(k)` (immutable T-Junction missing only the
  outward direction — cross-checked against `TM-3`'s own TEE table: masks
  7/14/13/11 are documented there as missing W/N/E/S, which is exactly
  `start_pad_mask(3)/(0)/(1)/(2)`) and `start_pad_inward_neighbour`, both
  wired into `place_fixed_geometry` (`SPAWN_PAD` and `ROCK_PROTECTED`
  respectively). `GE-4` is informational only (no code: it just explains
  *why* `CD-13` condition 7 has room to bind on Apron quality rather than
  raw count) and needed nothing here.
- Integration test: a hand-carved N=8 corridor from each of the 4 spawns to
  the Hub, run through `TransitGraph.reachable_to_hub` — plus the negative
  control (fixed geometry alone, no corridors, reaches nothing), confirming
  the positive result isn't an artefact of the geometry functions.

**`snail_labyrinth/transit.py`, extended this increment** — spec section 3.1, `MG-2`/`MG-3`:

- `ACT_MILLI`/`STEP_MILLI` — the spec's authored cost-table constants, as
  integer milli-units throughout (`MG-2`: "all generator arithmetic is
  integer" — no floats anywhere in this module).
- `tau_milli(mask, a, b)` — `TAU[c][a][b]`, re-derived directly over
  quarter-turn deltas from the cell's *current* mask rather than the
  spec's `ori()`/`MASK[shape][o]` indirection (provably the same formula;
  see `OPEN_QUESTIONS.md` OQ-3). Returns `None` (infinite) exactly when
  `carries` is false for that pair, checked exhaustively against `carries`
  itself for all 16 masks x 12 ordered pairs.
- `TransitGraph.weighted_edges_from` / `TransitGraph.solve_cost` —
  `edgeCost = TAU + STEP_MILLI`, and the Dijkstra that answers `SolveCost(s)`
  as the `(R, L)` pair plus `C = 2R+L` (`SolveCost` NamedTuple). The very
  first hop reuses `first_departures` and is zero-cost in `R`, consistent
  with `OQ-1`'s treatment of departure vs. interior-node `carries`. Runs
  one Dijkstra per spawn rather than `MG-3`'s "one reverse Dijkstra from the
  Hub answers all four spawns" optimisation — that trick is deferred (see
  "Not yet implemented" below), since it is a performance refinement for
  the generation loop, not a correctness requirement.
- See `OPEN_QUESTIONS.md` OQ-4 for a real tension in the spec's own text
  (the Dijkstra edge weight and the reported scalar `C` use different `R`:`L`
  weightings, 1:1 vs 2:1) and the reading implemented.
- Tests pin down hand-computed `TAU` values for Straight/Elbow/Tee worked
  examples (matching `TM-5`'s "CW==CCW on a Straight" and cross-checked
  against `ACT`'s own 0/1000/1600/1000 table), and `solve_cost` on hand-built
  boards: a zero-rotation Cross corridor, a one-rotation Straight corridor
  (exact `R`/`L`/`C` pinned down, not just "some value"), an unreachable
  board (`MG-6` fails), and a diamond with two equal-length routes where
  only the cost model distinguishes which one Dijkstra must prefer.

**`snail_labyrinth/rng.py`, new this increment** — spec section 3.6, `MG-24`:

- `splitmix64`, `fnv1a64` — the two primitive mixing/hashing functions
  every other formula in this module is built from.
- `root_key`, `attempt_key`, `stream_seed`/`make_stream`, `cell_hash` — the
  four formulas verbatim (`RootKey`, `AttemptKey(i)`, `Stream(label)`,
  `CellHash(label,x,y)`), each a pure function of its arguments only.
- `Pcg32` — a minimal PCG XSH-RR 64/32 generator (`next_u32`,
  `next_below(n)` via unbiased rejection sampling), seeded by `Stream`'s
  derived value. Reserved for genuinely sequential processes (darts,
  accretion order, repair) per `MG-24`; nothing indexed by cell should ever
  use it (`cell_hash` instead), and nothing in this module does.
- Not yet wired to anything — this is foundational scaffolding for the
  generator (layers 1-3) and for `CD-17`'s per-player card streams, both
  future increments. No `MatchSeed`/`SettingsHash`/`GeneratorVersion`
  plumbing or config schema exists yet to supply real values; tests exercise
  the formulas directly with arbitrary integers.
- `SettingsHash` itself (which settings it covers, the freeze-key exclusion
  rule) is **not implemented** — there is no settings schema yet (`DS-*`,
  a much later increment). This module only guarantees the property that
  exclusion rule depends on: equal `SettingsHash` values always reproduce
  the same `RootKey`.

### Not yet implemented

Everything else. In particular:

- `TM-4`, `TM-7` — trivial/rendering-only, nothing to implement in a headless
  core (Rock-is-mask-0 is already the only representation; `TM-7` is a
  rendering rule with no simulation-state counterpart).
- Section 3 (`MG-*`) — map generation proper. `MG-2`, `MG-3`, `MG-24` are
  done (above); **everything else in section 3 is the next increment**:
  `MG-5`..`MG-15`'s concrete guarantees (nothing generates a map yet, so
  there is nothing for them to check), the three-layer generator itself
  (`MG-17`), dead-end repair (`MG-18`), the symmetry repair loop (`MG-19`),
  placement search (`MG-20`), collectibles (`MG-21`-`MG-23`), and
  `MapDigest` (`MG-24`'s last piece). Also deferred: `MG-3`'s "one reverse
  Dijkstra from the Hub answers all four spawns at once" — the current
  `solve_cost` runs one forward Dijkstra per spawn, which is semantically
  identical but does 4 passes instead of 1; worth revisiting if/when
  generation performance actually matters (the §3.3 accretion loop calls
  this on every candidate rock placement).
- Section 4 (`MV-*`) — the movement state machine. Depends on `GE-*` (Hub
  cells, Start Pads) and reuses `Board.usable_exits` for `resolveExit`
  (`MV-7`) — note `MV-7`/`MV-8` explicitly use `usableExits`, i.e. **plain
  board connectivity**, not `G_T`; `G_T` is reserved for the softlock/
  fairness guarantees (`MG-6`, `AS-2`, `CD-13`), not for live routing. Don't
  conflate the two when implementing `resolveExit` and the route-highlight
  BFS (`MV-8`, `MV-12`).
- Section 5 (`CD-*`) — cards and legality, including the topology legality
  predicate `CD-13` (which is exactly `carryPreserving` + a `TransitGraph`
  reachability check either side of a proposed mutation — most of the hard
  part is already built).
- Section 6 (`AS-*`) — the anti-softlock theorem, encoded as fuzz/integration
  tests once `CD-*` and `MV-*` exist.
- Section 4.2's `Frozen` state and section 5.4 (`FZ-*`) — Freeze. Needs the
  full `Snail`/tick-order machinery from `MV-*`/`MP-5` first.
- Sections 7-11 (`MR-*`, `MP-*`, `PR-*`, `DS-*`) — match rules, multiplayer
  authority, presentation, developer settings. Multiplayer (`MP-*`) and
  presentation (`PR-*`) are engine/transport concerns largely out of scope
  for a headless `SimCore` oracle; revisit which parts of these are worth a
  pure-Python model (e.g. `MP-5`'s tick order, `MP-6`'s concurrent-edit
  arbitration) once `MV-*`/`CD-*`/`FZ-*` exist, since those two specifically
  describe `SimCore`-internal behaviour rather than networking.

### Next increment

**The map generator itself: `MG-5`, `MG-16`-`MG-23`.** The cost model and
determinism primitives it needs now both exist (this increment); this is
still the biggest remaining increment in the build order, so keep splitting
it further rather than doing all of section 3 in one pass — e.g. layer 1+2
placement first (a map with no rocks and no collectibles is already fully
testable against `MG-6`/`MG-8`/`MG-11`/`MG-14`), then the rock-accretion/
repair loop (`MG-17` layer 3, `MG-18`, `MG-19`), then collectibles
(`MG-20`-`MG-23`), then `MapDigest` (`MG-24`'s last piece) and the
determinism/cross-platform golden tests.

- `MG-5`: `geometry.place_fixed_geometry` already does the "Hub/Start Pads
  forced before any other placement" step this increment needs as its
  starting point.
- `MG-16`-`MG-17` layers 1-2: layer 1 is C4-symmetric corridors, reusing
  `geometry.rho` to replicate a quarter-turn fundamental domain; layer 2 is
  stateless per-cell hashing — `rng.cell_hash`, already built, not Python's
  `random` module, so results are reproducible across platforms. The
  `type(c)`/`ori(c)` weighted-pick formulas in `MG-17` need a
  `weighted_pick(hash_value, weights)` helper that doesn't exist yet
  (`CellHash` returns a raw integer; turning that into a weighted choice
  deterministically is a small new piece, not something `rng.py` already
  provides).
- `MG-17` layer 3, `MG-18`, `MG-19`: rock accretion (validated via
  `TransitGraph.solve_cost`/`reachable_to_hub` on every accept — both
  already exist), dead-end repair, and the symmetry repair loop. These are
  genuinely sequential (accretion order, repair candidates) so they should
  draw from `rng.make_stream`, not `cell_hash`.
- `MG-20`-`MG-23`: collectible placement (the dart-throwing relaxation
  ladder, `detour()` reusing the same Dijkstra machinery as `solve_cost`
  but from a forward direction, C4-quadruple placement reusing `geometry.rho`).
- `MG-24`'s remaining piece: `MapDigest` (FNV-1a 64 over the generated
  board + collectibles + spawns) and the `RootKey`/`AttemptKey` plumbing
  that actually drives one end-to-end `generate(seed, settings) -> Board`
  entry point — nothing calls `rng.py` yet; this is where it starts getting
  called.
- Tests: `MG-5`..`MG-15`'s guarantees hold for generated maps (start with a
  handful of fixed seeds per size, then widen); regenerate twice from the
  same seed and compare `MapDigest` (determinism); the 4 spawns' `SolveCost`
  spread satisfies `MG-11`, reusing `geometry.py`'s already-tested
  spawn/Hub cell sets and this increment's `solve_cost`.

### How to verify this increment

```
cd reference
python3 -m unittest discover -v
```

Last run: 98 tests, all passing, 0 failures, 0 errors (64 carried over from
increments 1-2 + 22 new in `test_rng.py` + 14 new in `test_transit.py`'s
`WeightedCostModelTests`; see the PR for the captured output).
