# Progress

Read this first on resume — it says exactly what is built, what is tested,
and what the next increment should be.

## Implemented

### `reference/sim/tiles.py` — spec section 1.1–1.3

| Rule | What |
|---|---|
| `TM-1` | `(x, y)` cell coordinates, `idx = y*N + x` |
| `TM-2` | 4-bit direction masks `N=1,E=2,S=4,W=8`; `cw`, `ccw`, `opp`, `orbit` |
| `TM-3` | `shape(mask)` derived from popcount + the two Straight masks; never stored |
| `TM-4` | Rock Blocker is mask 0, handled by the same `shape()` path as everything else |
| `TM-5` | implied by `cw`/`ccw` arithmetic (no special-casing needed; covered by tests) |
| `TM-6` | `Grid` class: `mask[N*N]`, `flags[N*N]`, `version[N*N]`; `set_mask` bumps `version` |
| `TM-7` | not applicable — a rendering rule, out of scope for `SimCore` (`HT-1`) |
| `TM-8` | `connected(grid, x, y, d)`, `usable_exits(grid, x, y)` — mutual openness only |
| `TM-9` | off-grid reads as mask 0 (`Grid.mask_at` bounds check); no wrapping |
| `TM-10` | **not implemented yet** — this is a card-legality (CD-*) rule, not a tile-model rule. See `OPEN_QUESTIONS.md`. |

### `reference/sim/transit_graph.py` — spec section 1.4

| Rule | What |
|---|---|
| `TM-11` | demonstrated by test: a Dead End carries no pair, a Straight carries only collinear pairs, an Elbow carries only turns, regardless of current orientation |
| `TM-12` | `carries(mask, a, b)`, `build_graph(grid)`, `source_nodes`, `reachable_nodes`, `is_reachable` — full `(cell, entryDir)` transit graph and BFS |

This module is the shared reachability primitive that `MG-6`, `AS-2`, and
`CD-13` will all call into once their increments land — it is deliberately
generic over the sink-cell set (not hardcoded to the Hub), since the Hub
doesn't exist yet (that's `GE-1`, section 2).

## Test results (last run)

```
$ cd reference && python3 -m unittest discover -v
...
Ran 38 tests in 0.006s

OK
```

38/38 passing. Covers every `§12.1` ("Headless-testable core") row that
applies to tile algebra, connectivity, and the transit graph:
- `cw⁴(m) == m`; `ccw(cw(m)) == m`; `opp(opp(d)) == d` (exhaustive, all 16 masks)
- `popcount` invariant under `cw`/`ccw` (the assertable form of `CD-7`)
- mask ↔ (shape, rotation) is a bijection (exhaustive)
- `connected(a,d) ⟺ connected(a+δ(d), opp(d))` (property, random boards)
- off-grid neighbours are never connected (exhaustive on the border ring)
- `carries()` matches the §1.4 table for all 6 shapes × 12 ordered direction pairs (exhaustive)
- a Dead End carries no pair; a Straight carries only collinear; an Elbow carries only turns (exhaustive)

## Open questions raised this increment

See `OPEN_QUESTIONS.md`:
- `TM-3`'s "rotation index" is informal in the spec; a test-only canonical
  convention was adopted (does not affect any stored/wire format).
- `TM-10` is explicitly deferred to the CD-* (card legality) increment.

## Next increment

Per the build order (`BO-1`) and the task's suggested sequencing, the next
coherent unit is **section 2: board geometry and spawns (`GE-1`..`GE-8`)**:

- `GE-1`/`GE-2`/`GE-3`/`GE-4`: the Hub as a 4-cell (even N) or 1-cell (odd N)
  logical goal node, `FINISH_LOCKED`, forced to mask 15, untargetable; Apron
  cells ordinary and contestable.
- `GE-5`/`GE-6`/`GE-7`: the four spawns as the C4 orbit of `(m, 0)`, one per
  side, no teams, no assignment problem.
- `GE-8`: Start Pads as immutable T-Junctions, `SPAWN_PAD` flag, the inward
  `ROCK_PROTECTED` neighbour.

This increment should:
1. Add a `board.py` (or similar) building on `sim/tiles.py`'s `Grid` and
   `flags` bit constants (`FINISH_LOCKED`, `SPAWN_PAD`, `ROCK_PROTECTED`
   already exist in `tiles.py`).
2. Reuse `sim/transit_graph.py`'s `is_reachable`/`reachable_nodes` for any
   Hub-reachability check — do not write a second BFS.
3. Test at every preset size (8, 12, 16, 20, 24) since `GE-5`'s `m` formula
   and the Hub cell set both branch on N even/odd and the spawn `m` value
   differs per size (§3.5's table: `m = 2,3,4,5,6`).
4. Verify `GE-6`'s C4 simple-transitivity claim directly: compute
   `ρ(x,y) = (N-1-y, x)` and check it maps `S[k] -> S[k+1 mod 4]` for all 4
   spawns at all 5 sizes.

After section 2, the natural following increments are section 3 (map
generation, `MG-*` — this is large; consider splitting accretion/repair
from the cost-model Dijkstra) and section 4 (movement state machine,
`MV-*`).
