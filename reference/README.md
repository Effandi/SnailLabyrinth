# Snail Labyrinth — headless Python reference implementation

A pure-stdlib, deterministic, engine-agnostic reference implementation of
the simulation core described in `../SNAIL_LABYRINTH_TECHNICAL_SPEC.md`
(authoritative) and `../DECISIONS.md` (locked decisions). It exists to be an
executable oracle the later Godot/GDScript port is checked against — see
`HT-1`. No third-party packages; no Godot.

## Running the tests

From this directory:

```
python3 -m unittest discover -v
```

Or, from the repository root:

```
python3 -m unittest discover -s reference -v
```

Every test cites the spec rule id(s) it verifies in its name and/or
docstring, per the project's testing policy.

## Layout

```
reference/
  snail_labyrinth/        # the SimCore package
    directions.py         # TM-2: direction bits, cw/ccw/opp, orbit
    tile.py                # TM-3, TM-5: mask -> shape, rotation-noop facts
    board.py               # TM-6, TM-8, TM-9, TM-10: grid state, mutual connectivity
    transit_graph.py        # TM-11, TM-12: carries(), G_T, BFS reachability
  tests/                   # unittest suite, one file per module above
  PROGRESS.md              # what's implemented, what's next — read this first
  OPEN_QUESTIONS.md        # ambiguities not resolved by the spec, with reasoning
```

## Status

See `PROGRESS.md` for exactly what is implemented and what the next
increment should be.
