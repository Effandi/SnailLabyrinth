# Progress

This file is how the next scheduled run knows where to resume. Keep it
precise: what's implemented, which rules are covered by tests, and exactly
what the next increment is.

## Implemented (increment 1)

**Module:** tile model, mutual connectivity, and the transit graph `G_T`.

| File | Spec rules | Notes |
|---|---|---|
| `snail_labyrinth/directions.py` | `TM-2` | Direction bits, `cw`/`ccw`/`opp`, `orbit`, `popcount`. |
| `snail_labyrinth/tile.py` | `TM-3`, `TM-5` | `shape(mask)`, the mask<->shape table, rotation-noop / CW-equals-CCW facts. |
| `snail_labyrinth/board.py` | `TM-6`, `TM-8`, `TM-9`, `TM-10` | `Board` grid state (`mask`/`flags`/`version`), mutual `connected()`/`usable_exits()`, off-grid-is-Rock border handling, flag helpers. |
| `snail_labyrinth/transit_graph.py` | `TM-11`, `TM-12` | `carries()`, `source_nodes()`, `neighbors()`, `bfs_transit()`, `is_solvable()` — reachability over `(cell, entryDir)` nodes, not open-cell connectivity. |

**Explicitly not implemented, by design:** `TM-4` (Rock-is-mask-0) is
implicit in `shape()`/`popcount` and not a separate code path, per the
spec's own point. `TM-7` (rendering/mesh-yaw rule) is out of scope for
`SimCore` per `HT-1` — see `OPEN_QUESTIONS.md`.

**Tests:** 41 tests, all passing (`python3 -m unittest discover -v` from
this directory). Coverage includes every §12.1 "Tile algebra" and
"Connectivity" row, and the "Transit graph" rows (`carries()` exhaustive
over all 6 shapes x 12 ordered direction pairs; a Dead-End-sealed corridor
and an Elbow-sealed straight corridor are both correctly judged
unsolvable, while the same corridors with Straight/TEE/Cross middles are
solvable — the concrete demonstration of `TM-11`'s "naive connectivity
passes boards that are actually unsolvable" claim).

**Open questions filed:** two, both in `OPEN_QUESTIONS.md` (`TM-7` scope,
`flags` bit-order non-normativity, and `source(s)` semantics reasoning).
Neither blocks downstream work.

## Next increment

**Board geometry and spawns: `GE-1` through `GE-8`.**

Build a `geometry.py` (or similar) module, pure function of board size `N`,
that computes:

- `HUB` (the 2x2-or-1 centre cell set, `GE-1`) and forces those cells to
  mask 15 + `FINISH_LOCKED` (`GE-2`) — note Hub cells must also be
  untargetable by all six cards, but *card legality* is `CD-*` (a later
  increment); this increment should just establish the Hub's forced state
  and flag, not the targeting-legality check itself.
- `APRON` (orthogonal neighbours of `HUB`, outside `HUB`; `GE-1`, `GE-3`) —
  ordinary, rotatable, rockable cells; record them as a set so later `CD-13`
  (not yet implemented) can reference "zero non-Rock apron cells" as an
  illegal state.
- The four spawns `S0..S3` as the C4 orbit of `(m, 0)` (`GE-5`, `GE-6`),
  with `m = clamp(round(N/4), 1, N/2 - 2)`. Verify spawns are a *simply
  transitive* C4 orbit (`GE-6.1`) for all five preset sizes (8, 12, 16, 20,
  24) and that minimum spawn-to-Hub Manhattan distance is identical across
  all four at each size (the numbers in `GE-6.1`'s parenthetical: 4, 7, 10,
  13, 16).
- Start Pads (`GE-8`): each `S[k]` forced to an immutable T-Junction, open
  on the three non-outward directions, flagged `SPAWN_PAD`; the inward
  neighbour `S[k] + inward` flagged `ROCK_PROTECTED`.

**Suggested tests to write** (these are the §12.1-adjacent invariants that
apply to `GE-*`, even though §12.1's own table doesn't enumerate them by
name — the Generation row of §12.1 covers `MG-*`, which depends on this
module existing first):

- `HUB` has exactly 4 cells for even `N`, 1 for odd `N`, and every preset
  size in `MG`'s table (8, 12, 16, 20, 24) matches the `(N/2-1, N/2-1)...`
  formula in `GE-1` literally (cross-check against the §3.5 table's `Hub`
  column, which gives the exact cell coordinates per size).
- Every Hub cell, after geometry setup, has `mask == 15` and
  `FINISH_LOCKED` set (`GE-2`).
- `APRON` has exactly 8 cells for even `N`, 4 for odd `N` (`GE-1`).
- The spawn set equals `{rho^k(S0) : k in 0..3}` for the rotation
  `rho(x,y) = (N-1-y, x)` (`GE-6`), i.e. apply `rho` to `S0` and confirm you
  get `S1, S2, S3` in order, and that `rho^4 == identity`.
- `GE-6`'s chirality claim: the mirror `mu(x,y) = (N-1-x, y)` does *not*
  map the spawn set onto itself (a property test, not an invariant to
  enforce — it's stated to confirm nobody "fixes" it later).
- Start Pad mask is a T-Junction (`popcount == 3`) missing exactly the
  outward direction, for all 4 spawns at all 5 preset sizes.
- `S[k] + inward` is flagged `ROCK_PROTECTED` but remains otherwise
  ordinary (still rotatable — i.e. `ROCK_PROTECTED` is a flag the *rock
  legality* predicate (`CD-13`, not yet built) must consult, not something
  this module enforces by itself).

After `GE-*`: map generation (`MG-*`), which needs `geometry.py`'s Hub/Apron/
Spawn/StartPad output plus the seeded-stream and cell-hash primitives of
`MG-24` (splitmix64/pcg32/fnv1a64 — pure-stdlib integer hashing, no
dependency needed) before the layered generator (`MG-16`..`MG-23`) can be
written.

## Longer-term build order (unchanged from spec §14.1 / this task's brief)

1. ~~Tile model + connectivity + transit graph (`TM-*`)~~ — **done, this increment.**
2. Board geometry and spawns (`GE-*`) — **next.**
3. Map generation (`MG-*`).
4. Movement state machine (`MV-*`).
5. Cards and legality (`CD-*`).
6. Anti-softlock invariants (`AS-*`).
7. Freeze (`FZ-*`).
8. Match rules / placement (`MR-*`), draw/bag mechanics, determinism/golden
   tests (`MG-24`'s `MapDigest`, full-state-hash determinism test from
   `HT-1`/§12.1 "Determinism" row).
