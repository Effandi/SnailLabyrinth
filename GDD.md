# Snail Labyrinth — 4v4 Puzzle Race
## Game Design Document (as supplied by the developer, verbatim intent)

## Game Concept

Create a 4 vs 4 multiplayer competitive puzzle-racing game featuring snails navigating a
dynamically generated labyrinth.

Each player controls a snail starting from one of the four sides of the map. The objective is to
manipulate the road tiles and create a continuous pathway from the player's starting position
toward the center of the labyrinth, where the finishing point is located.

The first snail to successfully reach the center wins.

Core gameplay combines: puzzle solving, real-time decision making, tile manipulation,
resource/card management, racing, strategic blocking, randomized maps, risk vs reward exploration.

The game should be easy to understand but become increasingly strategic as players learn how to
manipulate the labyrinth efficiently.

## 1. Camera & Presentation

Camera:
- Isometric / 3D top-down view
- Camera should clearly show the surrounding labyrinth
- Slight camera elevation so players can easily identify road directions
- Smooth camera tracking following the player's snail
- Zoom out slightly when important sections of the map need to be visible

Visual Style:
- Stylized 3D game art
- Cute, expressive snails
- Colorful but readable environment
- Clear road markings and tile boundaries
- Strong visual distinction between different road types
- Road direction must be immediately understandable from the camera

The game should feel playful and accessible while maintaining enough visual clarity for
competitive puzzle gameplay.

## 2. Match Structure

Players: 8 total
Teams: Team A = 4 snails, Team B = 4 snails

Starting Positions: North, South, East, West.
Each team should have two snails positioned on opposite or strategically separated starting areas.

The center of the map is the final destination.

Winning Condition: the first snail to reach the center finishing area wins the match.

Optional future modes: first team to get 2 snails to the center; first team to get all 4 snails to
the center; individual race mode; time attack; survival labyrinth.

## 3. Labyrinth Map

Grid-based tile system. Example: 16 x 16 grid.

Every grid cell contains one randomly generated road configuration. Each tile must connect to
neighbouring tiles using four possible directions: North, East, South, West.

The initial labyrinth is randomly generated at the beginning of every match. The objective is to
manipulate tiles and create a continuous road from the snail's current location toward the center.

## 4. Road Tile Types

- **Straight Road** — North<->South, or East<->West
- **90-Degree Junction** — North<->East, East<->South, South<->West, West<->North
- **T-Junction** — three connected directions (e.g. North + East + West)
- **Cross Junction** — four-way: North + East + South + West
- **Dead End** — one connected direction. The snail can only enter/exit through the available
  road connection.
- **Rock Blocker** — completely blocked grid. No snail can travel through the tile. Rock blockers
  can be strategically used to obstruct opponents or alter available routes.

## 5. Core Puzzle Mechanic

The central mechanic is changing the orientation of road tiles.

A player looks toward a grid tile and uses a card to manipulate that tile.

Example: a tile currently North<->South; the player uses a clockwise rotation card; the tile
becomes East<->West. This immediately changes the available route.

Players must continuously evaluate: Where am I? Where is the center? Which tiles are connected?
Which route is shortest? Which opponent is approaching? Should I create my own route? Should I
block an opponent? Should I save a powerful card?

## 6. Card System

Each snail has a hand of cards.
- Default snail: 4 card slots
- Stronger snail: maximum 6 card slots

Every time a card is consumed the player immediately receives a new random card from the card
pool. Continuous tactical loop: Use Card -> Modify Labyrinth -> Receive New Card.

Players should never permanently run out of cards during normal gameplay.

## 7. Card Types

**Card 1 — Rotate Any Direction.** Rotate the targeted grid tile to any valid orientation.
Target: tile directly facing the snail. Most flexible basic manipulation card.

**Card 2 — Rotate Clockwise.** Rotates the targeted tile 90 degrees clockwise.
The player must understand the current orientation of the tile before using the card.

**Card 3 — Rotate Anti-Clockwise.** Rotates the targeted tile 90 degrees counter-clockwise.

**Card 4 — Rock Blocker.** Converts a selected grid into a Rock Blocker. Unlike normal rotation
cards, this card can target **any selected grid within the allowed range**, rather than only the
tile directly facing the snail. Used offensively or defensively: block an opponent's shortcut,
close a dangerous route, force opponents to take a longer path, protect a player's route, create
temporary strategic barriers.

**Card 5 — Wildcard.** The most powerful card. Select a grid directly facing the snail and
transform it into any available road configuration or Rock Blocker (Straight, T-Junction, Cross
Junction, 90-Degree Junction, Dead End, Rock Blocker). This card should be rare.

## 8. Facing Mechanic

Cards that affect the facing grid should clearly show the target tile. When the snail faces a grid:
- Highlight the targeted tile
- Display a preview of the card effect
- Show the resulting road configuration
- Allow the player to confirm before applying the card

The tile changes immediately on confirm. This system should make the puzzle mechanics easy to
understand for new players.

## 9. Collectable Extra Card Slots

Special Card Upgrade Collectibles are placed throughout the labyrinth. Collecting one gives
Maximum Card Slots +1 (4/4 -> 5/5 -> 6/6, maximum 6).

Extra card-slot collectibles should be strategically placed in areas that require players to take
risks or move away from the optimal route. This creates a strategic choice: shortest route to the
center vs. a slightly longer route to collect additional resources.

## 10. Gem System

Gems are scattered throughout the labyrinth. Collecting a Gem grants Movement Speed +20%,
temporary, recommended default duration 5–10 seconds. Display the boost clearly around the snail
("GEM COLLECTED! SPEED +20%").

Uses: catch opponents, escape opponents, reach the center faster, recover from taking a longer
route, take calculated risks when collecting resources.

Multiple Gems should not stack infinitely. Use a configurable maximum stack, or refresh the
duration when another Gem is collected.

## 11. Snail Movement

Snails automatically travel along connected roads.

The player primarily controls: direction/facing, tile manipulation, card selection, strategic
positioning.

The snail should not require traditional joystick movement as the primary gameplay mechanic.
The core challenge should be: solve the road faster than the opposing players.

Movement speed must be configurable through the Developer Settings.

## 12. Road Validation

The game must continuously evaluate whether the current road configuration allows the snail to
move forward. A snail can only travel through connected road segments.

If a road ends at a Dead End: the snail stops; the player must manipulate another tile; the player
needs to create a new route.

If the road connects to the center: the snail automatically continues toward the finish.

The game should provide subtle visual feedback showing the currently connected route.

## 13. Competitive Gameplay

Players should be able to interfere with opponents indirectly:
- **Blocking** — place a Rock Blocker in front of an opponent
- **Route Manipulation** — rotate a shared tile to break an opponent's route
- **Race** — two snails may approach the same intersection and compete for the optimal path
- **Resource Competition** — players race toward Gems, Extra Card Slots, strategic tiles

The game should encourage players to constantly decide between: Solve -> Race -> Block ->
Collect -> Re-route.

## 14. Map Generation

Generate a new random labyrinth at the beginning of every match. The procedural generator must
ensure:
- The map is playable
- Every starting area has at least one possible route toward the center
- The center is reachable
- Road orientations are randomized
- Dead ends and blockers are distributed throughout the map
- Gems and Card Upgrade collectibles are randomly scattered
- No starting snail spawns inside an impossible route
- The map provides multiple possible routes to the center

The map should feel different every match.

## 15. Difficulty & Dynamic Challenge

As the match progresses the labyrinth should become increasingly difficult to solve. Possible
future mechanics: more Rock Blockers, more Dead Ends, longer routes, more complex intersections,
reduced card availability, moving obstacles, temporary blocked tiles, special event tiles.

Do not make the initial prototype overly complicated. Focus on proving the core:
Manipulate -> Navigate -> Race -> Reach Center.

## 16. User Interface

Top HUD: "Team A: 2 / 4 reached center", "Team B: 1 / 4 reached center".

Player HUD: "Cards: 4 / 4". Card icons large and readable, e.g. [ CW ] [ CCW ] [ ANY ] [ ROCK ].
Show the currently selected card prominently.

Gem Boost: display "SPEED +20%" with a countdown timer.

Map Information: optional minimap showing player location, teammates, opponents, center, major
collectibles.

## 17. Snail Classes

For future balancing:
- **Normal Snail** — 4 card slots, standard speed, standard acceleration
- **Strong Snail** — up to 6 card slots, slightly slower movement, better card capacity
- **Fast Snail** — higher movement speed, smaller card capacity
- **Strategist Snail** — standard movement, better access to powerful cards

Do not overcomplicate class abilities in the first prototype. The initial prototype should
primarily test the labyrinth + cards + racing gameplay.

## 18. Developer Settings Tab

A dedicated Developer Settings tab inside the game, for designers/developers to tune gameplay
parameters without modifying code. All settings saved into a persistent configuration file. The
saved configuration should be loadable when generating the next version of the game.

**Map Settings**
- Map Size Grid: 8x8, 12x12, 16x16, 20x20, 24x24; allow custom numeric values

**Gem Settings**
- Total Gems (e.g. 10)
- Gem Scatter Density (Low / Medium / High)
- Gem Minimum Distance (how close gems can spawn to each other)
- Gem Boost Speed (default 20%)
- Gem Boost Duration (default 5–10 seconds)

**Card Collectible Settings**
- Total Card Slot Collectibles (e.g. 8)
- Card Collectible Scatter Density (Low / Medium / High)
- Maximum Card Slots (default 6)

**Snail Settings**
- Base Snail Speed (e.g. 5.0)
- Acceleration (e.g. 2.0)
- Maximum Speed (e.g. 8.0)
- Starting Card Slots (default 4)
- Maximum Card Slots (default 6)

**Card Distribution Settings** — editable probability of receiving each card:
| Card | Probability |
| Rotate Any Direction | 25% |
| Rotate Clockwise | 25% |
| Rotate Anti-Clockwise | 25% |
| Rock Blocker | 15% |
| Wildcard | 10% |

## 19. Save / Load Developer Settings

Developer Settings must include: Save Settings, Load Settings, Reset to Default, Export Settings
(for the development team or AI game-generation workflow), Import Settings.

## 20. AI Settings Integration

When generating a new version of the game, the AI should detect whether a saved Developer Setting
configuration exists. Before generating the next version, the AI must explicitly ask the developer:

"A tuned Developer Setting configuration has been detected. Would you like to use the saved
settings for this version?"

Provide: Use Tuned Settings, or Use Default Settings.

If Use Tuned Settings: apply all saved parameters to the new game build.
If Use Default Settings: ignore the saved configuration and use default prototype values.

The AI should never silently overwrite or ignore tuned developer settings.

## 21. Prototype Objective

The primary objective is to test whether the grid manipulation + racing mechanic is fun.

Most important gameplay loop:
Spawn -> Observe Labyrinth -> Select Card -> Manipulate Tile -> Create Route -> Move -> Collect
Resources -> React to Opponents -> Manipulate More Tiles -> Reach Center

Prioritise: fast gameplay, easy-to-understand road manipulation, clear card feedback, interesting
route decisions, competitive racing, randomized labyrinths, replayability.

Avoid adding unnecessary systems until this core gameplay loop is proven fun.

## 22. Prototype Acceptance Criteria

The prototype should demonstrate: 8 playable snails; 4v4 team structure; grid-based labyrinth;
four starting sides; central finishing point; random road generation; straight roads; T-junctions;
cross-junctions; 90-degree junctions; dead ends; rock blockers; four starting cards; random
replacement cards; up to six card slots; rotate-any-direction card; clockwise rotation card;
anti-clockwise rotation card; Rock Blocker card; Wildcard; gem collectibles; 20% temporary speed
boost; extra card-slot collectibles; multiplayer competition; Developer Settings panel; save/load
configuration; AI confirmation before applying tuned settings.

The final prototype should feel like a combination of a real-time puzzle game and competitive
race, where players are constantly solving the labyrinth while simultaneously reacting to what the
opposing team is doing.

## Core Design Philosophy

"Don't just find the road — build the road while racing."

---

## Known project context (not part of the original GDD)

- Repository: https://github.com/Effandi/SnailLabyrinth  (currently empty: one commit, README only)
- Developer's installed toolchain: Godot 4.7.1 stable (Windows, not on PATH), Blender 4.4.0,
  portable Android SDK/JDK at C:\AndroidDev. Godot export templates and Android export are
  already configured on this machine.
- The GDD does **not** state a target engine, a networking model, or a target platform.
