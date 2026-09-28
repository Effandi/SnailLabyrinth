# Snail Labyrinth — headless reference implementation

A pure Python 3 (standard library only) reference implementation of the
Snail Labyrinth simulation core, built directly against
`SNAIL_LABYRINTH_TECHNICAL_SPEC.md`. This is the oracle the eventual Godot
port is checked against — it is not a game, has no rendering, and does not
depend on Godot.

## Running the tests

From the `reference/` directory:

```
python3 -m unittest discover -v
```

No third-party packages are used or required. `python3 -m unittest
discover` (without `-v`) or `python3 -m unittest <module>` also work.

## Layout

```
reference/
  snail_labyrinth/     the implementation package
    tiles.py           TM-1 .. TM-10: the tile model and connectivity
    transit.py         TM-11, TM-12: the transit graph G_T
  tests/
    test_tiles.py
    test_transit.py
  OPEN_QUESTIONS.md     ambiguities found in the spec and how they were resolved
  PROGRESS.md           what's implemented, what's next
```

## Conventions

- Every test cites the spec rule id(s) it verifies, in its name or docstring.
- All arithmetic is integer; there is no floating point and no wall-clock
  dependency anywhere in `snail_labyrinth/`.
- See `PROGRESS.md` for exactly which spec rules are covered so far and what
  the next increment should build.
