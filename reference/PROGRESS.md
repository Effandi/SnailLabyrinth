# Progress

Read this file first if you are resuming this build. It records exactly
what is implemented, what is tested, and what the next increment should be.

## Status: increment 5 of N — dead-end repair (`MG-18`)

> **Note on process — read this before opening another PR; this is now
> the third time it has needed restating.** As of this increment there are
> **six** PRs open against this repository (`#1`-`#6`), spanning roughly
> seven weeks, and **none has been merged** — `main` still contains only
> the spec and decisions documents, with no `reference/` directory at all.
> Every increment's actual lineage lives only in the unmerged PR chain on
> GitHub, not in any local branch a fresh checkout of `main` would show.
> **This increment was built by `git fetch origin`, listing open PRs via
> the GitHub API (not just `git log`), finding `#5`
> (`reference/map-generation-layers-1-2`, stacked on `#4`) as the deepest
> unmerged chain, checking it out, and running its test suite (123/123
> passing) before writing any code** — the same process `#5`'s own note
> asked for. This increment's branch stacks on top of `#5`'s branch, not
> `main`, so its diff is just this increment.
>
> **If you are the next scheduled run, do this before anything else:**
> `git fetch origin`, then list open pull requests (not just local
> branches) and read the most recently created *open* one's `PROGRESS.md`
> from its branch tip. Stack your branch on top of it, the same way. Do
> **not** branch from `main` — `main` is now five increments stale and
> branching from it guarantees you will duplicate work that already
> exists, unmerged, on GitHub.
>
> **This note belongs to the repository's owner, not to any one scheduled
> run, and the right fix is outside this process's own power:** someone
> with merge access needs to either merge the PR chain (oldest first:
> `#4` -> `#5` -> this one) or explicitly say the project should restart
> from a clean `main`. Until that happens, every future run should expect
> to find this same situation and keep stacking, rather than silently
> re-doing increment 1 from `main` again.

### Implemented this increment

**`snail_labyrinth/repair.py`**, new — spec section 3.3, `MG-18`:

- `is_blocked(board, cell)` — `MG-7`/`MG-18`'s `BLOCK = ROCK ∪ DEAD_END`:
  is this cell excluded as a vertex of the BLOCK-free graph? A Dead End is
  excluded exactly like a Rock, regardless of which single direction it
  currently opens (`TM-11`'s "a Dead End... is a soft rock").
- `block_free_component(board, sources)` — plain BFS over *current*
  mutual connectivity (`TM-8`, `Board.connected`), restricted to non-BLOCK
  vertices. Deliberately **not** `TransitGraph`/`G_T`: this measures
  whether the board is connected *as currently oriented*, which is a
  **stronger** requirement than `MG-6`'s rotation-permissive reachability
  — see the module docstring and `OPEN_QUESTIONS.md`.
- `find_frontier_dead_ends(board, component)` — the actual boundary
  `MG-18` describes: a Dead End only counts as "frontier" if some member
  of `component` already has an opening pointing *at* it (a one-sided
  wall, `TM-8`). A Dead End merely sitting next to the component with
  nothing pressing on it is not picked.
- `choose_repair_mask(required_dirs)` — builds the replacement Tee: pads
  up to 3 openings in fixed `N,E,S,W` priority order when fewer than 3 are
  required, or drops the lowest-priority one when all 4 would be (see
  `OPEN_QUESTIONS.md` OQ-8 for why that case can arise and why dropping is
  safe).
- `repair_dead_ends(board, root_key, hub=None, spawn_cells=None)` — the
  actual `MG-18` loop: while some spawn is outside the Hub's BLOCK-free
  component, find every frontier Dead End, order them by
  `cell_hash(root_key, "repair", x, y)` (`MG-18`'s "deterministic hash
  order" — see `OPEN_QUESTIONS.md` OQ-7 for why a stateless hash was used
  over `MG-24`'s sequential "repair" stream), convert the lowest-hash one,
  repeat. Terminates either on full connection or when no frontier Dead
  End remains (a real, expected outcome — see below), capped at `n*n`
  steps as an unbounded-loop safety net in `MG-20`'s spirit. `hub` and
  `spawn_cells` default to the real `GE-1`/`GE-5` geometry but can be
  overridden, which is what makes the loop mechanics directly unit
  testable on small synthetic boards rather than only through the full
  generator.

**`reference/tests/test_repair.py`**, new — 21 tests: `is_blocked`
exhaustively; `block_free_component`'s Dead-End-exclusion-even-when-open
and misorientation-is-a-real-wall properties; `find_frontier_dead_ends`'s
no-frontier-without-pressure case and its required-direction accumulation
from one, two, and three distinct pressing neighbours; `choose_repair_mask`
exhaustively over every required-direction subset size 1-4 (always a Tee,
always a superset where it fits); integration tests on hand-built boards
showing repair connects a single obstruction, chains through several in
sequence, and terminates cleanly (not looping, not touching cells outside
its remit) when the real obstruction is a Rock or a misoriented
non-Dead-End tile instead; and, against the real `generate_board` pipeline
across the full 5-size x 40-seed sweep, a proof-by-measurement that repair
never *un-solves* a spawn that was `G_T`-solvable before it ran, plus an
honest (not-asserted-perfect) solvability improvement measurement.

### What this increment's measurements show, honestly

Running `repair_dead_ends` after `generate_board`'s layers 1-2, across the
same 5-size x 40-seed sweep increment 4 used for its own characterization:

| Metric | Before `MG-18` | After `MG-18` |
|---|---|---|
| `MG-6` (`G_T` reachability, the real target) | 782/800 (97.75%) | **786/800 (98.25%)** |
| Spawns that regressed (solvable -> unsolvable) | — | **0**, every run |
| Board-level block-free full connectivity (`MG-18`'s own, stronger, loop-termination condition) | not applicable pre-repair | 6/200 boards (3%) |

Two things worth stating plainly, because both are easy to get wrong by
skimming the first number:

1. **`MG-18` alone only ever helps or does nothing — it never hurts.**
   Converting a Dead End to a Tee strictly adds openings (the chosen mask
   always retains the Dead End's original bit) to a cell that, as a Dead
   End, never carried any route through it anyway (`TM-11`). Zero
   regressions were observed across the full sweep, and the module
   docstring states why that is expected rather than lucky.
2. **It closes only 4 of the 18 previously-unsolved spawns, and that is
   the correctly-scoped result, not a shortfall.** The previously-pinned
   concrete failure (`test_generator.py`'s `N=8`, seed 31, spawn `S0`) is
   investigated directly in this increment's tests
   (`test_the_previously_pinned_concrete_failure_needs_more_than_mg18`):
   its Hub-side block-free component is bounded entirely by **misoriented
   Elbow and Tee cells**, with no Dead End anywhere on that boundary at
   the point repair starts, so `repair_dead_ends` correctly makes zero
   progress on it (`steps=0`). `MG-18`'s own text ("a 10% dead-end field
   alone seals spawns") is a true statement about *aggregate* solvability
   across many seeds, not a claim that every individual failure is
   specifically a Dead-End-shaped obstruction sitting right at the
   boundary — most of layers 1-2's remaining disconnection is from plain
   misorientation of ordinary shapes, which is `MG-19`'s job, not this
   rule's. Block-free full connectivity (the *stronger* bar) staying low
   (6/200) after `MG-18` alone is exactly consistent with this: closing
   that gap needs re-orientation, not more Dead-End conversion.

`generate_board` itself is **unchanged this increment** — `repair_dead_ends`
is not wired into its pipeline yet. This was a deliberate choice, not an
oversight: wiring it in now would change the realised Dead-End/Tee ratio
in the free interior and risk breaking increment 4's
`test_statistical_type_distribution_over_the_free_interior` (which checks
the *unrepaired* layer-2 hash output converges to the authored weights).
The natural point to wire `repair_dead_ends` into `generate_board` is when
layer 3 (rock accretion) lands, since accretion's own accept/revert check
already assumes a solvable board going in (increment 4's `PROGRESS.md`) —
at that point the full pipeline becomes layer1 -> layer2 -> `MG-18` repair
-> layer3 accretion, and the statistical test above should move to call
`generate_layer2` directly rather than the full `generate_board`, to keep
testing what it was actually meant to test.

### Previous increment's summary, for history

**`snail_labyrinth/generator.py`** — spec section 3.3, `MG-16`,
`MG-17` layers 1-2:

- `weighted_pick(hash_value, weighted_items)` — the generic deterministic
  weighted choice `MG-17`'s `type(c) = weighted_pick(CellHash(...))`
  needs. Plain modulo against the (small, ~100) weight total rather than
  `rng.Pcg32`'s rejection sampling: there is no "redraw" available from a
  single fixed hash value, and the bias from plain modulo against a
  32-bit hash is astronomically negligible at this weight total.
- `type_mask(shape, ori)` / `cell_mask(root_key, x, y)` — `MG-17` layer
  2's per-cell formula (`type(c)`, `ori(c) & 3`, combined into a concrete
  mask). This is the one formula both layers 1 and 2 use; they differ
  only in which cells call it and how many images each result is
  replicated to.
- `c4_orbit`, `canonical_representative` — `GE-6`'s C4 orbit as a
  reusable primitive: the 4 images of a cell under repeated `rho`, and a
  deterministic "pick one representative of this orbit" rule (row-major
  least). Always exactly 4 distinct cells on every even preset `N`
  (`GE-6`: `rho` has no fixed point).
- `canonical_corridor_wedge`, `layer1_cells` — the geometric definition of
  layer 1's region (Apron ring + the canonical "Start Pad + radius-2
  wedge", replicated via `c4_orbit`). See `OPEN_QUESTIONS.md` OQ-5 for how
  "radius-2 wedge" was read (nothing in the spec defines it concretely).
- `generate_layer1` — generates one mask per orbit representative among
  the Apron ring and the canonical wedge, then writes the rotated mask
  (`cw` once per `rho` application) to every other member of that orbit.
  The whole region ends up exactly C4-symmetric by construction — tested
  exhaustively (`test_layer1_masks_are_c4_symmetric`) across all 5 preset
  sizes and several seeds.
- `generate_layer2` — every remaining cell (not Hub, not a Spawn pad, not
  claimed by layer 1) gets an independently hashed type/orientation —
  "free", per `MG-17`.
- `generate_board(n, root_key)` — composes `geometry.place_fixed_geometry`
  (`MG-5`) with layers 1-2 into a complete board. **No rock exists
  anywhere on the result** — layer 2's type weights are explicitly "over
  non-rock cells" (`MG-17`), and rocks are exclusively layer 3's job
  (next increment). Verified directly: every cell on a freshly generated
  board has a nonzero mask.

**`reference/tests/test_generator.py`**, new — 25 tests: `weighted_pick`
boundary/statistical behaviour, `type_mask`'s rotation-period edge cases
(Straight period 2, Cross period 1) cross-checked against `shape_of` for
every shape x ori combination, the C4-orbit primitives, the corridor
wedge's geometry (Chebyshev radius, exclusion of Hub/Apron/Spawn cells),
layer 1's exhaustive C4-symmetry check, `generate_board`'s determinism
(`MG-24`) and its untouched-Hub/untouched-Spawn-pad invariants, a
statistical check that the realised interior type distribution converges
to the authored 26/32/24/8/10 weights, and an honest characterization of
`MG-6` solvability pre-repair (see next paragraph).

### A correction to the previous increment's `PROGRESS.md`

Increment 3's `PROGRESS.md` described this increment's deliverable as "a
map with no rocks and no collectibles [that] is already fully testable
against `MG-6`/`MG-8`/`MG-11`/`MG-14`". Having built it and measured
empirically, **that is true only in the sense that the code to check
these now exists and runs** — the guarantees themselves do **not**
reliably hold from layers 1-2 alone:

| Guarantee | Observed pass rate (fixed seed sweep, 5 sizes x 40 seeds) |
|---|---|
| `MG-6` (every spawn's `SolveCost` finite) | ~97.75% (18/800 spawns fail) |
| `MG-8` (`C_min <= C(s) <= C_max`) | ~77% (903/1176 reachable spawns) |
| `MG-11` (`max C / min C <= 1.15`) | ~30% (88/291 fully-reachable boards) |

This is not a bug — it is exactly what `MG-18` ("dead-end repair is
mandatory") and `MG-19` (the symmetry repair loop) exist to fix, and the
spec's own framing (`GE-6`: layer 1's symmetry makes `MG-11` "achievable
rather than aspirational", not automatically true) says as much. A
concrete, reproducible `MG-6` failure (`N=8`, seed 31, spawn `S0`,
**zero rocks on the board**) is pinned down as a named test
(`test_a_concrete_pre_repair_failure_exists`) rather than left as an
aggregate statistic — see `OPEN_QUESTIONS.md` OQ-6 for the full
reasoning. Treat `MG-6`/`MG-8`/`MG-11`/`MG-14` as the *acceptance
criteria for the next few increments*, not as already-satisfied
properties of what exists now.

### Not yet implemented

- **Wiring `repair_dead_ends` into `generate_board`.** Deliberately
  deferred to the layer-3 increment — see "what this increment's
  measurements show" above for why.
- `MG-17` layer 3 — rock accretion (grow straight segments of length 2-4,
  validate via `TransitGraph.solve_cost`/`reachable_to_hub` on every
  accept, revert on failure or on no cost increase). `solve_cost` and
  `reachable_to_hub` already exist (increment 3) and are exactly what
  layer 3's accept/revert check needs.
- `MG-19` — the repair loop that closes residual `MG-11`/`MG-14`
  asymmetry *and* residual block-free disconnection from misoriented
  tiles (re-orient, retype Elbow<->Tee, revert one rock segment; capped
  at 3% of cells; never touches Hub/Apron/Start Pads; never creates a
  dead end). This increment's measurements make the need concrete: 6/200
  boards are block-free-fully-connected after `MG-18` alone, and the
  pinned `N=8`/seed-31 failure is a worked example of exactly the
  misorientation `MG-19` exists to fix.
- `MG-7`, `MG-9`, `MG-10` — the remaining structural guarantees (two
  vertex-disjoint routes, near-optimal route diversity, route-overlap
  cap). Not yet attempted; need a max-flow / k-shortest-paths
  implementation over `G_T` that does not exist yet.
- `MG-20`-`MG-23` — collectible placement (dart-throwing relaxation
  ladder, `detour()`, C4-quadruple placement).
- `MG-24`'s remaining piece — `MapDigest` and the end-to-end
  `generate(seed, settings) -> Board` entry point with real
  `MatchSeed`/`SettingsHash`/`GeneratorVersion` plumbing (nothing calls
  `root_key` with real values yet; tests all pass small arbitrary
  integers directly).
- Sections 4-11 (`MV-*`, `CD-*`, `AS-*`, `FZ-*`, `MR-*`, `MP-*`, `PR-*`,
  `DS-*`) — unchanged from previous increments' assessment, still all
  ahead.

### Next increment

**`MG-17` layer 3 (rock accretion), with `MG-18` wired into the pipeline
first.** Suggested shape:

- In `generate_board`, call `repair_dead_ends` right after `generate_layer2`
  and before returning — this is the point increment 4's own note
  predicted ("accretion's accept/revert check already assumes the board is
  solvable going in"). Move
  `test_statistical_type_distribution_over_the_free_interior` (currently in
  `tests/test_generator.py`) to call `generate_layer2` directly on a
  freshly-placed board instead of going through `generate_board`, so it
  keeps testing layer 2's hash fidelity specifically rather than the
  post-repair distribution.
- Layer 3 itself: `candidates = cells outside protected regions, ordered by
  hash`; for each, `grow a straight segment of length 2..4... tentatively
  set to ROCK`; accept iff `MG-6` and `MG-7` still hold **and** mean `C`
  did not decrease, else revert the whole segment. `MG-7` (two
  vertex-disjoint routes) does not exist yet and is needed for this
  accept/revert check — implement it as part of this increment, not
  separately; it is squarely layer 3's dependency, not a nice-to-have.
- After layer 3, re-run the full sweep and measure `MG-6`/`MG-8`/`MG-11`
  honestly (same style as increment 4's and this increment's tables)
  before claiming any of them pass — they are not expected to fully pass
  until `MG-19` also exists.
- `MG-19` (the repair loop) is the increment after that, per the ordering
  increment 4 already laid out and this increment's measurements confirm
  is still correct.

### How to verify this increment

```
cd reference
python3 -m unittest discover -v
```

Last run: 144 tests, all passing, 0 failures, 0 errors (123 carried over
from increments 1-4 + 21 new in `tests/test_repair.py`).
