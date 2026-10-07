# Haven City: New Dawn — Technical README

This document explains how Haven City: New Dawn (repository `jak3-mod-haven-city-new-dawn`,
formerly Jak2 Haven City, `jak3-mod-jak2-haven-city`) rebuilds Jak 2's Haven City
and the places around it inside Jak 3, and how to rebuild, extend and debug it. For each feature it
gives what you see in game, how it is made, which files hold it, and the problems met on the way.
Players only need the root [`README.md`](../../../README.md).

**Contents**

1. [What the mod does](#1-what-the-mod-does)
2. [How it is built](#2-how-it-is-built)
3. [Rebuilding it step by step](#3-rebuilding-it-step-by-step)
4. [Tooling changes (C++)](#4-tooling-changes-c)
5. [The city levels](#5-the-city-levels)
6. [Places and level loading](#6-places-and-level-loading)
7. [Navigation and traffic](#7-navigation-and-traffic)
8. [Moods, time of day and weather](#8-moods-time-of-day-and-weather)
9. [Travelling](#9-travelling)
10. [Jak 2 and Jak 3 differences](#10-jak-2-and-jak-3-differences)
11. [Memory and performance](#11-memory-and-performance)
12. [Debugging](#12-debugging)
13. [Change history](#13-change-history)
14. [Not done yet](#14-not-done-yet)

## 1. What the mod does

| Feature | In game | Section |
|---|---|---|
| Haven City | Jak 2's city split like Jak 2 splits it: a hub, `havenj2` (Jak 2's `ctywide`), and 15 district levels (the 14 districts, the stadium grounds), with their lighting, collision, props, water, particles and neon signs. Jak 2's own scripts load the hub and two districts at a time | [5](#5-the-city-levels) |
| Places | 30 more levels, one per Jak 2 place reached from the city (Hip Hog, hideout, palace pillar and roof, Dead Town with the Sage's hut, construction site, pumping station, mountain and its canyon, Haven Forest, the inside of the fortress, its prison and the way out, the stadium's race track, the bazaar's stall, Onin's tent...), loaded and unloaded by Jak 2's own door, elevator and region scripts, in Jak 2's own memory modes where Jak 3's heap allows | [6](#6-places-and-level-loading) |
| Hazards and decor | Every level complete like Jak 2's at the end of the game: Jak 2's particles in every place, the hazards that hurt Jak (palace cable fans and turrets, fortress lasers, the avalanche, the gun buoy, the city's guard turrets...), no enemies; the city's searchlights, force-field walls, parked vehicles and barges, the gardens' living yakows; Jak 2's own doors and airlocks; the places' moving decor | [5.6](#56-city-actors), [6.3](#63-doors-and-elevators), [6.12](#612-hazards-and-decor-of-the-places) |
| End of the game | Every level as it is once Jak 2 is finished: the actors Jak 2 spawns then (story task masks), the background of the end (the market roof broken, Dead Town's tower fallen...); the palace plaza alone as it is before Mar's tomb is found (the Baron's statue standing on its wall) | [5.1](#51-background-and-collision), [6.8](#68-the-end-of-the-game) |
| Dig site | The castle pad and the dig, reached by the port's air train or on foot from the pumping station, with their moving platforms | [6.5](#65-the-dig) |
| Dead Town, construction site | Dead Town and the Sage's hut in one level, its water, swinging bars and sliding beams; the construction site's silo doors and bomb elevator | [6.9](#69-dead-town), [6.10](#610-construction-site-fortress-and-stadium) |
| Prison | The fortress's far gate opens on its prison (cells, torture machine, hanging cells, warp gate), whose tunnels lead out of the fortress (lifts, pool, slide) back to the slums | [6.11](#611-the-prison-and-the-way-out-of-the-fortress) |
| Air trains | "Press triangle to travel to the Dig Site": a short fade, and Jak stands next to the other air train | [6.6](#66-air-trains) |
| Traffic | Jak 3's citizens, guards, hover bikes and cars on Jak 2's navigation data, at Jak 2's density; Jak 2's Freedom League Hellcats and Crimson Guard bikes | [7](#7-navigation-and-traffic) |
| Time and weather | A fixed hour or Jak 2's day and night; Jak 3's changing weather or a fixed one (sunny to thunderstorm, snow) in the whole game | [8](#8-moods-time-of-day-and-weather) |
| Travelling | Mods menu warps to every district, key places and places outside the city; two time gates between Jak 3's Freedom HQ and Jak 2's underground hideout; respawn at Jak 2's continue points, picked by Jak 2's own rule | [9](#9-travelling) |
| Saves | Saving anywhere in the mod's levels; the save screen names Jak 2's world on the slot | [9.4](#94-saves) |

## 2. How it is built

### 2.1 From Jak 2's data to Jak 3 levels

Nothing is modeled by hand. Everything comes from Jak 2's own data, extracted by the decompiler,
then turned into Jak 3 custom levels by the level port and `goalc`. The level port
([`scripts/level_port`](../../../scripts/level_port/README.md)) is a generic tool: this mod is its
manifest, `custom_assets/jak3/ports/jak2-haven-city/port.jsonc` ([2.5](#25-the-port-manifest)).

```text
Jak 2 ISO --task extract--> out/jak2/fr3/<level>.fr3          background, collision, textures
                            decompiler_out/jak2/entities/     actors, cameras, navigation data
                            decompiler_out/jak2/levels/       model rips (rip_levels)
      |
      v  python scripts/level_port custom_assets/jak3/ports/jak2-haven-city/port.jsonc
custom_assets/jak3/levels/havenj2/ and hj2-*/           level .jsonc, .gd, region files
custom_assets/jak3/models/custom_levels/hj2-*.glb       Jak 2 models rebuilt for build-actor
goal_src/jak3/levels/havenj2/havenj2-part.gc, ...       particles, ocean maps, traffic height map
goal_src/jak3/levels/havenj2/jak2-haven-city.gp         the levels' build steps (game.gp loads it)
goal_src/jak3/pc/features/jak2-haven-city-levels.gc     level-load-infos, continue points
      |
      v  goalc (mi): build-custom-level, build-actor, GOAL compiler
out/jak3/obj/*.go, out/jak3/fr3/*.fr3, out/jak3/iso/HJ*.DGO, GAME.CGO
```

### 2.2 Where each part lives

| Layer | Files | Role |
|---|---|---|
| Decompiler | `decompiler/level_extractor/` (`BspHeader`, `extract_actors`, `extract_collide_frags`, `extract_level`, new `extract_nav`), `decompiler/config.cpp` | Exports what Jak 2's bsps hold besides geometry: cameras, navigation data, TIE collision tags ([4.1](#41-decompiler)) |
| Level builder | `goalc/build_level/common/` (`fr3_import`, `ResLump`, `Entity`, new `DataBlob`), `goalc/build_level/jak3/` (`build_level`, `Entity`, `LevelFile`), `goalc/data_compiler/DataObjectGenerator` | Merges Jak 2's `.fr3` files and writes what Jak 2's levels need into Jak 3 bsps ([4.2](#42-level-builder)) |
| Tools | `tools/fr3_check.cpp` | Offline `.fr3` validator ([4.3](#43-fr3_check)) |
| Runtime | `game/system/crash_report.cpp` (new), `game/main.cpp`, `game/CMakeLists.txt` | Where the game crashed, written to the log ([4.4](#44-crash-report-gk)) |
| Level port | `scripts/level_port/` ([README](../../../scripts/level_port/README.md)) | The generic tool that turns Jak 2's data into level files, models, particles and level-load-infos: what it knows of Jak 2 (`games/jak2.py`) and Jak 3 (`games/jak3.py`), what changes between them (`convert/`), its steps (`steps/`). Nothing of this mod is in it |
| Port manifest | `custom_assets/jak3/ports/jak2-haven-city/` (`port.jsonc`, `particle-callbacks.gc`) | This mod's data for the level port: its levels, the doors and actors kept, its own classes, models and ids ([2.5](#25-the-port-manifest)) |
| Level data | `custom_assets/jak3/levels/havenj2/` and 45 `hj2-*/` folders (15 districts, 30 places) | Generated `.jsonc`, `.gd`, mesh, navigation and region files, nothing written by hand |
| Models | `custom_assets/jak3/models/custom_levels/hj2-*.glb` (94) | Jak 2 models rebuilt for `build-actor` ([6.7](#67-rebuilding-jak-2s-models)) |
| Level code | `goal_src/jak3/levels/havenj2/` | Code linked into one level's DGO (table below; of the districts only `hj2-port` has some); `jak2-haven-city.gp`, the levels' build steps (generated) |
| Game code | `goal_src/jak3/pc/features/jak2-haven-city-*.gc`, `levels/havenj2/havenj2-ocean.gc` | In GAME.CGO: what several levels share, and the Mods menu |
| Vanilla edits | `goal_src/jak3/game.gp` (one `load-file` of `jak2-haven-city.gp`), `goal_src/jak3/dgos/game.gd` (the mod's GAME objects, `hj2-common-obs.o` last), `goal_src/jak3/dgos/freehq.gd`, `goal_src/jak3/levels/city/traffic/citizen/guard.gc`, `goal_src/jak3/engine/level/level.gc`, `decompiler/config/jak3/jak3_config.jsonc` | Build steps, GAME objects, the Freedom HQ's time gate model ([9.2](#92-time-gates)), one guard check ([7.2](#72-traffic)), the level heaps' size ([11](#11-memory-and-performance)), the PC renderer told of a mod's loading levels (`*pc-renderer-early-level?*`, [6.1](#61-how-jak-2-loads-its-levels)) |

The level port runs its steps in this order, in about 15 seconds:

| Step | Writes, for this mod |
|---|---|
| `mesh` | A level's static props and pool surfaces as one mesh (`<level>-mesh.glb`): the city levels, and the places with a `mesh` (decor baked in, [6.12](#612-hazards-and-decor-of-the-places)) |
| `ocean` | `hj2-ruins-ocean.gc`, `hj2-mount-ocean.gc`: Jak 2's Dead Town and mountain ocean maps, copied from Jak 2's `goal_src` ([5.4](#54-water-and-ocean)) |
| `nav` | Each district's `hj2-<district>-nav.json`, the hub's `havenj2-height-map.gc` ([7.1](#71-navigation-data)) |
| `levels` | The rest: every level's `.jsonc` and `.gd`, their regions and water regions (`<level>-water-regions.json`), props, particles (`havenj2-part.gc`, `hj2-*-part.gc`) and `hj2-*.glb` models, `jak2-haven-city-levels.gc`, `jak2-haven-city.gp` |

Until phase 12, Python scripts in `custom_assets/jak3/levels/havenj2/` did this work. The history
([13](#13-change-history)) names them:

| Until phase 12 | Now, in the level port or the manifest |
|---|---|
| `gen_havenj2_links.py` | The `levels` step |
| `gen_havenj2_water.py`, `_mesh`, `_ocean`, `_nav`, `_props`, `_particles` | The steps of the same names; water, props and particles run inside the `levels` step (`steps/water.py`, `props.py`, `particles.py`) |
| `jak2_scripts.py` | `convert/scripts.py`, and Jak 3's side of it in `convert/jak2_jak3.py` |
| `jak2_actors.py` | `games/jak2.py` (`Story`) |
| `write_actor_glb` | `common/glb.py` (`rebuild_model`) |
| `convex_hull.py`, `nav_blob.py`, `goal_lisp.py`, `gen_util.py` | `common/` |
| The scripts' tables: `PLACES`, `DOORS`, `ACTOR_MODELS`, `PORTED_ACTORS`, `PLACE_PARTICLES`... | The manifest: `levels`, `doors`, `models`, `ported_etypes`, a level's `particles`... What is Jak 2's own is in `games/jak2.py` (`HIDDEN_PROTOTYPES`: `END_HIDDEN_PROTOTYPES`) |

The GOAL files. HJ2 is the hub's DGO: it holds the code of every district's actors, and the
district DGOs (HSA, HSB...) hold none but the port's barges ([2.3](#23-design-decisions)). Each
place with particles also links its generated `hj2-<place>-part.gc` ([5.3](#53-particles-and-sprite-textures)):

| File | DGO | Holds |
|---|---|---|
| Jak 3's `ctymark-obs-h.gc`, `ctymark-obs.gc`, `ctyfarm-obs.gc` | HJ2 | Jak 3's market and farm props ([5.2](#52-props)) |
| `levels/havenj2/havenj2-obs.gc` | HJ2 | Palace gate, propaganda speakers, guard turrets, parking spots, force-field walls, yakows ([5.6](#56-city-actors)) |
| Jak 3's `ctyport-obs.gc`, `levels/havenj2/hj2-port-obs.gc` | HPT | The port's barges ([5.6](#56-city-actors)) |
| `levels/havenj2/havenj2-farm.gc` | HJ2 | Farm crops ([5.2](#52-props)) |
| `levels/havenj2/havenj2-part.gc` (generated) | HJ2 | Jak 2's city particles, for the hub and every district |
| `levels/havenj2/havenj2-signs.gc` | HJ2 | Animated neon signs |
| `levels/havenj2/havenj2-traffic.gc` | HJ2 | Traffic callbacks and density, the Hellcats ([7.3](#73-hellcats)), the guards' and guard vehicles' minimap icons ([7.4](#74-minimap)) |
| `levels/havenj2/havenj2-height-map.gc` (generated) | HJ2 | How high the vehicles fly |
| `levels/havenj2/hj2-ruins-obs.gc` | HJR | Dead Town's beams and fallen pillars |
| `levels/havenj2/hj2-ruins-ocean.gc` (generated) | HJR | Dead Town's ocean map |
| `levels/havenj2/hj2-cons-obs.gc` | HJC | Construction site's silo doors and bomb elevator |
| `levels/havenj2/hj2-atoll-obs.gc` | HJL | Pumping station platforms and props, the gun buoy |
| `levels/havenj2/hj2-mount-obs.gc` | HJM | Mountain platforms and props, the temple's end state (also placed in `hj2-mtnx`, always loaded with the mountain) |
| `levels/havenj2/hj2-mount-ocean.gc` (generated) | HJM | The mountain's ocean map |
| `levels/havenj2/hj2-mtnx-obs.gc` | HJX | The avalanche |
| `levels/havenj2/hj2-forest-obs.gc` | HJF | Haven Forest's wrens and fish |
| Jak 3's `elec-gate.gc`, `levels/havenj2/hj2-caspad-obs.gc` | HJY | The castle pad's electric gate |
| Jak 3's `rigid-body-plat.gc`, `levels/havenj2/hj2-dig-obs.gc` | HJT | Dig platforms, props and stomp blocks |
| `levels/havenj2/hj2-fortb-obs.gc` | HJJ | The fortress's laser turrets and electric belt |
| `levels/havenj2/hj2-prison-obs.gc` | HKE | The prison's cell doors, vent fans, torture machine, hanging cells, warp gate |
| `levels/havenj2/hj2-fexa-obs.gc` | HKF | The fortress exit's scissor lifts |
| `levels/havenj2/hj2-fexb-obs.gc` | HKG | The fortress exit's pool |
| Jak 3's `searchlight.gc`, `levels/havenj2/hj2-pcab-obs.gc` | HJQ | The palace cable's nuts, falling platforms, electric fans, rotating gun, gun turrets, searchlights |
| `levels/havenj2/hj2-oracle-obs.gc`, `hj2-hide-obs.gc`, `hj2-garage-obs.gc`, `hj2-vin-obs.gc` | HJO, HJD, HJK, HJV | The Oracle's banners, the hideout's lamp, the garage's curtain, Vin's turbines |
| `levels/havenj2/havenj2-ocean.gc` | GAME | Jak 2's city ocean map |
| `levels/havenj2/hj2-common-obs.gc` | GAME | Jak 2's 8 door classes ([6.3](#63-doors-and-elevators)); decor classes of levels loaded together: windmills, flip steps, the low-res throne, prongs, the fortress's buttons and lights, Daxter's mech, the garage's cars ([6.12](#612-hazards-and-decor-of-the-places)) |
| `pc/features/jak2-haven-city-levels.gc` (generated) | GAME | 46 level-load-infos, 113 continue points, the Freedom HQ's time gate arrival point, `*havenj2-levels*`, `*havenj2-hubs*` (each district and its hub) and the district map (`*havenj2-district-names*`, `-grid*`, `-cells*`, [6.1](#61-how-jak-2-loads-its-levels)) |
| `pc/features/jak2-haven-city-world.gc` | GAME | Moods, time of day, weather driver, sprite pages, elevators, fortress gate, air trains, time gates, level callbacks, the district guard, the city's current level (respawn), saves, traffic and Hellcats switches |
| `pc/features/jak2-haven-city-menu.gc` | GAME | Mods menu |

### 2.3 Design decisions

- **The city split like Jak 2's** (phase 14). Until phase 13 the whole city was one `large` level
  (Jak 3's PC level heap is 10 times the original on this branch, `DEBUG_LEVEL_HEAP_MULT`, so a
  `large` level gets about 118 MB). It now follows Jak 2: a hub, `havenj2` (Jak 2's `ctywide`,
  `small-center`), and one `small-edge` level per district, loaded by Jak 2's own scripts with
  the hub and one neighbor district or interior, and shown or hidden by Jak 2's own display
  scripts.
- **The hub loads first and unloads last.** The hub holds the code of every district's actors
  (props, crops, speakers, signs, palace gate, turrets, particles) and the traffic; the districts
  hold their navigation and no code (but the port's barges, Jak 3's classes). Jak 3 loads a level list in order and unloads the most recently loaded
  level first (`load-order` in `level.gc`), and unloading a level sets the symbol of each type it
  defined to 0 and unlinks its particle groups. So every translated level list naming a district
  gets the hub, first, and the level port fails if a set of levels loads a district without its
  hub ([6.1](#61-how-jak-2-loads-its-levels)).
- **One custom level per other place**, loaded and unloaded by Jak 2's own scripts
  ([6](#6-places-and-level-loading)).
- **Merge `.fr3` render trees instead of re-baking glTF.** The Jak 2 extraction already contains the
  tfrag, TIE and shrub trees with their time-of-day palettes, and a collision mesh with each
  triangle's surface type (`pat`).
- **Jak 2 world coordinates are kept.** Jak 3's own city sits at the same place, so these levels
  must never be loaded together with Jak 3's city levels.
- **What more than one level uses is in GAME** (moods, the ocean map, elevators, air trains, the
  decor classes of `hj2-common-obs.gc`). Jak 2 unloads the city in several places, and a place
  must never depend on the city's code. Two levels loaded together can't both link a class: unloading
  one sets the type's symbol to 0 while the other's actors still use it. `jak2-haven-city-world.o` sits after
  `elevator.o` in `game.gd`, `hj2-common-obs.o` after it: a type's parent must be linked before it.
- **Generated, never edited by hand.** Rerunning the level port rebuilds every level file from
  Jak 2's data; a fix goes into the manifest, or into the tool when it is about Jak 2, Jak 3 or how
  levels are built.
- **A generic tool, the mod as data.** The level port knows the games and how to build levels; this
  mod is its manifest. Another port (Jak 1's levels, say) is another manifest, plus what the tool
  doesn't know yet of those games ([`scripts/level_port`](../../../scripts/level_port/README.md)).

### 2.4 Worked example: the Hip Hog door

Every door, elevator and region of the mod follows the path of this one.

1. **Jak 2's data.** The entity dump `decompiler_out/jak2/entities/ctyport-actors.json` lists
   `hip-door-a-6`, a `hip-door-a` whose lumps hold scripts: `on-activate` (Jak comes near: load the
   Hip Hog next to the port district), `on-enter` (display it), `on-cross` (Jak is now in it),
   `on-deactivate` (hide it again), `on-notice` (the levels the door waits for before it opens) and
   `next-actor` (the Hip Hog's own door).
2. **Translation.** The manifest lists the door in `doors`. The level port's `levels` step keeps it
   (Jak 2 spawns it at the end of the game, `games/jak2.py`) and translates each script
   (`convert/scripts.py`): `ctyport` becomes `hj2-port` (the port district), `hiphog` becomes
   `hj2-hiphog`, and the district's hub goes first: the door loads `havenj2 hj2-port hj2-hiphog`.
3. **Level file.** The actor goes into `hj2-port.jsonc` as the class the manifest's `etypes` names,
   `hj2-hip-door`, each script as a `["pair", "<script>"]` lump, the inner door as
   `["string", "hip-door-b-1"]`, and a `height` lump (20 m above and below, `door_height`, since
   Jak 2's door has none). The door's model `hj2-hip-door` goes into `custom_models`, its art group
   into the district's DGO: Jak 3 only looks a process's art up in its own level.
4. **Build.** The level builder writes the lumps as GOAL pairs and strings in the bsp (`ResLump`).
5. **In game.** `hj2-hip-door` (GAME, `hj2-common-obs.gc`), Jak 3's `com-airlock` with Jak 2's
   model, runs the scripts. `hj2-hiphog`
   loads (its level-load-info is in `jak2-haven-city-levels.gc`, its DGO is `HJH`), the door opens
   once it is loaded, and the Hip Hog's door `hip-door-b-1` leads inside.

### 2.5 The port manifest

`custom_assets/jak3/ports/jak2-haven-city/port.jsonc` holds everything the level port needs to know
about this mod; its comments say why each choice was made. What each key means:
[`scripts/level_port/README.md`](../../../scripts/level_port/README.md#the-manifest).

| Keys | What |
|---|---|
| `levels` | The 46 levels: name, nickname, ISO name, level index, actor ids, the Jak 2 levels merged into each (`sources`), memory mode, sky and ocean; each district's navigation (`nav`, Jak 2's as it is), the hub's traffic and particles (`particles.levels`: each district's part spawners go to its level, the garage's too); a place's `mesh` (decor baked in) and `particles` |
| `level_templates` | `city-district`: what the 15 districts share (`hub`, `small-edge`, `display-wait`, `ported_actors`, the city's mood, props mesh, props and speakers); a district takes it with `template` |
| `particles` | For every level: Jak 2's callbacks copied (`copied_callbacks`), the ids reserved by Jak 3's level code, where `"auto"` ids start (`auto_start`, [5.3](#53-particles-and-sprite-textures)) |
| `story` | The end of the game, the palace kept open ([6.8](#68-the-end-of-the-game)) |
| `doors`, `closed_doors`, `etypes`, `door_height`, `elevators`, `script_overrides`... | The doors and elevators, their classes, the height slice they act in, and their scripts ([6.3](#63-doors-and-elevators)) |
| `named_actors`, `ported_levels`, `ported_etypes`, `ported_everywhere`, `teleporters`, `new_teleporters` | The other actors: warp gates, platforms, hazards and props, the city's actors, air trains, the time gate. A lump is kept with its kind (`path`, `float`, `int32`, `uint32`, `vector`, `string`, `symbol`, `type`) |
| `art_groups` | Jak 3 art groups of the mod's classes; a ported actor's goes into its level's DGO (force-field walls, searchlights, barges) |
| `models` | The models rebuilt from Jak 2's rips, their collision and animations ([6.7](#67-rebuilding-jak-2s-models)) |
| `region_open_tasks`, `region_script_overrides` | A region's story branch, or its scripts replaced: the garage (319), the rotating gun (429), the avalanche (894), the gun buoy (177, 353, 873) |
| `continues` | Continue names, the ones kept or added ([9.3](#93-respawn-points)) |
| `ignore_outputs` | The `.gitignore` whose block lists the generated files, kept out of git ([3](#3-rebuilding-it-step-by-step)) |
| `sound` | Jak 2's sound banks and music, renamed `j2*`; Jak 3's banks loaded with the city's (`extra_banks`); the voice lines packed for Jak 3 (`voice_prefix`, `voices`) ([8.4](#84-sound-and-music)) |
| `level_info`, `build` | Where the level-load-infos and the levels' build steps are written; `level_info.hubs_var` names the generated `*havenj2-hubs*`, `level_info.district_map` the district map (25 m squares, [6.1](#61-how-jak-2-loads-its-levels)) |

To port one more place (one of [14](#14-not-done-yet)):

1. Add a level to `levels`: a free name (10 characters at most), nickname, ISO name, level index and
   `base_id`, its Jak 2 levels in `sources`.
2. List its doors in `doors` (the city's door to it moves out of `closed_doors`), and the actors to
   port in `ported_levels` and `ported_etypes`, with their `models`.
3. Write the classes Jak 3 lacks in `goal_src/jak3/levels/havenj2/hj2-<place>-obs.gc`, and add the
   object to the level's `code`; a class placed by levels loaded together goes in GAME's
   `hj2-common-obs.gc` instead. Give it `particles` with `"page"`, `"parts"` and `"groups"` set to
   `"auto"`.
4. Run the level port, then `(mi)`. `game.gp` needs nothing: the build steps are generated.

## 3. Rebuilding it step by step

1. **Build the tools.** The decompiler and `goalc` changed. The level port's particle step runs
   `fr3_check`, so build it too.

   ```bash
   task build-release-decomp
   task build-release-game
   cmake --build out/build/Release --target fr3_check --config Release
   ```

2. **Copy both discs' files** into `iso_data/jak2` and `iso_data/jak3` (the folders `task
   extract` reads), from official copies: the PS2 discs or ISOs dumped from them. The mod is
   made with the European Jak 2 (PAL, SCES-51608) and the American Jak 3 (NTSC-U, SCUS-97330);
   the level port runs the decompiler with `--version ntsc_v1` (its output paths), which extracts
   that PAL Jak 2's levels too. Other regions are untested.
   Jak 2 is required: nothing of Jak 2 or Jak 3 is in git, the levels, models, textures, level
   code, music and voices are made from them on each machine (step 4).

3. **Jak 3's Freedom HQ** must hold the time gate's model (`extra_art_groups_by_dgo` in
   `jak3_config.jsonc`, [9.2](#92-time-gates)): a Jak 3 extracted from this branch has it. On a
   Jak 3 extracted before, only the Freedom HQ needs extracting again (a few seconds):

   ```bash
   out/build/Release/bin/decompiler.exe ./decompiler/config/jak3/jak3_config.jsonc ./iso_data ./decompiler_out --version ntsc_v1 --config-override '{"decompile_code": false, "levels_extract": true, "allowed_objects": [], "levels_to_extract": ["FREEHQ.DGO"]}'
   ```

   The log shows `extra_art_groups_by_dgo: baking 'warp-gate-ag' into FREEHQ.DGO`. Without it
   the Freedom HQ has no gate (GAME checks that the model is there before spawning it).

4. **Run the level port** from the repository root:

   ```bash
   task level-port -- custom_assets/jak3/ports/jak2-haven-city/port.jsonc
   ```

   Its first step (`extract`) checks the extractions it reads and runs the decompiler for what is
   missing: Jak 2's backgrounds, entity, camera and navigation dumps, and model rips (`rip_levels`).
   With no Jak 2 rip at all it extracts the whole of Jak 2 with its rips, once (long: 11 GB);
   afterwards, only the DGOs of the levels whose files are missing (a level's DGO is its nickname:
   `ctysluma`, `CTA.DGO`). Jak 3 is extracted if it has no `.fr3` file. Then it writes the 301
   generated files (levels, models, regions, navigation, particles, level-load-infos, build steps),
   which the manifest's `ignore_outputs` keeps out of git (a block of `.gitignore` the run
   rewrites). Without them, `(mi)` stops at once and says to run this task.

5. **Build the levels and the code:** `task repl`, then `(mi)`. It builds the bsps, the `.fr3`
   files, the custom models and the DGOs.
6. **Check the result offline** (`total: 0 errors` expected), on every level (`hj2-slma.fr3`...):

   ```bash
   out/build/Release/bin/fr3_check.exe out/jak3/fr3/havenj2.fr3
   ```

7. **Play:** `task boot-game`, then L3 + SELECT, Mods, Haven City: New Dawn, Warp to Haven City (Jak 2).

What to redo after a change:

| You changed | Redo |
|---|---|
| The manifest or the level port | Run the level port, then `(mi)`. It only rewrites files whose content changed, so only those levels rebuild |
| A `.gc` file | `(mi)` |
| The level builder (`goalc/build_level`) | `task build-release-game`, touch the level's `.jsonc`, `(mi)` |
| The decompiler | `task build-release-decomp`, extract the Jak 2 levels concerned again (below), rerun the level port, `(mi)` |
| `extra_art_groups_by_dgo` in `jak3_config.jsonc` | Extract the Jak 3 levels concerned again (step 3), `(mi)` |
| A texture of something from Jak 2 (decor, prop, model, particle) | A PNG in `custom_assets/jak2/texture_replacements/<tpage>/<texture>.png` or `_all/<texture>.png`, then the level port (it extracts again the Jak 2 levels and rips older than the newest replacement), then `(make-group "iso" :force #t)` |
| A texture of something from Jak 3 (the guards, citizens, vehicles) | A PNG in `custom_assets/jak3/texture_replacements/` (same layout), then `(make-group "iso" :force #t)` |

**Textures.** The decompiler applies `custom_assets/<game>/texture_replacements` when it extracts
a game, and the level builder applies Jak 3's when it builds a level from Jak 3's art groups. What
comes from Jak 2 (backgrounds merged from `out/jak2/fr3`, models rebuilt from Jak 2's rips,
particle textures) is replaced only by Jak 2's folder, at Jak 2's extraction: the level port's
`extract` step re-extracts the Jak 2 levels and rips older than the newest PNG there. Names:
`decompiler_out/jak2/textures/<tpage>/<texture>.png`, or `fr3_check out/jak2/fr3/<level>.fr3
--textures <filter>`. The PNG can be any size (read as RGBA). `decompiler_out` and `out/jak2` are
shared by every worktree: a Jak 2 texture replaced here also shows in Jak 2 and its mods. The forced
build is needed because the models and art groups a level holds aren't dependencies of its `.fr3`.

A config override can now restrict an extraction to some levels (`levels_to_extract`, DGO names):
the 16 city levels take about 20 seconds instead of a full extraction.

```bash
out/build/Release/bin/decompiler.exe ./decompiler/config/jak2/jak2_config.jsonc ./iso_data ./decompiler_out --version ntsc_v1 --config-override '{"decompile_code": false, "levels_extract": true, "allowed_objects": [], "levels_to_extract": ["CPO.DGO"]}'
```

## 4. Tooling changes (C++)

### 4.1 Decompiler

| Change | Why | Files |
|---|---|---|
| Exports the bsp's `cameras` array to `<level>-cameras.json` | Jak 2's fixed cameras: elevator rides, camera regions | `BspHeader`, `extract_actors`, `extract_level` |
| Exports the bsp's `city-level-info` and nav meshes as relocatable data (`<level>-city.json`, `<level>-nav.json`) | The traffic's navigation data ([7.1](#71-navigation-data)) | `extract_nav` (new), `BspHeader`, `extract_level` |
| Tags each TIE collision triangle with its prototype (FNV-1a hash of the name, in the vertex's `pad2`) | Lets the builder drop the collision of hidden prototypes ([5.1](#51-background-and-collision)) | `extract_collide_frags` |
| Takes `levels_to_extract` from a `--config-override` | Extract a few levels again in seconds | `config.cpp` |

### 4.2 Level builder

| Need or problem | Fix | `.jsonc` key |
|---|---|---|
| Reuse Jak 2's background as it is | Merge the render trees, textures and collision of existing `.fr3` files. Only `normal`, `trans` and `water` tfrag trees are kept (Jak 3 has no low-res tfrag bucket) | `import_fr3` |
| Unreachable backdrops, kilometers wide, blow up the collide hash | Drop the collision outside a box | `import_fr3.collision_bounds` |
| Story-dependent background | Drop the TIE instances of the listed prototypes from the draw lists, and their collision by tag | `import_fr3.hide_prototypes` |
| Collide hash item array over 65535 entries (the game reads bucket indices as u16) | The main grid's cell size grows by 25% until the array fits; fragments go straight into the cells their box overlaps | |
| Triangles missing from fragments far from the origin | Fragment grid tests run relative to the fragment corner, with 1 unit of padding | |
| Crash on the first frame | Jak 3's draw reads `data[length - 1]` of the TIE tree and its proxy's `prototype-max-qwc`; the tree had a length of 0. Jak 3 now gets a tree with one empty instance array and a full-size proxy | |
| Imported geometry culled | Imported trees keep their vis ids, and the bsp gets a 2048-byte all-visible list (a level without vis info copies it into its vis bits each frame) | |
| Shrubs not drawn | An empty `drawable-tree-instance-shrub` (length 1, empty prototype array) makes the game send the shrub bucket | |
| Crash with a level without `region_trees` | `RegionArray` pointers were uninitialized; they default to null | |
| Door and elevator scripts | Res lump types `pair` (a script) and `string` (`next-actor` by name) | `lump` |
| Jak 2's load regions | Region trees read from separate files | `region_tree_files` |
| Fixed cameras | Entity cameras in the bsp's cameras array, found by name by `'use-camera` and by region settings | `cameras` |
| Particle textures | Textures copied from Jak 2's or Jak 3's `.fr3` files into the level's pool, under a texture page of the level's own (1566 for the city, [5.3](#53-particles-and-sprite-textures)) | `sprite_textures` |
| Jak 2's animated textures (waterfalls, the dig's lava) | Jak 2 draws them from animated texture slots, whose ids name Jak 2's slot table. The importer maps each to the slot's still texture (the slot's name without `-dest`, e.g. `waterfall`), the slot names read from the source game's table (`common/texture/texture_slots.cpp`); the log counts them. They don't move | `import_fr3` |
| Navigation data | A `DataBlob` (words and their links: pointers, types, symbols) written as it is: its `city-level-info` root goes to the bsp's `city-level-info`, its `nav-mesh-*` roots to a `nav-meshes` array sorted by aid | `nav_data` |
| The same art group extracted for every DGO | The processed list is shared by every DGO | `art_groups` |

### 4.3 fr3_check

`tools/fr3_check.cpp` (target `fr3_check`) reads a `.fr3` file without the game: reference errors,
extents, vertex counts. Options: `--palettes` (the average of each time-of-day palette), `--draws
<filter>` (triangles per texture or prototype), `--textures <filter>` (the textures of a page, used
by the level port's particle step), `--models <filter>` (the merc models, one name per line, used
by the level port's extract step), `--squares <meters>` (the area of the collision ground, triangles
facing up, in each square of that size: `ix iz m2` per line, used by the levels step's district map).
On a Jak 2 `.fr3` it prints the collision extent, to choose `collision_bounds`, and the triangles
tagged with a prototype.

### 4.4 Crash report (gk)

`game/system/crash_report.cpp` (installed by `game/main.cpp`, Windows only) writes where the game
crashed, between `======== crash report ========` lines, to `log/jak3-crash.txt` (rewritten at
each crash), to the terminal and at the end of the game log, before the process ends like before.

GOAL code runs on stacks in GOAL memory, outside its thread's Windows stack: Windows then stops
looking for a handler and ends the process without calling an unhandled exception filter, and
without an error report (checked with a test program). So the report comes from a vectored
exception handler, which Windows calls before that search, for the fatal exceptions of GOAL code
and of `gk` itself (nothing in them handles one); an unhandled exception filter takes the others.
Both hand the exception to a thread of the report's own, whose stack is large enough.

The game has no debug info for GOAL code, so the report names functions from Jak 3's symbol table:

| Line | What it says |
|---|---|
| First line | The exception, and the thread (`EE` runs the GOAL code) |
| `reading` / `writing` | The address that faulted, as a GOAL address when it is in GOAL memory |
| `at` | A native module and offset (`gk.exe+0x...`), or a GOAL address in its function: a symbol, `(method N type)`, `(type state) :code` (or `:trans`, `:post`, `:enter`, `:exit`, `:event`), or an anonymous function (a lambda) with the closest named function before it, in the same object file |
| `process (r13)` | The process running: name, type, state, level |
| `GOAL objects` | The registers holding a symbol or a basic (its type) |
| `stack` | Return addresses found on the stack, newest first: a heuristic, some can be stale |
| `GOAL output of this frame` | What GOAL printed with `(format #t ...)` since the last frame: the game prints it at the end of a frame, so a crash loses it |

### 4.5 Sound

What lets Jak 3 play Jak 2's music and voice lines ([8.4](#84-sound-and-music)). None of it changes
what Jak 3 plays: each part only acts on files Jak 3 doesn't have.

| Change | Why | Files |
|---|---|---|
| A music with a `<name>.MUS` file plays as Jak 2's MIDI music: the bank's sound 0 in a loop, steered by the MIDI registers the game sends (flava, mode, excitement), set again when it restarts. A streamed music stops it, and the other way around | Jak 3 streams its music from VAG files and ignores `set-midi-reg`; Jak 2's music is MIDI banks. Jak 3 has no `.MUS` file but `TWEAKVAL.MUS`, so its own music never takes this path | `game/overlord/jak3/srpc.cpp`, `rpc_interface.h` |
| A sound bank whose `.SBK` isn't in `out/jak3/iso` is skipped, with a warning | Loading it asserts. Only the copied Jak 2 banks can be missing (no Jak 2 extraction) | `srpc.cpp` |
| Two fixes of the decompiled bank records (phase 20): `LookupBank` finds only a loaded record (`in_use`), as Jak 1 and 2's; a half bank goes next to a loaded half bank of the same mode in any pair of level records, not only the first | An unloaded bank keeps its name in its record, so its next load was skipped; the half bank search never moved past records 2 and 3, so a half bank whose partner was elsewhere wasn't loaded when no pair was empty. Both silently: the game thinks the bank is loaded. Jak 3's own banks are affected too | `game/overlord/jak3/sbank.cpp` |
| `VAGDIRM.AYB`, when there, is added after the game's VAG directory; its lines are read from `VAGWADM.<language>` (the English one for a language Jak 2 doesn't have) | Jak 2's voice lines, in Jak 3's format, apart from Jak 3's files | `iso.cpp`, `iso_api.cpp`, `iso_cd.cpp`, `iso_cd.h` |
| `goalc` tool `pack-vags` | Packs Jak 2 voice lines in Jak 3's format: a 64-bit entry per line (its packed name, start in 32 KB pages, sample rate index), each line taking the pages of its longest language in every wad. A name already in Jak 3's directory is refused. It reads only the lines from Jak 2's wads (470 MB each) | `goalc/make/Tools.cpp`, `Tools.h`, `MakeSystem.cpp` |
| GOOS `file-exists?` | The build copies Jak 2's audio only when Jak 2 is extracted: without it, no audio, and the build still works | `common/goos/Interpreter.cpp`, `Interpreter.h` |

### 4.6 Launcher install

A player installs the mod from the OpenGOAL Launcher and does nothing else: the mod's release
ships nothing of Jak 2, and its extractor makes the levels from the player's own launcher-installed
Jak 2 during the launcher's normal install steps. The player must install Jak 2 and Jak 3 in the
launcher first.

| Launcher step | What runs (cwd: the mod's folder) | Result |
|---|---|---|
| Download | the release zip unpacked into `<installDir>/features/jak3/mods/<source>/<mod>/`, deleted and unpacked again at every install or update | `extractor`, `level_port`, `fr3_check`, `data/` |
| Extract | only when `<installDir>/active/jak3/data/iso_data/jak3` is missing (asks for the Jak 3 ISO) | Jak 3's disc files, with `buildinfo.json` |
| Decompile | `extractor <...>/iso_data/jak3 --folder --decompile --game jak3` | `data/out/jak3/fr3` with this mod's config (`extra_art_groups_by_dgo`) |
| Compile | `extractor <...>/iso_data/jak3 --folder --compile --game jak3` | `run_level_ports`, then the GOAL compile |

`run_level_ports` (`decompiler/extractor/main.cpp`) runs before the compile, also for the
launcher's own Compile of the mod:

1. It looks for `data/custom_assets/jak3/ports/*/port.jsonc`. Without a manifest, or without
   `level_port` next to the extractor (a development checkout, where `task level-port` runs the
   port), it does nothing.
2. It reads the manifest's `source_game` (`jak2`) and finds that game's disc folder, the first one
   holding a `DGO` folder: next to Jak 3's (`iso_data/jak2`), the launcher's layout
   (`<installDir>/active/jak2/data/iso_data/jak2`, found from Jak 3's path), then
   `data/iso_data/jak2`.
3. It runs `level_port <manifest> --root data --iso jak2=<Jak 2 disc> --iso jak3=<Jak 3 disc>
   --extractor <itself> --fr3-check <fr3_check>` with its own output (the launcher's log shows
   it) and no console window.
4. The port's `extract` step runs the extractor again, `--decompile --game jak2 --proj-path data`,
   on the Jak 2 DGOs the manifest names (50, about 30 s), never the whole game. It reads the
   disc's version from its `buildinfo.json` (a PAL Jak 2 gets the `pal` config). The other steps
   write the levels into `data/`; the build file copies Jak 2's sound from the absolute path of
   the Jak 2 disc.

Errors stop the compile. The launcher shows only `Unexpected error occurred with code N`; the
message is in the log (`extractor-jak3.log`).

| Code | Cause | Message |
|---|---|---|
| 4060 | Jak 2 not found | This mod builds its levels from your own copy of Jak 2, which isn't installed. Install Jak 2 in the OpenGOAL Launcher (and let it finish), then reinstall this mod (or run its Compile again). |
| 4061 | `level_port` failed | The level port `<manifest>` failed (exit code N), see the lines above. |

On Linux the shell keeps 8 bits of an exit code: 4060 and 4061 show as 220 and 221. A Compile
of an installed mod extracts nothing again (the files are there) but generates the levels again.

The release (`.github/workflows/release.yml`) builds `fr3_check` and `level_port` (a PyInstaller
one-file executable of `scripts/level_port`) and ships `game/graphics/texture/*_tpage_dir.cpp`
(the particle step reads it) only when the repository holds a port manifest.

## 5. The city levels

The city is 16 levels, like Jak 2's (phase 14; until phase 13 they were merged into `havenj2`):

| Level | DGO | Jak 2 | Memory | Holds |
|---|---|---|---|---|
| `havenj2`, the hub | HJ2 | `ctywide` | `small-center`, level flag `not-physical` | `ctywide`'s background (the city walls, the palace, the mountains), the traffic code and art, the traffic height map ([7](#7-navigation-and-traffic)), the city-wide ocean region, the code of every district's actors, the particle definitions and the sprite page 1566, 10 searchlights; no continues |
| `hj2-slma`, `hj2-slmb`, `hj2-slmc` | HSA, HSB, HSC | `ctysluma`, `ctyslumb`, `ctyslumc` (the slums) | `small-edge`, level flag `display-wait` | Each: its background and collision, regions, cameras, navigation, doors, props, crops, speakers, city actors ([5.6](#56-city-actors)), part spawners, mesh props and pools, and Jak 2's continues of that district; no code |
| `hj2-port` | HPT | `ctyport` | the same | the same, with the barges' code |
| `hj2-marka`, `hj2-markb` | HMA, HMB | `ctymarka`, `ctymarkb` (the market) | the same | the same |
| `hj2-inda`, `hj2-indb` | HIA, HIB | `ctyinda`, `ctyindb` (the industrial section) | the same | the same |
| `hj2-gena`, `hj2-genb`, `hj2-genc` | HNA, HNB, HNC | `ctygena`, `ctygenb`, `ctygenc` (main town) | the same | the same |
| `hj2-farma`, `hj2-farmb` | HFA, HFB | `ctyfarma`, `ctyfarmb` (the gardens) | the same | the same |
| `hj2-pal` | HPL | `ctypal` (the palace plaza) | the same | the same, with the palace pools and gate |
| `hj2-stdm` | HSD | `stadium` (the stadium grounds) | the same | the same, with its fountains |

The districts come from the manifest's level template `city-district`: indexes `0x148` to `0x156`,
`base_id` 53000 to 67000, the hub's mood `update-mood-havenj2`. `not-physical`: Jak is never in
the hub (Jak 3's own `ctywide` has the flag too). `display-wait`: at a district border Jak waits
while the next district loads, as in Jak 2.

### 5.1 Background and collision

- `import_fr3` imports each level's Jak 2 `.fr3` file (the hub `ctywide`'s, each district its
  own). Collision vertices keep their
  original `pat`: the `pat-surface` bit layout is identical in Jak 2 and Jak 3.
- `collision_bounds` drops unreachable backdrops, kilometers wide in `ctywide`, `palcab`, `atoll`
  and `mountain` (`atoll` alone made a 70 MB collide hash without it).
- **Story state: the end of the game.** Jak 2 shows or hides some TIE prototypes depending on the
  story (`level-method-22` in `task-control.gc`, `prototypes-game-visible-set!`, which also disables
  their collision). `STORY_PROTOTYPES` in the level port's `games/jak2.py` copies its conditions;
  at the end of the game they hide the market roof before
  the tanker crash (broken now), the Hip Hog's first paintings, Dead Town's standing tower and the
  swinging bars on it, the pumping station's tank and the distant castle, the castle pad's tanks,
  crane and tower (130 to 520 m up, the pad itself stays), the sewers' hover-board door. What the end
  shows needs nothing: every prototype is shown by default (the construction site's broken
  scaffolding). The palace plaza is before Mar's tomb is found (`story.level_open_tasks`,
  [6.8](#68-the-end-of-the-game)): the wall under the Baron's statue stands, its rubble is
  hidden. An unknown name is ignored by the builder:
  `fr3_check <level>.fr3 --draws ""` lists a level's prototypes.
- **Sky:** drawn only when an active level has the `sky` level flag (every outdoor place has it).

### 5.2 Props

- Jak 2 ignores the actor scale lump, so props keep their model size.
- 1126 market and farm props (crates, baskets, sacks, fruit stands, crops, sprinklers) are Jak 3's
  own classes: Jak 3 ships Jak 2's city props (`ctymark-obs`, `ctyfarm-obs` code, linked into the
  hub's HJ2; art from Jak 3's levels, in each district's DGO). They are solid and breakable; crops
  get a random yaw like Jak 2's. They are born and drawn within Jak 2's `vis-dist` (140 m for the market's;
  [11](#11-memory-and-performance)).
- **Farm crops** (marrows, beetrees, cabbages, small cabbages, chilirots): Jak 3 keeps them as
  scenery, without collision. `havenj2-farm.gc` ports Jak 2's class as `hj2-farm-*`:
  - solid (a sphere per crop);
  - a light hit shakes its leaves (Jak 2's shakers);
  - a strong hit (a vehicle, a gun shot, a dark attack) bursts it into pieces and particles.

  The pieces are Jak 2's burst models, still in Jak 3's `farm-*-ag` art groups (elements 3 to 5),
  thrown by Jak 3's `joint-exploder`. The particles are Jak 2's, in `havenj2-part.gc`.
- The other static props and the pool surfaces are one mesh per city level (`havenj2-mesh.glb`,
  `hj2-<district>-mesh.glb`), lit like merc; solid ones get an invisible collision box. The yakows
  and the street lamps left the mesh: they are actors now ([5.6](#56-city-actors)).

### 5.3 Particles and sprite textures

- The level port's particle step translates Jak 2's city part files into `havenj2-part.gc`: 731
  parts (ids 1200-1930) and 188 groups (300-487), renumbered to ids no Jak 3 code in havenj2 uses.
  It places 3108 part spawners and the 3 neon signs, each in the level of its Jak 2 source
  (`particles.levels`): 105 in the hub, 13 in Keira's garage (Jak 2's `garage` uses the city's
  parts), the others in their districts. The definitions are all in the hub's code.
- **Spawn distance.** Every spawner keeps Jak 2's `vis-dist` (the signs 384 m, the port's 600 m).
  Jak 2 culled its spawners through its visibility data instead; phase 15b's 150 m cap made the
  signs vanish early and phase 20 removed it ([11](#11-memory-and-performance)).
- **Sprite textures.** Jak 2 draws particles from each level's sprite texture page, which Jak 3
  doesn't have. `sprite_textures` puts the textures in havenj2's `.fr3` under page 1566, and
  `hj2-sprite-page-*` (GAME) builds the matching texture page at load and makes it the level's
  sprite page while havenj2 is active.
- **The districts draw with the hub's page** (`hj2-sprite-page-used`: a level's own page, else
  its hub's, `hj2-hub-of`). Jak 2's airlocks hide the hub while the district next to them stays
  shown, so the hub's page leaves the texture page directory only when the hub is unloaded
  (`havenj2-logout`), not when it is deactivated: a failed texture lookup gives particles
  `common-white`, drawn as squares.
- **Prop particles.** Jak 3's market and farm props break into sprite pieces and fruit, with
  textures of Jak 3's city sprite pages that Jak 3's `market-activate` and `farm-activate` set up.
  Those 15 textures are at the end of havenj2's page (its `target_textures`), and
  `hj2-prop-textures-on` points the parts to them when havenj2 is activated.
- **Two Jak 2 details changed meaning in Jak 3**, and the level port translates them (details in
  [10](#10-jak-2-and-jak-3-differences)):

  | Jak 2 detail | Symptom when copied as is | Translation |
  |---|---|---|
  | The smoke and fire texture groups (`birth-func-texture-group`) name textures by id, in Jak 2's `effects` page (id 12) | Squares in chimney smoke and fires: page 12 is Jak 3's font | Remapped by name to Jak 3's `level-default-sprite` (page 4) |
  | Particle flags 12, 16, 20 and 21 | Fountain drops flying in random directions: their acceleration turned with the spawner | Moved to Jak 3's bits 13, 17, 19 and 20 (`CPUINFO_FLAGS`) |

- `:part-engine-max` per level, for the static lights: one per 16 static launchers of the level's
  spawners, at most 255 (4 for the hub, 18 for `hj2-port`, 0 where there are none).
- **The places' particles** (a level's `particles` in the manifest): the same translation
  for one place, in a `hj2-<place>-part.gc` linked into its DGO, with the place's own sprite page.
  Callbacks Jak 3 doesn't have are copied from Jak 2's file (`copied_callbacks`, `defun` and
  `defbehavior` alike): renamed `hj2-*`, their part ids moved, and Jak 2's matrix argument read as
  Jak 3's `sprite-vec-data-2d` (same layout, every row mapped). The data arrays they read are
  copied too (the level's `particles.data`: `*hiphog-mirror-sheen-waveform*` becomes
  `*hj2-hiphog-mirror-sheen-waveform*`), renamed in the callbacks and written before them
  (`copied_func_text` in `convert/jak2_jak3.py`, `data_names`): the Hip Hog's mirror sheen read Jak
  2's name, never defined, and crashed the game. Items of a group bound to a part
  that isn't defined are dropped; `skip_groups` leaves a group's spawners out (the race track's
  scoreboards). 24 places have theirs:

  | Place | Source | Parts, groups | Spawners | Texture page (textures) |
  |---|---|---|---|---|
  | `hj2-forest` | `forest` | 53, 17 | 60 | 1594 (8) |
  | `hj2-ruins` | `ruins` | 7, 2 | 90 | 1627 (1) |
  | `hj2-hiphog` | `hiphog` | 48, 14 | 91 | 1507 (28) |
  | `hj2-gun` | `gungame` | 11, 4 | 112 | 1510 (0) |
  | `hj2-vin` | `vinroom` | 97, 36 | 156 | 1524 (45) |
  | `hj2-hide` | `hideout` | 27, 4 | 4 | 1530 (1) |
  | `hj2-oracle` | `oracle` | 17, 5 | 151 | 1534 (2) |
  | `hj2-consb`, `hj2-cons` | `consiteb`, `consite` | 4, 3; 17, 8 | 40; 95 | 1525, 1528 (0) |
  | `hj2-pshaft`, `hj2-proof`, `hj2-pcab` | `palshaft`, `palroof`, `palcab` (with `sew-gunturret.gc`) | 31, 5; 16, 6; 48, 36 | 144; 107; 269 | 1531 (0), 1545 (1), 1548 (5) |
  | `hj2-atoll` | `atoll` | 30, 15 | 197 | 1556 (1) |
  | `hj2-mount` | `mountain` | 77, 24 | 216 | 1558 (3) |
  | `hj2-caspad` | `caspad` | 10, 3 | 23 | 1532 (0) |
  | `hj2-dig` (`hj2-digb`'s spawners too) | `dig3a`, `dig3b` | 24, 5 | 132 + 109 | 1609 (1) |
  | `hj2-forta`, `hj2-fortb` | `forresca`, `forrescb` | 50, 13; 148, 28 | 146; 186 | 1535, 1559 (0) |
  | `hj2-prison` | `prison` | 75, 27 | 382 | 1567 (0) |
  | `hj2-fexa`, `hj2-fexb` | `forexita`, `forexitb` | 74, 11; 70, 14 | 70; 69 | 1568 (0), 1613 (1) |
  | `hj2-stadd` | `stadiumb-part.gc` | 9, 6 | 115 | 1569 (0) |
  | `hj2-kiosk`, `hj2-onin` | `kiosk`, `onintent` | 22, 6; 50, 10 | 8; 16 | 1637 (2), 1652 (4) |

  The forest and Dead Town have fixed ids (parts 2600-2999, groups 800-879); the others say
  `"auto"` (parts from 3000, groups from 880). Each `hj2-<place>-part.gc` header names its ranges.
- **Choosing a texture page id.** The PC texture pool (`TexturePool`) gives each page of Jak 3's
  directory (`game/graphics/texture/jak3_tpage_dir.cpp`) as many slots as that page has textures,
  one after the other. An id Jak 3 never uses has 0 slots, so every unused id of a run (1566 to
  1572) starts at the same slot, and a page's textures spill over the slots of the pages after it.
  Two pages loaded together must not share slots: 1594 starts 311 slots after 1566 (the city uses
  227), 1627 starts 1309 after it. The first choice, 1567 and 1568, put texture 0 of the forest,
  of Dead Town and of the city in the same slot.
- **`"auto"` pages and ids** (`Allocator` in the level port's `steps/particles.py`): the slots of
  every page are computed from `jak3_tpage_dir.cpp`; GAME's textures (`fr3_check GAME.fr3
  --textures`) and every page already given take theirs. An auto page is the first id with no
  Jak 3 texture, from 1500 up (below 2048: particle data keeps texture ids in signed fields), whose
  slots meet no taken one: no two of the mod's pages share a slot, whatever is loaded together.
  Auto part and group ids start at `auto_start` and skip the `reserved` ranges (Jak 3's level code
  linked with the levels) and the fixed ones.

### 5.4 Water and ocean

- Jak 3's water is regions only. The hub has a city-wide ocean sphere, `hj2-pal` and `hj2-stdm`
  one volume per pool (the palace plaza's pools, the stadium's fountains); their ids start at the
  level's `base_id`. Places get volumes from Jak 2's `water-vol` actors, and the ocean ones Jak 2's
  ocean water spheres.
- `*ocean-map-havenj2*` (GAME, `havenj2-ocean.gc`) is a generated copy of Jak 2's city ocean
  tables, used by havenj2, the palace roof and cable, the pumping station and Haven Forest.
- Dead Town's sea and the mountain's stream have maps of their own in Jak 2, copied by the level
  port's ocean step into their level code (`*ocean-map-hj2-ruins*`, `*ocean-map-hj2-mount*`).
  Jak 3's `ocean-map` has no `ocean-spheres` field: the copy leaves them out.
- **Which map is drawn.** Jak 3 draws the ocean of the first displayed level, in draw order
  (`draw!` of `ocean`); levels are sorted by `draw-priority` (the hub 9.0, the districts and places
  10.0; the districts have no ocean map), then by
  load slot. So a level with another map still displayed could hide the water of the level Jak is
  in: the mountain seen from Haven Forest. `hj2-update-ocean-order` (GAME, run by the respawn
  process every frame) sets the `draw-priority` of the level Jak is in to 8.5 when it has an ocean
  map, and the info's value back on the others.

### 5.5 Palace gate, propaganda speakers, neon signs

- **Palace gate.** Jak 3 has no palace door. `hj2-palace-door` is Jak 2's model and animation
  rebuilt by `build-actor`, placed in `hj2-pal` (its art there, its class in the hub's code); it
  must really close, because the city is hidden in the lobby and unloaded above it. `build-actor`
  plays animations at 60 fps, so Jak 2's 15 fps frame numbers are
  scaled by 4 in `havenj2-obs.gc`. The glb holds only the vertices the gate uses and an invisible
  collision box bound to the sliding door joint.
- **Propaganda speakers** (`hj2-propa`): a pole projecting the Baron's hologram (a particle group
  turned towards the closest target), solid. Like in Jak 2, the first hit damages its projector and
  the second breaks it; a strong hit (a gun shot, a vehicle) breaks it at once. Each hit rings like
  an iron crate (Jak 3's `icrate-nobreak` and `icrate-break`). Jak 2 switches between its three
  looks with mesh masks, which build-actor's models don't have: the damaged and broken looks are
  models of their own (`hj2-propa-damaged`, `hj2-propa-broken`), drawn by a child process
  (`hj2-propa-look`) while the intact model is hidden. The Baron speaks from it like in Jak 2
  (`hj2-propa-speech`, [8.4](#84-sound-and-music)).
- **Blue halo (phase 20).** The hologram's halo (Jak 2's part 819, a 10 m `glow-soft`) and the
  projector's flare (part 822, a `glow`) are blue instead of Jak 2's red and orange; the Baron's logo
  stays red. They are particles, not textures: the colors are set in the manifest
  (`particles.part_specs` on `havenj2`, which replaces init-spec values of a source part, by its
  Jak 2 id), so they survive a regeneration of `havenj2-part.gc`.
- **Neon signs** (`havenj2-signs.gc`): the Baron's skull, Praxis' name and the Hip Hog's marquee,
  blinking random patterns like Jak 2's.

### 5.6 City actors

Jak 2's actors of the districts at the end of the game, placed by class (`ported_etypes`,
`named_actors`; `ported_actors` on the hub and the districts). Their code is in the hub
(`havenj2-obs.gc`) but for the barges:

| In game | Jak 2 | Here |
|---|---|---|
| Parked hover bikes and cars, 49 spots | `parking-spot` | `hj2-parking-spot`, a copy of Jak 3's class (its file isn't linked in the hub): the spot spawns a vehicle of the traffic when the camera is 40 to 250 m away, keeps it while Jak is near; nothing while the traffic is off |
| Force-field walls, 8 | `security-wall` | `hj2-security-wall`, Jak 3's art and color animation (`*security-texture-anim-array*`, the hub's level callback 6, from Jak 3's `ctywide-texture.o`, no longer skipped). Jak owns the red, green and yellow passes at the end of the game: the 7 walls with a path are open, fading as Jak comes near; `ctymarka`'s wall without a path shows nothing, as in Jak 2 |
| Searchlights, 10 in the hub | `searchlight` | Jak 3's class (`searchlight-ag` in the hub's DGO) |
| Guard turrets, 9 | `cty-guard-turret` | `hj2-cty-guard-turret`, under their lids until the Freedom League squad's alert is at least 1 while Jak drives a vehicle within 100 m; bursts of guard shots, 6 hit points, its head blows apart (`joint-exploder`), back 3 s later |
| Barges in the port's canals | `boat-manager` | `hj2-boat-manager`, `hj2-barge` (`hj2-port-obs.gc`, HPT): Jak 3's classes (`ctyport-obs.o` linked before it), with Jak 2's 4 loops as static data (the builder writes one sample of the `path` lump) and every barge sailing; they steer on the port's water nav mesh (aid 26081) |
| Daxter's mech, 2 in the port | `farthy` | `hj2-farthy` (GAME, `hj2-common-obs.gc`), its idle in a loop |
| Street lamps, 42 in `hj2-gena` and 42 in `hj2-genc` (by the palace and by the stadium) | `ctyn-lamp` | `hj2-ctyn-lamp` (phase 20, `ported_everywhere`; baked into the district mesh before): Jak 2's pole and its 4-piece explode model rebuilt by `build-actor` (`models`: `hj2-ctyn-lamp`, extra `hj2-ctyn-lamp-explode`; collision two boxes, the pole and its head). Any attack of Jak snaps it, as do the vehicles: Jak 2's vehicles sent `attack` to what they touched, Jak 3's send `impact-impulse` (`rigid-body.gc`), and the lamp breaks on both. The pieces fly from the hitter (`joint-exploder`, Jak 2's tuning), `lamp-hit` plays; gone until the district reloads |
| Yakows, 14 in the gardens' pastures (`hj2-farmb`) | `yakow` | `hj2-yakow`, Jak 2's model with 4 of its animations (idle, graze, walk, kicked): idles, sometimes grazes, and while Jak is within 30 m now and then walks to a point within 4 m of its home (`*hj2-yakow-wander-radius*`, checked with collision probes: no nav mesh). A hit plays its kicked animation; it takes no damage. Solid. Silent: Jak 3's banks have no yakow sound |

## 6. Places and level loading

### 6.1 How Jak 2 loads its levels

Jak 2 loads its levels with scripts in three places: doors and elevators (`on-activate`,
`on-enter`, `on-inside`...), invisible regions (planes crossed, volumes entered; Jak 2's region
database is `goal_src/jak2/tools/db-fixtures/fixture-region.sql`) and continue points. Jak 3 runs
the same script language and the same airlock, elevator, warp gate and region code, so the
level port ports them all. Its script translator (`convert/scripts.py`) translates them:

| In Jak 2's script | Becomes |
|---|---|
| `ctywide` | `havenj2`, the hub |
| A city district (`ctyport`, `stadium`...) | Its district level (`hj2-port`, `hj2-stdm`...) |
| Another ported level | Its `hj2-*` level, or the one it is merged into (`sagehut` is `hj2-ruins`) |
| A level that isn't ported | Dropped from lists; a door waiting for it stays shut |
| A `want-load` or continue level list naming a district | The district's hub added if missing (hidden in a continue's list when Jak 2 didn't show `ctywide`) and moved first ([2.3](#23-design-decisions)). The level port fails if a set of levels loads a district without its hub |
| `want-display` of a city level | Kept, as in Jak 2: the districts' camera regions and the airlocks hiding `ctywide` (until phase 14 they were dropped, the whole city being one level) |
| `want-display` mode `'special` (drawn as a backdrop, never the level Jak is in; only its actors whose kill-mask has the bit `special` stay alive, the spawn loop of `entity.gc` kills the others) | Kept (phase 15b; it was translated to `#f`, hidden). Haven Forest's regions 433 and 437 show the mountain that way, and the actors keep the `special` bit (phase 18): the mountain's transport platform has it, so it stays under Jak ([6.4](#64-pumping-station-mountain-and-haven-forest)) |
| `want-vis` (the level Jak is in, for the respawn point) | Kept, but for a hub: the hub is `not-physical`, never Jak's level ([9.3](#93-respawn-points)) |
| `want-display` of a level merged into the place holding the script, from another of its levels | Dropped (Dead Town's regions showing and hiding the hut). A level showing or hiding itself keeps it |
| Story checks (`task-closed?`, `task-open?`) | Evaluated for the end of the game (the manifest's `story`, the actors' story state too), except `palace-sneak-in-meeting` (kept open), per-region exceptions (`region_open_tasks`) and per source level ones (`story.level_open_tasks`: the palace plaza before Mar's tomb, [6.8](#68-the-end-of-the-game)) |
| Continue names (`want-continue`, warp gate destinations) | The mod's continue names |
| `want-sound` (the sound banks), `sound-play-loop` (the ambiences) | Kept, the banks renamed ([8.4](#84-sound-and-music)) |
| Dialogs, cutscenes, settings other than fixed cameras, `task-close!` | Removed |

Region ids are Jak 2's plus 1000; water regions start at each level's `base_id`.

**How Jak 2 loads its city, and on PC.** Jak 2 has no city-specific loading code: only the
region scripts above, doors and continues call `want-levels` and `want-display-level`
(`goal_src/jak2/levels/city/` never does). The load-state's `update!` (Jak 2's and Jak 3's
`level.gc`, the same logic) unloads first, then starts one DGO at a time, and shows a wanted level
once it is loaded; a level shown while still loading trips Jak (`'loading`, `wait-for-load`). A
region's scripts run only while its level is `active` (shown, `region-tree-execute`). On PC,
`level-update` names a level to the renderer (`__pc-set-levels`) once it is loaded, and the
renderer (`Loader.cpp`, shared by every game) reads, decompresses and unpacks one `.fr3` at a time
on a thread, then uploads it over several frames (4.5 ms and about 2 MB per frame, at most 20
textures or 1 MB of them). It keeps up to `LEVEL_TOTAL` levels (7 in Jak 2, 11 in Jak 3) and
unloads only beyond that, first those no longer named and unused for 180 frames. A level shown
before its upload ends has collision and nothing drawn: Jak 2 hides it because its loading faces
come seconds before its display faces.

Measured (phase 19's log, `log/jak3.2026-10-07T02-18-32.log`): the game loads and links a district
in 0.05 to 0.3 s (`Elapsed time for level`), the renderer takes 1.5 to 2.5 s (`fr3_check`: 0.75 to
1.7 s to read a district's `.fr3`, then the upload; Jak waited 1 to 2 s on `hj2-farmb`, `hj2-farma`,
`hj2-slma`). The districts' `.fr3` files are Jak 2's size (3.2 to 6.6 MB, the same TIE); the hub's
is 15.5 MB with 1342 textures (`ctywide`: 2.4 MB, 194), loaded once on entering the city. The slow
cases came from the mod's own heuristics fighting Jak 2's scripts: the phase 19 preload loaded
`hj2-marka` in place of `hj2-port`, then the port back, then the market again; it replaced
`hj2-gena` (loaded by Jak 2's face 294) with `hj2-genc`, so the guard loaded it back; it replaced
`hj2-genb` (loaded by the stadium's face 130) with `hj2-slmc`; and showing districts within 50 m
showed a market Jak 2's camera face had just hidden.

**Loading faces walked around.** Jak 2's region scripts load a district on a face Jak crosses and
show it on a face the camera crosses; a request to show a level that isn't wanted is lost
(`can't display X because it isn't loaded`). Jak 2's scripts run here as they are, and since phase
20 they alone decide what the game loads and shows, but some of their loading faces can be walked
around: from the industrial section to the port, from the port to the gardens, from the palace to
the main town (load face 589 and display face 588 are 241 m apart on different streets), from the
gun course to the palace, from the gardens through the bazaar to the palace. Two fallbacks in the
mod's GAME code (`jak2-haven-city-world.gc`) act only when Jak 2's own loading would leave Jak on
the void. Neither evicts a district a script asked to load less than 5 s ago
(`hj2-recently-asked?`: a wrapper of `want-levels` notes the districts every caller but this code
names), so nothing loads back and forth.

1. **Swapped in at display time** (phase 15). The wrapper of `want-display-level` swaps a district
   asked to be shown while it isn't wanted for a hidden district of the same hub, or, when only the
   hub and one other level are wanted, takes an empty slot (a small-center hub and two small-edge
   districts fit the heap). When both districts are shown, nothing changes, like in Jak 2. The log
   prints `hj2: <district> wanted in place of <district>, to show it (frame N)`. A place Jak 2 loads
   with the city (a `small-edge` level that isn't a district: the stadium's race track, an
   interior) is swapped in the same way, with `havenj2` as its hub (phase 19). The port's region
   489 (a camera face on every way to the gardens) also loads `hj2-farmb`
   (`region_script_overrides`): Jak 2's loading face 487 there can be walked around.
2. **The district guard** (`hj2-district-guard`, phase 15b, run every frame by the respawn point
   process), for streets no face covers at all (from the port towards the palace). While Jak's
   level is the hub or one of its districts, it reads which district holds the 25 m square under
   him: `*havenj2-district-cells*` in the generated level-info file (the levels step's
   `district_map`). Since phase 20 a square belongs to the district whose collision ground (its
   Jak 2 `.fr3`, triangles facing up, `fr3_check --squares`) covers most of it, the hub's ground
   left out: the district drawing the ground under Jak. Only a square with no district ground
   (water, a canal) falls back to Jak 2's traffic cells (each cell's segments shared by the squares
   it overlaps in proportion to the overlap), and three rings of squares are grown around for the
   ground past the last street; all 48 city continues fall in their own district. When that
   district is loaded but hidden (Jak 2's camera face for it lies on another street), it is shown at
   once (`hj2-show-if-loaded`: `hj2: guard shows <district>, loaded and Jak on or near its
   ground`); when it isn't loaded for 0.3 s, it is shown: swapped in (step 1), else loaded with the
   hub and the district Jak was in (`hj2: district guard loads <district> (Jak in <level>, frame
   N)`). While it is shown, the district of the square Jak will be over in 1 s is shown if loaded,
   and the one he will be over in 1 s or 2.5 s at his speed, else (walking) the nearest district
   whose ground lies within 50 m of him (`hj2-near-district`, two squares around his), when not
   wanted, is loaded hidden (`hj2-load-ahead`), at most once every 2 s: in place of a hidden
   district no script asked for in the last 5 s, or an empty slot (`hj2-swap-in-district`), else in
   place of any district of the hub, or a place loaded with the city (the gun course), but the one
   under Jak, Jak's level, the nearest within 50 m, and a district shown or asked for by a script in
   the last 5 s whose ground lies within 100 m (a hidden one first): `hj2: <district> wanted in
   place of <district>, ahead of Jak`. The look-ahead reaches 60 m at most, and a loaded district is
   shown early only when its ground is within 25 m of Jak: farther, Jak 2's camera faces decide.
   Without these limits, flying to the stadium's gate the 2.5 s look-ahead reached the slums,
   swapped them with the stadium Jak 2 had just shown, and Jak 2's face swapped it back, again and
   again. Until the user's last phase 20 test it only showed a
   loaded district after Jak stood 0.3 s on it, and loaded ahead only in place of a hidden district
   no script had asked for: from the industrial section to the slums (Jak at 1092, 374, on a street
   no Jak 2 loading face covers: faces 1278 and 1344 lie on other streets), the industrial
   sections were both wanted and recent, and the slums loaded only once Jak was on them. Walking
   from the port to the palace plaza (Jak at 212, 1149), Jak's speed saw no border 2.5 s ahead:
   the plaza loaded only under him, hence the 50 m look around.

**Why the stadium never loaded** (phase 20, `log/jak3.2026-10-07T13-14-52.log`). Only `hj2-genb`'s
faces load and show the stadium grounds (target face 1130, camera face 1131), and they run only
while `hj2-genb` is shown, which only `hj2-gena`'s camera face 1117 does, on a street 300 m from the
stadium. Jak flew from the main town's north side, where the stadium's ground reaches 250 m west of
its streets: the traffic-cell map gave those squares to `hj2-gena`, shown, so the guard did nothing,
and `hj2-stdm` was never loaded. On the ground map they are `hj2-stdm`'s. Jak 2's city regions are
all ported (the 4 left out load places that aren't ported) and run as in Jak 2 (the same
`region-execute`: target and camera positions, active levels only); the late districts of that log
are display faces reached on streets without a loading face before them, which the log lines below
will place.

**Log lines for a loading report.** Each line ends with `(Jak at <x> <z>, frame N)` (meters, the
district map's coordinates):

- `hj2: script wants <levels>`: a level list naming this mod's levels asked by Jak 2's scripts, a
  door or a continue (`want-levels`), printed when it changes;
- `hj2: script shows <level>` (`(not wanted)` when it isn't loaded: the swap-in follows) and
  `hj2: script hides <level>`: a script's display request that changes one of this mod's levels;
- `hj2: guard: under Jak <district> (<state>), Jak's level <level>`: each time the district under
  Jak or its state changes. The state is the level's status (`active`: shown; `loading`,
  `loaded`...), `wanted` (asked, not loaded yet), `not-wanted`, `no-district`, or why the guard is
  off: `not-in-city`, `in-place` (a script made a place Jak's level), `no-hub`, `movie`,
  `no-border`, `no-level`.

Phase 19's preload (`hj2-preload-district`: the nearest district of Jak's square loaded hidden in
place of another) and showing ahead (`hj2-show-near-districts`: districts within 50 m shown) were
removed in phase 20: they changed what the game loads and shows, and evicted or showed districts
against Jak 2's scripts (above).

**Places on the city's squares.** The district map only knows streets. The stadium's race track
(`hj2-stadd`) runs in tunnels under the main town: 78 of its 115 actors stand on `hj2-gena`'s
squares, 7 on `hj2-genb`'s, 30 on none. Jak 2 never makes it Jak's level, so in the track Jak's level
stayed `hj2-stdm`, and the guard took him for being in the main town: it loaded `hj2-gena` with the
hub and `hj2-stdm`, discarding the track under him. The port's region 1317 (Jak 2's 317, the camera
face at the track's entrance, `region_script_overrides`) now also makes the track Jak's level
(`want-vis`, like Jak 2's garage region 776) and the stadium grounds again on the way out. While a
script has made a place Jak's level and asked to show it (`hj2-in-place?`), the guard and the
vis-nick update leave the city alone, even while the place loads and Jak's level is still the
district. `hj2-fexb` (the way out of the fortress, 46 of its 74 actors on `hj2-slma`'s squares, 28
on `hj2-slmb`'s) has no `want-vis` either: not changed, to check in game.

**The renderer ahead of the game.** Three vanilla edits of `level.gc` (marked
`og:jak2-haven-city added`, all `#f` by default: Jak 3's behavior) and one in `gk`:

- `*pc-renderer-prefetch*` (phase 20), called by `level-update` with the 10 level names it gives the
  renderer: the mod's `hj2-renderer-prefetch` moves the game's levels first and adds, in the empty
  slots, the district of Jak's street square and the two nearest other districts of that square
  within 130 m (`*havenj2-district-preload*`, the manifest's `preload`, about the distance between
  Jak 2's load and display faces). Only the renderer loads them: the game's loads stay Jak 2's, but
  when a script (or a fallback) loads one, its geometry is already there, and the district is shown
  about 0.1 s after its load starts instead of 1.5 to 2.5 s. With the hub, two districts, a place
  and three named ahead, the renderer stays under its 11 levels; the districts Jak passed stay
  there until it needs room. The log prints `hj2: renderer loads <district> ahead of Jak (frame N)`
  once for each district it doesn't have yet.
- `*pc-renderer-early-level?*`: the mod sets it to `hj2-mod-level?`, so `level-update` names the
  mod's levels to the renderer from the start of their load (`loading`, `loading-bt`,
  `loading-done`, `login`): the upload overlaps the load.
- `*pc-renderer-display-wait?*`, asked in the load-state's display step for a level to be shown:
  the mod's `hj2-display-wait?` keeps one of its levels hidden (collision and actors off) while
  `__pc-level-ready?` says the renderer doesn't have it, and Jak 3's display step shows it the first
  frame it does. Meanwhile, if Jak stands on that district's square, or a script made the level
  Jak's (vis-nick: the stadium's race track), he waits like for a stock `display-wait` level (the
  `'loading` event; Jak 3's target ignores it in a vehicle). After 6 s from the start of the load it
  is shown anyway. The log prints `hj2: <level> waits for the renderer (frame N)` once a second.
  A continue waits for its levels to be shown, so Jak respawns on drawn ground. A door of the
  mod's levels waits too, before it opens: Jak 2's door loads its level, waits for the load, then
  shows it and opens, and Jak 3's open door shuts at once while its level isn't shown. The mod's
  wrapper of `com-airlock`'s `destination-loaded?` (defined before the mod's door classes, which
  inherit it; Jak 3's doors unchanged) answers "not loaded" while the renderer lacks one of the
  door's levels (`hj2-renderer-pending?`, the same test and 6 s cap), so the door stays shut and the
  level is shown as it opens. The log prints `hj2: <door> waits for the renderer (<level>, frame N)`.
- `__pc-level-ready?` (`game/kernel/jak3/kmachine_extras.cpp`, through `GfxRendererModule::level_ready`
  and `Loader::is_level_ready`): `#t` once the renderer has loaded and uploaded the level. The loader
  now erases its loaded levels with its mutex held, so the game's thread can ask.

### 6.2 The levels and their memory

| Level | DGO | Jak 2 | Jak 2's memory | Memory | Loaded with |
|---|---|---|---|---|---|
| `havenj2` (the hub) | HJ2 | `ctywide` | small-center | small-center | every district, first ([5](#5-the-city-levels)) |
| 15 districts (`hj2-slma`...) | HSA... | the districts, `stadium` | small-edge | small-edge | the hub and a neighbor district, interior or place |
| `hj2-hiphog`, `hj2-gun`, `hj2-vin`, `hj2-hide`, `hj2-oracle`, `hj2-garage` | HJH, HJG, HJV, HJD, HJO, HJK | interiors | small-edge | small-edge | the hub and the district of their door (`havenj2 hj2-port hj2-hiphog`) |
| `hj2-ruins` | HJR | `ruins` (Dead Town) and `sagehut` (the Sage's hut, old Samos') | large | small-edge | the hub and `hj2-slmb` |
| `hj2-forta`, `hj2-fortb` | HJI, HJJ | `forresca`, `forrescb` (the inside of the fortress) | small-edge | small-edge | `hj2-forta` with the hub and `hj2-slma` (the slums' fortress gate), then each other; `hj2-fortb` with the prison |
| `hj2-prison` | HKE | `prison` (the fortress prison) | large | large | `hj2-fortb` or `hj2-fexa` |
| `hj2-fexa`, `hj2-fexb` | HKF, HKG | `forexita`, `forexitb` (the way out of the fortress) | small-edge | small-edge | the prison, each other; `hj2-fexb` with the hub and `hj2-slmb` (its gate to the slums) |
| `hj2-stadd` | HJZ | `stadiumd` (the stadium's race track) | small-edge | small-edge | the hub and `hj2-stdm` (the stadium's regions) |
| `hj2-consb`, `hj2-cons` | HJB, HJC | `consiteb`, `consite` | small-edge, large | small-edge, large | `consiteb` with the hub and `hj2-inda`, then both without them |
| `hj2-pshaft` | HJS | `palshaft` (palace pillar) | small-edge | small-edge | the hub and `hj2-genb` or `hj2-pal`, or the roof and cable |
| `hj2-proof`, `hj2-pcab` | HJP, HJQ | `palroof`, `palcab` | small-edge, small-center | small-edge, small-center | the pillar, never the city |
| `hj2-atollx` | HJA | `atollext` (the way to the pumping station) | small-edge | small-edge | the hub and `hj2-slmc`, or the station |
| `hj2-atoll` | HJL | `atoll` (the pumping station) | large | large | `hj2-atollx` or `hj2-caspad` |
| `hj2-mount` | HJM | `mountain` | medium | small-edge | the hub and `hj2-farma` (its foot), `hj2-mtnx` or `hj2-forest` |
| `hj2-mtnx` | HJX | `mtnext` (the temple outside, a backdrop) | medium | medium | `hj2-mount` |
| `hj2-forest`, `hj2-forstb` | HJF, HJN | `forest`, `forestb` (Haven Forest) | medium | medium | `hj2-mount`, or each other |
| `hj2-caspad` | HJY | `caspad` (the castle pad) | small-edge | small-edge | the hub and `hj2-port` (air train), `hj2-atoll` (on foot) or `hj2-dig` |
| `hj2-dig`, `hj2-digb` | HJT, HJU | `dig3a`, `dig3b` (the dig) | large, small-edge | large, small-edge | `hj2-caspad`, or each other |
| `hj2-kiosk` | HKH | `kiosk` (the bazaar's stall) | small-edge | small-edge | the hub and `hj2-marka` (its regions) |
| `hj2-onin` | HKI | `onintent` (Onin's tent) | small-edge | small-edge | the hub and `hj2-markb` (its regions) |
| `hj2-mincan` | HKK | `mincan` (the canyon) | small-edge | small-edge | `hj2-mount` (its regions, behind the iris doors) |

**How the memory is chosen** (`memory_modes` in the level port's `levels` step). Jak 2's `load-buffer-mode`
has the same four names as Jak 3's `level-memory-mode`, and each level takes Jak 2's (the largest
of its levels' when it merges several). Jak 3's level heap has 18 chunks, and each mode takes fixed
chunks (`level-group::alloc-levels!` in `level.gc`, no micro or tiny level loaded):

| Mode | Chunks |
|---|---|
| `large` | 0 to 11, or 6 to 17 |
| `medium` | 0 to 8, or 9 to 17 |
| `small-center` | 6 to 11 |
| `small-edge` | 0 to 5, or 12 to 17 |

The level port collects every set of levels loaded together (each `want-load` of the translated
door, elevator and region scripts, each continue's level list: `load_sets`) and checks each fits
(`fits`, an exact placement). Where one doesn't, it makes the change that fits with the fewest sets
left failing, and prints it. The city's load sets are Jak 2's: the hub (`small-center`, chunks
6 to 11) and two `small-edge` levels, a district and its neighbor district or interior. Jak 2 loaded
Dead Town and the mountain without `ctywide` (`ruins` with `ctyslumb`, `mountain` with
`ctyfarma`); here the hub stays (`havenj2 hj2-slmb hj2-ruins`, `havenj2 hj2-farma hj2-mount`),
because the code of its district's actors is in it. So these two are the only levels changed:
`small-edge` instead of Jak 2's `large` and `medium`. The large places (`hj2-cons`, `hj2-atoll`,
`hj2-dig`, `hj2-prison`) are never loaded with the hub. Continues whose levels still don't fit are
left out (printed).

A custom level's name is at most 10 characters (the level builder asserts it): Jak 2's `forresca`,
`forrescb`, `forexita` and `forexitb` became `hj2-forta`, `hj2-fortb`, `hj2-fexa` and `hj2-fexb`.
Their continue points keep Jak 2's names (`hj2-forresca-start`).

### 6.3 Doors and elevators

- **Jak 2's own doors** (phase 15b; until then Jak 3 doors stood in). Eight classes in GAME's
  `hj2-common-obs.gc`, each Jak 3's `com-airlock` (the same scripts as Jak 2's) set up like Jak 2's
  class of that door, with Jak 2's model and opening animation rebuilt by `build-actor` (the
  manifest's `etypes` and `models`), each leaf solid on its joint. Jak 2's frame numbers are scaled
  by 4, like the palace gate's. 42 doors use them:

  | Class | Jak 2 | Doors |
  |---|---|---|
  | `hj2-airlock-outer` | `com-airlock-outer`, `cas-front-door` (same model) | 13: the city's airlocks to the places outside it and their far doors; the castle pad's door, shut |
  | `hj2-airlock-inner` | `com-airlock-inner` | 15: the inner halves, the palace pillar's doors |
  | `hj2-hip-door` | `hip-door-a`, `hip-door-b` (same model) | 6: the Hip Hog's and the gun course's |
  | `hj2-hide-door-a`, `hj2-hide-door-b` | `hide-door-a`, `hide-door-b` | 1 each: the hideout's door in the slums, its inner door |
  | `hj2-oracle-door` | `oracle-door` | 2 |
  | `hj2-vin-door`, `hj2-vin-door-ctyinda` | `vin-door`, `vin-door-ctyinda` | 1 inside Vin's room; 3 of the power station, in the industrial section and at the construction site |

  Their sounds are Jak 2's names where Jak 3 has the same sound (`wood-*` for the hideout's doors):
  silent, like the traffic's, because they are in Jak 3's city half banks
  ([14](#14-not-done-yet)).
- **Keira's garage has no doors:** its two sliding doors aren't placed, and the region that loaded
  the garage also shows it now (`region_script_overrides`, region 319, which loads
  `havenj2 hj2-stdm hj2-garage` like Jak 2's `stadium ctywide garage`): the door's `on-enter` did.
- **Fortress gates** (`hj2-fort-gate`, GAME): Jak 2's `fort-entry-gate` (Jak 3 has no such door),
  Jak 3's airlock with Jak 2's model and opening animation, each leaf solid on its joint. The slums'
  gate opens on the inside of the fortress: Jak 2 pairs it with the dump's gate (`fordumpa`, not
  ported), `next_actor_overrides` pairs it with `forresca`'s. The fortress's far gate opens on the
  prison, and the way out of the fortress ends at a gate paired with the second slums gate
  (`fort-entry-gate-19`), which only opens from that side, like Jak 2's
  ([6.11](#611-the-prison-and-the-way-out-of-the-fortress)). The slums' third gate (to the dump,
  `fort-entry-gate-18`) opens once the dump is loaded, which nothing does at the end of the game:
  not placed.
- **The gun course's doors** (`gungame-door-4`, `-5`) are Jak 2's fortress gate model: placed as
  `hj2-fort-gate` in `closed_doors`, shut like in Jak 2 while no course runs.
- **Script changes by hand** (`script_overrides`): a door script replaced or removed, by Jak 2 level
  and actor name. The only one: the palace roof and cable outer doors lose their `on-deactivate`
  ([10](#10-jak-2-and-jak-3-differences), "Airlock scripts at load").
- **Door translation.** A door's `on-notice` (the levels it waits for) is evaluated for the story
  state first (`strict_notice` in `convert/scripts.py`): a branch naming a level that isn't ported
  only shuts the door when it is the branch the end of the game takes. The slums' fortress gate was
  shut by a branch of another story state.
- **The inside of the palace isn't ported** (entrance hall, throne room: Jak 2 missions only). Its
  doors stay shut. Of the pillar's two elevators only `com-elevator-2` is kept: lobby to roof door,
  with its ride cameras.
- **The palace elevator no longer kills Jak** on the way up. Jak 2's roof and cable outer doors run
  `want-display hj2-pshaft #f` in their `on-deactivate`. Riding up loads the roof, whose door is
  born closed with Jak on its front side (570 m below it): Jak 3 runs `on-deactivate` then, and
  the game log showed `Turning level hj2-pshaft off` with Jak and the elevator in it. The scripts
  are removed: the pillar is loaded with the roof and the cable anyway.
- **`hj2-elevator`** (GAME) is Jak 2's `com-elevator`: Jak 3's elevator with Jak 2's model (12 x
  13 m, it fills the shafts), a floor box and a fence along its edges, solid only during the ride
  (Jak 3's elevator `fence` flag). No `prevent-jump`: Jak moves freely.
- **Leaving the palace roof.** Jak 2's pillar top airlock (`com-airlock-inner-25`) reloads the city
  (`havenj2 hj2-pal hj2-pshaft`) as soon as Jak comes back in from the roof: the low-res city seen
  from the roof (`palcab`) is gone before the ride down goes through it.
- **Doors act only in a 40 m height slice.** Jak 2 paused the doors it didn't see, through its
  levels' visibility data; the mod's levels have none, and Jak 3's airlock tests Jak's distance on
  x and z only (`want-cross-airlock?` in `airlock.gc`). The pillar-top airlocks
  (`com-airlock-inner-23` and `-25`, about 420 m up) then acted on Jak in the lobby below them. A door
  without Jak 2's `height` lump gets one (`base_lumps` in the level port's `steps/levels.py`, the
  manifest's `"door_height": [20.0, 20.0]`, meters above and below): the airlock opens and runs its
  scripts only while Jak is within 20 m of the door's height.
- **No `vis-dist` copied** (phase 15b). Phase 14 copied Jak 2's `vis-dist` onto doors, elevators and
  named actors (a level without visibility data births an actor within it, 10 km by default,
  `entity.gc`). Jak 2's 200 m made the pillar-top airlocks be born on the way up the pillar: they
  ran their `on-inside`, which loads the bottom set, and the top unloaded under Jak (the palace
  pillar death of the user's second test). `placed()` no longer copies it; the height slice above
  does the job.

### 6.4 Pumping station, mountain and Haven Forest

- **The way to Haven Forest.** In Jak 2 the gardens airlock opens on the mountain's foot, and a warp
  gate there is the only way up. Both warp gates are Jak 3's `warp-gate` (same `on-notice` format).
  At the top, Jak 2's `trans-plat` (ported as `hj2-trans-plat`) rides down the stream to the
  forest.
- **The mountain seen from Haven Forest.** Jak 2's forest regions 433 and 437 show the mountain
  `'special` (a backdrop: only its actors whose kill-mask has the bit `special` stay alive there).
  Jak 2 gives that bit to the transport platform alone, so it carries Jak into the forest. Until
  phase 18 the platform vanished on arrival: the translator turned `'special` into `#f` until
  phase 15b, then the level port dropped the actor's kill-mask (`placed` now keeps its `special`
  bit, `SPECIAL_KILL_MASK` in `steps/levels.py`) ([6.1](#61-how-jak-2-loads-its-levels)).
- **The iris doors are open,** as at the end of Jak 2 (the items put in the canyon,
  `canyon-insert-items-door`): `hj2-iris-door` holds its idle's last frame, without collision. They
  lead to the canyon, `hj2-mincan`, which the mountain's regions load ([6.13](#613-small-places)).
  The temple elevator is parked at the top (it only leads to an iris door).
- **Platforms and props** (`ported_etypes`, `hj2-atoll-obs.gc`, `hj2-mount-obs.gc`): Jak 2's
  classes ported as `hj2-*` (pistons, turbines, lift catwalks, rotating pipes, sliders, the
  temple's moving, long, flipping and buried platforms...), with Jak 2's models. The windmills
  (`hj2-pal-windmill`) are in GAME: the palace cable places them too. Their story state is the end
  of the game: the station running, the temple's gap bridged; the temple's puzzles are solved
  ([6.12](#612-hazards-and-decor-of-the-places)).
- **The mountain's waterfall pools** (`water`: Jak 2's `water-anim-mountain` looks 13 to 15) get a
  water region (swim, wade) and their surface in the mountain's mesh.
- **Crates, swinging bars and slides** of every place are Jak 3's own classes
  (`ported_everywhere`): crates (wood look) with their pickups translated (Jak 3 inserted
  `eco-pill-light` and `lightjak` in `pickup-type`), `swingpole` (GAME), `slide-control` (not in
  GAME: `target-tube.o`, which the level placing it carries in its DGO, [6.11](#611-the-prison-and-the-way-out-of-the-fortress)).
- **Haven Forest's particles** (waterfalls' spray, butterflies, fireflies, cattails):
  [5.3](#53-particles-and-sprite-textures). Its lake is Jak 2's sea (the city's ocean map, 0 m
  high, like Jak 2's `forest`); Jak 2 places no other water object there.

### 6.5 The dig

- **Getting there.** Jak 2 reaches the castle pad by the port's air train ([6.6](#66-air-trains)),
  or on foot from the pumping station, whose regions already load it.
- **The castle pad's elevator** (`hj2-cpad-elevator`, GAME) is Jak 2's `cpad-elevator`: Jak 3's
  elevator with Jak 2's model, a floor box and a ride fence. It rides between the two ends of Jak
  2's path: Jak 3's elevator would stop at each of its seven points. The castle door stays shut (the
  castle isn't ported).
- **The dig's warp gate** leads to Vin's room. The level port translates the level names of a warp
  gate's quoted `on-notice` (its `on-activate` script and `wait-for` list), which the script
  translator leaves as data.
- **Platforms and props** (`hj2-dig-obs.gc`):

  | Class | Jak 2 | How it is made |
  |---|---|---|
  | `hj2-dig-spikey-step` | `dig-spikey-step` | A step turning around its length |
  | `hj2-dig-wheel-step` | `dig-wheel-step` | A wheel whose two steps have collide meshes bound to their own joints |
  | `hj2-dig-sinking-plat`, `hj2-dig-tipping-rock` | `dig-sinking-plat`, `dig-tipping-rock` | Jak 3's `rigid-body-platform` floating on the lava. Its code, `rigid-body-plat.o`, is only in Jak 3's volcano DGO, so HJT links it too. Jak 2's sinking platforms follow a path the dig's don't have: they get Jak 3's platform anchor at their place |
  | `hj2-dig-balloon-lurker`, `hj2-dig-trapeze` | `dig-balloon-lurker` | A balloon on its path, its trapeze a `swingpole` on the bar; a side camera while Jak hangs from it |
  | `hj2-dig-log`, `hj2-dig-button` | `dig-log`, `dig-button` | The log raised and its buttons down: the end of the game |
  | `hj2-dig-totem`, `hj2-dig-sphere-door` | `dig-totem`, `dig-spikey-sphere-door` | Still props; the sphere doors stay shut |
  | `hj2-dig-stomp-block-controller`, `hj2-dig-stomp-block` | `dig-stomp-block-controller` | A row of 4 blocks; Jak's flop sinks one 3 m; once two neighbors are 5 m apart the row breaks, each block a Jak 3 `rigid-body-object` thrown in a random direction |

- **Particles:** [5.3](#53-particles-and-sprite-textures).
- **Not ported:** the enemies, the spiky spheres, the precursor orbs.

### 6.6 Air trains

The mod's air trains, `hj2-air-train` (GAME), are Jak 3's `air-train` (its model and hover) with a
prompt naming where they go, "Press triangle to travel to" followed by their `travel-name` lump:

| Air train | Prompt | Trip |
|---|---|---|
| `air-train-1` (port) | Press triangle to travel to the Dig Site | The castle pad (`hj2-caspad-warp`) |
| `air-train-3` (castle pad) | Press triangle to travel to Haven City | The port (`hj2-ctyport-warp`) |

**The ride is a teleport.** Jak 3's air train plays boarding and landing cutscenes in its `use`
state; `hj2-air-train` replaces that state: a 0.1 s fade to black (`set-blackout-frames`), then the
destination continue loads (`start 'play`), and Jak stands next to the other air train. The
prompt's drawing and conditions (`hj2-travel-idle`) are shared with the time gates. Jak 2 hides
the port's air train once the game is over; here both always run.

### 6.7 Rebuilding Jak 2's models

`rebuild_model` (the level port's `common/glb.py`) turns a Jak 2 model rip into a `build-actor`
model:

- **Kept primitives:** only the parts of the model the actor uses.
- **Collision:** a box around the model, or the convex hull of the model (`common/hull.py`, over
  the model's extreme points to stay under build-actor's 255 vertices per collide mesh), bound to
  the main joint like Jak 2's meshes.
- **Joint-bound collision:** a collide mesh can be a joint's part of the model (the vertices mostly
  weighted to it), written in that joint's space. The GOAL collide prim names the joint (transform
  index = joint index + 1); build-actor's collide joint id is unused at runtime.
- **Borrowed animations:** a model can take its animations from another rip with the same joints.
  Jak 2 keeps the trapeze's swings in the balloon lurker's art group, and the rip exports them
  there.
- **Rest pose:** `build-actor` needs at least one animation, and some rips have none (Dead Town's
  slabs, the construction site's doors). `rebuild_model` then writes a one-frame animation of the
  skin's rest pose: each joint's local transform is the inverse bind matrix of its parent times
  the inverse of its own (`rest_pose_anim`).
- **Hull heights:** a hull can keep only the vertices between two heights (`{"hull": y_min,
  "y_max": y}`), to keep a platform without what hangs under it (the construction site's bomb
  elevator: its 20 m platform, not its 64 m screw).
- **Models without an actor of their own:** a model's `extras` build a model that a class spawns as a
  child (the bomb elevator's hinges).

### 6.8 The end of the game

Every level is placed as it is once Jak 2 is finished. The entity dumps list every actor of every
story state; Jak 2 only births an actor when its `kill-mask` shares no bit with its level's
`task-mask` (`entity.gc`). The level port reads Jak 2's actors through `games/jak2.py` (`Story`),
which computes that mask for the end of the game:

1. **The level's task area and base mask:** its `:taskname` and `:base-task-mask` in Jak 2's
   `level-info.gc` (`ruins` for `ruins` and `sagehut`, `city` for the districts...).
2. **The story nodes of that area,** in their order in Jak 2's `game-task.gc` (324 nodes), all
   closed but the manifest's `open_tasks`, change it like `level-method-22` does: `abs-task-mask` sets it,
   `set-task-mask` adds bits, `clear-task-mask` removes them.
3. **The bit `never`** is always there (Jak 2's settings add it): its actors are never born.

Only the story bits are computed (`task0` to `task7`, `done`); `ctywide`, `primary0` and the movie
bits depend on the levels loaded and the cutscenes, and are left as before. What the end of the game
removes: the story's enemies and characters, Dead Town's slabs, bridge, floating platforms and flag
(alive only before the tower falls, kill-mask `0xffff0ffe`), the palace roof's electric gates, the
elevator to the palace's inside (`com-elevator-3`, only for the sneak-in: `com-elevator-2` to the
roof stays), the mountain's shard, crates of missions. Jak 2 also marks some actors dead in the save
once broken, which no mask shows: the fortress exit's trap doors, broken by the escape. They are
placed whole, for Jak to break ([6.11](#611-the-prison-and-the-way-out-of-the-fortress)).

**The palace plaza before Mar's tomb (phase 20).** The plaza alone is as it is at the start of the
game: the manifest's `story.level_open_tasks` takes `canyon-insert-items-shard` and
`canyon-insert-items-resolution` as open for the source levels `ctypal` and `ctywide` (their actors,
background prototypes and scripts; no other `ctywide` actor or script depends on these nodes), the
rest of the city stays at the end. What changes, as in Jak 2:

| Element | At the start (now) | At the end | Decided by |
|---|---|---|---|
| The wall under the Baron's statue (`ctyp-statue-wall-breakable.mb`, TIE, solid) | Shown: the tomb's way is shut | Hidden | `level-method-22`, `canyon-insert-items-shard` (`STORY_PROTOTYPES`) |
| The statue's rubble (`ctyp-statue-rubble-a`, `-b`, `-big-a`) | Hidden | Shown | The same |
| The Baron's intact statue on the wall (`baron-statue`, a `ctywide` actor, 250 m high, no collision; in `havenj2`'s mesh) | Placed | Not placed | Its own code kills it once `canyon-insert-items-resolution` is closed (`ctywide-obs.gc`, `ACTOR_GONE_AFTER`) |
| The broken statue and the broken wall (`ctypal-baron-statue-broken`, `ctypal-broke-wall`, in the plaza's mesh) | Not placed | Placed | Their own code, `canyon-insert-items-resolution` (`ACTOR_SHOWN_AFTER`) |
| The tomb's airlock (`com-airlock-outer-22`, behind the wall) | Shut | Shut (the tomb isn't ported) | Its `on-notice` |

The Mods menu's "Mar's tomb" warp (`hj2-ctypal-tomb`, 11 m in front of the wall) lands on the
plaza, facing the wall. To port the plaza at the end again, remove `ctypal` and `ctywide` from
`level_open_tasks`.

### 6.9 Dead Town

Dead Town (`hj2-ruins`) is reached through the slums' airlock, at the end of the game: its tower
has fallen ([5.1](#51-background-and-collision)). The Sage's hut (old Samos', Jak 2's `sagehut`) is
merged into it (its `sources` in the manifest): Jak 2's continues load the hut with Dead Town, shown
`'special` (drawn, but never the level Jak is in), and Dead Town's regions showed and hid it. As two
levels, the hut only appeared once those regions loaded it, next to a Dead Town without it. Its
actors (`ported_etypes`, `hj2-ruins-obs.gc`, models rebuilt from Jak 2's):

| In game | Jak 2 | Here |
|---|---|---|
| The sea | its own ocean map | `*ocean-map-hj2-ruins*` ([5.4](#54-water-and-ocean)) |
| Bars Jak swings from | `swingpole` | Jak 3's `swingpole` (the bars themselves are background) |
| Beams slipping down when Jak comes near | `beam` | `hj2-ruins-beam`: Jak 2's slide animation, once, when the camera is within 25 m |
| Birds, street lights | `ruins-part` spawners | [5.3](#53-particles-and-sprite-textures) |
| The 3 pillars the titan suit knocked down | `ruins-pillar-collapse` | `hj2-ruins-pillar`: fallen (frame 0 of Jak 2's `-end` animation, the actor's name picks which), solid and walkable on 32 collide meshes bound to their pieces |
| Stone blocks | `pushblock`, `throwblock` | Baked into the level's mesh with a collision box (`mesh`) |
| The Sage's hut | `sagehut` | Part of the level. Mods menu: Dead Town: the Sage's hut |

Gone at the end of the game ([6.8](#68-the-end-of-the-game)): the slabs on pillars, the tower's
bridge, the floating platforms and the flag (their phase 11 ports are removed, commit `e769d5e2a`
has them). Not ported: the enemies, the walls the titan suit breaks (no rip has their end pose),
Jak 2's sounds.

### 6.10 Construction site, fortress and stadium

- **Construction site** (`hj2-cons`, `hj2-cons-obs.gc`): the silo doors (each leaf solid on its
  joint) and the bomb elevator (solid at its platform, its hinges drawn by a child process), still
  like at the end of the game.
- **The inside of the fortress** (`hj2-forta`, `hj2-fortb`, Jak 2's `forresca` and `forrescb`): the
  slums' fortress gate opens on it ([6.3](#63-doors-and-elevators)), and its regions load the far
  end, whose gate opens on the prison ([6.11](#611-the-prison-and-the-way-out-of-the-fortress)).
  Their moods follow Jak 2's (the fortress's four light groups, flickering electricity). Its laser
  turrets, electric belt, buttons and lights: [6.12](#612-hazards-and-decor-of-the-places). Mods
  menu: Inside the fortress.
- **The stadium's race track** (`hj2-stadd`, Jak 2's `stadiumd`): loaded by the stadium's regions,
  with Jak 2's lights and shimmering force field (palettes 5 and 6), its race hatch shut (baked into
  its mesh). The force field's ring of walls isn't placed ([14](#14-not-done-yet)). Mods menu:
  Stadium race track.

### 6.11 The prison and the way out of the fortress

Jak 2's escape from the fortress, open at the end of the game: the far gate of the fortress
(`fort-entry-gate-11` in `forrescb`) opens on the prison, whose tunnels lead to the way out
(`forexita`, then `forexitb`), whose gate opens on the slums. Each step is Jak 2's own script:

| Step | Jak 2 | Loads |
|---|---|---|
| The fortress's far gate, and its other side in the prison | `fort-entry-gate-11`, `fort-entry-gate-20` | `hj2-prison` + `hj2-fortb` |
| The prison's tunnels | regions 775, 530 | `hj2-prison` + `hj2-fexa` |
| On to the end of the way | region 300 | `hj2-fexa` + `hj2-fexb` |
| The gate to the slums, and its city side | `fort-entry-gate-5`, `fort-entry-gate-19` | `hj2-fexb` + `havenj2` + `hj2-slmb` |

The slums' side (`fort-entry-gate-19`) waits for `forexitb` to be loaded: it only opens when Jak
comes out of the fortress, like Jak 2's. The two gates of each pair stand back to back, 2 m apart,
and each opens toward Jak's back only once the other is open (`next-actor`): the far gate opens
once the prison is loaded and drawable by the renderer, the prison is shown as it opens, and the
prison's gate opens with it. A gate showing its level seconds after opening (phase 19's renderer
wait) let Jak step between the two before the second existed, and both then stayed shut
([6.1](#61-how-jak-2-loads-its-levels)). Their elements (`hj2-prison-obs.gc`, `hj2-fexa-obs.gc`,
`hj2-fexb-obs.gc`, models rebuilt from Jak 2's):

| In game | Jak 2 | Here |
|---|---|---|
| Cell doors | `prsn-cell-door` | `hj2-prsn-cell-door`, shut (Jak 2 opens them in a cutscene only), solid |
| Vent fans | `prsn-vent-fan` | `hj2-prsn-vent-fan`, turning |
| The torture machine | `prsn-torture` | `hj2-prsn-torture`, its animation in a loop, its body and arms solid on their 9 joints like Jak 2's collide meshes |
| Cells hanging from a rail | `prsn-hang-cell` | `hj2-prsn-hang-cell`: 8 cells an eighth of a lap apart on the entity's path, one lap in 100 s |
| The warp gate | `warp-gate-b` | `hj2-warp-gate-b`, Jak 3's `warp-gate` with Jak 2's model without its energy: at the end of the game Jak 2's leads to the strip mine, not ported, so it goes nowhere |
| Scissor lifts | `fort-lift-plat` | `hj2-fort-lift-plat`, Jak 3's `plat`: along its path (sync), or, with the `user18` option, in place raising its deck in its animation. Deck rideable, arms and base solid, on their joints |
| Trap doors over the drops to the slide | `fort-trap-door` | `hj2-fort-trap-door`, solid (the hull of its model) until Jak lands on it with a dive attack (`flop`): its 17 pieces fly apart (`joint-exploder` with `hj2-fort-trap-door-explode`), Jak 2's `trapdoor` (`j2forex2`) and `wcrate-break` sounds, and it stays broken, hidden, until `hj2-fexb` unloads: whole again each time the level loads (Jak 2 marks its entity dead, broken for good in the save; phase 20, the user's choice) |
| The pool under the trap doors | `water-anim-fortress` | `hj2-fort-pool`, its surface (alpha blended) at the water's height; swimming is its `water-vol`'s region, whose height is the top of its box (no `water-height` lump) |
| The slide | `slide-control` | Jak 3's `slide-control` (the same class) with Jak 2's curve. Its code and Jak's slide states (`target-tube.o`) and animations (`jak-tube+0-ag`) are not in GAME: `hj2-fexb`'s DGO carries them, as Jak 2's `FEB` and Jak 3's `PRECC` do (the `code` of the level, the manifest's `art_groups`) |
| Crates, swinging bar | `crate`, `swingpole` | Jak 3's |

Their particles: [5.3](#53-particles-and-sprite-textures) (382 spawners in the prison alone). Left
out: the chair (a cutscene prop),
the guards, the torture cutscene's lightning. Moods: Jak 2's (`update-mood-prison` at the end of the game, `update-mood-fortress`).
Mods menu: Warp outside the city, Fortress: the prison (no warp to the way out since phase 20).

### 6.12 Hazards and decor of the places

Phase 15's rule: every level as complete as Jak 2's at the end of the game, with every hazard that
hurts Jak, and no enemy. An inventory of Jak 2's actors spawned then found 8486, of which 3653 were
dropped, 2938 of them part spawners ([5.3](#53-particles-and-sprite-textures) now places them).
Each class below is Jak 2's, ported as `hj2-*` with Jak 2's model rebuilt by `build-actor`
(`ported_etypes`, `named_actors`):

| Place | In game | Here |
|---|---|---|
| Palace cable (`hj2-pcab-obs.gc`) | 7 nuts turning on the cable by sixth turns, Jak rides them | `hj2-pal-cable-nut` |
| | 4 hinged platforms that shake and swing down under Jak | `hj2-pal-falling-plat` |
| | 3 fans turning on the cable, their poles circled by lightning rings that hurt Jak | `hj2-pal-electric-fan`: Jak 3's lightning; the 24 KB process heap Jak 2 gave it is set in the type's cached `entity-info` (the default is 16 KB) |
| | The rotating gun spinning and firing while Jak is near | `hj2-pal-rot-gun`: region 429 sends it `trigger` and `untrigger` (`region_script_overrides`) |
| | 2 gun turrets: lock on, burst of guard shots, destroyed by one hit and stay so | `hj2-pal-gun-turret`, a Jak 3 `enemy` subclass; `joint-exploder` with its explode model; Jak 2's `sew-gunturret` particles; their shots flash the mood's palette 6 (`update-mood-hj2-pcab`) |
| | 6 searchlights | Jak 3's `searchlight` (`searchlight.o` linked in HJQ: the hub is never loaded with the cable) |
| Palace cable and roof (GAME, `hj2-common-obs.gc`) | The flip steps standing up, solid; the windmills | `hj2-pal-flip-step`, `hj2-pal-windmill` |
| Palace roof | The palace's inside seen through the roof's glass | `hj2-pal-lowrez-throne`, Jak 2's low-res throne room, its idle in a loop (the inside of the palace isn't ported) |
| | The two energy posts, broken | `hj2-pal-prong`: the base only, solid |
| Mountain temple (`hj2-mount-obs.gc`, placed in `hj2-mtnx` and `hj2-mount`) | The 3 floor buttons and the dice button pressed, the 5 steps ejected from the walls, the lens room (lens, shutter, floor), the 5 dice laid flat over the dark eco | `hj2-mtn-button`, `hj2-mtn-dice-button`, `hj2-mtn-plat-eject`, `hj2-mtn-lens`, `-lens-base`, `-lens-floor`, `hj2-mtn-dice` |
| | The dark eco pool under the dice kills Jak | `hj2-dark-eco-pool`: its surface in `hj2-mtnx`'s mesh; the process kills Jak below its height inside Jak 2's `vol` boxes (Jak 3's water regions only send `water` to a `water-anim`) |
| | The return platform riding down from the temple | `hj2-mtn-plat-return` (`mtn-plat-return-5`) |
| Temple gully (`hj2-mtnx-obs.gc`) | The avalanche, hurting Jak | `hj2-mtn-aval-rocks`: 48 rocks simulated on the background collision (Jak 2's streamed fall animation isn't extracted); region 894 shows and hides it |
| Dead Town | The fallen pillars | [6.9](#69-dead-town) |
| Dig | The stomp blocks | [6.5](#65-the-dig) |
| Fortress (`hj2-fortb-obs.gc`) | 8 laser turrets: sweeping lasers, 3 guard shots when the laser touches Jak; invincible like Jak 2's | `hj2-fort-turret`, a Jak 3 `enemy` subclass |
| | The electric belt: lightning arcs riding a rail across the corridor | `hj2-fort-elec-belt` |
| Fortress (GAME, `hj2-common-obs.gc`) | The 5 rescue buttons and their 5 green lights | `hj2-fort-elec-button`, `hj2-fort-led` |
| Castle pad (`hj2-caspad-obs.gc`) | The electric gate in front of the castle, hurting and pushing Jak back | `hj2-caspad-elec-gate`, a Jak 3 `elec-gate` subclass with Jak 2's parameters |
| Pumping station (`hj2-atoll-obs.gc`) | The gun buoy keeping Jak out of the open sea: surfaces 20 m ahead of him, warns, then fires homing shots that kill him | `hj2-gun-buoy`; regions 177, 353 and 873 send it `kill-player` (fires without warning). Unlike Jak 2's, its shots stop at walls and the ground, and it can be destroyed: Jak 2's 12 hit points (10 per strong hit), then it blows up for good until the station loads again (phase 18) |
| Haven Forest (`hj2-forest-obs.gc`) | 13 wrens pecking and flying off, or flying their curves; 7 schools of 12 fish | `hj2-wren`, `hj2-fish-manager` |
| Oracle, hideout, garage, Vin's room | 20 banners; the swinging lamp and its cone of light; the strip curtain (each strip solid); 7 turbines throwing lightning | `hj2-oracle-*-banner` (`hj2-anim-loop`), `hj2-hide-light`, `hj2-gar-curtain`, `hj2-vin-turbine` |
| Garage (GAME, `hj2-common-obs.gc`) | 2 parked cars, solid | `hj2-dummy-vehicle`: Jak 3's car of the `art-name` lump (`string`), its art in the hub |

**Decor baked into meshes.** Jak 2 props that never move (or whose idle is one frame) are a level's
`mesh` props, with a collision box where Jak can touch them: the Hip Hog's trophies, mirror and
whack-a-metal cabinet, the hideout's bike and faucet, the garage's bikes, Rift Rider and welding
project, Dead Town's blocks, the race track's hatch, the kiosk's banner and sign, Onin's brain, the
canyon's lighthouse, cogs and lens. Mesh props are lit through the level's time-of-day palettes
(`steps/mesh.py`, `palettes`): outdoors palette 0 is the ambient light and 1 to 4 the sun
directions. Interior moods light other palettes (the Hip Hog only palette 1), so the interiors'
meshes say `"sun": null` (the Hip Hog, the hideout, the garage, Onin's tent): the same light in all 8
palettes. With the light in palette 0 only, the Hip Hog's and Onin's props were black.

**`hj2-common-obs.gc`** (GAME) holds the classes of levels loaded together, and two bases:
`hj2-anim-loop` (a model looping its idle, no collision) and `hj2-still-prop` (a still, solid
model), with the macros `def-hj2-anim-loop` and `def-hj2-still-prop` (a class each, since
`def-actor` makes one skeleton group per type). A macro exists in a `goalc` session only once its
file is compiled, and `(mi)` skips up-to-date files: a class in another file is written out
(`hj2-oracle-obs.gc`), never declared with the macro.

### 6.13 Small places

Three small Jak 2 levels that the city or the mountain loads with no door: Jak 2's regions load and
show them, translated like the others ([6.1](#61-how-jak-2-loads-its-levels)).

| Level | Jak 2 | Loaded by | Holds |
|---|---|---|---|
| `hj2-kiosk` | `kiosk` | `hj2-marka`'s regions (`havenj2 hj2-marka hj2-kiosk`) | The bazaar's stall, its mesh props and particles; the city's mood |
| `hj2-onin` | `onintent` | `hj2-markb`'s regions | Onin's tent, its brain as mesh, its particles; its own mood ([8.1](#81-moods)) |
| `hj2-mincan` | `mincan` | `hj2-mount`'s regions, behind the open iris doors | The canyon, its lighthouse, cogs and lens as mesh; the mountain's mood |

## 7. Navigation and traffic

### 7.1 Navigation data

Jak 2 gives each city district its own `city-level-info` (the traffic data: a grid of cells holding
nav segments, and a nav graph of nodes and branches, linked to the neighbor districts') and its own
nav meshes. These structures have the same layout in Jak 2 and Jak 3.

1. **Export.** The decompiler copies them out of each bsp as they are (`extract_nav.cpp`): the
   objects the roots lead to, with their pointers, type tags and symbols. A res-lump's `data-top`
   points past its data (to the next object): it isn't followed, and is rebuilt.
2. **One per district.** Each district level keeps its own, as it is (the level port's nav step,
   `<district>-nav.json`, 36 to 124 KB): its grid of 25, 40 or 50 m cells, its nav graph and its
   links to its neighbors' graphs, and its nav meshes. The hub has none, like Jak 2's `ctywide`. The
   traffic engine (Jak 2's and Jak 3's are the same) links the city-level-infos of at most 2 levels,
   when they are displayed (`'level-loaded`), and unlinks one when it is hidden (`'level-killed`):
   the 2 districts loaded with the hub. Links resolve by graph id, the ids are Jak 2's (unique).
3. **Node levels.** Each node names the level it belongs to: when a level is unloaded, the traffic
   engine stops the vehicles heading to its nodes by that name (`deactivate-all-from-level`). The
   nav step renames Jak 2's district names to ours (`ctysluma` to `hj2-slma`).
4. **Cells.** The traffic engine activates a cell by the camera's distance to its sphere (radius +
   20 m always, + 120 m for pedestrians, + 200 m for vehicles in view), keeps at most 255 active
   cells per level, and kills an object outside the active cells of the linked levels: the traffic
   only lives where the city is displayed, with Jak 2's reach.
5. **Missing nav mesh.** 33 pedestrian segments of `ctygenc` are on a nav mesh no level has: they
   get nav mesh 0, which the traffic engine never spawns citizens on.
6. **Build.** Each district's blob goes into its bsp through `nav_data`. Jak 3 initializes the nav
   meshes at level load (the same `initialize-mesh!` as Jak 2). The traffic start unlinks the
   districts still loaded first (`havenj2-traffic-start`): a traffic stopped while they stayed (the
   Mods menu, the hub hidden) never undid their links to each other, and `level-link` only
   resolves the links not resolved yet. It unlinks only a graph already linked (its nav graph's
   `patched`): a graph never linked still holds indices where `level-link` writes pointers, and
   `level-unlink` overwrote them. That corrupted graph crashed the game going down the palace
   pillar (an `h-bike-c` in method 15 of `nav-branch`).
7. **Earlier, merged (phases 6 to 14):** the 15 districts were merged into one city-level-info
   with a 50 m grid, in the city level, then (phase 14) in the hub. In the hub it spawned the
   traffic over districts that weren't loaded: vehicles floating over the void in the first
   phase-14 test. Phase 15 gives each district its own again, as Jak 2 does.

### 7.2 Traffic

Jak 3's citizens (`citizen-norm`, `citizen-chick`, `citizen-fat`), Freedom League guards
(`crimson-guard`) and hover vehicles (`bikea` to `bikec`, `cara` to `carc`) run on Jak 2's
navigation data, driven by Jak 3's traffic engine. The traffic code and art are in the hub, which
starts it when it is shown; the traffic lives on the navigation of the displayed districts. Parked
vehicles wait at Jak 2's parking spots, and the guard turrets answer the squad's alert
([5.6](#56-city-actors)).

**Jak 2's alert** (`*mod-jak2-haven-city-alert*`, always on since phase 20, when its Mods
menu entry was removed; read every frame; phase 19). Jak 3 kept Jak 2's alert state machine as
`ff-squad-control-method-45`, but in havenj2 it never rose: `squad-control-method-18` only raises
it against the squad's primary target, which only Jak 3's `ctywide` sets (`settings.gc`, with
`*city-mode*` `'ctywide`, which havenj2 doesn't set: `level.gc` would then load `ctywide`'s sounds).
Jak 3's table also has one alert level of five, and its guard count returns nothing, so an alert
never ends. havenj2's DGO links `ff-squad-control.o` before `havenj2-traffic.gc`, which replaces
method 45 there (Jak 3's city links its own):

| Part | How |
|---|---|
| Target | Every frame, Jak is the squad's primary target (`squad-control-method-27`) |
| Raised by | A citizen hit (Jak 3's own) or a guard hit: 1 (the guard's `event-handler`, replaced in havenj2's DGO, calls `citizen-method-210` like Jak 2's `trigger-alert`). A guard vehicle hit (`vehicle-method-130`, empty in Jak 3): 2. Dark Jak: 2, every frame he is dark (Jak 2 raised it once, when he transformed) |
| Levels | Jak 2's five `*alert-level-settings*` in Jak 3's layout (`*hj2-alert-level-settings*`): guard counts, aim and delays per level. Jak 2 sends no grenadier; levels 2 to 4 add 1, 2 and 2 (phase 20, the user's request: the grenade launchers above the tazers' level). Guard bikes and Hellcats get the table's count (Jak 2: 1, 0, 2, 3, 3 bikes and 1, 0, 0, 2, 2 Hellcats), at most 3, and none while their own toggle is off (`hj2-guard-vehicle-caps`) |
| Timer | Jak 2's: 30 s after the last offence (faster while Jak hides), then the ending: no new guard or guard vehicle, the hunters stand down, and the level falls to 0 3 s after the last hunter stopped (Jak 2 waited for every guard to leave: Jak 3's guards keep patrolling, so only the hunters count). Every 8 kills raise the level |
| Hunt | Jak 3's guards ignore `'alert-begin`: each frame of an alert, every guard gets `'member-attacked` (the hatred Jak 3 gives a guard Jak attacks) and every guard vehicle `'alert-begin`; at the end, the guards lose that hatred and get `'end-pursuit`, the vehicles `'alert-end` |
| Sound and HUD | Like Jak 2: while Jak 2's city music (`j2city1`) plays, the `sound-mode` setting 1 (MIDI register 3) switches it to its alert mode; otherwise, or with the music volume at 0, the alarm plays (`city-alarm`, Jak 2's `CTYWIDE2` bank, loaded as `j2ctywi2`). The minimap flashes (`wanted-flash`) |
| Switch | Turning it on or off resets the alert. Off: Jak 3's own method 45, no primary target |

The guard vehicles chase Jak like Jak 2's `vehicle-guard` ([7.3](#73-hellcats)). The city's guard
turrets (`hj2-cty-guard-turret`) follow Jak 2's rule: they pop up and fire at Jak while he flies a
vehicle within 100 m and the alert is at least 1, and sink once he is 120 m away or both on foot and
forgiven. Jak 2 has no height rule: "in the air" is in a vehicle. Off, the turrets stay down.

**Guards' lines.** The guards speak Jak 2's Crimson Guards' lines: each of Jak 3's `guard-*` speech
types (and its second voice, the next type) gets the Jak 2 type said at the same moment of Jak 2's
guard code, with its delays (`hj2-restore-city-speeches`, havenj2-traffic.gc):

| Jak 3 type | Jak 2 type |
|---|---|
| `guard-chatter` (on patrol) | 1 |
| `guard-chatter-jak` (Jak near) | 4 (seeing a target that isn't hostile) |
| `guard-go-hostile` | 3 |
| `guard-hit` | 11 |
| `guard-battle-victory` | 10 (Jak killed) |
| `guard-change-targets` | 2 (Jak seen again) |
| `guard-bumped-by-jak` | 14 |
| `guard-generic-battle` | 6 and 9 (fighting) |
| `guard-witness-death` | none in Jak 2: Jak 3's lines |

| Part | How |
|---|---|
| Code | HJ2 links the objects of Jak 3's city DGO (`cwi.gd`) in the same order (the city's `traffic` in the manifest), without Jak 3's city itself: its props, particles, missions and scenes, its trail graph and its height map (its searchlights and force-field wall colors, `ctywide-texture`, are kept). The height map (how high the vehicles fly) is Jak 2's, `havenj2-height-map.gc` |
| Art | The traffic types' art groups (the traffic's `art`, `hellcat-ag` included) are in HJ2 and in havenj2's `.fr3`, instead of the levels Jak 3's city borrows. The vehicle HUD's health bar is near the end of havenj2's texture page, before the minimap's maps ([7.4](#74-minimap)) |
| Start and stop | `havenj2-login` (callback slot 33) allocates the traffic engine, the Freedom League squad and the attack controller in havenj2's heap; `havenj2-logout` (34) drops them. `havenj2-activate` starts the traffic: the traffic manager first (it clears every traffic type's level), then every attacker freed (`cty-attack-reset`), then havenj2 as the level of the citizens, guards and vehicles |
| No faction manager | Like Spargus (`waswide-init.gc`). Jak 3's faction manager runs its territories from the branches' `clock-type`, which Jak 2's graph uses for traffic lights, and it `break!`s on a level name it doesn't know. The traffic code checks that it exists everywhere but in the guards' post: a one-line vanilla edit in `guard.gc` adds the check (marked `og:jak2-haven-city added`) |
| Attack controller | A guard or a citizen takes an attacker from `*cty-attack-controller*` when it spawns. `crimson-guard` only checks that the controller is nonzero: with `#f` the first guard crashes the game. havenj2 allocates it like Jak 3's city does |
| Density | Jak 2's numbers, by Jak 3 type (`*havenj2-traffic-want-counts*`): 15 male, 15 female and 14 fat citizens, 9 guards, 8 of each hover bike and 7 of each car. Set before `restore-default-settings`, which derives the target and reserve counts from them. A type's `want-count` is an `int8`, at most 20 |
| Switch | `*mod-jak2-haven-city-traffic*`, always on (its Mods menu entry was removed in phase 20) |
| Sounds | The vehicles', citizens' and guards' sound effects are in Jak 3's city half banks (`citycarh`, `citypedh`, `cityffh`), which Jak 3's city loads through its borrow manager: havenj2 loads them with Jak 2's city banks ([8.4](#84-sound-and-music)). The citizens speak Jak 2's lines, the guards Jak 3's |

### 7.3 Hellcats

Jak 2's Freedom League Hellcats can fly in havenj2's traffic, and only there (`*mod-jak2-haven-city-hellcats*`,
always on since phase 20; until then a Mods menu entry, off by default). Jak 3 maps the
vehicle type `h-hellcat` to the traffic type `guard-car` and ships its constants and skeleton, but
only declares the class and never spawns it.

| Part | How |
|---|---|
| Classes | `h-hellcat` and its guard pilot `hj2-hellcat-pilot`, in `havenj2-traffic.gc`, copied from the Jak 3 mod Haven City: Breath of Peace |
| In game | Hellcats flying the traffic lanes. Jak can steal one and fire its front gun with R1. Stealing one throws its guard pilot out as a guard on foot (`vr3`, Jak 3's own): that raises the alert to 2. Silent, like the other vehicles |
| Pursuit | While Jak 2's alert is on ([7.2](#72-traffic)): Jak 2's `vehicle-guard` AI, ported from Breath of Peace and shared with the guard bikes (`hj2-guard-vehicle-*`, an `hj2-pursuit` per vehicle). A vehicle arms on `'alert-begin` from alert level 2 (or when Jak hits it, which raises the alert to 2), looks for Jak in its `active` state, chases him in `hostile` on sight (flying at where he will be, up to twice its top speed) and fires its front gun with the alert level's settings, gives up after 8 s out of sight or when two other units see him, and stands down on `'alert-end` or `'end-pursuit`. Stolen (`player-control`), it drops its alert |
| Spawning | Jak 3's `traffic-object-spawn` has no `guard-car` case. havenj2's DGO links its own copy of `traffic-manager.o`, and `havenj2-traffic.gc` wraps that copy: no vanilla edit, and Jak 3's city links its own again |
| Count | `want-count` of `guard-car` 3 (`HJ2_HELLCATS`). The squad rewrites the `guard-car` target count every frame from its alert settings; `hj2-guard-vehicle-caps` sets the squad's guard type 5 caps (`ff-squad-control-method-56`) every frame: the alert table's count, 0 to 3, while Jak 2's alert is on; 3 while it is off (Jak 3's table gives the Hellcats none) |
| Art | `hellcat-ag` in the traffic's `art`; the level builder extracts it from the first Jak 3 DGO that has it. The pilot uses `crimson-guard-ag` |
| Switch | Turning it on or off restarts the traffic if it runs |

**Guard bikes** (`*mod-jak2-haven-city-guard-bikes*`, always on since phase 20;
phase 18). Jak 2's Crimson Guard bikes fly the traffic lanes with a Freedom League
pilot, like the Hellcats:

| Part | How |
|---|---|
| Model | Jak 2's `crimson-bike` (the rip of `lwideb`), rebuilt by build-actor as `hj2-guard-bike` (manifest `models`, in the hub's DGO: 11.5 KB). The rip draws the intact, damaged and broken parts at once and build-actor models have no masks: only the intact ones are kept (`prims`), so damage doesn't show |
| Class | `hj2-guard-bike` (Jak 3's `h-bike-base`, `havenj2-traffic.gc`): Jak 2's collision spheres, the Hellcat's turret on joint 4 and its R1 gunnery (`hj2-guard-gunnery`, shared), the same guard pilot in the bike stance. `*hj2-guard-bike-constants*` copies `*h-bike-a-constants*` (Jak 2's guard bike has bike A's mass, centre of mass and thrusters), with Jak 2's flags (`#x54`), guard type 4 and lights |
| Spawning | Jak 3 has the traffic type `guard-bike` (24) but no vehicle type for it: `hj2-traffic-object-spawn` spawns `hj2-guard-bike` with `vehicle-spawn-hack` |
| Count | `want-count` 3 (`HJ2_GUARD_BIKES`, Jak 2's most); the squad's guard type 4 capped like the Hellcats' type 5 |
| Pursuit | The Hellcats' (above) |

### 7.4 Minimap

Jak 3's minimap shows in havenj2 with Jak 2's city maps, and the guards and guard vehicles show on
it as blue icons with their view cone (phase 19). Always on: Jak 3's own levels are unchanged.

| Part | How |
|---|---|
| When it shows | Jak 3's `minimap` `update!` (`minimap.gc`) draws the city map only while its `ctywide` field holds an active level, read from `(level-get *level* 'ctywide)`. A one-line vanilla edit (marked `og:jak2-haven-city added`) falls back to `havenj2`, so the map hides while the hub is hidden (Jak 2's airlocks) |
| Grid | Jak 2 and Jak 3 share the 5x7 city grid, its texture names (`map-ctysluma`...) and corners (`*minimap-texture-name-array*`, `*minimap-corner-array*`), and the mod keeps Jak 2's world coordinates. A square is drawn when an active level's `city-map-bits` names it: havenj2's level-load-info has the 21 squares with a Jak 2 map (`city_map_bits` `0x39d6f59cc` in its `level_info`) |
| Textures | Jak 3 finds a map by name in the minimap page (`texture-page 8`) of the active levels (`lookup-minimap-texture-by-name`). Jak 2's 21 maps (its per-district `*-minimap` pages, 256x256 or 256x128) are at the end of havenj2's texture page 1566 (the particles' `source_textures`). `hj2-minimap-page-on` (`havenj2-activate`) makes havenj2's minimap page a copy of that page with only the `map-` textures, as texture objects of its own: Jak 3 lays out the minimap pages and the sprite pages separately (`lay-out-hud-tex`, `lay-out-sprite-tex`), each moving the texture addresses of its pages. The copy keeps the page id and the indices, which the PC texture pool maps to the `.fr3` textures. Made once in the global heap (about 3 KB); `havenj2-logout` drops it from the level (`hj2-minimap-page-off`) |
| Guards | Jak 3's `crimson-guard` adds its icon (class 25, `guard-frustum`: blue, with its view cone) when the traffic sends it out, but only dropped it when its process died: a guard back in the traffic's pool kept a stale icon and got no new one when sent out again. havenj2's DGO wraps its `go-inactive` (`havenj2-traffic.gc`) to fade the icon out, like Jak 2's `inactive` state |
| Guard vehicles | The Hellcats and guard bikes get a `minimap` field, added when the traffic sends the vehicle out (`vehicle-method-123`, Jak 2's 128), faded out when it goes back to the pool (122, Jak 2's 127), is destroyed (124, Jak 2's 129) or is stolen by Jak (`player-control`). Its class is `*hj2-guard-vehicle-minimap-class*` (`jak2-haven-city-world.gc`, in GAME so that an icon still fading after havenj2 unloads never reads freed memory): Jak 3's `guard-frustum` at scale 1.4, set on the connection right after `add-icon!` (which only takes an index into `*minimap-class-list*`) |
| Sizes | Jak 2 drew a guard vehicle with its plain `guard` class (14): a dot drawn on the screen at 20 units, while a foot guard's `guard-frustum` dot is drawn into the 128-texel map texture (a diamond of half-diagonal 12), which shows at 112 screen units: the vehicle about 1.4 times larger. Jak 3's `draw-frustum-2` ignored the class `scale`, so a vehicle given `guard-frustum` looked exactly like a guard. A one-line vanilla edit (`og:jak2-haven-city added`) scales that diamond by the class `scale`; every stock frustum class has 1.0 |
| Cones | `draw-frustum-1` draws each frustum class's view cone (texture `map-guard-frustum`, 80 m long) at `frustum-alpha`, which Jak 2 and Jak 3 fade to 0 while Jak pilots a vehicle: in the guard vehicles' chases the cones were never seen. A vanilla edit in `sub-draw-1-1` (`og:jak2-haven-city added`) keeps them while `havenj2` is loaded; elsewhere they still fade out. The guard vehicles show a cone too (Jak 2's had none), at its usual length |

## 8. Moods, time of day and weather

### 8.1 Moods

Each level's mood (GAME) follows its Jak 2 mood. `update-mood-havenj2`, the mood of the hub and of
every district (the template's `level_info.mood`), follows Jak 2's `update-mood-ctysluma`
(palettes 5 street lights, 6 flames, 7 neon signs). The places follow
`palshaft`, `palroof`, `palcab`, `consite`, `consiteb`, `ruins` (Dead Town and the Sage's hut),
`atoll`, `atollext`, `mountain`, `forest`, `caspad`, `dig1` (red fog and lights), `forresca` and
`forrescb` (the fortress's light groups, flickering palettes) and `stadiumb` (the race track's
lights and force field); interiors use fixed palette weights. Onin's tent has its own,
`update-mood-hj2-onin` (Jak 2's `update-mood-onintent`: palettes 0 and 1 full, the flames' palettes
2 to 7 at their mean level). The other small places borrow one (`hj2-kiosk` the city's, `hj2-mincan`
the mountain's).
The palace cable's palette 6 flashes with its turrets' shots. The dig's
lava pulses use Jak 3's `update-mood-pulse` at full brightness. Interiors have no fog: `fog-dists`
z 255 and w 254, never equal (see [10](#10-jak-2-and-jak-3-differences)).

### 8.2 Time of day

The clock stays at `*mod-jak2-haven-city-hour*` (16:00 by default) while any of the mod's levels
is active (`*havenj2-levels*`, level callbacks 35 and 36), or runs like Jak 2's (day and night).
Mods menu, Time of day: 9:00, 12:00, 16:00, 19:00, 23:00, or the cycle. The default isn't noon: a
frozen noon puts the sun almost straight above and gives a flat, grey light.

### 8.3 Weather

Jak 2 and Jak 3 share their weather system (`mood-control`): the clouds and the fog drift towards
random targets within the ranges of the levels Jak is in (the mod's outdoor levels get Jak 2's: 0 to
1), it rains when both are high, with thunder and lightning, and it snows when the `snow` setting
is on. Jak 3 can draw snow (`update-snow`) but never uses it.

Mods menu, Weather (whole game) chooses the weather everywhere, Jak 3's levels too
(`*mod-jak2-haven-city-weather*`):

| Choice | Clouds | Fog | Snow | Rain |
|---|---|---|---|---|
| Changing (Jak 3's weather) | random | random | off | when both are high |
| Sunny | 0 | 0 | off | none |
| Cloudy | 0.75 | 0.4 | off | none |
| Foggy | 0.4 | 1 | off | none |
| Light rain | 0.75 | 0.75 | off | 0.25 |
| Rain | 0.9 | 0.9 | off | 0.64 |
| Thunderstorm | 1 | 1 | off | 0.75 (the most) |
| Snow | 1 | 0.5 | on | none |

Rain is min(0.75, 4 (clouds − 0.5) (fog − 0.5)), capped by the level's `max-rain`.

A process, `hj2-weather-driver` (GAME), holds the choice every frame: a fixed weather overrides
Jak 3's (`overide-weather-flag`), and nothing Jak 3 leaves behind (another level's weather, a
mission's fixed weather) takes it over. With the changing weather, in the mod's levels, a random
draw Jak 3 stopped starts again. The driver starts the first time Jak enters one of the mod's levels
or picks a weather; until then the game's weather is untouched, and with the changing weather it
touches nothing outside the mod's levels.

### 8.4 Sound and music

The levels play Jak 2's sound: its music, its sound banks (ambiences and object sounds) and its
voice lines. The build copies them from Jak 2's extracted disc (`iso_data/jak2`) into
`out/jak3/iso`, renamed. Without a Jak 2 extraction the levels are silent and the rest works.
Nothing of it is committed.

| Part | Jak 2 | Here |
|---|---|---|
| Music | Each level's `:music-bank` (`city1`, `forest`, `palcab`...), a MIDI bank (`.MUS`), with variations (flava) for the gun, the board, Dark Jak and vehicles | The same `:music-bank`, renamed (`'j2city1`, `J2CITY1.MUS`), played as MIDI by Jak 3's overlord ([4.5](#45-sound)). The city's process sets the flava like Jak 2 (`hj2-update-music-flava`; Jak 3 never sets it). The places without music in Jak 2 (Vin's room, the garage, the construction site...) have none |
| Sound banks | 3 per place: the continues' and region scripts' `want-sound` | The same, renamed (`ctywide1`: `'j2ctywi1`, `J2CTYWI1.SBK`), taken for Jak 3 half banks (`hj2-sound-bank-name->mode`; on PC a bank's size doesn't matter). The free half bank slots (Jak 3 loads 6 at most) take extra banks, loaded with the wanted ones (`hj2-update-extra-sound-bank`): in the city, Jak 3's traffic banks `cityffh`, `citycarh`, `citypedh`, then the Jak 2 banks the sound check lists for the level Jak is in (`*hj2-level-sound-banks*`); in a place, its own first. See "Every level's sounds" below |
| Ambiences | The region scripts' `sound-play-loop` (`city-amb1`, `hiphog-amb`, `forest-amb-1`, `dig-lava`...), and the part spawners' looped sounds (`effect-name` lumps: the fountains, steam vents, barrel fires, water sprays, consoles: 380 spawners in 15 levels) | Kept by the translator; the part spawners' `effect-name`, `effect-param` and `cycle-speed` lumps copied (`effect_lumps`, the particle step): Jak 3's `part-spawner` plays them the same way (`ambient-sound`, `effect-param->sound-spec` are the same in both games) |
| Object sounds | In each class | In the `hj2-*` classes, by Jak 2's names, when a bank loaded where the object stands has them: Jak 3's stand-ins (airlock and lift sounds on Jak 2's doors and elevators, `explosion`, `guard-shot`) replaced by Jak 2's. The particles' `:sound` (the neon signs' zaps, the barrel fires' pops, Vin's screens, the Hip Hog's) kept by the particle step (it dropped them before phase 20). The speakers' hits keep Jak 3's iron crate (Jak 2's play none). What is left out: [14](#14-not-done-yet) |
| Speeches | The propaganda speakers' 54 lines (`*propa-sounds*`) | `hj2-propa-speech`: once the camera is within 55 m, heard from 40 to 55 m, stopped beyond 60 m |
| Guards | The Crimson Guards' lines (speech types 1 to 14) | Given to Jak 3's `guard-*` speech types ([7.2](#72-traffic)) |
| Citizens | Their lines (speech types 16 to 28) | Given to Jak 3's `civ-*` speech types, which Jak 3's city leaves empty (`hj2-restore-city-speeches`, the traffic's speech callback; the traffic manager clears them when it stops) |

**Banks of a level loaded late.** Jak 2 asks for the banks in the region scripts of each level's
borders (`want-sound`), which run only while that level is loaded: a level loaded after Jak crossed
its border keeps the banks of the one before (the gardens' sprinklers were silent, their
`water-veggies` loop in `CTYFARM1`). When the level Jak is in (vis-nick) changes to one of the mod's,
`hj2-update-level-sounds` (GAME) wants the banks of its continue closest to Jak, as a respawn there
would; the regions inside a level still change them as in Jak 2.

**Guards' shots missing (phase 20).** The guards' rifle and tazer (`guard-shot-fire`, `guard-zap`,
also fired by the Hellcats, the guard bikes and the turrets, which shoot `guard-shot`) are in
`cityffh`, and among Jak 2's banks only in `CTYWIDE3` and `CTYFARM1`. Three causes, depending on
where Jak was and in which order the banks had loaded:

- The hub's `:extra-sound-bank` tied `cityffh` to `j2ctywi3`; where Jak 2 wants another bank instead
  (the stadium, the palace, the Hip Hog, the gun course, the hideout, Vin's room...), `cityffh` was
  no longer wanted and its slot went to the next bank loaded. `hj2-update-extra-sound-bank` (GAME,
  every frame of the city's process) now gives the wanted Jak 2 banks, in order, `cityffh`, then
  `citycarh`, then `citypedh`, and makes the hub's `:extra-sound-bank` that list.
- The overlord skipped the reload of a bank it had unloaded, and failed to load a half bank whose
  partner was in the second or third pair of records ([4.5](#45-sound)). The log shows it: after
  `Load soundbank cityffh` or `Load soundbank j2ctywi3`, no `CDvdDriver` line reads its `.SBK`
  (`CITYFFH SBK` was read once in a session that loaded it four times).
- Not a cause: the PC sound engine has no voice limit (`game/sound/989snd`), only each sound's own
  instance limit; the alert's `sound-mode` 1 only raises the music by 11 %; the alarm keeps its own
  sound id.

**Every level's sounds (phase 20).** The level port's sound check
(`scripts/level_port/steps/sound_check.py`, run by the `levels` step; `--steps sound` prints it)
lists, per level, the sounds its content can play: the scripts of its regions and actors, its part
spawners' `effect-name`, its particles' `:sound`, and the GOAL code of the classes placed there
(`sound-play`, `static-sound-spec`, `static-sound-name`... in their forms, the definitions they name
in the level's code, the hub's and the mod's GAME code, and their parents' forms they don't
override), with the hub's traffic for the city. It finds each sound's banks in the `.SBK` name
tables of both discs, and compares them with the level's want sets (each continue's and each
script's `want-sound`; a level without any takes those of the levels loading it). What it found:

- The part spawners' ambient sounds and the particles' sounds were never ported: 380 spawners (the
  palace plaza's and the stadium's fountains, the slums' barrel fires and steam, the atoll's water
  sprays and vents, the gun course's vents, the prison's and the fortress's consoles) and 12
  particles. Both are kept now.
- Jak 2 wants some banks only near the objects needing them, or nowhere: the castle pad's airlock
  and electric gate (`CASTLE2`, `CASTLE3`), the atoll's gun buoy (`ATOLL3`), the fortress gates'
  door sounds (`FOREXIT1`, wanted only by the way out), the warp gates (`FOREXIT1`), the places'
  airlocks back to the city (`CTYWIDE1`). 23 sounds were in no want set of their level, 80 only in
  some. The check lists, per level, the Jak 2 banks holding them, best first
  (`*hj2-level-sound-banks*`, in `jak2-haven-city-levels.gc`); `hj2-update-extra-sound-bank` loads
  them in the free half bank slots: in a place, Jak 2 wants 3 banks and leaves 3 slots free.
- The castle pad's elevator (`hj2-cpad-elevator`) called `hj2-elevator`'s `init-sound!`, which put
  back the palace elevator's sounds over its own (`dig-elevate`): it was silent. It calls Jak 3's
  `elevator` method now.
- The continues the port adds (the hideout's time gate, the cable pillar) had no banks: a respawn
  there, or `hj2-update-level-sounds` picking them, unloaded every Jak 2 bank. They take the banks
  of the nearest continue of their level (`nearest_want_sound`, the levels step).

What is left, by the check: in the city the 6 slots are taken (3 Jak 2 banks and the 3 traffic
ones), so the sounds Jak 2 itself wanted only in some places stay so (the hideout's door, the palace
gate, the farm crops, the turrets' explosion where Jak 2 wants other banks), and the fortress gates
of the slums (`FOREXIT1`) and the port's `port-amb1` (`PORTRUN1`, a mission bank) stay silent, as in
Jak 2. 8 sounds are in no bank of either game, silent in Jak 2 too: the airlocks' `airlock-slide-e`,
the speakers' `icrate-break` and `icrate-nobreak`, the particles' `fire-pop` and `screen-ring`, the
scripts' `city-amb1`, `canal-amb`, `lagoon-amb`. The check also lists the sounds of Jak 3's code
that the levels link but never run as Jak 2's objects (the traffic's Metal Heads, the crates' other
kinds): they play as in Jak 3.

**Names.** Both games have files of the same name (28 sound banks, the music `CITY1`), and Jak 3's
code plays some of Jak 2's voice names (its own copy of Jak 2's `propa` class): the banks and the
music get `j2` (cut to the disc's 8 characters, `renamed` in `scripts/level_port/steps/sound.py`),
the voice lines `j` (`jprop009`, `jcit099a`). The voice lists are the manifest's `sound.voices`,
defined as GOAL arrays in `jak2-haven-city-levels.gc`.

**End of a voice line.** Every Jak 3 line ends with an ADPCM frame flagged "end" (1) and a closing
frame (flag 7, `0x77` bytes); Jak 2's lines have neither, their data just stops. The Jak 3 overlord
streams a line through two 8 KB halves of SPU memory, each marked to loop, and counts on the flag
to stop the voice (`game/sound/common/voice.cpp`): without it, the voice ran on into the other
half and replayed the sentence's previous chunk in a loop whenever `CheckVAGStreamProgress`
(`spustreams.cpp`) missed the voice in the last chunk's half, which depends on where the line ends
in its chunk (phase 19). `pack-vags` now appends both frames to each mono line and grows the VAG
header's size (`add_vag_end_frames`, `goalc/make/Tools.cpp`). The lines play from their speaker
like Jak 3's own: the speech channel sends the speaker's position every frame (`fo-min` 15 m,
`fo-max` 90 m from Jak, curve 9, Jak 2's values too), and the overlord handles a mod line like
any other once `EEVagAndVagWad` picked its wad. Jak 2's lines are mastered as loud as Jak 3's
(about -15 dBFS RMS over speech in both).

**Build.** The level port writes the steps into `jak2-haven-city.gp`, each under a
`(file-exists? ...)`: a `copy` per bank and music (57 files, 14 MB), and `pack-vags` for the 314
voice lines (`VAGDIRM.AYB`, and a 28 MB `VAGWADM.<language>` for each of Jak 2's 7 languages).
`out/jak3` is shared by every mod's worktree: these files have names no other mod uses.

## 9. Travelling

### 9.1 Mods menu

L3 + SELECT opens the Mods menu (retail and debug boots); the mod's entries are under
Haven City: New Dawn. Every warp goes through a continue point, never through `bg`: the hub and its
districts need the level heap Jak 3's own city takes, and a continue point makes the level system
unload every level it doesn't want before loading the new ones (the hub first, then the
continue's districts).

| Entry | Contents |
|---|---|
| Mod enabled | `*mod-jak2-haven-city-enabled*`, off by default (`mod-jak2-haven-city-set-enabled`, GAME). On: the Freedom HQ's time gate stands (`hj2-freehq-activate`), the menu's weather holds (`hj2-weather-update`), the entries below can be used. Off: they are greyed out (`entry-disabled?`), no gate, Jak 3's weather. Jak 2's levels don't read it |
| Warp to Haven City (Jak 2) | `hj2-hideout-start`, in the underground hideout |
| Warp to a district | Each district (one of Jak 2's continues in each) and the places in it: the hideout's street, the fortress gate, the Oracle (outside and inside), the port, the Hip Hog, the gun course, the port's air train, the bazaar (Brutter's stall, the east side), the Industrial Section (Vin's side, Vin's power station, the construction site gate, the south side), Main Town (west side, cable pillar, east side, pillar to the palace), the gardens (mountain airlock, north side), the palace plaza and roof, the stadium grounds, Keira's garage |
| Warp outside the city | Dead Town, the Sage's hut, inside the fortress, the prison, the stadium race track, the construction site, the pumping station, the mountain top, Haven Forest, the castle pad, the dig site, and `freehq-start` (Jak 3's Freedom HQ, by the time gate) |
| Weather | [8.3](#83-weather), with a Time of day submenu ([8.2](#82-time-of-day)) |

The cable pillar's continue (`hj2-cable-pillar`) is one Jak 2 doesn't have (`door_continues`): 8 m
in front of the door, facing it, the camera behind Jak.

### 9.2 Time gates

Two teleporters link the worlds, both Jak 3's warp gate (its model, its particles and sound, its
conditions and Jak's jump into it, `target-warp-out`) as `hj2-time-gate` (GAME), with a prompt
naming the world they lead to:

| Gate | Stands | Prompt | Jak arrives |
|---|---|---|---|
| Freedom HQ (Jak 3) | on the free floor at the back of the main room (710, 80.34, −565 m, found on the HQ's collision dump) | Press triangle to travel through the time (Jak 2) | jumping out of the hideout's gate (`hj2-hideout-gate`) |
| Underground hideout (Jak 2) | in the free corner of the main room (`new_teleporters`) | Press triangle to travel through the time (Jak 3) | standing in front of the Freedom HQ's gate (`hj2-freehq-gate`) |

How each part is made:

1. **The model in a vanilla level.** `freehq` is one of Jak 3's levels and doesn't ship the warp
   gate. Two vanilla edits bring it: `warp-gate-ag.go` in `goal_src/jak3/dgos/freehq.gd` (the art
   group, for the game), and `extra_art_groups_by_dgo` in `jak3_config.jsonc` (its geometry, baked
   into freehq's `.fr3` for the PC renderer). Without the geometry the gate still spawns (its art
   group is in the DGO), so its particles and its jump work but its base is invisible. `out/jak3`
   is shared by every worktree, so a Jak 3 extraction made with another config (master-dev's,
   another mod's) rewrites `freehq.fr3` without it: the level port's `extract` step lists each
   `.fr3`'s merc models (`fr3_check --models`) and extracts again any DGO missing one of its
   `extra_art_groups_by_dgo` models ([3](#3-rebuilding-it-step-by-step)). By hand:
   `decompiler ./decompiler/config/jak3/jak3_config.jsonc ./iso_data ./decompiler_out --version
   ntsc_v1 --config-override '{"decompile_code": false, "levels_extract": true,
   "levels_to_extract": ["FREEHQ.DGO"]}'` (about 90 s).
2. **Spawning without an entity.** `freehq` has no level callbacks: GAME adds two to its
   level-load-info when it loads (slot 35 spawns the gate, slot 36 kills it), without editing
   `level-info.gc`. The gate is spawned into `*entity-pool*`, whose processes belong to the
   default level: `hj2-time-gate-init` sets the process's level to `freehq` before the skeleton is
   made, because a process looks its art up only in its own level. The gate only spawns when the
   model is in freehq's art (`hj2-level-has-art?`).
3. **The hideout's gate** is an actor of `hj2-hide`, written by the level port (`new_teleporters`) with
   its `on-notice` (the destination) and `travel-name` lumps.
4. **The arrival points** (`new_continues`, `target_continues`) stand 6 m in front of each gate, facing away from it,
   the camera behind. The hideout's has the `warp-gate` flag: Jak 3 then looks for the closest warp
   gate entity and plays Jak's jump out of it. The Freedom HQ's gate has no entity, so Jak just
   stands there; that continue is appended to freehq's continue list by GAME.

### 9.3 Respawn points

Respawn points are picked exactly like Jak 2 picks them (phase 15b). Jak 2 and Jak 3 share the rule
(the level group's update in `level.gc`): when Jak's current level, the load-state's `vis-nick`,
isn't the current continue's level, the current continue becomes the closest continue of that
level, never a `no-auto` or `change-continue` one, and stays until Jak enters another level. Scripts
can also set it (`want-continue`).

Jak 2 makes `vis-nick` the level the camera is inside (its bsp's inside test). Custom levels have no
bsp nodes: the engine sees the camera inside every active one, and `vis-nick` would stay on the
district Jak arrived in. So:

| Where | `vis-nick` set by |
|---|---|
| The city | `hj2-update-vis-nick` (GAME): the district holding the street square under Jak (the district map, [6.1](#61-how-jak-2-loads-its-levels)), when it is active. Never the hub (`not-physical`) |
| The places | Jak 2's own door and region scripts (`on-cross`, `want-vis`), kept by the translator |

Dying or saving respawns Jak at one of Jak 2's own respawn points. Every place keeps all of Jak 2's
continues but the title, intro, new game (the prison's `game-start`), demo and cutscene ones
(`scene-wait`), with Jak 2's level lists translated and Jak 2's `no-auto`, `warp-gate` and
`no-blackout` flags (`KEPT_CONTINUE_FLAGS`). A place with only `no-auto` continues (the palace roof)
keeps the previous one, like in Jak 2.

Until phase 15b, a process of the mod moved the current continue every frame to the closest one of
the level Jak was in (`havenj2-update-continue`, `hj2-closest-continue`): removed. The process
(`havenj2-continues-code`, GAME, running while any of the mod's levels is active) now only sets
`vis-nick`, runs the district guard ([6.1](#61-how-jak-2-loads-its-levels)) and puts the ocean of
the level Jak is in first ([5.4](#54-water-and-ocean)).

### 9.4 Saves

Saving works anywhere in the mod's levels: Jak 3 saves the current continue, one of the mod's.
The save screen shows it on the slot:

| Step | How |
|---|---|
| Mark the save | `save-game` of `game-info` is wrapped: Jak 3's runs, then the mark `HJ2S` (`#x484a3253`) goes into a word of the save's header Jak 3 leaves unused (`info-int32 4`) when the current continue is one of the mod's |
| Read it back | Jak 3 copies that word into each slot's preview data (`blind-data 4` of `*progress-save-info*`) |
| Show it | `draw-option` of `menu-memcard-slot-option` is wrapped: Jak 3's slot is drawn, then "Haven City (Jak 2)" under the slot's title |

A method is wrapped by keeping Jak 3's in a global (`(method-of-type game-info save-game)`) and
redefining it to call that first. The slot's level picture is still Jak 3's choice (from the
current task's level).

## 10. Jak 2 and Jak 3 differences

What this port had to learn about Jak 3, as a reference for other ports:

| Topic | What to know | Where it matters here |
|---|---|---|
| Particle texture ids | Texture ids name a page by number: Jak 2's `effects` is page 12, Jak 3's page 12 is `gamefont`; Jak 3's shared sprites are `level-default-sprite` (4) | Smoke and fire texture groups ([5.3](#53-particles-and-sprite-textures)) |
| Particle flags | Same names in both games, but Jak 3's launcher reads some meanings at other bits (the particles' level index takes bits 9 to 12): Jak 2's 12 (time of day tint on relaunch), 16 (acceleration kept in world space), 20 (cone follows the launcher's yaw) and 21 (launch and cone scaled by the launcher's matrix) are Jak 3's 13, 17, 19 and 20 | `CPUINFO_FLAGS` in the level port's `convert/jak2_jak3.py` |
| Particle groups | Jak 3's `defpartgroup` doesn't define the group's name; the known names are constants in `part-groups.gc`. A new group is reached by id in `*part-group-id-table*` | The groups code uses: the speakers' hologram, the crops' bursts (`*hj2-*-group-ids*`) |
| Particle callbacks | A `:func` gets the particle's sprite data (`sprite-vec-data-2d`, or a vector); Jak 2's decompiled callbacks type it as a matrix, same layout (row 0 x y z sx, row 1 flag matrix rot sy) | Copied callbacks ([5.3](#53-particles-and-sprite-textures)) |
| Texture pool slots | The PC pool gives each page of Jak 3's directory as many slots as it has textures: page ids Jak 3 never uses share their first slot, and spill over the next pages' | Sprite page ids ([5.3](#53-particles-and-sprite-textures)) |
| Animated textures | Background draws name an animated texture slot of their game's slot table (`common/texture/texture_slots.cpp`), not a texture | Jak 2's waterfalls and lava ([4.2](#42-level-builder)) |
| Ocean map | Jak 3's `ocean-map` has no `ocean-spheres`; the map drawn is the first displayed level's, in draw order | [5.4](#54-water-and-ocean) |
| Airlock scripts at load | A door born closed (at level load) with Jak on its front side runs its `on-deactivate`, however far Jak is: the side is an infinite plane (`com-airlock-method-26`) | The palace elevator ([6.3](#63-doors-and-elevators)) |
| Continue auto-pick | Jak 2 and Jak 3 share the rule: a continue is picked only when Jak's current level (`vis-nick`) changes, the closest of that level, never a `no-auto` or `change-continue` one | Respawn points ([9.3](#93-respawn-points)) |
| Warp gate arrival | A continue with the `warp-gate` flag makes Jak jump out of the closest `warp-gate` entity (subtypes too); with none found, Jak just stands there | Time gates ([9.2](#92-time-gates)) |
| Processes without an entity | A process spawned into `*entity-pool*` belongs to the default level: set its `level` before `initialize-skeleton` | The Freedom HQ's gate |
| A model in a vanilla level | The art group's `.go` in the level's `.gd`, and its geometry baked into the level's `.fr3` by the decompiler (`extra_art_groups_by_dgo`) | `freehq` |
| Save header | `info-int32 4` of a save is unused; the save screen reads it back as `blind-data 4` of the slot's preview | [9.4](#94-saves) |
| Custom level names | At most 10 characters (level builder assert) | `hj2-forta`, `hj2-fortb`, `hj2-fexa`, `hj2-fexb` |
| Process init | `process-spawn` without `:init` calls `<type>-init-by-other` | The time gate (`:init hj2-time-gate-init`) |
| Level callbacks | A level-load-info's `callback-list` holds (slot . function) pairs: 33 login, 34 logout, 35 activate, 36 deactivate. They can be added at runtime to one of Jak 3's own levels | Mod levels; `freehq` |
| Art lookup | A process looks its art up only in its own level | Each level lists the art groups of the doors and scenes it holds |
| Level heap | 18 chunks: `large` 0-11 or 6-17, `medium` 0-8 or 9-17, `small-center` 6-11, `small-edge` 0-5 or 12-17. Jak 2's `load-buffer-mode` has the same four names | [6.2](#62-the-levels-and-their-memory) |
| Load and unload order | Each level started loading gets the next `load-order`; the level unloaded first is the one with the highest, the most recently loaded (`level.gc`). Unloading sets the symbol of each type the level defined to 0 and unlinks its particle groups | The hub first in every level list ([2.3](#23-design-decisions)) |
| Actor birth distance | In a level without visibility data (every custom level), an actor is born within its `vis-dist` lump, 10 km by default (`entity.gc`). Jak 2's `vis-dist` only mattered in such levels: in its own, the visibility data paused or culled what Jak didn't see, so a copied `vis-dist` means something else here | Doors don't copy it ([6.3](#63-doors-and-elevators)); city spawners and props keep Jak 2's (phase 20; capped at 150 m and 80 m in phases 15b to 19), which is also the props' draw range ([11](#11-memory-and-performance)) |
| Airlock range | `want-cross-airlock?` (`airlock.gc`) tests Jak's distance to the door on x and z only, and his height only when the door has a `height` lump; Jak 2's unseen doors were paused by its visibility data | `door_height`: a 20 m slice above and below each door ([6.3](#63-doors-and-elevators)) |
| Current level | Custom levels have no bsp nodes: the camera is inside every active one, and Jak's current level (`vis-nick`) stays the district he arrived in | `hj2-update-vis-nick` sets it in the city ([9.3](#93-respawn-points)) |
| PC renderer upload | `level-update` names a level to the PC renderer (`__pc-set-levels`) only once it is loaded, and the renderer then uploads its geometry over several frames: a level loaded late shows black for a while | `*pc-renderer-early-level?*` ([6.1](#61-how-jak-2-loads-its-levels)) |
| Water | Water is regions only (a `water` region tree) | [5.4](#54-water-and-ocean) |
| Fog | `fog-dists` z equal to w scales the perspective's w by zero: the whole 3D view goes black. No fog is z 255, w 254 | Interior moods |
| Weather | Jak 3's `play` turns the changing weather on; snow is drawn when the `snow` setting is above 0 | [8.3](#83-weather) |
| Elevator paths | Jak 3's elevator stops at every point of its path | Two-point paths for the mod's elevators |
| Rigid bodies | Jak 2's rigid-body methods 29, 53 and 56 are Jak 3's `apply-gravity!`, `get-lava-height` and `rigid-body-platform-method-59`; `init-skel-and-rigid-body` is `init-rbody-control!`, which must call `initialize-skeleton` | Dig lava platforms |
| Swing poles | `swingpole-init` takes an index in the parent's node list (a joint index + 1), and the pole follows that node | The trapeze's bar (node 11, the `trapeze_end` joint) |
| Pickups | Jak 3 inserted `eco-pill-light` and `lightjak` in `pickup-type` | Crates |
| Nav meshes | `entity-nav-mesh-by-aid` is a binary search over the bsp's nav meshes | Sorted by aid in the builder |
| Faction manager | Reads territories from the branches' `clock-type` and `break!`s on unknown level names | No faction manager, `guard.gc` check |
| Attack controller | `crimson-guard` needs `*cty-attack-controller*` allocated, not `#f` | havenj2's login callback |
| Scenes | `load-scene` registers a scene object as art of the level loading it; `scene-play` spawns a scene player; the actors' art is looked up in the level each actor names | Air train cutscenes |
| build-actor | Plays animations at 60 fps; its collide joint id is unused at runtime (the GOAL prim's transform index, joint + 1, picks the joint); its models have no mask table, so `setup-masks` changes nothing: a look Jak 2 switches with masks is a model of its own, or its primitives are left out | Palace gate frames, joint-bound collision, the speakers' looks, the prison's warp gate |
| Actors of a story state | Jak 2 births an actor when its `kill-mask` shares no bit with its level's `task-mask`, which the closed story nodes of the level's task area set (`level-method-22`); `never` is always set. Some actors decide by their own code instead (the Baron's statue, broken or not), and some are dead in the save once broken | The level port's `games/jak2.py` ([6.8](#68-the-end-of-the-game)), the props mesh |
| Slides | Jak 3's `slide-control` is Jak 2's (a `path` curve, `path-k` knots); like Jak 2, Jak 3 keeps it and Jak's `tube` states (`target-tube.o`) and animations (`jak-tube+0-ag`) out of GAME, in the DGOs of the levels with slides (`PRECC`, `VOCA`) | The fortress exit's slide: `hj2-fexb` carries both |
| Curve paths | A `curve-control` without `path-k` knots becomes a straight `path-control` | Jak 2's two-point lift paths |
| Actor scale | Jak 2 ignores the actor scale lump | Props |
| Traffic graph unlink | `level-unlink` on a city-level-info nav graph that `level-link` never patched overwrites the indices it still holds, and corrupts it | `havenj2-traffic-start` ([7.1](#71-navigation-data)) |
| Process heap of an actor | An entity's process gets 16 KB unless its type's cached `entity-info` (method slot 13) says otherwise | The palace cable's electric fans (24 KB) |
| Lightning engine | `*lightning-engine*` has 64 connections (Jak 2's 128); a lightning that finds it full isn't drawn | The palace cable's fans take 54 |
| Water regions | They send `water` only to a `water-anim`: a hazard pool needs its own check | The dark eco pool ([6.12](#612-hazards-and-decor-of-the-places)) |
| `defmacro` in `goalc` | A macro exists in a session only once its file is compiled; `(mi)` skips up-to-date files | `hj2-common-obs.gc`'s macros |

## 11. Memory and performance

DGO sizes after phase 15's build (`out/jak3/iso`; phase 14's in brackets):

| DGO | Size |
|---|---|
| HJ2, the hub (bsp, traffic code and art, the code of the districts' actors; the navigation is now the districts') | 8.4 MB (9.4 MB) |
| A district (HSA...) | 0.9 MB (`hj2-gena`) to 3.0 MB (`hj2-port`, with the barges) (0.8 to 2.8 MB) |
| A place | 23 KB (`hj2-kiosk`) to 5.4 MB (`hj2-atoll`) (39 KB to 5.3 MB) |

The whole city merged into one level (phase 13), for comparison:

| Item | Size |
|---|---|
| `havenj2` bsp (collision and navigation data included) | 15.2 MB in the level heap |
| HJ2 DGO (bsp, traffic code and art included) | 19.6 MB |
| `havenj2.fr3` uncompressed | 285 MB |
| TIE after unpack | 21.6 M vertices, about 660 MB of GPU vertex data |
| Collision | 502 k triangles |

That was roughly five times what Jak 2 keeps loaded in the city at once. Since phase 14 the city
loads like Jak 2's, the hub and two districts at a time; its frame rate isn't measured yet.

**Spawn distance.** Jak 2 births its actors through its levels' visibility data, which the mod's
levels don't have: they are born within their `vis-dist` lump (Jak 2 reads it only without
visibility data, `entity.gc`). The level port copies Jak 2's. A prop whose last lod is 999999 m
(the market's and farm's) is also drawn only within it (`setup-lods!`, the same in both games): 140 m
for the market's, as in Jak 2. The part spawners' are up to 384 m (the districts' signs), 600 m
(the port's signs) and 950 m (its chimneys).

Phase 15b capped them (the districts' part spawners at 150 m, the market and farm props at 80 m):
the signs and the bazaar's baskets vanished well before Jak 2's, and phase 20 removed both caps.
The knobs stay, for a lag measured in the city: `props.max_vis_dist` (meters, `capped_vis_dist`
in `steps/props.py`) and `particles.max_vis_dist` (`[meters, [source levels kept as they are]]`,
`vis_dist` in `steps/particles.py`); a cap is a minimum with Jak 2's value.

How to measure the lag: [14](#14-not-done-yet).

**The level heaps must end below `#x10000000` (256 MB).** A texture keeps the shaders that use it
in a linked list whose links (`shader-ptr`) hold 24 bits of (address / 16): a shader past 256 MB is
linked to its address minus 256 MB. Unloading a level walks every list to splice out that level's
shaders (`unlink-shaders-in-heap`), and writes through those wrong links. `master-dev` raised Jak
3's `DEBUG_LEVEL_HEAP_MULT` to 15.0 (commit `334dcd5c0`), which ends the level heaps at
`#x12935000`: a level loaded in the top chunks could have shaders past 256 MB. This branch uses
10.0 (level heaps about 180 MB, ending near `#xCF63000`), and `init-level-system` prints an error
if they end past `#x10000000`. Jak 2's is 12.0 on `master-dev` (about 215 MB): close to the limit.

## 12. Debugging

- **Validate a `.fr3` offline:** `out/build/Release/bin/fr3_check.exe out/jak3/fr3/<level>.fr3`
  ([4.3](#43-fr3_check)).
- **Texture pool slots:** `fr3_check <level>.fr3 --textures ""` lists every texture with its page
  and index (`combo 0xPPPPIIII`) and whether it takes a pool slot (`pool true`). Its slot is the sum
  of the sizes of the pages before it in `jak3_tpage_dir.cpp`, plus its index. Two levels loaded
  together must not put different textures in one slot: the particles would show the other's.
- **Rebuild one level without the REPL:**
  `out/build/Release/bin/build_level.exe -g jak3 <level>.jsonc <output .go> --fr3`. The log prints
  every region's scripts.
- **Check a change of the level port:** the generated files aren't in git. Copy them aside (the
  `.gitignore` block lists them), run the level port, and compare: a change that only reorganizes
  the code leaves them as they were.
- **Game log:** `log/jak3.<date>.log` records level loads and the levels Jak enters.
- **Silent crashes:** when the game is launched through `task`, a crash leaves no Windows error
  report and `task` prints only the low byte of the exit code: `exit status 5` is `0xC0000005`
  (access violation), `exit status 9` is `0xC0000409` (`abort`). The crash report
  ([4.4](#44-crash-report-gk)) is in `log/jak3-crash.txt`.
- **`(mi)` crashes after many levels:** each level with `art_groups` loads Jak 3's 274 DGOs again.
  After about ten in one run `goalc` can die (segmentation fault) with a level's `.go` written but
  not its `.fr3`: touch that level's `.jsonc` and run `(mi)` again.
- **Do not use `bg` from inside Jak 3's city:** with phase 13's `large` havenj2, it allocated the
  `large` bank while `ctywide`,
  `citycast` and `ctyport` are still loaded and hits `could not find free large bank` followed by a
  `break!`.
- **Find where the game crashes:** read the crash report, `log/jak3-crash.txt`
  ([4.4](#44-crash-report-gk)). For more (the disassembly, with symbol names), start the game
  (`task boot-game`), then `task repl`, `(lt)` and `(dbgc)` (attach the debugger and continue). After the crash, `(:di "log/crash.txt")` prints the
  registers and the stack. Without debug info (code not compiled in that `goalc` session) the stack
  is raw: the values equal to the EE base plus an offset are return addresses. `rip` equal to `r15`
  (the EE base) is a call through a null function pointer, often a method called on `#f`.
  `(:disasm <address> <size>)`, while the game is still halted, names the object and the offset of
  an address and disassembles it with symbol names.

## 13. Change history

Phase 1 is commit `de9ec6962`; phases 2 to 10 are commit `dd14a7829`; phase 11 is commit
`e769d5e2a`; phase 12 is commit `051725569`; phase 13 is commit `a1daec395`; phases 14, 15 and
15b are commit `a4f797fc4`; phase 16 is commit `9a8dd7043`; phases 17 to 19 are the commits that add their
rows. Phases 1 to
10 were played in game before the next one started; phase 11 was partly (the time gates both ways,
the new places through the Mods menu); phase 12 was partly: the Freedom HQ sequence that crashed
(Jak 3's city, the HQ's elevator, its time gate to the hideout) works. The rest of phase 12 is built
(`(mi)`, `fr3_check` and the lints clean) but not played yet. Phase 13 changes no level: its files
were checked against phase 12's, and `(mi)` builds them. Phase 14 was played once: the district
loading holes and the traffic over the void found then are fixed in phase 15. Phase 15 was played
once (the user's second test): what it found is fixed in phase 15b, which is built (`(mi)` clean,
`fr3_check` finds 0 errors on every level) but not played yet. Phase 16 is built (`(mi)` clean,
the audio copied and packed) but not played yet.

| Phase | Asked | Done | Problems found: cause, fix |
|---|---|---|---|
| 1 | The whole city, walkable | `import_fr3`, `fr3_check`, Mods menu warp | Collide hash over 65535 items: `collision_bounds`, adaptive grid. Triangles lost far from the origin: local tests. First-frame crash: an empty TIE tree. Imported trees culled: all-visible list. `bg` from Jak 3's city fails: warp through a continue |
| 2 | Grey sky, no water | Jak 2's weather ranges, `sky` flag, ocean map, water regions, shrubs | Black 3D view: fog z equal to w. Jak fell through the water: the ocean region needs a placeholder argument |
| 3 | Interiors and the places around the city | Door scripts (`pair` and `string` lumps), `gen_havenj2_links.py`, the first places, respawn process | Door art missing: art groups listed per level |
| 4 | Follow Jak 2's loading exactly | Region scripts and translator, one level per place, memory modes, palace gate model, props mesh, time of day | Grey, flat light: frozen noon, now 16:00 |
| 5 | Props, speakers, particles, weather, cameras | Props as Jak 3 actors, propaganda speakers, particles and neon signs, weather menu, fixed cameras, story prototypes, pumping station, mountain, Haven Forest | Huge props: Jak 2 ignores the scale lump. Link error: a type's parent must be linked first in GAME |
| 6 | Doors, elevators, platforms, squares; prepare traffic | Jak 2's elevator model, platforms with convex hull collision, crates, prop particles, navigation data export and `nav_data` | Square particles: the sprite page was dropped on deactivation |
| 7 | City traffic | Jak 3's traffic code and art in HJ2, traffic callbacks, Mods menu switch | Faction manager `break!`: removed, `guard.gc` check. Nav mesh binary search: sorted by aid |
| 8 | Traffic crash, palace door | Attack controller, never-spawned actors filtered | First guard called a method on `#f`: allocate the attack controller. The palace door that "never opens" doesn't exist in Jak 2 (`kill-mask` never) |
| 9 | More traffic without blinking; the dig site; the port's air train | Jak 2's densities, 50 m cells with whole-cell spheres, castle pad and dig with their platforms, `hj2-air-train` | Traffic blinking: small spheres and empty cells made cells leave the active set |
| 10 | Weather everywhere, particle fixes, air train cutscenes, a time gate, warps | Weather driver and 8 weathers, texture id and flag remaps, 4 cutscenes, time gate, district and key place warps, `write_if_changed` | Squares: Jak 2's `effects` id is Jak 3's font page. Fountains: flag bits moved. Weather menu dead after a Jak 3 level: the weather was released to Jak 3's boot sky and nothing restored the choice, now held every frame |
| 11 | Palace respawns and elevator death; air train as a teleport; real teleporters between the Freedom HQ and the hideout; Jak 2's respawn points; construction site models; speakers breaking like Jak 2's; Dead Town's water, bars, slabs and hut; Haven Forest; the fortress and the stadium; no garage doors; farm crops; saves | Respawn by the level Jak is in, Jak 2's continue flags; air train fade; two `hj2-time-gate`s and their arrival points; silo doors and bomb elevator; two-hit speakers with three looks; ocean maps of Dead Town and the mountain, Dead Town's platforms, beams, flag, swing poles, Sage's hut; particles of the forest and Dead Town; animated texture slots mapped; ocean order; fortress gates, fortress and stadium levels; `hj2-farm-*`; save mark and slot label | Elevator death: the roof's door ran `on-deactivate` at load and turned the pillar off, script removed. Fortress gate shut: a branch of another story state named an unported level, `strict_notice`. Level names over 10 characters: renamed. Place sprite pages sharing texture pool slots with the city's: ids 1594 and 1627 |
| 12 | The crash of the Freedom HQ's time gate after walking in from Jak 3's city; Dead Town as one level with its hut; Jak 2's load mode for every level; every Jak 2 door to a level working; each level's elements in their most advanced state (the end of Jak 2); the prison | The hut merged into Dead Town (`merge`); Jak 2's memory modes placed exactly in Jak 3's heap (`memory_modes`); the end of the game everywhere: actors from Jak 2's story task masks (`jak2_actors.py`), background prototypes, the palace plaza's broken statue and wall; the fortress's escape (prison, way out, their gates); crates, swinging bars and slides in every place; a crash report in `gk` ([4.4](#44-crash-report-gk)) | The hut missing near the city: it was a level of its own, loaded deeper in. Jak 2's Dead Town has no slabs, floating platforms, bridge or flag at the end: their ports removed. A merged level shown and hidden by the other's scripts: dropped (the translator's `source`). A `water-vol` without `water-height`: the top of its box. The Freedom HQ crash (only after its elevator, the HQ then in the top chunks): the HQ's borrowed `lfreeout` sat past 256 MB, its shaders were linked to wrong addresses, and unloading `freecast` wrote into GAME's code (`nav-mesh` `init-from-entity`), run at `havenj2`'s login. Found with the crash report and a write watch on that code: `DEBUG_LEVEL_HEAP_MULT` 10.0 keeps the level heaps below 256 MB ([11](#11-memory-and-performance)) |
| 13 | Generic, reusable tools instead of the scripts of the havenj2 folder (Jak 2 → Jak 3 now, Jak 1 → Jak 3 and other directions later), with as little mod-specific code as possible; the level editor's submodule removed | The level port (`scripts/level_port`: games, game pairs, steps) and this mod's manifest (`custom_assets/jak3/ports/jak2-haven-city`); the levels' build steps generated (`jak2-haven-city.gp`, loaded by `game.gp`); the submodule link removed on branch `tools/open-goal-level-editor` | Every generated file compared with phase 12's: the same data, but for the order of two models in `hj2-dig`'s DGO, the order of lump keys in `hj2-forest` and `hj2-ruins` (the level builder sorts them) and the name of the palace gate's collision mesh (build-actor only prints it). One file had Windows line ends, now the same as the others |
| 14 | The city split like Jak 2's (the low-res city seen from the palace lobby); Jak 2's Hellcats in the traffic | The hub `havenj2` (Jak 2's `ctywide`, `small-center`, `not-physical`) and 15 district levels from the template `city-district` (`small-edge`, `display-wait`), Jak 2's load sets ([5](#5-the-city-levels), [6.2](#62-the-levels-and-their-memory)); the level port's `level_templates`, `hub`, `level_flags`, `nav.sources`, `particles.levels`, `hubs_var`, the hub first in every level list (`with_hubs`), Jak 2's district display scripts kept, the hub's `.jsonc` generated in full (the `section` mode and the `shown` key removed), the water step folded into `levels`, `part-engine-max` per level; districts drawing with the hub's sprite page, released at the hub's logout; respawn by hub group (`hj2-hub-of`); the Hellcats ([7.3](#73-hellcats)) | The low-res city in the palace lobby: the pillar-top airlocks, born 420 m below with the default 10 km `vis-dist`, opened and showed `hj2-pcab` and `hj2-proof`; doors copy Jak 2's `vis-dist`. A district's actors need the hub's code: the hub loads first and unloads last, and stays loaded with Dead Town and the mountain (Jak 2 drops `ctywide` there). Jak 2's airlocks hide the hub while a district stays shown: the hub's sprite page is kept until it unloads. The Freedom League squad rewrites the `guard-car` target count every frame from its alert settings, which give the Hellcats none: its guard type 5 is held at 3 |
| 15 | After the first phase-14 test: districts never shown, traffic floating over the void, Hellcats chasing Jak. Every level complete like Jak 2's, with the same levels loaded: every hazard that hurts Jak, no enemies, the palace's inside as the low-res throne seen from the roof, the small places (kiosk, Onin's tent, the canyon), no orbs, the garage doors still removed | `hj2-swap-in-district` ([6.1](#61-how-jak-2-loads-its-levels)); each district's own navigation (nav step `write_district`), the hub only the height map ([7.1](#71-navigation-data)); the Hellcats' pursuit removed ([7.3](#73-hellcats)); particles in 20 more places and the garage, `"auto"` pages and ids (`Allocator`), `skip_groups`, `defbehavior` callbacks copied ([5.3](#53-particles-and-sprite-textures)); static decor in meshes, `hj2-common-obs.gc`, the palace cable's hazards, the city's actors (parking spots, force-field walls, searchlights, guard turrets, barges), the places' end states, hazards and decor ([5.6](#56-city-actors), [6.12](#612-hazards-and-decor-of-the-places)); the mountain's iris doors open on `hj2-mincan`, and `hj2-kiosk`, `hj2-onin` ([6.13](#613-small-places)); the level port's lump kinds `string`, `symbol`, `type`, a ported actor's `art_groups` in its DGO, `ported_actors`, `region_script_overrides` for regions 429, 894, 177, 353 and 873; Jak 2's `GGA.DGO` and `ATE.DGO` extracted again with `rip_levels` | Districts never shown: some of Jak 2's loading faces can be walked around, and showing a level that isn't wanted is lost: the district asked is swapped in for a hidden one. The void traffic: the hub's merged navigation spawned it over districts not loaded; each district keeps Jak 2's own, and the engine links the 2 displayed ones. A crash going down the palace pillar (`h-bike-c`, `nav-branch` method 15): the traffic start unlinked a graph never linked, which corrupted it; only patched graphs are unlinked. Classes placed by levels loaded together (the windmills of the mountain and the cable, the flip steps of the cable and the roof) can't be linked by both: they moved to GAME |
| 21 | Installable from the launcher with nothing else to do: the Jak 2 content made on the player's machine, from the launcher-installed Jak 2, during the install | The extractor's `run_level_ports` before the compile ([4.6](#46-launcher-install)), error codes 4060 and 4061; `level_port` options `--root`, `--iso`, `--extractor`, `--fr3-check` (dev defaults unchanged); the release builds `level_port` (PyInstaller) and `fr3_check` when a port manifest exists | The rip folders and source levels left out `textures_from` and `backdrop_levels` (`sewer`, `palout`): the extract step reads every level the manifest names whose DGO is on the disc. PyInstaller missed the manifest's dynamic imports: `PYTHONPATH=scripts` at build time. Checked on a fake launcher install (Windows): 300 of 306 generated files identical to the dev ones; the others differ by the dev checkout's untracked Jak 2 texture replacements, an older camera dump, and the build file's absolute sound paths |
| 20 | The Freedom HQ's time gate lost its base (its halo and jump still worked); level loading "still too slow at times", Jak 2's city sector loading imperatively respected; during the alert some sounds disappeared at times (turret shots, the guards' tazer and rifles, the vehicles' shots); the palace plaza as at the start of the game, without access to Mar's tomb; the draw range of the level elements too short (signs, the bazaar's baskets); the street poles near the stadium destructible like in Jak 2; the halo of the Baron's propaganda speakers blue; then the Baron's intact statue gone from the plaza; then the prison never reached from the fortress ("the door opens but another overlapping door stays closed"); then on the way out of the fortress, the plates Jak breaks with a dive attack missing, and Jak's slide down the ramp near the end missing; a smaller Mods menu (the mod's switch, then the warp to Jak 2's city, the warps by district, the warps outside, the weather), the guard vehicles and Jak 2's alert always on, no warp to the way out of the fortress, its trap doors whole again each time it loads; then "still many levels loading at the last moment" and, by the stadium, a level never loaded (Jak on a vehicle over the void, `log/jak3.2026-10-07T13-14-52.log`); then still districts showing late (one loaded but shown only once Jak stood on it; the slums from the industrial section loaded only once Jak was on them); then the palace plaza still loading under Jak, walking from the port; the guards' grenade launchers gone (wanted above the tazers' alert level); then levels overlapping and the stadium and the slums swapped back and forth; then "some object sounds are missing in the levels; every level must have all of its sounds, completely" | The level port's `extract` step extracts again any Jak 3 DGO whose `.fr3` lacks a model of `extra_art_groups_by_dgo` (`missing_baked_models`, `fr3_check --models`); its decompiler run with an absolute path ([9.2](#92-time-gates), [4.3](#43-fr3_check)); the loading of the city measured against Jak 2's (on PC: the same load-state logic, the renderer's `Loader` shared by every game) and Jak 2's scripts made the only ones to load and show the districts: phase 19's preload and showing ahead removed, the PC renderer loading the geometry of the districts near Jak ahead of the game (`*pc-renderer-prefetch*`, a vanilla `level.gc` edit, `hj2-renderer-prefetch`) ([6.1](#61-how-jak-2-loads-its-levels)); the guards' bank `cityffh` wanted with whichever Jak 2 banks are wanted (`hj2-update-extra-sound-bank`), two overlord bank record fixes (`sbank.cpp`) ([8.4](#84-sound-and-music), [4.5](#45-sound)); the level port's `story.level_open_tasks` (story nodes open for one source level: its actors, background prototypes and scripts), Jak 2's prototype conditions (`STORY_PROTOTYPES`) and the actors hidden by their own code (`ACTOR_SHOWN_AFTER`) in `games/jak2.py`: the plaza before Mar's tomb is found ([6.8](#68-the-end-of-the-game)); the props' and part spawners' `max_vis_dist` caps removed from the manifest: Jak 2's `vis-dist` everywhere ([11](#11-memory-and-performance)); the street lamps (`ctyn-lamp`, 42 in `hj2-gena`, 42 in `hj2-genc`) left the district meshes for an actor, `hj2-ctyn-lamp` (`havenj2-obs.gc`, [5.6](#56-city-actors)): Jak 2's pole and 4-piece explode model rebuilt by `build-actor`, snapped by any attack or vehicle; the speakers' halo and projector flare blue through the particle step's new `part_specs` (init-spec values replaced per source part, [5.5](#55-palace-gate-propaganda-speakers-neon-signs)); the intact statue: `ctywide` added to `level_open_tasks`, the actors killed by their own code once a story node is closed (`ACTOR_GONE_AFTER`: `baron-statue`) and `baron-statue` baked into `havenj2`'s mesh ([6.8](#68-the-end-of-the-game)); the doors of this mod's levels wait, shut, for the PC renderer to have the levels they show before they open (a wrapper of `com-airlock`'s `destination-loaded?`, `hj2-renderer-pending?`), so a door's level is shown as it opens ([6.1](#61-how-jak-2-loads-its-levels), [6.11](#611-the-prison-and-the-way-out-of-the-fortress)); the way out's trap doors (`hj2-fort-trap-door`, `hj2-fexb-obs.gc`: Jak 2's `fort-trap-door` on Jak 3's `fac-break-floor` pattern, its model and explode model rebuilt) and Jak's slide (`target-tube.o` in `hj2-fexb`'s `code`, `jak-tube+0-ag` in `art_groups` for `slide-control`) ([6.11](#611-the-prison-and-the-way-out-of-the-fortress)); the Mods menu rewritten ([9.1](#91-mods-menu)): `*mod-jak2-haven-city-enabled*` (off by default) gates the Freedom HQ's time gate and the weather, the other entries greyed out while it is off; Hellcats and guard bikes on by default, the traffic, Hellcats, guard bikes and alert entries removed (always on); the hideout as the city warp; `hj2-fort-trap-door` no longer calls `cleanup-for-death` (hidden and asleep until `hj2-fexb` unloads); the district map built from each district's collision ground (`fr3_check --squares`, the levels step's `ground_squares`), the traffic cells only where no district has ground; the district guard loading the district Jak will be over in 1.5 s hidden, at most every 3 s; the log printing the scripts' level lists and display requests and the guard's state, with where Jak is ([6.1](#61-how-jak-2-loads-its-levels), [4.3](#43-fr3_check)); the district guard shows a loaded hidden district under Jak or 1 s ahead at once (`hj2-show-if-loaded`) and loads the district 1 s or 2.5 s ahead in place of any district but the one under Jak (`hj2-load-ahead`) ([6.1](#61-how-jak-2-loads-its-levels)); the guard also loads the nearest district whose ground is within 50 m (`hj2-near-district`); grenadiers at alert levels 2 to 4 (1, 2, 2) in `*hj2-alert-level-settings*` ([7.2](#72-traffic)); the look-ahead capped at 60 m, districts shown or recently asked for within 100 m never swapped out, a loaded district shown early only within 25 m (`hj2-district-within?`); the level port's sound check (`steps/sound_check.py`, the `sound` step): the part spawners' `effect-name` lumps and the particles' `:sound` kept, the Jak 2 banks each level's content needs besides its wanted ones (`*hj2-level-sound-banks*`) loaded in the free half bank slots by `hj2-update-extra-sound-bank`, the castle pad elevator's own sounds, the added continues given the banks of their nearest continue ([8.4](#84-sound-and-music)) | `freehq.fr3` (2026-10-04 22:05, with every other Jak 3 `.fr3`) came from a Jak 3 extraction made with a config without `extra_art_groups_by_dgo` (master-dev's or another Jak 3 mod's: `out/jak3` is shared by every worktree): its merc models had no `warp-gate-lod0`, while `warp-gate-ag.go` was still in FREEHQ.DGO, so `hj2-level-has-art?` let the gate spawn with no geometry to draw. FREEHQ.DGO extracted again: `warp-gate-lod0` is back. The step's `subprocess.run` of the decompiler by a relative path failed on Windows (`FileNotFoundError`); slow loading: the game loads a district in 0.05 to 0.3 s, the renderer its `.fr3` in 1.5 to 2.5 s (as in Jak 2, where the faces load seconds ahead), and the phase 19 preload fought Jak 2's scripts: `hj2-marka` and `hj2-port` swapped back and forth, `hj2-gena` and `hj2-genb` (loaded by Jak 2's faces 294 and 130) evicted, then loaded back by the guard; the showing ahead showed a market Jak 2 had just hidden. The hub's `.fr3` is 15.5 MB (1342 textures) against `ctywide`'s 2.4 MB: entering the city waits about 2 s for it; missing alert sounds: all are `guard-shot-fire` or `guard-zap`, in `cityffh`, `CTYWIDE3` and `CTYFARM1` only; `cityffh` was wanted only with `j2ctywi3`, and the overlord skipped reloading a bank it had unloaded (`LookupBank` ignored `in_use`) and failed half banks whose partner wasn't in its first record pair (a decompiled loop whose index never moved): `CITYFFH.SBK` read once in a session that loaded it four times, `j2ctywi3` never read again after the Freedom HQ; the plaza: Jak 2's `level-method-22` shows the wall under the Baron's statue and hides its rubble until `canyon-insert-items-shard` is closed, the broken statue (`no-draw`) and broken wall (left at the origin) wait for `canyon-insert-items-resolution` in their own code (`ctypal-obs.gc`), as does the tomb airlock's `on-notice`; the draw range: Jak 2 draws the market props up to their `vis-dist` lump (140 m: `setup-lods!` takes it for a 999999 m last lod, Jak 3's too) and births actors by its visibility data alone (the lump only counts without it), its signs are part spawners with a 384 m `vis-dist` (600 m in the port); phase 15b's caps (80 m props, 150 m spawners) made them vanish early; lamps not breaking: they were baked into the mesh as a `post` collision. Jak 3's vehicles never send `attack` to what they touch (their `touch-handler` does nothing), only `impact-impulse` from `rigid-body.gc`: the lamp handles both. The halo is particles (parts 819 and 822), not a texture; the intact statue is not the plaza's: it is `ctywide`'s `baron-statue` actor (250 m high, killed by `init-from-entity!` once `canyon-insert-items-resolution` is closed, `ctywide-obs.gc`), never ported since the port was at the end of the game; hiding the end's broken statue left the wall empty; the prison: `fort-entry-gate-11` (in `hj2-fortb`) and `fort-entry-gate-20` (in `hj2-prison`) stand back to back 2 m apart, and each opens toward Jak's back only once the other has set its `subtask-complete` (`next-actor`, Jak 3's `want-cross-airlock?` as Jak 2's). Gate 11 waits for the prison to be loaded, then shows it and opens; phase 19's `hj2-display-wait?` kept the prison hidden until the renderer had its 7.3 MB `.fr3`, up to 6 s (gate 9 loads the prison about when Jak reaches gate 11), and Jak 3's open state shuts a door whose level isn't shown, so gate 11 opened and shut in turn while gate 20 didn't exist yet. Jak walked through gate 11; when the prison appeared, gate 11 (Jak behind it) waited for gate 20 and closed, gate 20 (Jak behind it) waited for gate 11: both shut for good. It worked on 2026-10-06, before phase 19 (`log/jak3.2026-10-06T11-43-21.log`: `hj2-fortb`, then `hj2-prison`, then `hj2-fexa` walked through); the trap doors were left out on purpose (Jak 2 marks them dead once the escape breaks them); the slide: `slide-control` is defined by `target-tube.o`, which Jak 3 links only into `PRECC` and `VOCA` (Jak 2: `FEB`), not GAME, so `hj2-fexb`'s slide entity had no class and was never born, and Jak's tube animations (`jak-tube+0-ag`) were missing too ; the user's layout; the stadium: the only faces loading and showing `hj2-stdm` are `hj2-genb`'s 1130 and 1131, which run only while `hj2-genb` is shown, and `hj2-genb` is shown only by the camera face 1117 of `hj2-gena` (a street 300 m from the stadium). Jak came from the main town's north side (the log: `hj2-gena` shown, `hj2-genb` loaded hidden, the renderer loading `hj2-stdm` ahead), where the stadium's ground runs 250 m west of its streets (rows of squares the traffic cells gave `hj2-gena`): the guard saw Jak over a shown `hj2-gena` and did nothing. On the ground map those squares are `hj2-stdm`'s, and all 48 city continues still fall in their own district. Jak 2's city regions are all ported (the 4 missing load unported places) and run as in Jak 2 (the same `region-execute`, the target and camera positions); the late districts of the log are display faces reached by a street without a loading face (`hj2-farma` by `hj2-marka`'s face 1477 without crossing 1485), which the new log lines will place ; the guard waited 0.3 s on a loaded district, and loaded ahead only in place of a hidden district no script had asked for in the last 5 s (from the industrial section, both sections were wanted and recent) ; walking is too slow for the 2.5 s look-ahead; Jak 2's alert table has no grenadier at any level (Jak 3's sends 1 at rest) ; flying, the 2.5 s look-ahead reached the slums from the stadium's gate and evicted the shown stadium, which Jak 2's face then loaded back ; missing object sounds: the port dropped the part spawners' ambient sounds (380 spawners in 15 levels) and the particles' sounds; 23 sounds were in no want set of their level and 80 only in some (Jak 2 wants a bank only near its objects: the castle pad's airlock, the gun buoy, the fortress gates); `hj2-cpad-elevator` called `hj2-elevator`'s `init-sound!`, playing the palace elevator's sounds; two added continues wanted no bank |
| 19 | Jak 2's alert system in full; districts loading late ("in many places I must step onto the void for the level to load"): Jak 2's loading exactly; voice lines "sometimes a bit loud or repeat in a loop"; the stadium "has the same bug: I must be inside the level, visually bugged, for it to load correctly" | `ff-squad-control-method-45` replaced in havenj2's DGO: Jak as the squad's primary target, Jak 2's five alert levels and `update-alert-state` (Breath of Peace's port), Jak 2's alert music mode and alarm, the guards hunting, Dark Jak raising the alert; the Hellcats' and guard bikes' pursuit (`hj2-guard-vehicle-*`); their counts from the alert table ([7.2](#72-traffic), [7.3](#73-hellcats)); districts loaded ahead from the generated `*havenj2-district-preload*` (the manifest's `preload`), the swap-in and the guard never evicting a district a script asked for less than 5 s ago, no district shown before the PC renderer has its geometry (`*pc-renderer-display-wait?*`, `__pc-level-ready?` in `gk`) ([6.1](#61-how-jak-2-loads-its-levels)); the minimap with Jak 2's maps (`source_textures`, `city_map_bits`, `hj2-minimap-page-on`, a one-line edit in `minimap.gc`), the guards' icons dropped when they go back to the traffic's pool, the Hellcats and guard bikes with the guards' blue icon and view cone, 1.4 times larger (`*hj2-guard-vehicle-minimap-class*`, `draw-frustum-2` following the class scale), the cones kept while Jak pilots in havenj2 ([7.4](#74-minimap)); `pack-vags` ends each Jak 2 line with Jak 3's end frames (`add_vag_end_frames`) ([8.4](#84-sound-and-music)); the stadium fix: districts loaded ahead shown when Jak comes within 50 m (`hj2-show-near-districts`), the preload no longer blocked by the district Jak left, at most one preload per 5 s, places loaded with the city swapped in at display time, the race track made Jak's level by region 1317 (`region_script_overrides`, `hj2-in-place?`), Jak waiting for the renderer in it, the renderer wait printed every second ([6.1](#61-how-jak-2-loads-its-levels)) | The alert never rose in havenj2: only Jak 3's `ctywide` sets the squad's primary target (`*city-mode*` `'ctywide`), and `squad-control-method-18` ignores any other offender. Jak 3's guards ignore `'alert-begin`: `'member-attacked` instead. Jak 3's traffic manager `break!`s on `'increase-alert-level`: Dark Jak goes through `squad-control-method-18`. Late districts: Jak's route missed Jak 2's one-way loading faces, so the district loaded only when asked to be shown; the swap-in evicted hidden districts Jak 2's scripts had just loaded; the renderer's `.fr3` upload came after the load, with the collision already live. No minimap in havenj2: Jak 3 draws it only with a level named `ctywide` active, and no havenj2 level had `city-map-bits` or a minimap page. The guard vehicles' icons looked like the guards' (`draw-frustum-2` ignores the class scale) and no cone showed while Jak piloted (`frustum-alpha` 0 while piloting). Jak 2's voice lines have no ADPCM end flag: the voice ran past the line's end and looped the previous 8 KB chunk when the overlord's end check missed it; their position and loudness already matched Jak 3's lines. The stadium: on the main town's squares towards it the preload pair is `hj2-gena`/`hj2-stdm` and `hj2-gena`, left wanted hidden, blocked the preload, so the grounds loaded at Jak 2's face 1130 only 4 s before being shown; districts loaded ahead stayed hidden until Jak stood on them (`hj2-genb` loaded 12 s before being shown); the race track's tunnels lie on the main town's squares and Jak's level stayed `hj2-stdm` there, so the guard loaded `hj2-gena` over the track |
| 18 | After the user's fourth test: sounds missing in places (the gardens' sprinklers), the mountain's platform vanishing on arrival in Haven Forest, the dig not reached from the pumping station, the gardens loading late from the port, the gun buoy's shots through walls and the buoy indestructible; Jak 2's guard lines and alert (turrets firing at Jak in a vehicle); Jak 2's guard bikes with Freedom League pilots; the README to say Jak 2 is needed | `hj2-update-level-sounds` ([8.4](#84-sound-and-music)); the actors' kill-mask bit `special` kept (`placed`, [6.4](#64-pumping-station-mountain-and-haven-forest)); `hj2-atoll`'s collision box down to the castle pad's walkway; region 489 override, `hj2-swap-in-district` with an empty slot, the district map weighted by overlap and grown 3 rings ([6.1](#61-how-jak-2-loads-its-levels)); the gun buoy's shots stopped by the background, its 12 hit points ([6.12](#612-hazards-and-decor-of-the-places)); the guards' Jak 2 lines and Jak 2's alert ([7.2](#72-traffic)); the guard bikes ([7.3](#73-hellcats)); the README's Requirements | The platform: Jak 2 marks it alone with the kill-mask bit `special`, the only actors a `'special` backdrop keeps alive; the port dropped every kill-mask. The dig: the pumping station's `collision_bounds` cut the walkway to the castle pad (Jak fell through before the face showing the pad). The gardens: Jak 2's loading face can be walked around, the swap found no hidden district, and the map gave the port 50 m of the gardens' ground. The sprinklers: their bank's border was crossed before the gardens loaded |
| 17 | Nothing of Jak 2 or Jak 3 in the repository: the files made from them fetched and placed on each machine | The level port's `extract` step (the extractions checked, the decompiler run for what is missing: all of Jak 2 with its rips the first time, then only the DGOs missing), `task level-port`, the manifest's `ignore_outputs` (a full run lists its 301 outputs in a `.gitignore` block, removed from git), `game.gp` stopping with a message when they aren't generated ([3](#3-rebuilding-it-step-by-step)) | A run on the existing extractions extracts nothing and rewrites no file: the outputs are the committed ones of phase 16 |
| 16 | Jak 2's sound in full: music, ambiences, object sounds, speeches and citizens' lines | The level port's `sound` step ([8.4](#84-sound-and-music)): `want-sound` and `sound-play-loop` kept, banks and music renamed `j2*`, the levels' `:music-bank`, the hub's `:extra-sound-bank` (Jak 3's traffic banks), the copy and `pack-vags` build steps; Jak 3's overlord plays MIDI music, skips missing banks and reads a mod VAG directory, `goalc`'s `pack-vags`, GOOS `file-exists?` ([4.5](#45-sound)); Jak 2's banks as half banks, the music flava, the speakers' speeches, the citizens' lines; Jak 2's object sounds in 35 `hj2-*` classes: the palace gate, hideout doors, fortress gates and elevators, the guard turrets, the atoll's pistons, turbines, pipes, sliders and gun buoy, the dig's platforms, balloon and stomp blocks, the fortress's lift, turrets and laser belt, the mountain's platforms, eco pool and avalanche, the palace cable's nuts, fans, rotating gun and turrets, the ruins' beams | Jak 2's voice lines start with a little-endian `pGAV` header (Jak 3's with `VAGp`): `pack-vags` reads both. Jak 2's names collide with Jak 3's (28 banks, the `CITY1` music, the `propa` speeches Jak 3's code still plays): every file renamed. A build step's `:dep` must be another step's output: the build file is `pack-vags`' third input instead |
| 15b | After the user's second test: death riding up the palace pillar, the mountain missing from Haven Forest, black props in the Hip Hog and Onin's tent, a crash entering the Hip Hog, the void from the port to the palace, black areas and lag while districts load, respawn points like Jak 2's, the tanker crash place removed, living yakows, Jak 2's original doors. Jak 2's music and sounds researched, pending a decision ([14](#14-not-done-yet)) | Doors' height slice (`door_height`, `base_lumps`) and no `vis-dist` copied ([6.3](#63-doors-and-elevators)); `'special` kept ([6.1](#61-how-jak-2-loads-its-levels), [6.4](#64-pumping-station-mountain-and-haven-forest)); `"sun": null` mesh palettes, `update-mood-hj2-onin` ([6.12](#612-hazards-and-decor-of-the-places), [8.1](#81-moods)); particle `data` copied for copied callbacks ([5.3](#53-particles-and-sprite-textures)); the district guard with the generated district map and its 1.5 s look-ahead, the PC renderer told of loading levels (vanilla `level.gc` edit, off by default) ([6.1](#61-how-jak-2-loads-its-levels)); `hj2-update-vis-nick` in place of the continue manager ([9.3](#93-respawn-points)); spawn distance caps for the city's spawners and props ([11](#11-memory-and-performance)); `hj2-yakow` ([5.6](#56-city-actors)); 8 door classes from Jak 2's models for 42 doors ([6.3](#63-doors-and-elevators)) | Pillar death: phase 14's copied `vis-dist` (200 m) made the pillar-top airlocks be born on the way up, and their `on-inside` loaded the bottom set: the top unloaded under Jak. Jak 3's airlock tests distance on x and z only; Jak 2 paused unseen doors through its visibility data: a height lump bounds it. The mountain: the translator turned `'special` into `#f`. Black props: their light was in palette 0 only, and interior moods light others. Hip Hog crash: `hj2-hiphog-mirror-sheen-func` read Jak 2's `*hiphog-mirror-sheen-waveform*`, never copied. The void: no loading face covers that street. Black areas: the renderer heard of a level only once it was loaded. The district map puts 46 of the 48 city continues in their own district, the other 2 in alleys outside it, none in another Then: Haven Forest's far end (`hj2-forstb`: the mother tree and the Precursor stone head) shown as soon as region 436 loads it (`region_script_overrides`; Jak 2 shows it only when the camera crosses the small face 434); `hj2-anim-loop` steps its animation once per frame like Jak 2's `med-res-level` (a seek-until-done loop never yields on a one-frame animation such as the low-res throne's); swingpoles (Dead Town, the palace cable, the fortress exit) and the dig's trapezes grabbable: Jak 3's target only takes `'pole-grab` while `jakb-pole-cycle-ja` is loaded, an animation of `jak-pole+0-ag` that its own levels with poles carry (halfpipe, precc, tema): the manifest's `art_groups` give it to `swingpole` and `hj2-dig-balloon-lurker` |

## 14. Not done yet

- **Not played in game yet (phase 12):** everything in its row of [13](#13-change-history) but
  the Freedom HQ crash fix.
- **Not played in game yet (phase 19).** To check on a cold boot, in the city with the traffic on:
  - hitting a citizen or a guard: the minimap flashes, the music switches to its alert mode, guards
    hunt Jak; 30 s without offence: the guards stand down and the alert ends; 8 kills raise it;
  - with the music volume at 0: the alarm sounds instead, and stops at the end;
  - with the Hellcats and guard bikes on: hitting one, or reaching alert 2, makes them chase and
    shoot Jak; stealing one stops its chase; none fly at level 1, more come at levels 2 and 3;
  - Dark Jak raises the alert to 2;
  - the Mods menu toggle off during an alert: everything stops at once; on again: no alert until
    the next offence.
  - the minimap in the city: Jak 2's map of the district Jak is in, following him across the
    districts; the guards as blue icons with their cone, gone when they leave; with the Hellcats
    and guard bikes on, larger blue icons with their cone on them, gone when one is destroyed or
    stolen; the cones still shown while Jak drives in the city; no map in Jak 3's own levels
    changed (cones still hidden there while Jak drives).
  - the stadium: from the main town (on foot, then by zoomer), the stadium grounds drawn before Jak
    reaches them; through the stadium's gate into the race track and its tunnels, the track drawn
    and kept loaded, Jak's level the track (`hj2-stadd`), the grounds again on the way out. In the
    log: `hj2: renderer loads hj2-stdm ahead of Jak` well before `GAMEPLAY: enter hj2-stdm`, and no
    `district guard loads hj2-gena` while in the track.
- **Not played in game yet (phase 20): the city's loading.** On a cold boot, walk and drive across
  the city (port, gardens, market, palace, main town, stadium, slums): districts drawn before Jak
  reaches them, no void, no freeze. In the log: `hj2: renderer loads <district> ahead of Jak`
  seconds before that district's `Adding level`; few or no `hj2: <district> waits for the
  renderer` once in the city (their count is the time Jak waits); no `wanted in place of` back and
  forth; `district guard loads` rare (a face walked around).
- **Not played in game yet (phase 16).** To check on a cold boot, with Jak 2 extracted:
  - the music of each place (the city's `city1`, the forest's, the palace cable's...), its
    variations when Jak draws his gun, rides the board, turns dark or drives, and Jak 3's music
    back once Jak leaves for Jak 3's levels; the music volume and the pause menu;
  - the ambiences (the city, the Hip Hog, the forest, the dig's lava) and the object sounds of the
    phase-16 row of [13](#13-change-history);
  - the traffic's engines, footsteps and guards, the citizens' Jak 2 lines (shoot near them, take
    their vehicle);
  - the Baron's speeches near a speaker, stopping when it breaks;
  - with the speech and sound volumes of the options menu; the game log has a
    `No sound bank file` warning for any bank missing.
- **Not played in game yet (phase 15b).** To check on a cold boot (`task boot-game`), on a save
  made outside the mod's levels (a save restores its continue):
  - riding the palace pillar's elevator up and down: no death at the top, the low-res city never in
    the lobby; each airlock opening only when Jak stands at its level;
  - Haven Forest: the mountain and its transport platform seen and ridden from the forest;
  - the Hip Hog (no crash, the mirror's sheen), its props and Onin's tent's lit, not black;
  - walking and driving from the port towards the palace and across every border: no void, no black
    area (the game log's `hj2: district guard loads ...`);
  - dying in each district and in a few places: Jak respawns at the closest Jak 2 continue of the
    district he is in (no longer the one he arrived in);
  - the yakows in the gardens' pastures (idle, graze, walk near Jak, kicked when hit), the 42 Jak 2
    doors (model, opening, solid leaves);
  - the lag: open the ImGui bar (left Alt), Debugging, Frame Time Plot, then compare a busy district
    (the port, the market) with the traffic off (Mods menu), then with the graphics options' PS2
    Options page: Particle Culling on (the PS2's distance cull of part spawners; off, every launcher
    counts as at the camera, with a 4 times larger sphere, `sparticle-launcher.gc`) and Level of
    Detail (Foreground) on Default (the PS2's distances, `ps2-lod-dist?`). The caps of [11](#11-memory-and-performance) are tuned
    in the manifest if one of these changes much.
- **Not played in game yet (phases 14 and 15),** but what the user's second test covered.
  To check on a cold boot (`task boot-game`):
  - the city: every district warp, walking across every district border (`display-wait`, no
    district missing: the game log's `hj2: ... wanted in place of ...`), the palace lobby without
    the low-res city, the respawn point in each district, the pools of `hj2-pal` and `hj2-stdm`;
  - the traffic: on each district's navigation, never over the void, the parked vehicles, riding
    down the palace pillar (the phase-15 crash), the Mods menu's traffic switch off and on;
  - the Hellcats: stealing one throws its pilot out (alert 2), and the guard turrets pop up near
    Jak's vehicle;
  - the particles of every place and their textures (no squares, no other place's textures), the
    districts' (the hub's sprite page);
  - the hazards: the palace cable (nuts, falling platforms, fans, rotating gun, gun turrets), the
    fortress's lasers and electric belt, the avalanche, the dark eco pool, the gun buoy, the castle
    pad's electric gate, the dig's stomp blocks;
  - the open iris doors and the canyon, the kiosk, Onin's tent;
  - the decor: the force-field walls fading, the searchlights, the barges, the Oracle's banners,
    the hideout's lamp, the garage's curtain and cars, Vin's turbines, the forest's birds and fish.
- **Haven Forest's dark lake:** the forest's water is Jak 2's sea, drawn from the city's ocean map
  (its mask covers the lake, its height is 0 m like Jak 2's). Phase 10 had that map set and the
  lake still wasn't seen; the cause isn't found. Phase 11 adds the ocean order
  ([5.4](#54-water-and-ocean)), which fixes one possible cause (another level's map drawn first).
  To look in game, standing at the lake, in the REPL: `(= *ocean-map* *ocean-map-havenj2*)` should
  be `#t`.
- **Places Jak 2 opens at the end of the game, not ported yet** (found by following every door,
  elevator, warp gate and region script of the city in the end-of-game state). Their doors stay shut
  until then (a door waiting for a level that isn't ported):

  | Place | Jak 2 levels | Reached by |
  |---|---|---|
  | Mar's tomb | `tomba`, `tombb`, `tombc`, `tombd`, `tombe`, `tombboss` | the palace plaza's airlock (`com-airlock-outer-22`, `-inner-27`, `-inner-28`) |
  | The sewers | `sewescb`, `sewesc` | the industrial section's airlock (`com-airlock-outer-13`) |
  | The underport | `underb`, `under` | the port's doors (`hip-door-a-20`; `-21` opens from inside) |
  | The castle | `castle`, `casboss`, `cascity` | the castle pad's door (`cas-front-door-1`) |
  | The drill platform | `drillmid`, `drill`, `drillb`, `drillmtn` | Vin's room's warp gate |
  | The strip mine | `strip` | the prison's warp gate |

  Not open at the end of the game: the inside of the palace (missions only), the fortress's dump
  (its gate waits for a level nothing loads then).
- **Left out of phase 15**, with the reason in the manifest:

  | What | Why |
  |---|---|
  | The race track's force field (`stad-d-force-field`) | Its ring of walls needs Jak 2's own collide meshes, which the level port can't copy yet |
  | The pumping station's tank wreck | No rip has its wreck animation (the decompiler's animation export needs a fix) |
  | The mountain's buried rocks, step rocks, the rhino's walls, the breakable walls; Dead Town's walls the titan suit breaks | Broken for good at the end of the game; their end poses aren't in the rips |
  | The mountain's gear device (`mtn-gear-device`) | Its collapsed pose covers 30 of its 37 pieces |
  | Enemies, precursor orbs | Decision: no enemies, no orbs |
  | The garage doors | Decision: the garage stays open ([6.3](#63-doors-and-elevators)) |

- **Animated textures:** Jak 2's waterfalls and lava are still ([4.2](#42-level-builder)).
- **The fortress:** the prison's torture cutscene and the pool's ripples; the turrets' light
  flashes, the laser's shadow. **The stadium:** its races.
- **The construction site:** the Baron's fight (its breaking scaffolds, the bomb).
- **The farm:** the sprinklers' water.
- **The dig:** its spiky spheres. Its fixed cameras and the castle pad's: Jak 2's `caspad`, `dig3a`
  and `dig3b` were extracted before the camera export existed (a new Jak 2 extraction of these
  levels adds them; their camera regions are dropped meanwhile).
- **Traffic:** Jak 2's citizen and guard models, the KG and Metal Head squads.
- **Sounds left out (phase 16):** the object sounds in no Jak 2 bank (the yakow's, the dig's
  `mud-plat`, `atoll-windmill`...), or in a bank not loaded where the object stands (the barges'
  engines, `PORTRUN1`; the fortress turrets' shots); the sounds of Jak 2's `COMMON` and `COMMONJ`
  banks (Jak 3's common bank is loaded instead); the sounds played by particle callbacks (not
  copied, [5.3](#53-particles-and-sprite-textures)); the gun buoy's voice line `cityv052`. Only 5
  of the atoll's pistons play their loop: Jak 2 picks them by an options lump the level port
  doesn't keep, so they are listed by name (`*hj2-piston-sound-names*`). Jak 2's music doesn't fade
  in or out between levels.
- **The OpenGOAL launcher:** a release ships `goal_src` and `custom_assets`, and the launcher
  extracts and compiles the mod's target game (Jak 3) only. This mod needs Jak 2 extracted and the
  level port run first (the levels aren't in git), which the launcher doesn't do: for now it is
  built from the repository.
- **The save slot's picture** is Jak 3's choice ([9.4](#94-saves)).
- **Native non-regression, not met yet:** the time gate always stands in Jak 3's Freedom HQ,
  whatever the menu says. The vanilla code changes: a faction manager check in `guard.gc`, which
  changes nothing where Jak 3's faction manager exists (Jak 3's own city), and the PC renderer
  predicate in `level.gc`, `#f` by default, which the mod sets for its own levels only. The sound
  changes to Jak 3's overlord ([4.5](#45-sound)) only act on files Jak 3 doesn't have (`.MUS`
  music, `VAGDIRM.AYB`), or on a missing bank, which asserted before.
- **Symbols prefixed with the mod's slug, partly:** the menu's settings use
  `mod-jak2-haven-city-`; the levels' code uses the level prefixes `havenj2-` and `hj2-`.
- **Verified facts in the Lisp wiki, not yet:** the verified Jak 3 facts are listed in
  [10](#10-jak-2-and-jak-3-differences); record them with the `kb` skill.
- **Cover thumbnail:** none yet (`docs/img/mod/mod_cover.png`).
