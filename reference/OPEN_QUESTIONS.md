# Open questions

Ambiguities found while implementing the spec, recorded per the task rule:
"if the spec is silent or ambiguous on something you need, do not invent a
rule silently — implement the most defensible reading and record it here."

---

## OQ-1 — `TM-12`'s `source(s)` formula, fed literally into the `edge` rule,
## would make any snail resting on a Dead End unable to reach the Hub in
## `G_T`, even in the ordinary, unattacked case

**The literal text (`TM-12`):**

```
carries(c, a, b) = ∃ m ∈ orbit(mask[c]) : (m & a) && (m & b)        // a ≠ b, both single-bit
edge (v,a) --b--> (u, opp(b))   for u = v + delta(b), mask[u] ≠ 0, carries(v, a, b)
source(s) = { (s.cell, d) : ∃ m ∈ orbit(mask[s.cell]) with (m & d) }   // the snail is already on its cell
```

`source(s)` produces bare `(cell, d)` pairs shaped exactly like the `(v, a)`
nodes the one stated `edge` rule consumes. Read completely literally — feed
`source(s)`'s output straight into that same `edge` rule as `(v=s.cell,
a=d)` — the very first hop out of the source cell would require
`carries(mask[s.cell], d, b)` for some second direction `b`: i.e. *some
single rotation of the source tile must have both `d` and `b` open at once*.

For a Dead End (`popcount(mask) == 1`), no rotation ever has two bits set,
so `carries` is `False` for every `(a, b)` pair regardless of the tile's
current facing (this is exactly `TM-11`'s "a Dead End carries no pair" —
verified exhaustively in `tests/test_transit.py::CarriesTableTests`). Taken
literally, this would mean: the instant any live snail comes to rest on a
Dead End — including the ordinary case where it just walked in through that
Dead End's one opening from a neighbour that was, by `TM-8`'s mutual
openness rule, open toward it a moment ago — `G_T` reachability from that
snail's current cell is permanently `False`, with no rotation able to fix
it (rotating a Dead End only changes *which* single direction is open;
`CD-7` says rotation cards are shape-preserving, so it is still a Dead End
afterwards).

That contradicts the document's own theorem. `AS-3` step 2 states, as an
unconditional property that must hold at *every* instant for *every* live
snail (`P1a`, `AS-1`): "By I there is a path `P = (c0 = snail cell, c1, …,
ck ∈ HUB)` in the transit graph" — with `c0` explicitly the snail's own
current cell. If resting on a Dead End made `G_T` reachability from that
cell impossible by construction, `P1a` would fail every time *any* snail
merely walks into *any* Dead End during ordinary, non-adversarial play —
not just under the one-card-kill attack `CD-5`/`AS-2` rule II is written to
fix. The spec clearly does not intend that: `MV-10` treats entering a Dead
End as a normal, recoverable event (stop, then reverse or re-route), not as
an instant liveness violation.

**Resolution implemented (`transit.py`):** `source(s)` is treated as a
one-hop *departure* rule, distinct from the `carries`-gated `edge` rule used
for interior nodes. `TransitGraph.first_departures(cell)` enumerates every
direction `d` achievable by some rotation of the origin tile (exactly
`source(s)`'s direction set) and hops **directly** to the neighbour in that
direction — `(cell + delta(d), opp(d))` — with no requirement that a second
direction `b` be simultaneously open at the origin. From that neighbour
onward, the standard `carries`-gated `edges_from` (the literal `edge` rule)
applies unchanged.

This reading is supported by the source formula's own comment — "the snail
is already on its cell" — which is precisely the fact that makes a paired
entry/exit requirement inapplicable: the snail is not passing *through* its
own cell, it is *departing from* it, so there is no "entry side" for the
current tile to reconcile with an "exit side" in one fixed rotation. It also
reproduces `TM-11`'s table exactly as stated: a Dead End can be an *origin*
(this resolution allows it) but is never an *interior* path cell (unchanged
— `edges_from` on a real interior node with a real entry direction still
requires `carries`, which a Dead End never satisfies). See
`tests/test_transit.py::test_TM12_a_dead_end_can_be_an_origin_but_never_an_interior_cell`
for both halves of this distinction as an executable test.

**What would falsify this reading:** if a future section of the spec (not
yet implemented — e.g. the movement state machine's interaction with
`CD-13` condition 6, or the `FREEZE_UNDER_SIEGE` integration test) turns out
to *require* the literal every-node-through-`edges_from` reading, this
resolution should be revisited before that module ships, and this entry
updated.

---

## OQ-2 — `TM-10`'s statement is a legality principle, not a connectivity fact

`TM-10` ("Rotating a border tile is legal whenever the mask changes, even if
effective connectivity does not") is stated in section 1.3 (connectivity)
but its actual normative content — "legal whenever" — belongs to the card
mutation-legality rules (`CD-8`'s no-op rule, evaluated on `mask` equality,
not on `usable_exits` equality) which are not implemented yet. This
increment implements and tests only the observable fact `TM-10` depends on
(a border tile can change mask while its outward opening remains
permanently uncrossable, `TM-9`) and leaves the actual legality predicate
(`CD-8`) to the card-system increment, where it will be implemented as
`before_mask != after_mask`, not as a connectivity comparison. Not a
resolved ambiguity so much as a forward pointer, recorded so the next
increment doesn't have to rediscover the connection between the two rules.

---

## OQ-3 — `MG-2`'s `TAU[c][a][b]` formula uses `ori(c)` and `MASK[shape(c)][o]`,
## neither of which this increment gives a concrete representation

**The literal formula:**

```
TAU[c][a][b] = min over o of ACT[(o - ori(c)) mod 4] where MASK[shape(c)][o] ⊇ {a,b}
```

`ori(c)` ("the current orientation index of cell `c`, 0..3, relative to some
canonical reference mask for its shape") and `MASK[shape][o]` ("the mask you
get by rotating that canonical reference `o` quarter-turns") are never
defined concretely elsewhere in the document — there is no stated convention
for which mask is "canonical" per shape, nor for how `ori` is computed for a
shape whose rotation period is less than 4 (Straight repeats every 2 steps;
Rock and Cross are fixed points).

**Resolution implemented (`transit.tau_milli`): re-derive the formula over
quarter-turn deltas from the cell's own current mask, with no canonical
reference and no `ori()` at all.** For any `o`, by definition `MASK[shape(c)]
[o] == cw^o(canonical)`, and `ori(c)` is defined by `cw^ori(c)(canonical) ==
mask[c]`. Substituting one into the other: `MASK[shape(c)][o]` evaluated at
`Delta = (o - ori(c)) mod 4` equals `cw^Delta(mask[c])`, **for every `o`** —
the canonical reference and `ori(c)` cancel out algebraically regardless of
what convention you'd have picked for either. So the whole formula collapses
to: let `Delta` itself range over `0..3` and test `cw^Delta(mask[c])` for the
pair `{a,b}` directly, taking the minimum `ACT[Delta]` over the `Delta`s that
qualify. `tau_milli(mask, a, b)` implements exactly that, and returns `None`
(infinite cost) exactly when no `Delta` qualifies, i.e. exactly when
`carries(mask, a, b)` is false — this is checked directly in
`tests/test_transit.py::WeightedCostModelTests::test_MG2_tau_milli_is_none_exactly_when_carries_is_false`.

This is a re-expression, not an interpretive choice: the two formulas are
provably identical for every possible canonical-mask/`ori` convention, so
there is nothing left to get wrong by picking one.

---

## OQ-4 — `MG-2`'s Dijkstra edge weight and its own reported scalar `C` use
## two different weightings of `R` and `L`

**The tension.** `MG-2` states:

```
edgeCost = TAU[v][a][b] + STEP_MILLI
SolveCost(s) = shortest-path distance in G_T from source(s) to any HUB cell
             = the pair (R = card-actions, L = tiles), scalar C = 2·R + L  cost units (CU)
```

Summing `edgeCost` along a path gives `ΣTAU + L·STEP_MILLI`, i.e. a 1:1
weighting of `R` (in milli-card-actions) against `L` (in milli-tiles, since
`STEP_MILLI` is added once per edge). But the reported scalar is `2·R + L` —
a 2:1 weighting. A Dijkstra run with `edgeCost` as literally stated therefore
does not necessarily find the path that *minimises* `2·R + L`; it finds the
path that minimises `R + L`. These can disagree (a path with one extra tile
but one fewer required rotation could score better under `R+L` while scoring
worse, or the same, under `2R+L`, depending on exact values).

**Resolution implemented:** treat the two formulas as serving two different
purposes, both taken literally rather than reconciled into one weighting.
`TransitGraph.solve_cost` runs Dijkstra with the stated `edgeCost` (`R+L`
weighting) to find *a* shortest path — this is the `SolveCost` "shortest-path
distance" the spec names — and then reports that path's own `(R, L)` pair
and `C = 2·R + L`, computed from that specific path, as the stated formula
defines. It does not search for the path that separately minimises `2R+L`.

**Why this reading over re-deriving a 2:1-weighted Dijkstra:** the spec gives
`edgeCost` as a single, explicit, named formula for the graph traversal, and
separately gives `C` as a labelled *reporting* statistic ("scalar C = 2R+L
cost units"), not as a second edge-weight formula to re-run Dijkstra with.
Nothing in `§3` asks for two different shortest-path searches per spawn. If
a future increment (`MG-8`'s concrete per-size bounds, `MG-11`'s ratio, or
the accretion/repair loop in `MG-17`/`MG-19`, all of which consume `C`)
reveals that this disagreement actually changes which map configurations
pass or fail those guarantees, revisit this entry before that increment
ships — it is the one place the two SolveCost formulas could, in principle,
pick different "optimal" routes.

---

## OQ-5 — `MG-17` layer 1's "radius-2 wedge" has no concrete definition

**The literal text:** "The 4 corridor regions (Start Pad + a radius-2
wedge) and the Apron ring are generated once in a quarter-turn fundamental
domain and replicated by the C4 orbit (`GE-6`)." Neither "radius-2" nor
"wedge" is defined elsewhere — there is no stated distance metric, and no
stated shape for the region beyond "wedge" (as opposed to, say, a full
disc or a rectangle).

**Resolution implemented (`generator.canonical_corridor_wedge`):**
"radius-2" read as **Chebyshev distance <= 2** from the spawn cell. This
matches the document's own house convention for grid distance elsewhere —
`CD-9`: "Rock range: Chebyshev 3" — rather than Manhattan or Euclidean
distance, neither of which this document uses anywhere else. "Wedge" is
read as "every in-bounds cell within that radius, minus whatever the Hub/
Apron/Spawn-pad geometry already claims" — i.e. the full square
neighbourhood clipped by what's already reserved, not a quarter-disc or
other explicitly wedge-shaped subset, since nothing in the text gives a
boundary for a narrower reading and the clipping against reserved cells
already prevents overlap with the Hub/Apron/other spawns at every preset
size (checked directly: `CorridorWedgeTests` in `tests/test_generator.py`).

**What would falsify this reading:** a later increment (the rock-accretion
loop, `MG-17` layer 3, or the repair loop, `MG-19`) finding that the
radius-2 region is either too large (crowding out layer 2's "free"
interior near the spawn) or too small (failing to anchor enough of the
route cost near each spawn to make `MG-11`/`MG-14` achievable, which is
the whole stated point of layer 1) would be a sign to revisit the radius
or the "full square, clipped" shape, not necessarily the Chebyshev metric
itself.

---

## OQ-6 — layers 1-2 alone do not reliably satisfy `MG-6`, `MG-8`, `MG-11`,
## or `MG-14`; this corrects the previous increment's `PROGRESS.md`

The consolidated PR's `PROGRESS.md` (increment 3) described the next
increment's deliverable as "a map with no rocks and no collectibles [that]
is already fully testable against `MG-6`/`MG-8`/`MG-11`/`MG-14`". Having
now built layers 1-2 and measured it empirically (fixed, deterministic
seed sweeps; see `tests/test_generator.py`'s
`MG6PreRepairCharacterizationTests` and the numbers below), that phrasing
is true only in the narrow sense that the *code path* to check these
guarantees now exists and runs without error — it is not true that the
guarantees themselves are expected to *hold* yet:

- **`MG-6`** (every spawn's `SolveCost` finite): ~97.75% of spawns across
  40 seeds x all 5 preset sizes (18/800 unsolved in the measurement that
  produced this note). A concrete, reproducible failure — `N=8`, seed 31,
  spawn `S0` — is pinned down as
  `test_a_concrete_pre_repair_failure_exists`. This is exactly the failure
  mode `MG-18` ("dead-end repair is mandatory ... a 10% dead-end field
  alone seals spawns") describes, and it occurs with **zero rocks
  anywhere on the board** — layer 2's ~10% Dead-End weight is sufficient
  on its own, without any rock accretion at all.
- **`MG-8`** (`C_min <= C(s) <= C_max`): ~77% pass rate (903/1176
  reachable spawns, same sweep). Expected: layer 3's accretion loop
  deliberately grows rocks *until* `mean C >= C_target` (`MG-17`), so a
  rock-free board has no mechanism pushing cost up toward the target band
  at all; passing this often is incidental to layer 2's Dead-End/Elbow mix
  already adding some rotation cost, not a guarantee.
- **`MG-11`** (`max C / min C <= 1.15`): ~30% pass rate (88/291 boards
  where all 4 spawns were reachable). Expected and explicitly foretold by
  the spec's own framing: `GE-6` says layer 1's symmetry is what makes
  `MG-11` "achievable rather than aspirational" — not automatically true —
  and `MG-19`'s repair loop exists specifically to close the residual gap
  layer 2's independently-hashed free interior reopens. Asserting `MG-11`
  here would be asserting something the design does not yet claim.
- **`MG-14`** (`|R(s) - mean R| <= 2`): not separately measured, but tied
  to the same mechanism as `MG-11` and expected to be similarly unreliable
  pre-repair.

**No code change requested** — this is a documentation correction, not a
bug. Recorded so the next scheduled run does not write assertion tests for
`MG-6`/`MG-8`/`MG-11`/`MG-14` passing against a layers-1-2-only board, and
instead treats them as the acceptance criteria for the *next* increment
(`MG-18` dead-end repair, then `MG-19`'s repair loop, then layer 3's
accretion actually reaching `C_target`) — see `reference/PROGRESS.md`.

---

## OQ-7 — `MG-18`'s "deterministic hash order" could mean a stateless
## per-cell hash or a draw from `MG-24`'s sequential "repair" stream

**The tension.** `MG-18`'s own text says: "convert the frontier dead-end
nearest the Hub component (**deterministic hash order**)." Separately,
`MG-24` lists `repair` as one of the **sequential** stream labels
("Streams: `types, orient, walls, gems, upgrades, repair`... Stateless
hashing for anything indexed by cell... streams only for genuinely
sequential processes (darts, accretion order, **repair**)"). Those two
read as contradictory guidance for the *same* rule: `MG-18`'s own
parenthetical names a *hash*, but `MG-24`'s classification puts "repair"
specifically in the *stream* (sequential, stateful) bucket, not the
stateless-hash bucket.

**Resolution implemented (`repair.repair_dead_ends`):** every frontier
Dead End candidate at a given repair step is tied for "nearest" (each is
found by `find_frontier_dead_ends`, which only looks one step out from the
current component — see that function's docstring), so the tie-break is
the *entire* selection rule at that step, and `cell_hash(root_key, "repair",
x, y)` is used as a plain, stateless sort key over the current candidate
set. This is "deterministic hash order" taken completely literally.

**Why this reading over `rng.make_stream(root_key, "repair").next_below(...)`:**
a stateless hash keeps the result of repairing a board independent of
*which* candidates happened to exist at a prior step (since the hash of a
given cell never changes), whereas a sequential stream's output at step
`k` depends on exactly how many draws happened at steps `0..k-1` — i.e. on
how many frontier candidates existed each time, not just on cell identity.
Nothing in `MG-18` suggests the choice of *which* cell to repair next
should depend on the history of a repair run in that way; `MG-24`'s own
listed purpose for streams ("genuinely sequential processes") reads more
naturally as describing *accretion* and *darts*, where draws legitimately
consume state across iterations for reasons the spec states explicitly
(e.g. `MG-20`'s relaxation ladder), not as a blanket rule that the string
"repair" in that list must mean *this* rule reaches for a stream. The
`cell_hash` label argument is `"repair"` either way, so nothing about
`MG-24`'s stream-vs-hash *label namespace* is violated by this choice.

**What would falsify this reading:** if `MG-19`'s repair loop (not yet
implemented — a different, later rule, also using the word "repair") turns
out to need the sequential stream specifically (e.g. because its own text,
unlike `MG-18`'s, does not say "hash order"), that would be independent
evidence that `MG-24`'s `repair` stream label was reserved for `MG-19`,
not `MG-18` — revisit this entry if so, but it would not retroactively
change what `MG-18` itself asks for.

---

## OQ-8 — a frontier Dead End that four different directions press on at
## once cannot be fit into a Tee (3 openings); `MG-18` doesn't say what to
## do then

**The tension.** `MG-18` says to convert a frontier Dead End "to a TEE" —
unconditionally, with no fallback. A Tee has exactly 3 openings (`TM-3`).
`find_frontier_dead_ends` can, in principle, accumulate up to 4 required
directions for one cell: its own pre-existing single opening, plus up to
3 more from distinct component neighbours each independently pressing an
opening toward it from a different side. Four required directions cannot
fit in a 3-opening shape.

**Resolution implemented (`repair.choose_repair_mask`):** when exactly 4
directions are required, the lowest-priority one in fixed `N, E, S, W`
order is dropped, and the result is the Tee covering the other 3. The
connection(s) that direction would have made are simply not realised on
this repair step.

**Why this is safe, not a correctness gap:** dropping a connection never
*un-solves* anything — the cell was a Dead End a moment ago, carrying
nothing as an interior path cell either way (`TM-11`); every connection
the chosen Tee makes is strictly new. The dropped side, if it still
matters, remains a legitimate frontier opportunity (that neighbour is
still pressing an opening toward this now-Tee cell) — except this cell is
no longer a Dead End, so `find_frontier_dead_ends` will never re-offer it.
In practice this case has not been observed to matter: it requires three
*distinct* component cells to each already independently happen to face
the same single Dead End from three different sides, which is rare on the
boards this increment's sweep covers (`tests/test_repair.py`'s
`ChooseRepairMaskTests` covers the 4-required case directly as a unit
test, since the full-generator sweep may never happen to exercise it).

**What would falsify this reading:** if a future increment's measurement
shows this truncation measurably hurts `MG-6`/`MG-11`, the fix would be to
escalate to a Cross instead of a Tee in exactly the 4-required case —
`MG-18`'s text would then be read as "Tee, except when nothing less than
a Cross will do," which is a defensible fallback but not what the text
says outright, so it is not implemented pre-emptively.

---

## OQ-9 — `MG-17` layer 3's "ordered by hash" / "hash-chosen direction" vs
## `MG-24`'s explicit "accretion order" sequential-stream listing

**The tension, sharper than OQ-7's.** `MG-17` layer 3's own pseudocode
says, in one short passage: `candidates = cells outside protected regions,
ordered by hash`, then `grow a straight segment of length 2..4 from c in a
hash-chosen direction`. Both explicitly say "hash." But `MG-24` lists
`accretion order` by name as one of the processes streams are "reserved"
for: "Labelled stream splitting... Streams: `types, orient, walls, gems,
upgrades, repair`... streams only for genuinely sequential processes
(**darts, accretion order, repair**)." Unlike OQ-7's "repair" (which could
plausibly mean `MG-18` *or* the not-yet-implemented `MG-19`), "accretion
order" has only one possible referent — `MG-17` layer 3's own candidate
loop — so this is direct, unambiguous evidence that `MG-24` wants *this*
rule's candidate iteration to consume a sequential stream, not a stateless
per-cell hash. This is a stronger case for the stream reading than OQ-7's
was.

**Resolution implemented (`generator.generate_layer3`): stateless
`CellHash`, three independent labels (`"walls"` for candidate order,
`"walls_dir"` for growth direction, `"walls_len"` for segment length),
consistent with OQ-7's precedent rather than `MG-24`'s stream listing.**
Three reasons, weighed against the sharper tension above:

1. **The local rule's own text is unambiguous and says "hash" twice in
   the same short passage**, for both the two sub-decisions it explicitly
   names (order, direction). A rule that meant "stream" for its own
   mechanism would not plausibly phrase itself this way twice in a row.
2. **A sequential stream for candidate *order* would make the result
   order-of-discovery-dependent in a way deterministic hashing avoids**:
   `MG-24`'s own stated purpose for stateless hashing — "the interior is
   independent of iteration order" — is a correctness property worth
   keeping for *which cells layer 3 even considers*, the same way it
   matters for layer 2's types/orientations. A stream numbered off some
   externally-fixed candidate list would still be deterministic, but only
   as "deterministic given this exact enumeration order", a strictly
   weaker and more fragile property than CellHash's "deterministic given
   only `(label, x, y)`."
3. **`MG-24`'s own stream-label list is evidently not a perfectly precise
   taxonomy** — `OQ-7` already found "repair" ambiguous between two
   different rules that both use the word. Given the list has already
   been shown to be loosely drafted in one entry, a second entry
   ("accretion order") being loose in a different way (naming the right
   *rule* but the wrong *mechanism*, when that rule's own text says
   "hash" twice) is the more parsimonious reading than treating `MG-24`'s
   list as the more authoritative source and overriding `MG-17`'s own
   explicit words.

**What would falsify this reading:** if a future playtest-driven change to
layer 3 needs candidate selection to depend on accretion history (e.g. "do
not re-consider a cell adjacent to one already rejected this run" — a
genuinely sequential, state-carrying rule), that would be real evidence
`MG-24` meant a stream here after all, and this entry should be revisited
before making that change. Nothing in `MG-17`'s present text asks for that,
so it is not implemented pre-emptively.

---

## OQ-10 — `GE-3`'s "Apron... rockable" vs `MG-17`'s "protected from
## rocks at generation **and at runtime**: HUB union APRON union..."

**The tension.** `GE-3` (section 2.1) states plainly: "Apron cells are
ordinary, contestable, rotatable, and **rockable** — that chokepoint is
the most interesting blocking play in the game and blanket-immunising it
deletes it. The unwinnable state is prevented instead by `CD-13`: a Rock
placement that would leave the Hub with zero non-Rock apron cells is
illegal." `MG-17` (section 3.3), introducing layer 3's accretion loop,
says: "Protected from rocks at generation **and at runtime**: `HUB union
APRON union StartPads union StartPad-inward-neighbours`." Read literally,
these directly contradict each other on whether a *player's* Rock card
(`CD-13`, not yet implemented) may ever land on an Apron cell at runtime.

**Resolution implemented, scoped to what this increment actually
builds.** This increment (`generate_layer3`, the *generator's own*
rock-placement pass) only needs to resolve the **generation-time** half of
this tension, where both rules agree: Apron is protected from rocks the
*generator* places (`GE-3` is silent on generation-time placement; `MG-17`
states it outright). `generator.protected_from_rocks` therefore includes
Apron, matching `MG-17`'s literal list. `routes.exempt_cells` (`MG-7`,
used for this increment's vertex-disjointness check) deliberately
**excludes** Apron, matching `GE-3`'s "rockable" — because `MG-7`'s own
stated purpose is defending routes against a *future player's* Rock
placement, and a cell `GE-3` says *will* remain legally rockable needs
exactly that defence, unlike Hub/Spawn/StartPad-inward which `GE-2`/`GE-8`
place genuinely beyond any card's reach.

**What is deliberately left unresolved:** whether `MG-17`'s "and at
runtime" clause is simply wrong (a drafting error that should read
"at generation" only, matching `GE-3`), or whether it is `GE-3` that is
incomplete (e.g. only describing Apron cells *not already* part of an
accreted rock segment, with `MG-17`'s runtime protection meant to apply
only to generator-placed Apron rocks specifically — though layer 3 as
built here never actually places one, since Apron is excluded from its
candidates, making that reading currently vacuous anyway). This is
squarely `CD-13`'s problem: the actual Rock-card legality predicate
decides, at runtime, whether a target cell carrying `SPAWN_PAD` or
similar is targetable, and `CD-13` is not implemented yet. Flagging here
rather than guessing now, so the `CD-13` increment resolves it with the
real targeting-legality code in front of it instead of in the abstract.
