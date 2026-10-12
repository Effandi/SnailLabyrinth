# Snail Labyrinth — Python Reference Implementation

A headless, pure-Python-3-standard-library reference implementation of the
simulation core described in `SNAIL_LABYRINTH_TECHNICAL_SPEC.md`. This is
the oracle the eventual Godot/GDScript port is checked against — it is not
the shipping game.

No third-party dependencies. No Godot. No GDScript.

## Running the tests

From the `reference/` directory:

```sh
cd reference
python3 -m unittest discover -v
```

Or from the repository root:

```sh
python3 -m unittest discover -s reference -t reference -v
```

Both are equivalent; `-t reference` sets `reference/` as the top-level
directory so `import sim.tiles` resolves regardless of your current working
directory.

## Layout

```
reference/
  sim/                  the simulation core (SimCore, HT-1)
    tiles.py            TM-1..TM-10: coordinate system, tile masks, connectivity
    transit_graph.py     TM-11, TM-12: the transit graph G_T and its BFS
  tests/
    test_tiles.py
    test_transit_graph.py
  PROGRESS.md            what's implemented, what's next (read this first on resume)
  OPEN_QUESTIONS.md       ambiguities found in the spec and the reading adopted
```

## Conventions

- Every rule implemented cites its spec rule id (`TM-3`, `GE-1`, ...) in a
  comment at the point it is implemented.
- Every test cites the rule id it verifies, in the test name or a docstring.
- All arithmetic is integer; no floats appear anywhere in simulation state
  (`SM-1`, `MG-2`).
