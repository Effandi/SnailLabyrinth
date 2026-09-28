# Progress

Read this file first if you are resuming this build. It records exactly
what is implemented, what is tested, and what the next increment should be.

## Status: increment 1 of N — tile model, connectivity, transit graph

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

### Not yet implemented

Everything else. In particular:

- `TM-4`, `TM-7` — trivial/rendering-only, nothing to implement in a headless
  core (Rock-is-mask-0 is already the only representation; `TM-7` is a
  rendering rule with no simulation-state counterpart).
- Section 2 (`GE-*`) — board geometry: the Hub, Apron, the four spawns and
  their C4 symmetry, Start Pads. **This is the next increment.**
- Section 3 (`MG-*`) — map generation. Depends on `GE-*` for Hub/spawn/Apron
  cell sets and on `TransitGraph` for `SolveCost` (needs the weighted
  `TAU`/`ACT` cost model on top of the unweighted BFS built so far — a
  Dijkstra variant of `TransitGraph`, not a rewrite of it).
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

**Board geometry and spawns: `GE-1` .. `GE-8`.**

- Hub cell set (`GE-1`, `GE-2`): 4 cells for even N, 1 for odd N, all forced
  to mask 15 + `FINISH_LOCKED`, untargetable by all cards (the untargetable
  part is a `CD-*` concern to wire in later; this increment should at least
  produce the correct cell set and apply the flag/mask).
- Apron cell set (`GE-1`, `GE-3`): orthogonal neighbours of Hub, outside Hub.
- Spawn cell set (`GE-5`, `GE-6`): the four `S[k]`, and a test that they are
  exactly the C4 orbit of `(m, 0)` under `rho(x,y) = (N-1-y, x)`, for every
  preset size in the spec's section 3.5 table (8, 12, 16, 20, 24).
- Start Pads (`GE-8`): immutable T-Junction, three non-outward openings,
  `SPAWN_PAD` flag, and the inward-neighbour `ROCK_PROTECTED` flag.
- Tests should use `TransitGraph.reachable_to_hub` from each spawn on a
  hand-built board to sanity-check the geometry before map generation
  (`MG-*`) exists to generate a full board automatically.

### How to verify this increment

```
cd reference
python3 -m unittest discover -v
```

Last run: 44 tests, all passing, 0 failures, 0 errors (see the PR for the
captured output).
