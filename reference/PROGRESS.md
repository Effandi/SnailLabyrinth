# Progress

Read this file first if you are resuming this build. It records exactly
what is implemented, what is tested, and what the next increment should be.

## Status: increment 2 of N — board geometry and spawns

> **Note on process (increment 2):** this increment's PR (`reference:
> board geometry and spawns (GE-1..GE-8)`) is stacked on top of increment
> 1's PR (`reference/tile-model-transit-graph`, #1 on GitHub), which was
> still open/unmerged when this run started. Two independent scheduled runs
> both built increment 1 concurrently under slightly different branch
> names/APIs; this run detected the collision, discarded its own duplicate
> of increment 1, and continued on top of the version already pushed and
> under review rather than compete with it. If you are a human merging
> these: merge #1 first, then this PR's base will need retargeting to
> `main` (or just merge in order, which resolves it the same way). If you
> are the next scheduled run: check for open, unmerged `reference/*` PRs
> before assuming `main` is the base to build on — `PROGRESS.md` only
> reflects what has been *written*, not what has been *merged*.

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

### Not yet implemented

Everything else. In particular:

- `TM-4`, `TM-7` — trivial/rendering-only, nothing to implement in a headless
  core (Rock-is-mask-0 is already the only representation; `TM-7` is a
  rendering rule with no simulation-state counterpart).
- Section 3 (`MG-*`) — map generation. **This is the next increment.**
  Depends on `GE-*` (now implemented) for Hub/spawn/Apron cell sets and on
  `TransitGraph` for `SolveCost` (needs the weighted `TAU`/`ACT` cost model
  on top of the unweighted BFS built so far — a Dijkstra variant of
  `TransitGraph`, not a rewrite of it).
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

**Map generation: `MG-1` .. `MG-24`.** This is the biggest single increment
in the build order so far; consider splitting it further (e.g. layer 1+2
placement first, then the rock-accretion/repair loop, then collectibles)
rather than doing all of section 3 in one pass.

- `MG-2`/`MG-3`: the weighted cost model (`TAU`, `ACT`, `SolveCost`) is a
  Dijkstra variant over the *same* `G_T` nodes `transit.py` already defines
  — extend `TransitGraph` (e.g. a `solve_costs()` method doing one reverse
  Dijkstra from the Hub) rather than duplicating the graph structure.
  Everything must stay integer arithmetic (`MG-2`: "All generator arithmetic
  is integer").
- `MG-5`: `geometry.place_fixed_geometry` already does the "Hub/Start Pads
  forced before any other placement" step this increment needs as its
  starting point.
- `MG-16`-`MG-19`: layer 1 (C4-symmetric corridors, reusing `geometry.rho`
  to replicate a quarter-turn fundamental domain), layer 2 (stateless
  per-cell hashing — `CellHash` per `MG-24`, not Python's `random` module,
  so results are reproducible across platforms), layer 3 (rock accretion,
  validated via `TransitGraph` on every accept), dead-end repair (`MG-18`),
  and the symmetry repair loop (`MG-19`).
- `MG-24`: determinism scaffolding (`splitmix64`, `fnv1a64`, `pcg32`,
  labelled stream splitting) is foundational and probably belongs in its
  own small module (e.g. `rng.py`) that `MG-*`'s generator and later the
  per-player card streams (`CD-17`) both import, rather than being
  reimplemented per-caller.
- Tests: `MG-5`..`MG-15`'s guarantees hold for generated maps; regenerate
  twice from the same seed and compare `MapDigest` (determinism); the 4
  spawns' `SolveCost` spread satisfies `MG-11`, reusing `geometry.py`'s
  already-tested spawn/Hub cell sets.

### How to verify this increment

```
cd reference
python3 -m unittest discover -v
```

Last run: 64 tests, all passing, 0 failures, 0 errors (44 from increment 1
+ 20 new in `test_geometry.py`; see the PR for the captured output).
