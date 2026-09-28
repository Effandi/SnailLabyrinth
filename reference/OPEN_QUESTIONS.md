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
