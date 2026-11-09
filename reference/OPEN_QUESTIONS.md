# Open questions and ambiguities

Recorded per spec rule id, with the reasoning for the reading chosen. Do not
silently invent behaviour where the spec is silent — if a future increment
hits a gap, add an entry here before resolving it.

## TM-7 — rendering rule is out of scope for this reference implementation

`TM-7` ("derive mesh yaw from the mask every time it changes; never
accumulate") is a rendering rule about the Godot port's mesh instances. Per
`HT-1`, `SimCore` has no rendering: "no engine types, no scene nodes, no
rendering, no input." This reference implementation is `SimCore`-only, so
`TM-7` has no corresponding code here by design, not by omission. It should
still be checked against the eventual GDScript port's mesh-update code, just
not here.

## TM-12 — bit assignment for `flags` (board.py)

`TM-6` names the flags (`FINISH_LOCKED | SPAWN_PAD | HAS_GEM | HAS_SLOT |
ROCK_PROTECTED`) but does not specify their bit order within the flags byte.
Chosen: `FINISH_LOCKED=1, SPAWN_PAD=2, HAS_GEM=4, HAS_SLOT=8,
ROCK_PROTECTED=16` (declaration order, ascending bit). This is an
implementation detail with no behavioural consequence as long as the GDScript
port picks any consistent assignment — flags are never serialized or compared
across implementations in the spec (unlike `mask`, which is network-visible
per `TM-6`'s "replicate full state" and the `MapDigest` in `MG-24`). Flagging
here only so nobody assumes these bit values are normative.

## TM-12 — `source(s)` semantics confirmed by construction, not by an explicit worked example

The spec gives `source(s) = {(s.cell, d) : exists m in orbit(mask[s.cell])
with (m & d)}` but does not walk through why this is the right definition
(as opposed to, say, only the directions open in the spawn's *current*
mask). Reading adopted: a spawn's starting node set must include every
direction the spawn tile *could* be rotated to present, because `G_T`
answers "is this board still solvable by rotation cards alone" (`TM-12`),
and the spawn tile's own orientation is as mutable as any other tile's
(Start Pads are an immutable **T-Junction**, per `GE-8`, which is a *shape*
constraint, not an orientation lock — nothing in `GE-8` freezes a Start
Pad's rotation). This reading is also the only one consistent with
`source_nodes` producing the empty set for a Rock-masked cell (no card can
ever open a Rock; `TM-4`), which the differential/BFS behaviour elsewhere in
the spec requires (a Rock-sealed spawn must be correctly judged
unsolvable). No test in this increment depends on Start Pads specifically
(that is `GE-8`, a later increment, with its own board-geometry module); the
`transit_graph` module here is deliberately generic over any `(board,
cell)` pair.
