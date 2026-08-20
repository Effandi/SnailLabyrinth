# Snail Labyrinth — Technical Design Specification

**Status:** authoritative. Where this document and the GDD disagree, this document wins and says so explicitly.
**Scope:** the normative rules of the simulation, the map generator, the card system, the authority model, and the developer-settings contract. Rationale is compressed to one line per decision; it is not the point of this document.
**Convention:** rules are numbered (`TM-3`, `CD-7`, …) so tests and bug reports can cite them. A rule marked **[TUNABLE]** has a matching key in the settings schema (§10). A rule marked **[FORK]** is a decision the developer must make before implementation (§0).

---

## 0. Decisions needed from the developer

**All four are settled.** D1, D2 and D4 were ruled on by the developer after this document's first draft and the rulings are recorded below as decisions, not recommendations. D3 stays a flag with a default; it is settled in playtest one, not before implementation. Everything else in this document is resolved.

| # | Decision | Ruling | Why |
|---|---|---|---|
| **D1** | **Engine and target platform** | **[SETTLED] Godot 4.7.1 stable, Windows first, Android later.** | The engine is nearly irrelevant to whether this game works — the simulation is a 256-byte integer array and four moving points. Godot 4.7.1 with export templates and a configured portable Android SDK/JDK is already installed on this machine and the Blender → glTF → Godot asset path is verified, which is 2–5 days of setup already paid for, and `--headless` gives the test harness in §12 for free. Two toolchain gotchas belong in the build script rather than in someone's memory: Android export needs `rendering/textures/vram_compression/import_etc2_astc=true` in `project.godot`, and Godot rewrites `editor_settings-4.7.tres` on exit, so Android export settings must be re-applied and the export run **in the same shell invocation**. |
| **D2** | **Player count, match structure, and multiplayer scope for v1** | **[SETTLED] 4 players, free-for-all, hot-seat on one shared screen.** The GDD's "4v4, 8 snails, two teams" is **withdrawn**: the game is 1 versus 3 others — 4 snails, **exactly one per side**, no teams. v1 is one machine, one camera framing the whole labyrinth, up to 4 humans, bots filling empty slots, no sockets. GDD §22's "multiplayer competition" is **met locally and not over a network in v1**; the network build moves to M1. | Every structural consequence is a simplification. N/S/E/W maps 1:1 to the four spawns, so the team-to-side assignment problem disappears (`GE-5`). First-past-the-post becomes correct by construction instead of a tension to be excused (`MR-1`). The spawn set is a single C4 orbit acting *simply transitively*, which is a stronger fairness guarantee than the eight-spawn case (`GE-6`). Four gamepads on one machine is an ordinary setup where eight was not. Two costs must be stated rather than discovered. Hot-seat removes real-time simultaneity as a separate thing to test, and it makes the whole board public to every player — which is exactly what licenses Freeze's unrestricted targeting (`FZ-2`) and exactly why that licence expires at M1 (`CD-9`, `FZ-11`). And a hot-seat Freeze victim is a person sitting in the room holding a dead controller for 20 s, which is a design constraint, not a UX detail (`FZ-8`). The simulation core stays deterministic and engine-independent so M1 is a transport swap (`HT-1`). |
| **D3** | **Junction control policy** [FORK] | **`intent_then_stop`** (rule `MV-9`). Persistent facing intent decides; a completed route to the Hub autopilots; a genuine unsteered branch **stops the snail**. Ship `intent_then_seek` behind the same flag and settle it in playtest one. | These are two different games. Stop-and-wait is a puzzle game with movement, where the pause *is* the thinking time (§5's "continuously evaluate"). Never-stop with a goal-seeking fallback is an action racer — but a fallback that steers toward the goal with no player input means the game solves the maze for the player, which contradicts §11's "solve the road faster than the opposing players". Recommend stop-and-wait; the flag costs ~20 lines. |
| **D4** | **Is §20 literal?** Do you intend to *regenerate the game from the GDD + config repeatedly*, or does §20 just mean "don't clobber my tuning"? | **[SETTLED] Not literal.** §20 means only "do not clobber my tuning". §11 collapses to: detect a saved config, ask once, apply or ignore. The schema-migration framework, the older-schema-version prompt, and the registered migration chain are **deleted** — about 3 weeks of specified work removed (`DS-11`, old §11.3, milestone M4). | The `schemaVersion` stamp is **kept** (`DS-10`). It costs one field and it is the only thing that makes a migration framework addable later without invalidating every config saved before then. Deleting the stamp would make the decision irreversible, which is a different and worse thing than deferring the work. |

**Recorded reconciliations** (these were contradictory across analyses and are now settled; do not re-litigate without changing this document):

| Question | Ruling | Rule |
|---|---|---|
| Time per tile | **0.80 s** at default speed | `MV-13` |
| Speed units | **tiles/second**; GDD's 5.0/2.0/8.0 read as world-units/s at `tileWorldSize = 4.0` | `MV-13` |
| Target match length, 16×16 | **40–90 s** | `MR-5` |
| Rock Blocker range | **Chebyshev 3** | `CD-11` |
| Simulation tick | **20 Hz fixed, integer/fixed-point only** | `SM-1` |
| Card draw | **Shuffled bag** of five card types; **Freeze is a deterministic rare slot outside the bag** | `CD-17`, `CD-18` |
| Rotate-Any target set | **own cell + 4 orthogonal neighbours** | `CD-6` |
| Own-cell targeting | **legal for CW/CCW/ANY/WILD when stationary at a node** | `CD-5` |
| Gem stacks | **max 2, single shared timer, refresh to full** | `MV-16` |
| Anti-softlock relief | **transit-graph invariant + discard valve. No pity timers.** | `AS-1..AS-4` |
| **Teams** | **None. 4 players, free-for-all, one snail per side.** GDD §2's 4v4 is withdrawn (D2) | `GE-5`, `GE-6`, `MR-1` |
| **Card 6, Freeze** | **Ships. 20 s lockout, 2% draw weight, free opponent selection** | `FZ-1`…`FZ-12` |
| **Liveness under Freeze** | P1 **split three ways**: board liveness, agency liveness, bounded denial. `AS-3`'s conclusion survives; its statement did not | `AS-1`, `AS-3` |
| **Freeze bound** | **One Freeze per victim per match**, immunity = duration. Worst-case denial 20 s + one global cooldown | `FZ-6`, `AS-1` P1c |
| **Topology-reducing mutations** | `CD-13` conditions 6–7 apply to **any non-carry-preserving mutation**, not only Rock output | `CD-13` |
| §20 handoff | **Not literal.** Detect, ask once, apply or ignore. No migration framework | D4, §11 |

---

## 1. Coordinate system, tile model, connectivity

Engine-agnostic. Everything in this section is integer arithmetic on a byte array and is unit-testable with no engine present.

### 1.1 Grid and directions

**`TM-1`** Cells are `(x, y)`, `x` increasing East, `y` increasing South, both in `[0, N)`. Index `i = y*N + x`.

**`TM-2`** Directions are a 4-bit mask. Bit order is screen-clockwise, so rotation is a bit-rotate with no lookup table.

```
N = 1  (0,-1)     E = 2  (+1, 0)     S = 4  (0,+1)     W = 8  (-1, 0)

cw (m) = ((m << 1) | (m >> 3)) & 0xF        // N->E->S->W->N
ccw(m) = ((m >> 1) | (m << 3)) & 0xF
opp(d) = ((d << 2) | (d >> 2)) & 0xF        // single-bit d only
orbit(m) = distinct[ m, cw(m), cw²(m), cw³(m) ]
```

Verification against GDD §5 verbatim: `cw(0b0101 /*N–S*/) = 0b1010 /*E–W*/`. Correct.

### 1.2 A tile is one byte

**`TM-3`** **A tile is fully described by its 4-bit opening mask. Shape and rotation are derived, never stored.** Storing `{shape, rotationIndex}` alongside a mask creates two sources of truth that desynchronise the first time a Wildcard writes an arbitrary configuration.

| mask | openings | shape | distinct rotations |
|---|---|---|---|
| 0 | — | **Rock Blocker** | 1 |
| 1, 2, 4, 8 | N / E / S / W | Dead End | 4 |
| 5, 10 | N–S, E–W | **Straight** | **2** |
| 3, 6, 12, 9 | NE, ES, SW, WN | 90-Degree (Elbow) | 4 |
| 7, 14, 13, 11 | missing W / N / E / S | T-Junction | 4 |
| 15 | N,E,S,W | **Cross** | **1** |

1 + 4 + 2 + 4 + 4 + 1 = 16. The mapping mask ↔ (shape, rotation) is a bijection. Name a T-Junction by its **missing** direction; that is the only unambiguous naming.

```
shape(m):
  p = popcount(m)
  if p == 0: ROCK ; if p == 1: DEAD_END ; if p == 3: TEE ; if p == 4: CROSS
  return (m == 5 || m == 10) ? STRAIGHT : ELBOW
```

**`TM-4`** **Rock Blocker is mask 0, not a separate type.** GDD §4's "completely blocked grid" and "no openings" are the same thing; unifying them gives every rule below exactly one code path.

**`TM-5`** Consequences that must be surfaced in the UI, because they are card-wasting traps otherwise:
- `cw(0) = 0`, `cw(15) = 15` — **rotation is a no-op on Rock and on Cross.**
- `cw(5) = ccw(5) = 10` — **on a Straight, CW and CCW are the same card.**

**`TM-6`** Full grid state:

```
mask   [N*N] : u8    // 4 bits used; authoritative
flags  [N*N] : u8    // FINISH_LOCKED | SPAWN_PAD | HAS_GEM | HAS_SLOT | ROCK_PROTECTED
version[N*N] : u16   // increments on every mutation; used for concurrency (MP-6)
```

A 16×16 board is 256 bytes of mask. The entire labyrinth fits in one packet; **replicate full state, never build a delta protocol.**

**`TM-7`** *Rendering rule.* Derive mesh yaw from the mask every time it changes (`yaw = f(mask)`); **never accumulate** (`yaw += 90`). Wildcard writes arbitrary masks and accumulated yaw drifts out of agreement with logical state.

### 1.3 Connectivity is mutual

**`TM-8`** Two orthogonally adjacent cells are **connected** iff *both* open toward each other. A one-sided opening is a wall.

```
maskAt(p)       = inBounds(p) ? mask[idx(p)] : 0        // off-grid is Rock (TM-9)
connected(a, d) = (mask[idx(a)] & d) != 0 && (maskAt(a + delta(d)) & opp(d)) != 0
usableExits(a)  = OR over d in {N,E,S,W} of (connected(a,d) ? d : 0)
```

`usableExits` is the only connectivity primitive the rest of the game needs. Mutual openness is what makes GDD §13's "rotate a shared tile to break an opponent's route" work: an opening drawn on a tile is a promise, not a guarantee.

**`TM-9`** **Border: a virtual solid ring.** Off-grid is `mask = 0`. No wrapping. **Rendering requirement:** an outward-facing opening on a border tile must be drawn **capped** — a road stub ending in a cliff or wall, never as open road. GDD §1 demands "road direction must be immediately understandable from the camera"; drawing an untraversable opening as traversable is the worst readability failure available. One instanced cap prop, not a mesh variant per shape.

**`TM-10`** Rotating a border tile is legal whenever the *mask* changes, even if effective connectivity does not — the player may be setting up a later move.

### 1.4 The transit graph (used by every reachability check in this document)

**`TM-11`** Plain 4-connectivity over non-Rock cells is **not** a sufficient reachability test, because rotation cannot make every cell carry every path shape:

| shape | straight-through | turn | can be an interior path cell? |
|---|---|---|---|
| STRAIGHT | yes | **never** | only collinear |
| ELBOW | **never** | yes | only turning |
| TEE | yes | yes | always |
| CROSS | yes | yes | always |
| **DEAD END** | **never** | **never** | **never — it is a soft rock** |
| ROCK | — | — | never |

A Dead End is a hard pass-through block that no rotation can fix; only a Wildcard retype can. Any invariant built on plain connectivity will pass boards that are actually unsolvable without a Wildcard.

**`TM-12`** **Transit graph `G_T`.** Nodes are `(cell, entryDir)`; `4N²` nodes (1024 at 16×16, 2304 at 24×24).

```
carries(c, a, b) = ∃ m ∈ orbit(mask[c]) : (m & a) && (m & b)        // a ≠ b, both single-bit
edge (v,a) --b--> (u, opp(b))   for u = v + delta(b), mask[u] ≠ 0, carries(v, a, b)
source(s) = { (s.cell, d) : ∃ m ∈ orbit(mask[s.cell]) with (m & d) }   // the snail is already on its cell
sink      = any (c, ·) with c ∈ HUB
```

`carries` depends only on **shape**, not on current orientation, which is correct: orientation is always fixable by cards, topology is not. One BFS over `G_T` answers "is this board still solvable by rotation cards alone?" in ≤ 2304 node visits. **Every reachability guarantee in this document (`MG-6`, `AS-2`, `CD-13`) is a BFS over `G_T`, not over the open-cell grid.**

---

## 2. Board geometry: centre and spawns

### 2.1 The Hub

**`GE-1`** Every map size the GDD offers (8, 12, 16, 20, 24) is **even**, so no map has a single centre cell — the centre of an N×N grid with N even is a lattice point shared by four cells. Picking one of the four arbitrarily gives half the field a permanent one-tile advantage. Therefore:

```
HUB   = { (N/2-1,N/2-1), (N/2,N/2-1), (N/2-1,N/2), (N/2,N/2) }   if N even   → 4 cells
      = { ((N-1)/2, (N-1)/2) }                                    if N odd    → 1 cell
APRON = orthogonal neighbours of HUB, outside HUB                 → 8 cells (even), 4 (odd)
```

**`GE-2`** The Hub is **one logical goal node**: all Hub cells are forced to `mask = 15`, flagged `FINISH_LOCKED`, and are **untargetable by all six cards**. Entering any Hub cell sets the snail `Finished`. Without the lock, one Rock Blocker on the centre ends the match in an unwinnable state for all four players.

**`GE-3`** Apron cells are **ordinary, contestable, rotatable, and rockable** — that chokepoint is the most interesting blocking play in the game and blanket-immunising it deletes it. The unwinnable state is prevented instead by `CD-13`: a Rock placement that would leave the Hub with **zero** non-Rock apron cells is illegal. Contest the approaches; never seal them.

**`GE-4`** The even-N Hub has 8 outward edges — **two per snail at a four-player table** — so the goal is never a physical bottleneck, and `CD-13` condition 7 has room to bind on Apron *quality* rather than on raw count.

### 2.2 Spawns

**`GE-5`** **Four spawns, exactly one per side.** `m = clamp(round(N/4), 1, N/2 - 2)`. For every preset size N is divisible by 4, so `m = 2,3,4,5,6` for N = 8,12,16,20,24.

```
S0 = (m,        0)        // North side
S1 = (N-1,      m)        // East  side
S2 = (N-1-m,  N-1)        // South side
S3 = (0,    N-1-m)        // West  side
```

Under D2 the GDD's eight spawns in two teams are withdrawn. The four surviving positions are exactly the old `{S0, S2, S4, S6}` renumbered `S0..S3`, so nothing measured about that set in §3 is invalidated. **`playerSlot` k occupies `S[k]`; the mapping side ↔ player is the identity and there is no assignment problem left to solve.**

**`GE-6`** **There are no teams.** Let `ρ(x,y) = (N-1-y, x)` (90° rotation). On slot indices `ρ: k ↦ k+1 (mod 4)`, and `{S0,S1,S2,S3}` is the **single C4 orbit of `(m,0)`**. Two consequences, which are now the entire fairness argument and are stronger than the eight-spawn version they replace:

1. `⟨ρ⟩ = C4` acts **simply transitively** on the four spawns — one orbit, exactly one group element carrying any spawn to any other. No spawn is geometrically privileged, and minimum spawn→Hub Manhattan distance is identical for all four at every preset size (4, 7, 10, 13, 16 for N = 8…24). Under D4 acting on eight spawns this was transitivity only; simple transitivity is what lets §3's layer 1 be generated **once** in a quarter-turn fundamental domain and replicated exactly, and it makes a fully C4-symmetric board — every `SolveCost` provably *equal*, not merely within `MG-11`'s ratio — available as a tournament/debug configuration at the cost of variety. It is not the default because `MG-17` layer 2 exists to keep maps interesting.
2. The spawn set is **chiral**: the mirror `μ(x,y) = (N-1-x, y)` does not preserve it, because with N even there is no exact mid-cell on a side. This is harmless and is worth stating so nobody "fixes" it. Reflection symmetry was load-bearing before only because it was what mapped Team A onto Team B; with no teams, C4 is all fairness needs.

**`GE-7`** GDD §2's arithmetic problem ("each team should have two snails positioned on opposite or strategically separated starting areas" — but each team has four snails) is **not solved, it is dissolved.** D2 withdraws the team structure outright. What survives from that requirement is the thing it was reaching for: four antipodal-in-pairs starting areas (`S0`/`S2` and `S1`/`S3` are antipodal), giving two head-to-head axes at t=0 and delivering §13's contested-intersection premise from the first second. Rejected en route: corner spawns (D4-symmetric but a corner belongs to two sides, contradicting §22's "four starting sides"); side mid-axis spawns (no mid-cell exists at even N).

**`GE-8`** **Start Pad.** Each `S[k]` is an **immutable T-Junction** open on the three non-outward directions. Identical opening state for all four, three legal first moves, no possibility of spawning inside a rock or a dead end pointing off-board. Start Pads carry `SPAWN_PAD` and are untargetable by all cards. The inward neighbour `S[k] + inward` carries `ROCK_PROTECTED` (still rotatable) so a turn-zero Rock cannot entomb anyone.

---

## 3. Map generation

The generator is a pure function of `(seed, generation-affecting settings)` and is fully testable headlessly.

### 3.1 What the guarantee must be

**`MG-1`** GDD §14's requirements ("the map is playable", "the centre is reachable", "every starting area has at least one possible route") are **not properties of the generated board**, because players rotate tiles. Checked as plain grid connectivity they reject good maps; checked as connectivity-under-rotation they pass nearly everything and guarantee nothing. Both readings are useless.

**`MG-2`** The generator instead guarantees a **bounded, fair solution cost** over the transit graph `G_T`. Define, per spawn `s`:

```
ACT[Δ] = { 0:0, 1:1000, 2:1600, 3:1000 }          // milli-card-actions for a Δ-quarter-turn;
                                                   // Δ=2 costs 1.6 because ANY does it in one card
TAU[c][a][b] = min over o of ACT[(o - ori(c)) mod 4] where MASK[shape(c)][o] ⊇ {a,b}
             = ∞ if shape(c) cannot carry {a,b}

edgeCost = TAU[v][a][b] + STEP_MILLI          STEP_MILLI = 1000 (one tile = 1 cost unit)
SolveCost(s) = shortest-path distance in G_T from source(s) to any HUB cell
             = the pair (R = card-actions, L = tiles), scalar C = 2·R + L  cost units (CU)
```

**All generator arithmetic is integer.** No floats anywhere in the cost path, so the generator is bit-identical across Windows and Android, x86 and ARM.

**`MG-3`** Because `TAU[c][a][b] == TAU[c][b][a]`, **one reverse Dijkstra from the Hub yields all four spawn costs simultaneously**, which is what makes the adaptive loop in §3.3 affordable. Bucket queue, max edge cost 2600 → sub-millisecond. The same single traversal also answers `CD-13` conditions 6 and 7 at runtime, so the legality predicate costs no new pass.

**`MG-4`** *Do not report `C` as seconds.* Card draw is random, so `C` is an idealised lower bound no player will experience. It is a **relative fairness measure**. A separate, clearly-labelled tuning estimator may be shown: `estSeconds ≈ L · tileTime + R · globalCooldown` (§10 defaults: `0.8·L + 1.5·R`).

### 3.2 Guarantees

| # | Guarantee | Check |
|---|---|---|
| **`MG-5`** | Hub forced to mask 15 + `FINISH_LOCKED`, Start Pads forced to T-Junction + `SPAWN_PAD`, before any other placement. | assertion |
| **`MG-6`** | **`SolveCost(s) < ∞` for all 4 spawns.** This is the real solvability guarantee and it collapses §14's four separate bullets into one BFS over `G_T`. | one reverse Dijkstra |
| **`MG-7`** | **Two vertex-disjoint routes** per spawn in `G_T` with `BLOCK = ROCK ∪ DEAD_END` removed. Vertex-capacitated max-flow ≥ 2 (node splitting, two BFS augmentations). | This is what survives runtime: rotation cannot remove a rock, so a spawn on one route can be cut by a single opposing card. It is also what makes `CD-13` rarely fire. |
| **`MG-8`** | `C_min ≤ C(s) ≤ C_max` per size (§3.5 table). | Dijkstra |
| **`MG-9`** | ≥2 routes within `1.25 × C(s)` that are edge-disjoint over ≥50% of their length. This is §14's "multiple possible routes", made checkable. | k-shortest paths, k=4 |
| **`MG-10`** | No non-Apron cell lies on the optimal route of more than 2 of the 4 spawns. | path union |

**Fairness invariants**, stated dimensionlessly (never in invented milliseconds):

| # | Invariant | Tolerance |
|---|---|---|
| **`MG-11`** | `max C / min C ≤ 1.15` | across the 4 spawns |
| **`MG-12`** | **Withdrawn by D2** — this was `|mean C(TeamA) − mean C(TeamB)|`. There are no teams. The number is kept as a tombstone so citations rot loudly rather than silently. | — |
| **`MG-13`** | **Withdrawn by D2** — this was the per-side A-vs-B duel bound. With one snail per side there is no intra-side pair, and `MG-11`'s ratio already bounds every pairwise gap across the single C4 orbit. | — |
| **`MG-14`** | `|R(s) − mean R| ≤ 2` card-actions | cards are the scarce resource, not just time |
| **`MG-15`** | per-spawn count of gems within a 1.5 CU detour, spread ≤ 1 | §3.4 |

With `MG-12` and `MG-13` gone, `MG-11` and `MG-14` carry the whole fairness claim. That is sound only because `GE-6`'s C4 action is *simply* transitive: every spawn is the image of every other under exactly one rotation, so a per-pair constraint would add nothing a per-orbit constraint does not already say.

### 3.3 The algorithm

**`MG-16`** Naive scatter-and-hope (GDD §14 as literally written) is not merely imperfect, it is unusable. Measured over 60 seeds per configuration on 16×16: at 6% rock density, 5 of 60 maps had at least one spawn that **could not reach the centre at all**; at 20%, 40 of 60; at 30%, 58 of 60. Worst observed spawn-cost spread was 4× between the luckiest and unluckiest spawn on the same map. In a competitive race that is the whole match, decided by the seed.

**`MG-17`** Three layers. **Symmetry is enforced only where it buys fairness, and released where it would cost variety** — a fully symmetric labyrinth is visually repetitive and lets a player read the whole map from their own quadrant, which works directly against §14's "should feel different every match".

```
Layer 1 — Spawn corridors and Hub approaches: C4-symmetric (quarter-turn).
  The 4 corridor regions (Start Pad + a radius-2 wedge) and the Apron ring are
  generated once in a quarter-turn fundamental domain and replicated by the C4
  orbit (GE-6). This is what makes MG-11 and MG-14 achievable rather than
  aspirational, and it is half the replication work the eight-spawn D4 version
  needed.

Layer 2 — Interior: free.
  type(c)        = weighted_pick(CellHash("types", c))
  ori(c)         = CellHash("orient", c) & 3
  default type weights over non-rock cells:
      STRAIGHT 26, ELBOW 32, TEE 24, CROSS 8, DEADEND 10           [TUNABLE]
  Stateless per-cell hashing, so the interior is independent of iteration order.

Layer 3 — Rocks: grown, never scattered, and validated on every accept.
  candidates = cells outside protected regions, ordered by hash
  for c in candidates:
      if mean C >= C_target or rockFraction >= rockMax: break
      grow a straight segment of length 2..4 from c in a hash-chosen direction
      tentatively set to ROCK
      if MG-6 and MG-7 still hold AND mean C did not decrease:  keep
      else:                                                     revert whole segment
```

Protected from rocks at generation **and** at runtime: `HUB ∪ APRON ∪ StartPads ∪ StartPad-inward-neighbours`.

**`MG-18`** **Dead-end repair is mandatory.** A 10% dead-end field alone seals spawns, because a Dead End is a soft rock (`TM-11`). While any spawn is disconnected in the `BLOCK`-free graph, convert the frontier dead-end nearest the Hub component (deterministic hash order) to a TEE. Repeat.

**`MG-19`** **Repair loop**, run after accretion, to close residual asymmetry:

```
for iter in 1..256:
    C, P = solveAll()                        # costs + optimal paths, one reverse Dijkstra
    if MG-11 and MG-14 hold: return OK      # MG-12, MG-13 withdrawn by D2
    hi = argmax C ; lo = argmin C
    candidates = sorted(P[hi] \ P[lo])       # cells only the slow spawn uses
    apply the single edit minimising (max C / min C), from this vocabulary:
        1. re-orient a cell          (cheapest, try first)
        2. retype ELBOW <-> TEE      (never create a DEADEND)
        3. revert one accreted rock segment
    if no edit improves the ratio: break
return REJECT -> retry with AttemptKey(i+1)
```

Constraints: repair never touches Hub/Apron/StartPads, never creates a dead end, never edits a cell on ≥3 spawns' optimal routes (prevents oscillation), and is capped at 3% of cells so the map keeps its generated character. Candidates are iterated in a fixed total order with hash tie-breaks — **never hash-map iteration order**.

**`MG-20`** **Placement search is always bounded and never fails a match start.** Collectible placement is dart-throwing against a min-distance constraint; because `count × minDistance²` can exceed board capacity (guaranteed at N=8), the relaxation ladder is: 200 darts → decrement `minDistance` by 1 → repeat to a floor of 1 → place fewer and log a Tier-B warning. Never an unbounded loop, never a silent shortfall.

### 3.4 Collectibles

**`MG-21`** GDD §18 specifies both a total (10 gems, 8 upgrades) and a Low/Med/High density with no precedence, and neither scales with area — 10 gems on 64 cells and on 576 cells are two different games. Resolution: **density is a preset that *drives* the numbers; `custom` makes the numbers authoritative** (§10.4). Medium at 16×16 reproduces the GDD's own examples exactly, so `medium` and the shipped `custom` defaults are the same configuration.

```
count = round(base × densityFactor × (N/16)²)      # Low 0.6, Med 1.0, High 1.6
gems     → round to nearest multiple of 4          # C4 quadruples
upgrades → round to nearest multiple of 4, cap 8   # C4 quadruples; 2 per snail × 4 snails
```

The upgrade cap falls from 16 to **8** under D2: 8 upgrades is exactly 2 per snail, which is the full `4 → 5 → 6` slot progression for every player at the table. More than that is unreachable capacity, not generosity, so the cap binds at N ≥ 20 and that is correct.

**`MG-22`** **Place orbits, not individual items.** Upgrades are placed as C4 quadruples (one seed cell in the quarter-turn fundamental domain, all 4 images), so each spawn is nearest to exactly one member and `MG-15` holds by construction rather than by luck. Gems are C4 quadruples, plus one deliberately **contested** orbit placed on the **diagonals**, equidistant between each adjacent pair of spawns — with one snail per side the contested ground is between neighbours, not within a side, and that is where §13's resource competition now actually happens.

**`MG-23`** GDD §9's "away from the optimal route" is unmeasurable as written ("optimal for whom?"). Define it per spawn, in CU:

```
detour(u, s) = [ min over (a,b) of  dist(source(s) → (u,a)) + TAU(u,a,b) + STEP + dist((u via b) → HUB) ] − C(s)
```

Enumerate all 12 ordered `(a,b)` pairs plus the `a == b` U-turn case (needed for gems parked in dead ends, a legitimate risk/reward placement). One forward Dijkstra per spawn plus the already-computed reverse Hub Dijkstra gives the whole field.

- **Upgrade orbits:** every spawn's nearest member must satisfy `2.0 CU ≤ detour ≤ 6.0 CU`, and the spread across the 4 spawns must be ≤ 1.0 CU.
- **Gem bands:** 40% on-route (`detour ≤ 0.5 CU`, keeps the racing line flowing), 40% near-route (`0.5–2.0`), 20% risky (`2.0–5.0`).
- **Min distance** (Manhattan) applies to four things, not the one the GDD mentions: same-type pairs (gems `max(2, N/8)`, upgrades `max(4, N/3)`), cross-type pairs ≥1, Hub/Apron ≥2, Start Pads ≥3.
- Uniformity check: partition into a 4×4 macro-grid; no macro-cell holds more than `ceil(1.75 × mean)` items, and no macro-cell that is not fully rock/Hub holds zero.

### 3.5 Defaults per map size

| N | m | Hub | min tiles spawn→Hub | `C_target` (CU) | rock % **ceiling** | gems | upgrades | gem min-dist | upg min-dist |
|---|---|---|---|---|---|---|---|---|---|
| 8 | 2 | (3,3)(4,3)(3,4)(4,4) | 4 | 11 | 12% | 4 | 4 | 2 | 2 |
| 12 | 3 | (5,5)… | 7 | 20 | 16% | 8 | 8 | 2 | 4 |
| **16** | **4** | **(7,7)(8,7)(7,8)(8,8)** | **10** | **28** | **18%** | **12** | **8** | **2** | **5** |
| 20 | 5 | (9,9)… | 13 | 35 | 20% | 20 | 8 | 3 | 7 |
| 24 | 6 | (11,11)… | 16 | 44 | 20% | 28 | 8 | 3 | 8 |

`C_min = 0.6 × C_target`, `C_max = 1.15 × C_target`. The accretion loop terminates on **whichever bound is hit first**, cost target or rock ceiling; `C_target` is set below the achievable ceiling so that it is usually the cost target, which keeps rock density from being the only lever. **These two columns are starting values to tune from playtest, not measurements to preserve.**

The generator ceiling deliberately leaves headroom under the runtime cap (`CD-13` condition 8, 35% of the board): at 16×16 that is 46 cells generated and room for ~44 player-placed rocks, against **~12 expected** in a match of the target length. That figure halves under D2 — four players drawing ~3 rocks each, not eight — so the headroom is now very generous, and condition 8 should bind essentially never.

### 3.6 Determinism and reproducibility

**`MG-24`** The map is a **pure function of `(MatchSeed, SettingsHash, GeneratorVersion)`**. Without this there is no way to reproduce a bug, replay a match, give clients the same labyrinth, or A/B two settings on the same map — and §19's export/import of tuned settings is unverifiable, because you cannot demonstrate a setting changed anything if the map changes every run.

```
RootKey           = splitmix64(MatchSeed ^ splitmix64(SettingsHash ^ GeneratorVersion · 0xA24BAED4963EE407))
AttemptKey(i)     = splitmix64(RootKey ^ 0xD1B54A32D192ED03·(i+1))
Stream(label)     = pcg32(splitmix64(RootKey ^ fnv1a64(label)))
CellHash(label,x,y) = splitmix64(RootKey ^ fnv1a64(label) ^ (x·0x9E3779B1) ^ (y << 32)) >> 32
```

- **`MatchSeed`** u64, surfaced to the player as 13-char Crockford Base32, copyable, enterable in Developer Settings to replay a map. A `fixedSeed` toggle exists for A/B tuning.
- **`SettingsHash`** covers *only* generation-affecting settings, canonicalised (fixed field order, fixed-width ints, floats quantised to milli-units). Changing Gem Boost Duration must not reshuffle the map. **Every `freeze*` key is explicitly excluded** for the same reason and by the same rule — Freeze is not generation-affecting, and a designer tuning its duration must be able to A/B it on one map.
- **`GeneratorVersion`** integer, bumped on any algorithm change. Without it, "seed 12345" means different maps across builds and every archived bug report rots.
- **Labelled stream splitting, not one sequential PRNG.** Streams: `types, orient, walls, gems, upgrades, repair`, plus one per player for cards (`Stream("cards" ^ playerIndex)`). A single stream means adding one `rng.next()` in the gem code silently reshuffles every downstream decision; a global card stream means one player's lag shifts everyone else's draws.
- **Stateless hashing for anything indexed by cell** (types, orientations); streams only for genuinely sequential processes (darts, accretion order, repair).
- **Forbidden in the generator:** wall clock, engine global RNG, dictionary/set iteration order, float accumulation.
- **`MapDigest`** = FNV-1a 64 over `(N, row-major (mask, flags), sorted collectibles, spawns)`. Compared by all participants at match start; mismatch aborts rather than desyncs. This is the only thing that makes "reproducible" verifiable rather than assumed.

---

## 4. Snail kinematics and the movement state machine

### 4.1 State

**`MV-1`** Nodes (tile centres) are the only rest positions. Movement is edge traversal between adjacent centres.

```
Snail {
  id, playerSlot                     // no `team` field — D2 withdrew teams entirely
  cell     : GridPos     // owner cell: the cell the snail departed from
  heading  : Dir         // valid while Traversing
  s        : Q16         // 0.0 at centre(cell), 1.0 at centre(cell + delta(heading))
  arrivedFrom : Dir      // direction of travel on the edge just completed
  intent   : Dir         // player-set facing; persistent; independent of traversability
  intentSelf : bool      // fifth "SELF" position of the facing control
  intentLocked : bool    // look-only: intent does not act as junction steering
  reverseLatch : bool ; reverseTimer
  v        : Q8.8        // tiles/second
  gemStacks : u8 ; gemTimer
  cards[6], slots, drawCount
  state    : MoveState
  freezeUntilTick       : u32   // absolute tick; 0 = not frozen          (FZ-1)
  freezeImmuneUntilTick : u32   // absolute tick; 0 = not immune          (FZ-6)
  freezeSubstate        : { NONE, SETTLING, HELD }                     // (FZ-4)
  freezeCasterSlot      : u8    // 0xFF = none; HUD attribution + telemetry
  freezesReceived       : u8    // per-match counter, capped by FZ-6
}

occupancy(sn) = { sn.cell }                              if s == 0
              = { sn.cell, sn.cell + delta(heading) }    if 0 < s < 1

anchor(sn)    = (s < 0.5) ? cell : cell + delta(heading)
```

**`MV-2`** A traversing snail occupies **two** cells. Every rule about "the tile a snail is on" uses `occupancy`, not `cell`. `anchor` — the nearest tile centre — is the origin for **all** card targeting and range checks; it flips at the edge midpoint, exactly when the snail visually crosses the tile boundary.

**`MV-3`** **Facing is a free, instant, zero-cost, zero-cooldown control** with five positions: N/E/S/W plus SELF. It may be changed at any time, moving or stopped, and does not require the direction to be traversable. It does two jobs — it targets tiles for cards, and it expresses route intent at junctions. To aim without steering, the player holds **Look-Only** (`intentLocked`). `intentSelf` never acts as steering.

Rendering: the snail's body follows `heading`, its eyestalks turn toward `intent`. Cheap, cute, unambiguous.

### 4.2 States

| State | Meaning | Speed |
|---|---|---|
| `Spawning` | frozen on the Start Pad until the countdown ends | 0 |
| `Traversing` | interpolating `cell → cell+delta(heading)`, `s ∈ [0,1)` | `v` |
| `AtNode` | exactly at a centre; **zero logical duration**, resolved in the same tick | — |
| `Waiting` | at a node with no chosen exit; idle animation; the player must act | 0 |
| `Recoiling` | the committed edge was invalidated ahead; returning to `cell` | `2 × baseSpeed`, fixed |
| `Frozen` | agency denied by Card 6 (`FZ-1`). Substate `SETTLING` — finishing a committed edge or recoil; or `HELD` — at a node, `s == 0` | `SETTLING`: `v` per `MV-13` with `gemStacks` forced to 0. `HELD`: **0**, and the integrator skips the snail entirely (`MP-5` step 4) rather than merely reading a zero |
| `Finished` | entered a Hub cell | — |

`Frozen` is a **state, not a flag on the card system.** A flag would need an "unless frozen" clause inside all six other states *and* inside `MP-5` steps 4, 5, 6, 7 and 8 independently — five places to drift apart. One state, dispatched once. The two substates exist because a freeze that lands mid-edge must not halt a snail at fractional `s` (`FZ-4`).

**`MV-4`** `AtNode` is **not a pause**. It exists for one tick, resolves, and the snail departs on the same tick with the leftover travel distance carried into the next edge — otherwise distance is lost and the sim is not deterministic.

**`MV-5`** Transitions:

```
Spawning  → AtNode      on race start
AtNode    → Traversing  when resolveExit returns a direction; if it is a 90° turn, v *= turnRetention
AtNode    → Waiting     when resolveExit returns NONE
AtNode    → Finished    if cell ∈ HUB
Traversing→ AtNode      when s reaches 1.0 (carry remainder)
Traversing→ Recoiling   when the committed edge is invalidated (MV-11)
Traversing→ Finished    at s ≥ 0.5 when the destination cell ∈ HUB
Recoiling → AtNode      on reaching cell, with v = 0
Waiting   → AtNode      re-evaluated whenever a mutation dirties this cell (MV-12),
                        or immediately on a Reverse input

Freeze edges (FZ-4). freezeUntilTick is stamped at the CAST tick on every path.
Traversing → Frozen(SETTLING)   on FreezeApplied
Recoiling  → Frozen(SETTLING)   on FreezeApplied   (recoil stays uninterruptible, MV-11)
AtNode     → Frozen(HELD)       on FreezeApplied   (pre-empts this tick's resolveExit)
Waiting    → Frozen(HELD)       on FreezeApplied
Frozen(SETTLING) → Frozen(HELD) on arrival at the node (or back at `cell` if recoiling); v = 0
Frozen(SETTLING) → Finished     at s ≥ 0.5 into a HUB cell — MV-5 above is unchanged
Frozen(HELD)     → AtNode       at tick ≥ freezeUntilTick; v = 0; then the normal MV-7 ladder
```

There is **no `Frozen(HELD) → Finished` edge** and no other exit from `Frozen`. A `SETTLING` snail whose committed edge ends in the Hub still finishes: Freeze cannot retroactively un-commit a finish, `CD-12` already made that destination cell untargetable so no rotation could have stopped it either, and Freeze must not be the one card that is strictly stronger than every other card in the single moment that decides the match.

### 4.3 Exit resolution

**`MV-6`** GDD §11 says snails travel automatically and the player controls facing; GDD §12 says a completed route to the centre is followed automatically. Neither says how a snail picks among three exits at a Cross. That gap makes the core loop unimplementable past the first junction, and every naive fill-in fails differently: random choice makes a competitive race arbitrary *and* desynchronises networked clients; always-straight silently ignores the player's stated control channel; always-toward-centre removes agency at the exact moment §13 designates as contested.

**`MV-7`** **Normative ladder.** No RNG anywhere.

```
resolveExit(sn):
  ex   = usableExits(sn.cell)
  back = opp(sn.arrivedFrom)
  fwd  = ex & ~back                        # U-turns excluded during normal travel

  1. if sn.reverseLatch and (ex & back):        reverseLatch = false; return back
  2. if not intentSelf and not intentLocked
        and (fwd & intent):                     return intent
  3. if routeToHubExists(sn.cell):              return firstStepOfShortestRoute(sn.cell)
  4. if popcount(fwd) == 1:                     return fwd
  5. if popcount(fwd) > 1:   [FORK MV-9]
  6. return NONE                                # → Waiting (dead end, or sealed)
```

**`MV-8`** Rule 3 is GDD §12 stated literally — *"if the road connects to the center, the snail automatically continues toward the finish"* — and it is **not** the game solving itself, because it only fires when a **complete connected route already exists** in `usableExits` (not in the transit graph). The player built that route; autopilot is the reward. `routeToHubExists` and `firstStepOfShortestRoute` come from one multi-source BFS from the Hub over `usableExits`, recomputed only on mutation (`MV-12`), never per frame. Rule 2 sits above rule 3 deliberately: a player detouring for a gem must be able to override their own finished route.

**`MV-9`** **[FORK — decision D3]** Behaviour at an unsteered branch (`popcount(fwd) > 1` and no complete route):

| `junctionPolicy` | Rule 5 | Character |
|---|---|---|
| **`intent_then_stop`** (default, recommended) | return NONE → `Waiting` | Puzzle game with movement. The pause is the thinking time. |
| `intent_then_seek` | return `argmin` over `fwd` of `distToHub[neighbour]` from a rotation-permissive BFS; ties broken by reducing the larger of `|dx|,|dy|` first, then fixed cardinal priority N > E > S > W | Action racer. Costs zero input, but an unsteered snail navigates itself. |

Both are deterministic. Ship both, settle in playtest one.

**`MV-10`** **Dead ends and U-turns.** A snail *enters* a Dead End and stops at its centre; it does not refuse entry and does not auto-reverse. Entering makes the dead end a real cost in time, which is the point of GDD §12; auto-reversing would make it free. Reverse is an **explicit latched input** (`reverseBufferTime` 1.5 s), consumed at the next node arrival or immediately when `Waiting`. Aiming backwards never reverses you — the two controls stay separate on purpose, or snails ping-pong.

**`MV-11`** **Mid-traversal invalidation.** Once `Traversing` begins, the **departure half** of the edge is committed and treated as returnable no matter what happens to `cell` — this guarantees a recoil always has somewhere to land. If `connected(cell, heading)` goes false while `0 < s < 1` (the destination was rotated shut; it cannot be rocked, see `CD-13`), the snail enters `Recoiling` and returns to `cell`. Because the anchor cell is rock-immune, this can only happen while `s < 0.5`. Recoil is uninterruptible except by `Finished`. **A snail always resolves to a tile centre, never to a vanished edge** — this single sentence is what makes the simulation total and removes the largest client/server divergence risk in the design.

**`MV-12`** **Reactive evaluation.** GDD §12 asks the game to "continuously evaluate". Do not poll per frame. On `mutate(c)`:

```
version[c]++
dirty = { c } ∪ orthogonalNeighbours(c)              # ≤ 5 cells
rebuild distToHub (one multi-source BFS from HUB over usableExits, ≤ N² cells)
for each snail in Waiting whose cell ∈ dirty: re-run resolveExit
recomputeRouteHighlight()                            # BFS reachable set + shortest path into HUB
```

**`Frozen` snails are excluded from that loop, explicitly.** Do not rely on `Waiting` and `Frozen` being different enum values: a naive implementation models a frozen snail as "`Waiting` plus a flag", and then an attacker who rotates a neighbouring tile open **launches the victim into motion mid-freeze** — a movement the freeze forbids and a free rescue the attacker did not intend. A frozen snail's single evaluation is the `Frozen(HELD) → AtNode` transition at expiry (`FZ-5`).

### 4.4 Speed

**`MV-13`** **Units are tiles/second and tiles/second².** This closes the GDD's unstated-unit gap and the resulting 7.5× disagreement about how long a tile takes.

```
targetSpeed = min( baseSpeed × classMul × (1 + boostPct/100 × gemStacks), maxSpeed )
v          += clamp(targetSpeed − v, −accel·dt, +accel·dt)
s          += v · dt                                  # s is in tiles
```

| Setting | Default (tiles/s) | GDD's number | Consequence |
|---|---|---|---|
| `baseSpeed` | **1.25** | 5.0 world-units/s at `tileWorldSize = 4.0` | **0.80 s per tile** |
| `acceleration` | 0.5 | 2.0 ÷ 4 | base→boosted in 0.5 s: a surge, not a teleport |
| `maxSpeed` | 2.0 | 8.0 ÷ 4 | hard ceiling on the *boosted* result |

The developer's stated numbers are preserved exactly; only the unit is named. `tileWorldSize` is a **rendering constant only** and never appears in the simulation.

**`MV-14`** `maxSpeed` is load-bearing at these defaults: two gem stacks give `1.25 × 1.44 = 1.80`, and a Fast-class snail (`classMul 1.15`) reaches `2.07` and is clipped to `2.00`. The cap exists precisely to stop "fast class + double gem" running away. A validation advisory (`I6`, §10.5) fires whenever `baseSpeed × 1.2 > maxSpeed`, because at that point the gem is silently a no-op while the HUD still announces "SPEED +20%".

**`MV-15`** **Momentum events.** These give disruption teeth beyond pure geometry and make route straightness a genuine optimisation target.

| Event | Effect on `v` |
|---|---|
| straight through a node | unchanged |
| 90° turn at a node | `v *= turnRetention` (0.7) |
| reverse / U-turn | `v = 0` |
| enter `Waiting` | `v = 0` |
| enter `Recoiling` | `v = 2 × baseSpeed`, fixed and ungameable |
| arrive back from `Recoiling` | `v = 0` |
| enter `Frozen(HELD)` | `v = 0` |
| exit `Frozen` | `v = 0` |

The freeze rows carry a cost that must be named rather than discovered: from `v = 0` at `acceleration` 0.5 the snail needs 2.5 s to regain `baseSpeed` 1.25, and the first tile from rest takes ~2 s. A 20 s lockout therefore has a ~2 s tail — about 10% more, not the half-second the `MV-13` boost figure might suggest. It needs no compensation, and the reason is that this is the **identical ramp** `MV-15` already imposes on every `Waiting` exit and every `Recoiling` arrival. Freeze is not being charged a new penalty; it is being charged the existing one.

**`MV-16`** **Gem stacking.** One shared timer, additive capped stacks. GDD §10 offers "max stack or refresh duration" — do both, because a single timer is what makes §16's "SPEED +20% with a countdown" literally renderable; per-stack timers would need N countdowns.

```
onPickup:      gemStacks = min(gemStacks + 1, maxGemStacks)   # default 2
               gemTimer  = gemBoostDuration                   # ALWAYS refresh to full (7.0 s)
onTimerExpire: gemStacks = 0                                  # whole stack drops together
```

HUD shows `+20%` / `+40%`. The timer runs on match time and **keeps ticking while `Waiting` or `Recoiling`** — deliberately, so being blocked burns your gem — **and pauses while `Frozen`** (`FZ-5`). The distinction is the whole justification: being blocked is a board state the victim can rotate their way out of, and burning the gem is the price of that fight. A freeze is total denial with zero counterplay, and because 20 s exceeds the boost's entire recommended band (5–10 s) a running timer would make gem destruction a *certainty*, silently welding "and also deletes the collectible you took a 2.0–5.0 CU detour for" (`MG-23`) onto a 2% card aimed by a caster who cannot see the victim's buff.

**`MV-17`** **Boost duration is a single value (default 7.0 s), not a randomised 5–10 s range.** Reasons in order of weight: (1) §16 requires a countdown, and a random duration means the player cannot learn what a gem is worth; (2) §13 makes two players race for the same gem, and they must receive the same reward or the race that decided it was meaningless; (3) in multiplayer a per-pickup roll must be server-generated and replicated — a message and a desync surface bought for zero design value. The GDD's 5–10 is preserved as the **recommended band** on the slider.

### 4.5 Snail-vs-snail

**`MV-18`** **Snails do not collide. Any number may occupy the same cell or the same edge, in either direction, passing through one another.** Rationale, in priority order:

1. Body blocking makes the entire designed blocking toolkit (Rock Blocker, rotation, §13) redundant, replaced by a cruder non-puzzle strategy: park in a corridor. That contradicts §11's "the core challenge should be: solve the road faster".
2. It creates trivially unrecoverable states — two snails deadlocked in a one-wide corridor with no reverse target.
3. Combined with Freeze it would be lethal: a frozen snail cannot move, so a body-blocking frozen snail is a 20 s wall no card placed it and no card can remove. This is reason 2 with a timer attached, and it is the single clearest argument that `MV-18` must not be relaxed "just for ice blocks". The hot-seat intuition — *the frozen snail is in the way* — is wrong here, and someone will implement it if it is not written down.
4. Edge-based movement with no collision is order-independent, therefore trivially deterministic and rollback-friendly.
5. §13 frames contested junctions as competing for *the path* (tile control), not for physical space.

Rendering: deterministic lateral offset `((id % 4) − 1.5) × 0.10` tiles perpendicular to `heading` — with four snails this is exactly one lane each; co-located snails at a node arrange on a ring by `id`. Non-controlled snails render at 85% opacity with a player-coloured rim light so overlaps stay readable.

**`MV-19`** Where snails *do* interact:
- **Pickups are exclusive, first-touch**, consumed by the first snail whose interpolated centre comes within `pickupRadius` (0.35 tiles); same-tick ties broken by lower `id`. One-shot by default (`gemRespawnSeconds` default 0 = never).
- **Anchor cells are Rock-immune** (`CD-13`) — the only sense in which a snail occupies space.
- **The Hub is non-exclusive.** Multiple snails may finish; the winner is the earliest finish, ties by lower `id`.
- **Frozen snails take no pickups** (`MP-5` step 6) and **nothing is destroyed**: the collectible stays on the board, stays contestable by everyone else for the full lockout — an opponent walking in and taking it out from under a frozen player is a real cost and a good hot-seat moment — and is acquired by the victim on the **expiry tick** by the ordinary step-6 check, because `HELD` means `s == 0` and the victim's centre is at distance 0. Denying it permanently would invent a second effect the developer never specified and the caster cannot aim.
- There is **no teammate targeting rule** any more. D2 withdrew teams; every other snail is an opponent, and the friendly-fire warning tint is deleted along with the concept.

---

## 5. Card system

### 5.1 Hand model

**`CD-1`** Slots start at 4, cap at 6 (§9, §18). **Draw-on-consume:** consuming a card (played *or* discarded) immediately draws one, so the hand is always full and `Cards: 4/4` is invariant except during the slam-in animation.

**`CD-2`** The replacement lands in the vacated slot with a **0.35 s selection lockout** on that slot, and the selection cursor auto-advances to the next non-identical card. Without this, draw-on-consume guarantees a double-tap misfire: you press slot 2 twice and the second press plays a card that materialised 80 ms earlier and you never read.

**`CD-3`** **The opening hand is fixed and identical for all players: `[ANY] [CW] [CCW] [ROCK]`** — exactly the hand §16's HUD mockup shows. Zero opening variance is correct for a symmetric competitive race; a random opening hand is a coin flip on a short match. The bag (`CD-17`) starts fresh *after* the opening hand, and **Freeze can therefore never appear in it** — the opening hand is off-bag and `CD-18`'s rare slot has an index floor of 8. No turn-zero freeze is possible and no arming timer is needed to prevent one.

**`CD-4`** **Slot upgrade:** on pickup, `maxSlots += 1` **and a card is drawn immediately into the new slot**. The GDD's own `4/4 → 5/5 → 6/6` notation asserts this; it just never says it. A slot that fills only on the next consume is a delayed reward and makes the risky detour feel bad, defeating §9's whole purpose. At 6/6, further slot collectibles are **non-interactable** — rendered inert, not consumed, left on the map for others. Prevents denial-farming and adds no new system.

### 5.2 Targeting

**`CD-5`** **Own-cell targeting is legal for CW, CCW, ANY and Wildcard, provided the snail is stationary at a node** (`s == 0`). This is an addition to GDD §7 and it is load-bearing.

Under the GDD as written, **no card can modify the tile the snail is standing on.** That is the cheapest kill in the design: a snail resting on a Dead End has exactly one exit, and one enemy card on the single adjacent tile — not even a Rock; rotating a neighbouring Straight from N–S to E–W does it, at 25% draw rate, possibly *by accident* — removes that player permanently. §12 explicitly routes players into dead ends, so the vulnerable state is designed and common. Restricting the fix to the Wildcard (the alternative proposal) gates rescue behind a 10% draw, which is removal-by-tempo rather than removal by rule.

The stationary requirement means no mid-transit rug-pull, and it keeps §8's Facing Mechanic intact as the common case.

**`CD-6`** Target sets and effects. **There are six cards.** Card 6 is Freeze (D2/D5), the only card whose target is a *snail* rather than a *cell*; its full rules are §5.4.

| Card | Draw weight | Target set | Result set | Illegal on |
|---|---|---|---|---|
| **1 Rotate Any Direction** | 24% | **own cell + all 4 orthogonal neighbours (5)** | `orbit(m) \ {m}` | ROCK, CROSS, Hub, Spawn Pad |
| **2 Rotate Clockwise** | 24% | own cell + faced cell (2) | `{ cw(m) }` | ROCK, CROSS, Hub, Spawn Pad |
| **3 Rotate Anti-Clockwise** | 24% | own cell + faced cell (2) | `{ ccw(m) }` | same |
| **4 Rock Blocker** | 16% | any cell within **Chebyshev 3** of `anchor` | `{ 0 }` | see `CD-13` |
| **5 Wildcard** | 10% | own cell + faced cell (2) | `{0..15} \ {m}`; **every non-carry-preserving output obeys `CD-13`** | Hub, Spawn Pad |
| **6 Freeze** | **2%** | **any of the 3 opponent snails, no range limit** | target becomes `Frozen` for `freezeDurationSeconds` | see `FZ-6` |

**Targeting is now typed.** `Target = Cell(GridPos) | Snail(SnailId)`. Cards 1–5 take `Cell`; Card 6 takes `Snail`. `CD-8`'s no-op rule, `CD-12`'s edge lock and `MP-6`'s `version[]` staleness check are all defined over `Cell` targets and none of them applies to Card 6; `FZ-6` is the whole legality predicate for a `Snail` target. This is one type, not a new subsystem, and naming it is what stops Freeze from being routed down the tile path — where it would be unusable against moving snails and would hand the game a degenerate counterplay ("never stop moving and you can never be frozen").

Rates are the authored weights from D5's renormalised table; `DS-7` normalises by their actual sum, and `CD-17`/`CD-18` state exactly how each becomes a physical draw.

**`CD-7`** **ANY is shape-preserving; Wildcard is not.** Formal invariant, assertable in code: `popcount(result) == popcount(before)` holds for Card 1 and fails for Card 5.

| | Rotate Any Direction | Wildcard |
|---|---|---|
| result set | the rotation orbit of the current shape | all 16 masks |
| changes number of exits | never | yes |
| creates a Rock | no | yes |
| **removes a Rock** | **no** | **yes — the only card in the game that can** |
| choices on Dead End / Elbow / T | 3 | 15 |
| choices on a Straight | **1** | 15 |
| choices on a Cross or Rock | **0 — illegal target** | 15 |
| target set | **5 cells** | 2 cells |

The alternative reading — that ANY produces any of the 16 masks — makes it strictly dominate Wildcard at ~2.4× the draw rate, contradicting §7's "the most powerful card… should be rare". **The domination is instead broken on the target axis, not the power axis:** ANY has the larger *reach*, Wildcard the larger *effect*. Neither dominates, both have a one-sentence identity, and ANY's neighbour reach is what does the anti-softlock work in §6. The GDD's stated draw rates are therefore kept unchanged.

Two emergent properties fall out and are good: **Cross tiles are hardened terrain** (immune to all three rotation cards; only Wildcard or Rock touches them, so they become contested real estate), and **Rock is permanent under rotation** (Wildcard is the only eraser — a concrete, legible reason it is the most powerful card).

**`CD-8`** **The no-op rule.** For a `Cell` target, `legal(card, cell)` requires `result != mask[cell]`. A card whose preview shows no change is an **illegal target**: confirm disabled, card not consumed. Follows directly from §8's contract, and removes the trap where a new player burns a CW card on a Cross. For a `Snail` target the analogue is `FZ-6`, and its consequence is identical and deliberate: **a refused Freeze is never consumed.**

**`CD-9`** **Rock Blocker range is Chebyshev 3** — a 7×7 diamond-free square, 48 addressable cells, 18.8% of a 16×16 board. **[TUNABLE]**

The governing rule, which is what should be written into the GDD, is: *the target must lie inside the caster's visible camera region, and therefore inside the victim's.* **A player must never be hit by a card originating outside their own screen.** Chebyshev (not Manhattan) because the constraint is a rectangular viewport. Three independent checks land on 3 at the default size: at 0.80 s/tile it is ~2.4 s of lead time (≈10× the human reaction floor, so a targeted player can see the rock land and re-route); a 7×7 window sits comfortably inside §1's camera framing; and to rock the tile in front of an opponent you must be within ~4 of that opponent, which is precisely §13's "two snails approach the same intersection" and nothing further. Cross-map sniping is structurally impossible.

**`CD-10`** **Rocks are permanent for the match.** §7's phrase "temporary strategic barriers" contradicts §4's terrain definition and is **corrected here**: a board that un-rocks itself is unplannable and unteachable, which kills §8's stated goal. Delete "temporary" from §7. State explicitly, because it is currently only inferable: **a Rock is reversible only by a Wildcard on an own or faced cell.** No `lifetimeSeconds` setting is added; §15 already defers timed blockers to future work.

**`CD-11`** **Rotation cards targeting a Rock are illegal** (greyed, not consumed), not a silent no-op. Same for Hub, Spawn Pads, and Cross (rotation only).

### 5.3 Mutation legality

**`CD-12`** **Edge lock.** While any snail has `0 < s < 1`, **both cells of its `occupancy` set are untargetable by every tile-mutating card** (ANY, CW, CCW, ROCK, WILD). Traversal is atomic: once committed to an edge, a snail always completes or recoils. Targeting shows "TARGET BUSY"; the card is not consumed. Bound: ≤2 cells per moving snail, ≤8 of 256 at a full four-player table. Not a stall exploit — snails cannot voluntarily stop mid-edge, and the lock releases on arrival (~0.8 s).

**Freeze does not touch this rule and must not.** It targets a snail, not a cell, so a snail with `0 < s < 1` is a legal Freeze target (`FZ-6`). The lock's stated bound — two cells, released on arrival — survives only because `FZ-4` never leaves a snail at fractional `s`. Halting a frozen snail mid-edge would turn an 0.8 s two-cell lock into a **20 s, two-cell, all-card immunity field placeable at unlimited range with no line of sight** — strictly stronger than Rock Blocker, available to no other card, and a route seal that `CD-13` conditions 6–7 never evaluate because no tile was mutated. `CD-12`'s own reason for not being an exploit ("snails cannot voluntarily stop mid-edge") is exactly what a mid-edge freeze would remove.

**`CD-13`** **Topology legality predicate.** A mutation at `p` is legal iff **all** applicable conditions hold. Evaluated client-side at preview time so illegal targets are greyed live, and re-evaluated authoritatively at confirm.

| # | Condition | Applies to | Failure message |
|---|---|---|---|
| 1 | `p ∉ HUB ∪ StartPads ∪ StartPad-inward-neighbours` | Rock output | TILE PROTECTED |
| 2 | `p ∉ occupancy(s)` for **every live snail**, foe or the caster's own — **explicitly including `Frozen` snails in both substates**, and including `Suspended` snails for their grace period (`MP-10`) | Rock output | TILE OCCUPIED |
| 3 | `mask[p] != 0` (no-op rule) | Rock output | NO EFFECT |
| 4 | `p` holds no Gem or Card-Slot collectible | Rock output | COLLECTIBLE HERE |
| 5 | `chebyshev(p, anchor(caster)) ≤ rockRange` | Card 4 | OUT OF RANGE |
| 6 | After the mutation, **every live snail still has a finite-cost route to the Hub in the transit graph `G_T`** — quantified over `{Spawning, Traversing, AtNode, Waiting, Recoiling, Frozen}` and over `Suspended` snails inside their grace period | **any non-carry-preserving mutation** | WOULD SEAL THE LABYRINTH |
| 7 | After the mutation, the Hub retains **≥1 Apron cell that can carry a path into the Hub in `G_T`** | **any non-carry-preserving mutation** | GOAL MUST STAY REACHABLE |
| 8 | `rockedCells + 1 ≤ rockBlocker.capFractionOfBoard × N²` | Rock output | ROCK LIMIT REACHED |

**Conditions 6 and 7 fire on *any topology-reducing mutation*, not only on Rock output.** The trigger is one predicate over the 12 ordered direction pairs:

```
carryPreserving(before, after) =
    ¬∃ (a,b) : carries(before, a, b) ∧ ¬carries(after, a, b)
evaluate conditions 6 and 7 ⟺ ¬carryPreserving(mask[p], result)
```

This closes a hole that pre-dates Freeze and that Freeze makes lethal. `CD-6` previously routed only a Wildcard's *Rock* output through this predicate — but `TM-11` states a Dead End is a soft rock carrying no direction pair, so `Wildcard → DEAD_END` (masks 1/2/4/8) removes `G_T` edges exactly as a Rock does and was checked by **nothing**. `CROSS → STRAIGHT` has the same property. Condition 6's own worked justification below names this exact case and then guarded only rocks. Today a victim rotates around a hostile Dead End or walks away; **frozen, they cannot, and the damage is permanent — only another Wildcard rewrites it** — which is a genuine permanent-removal path that `AS-3` claims is impossible. One predicate catches `Wildcard → DEAD_END`, `Wildcard → STRAIGHT` from a Cross, and `Wildcard → ROCK` together, instead of three rules.

**Rotation is exempt by construction, and this is provable rather than asserted:** ANY, CW and CCW all produce members of `orbit(m)`, and `TM-12`'s `carries()` quantifies over the whole orbit, so the carry set is invariant. 72% of all plays therefore pay nothing at runtime — the check never even runs.

Conditions 6 and 7 are the ones that make the match un-losable-by-grief. **Condition 6 must be checked over `G_T`, not over plain open-cell connectivity** — the naive version passes boards that are unsolvable without a Wildcard (a Dead End on the sole remaining corridor), and it also passes the case where a snail on a N–S Straight has its N and S neighbours rocked: still 4-connected to the Hub via E and W, still permanently immobile. Cost: one BFS over ≤2304 nodes, sharing `MG-3`'s traversal. Condition 7 as previously worded ("≥1 non-Rock Apron cell") did not do this job, because a Dead-End apron cell is non-Rock and still cannot carry a path into the Hub; reworded, condition 7 is largely subsumed by condition 6 and is retained as a cheap early-out.

Condition 2 is deliberately asymmetric with rotation and the asymmetry is one sentence to a player: ***you can turn the road under someone; you cannot drop a rock on them.*** Its extension to frozen snails is the single most dangerous silent regression available in this document. If a Rock lands on a frozen snail's own cell, that cell is mask 0, all three rotation cards are illegal on a Rock (`CD-11`), `CD-5`'s own-cell rescue evaporates, and `AS-3` step 1's premise is simply false — permanent removal, reversible only by a Wildcard the victim may never draw. **Do not relax condition 2 for a snail that "isn't using" its tile.**

Condition 8 is a safety rail, not a designed mechanic. At the target match length (`MR-5`) roughly **12** player rocks land on a 256-cell board (~5%) on top of the generator's 18% ceiling — about **23%** total, comfortably under the 35% cap. (That figure was ~24 rocks and ~27% under the withdrawn eight-player structure; D2 halves the number of hands playing them.) The cap exists so a pathological match cannot harden the board into a near-percolation state where condition 6 rejects constantly and the rejections start to feel arbitrary. **If condition 8 binds regularly, the match is too long or the Rock draw rate is too high** — fix the cause, do not raise the cap. At the cap, Rock cards render greyed (still discardable) until a Wildcard frees a cell.

**Preview UX requirement:** a Rock can be rejected because of a distant enemy snail the caster cannot see. The preview must state *which* condition failed, or players will read it as a bug. **A rejection caused by a *frozen* snail must say so by name** — the caster may have frozen that snail himself thirty seconds ago and will otherwise read a correct rejection as a defect.

**`CD-14`** **Stationary snails do not protect their tile from rotation, and neither do frozen ones.** A snail at a node may have the road rotated out from under it, by an opponent or by itself. This is the core offensive play of §13 "Route Manipulation" and must stay legal. The snail recomputes `usableExits` and may end up with none — a legal, intended, recoverable state (§6).

Keeping `CD-14` unchanged under Freeze is deliberate and is what stops the card from being a removal tool. Rotation cannot change the transit graph at all (`carries()` is a function of shape and `orbit` is rotation-invariant), so the rotation half of a freeze-and-rotate combination can only inflict **re-orientation debt**, which the victim erases at one card per 1.5 s using own-cell targeting (`CD-5`) once the lockout ends. That is the drama the card exists for, and it is bounded. The unbounded half would have been the rock half, and conditions 2, 6 and 7 above are what bound it.

**`CD-15`** **Cast time is 0 ms and the game never pauses.** §8 demands highlight → preview → confirm; §5 says the tile changes immediately on confirm; §21 demands fast gameplay. A modal confirm is unimplementable in a real-time race: you cannot freeze the world, and if you do not, the player reads a dialog while their snail drives into a wall.

**Resolution: the preview is a persistent always-on overlay, not a step.** Selecting a card is instant, free and sticky; the ghost of its effect renders continuously on the live target and updates as the snail moves and re-faces; legality is recomputed on every board mutation. "Confirm" is then the same single press that would have played the card anyway. **The confirm step costs exactly zero additional time, because the preview is what you were already looking at.** §8's promise and §21's pacing are both preserved.

The two parameterised cards (ANY, Wildcard) genuinely need a choice, so they open a radial. **The game still does not pause**; the target cell is latched on open; the default-highlighted option is the goalward heuristic so one press accepts; and if the snail leaves adjacency to the latched target, the radial auto-cancels and **the card is not consumed**.

**Freeze uses the same radial, with three positions and no new interaction verb** (`FZ-7`). Under D2 there are exactly 3 opponents, which is inside comfortable radial arity — no target list, no `Tab` cycling, no rank-ordered scrolling, and no second selection idiom for players to learn. An open radial of any kind **hard-cancels on freeze engagement** and **the card is not consumed**, reusing the existing "left adjacency to the latched target" cancel path; without that clause a 2%-draw card destroys a 10%-draw Wildcard mid-radial.

**`CD-16`** **Cooldowns** — the GDD specifies none, and without them a player empties a full hand in under half a second, mutating four tiles faster than any opponent can read the board. **[TUNABLE]**

| Action | Global CD | Card CD | Cast |
|---|---|---|---|
| Play ANY / CW / CCW / WILD | **1.5 s** | 0 | 0 ms |
| Play ROCK | 1.5 s | **6.0 s** | 0 ms |
| **Play FREEZE** | 1.5 s | **20.0 s** (`= freezeDurationSeconds`) | 0 ms |
| **Discard** (no effect, triggers a draw) | 1.5 s | **4.0 s** — *waived when the player has zero legal plays* | 0 ms |
| Change facing / select card | 0 | 0 | 0 ms |

The Freeze card cooldown is nearly inert in practice — a player rarely holds two — but it is required under `drawMode: independent` and whenever a bag boundary falls mid-hand, and without it a single caster chain-locks two different victims back to back at the 1.5 s global cooldown.

**The discard waiver reads a board predicate, not an agency predicate.** State the two separately, one line each:

```
boardLegalPlays(sn)  = plays that would be legal if sn had full agency   # the waiver's trigger
agencyDenied(sn)     = frozen(sn) ∨ cooling down                          # never the waiver's trigger
```

If Freeze is implemented as "all plays become illegal", the two collapse, the waiver reads true for the whole lockout, its cost model (`~20 discards × 4 s ≈ 80 s`) is voided, and `PR-13`'s bot policy, the HUD and `BO-2`'s telemetry all misreport a frozen player as hand-dead. With the predicates separated, `AS-2` III needs no change at all.

1.5 s × 4 ≈ 6 s to spend a hand ≈ the time to cross 7 tiles: proportionate. The 6 s Rock cooldown caps one player at 10 rocks/min and means a three-rock partial pocketing takes ≥18 s, so the victim always has time to see it and leave. The 4 s discard cooldown is what makes the discard valve safe: fishing for a Wildcard by discarding costs ~20 discards × 4 s ≈ 80 s, strictly worse than playing normally. `refillDelaySeconds` is exposed separately so burst and sustained output can be tuned independently.

**`CD-17`** **Draw is a seeded shuffled bag, not independent draws.** At the GDD's 10% Wildcard rate, `P(no Wildcard in 20 draws) = 12.2%`; two players in the same symmetric race will routinely be several Wildcards apart through nothing but variance. Streak variance in a short race is not spice, it is match-deciding noise.

```
BAG(20) = [ANY ×5, CW ×5, CCW ×5, ROCK ×3, WILD ×2]        # five card types; Freeze is not in the bag
```

- **The bag holds the five tile cards only.** Freeze is delivered by `CD-18` from a rare slot outside the bag, and its weight is excluded from the apportionment below. This is why `BAG(20)` is bit-identical to the pre-Freeze bag: nothing about the tuned tile-card feel moved.
- Composition is **largest-remainder apportionment over `bagSize`** (10/20/40, default 20), stated explicitly because the previous wording was ambiguous enough to be implemented three ways:

```
apportion(weights[1..5], bagSize):
    W        = Σ weights                       # DS-7: relative weights, normalised by their own sum
    q[c]     = weights[c] × bagSize / W        # exact rational; do NOT round here
    seats[c] = floor(q[c])
    award the (bagSize − Σ seats) remaining seats to the largest fractional parts of q,
        ties broken by fixed card-id order ANY < CW < CCW < ROCK < WILD  (never map order, MG-24)
    assert Σ seats == bagSize
    assert seats[c] ≥ 1 for every c with weights[c] > 0      # I9; Tier A if it fails
```

  At the authored `24/24/24/16/10` (W = 98) over `bagSize` 20 the quotas are `[4.898, 4.898, 4.898, 3.265, 2.041]`, floors sum to 17, and the three leftover seats go to the three `.898` remainders — `[5, 5, 5, 3, 2]`. **State the quantisation honestly rather than claiming the authored rate:** the delivered bag rates are 25/25/25/15/10 of non-Freeze draws, up to 1.0 pp from the authored weights, and that is a property of dealing 98 units of weight into 20 physical seats, not a bug. `DS-7`'s settings tab shows the normalised authored weight; the tab must also show the **realised bag rate** beside it, or the two numbers will be confused for each other.
- Each player has their **own** bag, seeded `Stream("cards" ^ playerSlot)` and advanced by `drawCount` — deterministic for replays and restores exactly on reconnect.
- **Shuffle constraints** (rejection sampling, 64 attempts, then deterministic swap-repair): WILD lands in index 4..15; ROCK–ROCK spacing ≥3, evaluated **across the bag seam**; no 3 identical ids consecutively, also across the seam.
- The resulting guarantee that makes the hand model safe: **at most 2 consecutive non-rotation draws.** Your hand can never be starved of orientation tools. `CD-18` is constrained so that this guarantee holds **verbatim and un-weakened** once Freeze is interleaved.
- `drawMode: bag | independent` is exposed so the feel can be A/B tested without a code change.

**`CD-18`** **Freeze is a deterministic rare slot outside the bag.** At `bagSize` 20 a 2% weight apportions to `0.4` seats — **floor 0, and the three leftover seats all go to the 0.8 remainders of the rotation cards.** Freeze would get zero copies: fully implemented, visible in the settings tab, and never drawn. No value in `bagSize`'s 10..40 range expresses 2% honestly either (40 gives exactly one copy = 2.5%). **The mechanism has to change, not the number.**

```
freezePeriod = round( Σ all six weights / weight[FREEZE] )      # 100 / 2 = 50 draws
per player, per super-cycle n:
    i = 8 + ( Stream("cards" ^ playerSlot).next() mod (freezePeriod − 8) )
    advance i deterministically (wrapping once within [8, freezePeriod)) to the first index
        whose immediately preceding and following BAG draws are both rotation cards
    the draw at super-cycle index i yields FREEZE; every other index yields the next bag card
```

Five properties, each of which is why this and not the alternatives:

1. **The delivered rate is exactly `1/freezePeriod` = 2.0%**, deterministic, with no streak variance on the one card where variance costs 20 s. Exactly one Freeze per 50 draws per player, never two.
2. **Every `CD-17` guarantee survives untouched**, because the bag is unmodified: composition, the WILD index window, ROCK spacing, seam evaluation. The interleaving constraint above is what preserves the ≤2-consecutive-non-rotation property, which would otherwise break the first time the token landed between a ROCK and a WILD.
3. **No new replicated state.** Reconnect and replay still reproduce from `(MatchSeed, playerSlot, drawCount)` exactly per `MP-8` — replaying `drawCount` rolls recovers both the bag index and the token index. A per-player carry ledger (the other candidate fix) would have needed seeding, a `WorldState` field, a keyframe entry and a rewritten `HT-1` statistical row for a strictly weaker result.
4. **The index floor of 8 removes the turn-one Freeze without inventing an arming timer.** `CD-3`'s opening hand is fixed and off-bag, and at `CD-16`'s 1.5 s global cooldown the 8th consume lands ≈13.5 s into the match. It is stated in the same style as the existing `WILD ∈ [4,15]` window rather than as a second parallel concept, and it is not a tunable.
5. **The renormalisation question in D5 is resolved by making it moot.** The five tile weights are apportioned among themselves; whether they read `25/25/25/15/10` or `24/24/24/16/10` changes the bag by nothing at `bagSize` 20. The authored table is D5's renormalised one because that is what the developer wrote down and what the tab must display; the bag is what it always was.

**What 2% actually means, at four players** — the number the balance conversation needs, recomputed for D2 rather than inherited from the eight-player analysis:

| Draws per player per match (`MR-5`) | 15 | 20 | 25 |
|---|---|---|---|
| P(a given player holds a Freeze) | 17% | **29%** | 41% |
| E[casts per 4-player match] | 0.67 | **1.14** | 1.62 |
| P(≥1 Freeze in the match) | 52% | **74%** | 88% |

Freeze is **rare to hold and common to suffer, and those are different rarities.** Roughly three matches in four contain one; a given player draws one about once every three or four matches. Because `MR-1` is first-past-the-post and D2's shared camera makes the standings free to read, the rational target is always the leader, so casts do not spread — they converge. That convergence, not the draw weight, is what `FZ-6`'s per-victim cap is sized against.

### 5.4 Card 6 — Freeze

**`FZ-1`** **Freeze is a snail-targeted effect, not a tile mutation.** It writes no `mask[]`, increments no `version[]`, takes no tile lock, and therefore can never be rejected `STALE` through `MP-6`'s tile path. Its entire authoritative footprint is the five `Snail` fields in `MV-1`, plus the `Frozen` `MoveState` in §4.2.

```
freezeDurationTicks = round(freeze duration × sim.tickHz)     // 20.0 s @ 20 Hz = 400
freezeImmunityTicks = round(immunity       × sim.tickHz)      // 20.0 s @ 20 Hz = 400

frozen(sn)       = tick < sn.freezeUntilTick
freezeImmune(sn) = tick < sn.freezeImmuneUntilTick
```

**Absolute deadlines, never countdowns.** A per-tick decrement is one dropped tick away from divergence and needs reconciliation on reconnect; a deadline is one `u32` that replicates verbatim inside the existing `WorldState` keyframe (`MP-1`, ~448 B — no new message type) and restores exactly under `MP-10`'s grace resume. It is also order-independent within a tick. Both tick counts are quantised once at match start from the frozen resolved config (`MP-4`) and **captured into `freezeUntilTick` at the cast tick**, so a live edit or `ConfigPatch` cannot lengthen or shorten a freeze already running — `DS-3`'s rule ("retro-editing a live timer is the classic desync bug") holds here by construction rather than by special case.

`freezesReceived` and `freezeImmuneUntilTick` are **per-match simulation state**: they live in `WorldState`, ride in `MP-10`'s reconnect keyframe, and are covered by `HT-1`'s determinism golden test. A cap that is not replicated is not a cap.

**`FZ-2`** **Targeting is free selection among the 3 opponents: not facing-limited, not range-limited, not line-of-sight-limited.** This is the developer's ruling and it is the only card in the game that breaks `CD-9`'s governing principle — *"a player must never be hit by a card originating outside their own screen."*

It does not break it **in v1**, and the reason is D2 and only D2: hot-seat means one shared camera framing the whole labyrinth, so every snail is on every player's screen by construction and there is no off-screen origin. **This licence is milestone-scoped and expires with the shared camera** (`FZ-11`).

**`FZ-3`** **What Freeze denies, exhaustively, so that nothing is decided at a call site.**

| Denied for the duration | Explicitly **not** denied |
|---|---|
| Playing a card; confirming any target; discarding; changing `intent` / `intentSelf` / `intentLocked`; latching reverse; resolving an exit; movement; picking up a gem or slot collectible | Drawing. Freeze locks *plays*, not *draws*: refills complete normally, `CD-1`'s `Cards: 4/4` invariant stays visibly true, and draw identity is deterministic from `(MatchSeed, playerSlot, drawCount)` so a mid-freeze draw replays and reconnects identically |
| — | Reading. Card-slot cursor movement, the `CD-15` preview overlay and live legality all keep working (`FZ-8`) |
| — | The victim's protection: their cell stays un-rockable (`CD-13` cond. 2) and their route stays guaranteed (`CD-13` cond. 6) |
| — | `CD-14`: the tile under a frozen snail remains rotatable by anyone. That is the counterplay axis and it stays open |

Retained across the lockout: the hand, `intent`'s value, `arrivedFrom`, `gemStacks`, slots, and the snail's place in `MP-5`'s `playerSlot` ordering.

**`FZ-4`** **A freeze landing mid-edge completes the committed edge. It never halts a snail at fractional `s`.** The victim enters `Frozen(SETTLING)`, glides to the next node centre (or back to `cell` if recoiling), and ices over **there**.

`freezeUntilTick = castTick + freezeDurationTicks` is stamped at the **cast** tick on every path, so **the settle is spent inside the lockout, never added to it.** Total denial is exactly `freezeDurationTicks` whatever the victim was doing, which is what makes the HUD countdown honest and what removes any `+ engagementLatency` term from `AS-1`'s P1c. The settle is bounded: 16 ticks (0.80 s) at base speed, at most 40 ticks (2.0 s) from a standstill at `acceleration` 0.5, at most 4 ticks for a recoil. **Assert `SETTLING` never exceeds 64 ticks.** `gemStacks` is forced to 0 for the settle so no boosted ground is banked.

Three reasons, in order of weight. It is what stops `CD-12` from becoming a 20 s two-cell immunity field (see `CD-12`). It is what preserves `MV-11`'s totality — *"a snail always resolves to a tile centre, never to a vanished edge"*, the sentence that removes the largest client/server divergence risk in the design — since a mid-edge frozen snail whose destination is rotated shut cannot execute the recoil `MV-11` guarantees. And `CD-12` already contains the answer: *"once committed to an edge, a snail always completes or recoils."* Freeze being involuntary changes **who decided**, not whether traversal is atomic.

**`FZ-5`** **Timers, decided one at a time, and the thaw contract.**

| Timer | While `Frozen` | Why |
|---|---|---|
| Gem boost `gemTimer` | **PAUSES**, stacks retained, multiplier suspended | `MV-16`. D5's ruling; the argument is there |
| Global and per-card cooldowns | **PAUSE** | D5's ruling. The honest consequence is stated rather than hidden: the victim can emerge with up to 1.5 s still to serve, so **maximum inaction is `duration + one global cooldown` = 21.5 s at defaults**, not 20 s. `AS-1` P1c and `AS-3` clause 1 both state the sum |
| Card refill / `refillDelaySeconds` | **PAUSES**; a draw already in flight completes | `FZ-3` |
| `reverseTimer` / `reverseLatch` | keeps running, therefore expires normally inside the lockout | A 1.5 s input buffer consumed 400 ticks later is not buffered input, it is a stale command that fires an unwanted U-turn (`v = 0`, `MV-15`) |
| Match clock, `hardTimeoutSeconds` (`MR-6`) | **run, no extension** | D5's ruling. `MR-6` exists to bound wall-clock; extending it per freeze reintroduces the unbounded match it was written to prevent |
| Gem `respawnSeconds`, `contestedTileLockMs` | run | world timers, not player timers |
| `freezeImmuneUntilTick` | starts at **expiry**, not at cast | `FZ-6` |

**Thaw re-derives; it never resumes a cached decision.** `Frozen(HELD) → AtNode` with `v = 0`, then the **unmodified `MV-7` ladder** on that same tick. This is neither "resume prior intent" nor "stop and await input" — it is re-evaluation against a board that up to three opponents have been mutating for 20 s. Everything the player is owed survives without a special case, because `MV-7` reads persistent state: `intent` was preserved so ladder rule 2 fires if that direction is still a usable forward exit; `arrivedFrom` was preserved so `fwd = ex & ~back` still excludes the U-turn and the snail does not spin around on release; if the intent died but a complete route now exists, rule 3 autopilots and the player collects the reward for a route they built before being frozen; and if nothing resolves, rule 6 → `Waiting`, which is the correct destination for someone who has just had 20 s of board changes happen at them.

**All input received during the lockout was dropped, never buffered.** An action that auto-fires at thaw is a zero-latency advantage no unfrozen player gets, and it would resolve a 20-second-old preview against a changed board — precisely the "you showed a preview and then applied something else" failure `MP-6` decision 1 forbids.

**`FZ-6`** **Legality, immunity, and the bound.** Evaluated at preview per `CD-15` and re-evaluated authoritatively at confirm. **On any failure the card is not consumed** — `CD-8`'s no-op rule applied to a snail target rather than to a mask, not a new principle — and the preview names the failing condition, per `CD-13`'s Preview UX requirement.

| # | Condition | Failure message |
|---|---|---|
| 1 | `target != caster` | — (never offered) |
| 2 | `target.state ∉ { Spawning, Finished }` | NOT IN THE RACE |
| 3 | `¬frozen(target)` — no stacking, no timer refresh | ALREADY FROZEN |
| 4 | `¬freezeImmune(target)` | RECENTLY FROZEN |
| 5 | `target.freezesReceived < maxFreezesReceivedPerMatch` | FREEZE CAP REACHED |
| 6 | caster is not itself frozen; global cooldown elapsed; card cooldown elapsed | — |

Condition 2 needs writing down explicitly because `MR-8` keeps finished snails rendered and spectatable, so on a shared hot-seat screen a finished snail is a visible, selectable object and a cast on one would otherwise be a silent 2% card burn. **Mid-edge targets are legal** (`0 < s < 1`) — the selector latches `snailId`, not a position, so no `version[]` staleness check is meaningful. Two casters targeting the same snail inside `contestedTileLockMs`: first by `serverReceiveIndex` wins, the loser fails condition 3 and is rejected **CONTESTED and refunded**, which is `MP-6`'s existing arbitration reached without a tile lock.

```
maxFreezesReceivedPerMatch = 1      [TUNABLE 1..3]   counted per VICTIM, not per caster
freezeImmunitySeconds      = 20.0   [TUNABLE]        default = freezeDurationSeconds
```

**The developer's proposed 3 s immunity is the right idea with the wrong number, and on its own it is a duty cycle rather than a mitigation.** 3 s buys a victim 3.75 tiles and two card plays. With three opponents chaining at the earliest legal instant it produces `20 + 3 + 20 + 3 + 20 = 66 s`, of which 60 s is lockout, inside `MR-5`'s 40–90 s band — removal by any honest reading, and in hot-seat it is a human sitting in the room watching everyone else play.

**The per-victim cap is the load-bearing fix and the immunity is the secondary rail.** Draw weight controls how often a player *holds* Freeze; all the pain is in *receiving* it, and nothing previously bounded that. The cap of 1 bounds a single victim's total lockout at `1 × freezeDurationSeconds` = **20 s absolutely**, which makes `AS-1`'s P1c a constant known before the match starts rather than an unbounded statement. At the recomputed four-player rate (`CD-18`: ~1.14 casts per match, all converging on the leader) the cap binds in roughly a third of matches at 20 draws — precisely the third in which an uncapped Freeze would take 40 s or more off one player — and costs attackers nothing in the other two thirds. The refused caster keeps the card and can spend it on whoever leads next, which spreads the effect instead of concentrating it. Immunity at `= duration` then only matters if the cap is tuned above 1, and covers same-tick simultaneous casts.

This is not a pity timer and `AS-4` does not bar it: it is a hard cap of one integer that prevents a state from being constructible, not a relief mechanism that fires after a bad state has been reached.

**`FZ-7`** **Targeting UI: a three-position radial, and no new interaction verb.** D2 leaves exactly 3 opponents, so `CD-15`'s existing radial does the whole job — the same widget ANY and Wildcard already open, at arity 3.

- Selecting the Freeze slot is instant, free and sticky, exactly as for every other card. **The game does not pause.**
- The radial's three positions are the three opponents, ordered by `playerSlot` so their screen positions are **stable across the whole match** — a player learns "left is P2" once. Do not sort by rank: a target that moves under the thumb between two presses is the single most common way to freeze the wrong snail.
- The **default-highlighted** position is the leader — the snail with the lowest cost-to-finish over `G_T`, reusing the backward Dijkstra `PR-13` already shares every 250 ms, so one press is the right press with zero additional cost. Cost-to-finish, not raw distance to Hub: a snail three tiles from the Hub behind a sealed wall is not the leader.
- A board-space **frost reticle** tracks the highlighted victim, drawn in the caster's colour and offset on `MV-18`'s lateral ring so several casters' reticles on one victim stay readable.
- Confirm is the same press that would have played the card anyway, so `CD-15`'s zero-additional-cost promise is preserved exactly.
- If the highlighted victim becomes illegal, the highlight advances to the next legal position, the illegal one greys with its `FZ-6` reason, and **confirm presses are swallowed for 250 ms** with a soft click — `CD-2`'s slot-lockout rationale applied to a moving target: never resolve a press against a target the player has not had time to read.

Rejected: a rank-ordered target rail with `Tab` cycling. That design exists to manage a long candidate list; at three candidates it is strictly more machinery, it needs a second selection idiom, and hot-seat has 2–4 humans sharing one pointer, so a pointer-only path is not acceptable either. Direct click on a snail is permitted as an *additional* path for whoever holds the mouse, never as the only one.

**`FZ-8`** **Hot-seat: the victim is locked out of the world, not out of the interface.**

D5 says "fully locked out" and does not say whether that means the world or the interface, and the two readings produce very different games. Taken as the interface, a hot-seat human sits at a dead screen for 20 s in front of a fully visible board they are forbidden to read into any decision — the worst possible version of this card in the room it is played in. **Ruling: world mutation is locked; the interface is not.** D5's phrase "no targeting" means **no target *confirmation***; this has to be said explicitly, because an implementer reading D5 alone will build the dead-screen version and be right to.

The frozen player **may** move the card cursor, watch the always-on `CD-15` preview and its live legality, and read the board and minimap. They **may not** confirm anything (the press is inert and is not buffered), and they may not change `intent` — that is a simulation field (`MV-3`) and `MV-7` rule 2 makes a facing change a queued steering decision, which is a world effect. Both boundaries are exposed: `frozenPlayerMayPreview` (presentation, `live`) and `frozenPlayerMayChangeFacing` (simulation semantics, therefore `next_match`).

Presentation is a **requirement here, not polish**, because 20 s of unexplained dead input is indistinguishable from a crash:

- The victim's HUD panel shows `FROZEN BY <caster> — 19.4`, **rendered from `freezeUntilTick − tick`, never from a view-local timer.** The victim watching a UI clock reach zero while still locked, in front of everyone, is the worst readability failure this card can produce. Same discipline `MP-7` applies to the route highlight.
- Attribution is mandatory. An anonymous lockout reads as a bug and poisons a room where the caster is sitting two feet away.
- The frozen snail carries an **ice shell that changes its silhouette** and a distinct minimap glyph — silhouette and glyph, not hue, per `PR-11`.
- Audio: a cast sting, and an audible count in the final three seconds so the victim can get their hands back on the keys.
- Locked input is **explicitly rejected with feedback**, never silently dropped, rate-limited to one response per slot per 10 ticks, or the player will mash and conclude the build hung.
- **Thaw diff:** on expiry, every tile whose `version[]` changed during the lockout pulses on `PR-3`'s existing decal layer for ~1.5 s. `TM-6` already keeps the per-cell counter, so this is a snapshot at cast and a diff at expiry — it converts 20 s of board mutation from a re-acquisition problem into one glance, and it is the highest value-per-line item in this rule.
- Do **not** desaturate or dim the victim's whole frame. Their job for 20 s is to read the board; dimming their view is the one change that makes the lockout strictly worse.

**Still open (D5's own list), recorded rather than invented:** whether Freeze is telegraphed to the victim at all. `CD-9` justifies Rock's range by lead time — *"~2.4 s of lead time, so a targeted player can see the rock land and re-route"* — and Freeze at unlimited range has none, so a wind-up of ~0.6 s (consume at press, re-check and refund on fizzle, no voluntary cancel) is the natural way to move that enforcement from the space axis to the time axis. **v1 ships with no wind-up**, because 0.6 s of extra machinery is not worth adding before playtest says the card is unfair, and because a cancellable wind-up becomes a fakeout minigame. Revisit with `BO-2`'s freeze telemetry in hand.

**`FZ-9`** **`MP-5` tick order.** Freeze **expiry is step 0**, before commands, so an unfreezing snail is an ordinary `AtNode` snail for the whole of that tick and resolves at step 5 in `playerSlot` order with everyone else: no second `resolveExit` call site to drift from `MV-7`, no extra tick of lockout, and the snail is legally targetable again from step 1 of that same tick (blocked by immunity). Because expiry is step 0 and application is step 1b, `frozen(sn) ⟺ tick < freezeUntilTick` holds exactly — a freeze cast at tick `T` locks ticks `T … T+399` and the snail acts on `T+400`. Exactly 400 ticks, no fencepost. The full amended order is in `MP-5`.

**`FZ-10`** **Bots.** Three rules, all cheap, all preventing a specific defect:

- A frozen bot is **skipped entirely** from the per-bot loop and re-enters with a **fresh** decision at expiry, never a stale one — symmetric with `FZ-5`'s no-buffering rule for humans. Without this, `PR-12` routes a frozen bot's commands through the identical pipeline, they are correctly rejected, and `MP-6` classifies rejected-illegal as *"a bug-or-cheat signal, since a correct client never sends one"* — three bots ticking at 250 ms for 20 s would emit ~240 false cheat signals per freeze. The sim also classifies a frozen actor's rejected command as reason `FROZEN`, a distinct non-cheat code.
- A bot holding Freeze targets the leader by `FZ-7`'s cost-to-finish metric, skips candidates with infinite cost (freezing an already-stuck snail wastes the rarest card in the deck), and fires only when that leader's estimated finish is within `freezeDurationSeconds + 5`. It never discards a Freeze.
- **`PR-14`'s shadow-the-leader policy explicitly does not extend to Freeze.** `PR-14` exists to force `MP-6`, `CD-12` and `CD-13` collisions with the human; Freeze exercises none of those. Extending it makes one bot a dedicated human-locker, and with bots filling most v1 slots that would be the entire play experience rather than an edge case.

**`FZ-11`** **The free-targeting licence expires at M1, and the expiry must be scheduled now.** Nothing in the code will fail at that boundary, which is exactly why it has to be written down. When `PR-1`'s per-player 11×11 follow camera returns, either Freeze acquires a range or visibility constraint — the natural value is `floor(cameraTilesVisible / 2)` = 5 — or `CD-9`'s governing rule is formally amended to exempt snail-targeted cards. **Record this as an M1 gate, not a v1 concern.** Do not let it be decided implicitly by whoever ports the camera.

**`FZ-12`** **Duration: 20.0 s ships as authored. The evidence is recorded, not overridden.** [TUNABLE, recommended band **6–10 s**]

| Measure | @ 20 s | @ 6 s | Benchmark |
|---|---|---|---|
| tiles of progress denied | **25.0** | 7.5 | one gem is worth **1.75 tiles** (`MV-16`, +20% for 7.0 s at 1.25 tiles/s) |
| × one gem | **14.3×** | 4.3× | must exceed 2 gems (3.5 tiles) to earn §7's "most powerful card" |
| vs minimum spawn→Hub distance (10 tiles, §3.5) | **2.5×** | 0.75× | |
| vs a realistic 16–24 tile route (`MR-5`) | **104–156%** | 31–47% | |
| card plays denied (at 1.5 s global CD) | **13** | 4 | match total is 15–25 plays |
| % of the victim's card economy | **53–89%** | 16–27% | |
| % of the 40–90 s target match | **22–50%** | 6.7–15% | |

`MR-5`'s length derivation has no freeze term and is incomplete with Freeze in the deck; see the amendment there. The recommended band's lower bound is not arbitrary: 6 s is `CD-16`'s own published unit — *"1.5 s × 4 ≈ 6 s to spend a hand ≈ the time to cross 7 tiles: proportionate"* — so at 6 s the card reads as one teachable sentence, **"I deleted your next hand"**, while still being 4.3× a gem and unambiguously the strongest card in the deck. The upper bound of 10 s is `MR-7`'s 5 s observe phase doubled — that phase is the only interval this document already sanctions as a tolerable period of watching without acting, which is the correct hot-seat benchmark because the victim is sitting in the room with nothing else to look at.

**How this gets settled, and it is not by argument:** run three matches at 20 s and three at 6 s on the same `MatchSeed` (`/match/fixedSeed`) in the first hot-seat session, and read `BO-2`'s `placementDelta` — how many opponents overtook the victim during the lockout. That is the only honest measure of whether one card decided the match, and it is the answer to D5's own open question.

---

## 6. Anti-softlock: the constraint set and the theorem

**`AS-1`** GDD §6 promises players "should never permanently run out of cards". As a card *count* that is trivially true under draw-on-consume and therefore protects nothing. The property that actually matters was previously stated as one sentence:

> ~~**Liveness (P1): at every instant every snail has at least one legal play, and is never unable to act for longer than one global cooldown.**~~

**P1 as written is false by design once Freeze exists, and a false invariant is worse than no invariant.** It is false for 20 s in the second clause, and ambiguous in the first — does "has at least one legal play" mean the *board* offers one, or that the *player* may make one? Left as one sentence, §12.1's liveness fuzz row asserts it every tick, fails on the first generated freeze, and is then weakened or deleted by whoever hits it first, taking the real guarantee with it. **P1 is therefore split along the axis Freeze actually cuts.**

> **P1a — Board liveness. Unconditional: every live snail, frozen or not, every tick.**
> `boardLegalPlays(sn) ≥ 1 ∨ discardValveAvailable(sn)`, where `boardLegalPlays` is evaluated **as if the snail had full agency**, and a rotation-realisable route to the Hub exists in `G_T`. Checkable on every tick *including frozen ticks*, and it is exactly the precondition that makes thaw safe. Delivered by `CD-13` conditions 2 and 6, whose quantifier **"every live snail" explicitly includes frozen snails** — that single clause is what `AS-3`'s conclusion rests on.
>
> **P1b — Agency liveness. Every snail not currently `Frozen`.**
> The snail is never unable to act for longer than one global cooldown (1.5 s). This is the old P1 with its scope named honestly.
>
> **P1c — Bounded denial. Over the match, every snail.**
> Total time any snail is denied agency for reasons other than its own cooldowns is bounded above by a constant fixed **before the match starts**:
> `freezeDurationSeconds × maxFreezesReceivedPerMatch` = **20 s at defaults**, and no single denial interval exceeds `freezeDurationSeconds + one global cooldown` = **21.5 s**.

Three notes on P1c, because each is a place the arithmetic could quietly go wrong. The `+ 1.5 s` term exists because D5 **pauses** cooldowns during the lockout, so a victim can emerge still owing part of a cooldown; state the sum rather than denying it. There is no `+ engagementLatency` term, because `FZ-4` starts the clock at the **cast** tick and spends the settle inside the lockout rather than after it. And P1c is a theorem only because `FZ-6`'s per-victim cap exists: without a cap it has no constant and degenerates into an unbounded statement dressed as a bound. **The cap and P1c land together or neither is worth writing.**

P1 previously failed under the GDD as written, in two ways, and both are still killed by the rules below. **Hand freeze:** if every card's only legal target is illegal or a no-op, nothing is consumed, so nothing is drawn, so the hand never changes — the player is a spectator holding a full 4/4 hand for the rest of the match, and the only rescue (Wildcard) is gated behind the exact mechanism that is broken. **The one-card kill:** a snail stopped on a Dead End is removed permanently by a single enemy rotation on its one open neighbour.

**`AS-2`** **Five rules restore it.** Four are stated above; they are collected here because the theorem needs all five.

| # | Rule | Kills |
|---|---|---|
| **I** | **Transit-graph invariant** (`CD-13` conditions 6–7), now firing on **any non-carry-preserving mutation** and quantified over `{Spawning, Traversing, AtNode, Waiting, Recoiling, Frozen}` | encirclement, pocketing, goal seal, map bisection, the unsolvable-corridor case plain connectivity misses, the unguarded `Wildcard → DEAD_END` retype, and encirclement of a snail that cannot object |
| **II** | **Own-cell targeting** for CW/CCW/ANY/WILD when stationary (`CD-5`), plus ANY's 5-cell reach (`CD-6`) | the one-card Dead End kill. **Available at thaw by construction**, because a `Frozen(HELD)` snail is always at a node, so `CD-5`'s `s == 0` precondition holds |
| **III** | **Discard valve** (`CD-16`): any card may be burned for no effect, triggering the normal draw; 4 s cooldown, **waived when `boardLegalPlays == 0`** | constructible dead hands; bounds inaction at one 1.5 s global cooldown. The waiver reads a *board* predicate, so a frozen player never trips it vacuously (`CD-16`) |
| **IV** | **Occupied cells are never rockable** (`CD-13` condition 2), **explicitly including `Frozen` snails** | entombment; guarantees the snail's own cell is always a non-Rock road tile, which every rotation card accepts |
| **V** | **Bounded freeze** (`FZ-6`): one Freeze per victim per match, immunity = duration | chain-freeze; converts unbounded agency denial into a constant known before the match begins |

**`AS-3`** **Theorem (No Permanent Removal, with bounded agency denial).** Under I–V, for every snail at every instant:

1. *A legal play always exists on the board.* By IV the snail's own cell is a non-Rock road tile **throughout a freeze as well as outside one**, and by II every road type accepts `ANY` on the own cell (`orbit(m) \ {m}` is non-empty for every non-Rock, non-Cross mask; on a Cross the four neighbours give ANY a target, and if all of those are also illegal, III fires with its cooldown waived). **Maximum inaction: 1.5 s unfrozen; `freezeDurationSeconds` + one global cooldown = 21.5 s at defaults when frozen** (`FZ-5` pauses cooldowns, so the two do sum).
2. *A rotation-realisable escape route always exists.* By I there is a path `P = (c₀ = snail cell, c₁, …, c_k ∈ HUB)` in the transit graph. By construction of `G_T`, each `c_i` has some orientation in its orbit carrying its (entry, exit) pair. **This step never depended on the victim being able to act** — condition 6 is a property of the board, evaluated at the *attacker's* confirm time — so it survives Freeze intact, *provided* the quantifier includes `Frozen`.
3. *Both endpoints of every edge in `P` are reachable by cards.* `c_i` is targetable as the own cell; `c_{i+1}` is targetable as the faced cell (all four tile-rotating cards) or as an ANY neighbour. **Also independent of the victim's agency**; it is a statement about the target sets in `CD-6`. Rotation cards are **72% of the authored pool** (was 75%); the walk completes, and `I11` guards the margin.
4. *(new)* *Agency returns within a constant known before the match begins.* By V, and the constant is `freezeDurationSeconds × maxFreezesReceivedPerMatch` = 20 s at defaults.

∴ **A player can be delayed. The delay is bounded: at most 20 s of enforced inaction per match, plus at most one global cooldown of tail. A player can never be removed — and can no longer be delayed *arbitrarily while unable to respond*.** ∎

Note precisely what changed and what did not. **Steps 2 and 3 needed no repair**, because both rest on board-side quantifiers — rule I's transit-graph invariant and rule IV's occupancy rule — that never referenced the victim's ability to act. That is a real strength of the original design and it is worth recording as one. Step 1 needed re-scoping and an honest bound. Step 4 is the genuinely new obligation Freeze creates. The conclusion is **stronger** than before, not weaker: "delayed arbitrarily" was a harmless admission when the practical bound on delay was contestation — the attacker mutated at one global cooldown and the victim un-mutated at the same cooldown, an even card trade the attacker paid for out of their own race. Freeze deletes the victim from that exchange for 13 global cooldowns, so what was previously bounded by contestation must now be bounded by rule.

**`AS-4`** **No pity timers, no stall amnesty, no forced Wildcards.** Timed relief mechanisms were proposed to cover the case where the guaranteed path is topologically open but not *rotation-realisable*. Using the transit graph in condition 6 removes that case by construction, so the relief mechanism is unnecessary — and it would add two tunables the GDD does not have, plus an exploit (deliberately walling yourself in to farm Wildcards) that then needs a `lastMutator` byte per tile to close.

**This ruling stands and rule V does not violate it.** A pity timer is a *conditional* relief that fires after a bad state is reached; V is a hard cap of one integer that prevents the state from being constructible, in the same family as `CD-13`'s conditions and evaluated with machinery that already exists. Also rejected, explicitly, so it is not re-proposed: a "frozen escape budget" condition capping how far a victim's shortest route may be lengthened during a lockout. It is a real concern with a cheaper answer — rule I's extension to non-carry-preserving mutations already stops the permanent-damage half, and rotation can only inflict re-orientation debt (`CD-14`), which is erasable at one card per 1.5 s. A budget would add two tunables and a second traversal to bound a quantity the existing rules already bound in kind.

**Encode `AS-3` as an integration test instead** (§12): place a snail in an adversarial pocket, drive it with rotation cards only, assert it reaches the Hub within N cards — **and run the same driver with the subject frozen for the whole window**, which is the executable form of the amended theorem.

---

## 7. Match rules

**`MR-1`** **Win condition: the first snail to enter any Hub cell wins.** Under D2 this is **correct by construction, not a compromise.**

The previous edition of this rule raised an objection — that first-past-the-post makes teammates' positions irrelevant, so the 4v4 structure contributed nothing except "don't block your own team" — and referred the tension to the developer. **The developer resolved it by withdrawing the team structure.** With 4 players free-for-all there are no teammates whose position could matter, so the objection does not need answering; it does not arise. There is no team-mode discussion left standing here and none should be reintroduced without changing D2.

Two consequences follow and both are load-bearing elsewhere:

- **Placement is a total order, 1st through 4th**, recorded as snails finish and shown on the end screen (`MR-8`). The HUD carries a placement ladder, not a team tally (`PR-2`).
- **The rational Freeze target is always the current leader**, because only the leader can beat you. Casters therefore converge rather than spread — which is not a flaw in Freeze's targeting rule but a direct consequence of this one, and it is why the bound lives in `FZ-6` rather than in the target set.

**`MR-2`** **Sub-tick finish.** Integrate motion, then detect the crossing analytically rather than snapping to tick boundaries; without this every snail crossing in the same 50 ms tick is a tie and you coin-flip constantly.

```
s_prev = sn.s ; integrate(sn, dt)
if destCell ∈ HUB and s_prev < 0.5 ≤ sn.s:
    alpha = ((0.5 − s_prev) << 16) / (sn.s − s_prev)
    finishTick_q = ((T−1) << 16) + alpha
```

**`MR-3`** **Arbitration order** (minimum over all crossers in the tick): lower `finishTick_q` → higher speed at crossing (rewards the gem play) → greater total distance travelled (rewards the harder route) → `hash(MatchSeed, snailId)`. The last step will essentially never fire but must exist: two clients disagreeing about who won is the worst bug this game can ship.

**`MR-4`** **Photo finish.** When first and second are within 200 ms, play a 1.5 s slow-motion replay from confirmed positions and display the margin in milliseconds. The "I saw myself cross first and lost" moment is inevitable at some latency; converting it into the highlight of the match is cheap.

**`MR-5`** **Match length. Target band 40–90 s at 16×16.** [TUNABLE] Derivation, so it is checkable: minimum spawn→Hub distance is 10 tiles; a realistic route with rock detours is 16–24 tiles; at 0.80 s/tile that is 13–19 s of travel, plus roughly 8–15 blocking events at 1.5–3 s each. At that length a player makes ~15–25 card plays, so a 20-card bag turns over once and yields 1–2 Wildcards — a memorable moment, which is what §7 asked for.

**The derivation needs a freeze term and is incomplete without one.** At `CD-18`'s four-player rate (~1.14 casts per match, all converging on the leader) and `FZ-6`'s cap of 1 per victim, the eventual winner absorbs roughly half the casts:

```
matchLength ≈ travel(13-19 s) + blocking(12-45 s)
              + freezeLoadOnWinner( ≈ 0.5 × E[casts] × min(cap, 1) × freezeDurationSeconds )
```

At the shipped 20 s that term is **≈11 s**, taking a 65 s median match to ~76 s — inside the band, near its top. At the recommended 6 s it is ~3 s. Without `FZ-6`'s cap it would be ~23 s and the median would leave the band entirely. **This is the arithmetic that makes the cap a match-structure rule rather than a balance preference**, and it is why the cap is not optional.

**`MR-6`** **Hard timeout, default 180 s.** [TUNABLE] The GDD gives a match no way to end other than someone winning. With rocks accumulating and four players interfering, a stall is reachable. On timeout the winner is the snail with the lowest `distToHub` over `usableExits`, ties by lowest `SolveCost`, then by **fewest cumulative frozen seconds**, then by lowest `id`. Emit the same `MatchEnd` payload.

The freeze tiebreak is free and removes an arbitrary penalty: a snail that spent 20 s frozen is systematically behind through no play of its own, and without the tiebreak Freeze becomes a scoring attack on top of a tempo attack. **The timeout itself is never deferred or extended for a running freeze.** `MR-6` exists to bound wall-clock; extending it per freeze reintroduces the unbounded match it was written to prevent. A snail `Frozen(HELD)` at the buzzer is judged from its held cell, which is always a well-defined tile centre.

**`MR-7`** **Match start sequence.** §21's core loop begins with "Observe Labyrinth" and it must exist: a **5 s pre-race phase** with the camera framed on the whole board, cards visible but locked, facing settable. Cheap, and it directly serves the stated loop.

**`MR-8`** Finished snails continue to be rendered and may be spectated; 2nd/3rd/4th placements are recorded and shown on the end screen. A finished snail is **not** a live simulation participant: it resolves no exits, runs no timers, and is **not a legal Freeze target** (`FZ-6` condition 2). Because it stays rendered and selectable on a shared screen, the preview must reject that cast **by name** rather than silently consuming the card.

---

## 8. Multiplayer authority model

Applies from milestone M1. The v1 build (decision D2) runs the identical `SimCore` through a `LocalTransport`, so nothing in this section changes v1 code — it changes which transport is plugged in.

**`MP-1`** **Server-authoritative, single total order over commands.** Not lockstep, not host-authoritative P2P.

The decisive fact is that **every tile is writable by every player, and a mis-ordered edit changes world topology for everyone.** There is no authority partition to make — the contested resource *is* the terrain, and all players contend for all of it. A peer mesh would need distributed consensus on edit ordering before any tile could change, which costs more latency and far more complexity than one machine deciding. Lockstep is more tempting than usual (tiny state, no physics, integer maths) but loses operationally: input delay equals the worst RTT across all peers, Android clients suspend and resume constantly, and both reconnect and bot substitution require injecting state no peer generated.

The usual objection to server-auth — bandwidth and per-player state — evaporates here:

| Map | Cells | Full keyframe, uncompressed |
|---|---|---|
| 16×16 | 256 | **~448 B** |
| 24×24 | 576 | **~848 B** |

Under 1 KB for the entire world. **No delta compression, no interest management, no area-of-interest culling.** Broadcast the whole world; at 20 Hz that is ~17 KB/s down per client.

**`MP-2`** **Topology:** listen-server (one player hosts) for M1; the identical binary running headless for M2. Reliable-ordered channel for commands, events and keyframes; unreliable-sequenced for snapshots.

**`MP-3`** **Simulation: 20 Hz fixed tick (`dt = 50 ms`), integer/fixed-point only.** Rendering is decoupled and interpolates between the last two authoritative states with a 2-tick (100 ms) render delay. At 0.80 s/tile there are 16 ticks per tile — nothing is gained above 20 Hz and mobile battery cost halves versus 60 Hz.

**`MP-4`** **All floats are quantised to fixed-point once, at match start**, when the resolved config is frozen. `s` is Q16 along the edge; `v` is Q8.8 tiles/s. Consequence: **client-side prediction of locomotion is lossless, not approximate** — the client computes bit-identical positions given the same topology, and reconciliation is a no-op except on the exact tick a tile changes. This is unusual and it is why this game can get away with simple netcode. Do not throw it away by using `float` for `s`.

**`MP-5`** **Deterministic tick order.**

```
0. Freeze expiry (FZ-9): for each Frozen(HELD) with tick >= freezeUntilTick:
       state = AtNode ; v = 0 ; freezeSubstate = NONE
       freezeImmuneUntilTick = tick + freezeImmunityTicks
1. Apply accepted commands, ordered by (serverReceiveIndex); mark graph dirty
   1b. FreezeApplied: state = Frozen
       substate = (Traversing | Recoiling) ? SETTLING : HELD
       freezeUntilTick = tick + freezeDurationTicks ; freezesReceived += 1
       clear reverseLatch ; suspend gem multiplier
       (a HELD entry pre-empts this tick's step 5 for that snail)
2. Rebuild distToHub if dirty (one multi-source BFS from HUB)
3. Validate every Traversing snail's committed edge → Recoiling transitions (MV-11).
   Frozen(SETTLING) is validated identically.
4. Integrate v, advance s (carry remainder across nodes).
   Frozen(SETTLING): yes.  Frozen(HELD): SKIPPED entirely — not "integrated at speed 0",
   which is a value the integrator would immediately overwrite.
5. Node arrivals, processed in playerSlot order: resolveExit → depart or Waiting.
   Frozen(SETTLING) arriving -> Frozen(HELD), v = 0, resolveExit NOT run.
6. Pickup resolution.  Frozen snails excluded (MV-19); nothing is consumed or destroyed.
7. Finish checks (MR-2).  Frozen(SETTLING) included; Frozen(HELD) cannot finish.
8. Tick gemTimer, cooldowns, refillDelay — ALL PAUSED while Frozen (FZ-5).
   reverseTimer, the match clock and hardTimeoutSeconds keep running.
```

**Expiry is step 0 for a reason.** An unfreezing snail is then an ordinary `AtNode` snail for the whole of that tick and resolves at step 5 in `playerSlot` order with everyone else. Evaluate expiry after step 5 instead and the snail misses that tick's node-arrival pass, needs its own out-of-band `resolveExit` call site — a second code path that will drift from `MV-7` — and eats an extra tick of lockout. With this ordering the predicate `frozen(sn) ⟺ tick < freezeUntilTick` holds exactly, with no fencepost at tick 400 for a replay to diverge on.

**`MP-6`** **Concurrent tile edits — first-wins with refund.** Two players confirm on the same tile within a few hundred milliseconds. The rule:

```
onCommand(cmd):
  if not legal(cmd, world):            reject ILLEGAL   ; card NOT refunded ; log
  if tile.lockUntilTick > now:         reject CONTESTED ; card REFUNDED
  if version[cell] != cmd.version:     reject STALE     ; card REFUNDED
  apply(cmd) ; version[cell]++ ; tile.lockUntilTick = now + 300 ms ; tile.lastEditor = slot
  broadcast TileChanged
```

Four decisions inside that, each load-bearing:

1. **First-wins, not both-apply-in-order.** Sequential application produces outcomes no player can parse ("I rotated it and it turned into a rock?") and it breaks the promise §8 makes: the game showed you a preview and asked you to confirm. If you show a preview and then apply something else, you lied to the player. Reject visibly instead.
2. **A 300 ms lock, not same-tick-only.** A tick is 50 ms; human simultaneity is 200–300 ms. Same-tick arbitration degenerates into *ping wins*. The lock must be ≥ human simultaneity for the rule to arbitrate the tie a human actually perceives.
3. **Contested and stale rejections refund; illegal commands do not.** Losing a Wildcard to a race you could not see is the worst feeling this game can produce. An illegal command is a bug-or-cheat signal, since a correct client never sends one.
4. **Ordering is the server's receive order. No client-claimed ticks.** Client-supplied timestamps open a spoofing channel that is strictly worse than the ping asymmetry they would fix. Ping asymmetry is real, bounded, and symmetric over a match. **If playtest shows ping actually decides races, the remedy is `commandInputDelayMs` applied uniformly to every client including the host — not client-claimed ordering.**

Player-facing explanation, one sentence: *"One tile, one change at a time — whoever commits first holds it for a moment, and everyone else gets their card back."* The HUD shows `TILE CONTESTED` naming the winner and animates the card back into its slot.

**`MP-7`** **Prediction policy.**

| Predicted locally (0 RTT) | Must round-trip (never predicted) |
|---|---|
| Snail locomotion along **confirmed** topology — exact, per `MP-4` | **Every tile mutation** |
| Camera, card selection, targeting cursor, §8 preview overlay | Card draw identity |
| Pickup VFX (buff timer starts server-stamped) | Gem buff application, slot upgrade |
| Card slot entering a greyed "committing" state | Win detection and match end |

**No tile mutation is ever applied speculatively.** Mispredicting a rotation is the most visible error this game can produce: it re-renders world geometry, invalidates the §12 route highlight, and rolling it back can strand a snail that already started down a path which never existed — a geometry pop *plus* a snail teleport. **Corollary: the §12 route highlight is computed from confirmed state only.**

Four mitigations make the round-trip feel fine: the 250 ms cast animation *is* the latency budget (at any realistic ping the result lands inside it); the ghost preview persists through the commit and either snaps solid or shatters, so failure is *readable* rather than a mispredict; movement is slow enough that 150 ms is 19% of a tile; and `simulatedCommandLatencyMs` lets you tune the feel before a socket exists.

**`MP-8`** **Card draws are server-side.** The `cards` stream and the distribution live only on the authority; clients receive the drawn id. This closes the one-field cheat (edit your local Wildcard rate to 100%) regardless of what a client's settings file says, and makes reconnect reproducible from `(MatchSeed, playerSlot, drawCount)`.

**`MP-9`** **No late join.** Joining a race in progress is a loss by definition. Lobby fill window, then start.

**`MP-10`** **Disconnect (v1 rule, deliberately minimal). The state is named `Suspended`, and the word "frozen" is reserved for Card 6.** On disconnect the snail becomes **`Suspended` and non-blocking for a 30 s grace period, then removed from the race**; the match continues. Under first-past-the-post (`MR-1`) a missing racer changes nobody else's win condition, and this needs no AI. Reconnect inside the grace period restores the snail at its suspended position with its hand intact (`Hello{matchId, token, lastAckTick}` → `Keyframe` → resume). A `Suspended` snail's cells are **not** edit-locked (`CD-13` condition 2 is waived for it), so it cannot wall a corridor forever — but it **remains inside condition 6's quantifier for the grace period**, because it can still reconnect and `AS-3` forbids removing it.

**The rename is not cosmetic.** This rule previously used the word "frozen" and stated the exact *opposite* tile rule from the one a Card 6 victim requires: a Freeze-frozen snail's cells must be rock-immune under condition 2 and counted live under condition 6, which is precisely what prevents the freeze-then-wall-them-in exploit. Two distinct states sharing one word, carrying contradictory rules about the same predicate, in a document whose entire value is that rules can be cited unambiguously, is a bug that would be implemented as one boolean by anyone reading `MP-10` and `CD-13` in the same sitting. The carve-out is now scoped to exactly what disconnect needs — condition 2 edit-locking, expiring with the grace period — and to nothing else.

**Bot substitution becomes necessary only if a win mode ships in which a missing snail changes what winning means.** Under D2's free-for-all, none does. Schedule it with such a mode or not at all.

**`MP-11`** **Host disconnect ends the match with no result recorded.** Do not build host migration — migrating a fully mutable shared world plus four RNG streams across reconnecting peers is weeks of work protecting a case that a dedicated server removes entirely.

**`MP-12`** **Settings authority.** The configuration in force for a match is the one owned by whoever creates the match. It is resolved (presets expanded, clamps applied), frozen, and sent in the match-start payload with its `configHash`; every client verifies the hash and **refuses to start on mismatch** rather than simulating divergent physics. It is used for the duration of that match and **is never written to any client's own file**. Each client's own Developer Settings tab is **read-only while a networked match is in progress**. Live-scope edits by the host are broadcast as `ConfigPatch{applyAtTick, pointer, value}` and applied **at `applyAtTick`, not on receipt**, so every simulation changes on the same step; a `next_match`-scope pointer inside a patch is a protocol error.

---

## 9. Presentation, input, and bots

Not core-model material, but each item here is load-bearing on a rule above and none of it was specified anywhere.

### 9.1 Camera

**`PR-1`** **Orthographic, fixed yaw, fixed elevation, no player rotation.** [TUNABLE: `cameraTilesVisible`, default 11] The camera follows the local snail smoothly and frames an 11×11 tile window at default zoom, auto-zooming to 15×15 when the snail is within 3 tiles of the Hub.

Fixed yaw is not a stylistic choice — it is a dependency. `CD-9`'s range rule ("never be hit by a card from outside your own screen") requires a **defined viewport in tiles**, and touch input (§9.3) breaks entirely if grid-north is not always the same screen direction.

**`PR-2`** **The minimap is required, not optional.** §16 lists it as optional. With a snail-following camera on a 16×16+ board, the minimap is the player's only view of the goal, and §5's "Where is the centre? Which route is shortest?" is unanswerable without it. It shows: own snail, the three opponents, Hub, rocks, major collectibles, and a distinct glyph for any frozen snail (`FZ-8`). In v1's hot-seat build the camera frames the whole board, so the minimap is redundant *for that build only* — do not cut it, because it becomes load-bearing again the moment `PR-1`'s follow camera returns at M1.

**The status HUD carries a placement ladder, not a team tally.** §16's mockup shows `Team A: 2/4 reached center`; **that element is deleted with the team structure** (D2). It is replaced by a four-row ladder, always in the same screen position, ordered by cost-to-finish over `G_T` while racing and by actual finish order once snails start arriving:

```
1st  P3   ......   2nd  P1  ❄ 12.4   3rd  YOU   4th  P4  ✓ finished
```

Four rows, four players, one row each — under D2 the ladder is complete, never truncated, and never scrolls. It is also the only place a hot-seat player can see *why* they are being targeted, which matters because `MR-1` makes the leader the rational Freeze victim and the ladder is what tells them they are it.

**`PR-3`** **The §12 route highlight is an overlay/decal layer drawn on top of geometry**, never a lit surface treatment — otherwise it is occluded by exactly the raised geometry it needs to show you around. It renders the reachable set plus the shortest path into the Hub, computed from confirmed state only (`MP-7`), with an **animated flow** (moving dash) rather than a colour wash.

### 9.2 Art and asset constraints

**`PR-4`** The complete asset inventory is **under 15 unique meshes**: 6 tile shapes (rock, dead-end, straight, elbow, tee, cross), Hub plaza, spawn pad, border cap, snail (one mesh, 8 colours as a material parameter), gem, card-slot prop. This is a two-week art project — *provided the constraints below are fixed before anyone opens Blender.*

**`PR-5`** **Author each shape once; rotation is engine-side** (`TM-7`). Four variants per shape is 24 meshes and a desync waiting to happen.

**`PR-6`** **The real art risk is occlusion, not modelling.** §1 asks for camera elevation so road directions are readable; at any elevation raised geometry occludes the tiles behind it, and readability is the entire game. Decisions that must exist **before** modelling: a written **tile height budget** (rocks are low mounds, not boulders; nothing on the board is taller than the snail); snails render at **fixed screen size** with a rim light; border openings are **capped** (`TM-9`).

**`PR-7`** Pipeline: no textures — **vertex colours plus one flat/unlit material driven by a single palette resource**, so the whole game re-colours from one file (which you will do repeatedly while chasing readability). One `MultiMesh`-style instanced draw per tile shape (6 draw calls), not N² scene nodes. Establish the axis convention once in a `tile_template` file: 1×1 tile at origin, snapped, road surface at fixed height.

**`PR-8`** **Blender does not appear in v1 at all.** v1 uses primitives with flat colours and one directional light. Modelling cute snails before the mechanic is proven is the most seductive available way to lose a month, and §1 is precisely the section that will invite it.

### 9.3 Input and accessibility

**`PR-9`** The design needs three simultaneous inputs: set facing (persistent 5-way incl. SELF), select a card (1 of 4–6), and target-and-confirm (own / faced / free cursor within range for Rock).

**Mouse + keyboard, v1:** arrows or WASD for facing, `Q` for SELF, `1`–`6` for card, hold `Shift` for Look-Only, click for the Rock cursor, click or `Space` to confirm, `R` for reverse latch.

**D2's hot-seat build needs up to four independent devices on one machine**, which is the practical reason 4 players is buildable where 8 was not: one keyboard-and-mouse seat plus three gamepads is an ordinary living-room setup. Two consequences must be designed for rather than discovered. **Every selection path must be reachable without the pointer** — there is one mouse and up to four humans, so the Rock cursor and `FZ-7`'s freeze radial both need a full stick/d-pad path, with click permitted only as an *extra* for whoever holds the mouse. And **input must be rejected with feedback, never silently dropped**, for a player whose snail is frozen or whose device is unassigned (`FZ-8`); a person in the room with a dead controller and no explanation concludes the build has hung.

**`PR-10`** **v1 is desktop mouse+keyboard only.** Touch is a second design pass, not a port. Three unsolved problems, named so they are not rediscovered late: isometric + 4-way facing means screen-up is not grid-north (mitigated but not solved by `PR-1`'s locked yaw); the Rock cursor needs precision over ~48 tiles amid snails and HUD, requiring tile-snap plus a confirm step that conflicts with `CD-15`'s "confirm *is* the play input"; and Look-Only is a held modifier, the exact interaction that breaks on a phone. The configured Android export makes touch **cheap later**; it is not a reason to target it now.

**`PR-11`** **Accessibility minimums for v1**, because colour is currently the only channel for player identity, route highlight, card type, pickup type, frozen state, and "which snail is mine", and ~8% of male players have a colour-vision deficiency:

| Requirement | Cost |
|---|---|
| Player identity carried by a **silhouette badge**, not hue (four players, four badges) | free |
| **Frozen** state carried by a **changed silhouette** (ice shell) and a minimap **glyph**, never by a hue shift or a desaturation of the whole frame (`FZ-8`) | free |
| Freeze VFX must not exceed **2 Hz** over more than 25% of screen area — the photosensitivity threshold is 3 Hz and it is a ceiling, not a target. A 20 s effect is the longest-running VFX in the game and the one most likely to breach it | free |
| Countdown numerals legible at **hot-seat viewing distance (2–3 m, not 60 cm)**: ≥3.5% of screen height, plus the shrinking ring, plus audio — three channels, not one | free |
| The local player's snail gets a **persistent screen-space marker** | free |
| Route highlight uses **animated flow**, not colour wash (`PR-3`) | free |
| Card slots keep **text glyphs** — `[CW][CCW][ANY][ROCK][FREEZE]` is the GDD's own mockup extended by one and it is the accessible design; do not replace it with pretty icons | free |
| **Reduce camera motion** option: snap-follow, no auto-zoom | ~1 h |
| **Positional audio for tile mutations** — three sounds (rotate / rock / wildcard). **This is not polish.** `CD-9`'s range rule is "never hit from outside your own screen"; audio is the feedback channel that covers the cases where that fails, and without it §13's interference is illegible when it happens off-camera. | ~2 h |
| An **optional flat 2D schematic overlay** — reading tile orientation is a visual-acuity task and it is the whole game. This overlay is also the cheapest possible v1 renderer (§14). | reused from build step 3 |

### 9.4 Bots

**`PR-12`** Bots emit `Command` structs through the identical pipeline as humans — same legality checks, same cooldowns, same contest rules, same refunds. **No exceptions.** A bot that mutates the world directly implicitly wins every contest and makes the simulation unreusable for netplay.

**`PR-13`** **v1 bots are deliberately shallow.** The full planner (state space `(cell, entryDir)`, `4N²` nodes, per-tile card-cost model) is a week-plus of work and is not a v1 problem. v1:

```
shared, once per 250 ms, time-sliced at ~1.5 ms/frame, for ALL bots:
    one backward Dijkstra from the Hub over G_T  ->  D[cell][entryDir]
per bot, every 250 ms:
    if a legal exit reduces D: face it
    if blocked or D is infinite: play the cheapest card that reduces D on own or faced cell
    reaction delay before acting: Easy 900 ms / Medium 450 ms / Hard 150 ms
```

**Degrade difficulty by reaction delay, never by planning worse** — a bot that plans badly wanders and reads as broken, which misleads you about pacing.

**`PR-14`** **One bot runs a "shadow the leader" policy**: it preferentially targets tiles within 3 of the human's snail. Without this, bots rarely happen to contest the human's tiles and v1 never exercises `MP-6`, `CD-12` or `CD-13` — the rules most likely to be wrong. Force the collisions you need to observe.

---

## 10. Developer Settings

### 10.1 Two artifacts, one schema

**`DS-1`** There is **one schema**, materialised as two files with different owners and lifetimes.

| | **Runtime config** | **Exported handoff artifact** |
|---|---|---|
| Path | `user://devsettings.json` (per machine, per user) | `<repo>/config/devsettings.json` |
| Written by | Settings tab → **Save** | Settings tab → **Export** |
| Read by | game at boot; falls back to built-in defaults if absent | **AI build agent (§11)**, other developers, CI |
| In version control | no | **yes — it is the deliverable** |
| Mutated by the build agent | never (the agent must not touch the user data dir at all) | **never written; read-only input** |

The agent reading only `<repo>/config/` is what makes §20 checkable: "did the agent honour tuned settings?" is answerable by diffing one tracked file. If the agent could reach into per-machine storage, the protocol would depend on invisible state.

**`DS-2`** Sibling files the **build** writes, regenerated every build, none of them tuning state: `config/devsettings.defaults.json` (this build's defaults, so a human can diff tuned-vs-default without running the game), `config/devsettings.schema.json` (JSON Schema 2020-12 carrying every description, range, recommended band, and apply-scope — **all annotation lives here**, so the config file itself stays strict JSON that any tool can parse), and `build/config-handoff.json` (§11.5).

### 10.2 The schema

Strict JSON. 54 hashed parameters (everything except `schemaVersion` and `meta`). The eight added since the first edition are the `freeze*` keys required by Card 6; `schemaVersion` is bumped to 2 to record the addition, and per D4 **no registered migration is authored for it** (`DS-11`).

```json
{
  "schemaVersion": 2,
  "meta": {
    "profileName": "default",
    "savedAtUtc": "2026-08-19T00:00:00Z",
    "savedByTool": "devsettings-ui 1.0.0",
    "gameBuildId": "unset",
    "generatorVersion": 1,
    "notes": ""
  },
  "sim": {
    "tickHz": 20,
    "junctionPolicy": "intent_then_stop",
    "simulatedCommandLatencyMs": 0,
    "commandInputDelayMs": 0,
    "contestedTileLockMs": 300,
    "frozenPlayerMayChangeFacing": false
  },
  "map": {
    "sizePreset": "16x16",
    "gridWidth": 16,
    "gridHeight": 16,
    "rockFractionCeiling": 0.18,
    "typeWeights": {
      "straight": 26,
      "elbow": 32,
      "tee": 24,
      "cross": 8,
      "deadEnd": 10
    },
    "solveCostTarget": 28,
    "fairnessMaxRatio": 1.15,
    "repairEditBudget": 256
  },
  "gems": {
    "scatterDensity": "custom",
    "totalGems": 12,
    "minSpacingTiles": 2,
    "boostSpeedPercent": 20.0,
    "boostDurationSeconds": 7.0,
    "maxStacks": 2,
    "respawnSeconds": 0.0
  },
  "cardCollectibles": {
    "scatterDensity": "custom",
    "total": 8,
    "minSpacingTiles": 5,
    "minDetourCostUnits": 2.0,
    "maxDetourCostUnits": 6.0,
    "slotsGrantedPerPickup": 1,
    "pickupAtMaxSlots": "refuse_and_persist"
  },
  "snail": {
    "baseSpeedTilesPerSec": 1.25,
    "accelerationTilesPerSec2": 0.5,
    "maxSpeedTilesPerSec": 2.0,
    "turnRetention": 0.7,
    "recoilSpeedMultiplier": 2.0,
    "reverseBufferSeconds": 1.5,
    "pickupRadiusTiles": 0.35,
    "startingCardSlots": 4,
    "maxCardSlots": 6
  },
  "snailClassOverrides": {},
  "cards": {
    "distribution": {
      "rotateAnyDirection": 24.0,
      "rotateClockwise": 24.0,
      "rotateAntiClockwise": 24.0,
      "rockBlocker": 16.0,
      "wildcard": 10.0,
      "freeze": 2.0
    },
    "distributionLocks": {
      "rotateAnyDirection": false,
      "rotateClockwise": false,
      "rotateAntiClockwise": false,
      "rockBlocker": false,
      "wildcard": false,
      "freeze": false
    },
    "drawMode": "bag",
    "bagSize": 20,
    "openingHand": ["ANY", "CW", "CCW", "ROCK"],
    "globalCooldownSeconds": 1.5,
    "rockCardCooldownSeconds": 6.0,
    "discardCooldownSeconds": 4.0,
    "freezeCardCooldownSeconds": 20.0,
    "freezeDurationSeconds": 20.0,
    "freezeImmunitySeconds": 20.0,
    "maxFreezesReceivedPerMatch": 1,
    "refillDelaySeconds": 0.0,
    "slotSelectionLockoutSeconds": 0.35
  },
  "rockBlocker": {
    "rangeChebyshev": 3,
    "capFractionOfBoard": 0.35,
    "forbidOnCollectibles": true,
    "requireOpenApron": true,
    "requireTransitRouteForAllSnails": true
  },
  "match": {
    "targetDurationSecondsMin": 40,
    "targetDurationSecondsMax": 90,
    "hardTimeoutSeconds": 180,
    "preRaceObserveSeconds": 5.0,
    "mapSeed": null,
    "drawSeed": null,
    "fixedSeed": false
  },
  "presentation": {
    "cameraTilesVisible": 11,
    "reduceCameraMotion": false,
    "schematicOverlay": false,
    "junctionGhostChevron": true,
    "frozenPlayerMayPreview": true
  }
}
```

### 10.3 Ranges and apply scope

**`DS-3`** Every field carries an `applyScope`: `live` (takes effect immediately in the running match) or `next_match` (editable any time; the tab shows "applies next match").

| Pointer | Type | Default | Hard range | Recommended | Scope |
|---|---|---|---|---|---|
| `/schemaVersion` | int | 2 | 1..CURRENT | — | — |
| `/sim/tickHz` | int | 20 | 10..60 | 20 | next_match |
| `/sim/frozenPlayerMayChangeFacing` | bool | false | — | false | **next_match** — `intent` is a simulation field (`MV-3`), so this changes sim semantics |
| `/sim/junctionPolicy` | enum | `intent_then_stop` | `intent_then_stop`\|`intent_then_seek` | — | next_match |
| `/sim/simulatedCommandLatencyMs` | int | 0 | 0..500 | 0/60/120/250 | live |
| `/sim/contestedTileLockMs` | int | 300 | 50..1000 | 250..400 | live |
| `/map/sizePreset` | enum | `16x16` | 8x8\|12x12\|16x16\|20x20\|24x24\|custom | — | next_match |
| `/map/gridWidth`, `/gridHeight` | int | 16 | 8..32 | 8..24 | next_match |
| `/map/rockFractionCeiling` | float | 0.18 | 0..0.30 | 0.10..0.22 | next_match |
| `/map/typeWeights/*` | int | see §10.2 | 0..100 | — | next_match |
| `/map/solveCostTarget` | int | 28 | 4..200 | per §3.5 | next_match |
| `/map/fairnessMaxRatio` | float | 1.15 | 1.00..2.00 | 1.10..1.25 | next_match |
| `/gems/totalGems` | int | 12 | 0..⌊playable×0.15⌋ | 4..20 | next_match |
| `/gems/minSpacingTiles` | int | 2 | 1..8 | 2..5 | next_match |
| `/gems/boostSpeedPercent` | float | 20.0 | 0..200 | 10..40 | **live** |
| `/gems/boostDurationSeconds` | float | 7.0 | 0.5..60 | **5..10** | **live** |
| `/gems/maxStacks` | int | 2 | 1..5 | 1..3 | **live** |
| `/gems/respawnSeconds` | float | 0.0 | 0..300 | 0 or 15..60 | live |
| `/cardCollectibles/total` | int | 8 | 0..**8** | 4..8 | next_match |
| `/cardCollectibles/minDetourCostUnits` | float | 2.0 | 0..20 | 1..4 | next_match |
| `/cardCollectibles/slotsGrantedPerPickup` | int | 1 | 1..2 | 1 | live |
| `/cardCollectibles/pickupAtMaxSlots` | enum | `refuse_and_persist` | `refuse_and_persist`\|`consume_no_effect` | — | live |
| `/snail/baseSpeedTilesPerSec` | float | 1.25 | 0.1..8.0 | 0.8..2.0 | **live** |
| `/snail/accelerationTilesPerSec2` | float | 0.5 | 0.05..12.0 | 0.25..1.5 | **live** |
| `/snail/maxSpeedTilesPerSec` | float | 2.0 | 0.1..12.0 | ≥ base×1.2 | **live** |
| `/snail/turnRetention` | float | 0.7 | 0.1..1.0 | 0.6..0.9 | live |
| `/snail/startingCardSlots` | int | 4 | 1..6 | 3..4 | next_match |
| `/snail/maxCardSlots` | int | 6 | 1..**6** | 6 | **split** — see `I2` |
| `/cards/distribution/*` | float | see §10.2 | 0..100 each | — | **live** (next draw only) |
| `/cards/drawMode` | enum | `bag` | `bag`\|`independent` | `bag` | next_match |
| `/cards/bagSize` | int | 20 | 10..40 | 20 | next_match |
| `/cards/globalCooldownSeconds` | float | 1.5 | 0..10 | 1.0..2.5 | **live** |
| `/cards/rockCardCooldownSeconds` | float | 6.0 | 0..60 | 4..10 | **live** |
| `/cards/discardCooldownSeconds` | float | 4.0 | 0..60 | 3..8 | **live** |
| `/cards/freezeCardCooldownSeconds` | float | 20.0 | 0..60 | ≥ duration | **live** |
| `/cards/freezeDurationSeconds` | float | **20.0** | 0.5..60 | **6..10** (`I10` fires at 20) | **live**, captured at cast |
| `/cards/freezeImmunitySeconds` | float | 20.0 | 0..60 | ≥ duration (`I12`) | **live**, captured at expiry |
| `/cards/maxFreezesReceivedPerMatch` | int | **1** | 1..3 | 1 | next_match |
| `/rockBlocker/rangeChebyshev` | int | 3 | 1..12 | 2..4 | **live** |
| `/rockBlocker/capFractionOfBoard` | float | 0.35 | 0.05..0.80 | 0.30..0.45 | live |
| `/match/hardTimeoutSeconds` | int | 180 | 30..1800 | 120..300 | next_match |
| `/match/mapSeed`, `/drawSeed` | int64\|null | null | any | — | next_match |
| `/presentation/*` | — | see §10.2 | — | — | live |

`/snail/maxCardSlots` is **split-scope**: **raising is live** (new empty slots appear and fill on the next draw); **lowering is `next_match`**, because dropping below a snail's filled count would discard cards mid-race and hand a player a silent disadvantage. The tab greys the down-arrow with "reduce takes effect next match".

Note `/gems/boostSpeedPercent` and `/boostDurationSeconds` are `live` **for boosts started after the change**; an already-running boost keeps the values captured at its pickup. Retro-editing a live timer is the classic desync bug.

`/cards/freezeDurationSeconds` and `/freezeImmunitySeconds` follow the identical rule for the identical reason, and here "live" is **exact rather than approximate**: `FZ-1` stores an absolute deadline captured at the cast tick, so a running freeze is untouchable by construction rather than by a special case in the editor.

`/cards/maxFreezesReceivedPerMatch` is `next_match` because `freezesReceived` is per-match simulation state; lowering the cap mid-match would retroactively invalidate a freeze already served.

### 10.4 Density presets resolve the triple control

**`DS-4`** §18 gives three independent controls for one outcome (total, density enum, min distance) with no stated relationship, so a designer setting Total 10 + Density High authors a number the generator either ignores or silently multiplies. Rule: **`scatterDensity` is a preset that *drives* `total` and `minSpacingTiles`; the value `custom` makes the numeric fields authoritative.** When the density is not `custom`, the derived numbers are **rewritten into the file on save**, so the file never contains a stale number the generator ignores.

| Density | gems total | gem spacing | collectibles total | collectible spacing |
|---|---|---|---|---|
| low | ⌈cells/64⌉ (4 @16×16) | 5 | ⌈cells/128⌉ (2) | 8 |
| **medium** | **⌈cells/26⌉ (10 @16×16)** | **3** | **⌈cells/32⌉ (8)** | **5** |
| high | ⌈cells/13⌉ (20) | 2 | `min(8, ⌈cells/21⌉)` (**8** @16×16) | 3 |

The collectible column is capped at 8 under D2 (`MG-21`): 8 upgrades is exactly 2 per snail across a four-player table, which is the full `4 → 5 → 6` slot progression for everyone. `high` therefore differs from `medium` in gem density only, and that is correct rather than a rounding accident.

Medium at 16×16 reproduces the GDD's own examples (10 gems, 8 collectibles) exactly, so `medium` and the shipped custom defaults are close to the same configuration by construction.

### 10.5 Validation

**`DS-5`** Three tiers.

| Tier | Trigger | In game | Build agent |
|---|---|---|---|
| **A — Structural** | unparseable; missing required key; wrong type; unknown enum; `schemaVersion` absent or ≠ build's (`DS-11`: no migration in either direction) | **Reject the whole file.** Keep the in-memory config. Modal error naming the JSON pointer. **Never partially apply.** | **HALT.** Exit non-zero. **Never fall back to defaults silently** — that is indistinguishable from the developer choosing "Use Default Settings", which they did not. |
| **B — Out of hard range** | numeric outside `[min,max]`; cross-field invariant violated | **Clamp to the nearest bound**, warn with `{pointer, given, applied, rule}`, amber row. Match still starts. | Clamp identically; every clamp is listed in the handoff record and echoed in the prompt. |
| **C — Advisory** | in hard range, outside recommended band; soft interaction warning | Accept as authored; amber "!" with an explanation. | Accept; logged, not prompted. |

Unknown keys at the same schema version are **preserved verbatim** on load and re-written on save (round-trip safe) with a Tier-C advisory. Dropping them is silent data loss.

**Cross-field invariants:**

| # | Rule | On violation |
|---|---|---|
| `I1` | `maxSpeed ≥ baseSpeed` | clamp `maxSpeed = baseSpeed` (B) |
| `I2` | `1 ≤ startingCardSlots ≤ maxCardSlots ≤ 6` | clamp (B) |
| `I3` | `sum(cards.distribution) > 0` | **Tier A.** A zero-sum deck cannot draw, which breaks §6 outright and normalisation cannot fix it. |
| `I4` | collectible counts placeable at the given spacing | relaxation ladder `MG-20`, then Tier B. **The generator never loops unbounded and never fails a match start.** |
| `I5` | `gems + collectibles + spawns + Hub ≤ playable × 0.35` | Tier C |
| `I6` | `baseSpeed × (1 + boostPct/100) ≤ maxSpeed` | **Tier C with concrete text**: *"Gem boost has no effect: 1.25 × 1.20 = 1.50 but Maximum Speed is 1.40. The HUD will still show SPEED +20%."* This is the interaction that silently neuters §10's headline collectible from a field in a different settings group. |
| `I7` | `rockBlocker.capFractionOfBoard > map.rockFractionCeiling` | clamp cap to `ceiling + 0.10` (B) |
| `I8` | duplicate legacy `/cardCollectibles/maximumCardSlots` present | **take `/snail/maxCardSlots`**, Tier B naming both values and the winner. Never average or take the minimum silently — a designer who set 5 in one place and 6 in the other has an intent that must be surfaced. |
| `I9` | `drawMode == "bag"` and any bag card with `distribution > 0` apportions to **zero seats** over `bagSize` (`CD-17`) | **Tier A.** A card that exists in the config, appears in the tab, is fully implemented and can never be drawn is a silent failure no other check catches. This is the rule that would have caught the Freeze-at-2%-in-a-20-bag defect before it shipped, and it is why Freeze is now a rare slot (`CD-18`) rather than a bag seat. Freeze itself is exempt from this check because it is not a bag card; instead assert `freezePeriod ≥ 1` and that a token is scheduled. |
| `I10` | `cards.freezeDurationSeconds > 0.25 × match.targetDurationSecondsMin` | **Tier C with concrete text**, in `I6`'s style: *"Freeze lasts 20.0 s. At 1.25 tiles/s that denies the target 25.0 tiles of progress — 2.5× the entire minimum spawn→Hub distance, more than a realistic 16–24 tile route (`MR-5`), and 13 of their 15–25 card plays. One gem is worth 1.75 tiles, so Freeze is 14× a gem. In hot-seat the target is a person sitting next to you for 22–50% of the match. Recommended 6–10 s."* |
| `I11` | `rotateAnyDirection + rotateClockwise + rotateAntiClockwise < 0.70 × Σ distribution` | **Tier C.** `AS-3` step 3's walk-completion argument depends on rotation cards dominating the pool; at the authored weights they are 72%, and the margin above 70% is thin enough to be worth a warning rather than a discovery. |
| `I12` | `cards.maxFreezesReceivedPerMatch > 1` and `freezeImmunitySeconds < freezeDurationSeconds` | **clamp immunity up to duration (B).** Below this a victim's locked duty cycle exceeds 50% and `AS-1`'s P1c stops being a usable bound. At the default cap of 1 the invariant is vacuous, which is the point: the cap is the primary guard and the immunity is the rail behind it. |

**`DS-6`** **"Maximum Card Slots" appears twice in §18** (Card Collectible Settings and Snail Settings, both default 6). **Canonical location: `/snail/maxCardSlots`**, hard-capped at 6 per §9. It is a per-snail capacity that §17 explicitly varies by class, so it must live where `snailClassOverrides` can reach it. The Card Collectible group may render a **read-only mirror**; what must not exist is a second editable control. The duplicate is replaced by two fields that describe the *collectible's* behaviour, which the GDD never specifies: `slotsGrantedPerPickup` and `pickupAtMaxSlots`.

### 10.6 Card distribution semantics

**`DS-7`** The **six** percentages are **relative weights, and the draw always normalises by their actual sum.** The tab displays the live normalised percentage beside each row, so the designer always sees the authored rate. Only a **zero sum** is rejected (`I3`).

This is the minimum that closes the gap. §18 states five numbers that happen to sum to 100 and never says they must, so "drag Wildcard from 10 to 5" has three defensible readings (renormalise / reject / draw against 95). Unconditional normalisation makes the natural single-field edit always legal and always mean what it looks like, and it is what lets D5's `24/24/24/16/10/2` and the un-renormalised `25/25/25/15/10` coexist without either being wrong.

**The tab must display two numbers per row, not one: the normalised authored weight and the realised draw rate.** They are not the same and the difference is not noise. The five tile weights are apportioned into `bagSize` physical seats (`CD-17`), which quantises them by up to 1.0 pp; Freeze bypasses the bag entirely and its realised rate is exactly `1/freezePeriod` (`CD-18`). A tab showing only the authored weight silently promises a rate the bag does not deliver, which is the same class of defect as `I6`.

Optional UI polish, not required: per-row locks with proportional redistribution of the unlocked rows. Do not specify it as a rule — it over-constrains the tab.

### 10.7 Save / Load / Reset / Export / Import

**`DS-8`** All five operate on the in-memory config; only Save and Export write files.

- **Save** — validate → apply A/B/C → on Tier A abort and **write nothing** → rewrite derived fields (preset-driven counts, rounded floats) → stamp `meta` → write **atomically** (`.tmp` → flush → rename, previous file moved to `.bak.json`). A crash mid-write can never leave a truncated config.
- **Load** — validate, show the warning list, apply by scope (`live` immediately, `next_match` staged behind a visible "N settings apply next match" banner). A version mismatch in either direction is refused whole, not repaired (`DS-11`, `DS-12`).
- **Reset to Default** — two scopes (section / all), **in-memory only and undoable until Save**; the file on disk is untouched. *Reset all* requires confirmation. Reset never deletes files.
- **Export** — the promotion step. Writes strict JSON, 2-space indent, LF, keys in schema order (stable, so git diffs are readable), with `meta.gameBuildId` and `meta.exportChecksum` filled in, and drops `devsettings.schema.json` alongside if absent. Must go through a real filesystem path — a packed/exported game build cannot write back into its own resource bundle.
- **Import** — read, validate, then **show a diff table (current → incoming, changed rows only) and require confirmation.** Import never applies blind, and never auto-saves.

**`DS-9`** `configHash = SHA-256(canonical(config))`, where canonical = the non-`meta`, non-`schemaVersion` subtree, keys sorted lexicographically, floats formatted to 4 decimals, ints plain, no whitespace. The 4-decimal rounding is what makes hash equality achievable across platforms, and it is also the quantisation point for `MP-4`.

### 10.8 Versioning

**`DS-10`** `schemaVersion` is required and is the first key. **Keep it. It is the whole of what survives D4.**

The developer has ruled that §20 is not literal (D4), so the migration framework below it is deleted — but the stamp costs one integer and it is the only thing that makes a migration framework **addable later without invalidating every config saved before then.** Deleting it would not defer the work, it would make the work impossible to do cleanly; those are different decisions and only one of them was made. The stamp is also what lets a build say "this file is from a schema I do not know" instead of guessing, which is the one behaviour §20 unambiguously does require.

**`DS-11`** **There is no migration framework.** Per D4, the registered ordered chain, the pure per-step migrations, `ChangeNote{kind, …}`, the `lossy: true` acknowledgement path and the `v1 → v2` example migration are all **struck**. Roughly 3 weeks of specified work is removed with them, and milestone M4 shrinks accordingly.

What replaces it is two rules and nothing else:

- **Same version:** load it. Unknown keys at the same version are preserved verbatim and round-tripped on save (`DS-5`), exactly as before.
- **Any other version, older or newer:** do not guess. The config is offered as-is or ignored as a whole (`HO-2`), and the build says which it did.

Adding the six `freeze*` keys bumped `schemaVersion` 1 → 2. Under the deleted framework that would have been a registered `add-freeze-card` migration; under D4 it is **a version bump and a line in the changelog.** New keys take their defaults, which is what a key-matching load does anyway, and no tuned value can be lost by it because none of the added keys existed to be tuned.

**`DS-12`** `fileVersion > buildVersion` (a config from a newer build, e.g. after a rollback) is **never guessed at.** Halt and ask. This rule survives the collapse unchanged, because it never depended on migrations existing — it is the statement that silently dropping keys you do not understand is the one thing §20 actually forbids.

---

## 11. §20 — AI config handoff protocol

A requirement on the **build agent**, not a game feature. Nothing here ships in the game.

**Scoped by decision D4.** The developer has ruled that §20 is **not literal**: it does not describe repeatedly regenerating the game from the GDD plus a config, it means *"do not clobber my tuning."* This section is therefore **three steps — detect a saved config, ask once, apply or ignore** — and nothing more. The schema-migration framework, the older-schema-version prompt, and the migration machinery that used to sit here are deleted along with `DS-11`; about 3 weeks of specified work goes with them, and milestone M4 drops from 1–2 weeks to roughly 2 days.

What is deliberately **kept**, because it is cheap and is the actual content of §20: the search order, the definition of "tuned", the halt-rather-than-guess states, the single prompt, and the guarantees in §11.3 that make "did the agent honour my settings?" an answerable question rather than a hope.

### 11.1 Detection

**`HO-1`** Run **before generating or modifying any gameplay code**, at the top of the build task.

```
search order, first match wins; exclude .git/ build/ export/ and engine cache dirs:
  1. config/devsettings.json                ← canonical
  2. config/devsettings.*.json              ← named profiles
  3. **/devsettings*.json                   ← rescue scan
```

**`HO-2`** **"Tuned" means: parses, has `schemaVersion`, and at least one leaf differs from that version's defaults.** A file byte-identical to defaults produces **no prompt** — the developer is not nagged about a config they never touched — but the build log still records that it was found and matched.

| State | Condition | Action |
|---|---|---|
| `NONE` | no candidate | No prompt. Build with defaults. Log it. Write `config/devsettings.defaults.json`. |
| `UNTUNED` | valid, identical to defaults | No prompt. Build with defaults. Log the path. |
| `TUNED_SAME_VERSION` | ≥1 leaf differs, version == build's | **Prompt A.** Block until answered. |
| `TUNED_OTHER_VERSION` | ≥1 leaf differs, version ≠ build's (older **or** newer) | **HALT**, exit `CONFIG_VERSION_MISMATCH`. Write nothing. Name both versions and the path. Per D4 there is no migration path in either direction, so the honest options are "re-export from a matching build" or "choose defaults deliberately" — both of which are the developer's call, not the agent's. |
| `CORRUPT` | exists but unparseable or lacks `schemaVersion` | **HALT**, exit `CONFIG_UNREADABLE` with the parse error and byte offset. **Do not fall back to defaults** — that is the developer's choice to make. |
| `MULTIPLE` | >1 candidate at tier 1 or 2 | **Prompt C**: list each with path, version, saved-at, tuned-field count. **Never auto-select.** |

*Current repo state:* `Effandi/SnailLabyrinth` contains only `README.md`, so the first build resolves to `NONE`.

### 11.2 Prompt A — same schema version

The GDD's sentence is the first line, verbatim. The rest is the context required to answer it honestly.

```
A tuned Developer Setting configuration has been detected. Would you like to use
the saved settings for this version?

  File            config/devsettings.json
  Schema version  2  (matches this build)
  Saved           2026-08-14T09:12:03Z by devsettings-ui 1.0.3
  Profile         "playtest-fast-snails"
  Checksum        sha256:4f9c…a172  (verified)

  Tuned away from defaults in 6 of 54 parameters:
    map.gridWidth / gridHeight        16 x 16  ->  20 x 20
    gems.totalGems                    12       ->  18
    gems.boostDurationSeconds         7.0      ->  9.0
    snail.baseSpeedTilesPerSec        1.25     ->  1.60
    snail.maxSpeedTilesPerSec         2.00     ->  2.40
    cards.distribution.wildcard       10.0     ->  6.0

  Warnings: none.

  [1] Use Tuned Settings    - apply all 54 saved parameters to this build
  [2] Use Default Settings  - ignore the saved file for this build
                              (the file is left on disk, unmodified)
```

**`HO-3`** **There is exactly one prompt, and it has exactly the two options §20 names.** The older-schema-version prompt that used to stand here — with its migration chain, its categorised carried/renamed/lossy/defaulted report and its third "cancel and let me look" exit — is **deleted by D4** along with the framework it reported on. A version mismatch is no longer a thing the build negotiates; it halts (`HO-2`, `DS-12`).

This is a real reduction in capability and it is worth naming honestly rather than presenting as pure savings. Under the deleted design, a developer who tuned six values against last month's build could carry them forward and be shown precisely what could not be carried. Under D4 they re-export from a matching build or accept defaults. **That is the correct trade only because §20 is not literal:** if the config were the durable artifact and the code disposable, losing forward-carry would be unacceptable. It is not, so it is acceptable — and `DS-10`'s retained version stamp is what keeps the door open if that judgement ever changes.

### 11.3 Guarantees, each with its test

| # | Guarantee | Test |
|---|---|---|
| `G1` | The agent **never writes** `config/devsettings.json`. Loaded values are held in memory and baked into generated defaults. | sha256 before == after, for **both** answers |
| `G2` | New-build defaults live in a **separate file**, so regenerating defaults can never clobber tuning. | file identity |
| `G3` | **No gameplay code that bakes a tunable constant is emitted before the prompt is answered.** | mock a refused prompt; assert zero files written under the source tree |
| `G4` | "Use Tuned Settings" applies **every** parameter, not a subset. | post-build resolved config == source file, leaf by leaf |
| `G5` | "Use Default Settings" leaves the tuned file untouched — never deleted, renamed, or rewritten. | sha256 before == after |
| `G6` | Unreadable, version-mismatched, or ambiguous config **halts**. Falling back to defaults unbidden is forbidden. | three fixtures, assert non-zero exit |
| `G7` | Every clamp and every preserved-unknown key is recorded in the handoff record. | each warning appears in the artifact |
| `G8` | The prompt's diff is **derived from the loaded data**, never hand-written, so it cannot drift from what is applied. | mutate a fixture field; assert it appears in the rendered prompt |

`G1`…`G8` are the part of §11 that carries §20's actual promise, and none of them depended on migrations existing. They survive D4 intact and are still worth their (now much smaller) implementation.

### 11.4 Unattended and CI builds

**`HO-4`** §20 mandates an interactive prompt, but the workflow it describes can plausibly run with no human attached. **Silence is not consent. Fail closed.**

- With no TTY and no explicit flag, exit `CONFIG_CHOICE_REQUIRED` and generate nothing whenever the state is `TUNED_SAME_VERSION`, `CORRUPT` or `MULTIPLE`.
- The choice may be pre-supplied out of band: `--config-choice=tuned|default`, optionally `--config-file=<path>`. Supplying the flag **is** the human decision, and is recorded as `"decisionSource": "flag"`. There is no `--accept-lossy-migration` flag because there are no migrations (D4).
- `NONE` and `UNTUNED` proceed unattended — neither involves a tuned setting to honour or discard. `TUNED_OTHER_VERSION` never proceeds, attended or not.

### 11.5 `build/config-handoff.json`

```json
{
  "timestampUtc": "2026-08-19T11:02:44Z",
  "detectionState": "TUNED_SAME_VERSION",
  "candidatesFound": ["config/devsettings.json"],
  "sourceFile": "config/devsettings.json",
  "sourceSha256": "4f9c...a172",
  "sourceSchemaVersion": 2,
  "buildSchemaVersion": 2,
  "decision": "tuned",
  "decisionSource": "prompt",
  "warnings": [],
  "preservedUnknownKeys": [],
  "appliedConfigHash": "sha256:8b31...cc04",
  "sourceUnmodified": true
}
```

`migrationChain`, `lossyMigrations` and `changeNotes` are removed from this record by D4.

**`HO-5`** `sourceUnmodified` is asserted by re-hashing the source file at the end of the build. If it is ever `false`, **the build fails.** `G1` is enforced, not merely intended.

---

## 12. Headless-testable core

**`HT-1`** **`SimCore` is pure: no engine types, no scene nodes, no rendering, no input.** Signature `(WorldState, Command[]) → (WorldState, Event[])` at a fixed tick, deterministic given a seed. Everything in §§1–8 lives here. `Transport` is an interface (`LocalTransport` in v1, network transport at M1); `ClientView` renders `WorldState`, emits `Command`s, and owns prediction. **Adding networking then becomes swapping one implementation** — roughly two weeks of work deferred for about three days of discipline now.

### 12.1 Invariants worth unit tests

| Area | Invariant | Kind |
|---|---|---|
| Tile algebra | `cw⁴(m) == m`; `ccw(cw(m)) == m`; `opp(opp(d)) == d` | property, all 16 masks |
| Tile algebra | `popcount` is invariant under `cw`/`ccw` — this is the assertable form of `CD-7` | property |
| Tile algebra | mask ↔ (shape, rotation) is a **bijection** over all 16 masks | exhaustive |
| Connectivity | `connected(a,d) ⟺ connected(a+δ(d), opp(d))` | property, random boards |
| Connectivity | off-grid neighbours are never connected (`TM-9`) | exhaustive on the border ring |
| Cards | **legality and application, exhaustively**: 5 tile cards × 16 masks × ~6 target relations ≈ a few hundred cases. This is a *complete* test of the core rules, not a sample — very few games can say that. | exhaustive |
| Cards | no-op rule (`CD-8`): every legal application changes the mask | property |
| Cards | ANY preserves `popcount`; Wildcard need not | property |
| Topology legality | **differential test**: the fast predicate agrees with a naive full re-solve on random boards × random mutations. **Must exercise `Wildcard → DEAD_END` and `Wildcard → STRAIGHT` from a Cross, not only `→ ROCK`** — those are the cases the predicate previously never saw (`CD-13`) | differential, 10⁵ cases |
| Topology legality | `carryPreserving(before, after)` is **true for every rotation output and every mask**, so conditions 6–7 never run on a rotation | exhaustive, 16 masks × 3 rotation cards |
| Rock legality | a Rock is never accepted on an occupied cell — **including a `Frozen` cell in either substate** — the Hub, a spawn pad, or a collectible | exhaustive |
| Transit graph | `carries()` matches the §1.4 table for all 6 shapes × 12 ordered direction pairs | exhaustive |
| Transit graph | a Dead End carries **no** pair; a Straight carries only collinear; an Elbow carries only turns | exhaustive |
| Movement | `resolveExit` table-driven over (mask field, cell, arrivedFrom, intent, policy) — ~50 cases covers every branch | table |
| Movement | `s` never exits `[0,1]`; the remainder carried across a node conserves total distance exactly | property |
| Movement | a snail is never suspended on an edge that no longer exists (`MV-11`) — **run with freezes injected mid-traversal**; this is the test that catches a violation of `FZ-4` | fuzz |
| Movement | a frozen snail always rests at a tile centre, including when frozen at `s = 0.999` and while `Recoiling`; `Frozen(SETTLING)` never exceeds 64 ticks | property |
| Movement | a mutation dirtying a frozen snail's cell **never** moves it (`MV-12` exclusion) — the "Frozen is Waiting-plus-a-flag" regression | fuzz |
| Generation | `MG-5`…`MG-15` hold for every generated map | 10⁴ seeds × 5 sizes × 3 densities |
| Generation | **regenerate twice from the same seed, compare `MapDigest`** | determinism |
| Generation | cross-platform digest match (Windows vs Android CI) | determinism |
| Generation | the 4 spawns are the C4 orbit of `(m,0)` and their `SolveCost` spread satisfies `MG-11` (`GE-6`) | property, all 5 sizes |
| Anti-softlock | **`AS-3` as a fuzz test**: random board, adversarial rock placements, rotation cards only — assert the snail reaches the Hub within N cards | fuzz |
| Anti-softlock | **`FREEZE_UNDER_SIEGE`**: freeze the subject for the full duration while driving 3 adversaries at full `CD-16` cadence (13 plays, 4 rocks each) biased toward the victim's `G_T` frontier. Assert every tick that `CD-13` conditions 2, 6 and 7 hold with the frozen snail counted live; assert at expiry that its own cell is a non-Rock road tile and a finite-cost route exists; assert it then reaches the Hub on rotation cards alone. **This is the amended `AS-3` as an executable test and the formal answer to D5's stated main balance risk.** | integration, 10⁴ seeds |
| Liveness | **P1a** holds on every tick **including frozen ticks** | fuzz |
| Liveness | **P1b** holds for every snail **not currently `Frozen`** | fuzz |
| Liveness | **P1c** as an accumulator over a whole match: `Σ frozenSeconds(sn) ≤ duration × maxFreezesReceivedPerMatch`, and no single denial interval exceeds `duration + globalCooldown` | property, random command logs |
| Liveness | a legal play exists **on the expiry tick** | fuzz |
| Freeze | total lockout is exactly `freezeDurationTicks` from all four legal source states (`Traversing`, `Recoiling`, `AtNode`, `Waiting`) | table |
| Freeze | no snail's `occupancy` has size 2 for more than 64 consecutive ticks under any command log including freezes — the assertable form of `FZ-4` and of `CD-12`'s stated bound | fuzz |
| Freeze | `gemTimer` decrements exactly `(ticks elapsed − ticks frozen)`; `gemStacks` unchanged across a freeze; cooldowns likewise pause | property |
| Freeze | a cast on a `Finished`, `Spawning`, already-frozen, immune or capped target **consumes no card** | exhaustive |
| Freeze | `freezesReceived` never exceeds the cap; both counters survive a keyframe round-trip and appear in the determinism golden test | property |
| Freeze | a collectible under a `HELD` snail is neither consumed during the lockout nor lost at expiry | table |
| Freeze | replay the same command log; compare `WorldState` hash at `T`, `T+1`, `T+399`, `T+400`, `T+401` — the fencepost `FZ-9`'s step-0 ordering exists to fix | golden |
| Determinism | run the sim twice from the same seed + command log, compare a state hash. **This single test protects the netcode months before you write any** — and it costs nothing *if* `SimCore` is pure. | golden |
| Draw | bag composition matches largest-remainder apportionment of the five tile weights; shuffle constraints hold across the seam; ≤2 consecutive non-rotation draws **with the Freeze token interleaved** (`CD-18`) | statistical, 10⁵ draws |
| Draw | **every card with weight > 0 is drawable**: FREEZE appears exactly once per `freezePeriod` draws, never below index 8, and the realised rate converges to `1/freezePeriod` within ±0.05 pp. *This is the test that would have caught the undrawable-card defect.* | statistical, 10⁵ draws |
| Config | schema validation, clamping, `I1`…`I12` against stored fixtures | pure data |
| Handoff | `G1`…`G8` (§11.3) | integration |

**`HT-2`** **Not testable this way, and these are the actual risks:** camera readability, whether rotation *feels* good, whether the isometric view communicates direction, whether four snails are legible on one shared screen, and — the one D5 adds — **whether a hot-seat human will sit through a 20 s lockout without leaving the room.** No test touches any of it, which is exactly why the build order in §14 front-loads a renderer you can throw away and why `V1-5` now carries a kill criterion for the last one.

**`HT-3`** Keep any prototype scripts used to derive the generator's numbers as **reference oracles for differential testing**, not as shipping code. Discarding them turns the measured figures in §3 into unverifiable folklore.

---

## 13. Proposed v1 vertical slice

**`V1-1`** The hypothesis under test is §21's: *is grid manipulation + racing fun?* Everything that does not test it is deferred. Honest estimate for the full §22 as elaborated in this document: **7–12 months solo.** For the slice below: **6–9 weeks.**

**`V1-2`** §22 is not one deliverable, it is four, and only the first tests the hypothesis: (a) the real-time tile-manipulation racer, (b) networked multiplayer, (c) the Developer Settings tab, (d) the §20 handoff protocol. **(d) is a requirement on the build process, not a game feature, and should not gate a prototype demo at all** — and under D4 it is now roughly two days of work rather than three weeks.

### 13.1 In v1

| Kept | Why |
|---|---|
| **4 snails, one per side** (`GE-5`) | No longer a cut — this **is** the game under D2. Contested intersections, blocking and racing are all present, and the on-screen readability problem is halved relative to the withdrawn eight-snail design. |
| **Hot-seat, up to 4 humans, bots filling empty slots** | D2. This reverses the previous edition's recommendation, which was 1 human + 3 bots on the grounds that bots preserve real-time simultaneity where hot-seat destroys it. That argument is sound and the developer accepted the cost: what hot-seat buys back is the thing bots cannot test at all — **blocking is a social mechanic whose payoff is the other player's reaction**, and Freeze is that in its most extreme form. A bot does not mind being frozen for 20 s. A person in the room does, and that reaction is data you cannot get any other way. |
| **16×16 only** | one size |
| **Three tile cards: CW, CCW, ROCK** | The sharpest cut, and it stands. CW/CCW **are** the mechanic — §5's worked example is literally a clockwise rotation. ROCK is the entire interference axis. **Rotate-Any removes the arithmetic tax of reading tile orientation, so including it masks the very thing being tested:** can players parse orientation fast enough for this to be fun? If CW/CCW alone are not fun, ANY and Wildcard will not fix it — they will hide the failure. |
| **Freeze — implemented, and defaulted OFF** (`cards.distribution.freeze = 0.0`) | See `V1-6`. |
| **Gems** | ~2 days, and the only positive-reward loop in the game |
| **Own-cell targeting** (`CD-5`) and the **rock legality predicate** (`CD-13`, naive re-solve, no incremental algorithm) | one hour each; both prevent unrecoverable states |
| **Full tile model, transit graph, movement state machine, `SimCore` purity** | this is the durable artifact |
| **Telemetry** (§14.2) | the prototype's entire purpose is to learn something |
| **JSON config + hot-reload key** | two hours, not three weeks — see below |

**`V1-3`** With three tile cards and no Wildcard, `AS-3`'s premise still holds: the theorem needs only rotation cards, own-cell targeting, and the transit-graph invariant. Wildcard is a convenience, never the anti-softlock crutch. **If you need a Wildcard in week one, the rules are wrong.** This is unchanged by Freeze, which removes no cards from the pool and adds no anti-softlock obligation that rules I–V do not already discharge.

**`V1-6`** **Freeze ships in v1 code, disabled by default. This is a deliberate middle position and both extremes were considered.**

*Deferring it to M2 with ANY and Wildcard* is wrong. Freeze's entire risk is **social** — whether a human tolerates being locked out — and D2's hot-seat build is the only configuration that can measure it. Defer the card and you defer the measurement past the point where 20 s has been baked into everyone's mental model of the game.

*Shipping it enabled* is also wrong. v1's stated hypothesis is whether players can read tile orientation fast enough for rotation-racing to be fun (`V1-5`), and with bots filling most slots and `MR-1` making the human a natural leader-target, an enabled 2% Freeze means some early sessions are "the human watched for 20 seconds" — which corrupts the readability measurement rather than adding to it.

**So: build it, wire it, test it headlessly (§12.1 has nine Freeze rows), and ship with `cards.distribution.freeze = 0.0`.** Enabling it is one JSON edit under `V1-4`'s hot-reload. The first hot-seat session runs three matches at 20 s and three at 6 s on a fixed `MatchSeed` and settles the duration with `BO-2` data instead of argument (`FZ-12`). The cost of building it now rather than at M2 is small — the expensive parts (`FZ-4`'s settle, `FZ-9`'s tick order, the amended `AS-1`) are exactly the parts most likely to be wrong, and none of §12.1's existing suites can exercise them without a Freeze in play.

### 13.2 Cut from v1, explicitly

All networking · the Developer **Settings tab UI** · §20 protocol · Wildcard · Rotate-Any · card-slot collectibles · snail classes · map sizes other than 16×16 · the repair loop and the 10⁴-seed CI harness · sub-tick photo finish · reconnect · `FZ-8`'s thaw-diff and audio polish (the countdown and attribution are **not** cuttable) · §15's difficulty ramp (already labelled future work) · all custom art.

**No longer on this list, because D2 deleted the features rather than deferring them:** 4v4 team scoring, 8 snails, and bot substitution. They are not "cut from v1"; they do not exist.

**`V1-4`** **Dev settings in v1 = a hand-edited JSON file plus a hot-reload key.** Every value in §10.2 stays valid; only the tab UI, the three validation tiers and the handoff protocol are deferred. (The migration framework is not deferred — it is deleted, D4.) Two hours, not three weeks.

**`V1-5`** **Kill criteria — write these down before building, or the prototype never dies.** Target: 6 testers, 10 matches, instrumented.

- Do players use rotation cards **offensively** without being told to? (tests §13)
- Does anyone ever choose the **longer route** for a gem? (tests §9/§10)
- **Median time from spawn to a new player's first successful rotation.** If it exceeds ~30 s, §8's readability promise has failed and §1's art direction cannot save it.
- At an unsteered branch, do players stop and **enjoy** it, or stop and get frustrated? (settles decision D3)
- Match length distribution vs. the 40–90 s intent (`MR-5`).
- **With Freeze enabled: does the frozen player stay at the table?** Concretely — median seconds a hot-seat human spends frozen per match as a fraction of median match length, and whether any victim exceeds 25%. **If it exceeds 25%, the duration is wrong regardless of what the win-rate balance says.** A player who spends a quarter of the match watching will not ask for another game, and that outcome is invisible to every other metric on this list.

### 13.3 §22 acceptance criteria, mapped honestly

| §22 criterion | v1 | Note |
|---|---|---|
| 8 playable snails | **Withdrawn** | Not deferred — **withdrawn by the developer (D2).** The game is 4 players. `SimCore` no longer carries an eight-snail path, and building one "just in case" would be paying for a structure that was deliberately removed. |
| 4v4 team structure | **Withdrawn** | Not deferred — withdrawn by D2. There is no `team` field, no team scoring, and no team-mode discussion left in this document. |
| Grid-based labyrinth | **Met** | |
| Four starting sides | **Met** | one snail per side, `S[k]` on side `k` (`GE-5`) |
| Central finishing point | **Met** | as a 2×2 Hub (`GE-1`) — the GDD's "the centre" does not exist on any even preset |
| Random road generation | **Met** | `MG-17` layers 1–3 |
| Straight / T / cross / 90-degree / dead ends / rock blockers | **Met** | all six shapes, derived from mask |
| Four starting cards | **Partially met** | hand of 4, but drawn from a 3-card pool |
| Random replacement cards | **Met** | seeded bag |
| Up to six card slots | **Deferred** | slots fixed at 4; no slot collectibles |
| Rotate-any-direction card | **Deferred** | deliberate — see `V1-2` |
| Clockwise rotation card | **Met** | |
| Anti-clockwise rotation card | **Met** | |
| Rock Blocker card | **Met** | with the full `CD-13` legality predicate |
| Wildcard | **Deferred** | |
| **Freeze card** (new — D5, not in §22) | **Partially met** | Implemented in full and headlessly tested, shipped **disabled by default** (`V1-6`). One JSON edit enables it. |
| Gem collectibles | **Met** | |
| 20% temporary speed boost | **Met** | single 7 s timer, max 2 stacks |
| Extra card-slot collectibles | **Deferred** | |
| **Multiplayer competition** | **Met locally; networked play deferred to M1** | This is the criterion whose reading changed most under D2. The previous edition scored it *not met* because v1 was 1 human + 3 bots. Hot-seat means up to **4 humans competing on one machine in real time**, which is multiplayer competition by any ordinary reading of §22 — it is simply not *networked*. State it exactly that way to the stakeholder: do not upgrade it to a clean "met", and do not keep calling it a headline miss when four people can now play. |
| Developer Settings panel | **Deferred** | JSON file + hot reload instead |
| Save/load configuration | **Partially met** | file load; no in-game Save/Export UI |
| AI confirmation before applying tuned settings | **Deferred** | §11 is a build-process deliverable, not a game feature — and under D4 it is now ~2 days of work |

**Score: 11 met, 4 partial, 6 deferred, 2 withdrawn.** The headline changed: multiplayer competition is no longer the criterion v1 most visibly fails, because D2 turned it into a local-versus-networked distinction rather than a presence-versus-absence one. The two **withdrawn** rows are the ones to state up front instead — a stakeholder holding the GDD will look for eight snails and two teams and must be told they were removed by decision, not missed by scope.

### 13.4 Milestones after v1

| Milestone | Content | Estimate |
|---|---|---|
| **M1** | LAN listen-server, 2–4 humans, `MP-1`…`MP-12`, networked competition. **Blocking gate: `FZ-11`** — Freeze's unlimited targeting must acquire a range/visibility constraint or `CD-9`'s governing rule must be formally amended, before the per-player follow camera ships. | 3–4 weeks |
| **M2** | All six cards enabled (ANY, Wildcard, Freeze on by default), slot collectibles, all map sizes | 2–3 weeks |
| **M3** | Developer Settings tab, validation tiers, save/load/export/import | 3–4 weeks |
| **M4** | §20 handoff protocol + CI harness | **~2 days** (D4 answered "not literal"; the 1–2 week estimate assumed the deleted migration framework) |
| **M5** | Art pass per §9.2 | 3–5 weeks |
| **M6** | Online (relay/matchmaking/hosting) — **a population and infrastructure problem, not a design problem** | 6–10 weeks + ongoing |

Attempting M6 before a 4-human LAN build is proven is the most likely way this project stalls.

---

## 14. Build order, telemetry, repo hygiene

### 14.1 Build order

**`BO-1`** In this order, because each step de-risks the next and the first three are nearly free.

1. **`SimCore`, headless.** Run under a CI test runner from day one. §§1–8 in full, with §12's invariant suite.
2. **An ASCII terminal renderer.** Print the board as text, drive it from a script. You can playtest the *rules* — not the feel — in a terminal within a day, and you will discover "the snail stops at every junction and it's tedious" before a snail has been modelled.
3. **A flat 2D scene**: coloured squares, arrows, real input. This tests the single highest-risk unknown in the design — *can a player read tile orientation at a glance?* — at roughly 1% of the cost of the 3D isometric build. **If orientation is not readable in flat 2D, it will not become readable in isometric.** This scene then ships permanently as `PR-11`'s schematic overlay.
4. **Only then, 3D isometric.**

### 14.2 Telemetry

**`BO-2`** The prototype exists to learn something and there is currently no logging spec anywhere. ~100 lines, and it is the only instrument for the stated objective; without it, "is it fun?" is answered by vibes.

Log per match, as newline-delimited JSON: match id, seed, `MapDigest`, resolved `configHash`; every card play (`tick, player, card, target, maskBefore, maskAfter, accepted/rejected+reason`); every junction stop (`tick, player, cell, exitCount`); every `Waiting` entry and exit with duration; time-to-first-card; time-to-first-successful-rotation; route length and finish time per snail; every rock rejection with the failing `CD-13` condition; **final placement order 1st–4th** (`MR-1`).

The card-play line already covers Freeze casts and refusals generically. **Four freeze-specific fields are new and none of them can be reconstructed after the fact**, so they must be logged at the moment:

```
frozen_interval { victim, caster, startTick, endTick, victimRankAtCast, victimRankAtExpiry,
                  placementDelta, distToHubAtCast, distToHubAtExpiry, tilesMutatedDuringFreeze,
                  gemSecondsPaused, cooldownSecondsPaused, victimFinished }
per-snail summary: cumulativeFrozenSeconds, frozenAtMatchEnd, freezesReceived, freezesRefused+reason
```

Two of these carry the whole balance argument. **`victimRankAtCast`** answers *do casters converge on the leader?* — if the histogram is a spike at rank 1, `FZ-6`'s cap is load-bearing rather than precautionary. **`placementDelta`** — how many opponents overtook the victim during the lockout — answers *was the freeze decisive?*, which is the only honest measure of whether 20 s is proportionate and is the direct answer to D5's own open question (`FZ-12`).

### 14.3 Repo hygiene

**`BO-3`** The repository is empty; set these before the first commit.

- `.gitignore` engine cache directories and `user://`-equivalent output.
- **Export/build preset files can carry Android keystore paths and passwords and must not be committed.** Add them to `.gitignore` on day one; committing once and removing later does not remove them from history.
- Git LFS for binary art (`.blend`, textures) from the first art commit, not retroactively.
- CI job running the headless test suite on every push. Three separate CI harnesses are specified in §12 and none of them exists until this does.
- **Pin the engine version in the repo** and check test-framework compatibility on day one; discovering it in week six is expensive.
- **Commit `.glb` (or equivalent) rather than relying on direct `.blend` import before CI or a second developer exists** — direct DCC import requires the DCC app installed on every machine that opens the project, including the build machine.
- **Set a performance target now or drop Android from v1**: 60 fps desktop, 30 fps on a 2021 mid-range Android device. No model in the design currently states one.

---

## Appendix A — Constants quick reference

| Constant | Value | Rule |
|---|---|---|
| Direction bits | N=1, E=2, S=4, W=8 | `TM-2` |
| Off-grid mask | 0 (Rock) | `TM-9` |
| **Players** | **4, free-for-all, one snail per side. No teams.** | D2, `GE-5`, `MR-1` |
| Hub | 2×2 centre (even N), all mask 15, card-immune | `GE-1`, `GE-2` |
| Spawn offset `m` | `clamp(round(N/4), 1, N/2-2)`; spawns are the C4 orbit of `(m,0)` | `GE-5`, `GE-6` |
| Sim tick | 20 Hz, `dt = 50 ms`, fixed-point | `MP-3`, `MP-4` |
| Base speed | 1.25 tiles/s → **0.80 s per tile** | `MV-13` |
| Max speed | 2.0 tiles/s (hard cap on boosted) | `MV-13` |
| Turn retention | ×0.7 on a 90° turn | `MV-15` |
| Gem boost | +20%, 7.0 s, refresh to full, max 2 stacks | `MV-16` |
| Rock range | Chebyshev 3 | `CD-9` |
| Rock cap | 35% of board (generator ceiling 18%) | `CD-13` |
| Global card cooldown | 1.5 s (Rock 6.0 s, Freeze 20.0 s, discard 4.0 s, waived when no legal play) | `CD-16` |
| Bag | 20 cards, `[ANY×5, CW×5, CCW×5, ROCK×3, WILD×2]`, per-player seed. **Five card types; Freeze is not in the bag** | `CD-17` |
| **Authored draw weights** | **24 / 24 / 24 / 16 / 10 / 2** (ANY, CW, CCW, ROCK, WILD, FREEZE) | `CD-6`, `DS-7` |
| **Freeze rare slot** | **1 token per 50-draw super-cycle = exactly 2.0%**, index ≥ 8, per-player seed | `CD-18` |
| **Freeze duration** | **20.0 s = 400 ticks** (recommended band 6–10 s); immunity 20.0 s | `FZ-1`, `FZ-12` |
| **Freeze cap** | **1 per victim per match**; max inaction 20 s + one global cooldown = **21.5 s** | `FZ-6`, `AS-1` P1c |
| Contested tile lock | 300 ms, loser refunded | `MP-6` |
| Target match length (16×16) | 40–90 s; hard timeout 180 s | `MR-5`, `MR-6` |
| Fairness | `max C / min C ≤ 1.15` across 4 spawns | `MG-11` |
| Schema | `schemaVersion` 2, 54 hashed parameters, **no migration framework** | `DS-10`, `DS-11` |

