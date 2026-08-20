# Snail Labyrinth — Locked Developer Decisions

Decided by the developer in session. These override anything in GDD.md that conflicts, and
override any recommendation in SNAIL_LABYRINTH_TECHNICAL_SPEC.md §0.

---

## D1 — Engine: Godot 4.7.1 stable  **[SETTLED]**

Already installed with export templates and a configured portable Android SDK/JDK; the
Blender 4.4 -> glTF/GLB -> Godot asset path is verified working. `--headless` gives the §12 test
harness for free.

Toolchain gotchas that apply (from the developer's own notes):
- Android export needs `rendering/textures/vram_compression/import_etc2_astc=true` in `project.godot`.
- Godot rewrites `editor_settings-4.7.tres` on exit; Android export settings must be re-applied and
  the export run **in the same shell invocation**.

---

## D2 — Player count and match structure: **4 players, free-for-all**  **[SETTLED — CORRECTS THE GDD]**

**The GDD's "4v4, 8 snails, two teams" is withdrawn by the developer.** The game is
**1 versus 3 other players — 4 players total, no teams.**

This is a correction to GDD §2, not a scope cut. Consequences, all simplifications:

| GDD as written | Corrected |
|---|---|
| 8 snails, 2 per side, ambiguous team-to-side mapping | **4 snails, exactly one per side** — N/S/E/W maps 1:1, no assignment problem |
| Team win condition vs first-past-the-post tension (spec `MR-1`) | **First-past-the-post is now correct by construction.** `MR-1`'s objection dissolves — there are no teammates whose position could matter |
| §16 HUD "Team A: 2/4 reached center" | 4-player placement ladder (1st/2nd/3rd/4th) |
| Freeze must pick among 7 opponents | **3 opponents** — a 3-way radial, no scrolling target list |
| Hot-seat needs 8 input devices | **4 input devices** — actually achievable on one machine |
| Spawn fairness across 8 spawns in 4 groups | 4 spawns, 4-fold rotational symmetry — a much stronger fairness guarantee is available |

Spec sections requiring rewrite for this: §2.2 (spawns and teams), §7 `MR-1`, §9 (HUD/camera),
§13 (v1 slice), and every "8 snails" / "up to 7 opponents" count.

---

## D3 — v1 multiplayer scope: hot-seat / shared screen  **[SETTLED]**

One machine, one shared camera framing the whole labyrinth, up to 4 humans, bots filling empty
slots. No netcode in v1.

Note this **overrides spec §0 D2's recommendation** of "local, 1 human + 3 bots". The developer
chose hot-seat. With the D2 correction to 4 players this is now far more practical — 4 gamepads on
one machine is an ordinary setup.

Consequence the spec must absorb: the shared whole-board camera means **every player can see the
entire board at all times**. Freeze's unrestricted "select any opponent" targeting is only
reasonable *because* of this. When online play arrives (M1), free targeting must be re-examined —
picking a target you cannot see is a different and worse mechanic.

The simulation core must still be a deterministic, engine-independent module so online play can be
layered on later without a rewrite.

---

## D4 — GDD §20 "loadable when generating the next version": **not literal**  **[SETTLED]**

The developer's ruling: **ignore the regeneration reading.** §20 means only "do not clobber my
tuning".

Consequences:
- §11 (the AI config handoff protocol) collapses to: detect a saved config, ask once, apply or
  ignore. No schema-migration framework.
- Roughly 3 weeks of specified work is cut.
- **Keep the schema version stamp anyway.** It costs one field and it is the only thing that makes
  a migration framework addable later without invalidating every config saved before then.

---

## D5 — New card: Card 6, Freeze  **[SETTLED, with open balance risk]**

Rare card. Freezes a selected opponent.

| Property | Value |
|---|---|
| Effect | Target **fully locked out** — no movement, no card play, no targeting, no collection |
| Duration | **20 s** (dev-tunable) |
| Targeting | Caster **freely selects** any opponent snail. Not facing-limited, not radius-limited |
| Draw weight | **2%** |

### Two hard problems this creates (both must be fixed in the spec)

1. **Freeze is currently undrawable.** Spec `CD-17` draws from a shuffled bag of 20 with
   composition by largest-remainder apportionment. `2% x 20 = 0.4`, which apportions to **zero
   seats**. No bag would ever contain a Freeze card. *No legal bag size expresses 2% either* — the
   fix must change the mechanism, not the number. This is a blocker.

2. **The theorem's liveness property becomes false.** Spec `AS-1` asserts P1: "at every instant
   every snail has at least one legal play, and is never unable to act for longer than one global
   cooldown." A frozen snail violates this by design for 20 s. P1 must be **split** into board
   liveness (a route exists), agency liveness (the player can act), and bounded denial (how long
   agency may be suspended) — otherwise `AS-3`'s theorem and the §12.1 liveness fuzz test both
   break the day Freeze ships.

   The theorem's *conclusion* survives: `AS-3` rests on `CD-13` condition 6 (transit-graph
   invariant) and condition 2 (occupied cells are never rockable), neither of which depends on the
   victim being able to act. A frozen snail can be delayed but still cannot be entombed —
   **provided condition 6's "every live snail" is explicitly stated to include frozen snails.**

### Balance risk, recorded as evidence rather than as a veto

Spec `MR-5` derives a target match length of **40-90 s** at 16x16. A 20 s lockout is **22-50% of
the entire race**, against a benchmark where the game's existing power pickup (a gem) gives +20%
speed for 5-10 s. Analysis put Freeze at roughly **14x a gem's swing**. 20 s ships as specified and
is tunable; expect playtest to pull it down.

### Guard rules (developer to confirm or override)

- **No re-freeze while frozen.** Card not consumed on an invalid target, so the attempt is not wasted.
- **Post-freeze immunity, 3 s.** Flagged by analysis as insufficient on its own — with 3 opponents
  able to chain, 3 s is a duty cycle rather than a mitigation. Needs raising or a per-victim
  freeze budget per match.
- **Cannot target a finished snail** (spec `MR-8` keeps finished snails rendered and clickable, so
  without this rule targeting one is a silent 2% card burn).
- **Mid-edge freeze must not create a 20 s two-cell targeting-immunity field.** `CD-12`'s edge lock
  makes both cells of a moving snail untargetable; freezing a snail mid-edge would extend a 0.8 s
  lock to 20 s. Resolution: the snail completes its current edge, then locks at the node.
- **Timers that must pause while frozen:** gem boost (otherwise Freeze silently also destroys a gem
  the victim took a detour for), card cooldowns, refill delay. The match clock and hard timeout
  keep running.

### Renormalized distribution

| Card | Original | With Freeze |
|---|---|---|
| Rotate Any Direction | 25% | 24% |
| Rotate Clockwise | 25% | 24% |
| Rotate Anti-Clockwise | 25% | 24% |
| Rock Blocker | 15% | 16% |
| Wildcard | 10% | 10% |
| **Freeze** | — | **2%** |

Analysis flagged that renormalising the other five is arguably the wrong move — leaving them and
letting Freeze occupy a separate rare slot outside the bag is cleaner. Resolve when the bag fix
lands.

---

## Still open

- Match length target confirmation (drives whether 20 s is proportionate).
- Whether Freeze is telegraphed to the victim at all.
- Whether a frozen player may pre-select a card / queue a facing while locked out — this is the
  boundary of "fully locked out" and it decides whether a 20 s wait is bearable in a shared room.
- Junction control policy (spec §0 D3): `intent_then_stop` recommended, `intent_then_seek` behind
  a flag, settle in playtest one.
