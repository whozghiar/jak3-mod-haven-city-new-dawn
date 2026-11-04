# Haven City: New Dawn — How it works

This document explains, feature by feature, how Haven City: New Dawn rebuilds Jak 2's Haven City
inside Jak 3: what you see in game, how it is made, why it is made that way, and where the code
is. It is written for a developer new to GOAL. Read sections 1 to 4 of the
[developer guide](haven_city_new_dawn_readme.md) first: they explain processes, hooks, art groups
and the level port, which this document uses everywhere. The war mode, the color variants and the
change log are in the guide too.

**Contents**

1. [Words used in this document](#1-words-used-in-this-document)
2. [Where things are](#2-where-things-are)
3. [Building it from scratch](#3-building-it-from-scratch)
4. [The city: a hub and 15 districts](#4-the-city-a-hub-and-15-districts)
5. [Loading levels like Jak 2](#5-loading-levels-like-jak-2)
6. [Places, doors and elevators](#6-places-doors-and-elevators)
7. [Jak 2's models in Jak 3](#7-jak-2s-models-in-jak-3)
8. [Traffic](#8-traffic)
9. [Sound and music](#9-sound-and-music)
10. [Time of day, weather and light](#10-time-of-day-weather-and-light)
11. [Travelling and saving](#11-travelling-and-saving)
12. [Mini-games](#12-mini-games)
13. [Changes to the C++ tools](#13-changes-to-the-c-tools)
14. [Installing from the launcher](#14-installing-from-the-launcher)
15. [Jak 2 and Jak 3: what differs](#15-jak-2-and-jak-3-what-differs)
16. [Memory](#16-memory)
17. [Debugging](#17-debugging)
18. [Not done yet](#18-not-done-yet)

## 1. Words used in this document

| Word | Meaning |
|---|---|
| Level | A piece of the world loaded and unloaded as a whole: background, collision, actors. The mod adds 46 |
| DGO | The file a level loads from: its code, models and data, named after the level's nickname (`HJ2.DGO`) |
| bsp | The level's main data inside its DGO: collision, actors, regions, navigation |
| `.fr3` | The PC copy of a level's graphics, read by the PC renderer |
| Actor (entity) | Something a level places: a door, a crate, a lamp. The game starts a process for it when Jak comes close |
| Lump | A named value stored on an actor: a path, a script, a model name |
| Region | An invisible plane or volume that runs a script when Jak or the camera crosses or enters it |
| Continue point | A place where Jak starts or respawns, with the list of levels to load there |
| Hub, district | The city is one hub level (the walls, the palace, the far scenery) plus one level per district |
| Place | Any other level reached from the city: an interior, Dead Town, Haven Forest... |
| Rip | A model the decompiler exported from Jak 2 as a `.glb` file |

## 2. Where things are

| What | Where | Written by hand |
|---|---|---|
| The level port, the tool that turns Jak 2's data into Jak 3 levels | `scripts/level_port/` ([its README](../../../scripts/level_port/README.md)) | Yes. It knows nothing of this mod |
| This mod's data for the level port: levels, doors, models, sounds | `custom_assets/jak3/ports/jak2-haven-city/port.jsonc` (the manifest) | Yes |
| Level files | `custom_assets/jak3/levels/havenj2/`, `custom_assets/jak3/levels/hj2-*/` | No, generated |
| Models | `custom_assets/jak3/models/custom_levels/hj2-*.glb` | No, generated |
| Code every level shares, in GAME | `goal_src/jak3/pc/features/jak2-haven-city-*.gc`, `goal_src/jak3/levels/havenj2/hj2-common-obs.gc`, `havenj2-ocean.gc` | Yes, but `jak2-haven-city-levels.gc` |
| Code of one level, in its DGO | `goal_src/jak3/levels/havenj2/` | Yes, but the `*-part.gc`, `*-ocean.gc` and height map files |
| The war mode's part of a city | `goal_src/jak3/levels/city/war/` | Yes |
| Lines changed in Jak 3's own code | marked `og:jak2-haven-city added` | Yes |
| C++ changes | `decompiler/`, `goalc/build_level/`, `tools/fr3_check.cpp`, `game/overlord/jak3/`, `game/system/crash_report.cpp` ([13](#13-changes-to-the-c-tools)) | Yes |

**Where a class goes.** A class that two levels loaded together both place goes in GAME. When a
level unloads, every type its code defined is erased (its symbol becomes 0), even if actors of the
other level still use it. Example: the windmills stand on the palace roof and on the palace
cable, two levels loaded together, so `hj2-pal-windmill` is in GAME's `hj2-common-obs.gc`. The
hub's DGO (HJ2) holds the code of every district's actors, since a district is never loaded
without its hub ([5.1](#51-jak-2s-scripts-do-the-loading)).

**Generated files are never edited.** The level port lists every file it writes in a block of
`.gitignore`. To change a level, change the manifest (or the tool, when the fix is about Jak 2,
Jak 3 or how levels are built), then run the level port again.

## 3. Building it from scratch

1. Build the tools. The level port's particle step runs `fr3_check`, so build it too:

   ```bash
   task build-release-decomp
   task build-release-game
   cmake --build out/build/Release --target fr3_check --config Release
   ```

2. Copy each disc's files into `iso_data/jak2` and `iso_data/jak3`. The mod is made with the
   European Jak 2 (PAL, SCES-51608) and the American Jak 3 (NTSC-U, SCUS-97330); other regions are
   untested.
3. Run the level port. Its first step extracts what is missing (with no Jak 2 rip at all, the whole
   of Jak 2 once: about 11 GB), then it writes about 300 files:

   ```bash
   task level-port -- custom_assets/jak3/ports/jak2-haven-city/port.jsonc
   ```

4. Build: `task repl`, then `(mi)`.
5. Check a level offline. `total: 0 errors` is expected:
   `out/build/Release/bin/fr3_check.exe out/jak3/fr3/havenj2.fr3`.
6. Play: `task boot-game`, then L3 + SELECT, Mods, Haven City: New Dawn, Warp to Haven City (Jak 2).

What to redo after a change:

| You changed | Redo |
|---|---|
| The manifest or the level port | The level port, then `(mi)`. Only files whose content changed are rewritten, so only those levels rebuild |
| A `.gc` file | `(mi)` |
| The level builder (`goalc/build_level`) | `task build-release-game`, touch the level's `.jsonc`, `(mi)` |
| The decompiler | `task build-release-decomp`, the level port (it extracts the stale levels again), `(mi)` |
| A texture | See below |

**Textures.** The mod's texture pack is a Jak 3 pack, zipped in
`docs/modding/current_mod/texture_packs/`. To work on it, unzip it into
`custom_assets/jak3/texture_replacements/` (gitignored). What comes from Jak 2 (backgrounds,
rebuilt models, particles) takes a PNG when the level port extracts Jak 2 again, which it does by
itself for the levels older than the newest PNG. What comes from Jak 3 (the guards, citizens,
vehicles) takes it at the build: `(make-group "iso" :force #t)`. A PNG named like a Jak 3 texture
also changes Jak 3's own levels: that is what a Jak 3 texture pack does. The color variants'
textures are explained in the [guide, 6.4](haven_city_new_dawn_readme.md#64-the-variants-textures-in-a-texture-pack).

**This worktree's Jak 2 extraction is its own.** Other worktrees share the main folder's
`decompiler_out/` and `out/` through junctions; here `decompiler_out/jak2` and `out/jak2` are real
folders, so the mod's texture pack applied to Jak 2 never changes the other mods. Before
`git worktree remove`, `rmdir` the junctions `decompiler_out\jak1` and `decompiler_out\jak3`.

## 4. The city: a hub and 15 districts

**What you see:** Jak 2's Haven City with its lighting, collision, props, water, particles and neon
signs, loaded district by district as Jak moves.

**How:** like Jak 2, the city is split in levels:

- the hub, `havenj2` (Jak 2's `ctywide`): the city walls, the palace, the far scenery, the traffic
  code and the code of every district's actors. Jak is never "in" the hub (level flag
  `not-physical`);
- one level per district, each with its background, collision, navigation, props and continue
  points. At a border, Jak waits for the next district if it isn't loaded yet (`display-wait`).

| District | Levels |
|---|---|
| Slums | `hj2-slma`, `hj2-slmb`, `hj2-slmc` |
| Port | `hj2-port` |
| Bazaar (market) | `hj2-marka`, `hj2-markb` |
| Industrial section | `hj2-inda`, `hj2-indb` |
| Main town | `hj2-gena`, `hj2-genb`, `hj2-genc` |
| Gardens | `hj2-farma`, `hj2-farmb` |
| Palace plaza | `hj2-pal` |
| Stadium grounds | `hj2-stdm` |

**Why:** the city was first one level: its `.fr3` was 285 MB, five times what Jak 2 keeps loaded,
and the low-res city showed in the palace lobby. Split like Jak 2's, it loads through Jak 2's own
scripts ([5](#5-loading-levels-like-jak-2)).

### 4.1 Background and collision

- The level builder imports Jak 2's `.fr3` file of each level as it is (`import_fr3`): its
  geometry with its time-of-day colors, and its collision with each triangle's surface type. Jak 2
  and Jak 3 store surface types the same way, so nothing is re-baked.
- `collision_bounds` drops the collision of far scenery Jak can't reach. Without it, the
  kilometer-wide mountains overflowed the collision tables (the pumping station alone made a 70 MB
  table).
- The sky is drawn only while a loaded level has the `sky` flag; every outdoor level has it.

### 4.2 Props and city actors

- **Market and farm props** (1126 crates, baskets, fruit stands, crops): Jak 3 still ships Jak 2's
  classes and models for them, so the mod places Jak 3's own. They break like Jak 2's.
- **Farm crops:** Jak 3 keeps them as scenery. `havenj2-farm.gc` ports Jak 2's class: solid, shaken
  by a light hit, burst by a strong one.
- **Still props** are baked into one mesh per level (`<level>-mesh.glb`), with an invisible
  collision box where Jak can touch them: one mesh draws much faster than hundreds of actors.
- **Jak 2's own actors**, rebuilt with Jak 2's models (`havenj2-obs.gc` unless noted):

| In game | Class | Notes |
|---|---|---|
| Palace gate | `hj2-palace-door` | Jak 3 has none. It really closes: the city is hidden in the lobby behind it |
| Propaganda speakers | `hj2-propa` | The Baron's hologram and speeches; two hits break one. In French with the war off, the speakers say Torn's lines (the owner's own recordings, `custom_assets/jak3/ports/jak2-haven-city/voices/`) |
| Neon signs | `havenj2-signs.gc` | Blink in random patterns like Jak 2's |
| Anti-air turrets | `hj2-cty-guard-turret` | Rise during an alert when Jak drives within 100 m, fire, sink 120 m away. Blue out of the war, red during it |
| Street lamps | `hj2-ctyn-lamp` | Snap when Jak or a vehicle hits them |
| Parked vehicles | `hj2-parking-spot` | 49 spots, each spawning a traffic vehicle |
| Force-field walls | `hj2-security-wall` | Open: at the end of the game Jak owns every pass |
| Searchlights | Jak 3's `searchlight` | |
| Barges | `hj2-boat-manager`, `hj2-barge` (`hj2-port-obs.gc`) | Sail the port's canals |
| Yakows | `hj2-yakow` | Graze and wander in the gardens |

### 4.3 Particles and their textures

**What you see:** smoke, fires, fountains, neon glows, race posters.

**How:** the level port translates Jak 2's particle definitions into GOAL files
(`havenj2-part.gc` for the city, `hj2-<place>-part.gc` for a place), gives them ids that no Jak 3
code uses, and places Jak 2's part spawners. Jak 2 callbacks that Jak 3 lacks are copied from Jak
2's code, renamed `hj2-*`, with the data they read.

Three traps, each met on the way:

1. **White squares mean a missing texture page.** Jak 2 draws particles from a texture page of the
   level; Jak 3 has no such page for Jak 2's levels. The level builder copies the textures into a
   page of the level's own (1566 for the city), and GAME code registers it while the level is
   loaded. When a lookup fails, the particle is drawn with `common-white`: a white square.
2. **Texture page ids can overlap.** The PC texture pool gives each page id as many slots as Jak 3's
   page of that id has textures. An id Jak 3 never uses has none, so its textures spill over the
   next pages'. The level port picks "auto" page ids whose slots meet no other page of the mod
   (`Allocator`, `scripts/level_port/steps/particles.py`).
3. **Some ids changed meaning.** Jak 2's texture page 12 is its effects page, Jak 3's is the font;
   four particle flag bits moved. The level port translates both
   ([15](#15-jak-2-and-jak-3-what-differs)).

Spawners keep Jak 2's spawn distance (`vis-dist`: 384 m for the signs). Example: the race posters
stand at Jak 2's exact spots, and show the poster Jak 2 shows once every race is won.

### 4.4 Water

- In Jak 3, water is only regions: an invisible volume that says "swim here". The hub has one
  city-wide ocean sphere; pools and fountains get volumes.
- The sea's look comes from an ocean map. GAME holds a copy of Jak 2's city map
  (`*ocean-map-havenj2*`), used by the city, the palace roof and cable, the pumping station and
  Haven Forest; Dead Town and the mountain have their own.
- Jak 3 draws only one ocean: the first displayed level's, in draw order. `hj2-update-ocean-order`
  puts the level Jak is in first; without it, the mountain's ocean hid Haven Forest's.

## 5. Loading levels like Jak 2

### 5.1 Jak 2's scripts do the loading

Jak 2 has no code that loads its city. Scripts on doors, elevators, regions and continue points ask
for levels (`want-levels`) and show or hide them (`want-display-level`). Jak 3 runs the same script
language and the same door and region code, so the mod keeps Jak 2's scripts and translates their
level names (`scripts/level_port/convert/scripts.py`):

| In Jak 2's script | Becomes |
|---|---|
| `ctywide` | `havenj2`, the hub |
| A district (`ctyport`) | Its level (`hj2-port`), with the hub added first |
| Another ported level (`hiphog`) | Its `hj2-*` level (`hj2-hiphog`) |
| A level that isn't ported | Dropped; a door waiting for it stays shut |
| A story check (`task-closed?`) | Answered for the end of the game ([6.2](#62-the-end-of-jak-2s-story)) |
| Dialogs, cutscenes, story changes | Removed |

**Example: the Hip Hog's door** (`hip-door-a-6` in Jak 2's port). Its `on-activate` lump, run when
Jak comes near, holds `(want-load 'ctyport 'ctywide 'hiphog)`. The level port writes
`(want-load 'havenj2 'hj2-port 'hj2-hiphog)` into `hj2-port.jsonc`: the hub first, then the
district, then the place. Its `on-notice` lump, a story check in Jak 2, becomes `'(hj2-hiphog)`:
at the end of the game the door only waits for the Hip Hog to load. Its `on-cross` lump makes the
Hip Hog Jak's level once he walks through.

**Why the hub always goes first:** Jak 3 unloads the most recently loaded level first. The hub
holds the districts' code, so it must load first and unload last. The level port refuses a level
list that loads a district without its hub.

### 5.2 Memory: which levels fit together

Jak 3's level memory has 18 chunks, and each level size takes fixed ones:

| Size | Chunks |
|---|---|
| `large` | 0 to 11, or 6 to 17 |
| `medium` | 0 to 8, or 9 to 17 |
| `small-center` | 6 to 11 |
| `small-edge` | 0 to 5, or 12 to 17 |

Jak 2 uses the same four sizes, and each level takes Jak 2's. The city loads like Jak 2's: the hub
(`small-center`) and two `small-edge` levels, a district and its neighbor or an interior. The level
port lists every set of levels loaded together and checks that it fits; where one doesn't, it
changes the fewest sizes and prints the change. Only Dead Town and the mountain changed, to
`small-edge`: Jak 2 loads them without `ctywide`, here they load with the hub.

A custom level's name has 10 characters at most (the level builder checks it): Jak 2's `forresca`
became `hj2-forta`.

### 5.3 When Jak 2's scripts are not enough

Some of Jak 2's loading planes can be walked around: from the palace plaza to the main town, the
plane that loads the district and the one that shows it are 241 m apart, on different streets.
Jak could then reach a district that wasn't loaded and fall into the void. Two fallbacks in GAME
(`jak2-haven-city-world.gc`) act only in that case:

1. **Swap at display time.** When a script asks to show a district that isn't loaded, the district
   takes the place of a hidden one.
2. **The district guard.** A map of 25 m squares, generated from each district's ground, tells
   which district is under Jak. If that district isn't shown, the guard shows or loads it. It also
   loads, up to 60 m ahead, the district Jak is heading to.

Neither removes a level that a script asked for in the last 5 s. Earlier versions fought Jak 2's
scripts and loaded districts back and forth.

To report a loading problem, read the `hj2:` lines of the game log (`log/jak3.<date>.log`). Each
ends with Jak's position and the frame:

| Line | Says |
|---|---|
| `hj2: script wants <levels>` | A script, door or continue asked for these levels |
| `hj2: script shows <level>`, `hides <level>` | A script showed or hid one of the mod's levels |
| `hj2: guard: under Jak <district> (<state>)` | The district under Jak changed, or its state |
| `hj2: <district> wanted in place of <district>` | A fallback swapped two districts |
| `hj2: <level> waits for the renderer` | Once a second while the renderer lacks the level ([5.4](#54-drawing-a-level-before-jak-reaches-it)) |

### 5.4 Drawing a level before Jak reaches it

On PC, the game loads a district in 0.05 to 0.3 s, but the renderer needs 1.5 to 2.5 s to read and
upload its `.fr3`. Shown before that, a district has collision but nothing drawn. Three hooks in
Jak 3's `level.gc`, off unless the mod sets them, close the gap:

| Hook | What the mod does with it |
|---|---|
| `*pc-renderer-early-level?*` | The renderer starts uploading a mod level as soon as it starts loading |
| `*pc-renderer-prefetch*` | The renderer also loads the nearest districts within 130 m of Jak, before any script asks |
| `*pc-renderer-display-wait?*` | A mod level stays hidden until the renderer has it (6 s at most); Jak waits as at a `display-wait` border, and a door stays shut until then |

The game asks the renderer through `__pc-level-ready?`, a C++ function added for this.

## 6. Places, doors and elevators

**What you see:** 30 places reached from the city through Jak 2's own doors, elevators and air
trains, as they are at the end of Jak 2.

### 6.1 Doors and elevators

- **Doors.** 42 doors use Jak 2's door models in 8 classes (`hj2-common-obs.gc`). Each is Jak 3's
  `com-airlock`, which runs the same scripts as Jak 2's, drawn with Jak 2's model rebuilt by
  `build-actor`. Jak 2's frame numbers are multiplied by 4: `build-actor` plays animations at 60
  frames per second, Jak 2 at 15.
- **A door acts only within 20 m of its height** (`door_height` in the manifest). Jak 3's airlock
  measures its distance to Jak on the ground plane only; Jak 2 got away with it because its
  visibility data paused the doors Jak couldn't see, and custom levels have no visibility data.
  Without the height limit, the doors at the top of the palace pillar, 420 m up, acted on Jak in
  the lobby.
- **Elevators** (`hj2-elevator`, GAME) are Jak 3's elevator with Jak 2's model. Their paths have two
  points: Jak 3's elevator stops at every point of its path.
- **The fortress gates** are `hj2-fort-gate`; Keira's garage has no doors (the owner's choice).
- **Trap:** a door born closed at level load, with Jak on its front side, runs its `on-deactivate`
  script however far Jak is. The palace roof's doors did that and hid the pillar under Jak, who
  died. Their scripts are removed (`script_overrides` in the manifest).

### 6.2 The end of Jak 2's story

Every level is as Jak 2 leaves it once finished. Jak 2 places an actor only when its `kill-mask`
shares no bit with the level's task mask, a value the closed story steps of that area build up.
The level port computes that mask for the end of the game from Jak 2's story steps
(`scripts/level_port/games/jak2.py`, `Story`). Background pieces that depend on the story are
hidden by name: the market roof is broken, Dead Town's tower has fallen.

**Example, and the one exception:** the palace plaza is as it is before Mar's tomb is found, the
Baron's statue still standing on its wall (`story.level_open_tasks` in the manifest). Remove that
key to have the broken statue of the end.

### 6.3 Hazards and moving decor

The rule: everything that can hurt Jak, no enemy.

| Place | Hazards and moving decor |
|---|---|
| Palace cable | Turning nuts, falling platforms, electric fans, rotating gun, gun turrets, searchlights |
| Palace roof | The low-res throne room seen through the glass, the broken energy posts |
| Fortress | Laser turrets, electric belt, the rescue buttons and lights |
| Mountain | The avalanche, the dark eco pool, the temple's puzzles solved |
| Pumping station | Platforms, pistons, the gun buoy that keeps Jak out of the open sea |
| Castle pad, dig | The electric gate; stomp blocks and platforms floating on the lava |
| Haven Forest | Birds and schools of fish |
| Interiors | The Oracle's banners, the hideout's lamp, the garage's curtain, Vin's turbines |

Simple decor uses two base classes in `hj2-common-obs.gc`: `hj2-anim-loop` (plays its idle in a
loop) and `hj2-still-prop` (still and solid), with the macros `def-hj2-anim-loop` and
`def-hj2-still-prop`. **Trap:** a macro exists in a `goalc` session only once its file has been
compiled, and `(mi)` skips up-to-date files. A class in another file can't rely on the macro: write
it out in full (as in `hj2-oracle-obs.gc`).

### 6.4 The places one by one

| Place | Levels | Reached by |
|---|---|---|
| Hip Hog, gun course, Vin's room, hideout, Oracle, Keira's garage | `hj2-hiphog`, `hj2-gun`, `hj2-vin`, `hj2-hide`, `hj2-oracle`, `hj2-garage` | Their doors, with the hub and the door's district |
| Dead Town and the Sage's hut | `hj2-ruins` (the hut merged into it) | The slums' airlock |
| Palace pillar, roof, cable | `hj2-pshaft`, `hj2-proof`, `hj2-pcab` | The palace gate or the main town's cable pillar, then the pillar's elevator |
| Construction site | `hj2-consb`, `hj2-cons` | The industrial section's gate |
| Pumping station | `hj2-atollx`, `hj2-atoll` | The slums' airlock |
| Mountain, temple, canyon | `hj2-mount`, `hj2-mtnx`, `hj2-mincan` | The gardens' airlock, then a warp gate to the top |
| Haven Forest | `hj2-forest`, `hj2-forstb` | The platform riding down the mountain's stream |
| Castle pad, dig | `hj2-caspad`, `hj2-dig`, `hj2-digb` | The port's air train, or on foot from the pumping station |
| Fortress, prison, way out | `hj2-forta`, `hj2-fortb`, `hj2-prison`, `hj2-fexa`, `hj2-fexb` | The slums' fortress gate in; trap doors, a slide and a gate back to the slums |
| Stadium race track | `hj2-stadd` | The stadium's gate |
| Bazaar stall, Onin's tent | `hj2-kiosk`, `hj2-onin` | The bazaar's regions |

Not ported: the inside of the palace (only used by Jak 2's missions), and the places listed in
[18](#18-not-done-yet).

## 7. Jak 2's models in Jak 3

Every Jak 2 model of the mod is a rip rebuilt for `build-actor`, OpenGOAL's tool for custom models,
by `rebuild_model` (`scripts/level_port/common/glb.py`). The manifest's `models` entry says what to
keep; the [guide, 4](haven_city_new_dawn_readme.md#4-from-jak-2s-disc-to-jak-3-levels-the-level-port)
shows one.

| Need | What `rebuild_model` does |
|---|---|
| Only the parts the actor uses | Keeps the listed primitives (`prims`) |
| Collision | A box, or the model's convex hull (at most 255 vertices, `build-actor`'s limit), or one joint's part of the model so it moves with that joint |
| Animations | Keeps the listed clips in the order the GOAL code expects, borrows them from another rip, or writes a one-frame rest pose when the rip has none (`build-actor` needs one) |
| Transparent and glowing parts | Keeps each material's PS2 blend: the hideout lamp's cone of light stays additive |
| The war's guards | Jak 3's guard skeleton (3 joints inserted) and clip order, so Jak 3's guard code drives Jak 2's guard unchanged |
| Color variants | Recolors textures ([guide, 6](haven_city_new_dawn_readme.md#6-color-variants)) |

Three limits of `build-actor` models to keep in mind:

- They play animations at 60 frames per second: multiply Jak 2's frame numbers (15 fps) by 4.
- They have no mask table, so a look Jak 2 switches with masks is a model of its own (the
  speaker's damaged and broken looks, the gold metal head).
- They have no effect control, so the sounds and effects written in their clips don't run on
  their own ([guide, 5.6](haven_city_new_dawn_readme.md#56-death-the-purple-cloud)).

## 8. Traffic

### 8.1 Navigation data

Each Jak 2 district has its own traffic data, `city-level-info` (a grid of cells and a graph of
lanes), and its own navigation meshes. Jak 2 and Jak 3 store them the same way. The decompiler
copies them out of Jak 2's levels as they are (`extract_nav.cpp`), and the level builder writes them
into the district's bsp (`nav_data`). Each district keeps its own, as in Jak 2: merged into the
hub, they made the traffic spawn over districts that weren't loaded, with cars floating over the
void.

**Trap:** unlinking a traffic graph that was never linked corrupts it. `havenj2-traffic-start`
unlinks only the graphs already linked; before that fix, the game crashed going down the palace
pillar.

### 8.2 Citizens, guards and vehicles

**What you see:** Jak 3's citizens, Freedom League guards, hover bikes and cars on Jak 2's lanes,
in Jak 2's numbers.

**How:**

- The hub's DGO links Jak 3's city traffic code (the list of `cwi.gd`), without the rest of Jak
  3's city.
- The hub's level callbacks run it: when the hub loads, `havenj2-login` makes the traffic engine,
  the guard squad and the attack controller; when it is shown, `havenj2-activate` starts the
  traffic.
- The counts are Jak 2's (`*havenj2-traffic-want-counts*`, `havenj2-traffic.gc`): 44 citizens,
  9 guards, 24 bikes, 21 cars.
- The guards say Jak 2's lines, spaced like Jak 2's (`hj2-speech-ready?`); the citizens say Jak 2's
  lines too.

**Two traps, both crashes:**

- Jak 3's faction manager stops the game on a level name it doesn't know. The mod runs without it,
  as Jak 3's Spargus does; one marked line of `guard.gc` checks that it exists.
- A guard needs the attack controller. With none (`#f`), the first guard crashed the game; the hub
  now makes it like Jak 3's city does.

### 8.3 Jak 2's alert

**What you see:** hit a citizen or a guard, and the minimap flashes, the music turns to its alert
mode (or the alarm sounds), and guards hunt Jak. 30 s without a new offence, the alert ends. Every
8 kills raise it.

**How:** Jak 3 kept Jak 2's alert code (`ff-squad-control-method-45`) but only raises it in its own
city. The hub's DGO links its own version of that method, with Jak 2's five alert levels
(`*hj2-alert-level-settings*`) and timer. Jak is the squad's target every frame; the guards get
the hatred Jak 3 gives a guard Jak attacks.

### 8.4 Hellcats and guard bikes

- **Hellcats.** Jak 3 declares the Hellcat class but never spawns it. `havenj2-traffic.gc` writes
  `h-hellcat` and its pilot (from the mod Haven City: Breath of Peace), and spawns them through a
  wrapped copy of `traffic-object-spawn`.
- **Guard bikes:** Jak 2's model on Jak 3's bike base, `hj2-guard-bike`.
- Both fly the lanes, chase Jak from alert level 2 with Jak 2's pursuit rules, and can be stolen;
  R1 fires their gun. In the war mode they fly in both sides' colors
  ([guide, 6](haven_city_new_dawn_readme.md#6-color-variants)).

### 8.5 Minimap

Jak 2's 21 city maps show on Jak 3's minimap; the guards are blue icons with their view cone, the
guard vehicles larger ones. Three one-line changes of `minimap.gc` (marked): draw the city map when
`havenj2` is loaded, size a guard icon by its class, keep the view cones while Jak drives in Jak
2's city.

### 8.6 War mode

How the war works is in the [guide, 5](haven_city_new_dawn_readme.md#5-the-war-mode-step-by-step).
Outside the city, Krimzon Guards also stand in 10 places: the level port puts a spawner
(`hj2-kg-spawner`, `jak2-haven-city-kg.gc`) at each spot where Jak 2 put an enemy (374 in all).
About one spawner in three is used (35 %, drawn as the level loads), and at most 24 soldiers stand
at once.

## 9. Sound and music

**What you hear:** Jak 2's music, ambiences, object sounds, citizens' and guards' lines, and the
Baron's speeches.

**How:** the build copies these files from your Jak 2 disc and renames them, so that none clashes
with a Jak 3 file of the same name: `j2*` for sound banks and music (`J2CITY1.MUS`), `j*` for voice
lines. The scripts follow: the Hip Hog's door asks Jak 2 for `(want-sound 'ctywide1 'ctywide2
'hiphog1)`, and here for `(want-sound 'j2ctywi1 'j2ctywi2 'j2hipho1)`. Nothing of it is committed. Without Jak 2 extracted, the levels are silent and everything
else works.

| Kind | How Jak 3 plays it |
|---|---|
| Music | Jak 2's music is MIDI (`.MUS` files); Jak 3's sound code learned to play it ([13.5](#135-sound-in-the-overlord-and-goalc)). The city sets its variations (gun, vehicle, Dark Jak) like Jak 2 |
| Sound banks | Loaded as Jak 3 half banks; the free slots take the banks a level needs (`hj2-update-extra-sound-bank`) |
| Ambiences | Jak 2's region scripts and part spawners, kept as they are |
| Voice lines | Packed in Jak 3's format by `goalc`'s `pack-vags`, in `VAGDIRM.AYB` and `VAGWADM.<language>` |

Three traps:

- **Six bank slots.** Jak 3 holds 6 half banks. In the city they are taken by 3 Jak 2 banks and the
  3 traffic banks, so a door that needs its own bank asks for it and waits up to 2 s before
  opening.
- **A line that never ends.** Jak 3 stops a voice at an "end" marker that Jak 2's lines don't have:
  without it, the end of a sentence looped. `pack-vags` adds the marker.
- **Which sound is missing where.** The level port's sound check (`--steps sound`) lists, per level,
  the sounds its content plays and whether a loaded bank holds them.

## 10. Time of day, weather and light

- **Light.** Each level's mood (GAME) follows Jak 2's: street lights, neon signs, flames,
  flickering electricity in the fortress. **Trap:** an interior without fog sets its fog distances
  to 255 and 254, never equal: equal values turned the whole 3D view black.
- **Time of day.** While one of the mod's levels is shown, the clock stays at the hour picked in
  the Mods menu (16:00 by default: a frozen noon puts the sun straight above, with a flat, grey
  light), or runs Jak 2's day and night.
- **Weather.** Jak 2 and Jak 3 share their weather system. The Mods menu picks Jak 3's changing
  weather or a fixed one (sunny, cloudy, foggy, light rain, rain, thunderstorm, snow), for the whole
  game. A process, `hj2-weather-driver`, holds the choice every frame, so a Jak 3 level or mission
  can't take it over.
- **Trap:** a weather picked while the menu pauses the game left rain drops hanging in the air: the
  particles are paused, but the sky is not. The change now waits for the menu to close.

## 11. Travelling and saving

### 11.1 Mods menu

L3 + SELECT, Mods, Haven City: New Dawn. Every entry but "Mod enabled" is greyed out while the mod
is off.

| Entry | Does |
|---|---|
| Mod enabled | Switches the mod on or off; off at each boot |
| Warp to Haven City (Jak 2) | Warps to the underground hideout |
| Warp to a district | Warps to a district, or to a place in it |
| Warp outside the city | Warps to a place outside the city, or back to Jak 3's Freedom HQ |
| Weather | The weather, and a Time of day submenu |
| KG-Guard vs Freedom Fighters | The war mode |

Every warp goes through a continue point, never through the debug command `bg`: a continue point
makes the game unload what it doesn't need before loading the new levels, so the city fits in
memory.

### 11.2 Time gates

Two gates link the games: one in Jak 3's Freedom HQ, one in Jak 2's underground hideout. Both are
Jak 3's warp gate (`hj2-time-gate`, GAME): Jak jumps in, and comes out of the other gate.

- **The Freedom HQ has no gate model.** Two changes bring it: the art group in
  `goal_src/jak3/dgos/freehq.gd`, and its geometry baked into the HQ's `.fr3` by the decompiler
  (`extra_art_groups_by_dgo` in `jak3_config.jsonc`).
- **Spawned without an actor.** The HQ has no level callbacks; GAME adds two when the level loads:
  one spawns the gate (only while the mod is on), one removes it.
- **Trap:** a process spawned into `*entity-pool*` belongs to the default level, and a process looks
  its model up only in its own level. The gate sets its level to the HQ before loading its model.
- **Trap:** a warp gate's opening faces its local x axis, not z.

### 11.3 Air trains

The port's air train and the castle pad's take Jak to each other: Jak 3's air train
(`hj2-air-train`, GAME) with its cutscene replaced by a short fade and a continue point. Triangle
at the prompt.

### 11.4 Respawn points

Jak 2 and Jak 3 share the rule: when Jak's current level changes, his respawn point becomes the
closest continue point of that level. Jak 2 knows the current level from its levels' inside test,
which custom levels lack: the game would keep the district Jak arrived in. So in the city
`hj2-update-vis-nick` sets the current level from the district map ([5.3](#53-when-jak-2s-scripts-are-not-enough));
in the places, Jak 2's own scripts set it.

### 11.5 Saves

Jak saves anywhere in the mod's levels, and the save screen writes "Haven City (Jak 2)" on the slot.
The mod wraps `save-game`: Jak 3's version runs, then a mark goes into a word of the save header
Jak 3 leaves unused. The slot's drawing is wrapped the same way to read it back. How to wrap a
stock method: [Lisp wiki, 4.10](../../../.agents/skills/goal-lisp/wiki/jak3.md#410-wrapping-a-stock-method-from-a-game-file).

## 12. Mini-games

| Game | Where | From | Kept, and changed |
|---|---|---|---|
| Whack-a-Metal-Head | The Hip Hog's cabinet | Jak 2 (`hj2-hiphog-obs.gc`) | Daxter, his hammer, the 8 holes, the scoreboards, Tess's lines, the music. No reward: every game is a replay with a session high score |
| Bubble game | Onin's tent, war mode off | Jak 2 (`hj2-onin-obs.gc`) | Onin, Pecker's lines, the bubbles and their physics. No reward |
| Vin's game | Vin's room, war mode off | Jak 3's own (`hj2-vin-game.gc`) | Jak 3's board, loaded only during a game. No reward, no auto-save |

Triangle at the prompt starts a game, R3 quits it (Jak 2 has no quit).

Two traps met on the Whack-a-Metal-Head:

- Its animations are 30 frames per second, played by `build-actor` at 60: Jak 2's frame numbers are
  doubled.
- The game reads the presses of the pad's last 3 frames, and the triangle press that started it was
  still there: Daxter hit the triangle hole at once. Starting a game clears them.

## 13. Changes to the C++ tools

None of them is about this mod alone: they are candidates for `master-dev`.

### 13.1 Decompiler

| Change | Why |
|---|---|
| Exports each level's cameras to `<level>-cameras.json` | Jak 2's fixed cameras: elevator rides, camera regions |
| Exports the traffic data and navigation meshes as relocatable data (`extract_nav.cpp`) | The traffic ([8.1](#81-navigation-data)) |
| Tags each collision triangle of the background with its prototype's name | Drops the collision of story pieces hidden at the end of the game |
| `levels_to_extract` in a config override | Extracts a few levels again in seconds |
| Several texture replacement folders, searched in order; `extra_texture_replacement_dirs` | The Jak 2 extraction applies the mod's Jak 3 texture pack |
| A rip material keeps its PS2 blend in `extras` | Additive parts were rebuilt opaque |

### 13.2 Level builder

| Change | Why |
|---|---|
| `import_fr3`: merge Jak 2's `.fr3` geometry, textures and collision | Reuse Jak 2's levels as they are |
| `collision_bounds`, `hide_prototypes` | Drop far scenery's collision; hide story pieces |
| The collision table grows its cells until it fits; local coordinates in its tests | Overflow and missing triangles far from the origin |
| An empty background tree gets one empty element | Jak 3 read past the end of an empty tree: a crash on the first frame |
| `pair` and `string` lumps, `region_tree_files`, `cameras` | Jak 2's door scripts, regions and cameras |
| `sprite_textures` | Particle texture pages ([4.3](#43-particles-and-their-textures)) |
| `nav_data` | Traffic data and navigation meshes |
| Animated texture slots mapped to their still texture | Jak 2's waterfalls and lava (they don't move) |
| A `build-actor` model's translucent parts drawn after the opaque ones | The hideout lamp's light cone |

### 13.3 fr3_check

`tools/fr3_check.cpp` reads a `.fr3` file without the game and reports reference errors, extents and
vertex counts. Options print a level's textures (`--textures`), models (`--models`), draws per
texture (`--draws`) and collision ground per square (`--squares`, used for the district map).

### 13.4 Crash report

`game/system/crash_report.cpp` writes where the game crashed to `log/jak3-crash.txt`, the terminal
and the game log: the exception, the GOAL function or state it happened in (named from Jak 3's
symbol table), the running process, and the return addresses on the stack. Windows only. It uses a
vectored exception handler: GOAL code runs on stacks Windows doesn't know, and Windows then ends
the process without calling a normal crash handler.

### 13.5 Sound in the overlord and goalc

| Change | Why |
|---|---|
| A music with a `.MUS` file plays as Jak 2's MIDI music | Jak 3 streams its music and has no MIDI player; it has no `.MUS` file of its own, so its music never takes this path |
| A missing sound bank is skipped with a warning | It asserted |
| Two fixes of the bank records (`sbank.cpp`) | An unloaded bank was never reloaded; a half bank whose partner sat in another record wasn't loaded. Both silent, and Jak 3's own banks were affected |
| `VAGDIRM.AYB` and `VAGWADM.<language>` read after Jak 3's voice files | Jak 2's lines, apart from Jak 3's |
| `goalc` tool `pack-vags` | Packs Jak 2's lines, and the mod's own (Torn's), in Jak 3's format |
| GOOS `file-exists?` | The build copies Jak 2's audio only when Jak 2 is extracted |

## 14. Installing from the launcher

A player installs the mod from the OpenGOAL Launcher and does nothing else: the release holds
nothing of Jak 2, and the mod's levels are made on the player's machine from the Jak 2 the launcher
installed. Jak 2 and Jak 3 must both be installed in the launcher first.

At the launcher's Compile step, the mod's extractor (`run_level_ports`,
`decompiler/extractor/main.cpp`) finds the manifest, finds the Jak 2 disc in the launcher's
folders, extracts the 50 Jak 2 levels the manifest names (about 30 s), runs the level port, then the
GOAL compile. The release builds `level_port` (a one-file executable) and `fr3_check` for this.

When it fails, the launcher only shows `Unexpected error occurred with code N`; the message is in
`extractor-jak3.log`:

| Code (Linux) | Cause |
|---|---|
| 4060 (220) | Jak 2 isn't installed in the launcher |
| 4061 (221) | The level port failed; the lines above it in the log say why |

## 15. Jak 2 and Jak 3: what differs

What this port learned about Jak 3, for anyone porting from Jak 2.

**Particles and textures**

| Topic | What to know |
|---|---|
| Texture ids | They name a page by number: Jak 2's page 12 is `effects`, Jak 3's is `gamefont`. Jak 3's shared sprites are page 4, `level-default-sprite` |
| Particle flags | Jak 2's bits 12, 16, 20 and 21 are Jak 3's 13, 17, 19 and 20 (`CPUINFO_FLAGS`, `convert/jak2_jak3.py`) |
| Particle groups | Jak 3's `defpartgroup` defines no global; reach a new group by id in `*part-group-id-table*` |
| Particle callbacks | A `:func` gets the particle's sprite data; Jak 2's decompiled callbacks call it a matrix, same layout |
| Texture pool slots | Page ids Jak 3 never uses have no slots of their own and overlap the next pages |
| Animated textures | The background names a slot of its game's animated texture table, not a texture |

**Levels and loading**

| Topic | What to know |
|---|---|
| Level memory | 18 chunks; the four sizes take fixed chunks ([5.2](#52-memory-which-levels-fit-together)) |
| Unload order | The most recently loaded level unloads first; unloading erases the types its code defined |
| Actor birth | In a level without visibility data (every custom level), an actor is born within its `vis-dist` lump, 10 km by default |
| Airlocks | Distance tested on the ground plane only, unless the door has a `height` lump; a door born closed with Jak in front runs `on-deactivate` |
| Current level | Custom levels have no inside test: Jak's current level stays the one he arrived in unless code sets it |
| Continue auto-pick | The closest continue of Jak's new level, never a `no-auto` one, only when the current level changes |
| PC renderer | A level is named to the renderer only once loaded, then uploads over several frames |
| Water | Regions only; they send `water` only to a `water-anim`, so a hazard pool needs its own check |
| Ocean map | No `ocean-spheres`; only the first displayed level's map is drawn |
| Fog | Equal fog distances (z = w) black out the whole 3D view |
| Level names | 10 characters at most in a custom level |

**Actors and processes**

| Topic | What to know |
|---|---|
| Art lookup | A process looks its model up only in its own level: a level that places a door ships its art group |
| Processes without an actor | One spawned into `*entity-pool*` belongs to the default level: set its level before `initialize-skeleton` |
| Default init | `process-spawn` without `:init` calls `<type>-init-by-other` |
| Level callbacks | Slots 33 login, 34 logout, 35 activate, 36 deactivate; they can be added at runtime to a Jak 3 level |
| A model in a Jak 3 level | Its art group in the level's `.gd`, its geometry baked into the `.fr3` (`extra_art_groups_by_dgo`) |
| Process heap | 16 KB, unless the type's cached `entity-info` says otherwise |
| Elevators | Jak 3's elevator stops at every point of its path |
| Rigid bodies | Jak 2's methods 29, 53 and 56 are Jak 3's `apply-gravity!`, `get-lava-height`, `rigid-body-platform-method-59` |
| Pickups | Jak 3 inserted `eco-pill-light` and `lightjak` in `pickup-type` |
| Navigation meshes | Found by a binary search: the bsp's list must be sorted by id |
| Traffic | The faction manager stops the game on unknown level names; a guard needs `*cty-attack-controller*` |
| Lightning | 64 connections (Jak 2: 128); a lightning that finds none free isn't drawn |
| Actor scale | Jak 2 ignores the actor scale lump |
| Saves | `info-int32 4` of a save header is unused, and read back as `blind-data 4` of the slot's preview |

## 16. Memory

- **DGO sizes:** the hub about 8 MB, a district 0.9 to 3 MB, a place 23 KB to 5.4 MB.
- **The level heaps must end below 256 MB** (`#x10000000`). A texture links the shaders that use it
  through 24-bit pointers to `address / 16`, so a shader past 256 MB is linked at the wrong place;
  unloading a level then writes through that wrong link and corrupts the game's code. This branch
  sets Jak 3's `DEBUG_LEVEL_HEAP_MULT` to 10.0 (level heaps of about 180 MB), and
  `init-level-system` prints an error if the heaps end past the limit.
- **Spawn distance.** Actors and part spawners are born within Jak 2's `vis-dist`. If the city lags,
  the manifest can cap it: `props.max_vis_dist` and `particles.max_vis_dist`.

## 17. Debugging

- **Game log:** `log/jak3.<date>.log`: level loads, the levels Jak enters, the mod's `hj2:` lines
  ([5.3](#53-when-jak-2s-scripts-are-not-enough)).
- **A crash:** read `log/jak3-crash.txt` ([13.4](#134-crash-report)). Launched through `task`, a
  crash prints only the low byte of the exit code: `exit status 5` is an access violation
  (`0xC0000005`), `9` an abort (`0xC0000409`).
- **More on a crash:** start the game, then `task repl`, `(lt)` and `(dbgc)`. After the crash,
  `(:di "log/crash.txt")` prints the registers and the stack, and `(:disasm <address> <size>)` names
  the function at an address. `rip` equal to `r15` is a call through a null function, often a method
  called on `#f`.
- **A level offline:** `fr3_check <level>.fr3` ([13.3](#133-fr3_check)). One level without the REPL:
  `out/build/Release/bin/build_level.exe -g jak3 <level>.jsonc <output .go> --fr3`.
- **`(mi)` dies after many levels:** each level with `art_groups` reads Jak 3's DGOs again, and after
  about ten `goalc` can crash. Touch the last level's `.jsonc` and run `(mi)` again.
- **A change to the level port:** copy the generated files aside (the `.gitignore` block lists
  them), run the port, compare. A change that only reorganizes code leaves them identical.

## 18. Not done yet

**Not played by the owner yet,** to check on a cold boot (`task boot-game`):

- the city's loading: walking and driving across every district border, no void, few
  `waits for the renderer` lines in the log;
- the alert and the minimap: guards hunting Jak, the alarm, the Hellcats and guard bikes chasing
  him, the icons and cones;
- the sound: each place's music and its variations, the ambiences, the traffic's sounds;
- the Whack-a-Metal-Head;
- respawning in each district at its closest continue.

**Places Jak 2 opens at the end of the game, not ported.** Their doors stay shut:

| Place | Reached by |
|---|---|
| Mar's tomb | The palace plaza's airlock |
| The sewers | The industrial section's airlock |
| The underport | The port's doors |
| The castle | The castle pad's door |
| The drill platform | Vin's room's warp gate |
| The strip mine | The prison's warp gate |

**Left out:**

| What | Why |
|---|---|
| The race track's force field | It needs Jak 2's own collision meshes, which the level port can't copy yet |
| The pumping station's tank wreck, walls broken for good | No rip has their end pose |
| The mountain's gear device | Its collapsed pose covers 30 of its 37 pieces |
| Enemies, precursor orbs, the garage doors | The owner's choices |
| Moving waterfalls and lava | Animated textures are drawn still ([13.2](#132-level-builder)) |
| Some object sounds | In no Jak 2 bank, or in a bank not loaded where the object stands (the barges' engines) |

**Open questions:**

- Haven Forest's lake looks dark. Its water is Jak 2's sea drawn from the city's ocean map, like
  Jak 2's; the cause isn't found. Standing at the lake, `(= *ocean-map* *ocean-map-havenj2*)` in the
  REPL should be `#t`.
- The save slot's picture is Jak 3's choice, from the current mission's level.
- The facts of [15](#15-jak-2-and-jak-3-what-differs) are not all in the Lisp wiki yet: record them
  with the `kb` skill.
