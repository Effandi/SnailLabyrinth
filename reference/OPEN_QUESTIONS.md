# Open Questions / Ambiguities

Recorded per the build process rules: where the spec is silent or ambiguous,
implement the most defensible reading and log the ambiguity here with the
rule id and reasoning. Nothing below blocks the current increment; all are
implementation notes for whoever builds the next layer on top.

## TM-3 — canonical "rotation index" is not actually defined by the spec

TM-3's claim "the mapping mask <-> (shape, rotation) is a bijection" treats
`rotation` as an informal concept (it appears in the table only as a
*count* of distinct rotations per shape, e.g. "4" for Dead End, "2" for
Straight). The spec never states which orbit member is rotation-index 0 for
a given shape.

**Reading adopted:** for the headless-testable-core invariant (HT-1 §12.1,
"mask <-> (shape, rotation) is a bijection over all 16 masks"), rotation
index is defined relative to each shape's *canonical* orbit member
(`min(orbit(m))`), counted in `cw()` steps from that canonical mask. This is
an internal test-only convention — it is never serialized, never compared
across modules, and nothing in the spec's wire format or save format
depends on it (TM-3 is explicit that only the mask itself is ever stored:
"Shape and rotation are derived, never stored"). No spec rule is at risk
from this choice; it only affects how `reference/tests/test_tiles.py`
proves the bijection property.

## TM-10 — border-tile rotation legality is a card-system concern, not tile-model

TM-10 ("Rotating a border tile is legal whenever the mask changes, even if
effective connectivity does not") is a *legality* rule for the card system
(CD-*), which this increment does not implement yet. `reference/sim/tiles.py`
provides the pure mask/connectivity primitives TM-10 depends on
(`cw`/`ccw` always produce a new mask when the input isn't a fixed point;
`Grid.set_mask` always accepts any 4-bit value), but the actual "is this
card application legal" predicate belongs with the CD-* increment. No
action needed now; flagging so the next increment's author knows TM-10 is
still unimplemented, not forgotten.
