# Progress

Read this file first if you are resuming this build. It records exactly
what is implemented, what is tested, and what the next increment should be.

## Status: increment 6 of N — `MG-7` (vertex-disjoint routes), `MG-18`
## wired into the pipeline, and `MG-17` layer 3 (rock accretion)

> **Note on process, read before opening another PR — same warning as
> increment 5's, now resolved for the lineage this increment extends.**
> At the time this increment started, **seven** PRs existed against this
> repository (`#1`-`#7`), none merged, including **two independent
> duplicate restarts of increment 1 from `main`** (`#6`, opened after `#4`
> already existed, and now this run's own first instinct before this note
> stopped it). The real lineage was `main` -> `#4` (`reference/map-
> generation`) -> `#5` (`reference/map-generation-layers-1-2`) -> `#7`
> (`reference/dead-end-repair-mg18`, the deepest unmerged tip). **This
> increment's branch was built by fetching `origin`, listing every open
> PR via the GitHub API (not just `git log` on the local checkout), and
> stacking on `#7`'s branch** — the same process increments 4 and 5 asked
> for, which a scheduled run (this one, initially) skipped anyway because
> `main` has no `reference/` directory and nothing announces the
> unmerged PRs to a fresh checkout.
>
> **The actual fix is still outside this process's own power, and it has
> now been asked for twice without happening:** someone with merge access
> needs to merge the chain (`#4` -> `#5` -> `#7` -> this increment's PR,
> oldest first) into `main`, or explicitly decide to restart from a clean
> `main` and close the rest. Until `main` actually has a `reference/`
> directory, every future scheduled run will keep finding this same
> situation, and at least one of them will keep re-doing increment 1 by
> accident the way this run's first instinct did — the GitHub-API-listing
> step this note asks for is a mitigation, not a fix, because it depends
> on every run remembering to do it before writing any code.

### Implemented this increment

**`snail_labyrinth/routes.py`** and **`snail_labyrinth/flow.py`**, new —
spec section 3.2, `MG-7`:

- `flow.FlowNetwork` — a small generic max-flow primitive (Edmonds-Karp:
  BFS augmenting paths), with early stopping once a target flow value is
  reached. `MG-7`'s own suggested algorithm, "vertex-capacitated max-flow
  >= 2 (node splitting, two BFS augmentations)", is implemented literally:
  `max_flow_at_least(source, sink, 2)` runs at most two augmenting-path
  searches. Knows nothing about cells, directions, or `G_T` — opaque,
  hashable node identifiers only.
- `routes.exempt_cells(n)` — the cells `MG-7`'s vertex cap does not need
  to apply to: Hub (`GE-2`, untargetable), Spawn Pads (`GE-8`, likewise),
  and each Start-Pad `ROCK_PROTECTED` inward neighbour (`GE-8`) — none of
  these can ever carry a Rock, so there is nothing for a disjointness cap
  to defend. A deliberately *smaller* set than `generator.
  protected_from_rocks` (below) — see `OPEN_QUESTIONS.md` OQ-10.
- `routes.has_two_vertex_disjoint_routes(board, spawn_cell, hub, exempt=None)`
  — builds a direction-aware node-split flow network on top of
  `TransitGraph`'s existing `first_departures`/`edges_from` (no
  duplication of `G_T`'s own carries-gating or BLOCK-exclusion logic): a
  capacity-1 "arrival bottleneck" per not-exempt cell, placed strictly
  between "a predecessor's exit lands here" and "the route resumes toward
  a specific further exit" so the per-entry-direction `carries()` legality
  that gates a Straight's or Elbow's further travel is preserved exactly,
  while still capping the *cell's* total use (across every entry-direction
  variant combined) to 1. The module docstring explains why a naive
  per-cell cap (ignoring entry direction) would be wrong, and why Hub
  cells need an *unlimited*, not capacity-1, edge into the sink (two
  routes converging on the exact same final (Hub cell, entry direction)
  hop is a real, legitimate case — the Hub has only 8 outward edges total,
  `GE-4` — and is not itself a defended resource).
- `tests/test_flow.py` (8 tests) and `tests/test_routes.py` (7 tests):
  the flow primitive on hand-built graphs (parallel paths, a shared
  bottleneck fed by multiple predecessors, the degenerate source==sink
  case); `has_two_vertex_disjoint_routes` on hand-built boards with a
  *known* route count — two independent branches (2 routes), a single
  branch (1 route, correctly fails), a shared choke cell that caps two
  branches at 1 route, and the same choke marked exempt to confirm 2
  routes are then correctly allowed. **The choke/exempt pair of tests is
  the one that actually caught a real bug while writing it** (the
  dir_node->SINK edge was originally capacity 1, which silently became a
  second, unintended bottleneck whenever two routes converged on the
  exact same Hub-cell landing — see the `land()` comment in `routes.py`
  for the fix); worth recording because it is exactly the kind of subtle
  node-split mistake a reviewer should specifically look for.

**`snail_labyrinth/generator.py`**, extended — spec section 3.3, `MG-18`
wired into the pipeline, and `MG-17` layer 3:

- `generate_layers_1_and_2(n, root_key)` — the old `generate_board`
  body, factored out under a new name. Exists for callers (chiefly tests)
  that specifically need layers 1-2 in isolation, pre-repair,
  pre-accretion.
- `protected_from_rocks(n)` — `MG-17`'s "Protected from rocks at
  generation ... HUB union APRON union StartPads union
  StartPad-inward-neighbours." Deliberately a *larger* set than `routes.
  exempt_cells`: Apron is generation-protected but remains legally
  rockable by players at runtime (`GE-3`). See `OPEN_QUESTIONS.md` OQ-10
  for the `GE-3`/`MG-17` "and at runtime" tension this reflects, left for
  the `CD-13` increment to resolve with real code in front of it.
- `ACCRETION_DEFAULTS` — section 3.5's per-size `(C_target, rock% ceiling)`
  table, as a plain dict (not wired to the developer-settings schema,
  section 10, which does not exist yet).
- `generate_layer3(board, root_key)` — the accretion loop itself:
  candidates ordered by `CellHash("walls", ...)`, a hash-chosen growth
  direction (`CellHash("walls_dir", ...)`) and segment length 2-4
  (`CellHash("walls_len", ...)`); tentatively Rock the whole segment;
  accept iff every spawn's `SolveCost` (`MG-6`) is still finite **and**
  did not decrease **and** every spawn still has two vertex-disjoint
  routes (`MG-7`), else revert the whole segment. Stops once mean `C`
  reaches `C_target` or the rock fraction reaches the ceiling (checked at
  the *start* of each candidate's turn, per `MG-17`'s own pseudocode, so
  the final fraction can overshoot the ceiling by up to one segment — not
  a bug, see the measurements below). If the pre-accretion board already
  has an unreachable spawn (an `MG-18`-can't-fix-it case, still possible
  before `MG-19` exists), accretion does nothing rather than placing
  rocks against an undefined "mean C" baseline. See `OPEN_QUESTIONS.md`
  OQ-9 for why candidate order/direction/length are each read as a
  stateless hash rather than `MG-24`'s "accretion order" sequential
  stream (a sharper version of OQ-7's tension, resolved the same way).
- `generate_board(n, root_key)` — now the **full** pipeline:
  `generate_layers_1_and_2` -> `repair_dead_ends` (`MG-18`) ->
  `generate_layer3`. Every existing caller that specifically wanted the
  pre-repair, pre-accretion board (`test_generator.py`'s
  `MG6PreRepairCharacterizationTests` and its statistical-distribution
  test, and `test_repair.py`'s own real-generator sweep) was switched to
  call `generate_layers_1_and_2` directly instead, so they keep testing
  exactly what their names and docstrings say — see "Tests adjusted this
  increment" below.

**`reference/tests/test_layer3.py`**, new — 11 tests, deliberately over a
*small* seed budget (3 seeds, not 40 — see the module docstring and
"Performance" below): `protected_from_rocks`'s composition and its
strictly-larger-than-`exempt_cells` relationship; layer 3 never places a
Rock on a protected cell; the rock fraction stays within the ceiling plus
one segment's overshoot; layer 3 never regresses `MG-6` solvability
relative to the pre-accretion board; determinism; the "does nothing when
the pre-accretion board is already unsolvable" case, directly exercised;
and, for the full `generate_board` pipeline: it matches a manually
assembled call sequence byte-for-byte, it actually places rocks on most
boards, its `MG-6` solvability rate is at least as good as layers 1-2
alone, and Hub/Spawn-Pad survive intact.

### Tests adjusted this increment

`generate_board`'s meaning changed (it now runs repair and accretion), so
every existing test whose premise was specifically "layers 1-2 only,
no rocks, pre-repair" had to be pointed at the new
`generate_layers_1_and_2` instead, or it would have started testing a
different thing than its own name and docstring claim, or (worse) started
paying layer 3's much higher per-board cost for no reason:

- `tests/test_generator.py`: `test_no_rock_anywhere_before_layer_3` (now
  `Layer1And2OnlyTests.test_no_rock_anywhere_in_layers_1_and_2_alone`),
  `test_statistical_type_distribution_over_the_free_interior` (moved into
  the same new `Layer1And2OnlyTests` class), and both
  `MG6PreRepairCharacterizationTests` methods.
- `tests/test_repair.py`: all three `generate_board(...)` calls in
  `RepairAgainstTheRealGeneratorTests`.

`GenerateBoardTests` in `test_generator.py` keeps only the invariants that
hold regardless of layer 3 (Hub/Spawn-Pad survive, determinism).

### Performance, and why the test seed budget shrank for this increment

Every accept/revert attempt in `generate_layer3` costs one `solve_cost`
Dijkstra (4 spawns) plus one `has_two_vertex_disjoint_routes` max-flow
check (4 spawns), repeated per candidate tried until `C_target`/`rockMax`
is hit. Measured single-board `generate_board` wall-clock (this machine,
one seed each): N=8 ~0.03s, N=12 ~0.2s, N=16 ~0.3s, N=20 ~0.35s, N=24
~1.6s. `tests/test_layer3.py` caches each `(n, seed)`'s pipeline result
once (`_pipeline`/`_full_pipeline_board`) and reuses it across every test
method that needs it, and uses 3 seeds rather than the 40 used elsewhere
in this project; the full suite (170 tests) runs in about a minute on
this machine. Revisit the seed budget if a real regression needs a wider
net — it was chosen for test suite runtime, not because 3 seeds is
inherently enough evidence.

### Increment 5's summary, for history

**`snail_labyrinth/repair.py`** — spec section 3.3, `MG-18`:

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

### Increment 4's summary, for history

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

*(The rest of increment 5's own "Not yet implemented" / "Next increment"
sections are omitted here — they asked for exactly what this increment
(6) built (`MG-7`, `MG-18` wired in, layer 3), and are superseded by the
current versions below rather than kept as a second, now-stale copy.)*

### Not yet implemented

- `MG-19` — the repair loop that closes residual `MG-11`/`MG-14`
  asymmetry *and* residual block-free disconnection from misoriented
  tiles (re-orient, retype Elbow<->Tee, revert one rock segment; capped
  at 3% of cells; never touches Hub/Apron/Start Pads; never creates a
  dead end). This is now **the** next increment — see below.
- `MG-9`, `MG-10` — near-optimal route diversity (k-shortest-paths, k=4)
  and the route-overlap cap. Not yet attempted; `MG-7`'s flow network
  (this increment) handles the *existence* of two disjoint routes but not
  yet "k=4 paths within 1.25x cost" or "no non-Apron cell on >2 spawns'
  optimal route."
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

**`MG-19`: the repair loop that closes residual `MG-11`/`MG-14` fairness
asymmetry and residual block-free disconnection from misoriented tiles.**
This is squarely the next step per the ordering increment 4 laid out and
every increment since has confirmed: `MG-18` (dead-end repair) and layer
3 (rock accretion, this increment) both only ever *add* openings or
*validate against* `MG-6`/`MG-7` — neither one re-orients an already-
present Straight/Elbow/Tee, which is exactly the residual failure mode
`test_the_previously_pinned_concrete_failure_needs_more_than_mg18` (in
`test_repair.py`) pins down concretely (`N=8`, seed 31, spawn `S0`,
bounded by misoriented Elbow/Tee cells, not a Dead End). Suggested shape,
per `MG-19`'s own pseudocode (section 3.3):

```
for iter in 1..256:
    C, P = solveAll()                        # costs + optimal paths
    if MG-11 and MG-14 hold: return OK
    hi = argmax C ; lo = argmin C
    candidates = sorted(P[hi] \ P[lo])        # cells only the slow spawn uses
    apply the single edit minimising (max C / min C), from:
        1. re-orient a cell          (cheapest, try first)
        2. retype ELBOW <-> TEE      (never create a DEADEND)
        3. revert one accreted rock segment
    if no edit improves the ratio: break
return REJECT -> retry with AttemptKey(i+1)
```

Concretely: `TransitGraph.solve_cost` (already exists) gives `C` per
spawn; the *path* `P[s]` itself is not currently returned by `solve_cost`
(it returns the cost pair only) — this increment will need a path-
reconstruction variant (parent pointers through the Dijkstra, same
pattern `repair.py`'s frontier search uses for determinism) before
`P[hi] \ P[lo]` is computable. Constraints from the spec to carry over
literally: never touches Hub/Apron/Start Pads, never creates a Dead End,
never edits a cell on >= 3 spawns' optimal routes (prevents oscillation),
capped at 3% of cells. `AttemptKey(i)` (`MG-24`, already implemented in
`rng.py`) is the retry mechanism on total rejection — this increment
should be the first caller that actually uses it for something.

After `MG-19` lands, re-run the full sweep and measure `MG-6`/`MG-8`/
`MG-11`/`MG-14` honestly (same style as the tables in this file) — this
is the point at which all four should finally be expected to pass, or
close to it, and is worth stating plainly either way rather than assuming.

### How to verify this increment

```
cd reference
python3 -m unittest discover -v
```

Last run: **170 tests, all passing, 0 failures, 0 errors** (144 carried
over from increments 1-5 + 26 new: 8 in `tests/test_flow.py`, 7 in
`tests/test_routes.py`, 11 in `tests/test_layer3.py`). Takes roughly a
minute — see "Performance" above for why, before assuming something is
hanging.
