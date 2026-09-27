# Jak 2 Haven City in Jak 3 — Technical README

This document explains how the `jak3/features/jak2-haven-city` branch rebuilds Jak 2's Haven City
and the places around it inside Jak 3, and how to rebuild, extend and debug it. For each feature it
gives what you see in game, how it is made, which files hold it, and the problems met on the way.
Players only need the root [`README.md`](../../../README.md).

**Contents**

1. [What the mod does](#1-what-the-mod-does)
2. [How it is built](#2-how-it-is-built)
3. [Rebuilding it step by step](#3-rebuilding-it-step-by-step)
4. [Tooling changes (C++)](#4-tooling-changes-c)
5. [The city level](#5-the-city-level)
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
| Haven City | Jak 2's whole city as one Jak 3 level, `havenj2`: 16 Jak 2 levels merged (`ctywide`, the 14 districts, the stadium grounds) with their lighting, collision, props, water, particles and neon signs | [5](#5-the-city-level) |
| Places | 25 more levels, one per Jak 2 place reached from the city (Hip Hog, hideout, palace pillar and roof, Dead Town and the Sage's hut, construction site, pumping station, mountain, Haven Forest, the inside of the fortress, the stadium's race track...), loaded and unloaded by Jak 2's own door, elevator and region scripts | [6](#6-places-and-level-loading) |
| Dig site | The castle pad and the dig, reached by the port's air train or on foot from the pumping station, with their moving platforms | [6.5](#65-the-dig) |
| Dead Town, construction site | Dead Town's water, swinging bars, crumbling slabs, floating platforms and the Sage's hut; the construction site's silo doors and bomb elevator | [6.9](#69-dead-town), [6.10](#610-construction-site-fortress-and-stadium) |
| Air trains | "Press triangle to travel to the Dig Site": a short fade, and Jak stands next to the other air train | [6.6](#66-air-trains) |
| Traffic | Jak 3's citizens, guards, hover bikes and cars on Jak 2's navigation data, at Jak 2's density | [7](#7-navigation-and-traffic) |
| Time and weather | A fixed hour or Jak 2's day and night; Jak 3's changing weather or a fixed one (sunny to thunderstorm, snow) in the whole game | [8](#8-moods-time-of-day-and-weather) |
| Travelling | Mods menu warps to every district, key places and places outside the city; two time gates between Jak 3's Freedom HQ and Jak 2's underground hideout; respawn next to Jak, at Jak 2's continue points | [9](#9-travelling) |
| Saves | Saving anywhere in the mod's levels; the save screen names Jak 2's world on the slot | [9.4](#94-saves) |

## 2. How it is built

### 2.1 From Jak 2's data to Jak 3 levels

Nothing is modeled by hand. Everything comes from Jak 2's own data, extracted by the decompiler,
then turned into Jak 3 custom levels by Python generators and `goalc`.

```text
Jak 2 ISO --task extract--> out/jak2/fr3/<level>.fr3          background, collision, textures
                            decompiler_out/jak2/entities/     actors, cameras, navigation data
                            decompiler_out/jak2/levels/       model rips (rip_levels)
      |
      v  Python generators (custom_assets/jak3/levels/havenj2/gen_*.py)
custom_assets/jak3/levels/havenj2/ and hj2-*/           level .jsonc, .gd, region files
custom_assets/jak3/models/custom_levels/hj2-*.glb       Jak 2 models rebuilt for build-actor
goal_src/jak3/levels/havenj2/havenj2-part.gc, ...       particles, traffic height map
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
| Generators | `custom_assets/jak3/levels/havenj2/*.py` | Turn Jak 2's data into level files, models, particles and level-load-infos (table below) |
| Level data | `custom_assets/jak3/levels/havenj2/` and 25 `hj2-*/` folders | Generated `.jsonc`, `.gd` and region files; only the part of `havenj2.jsonc` outside its GENERATED markers is written by hand |
| Models | `custom_assets/jak3/models/custom_levels/hj2-*.glb` (42) | Jak 2 models rebuilt for `build-actor` ([6.7](#67-rebuilding-jak-2s-models)) |
| Level code | `goal_src/jak3/levels/havenj2/` | Code linked into one level's DGO (table below) |
| Game code | `goal_src/jak3/pc/features/jak2-haven-city-*.gc`, `levels/havenj2/havenj2-ocean.gc` | In GAME.CGO: what several levels share, and the Mods menu |
| Vanilla edits | `goal_src/jak3/game.gp`, `goal_src/jak3/dgos/game.gd`, `goal_src/jak3/dgos/freehq.gd`, `goal_src/jak3/levels/city/traffic/citizen/guard.gc`, `decompiler/config/jak3/jak3_config.jsonc` | Build steps, GAME objects, the Freedom HQ's time gate model ([9.2](#92-time-gates)), one guard check ([7.2](#72-traffic)) |

The generators, in the order to run them from the repository root:

| Generator | Writes |
|---|---|
| `gen_havenj2_water.py` | The pools' water regions (`havenj2-water-regions.json`) |
| `gen_havenj2_mesh.py` | The static props and pool surfaces as one mesh (`havenj2-mesh.glb`) |
| `gen_havenj2_links.py` | Everything else: havenj2's actors and regions, `havenj2.gd`, every `hj2-*` level, `jak2-haven-city-levels.gc`, the `hj2-*.glb` models. It runs the three generators below |
| `gen_havenj2_props.py` | Props as Jak 3 actors, model rebuilding (`write_actor_glb`) |
| `gen_havenj2_particles.py` | `havenj2-part.gc` and the places' `hj2-*-part.gc`, the part spawners, the sprite texture lists |
| `gen_havenj2_nav.py` | `havenj2-nav.json`, `havenj2-height-map.gc` |
| `gen_havenj2_ocean.py` | `hj2-ruins-ocean.gc`, `hj2-mount-ocean.gc`: Jak 2's Dead Town and mountain ocean maps, copied from Jak 2's `goal_src` ([5.4](#54-water-and-ocean)). Independent of the others, run by hand |

Their helpers: `jak2_scripts.py` (the script translator), `jak2_actors.py` (Jak 2's actors, without
the ones Jak 2 never spawns), `convex_hull.py`, `nav_blob.py` (reads and writes navigation data),
`goal_lisp.py` (reads GOAL source files), `gen_util.py` (`write_if_changed`).

The GOAL files:

| File | DGO | Holds |
|---|---|---|
| `levels/havenj2/havenj2-obs.gc` | HJ2 | Palace gate, propaganda speakers |
| `levels/havenj2/havenj2-farm.gc` | HJ2 | Farm crops ([5.2](#52-props)) |
| `levels/havenj2/havenj2-part.gc` (generated) | HJ2 | Jak 2's city particles |
| `levels/havenj2/havenj2-signs.gc` | HJ2 | Animated neon signs |
| `levels/havenj2/havenj2-traffic.gc` | HJ2 | Traffic callbacks and density |
| `levels/havenj2/havenj2-height-map.gc` (generated) | HJ2 | How high the vehicles fly |
| `levels/havenj2/hj2-ruins-obs.gc` | HJR | Dead Town's slabs, bridge, floating platforms, beams and flag |
| `levels/havenj2/hj2-ruins-ocean.gc` (generated) | HJR | Dead Town's ocean map |
| `levels/havenj2/hj2-ruins-part.gc` (generated) | HJR | Dead Town's particles |
| `levels/havenj2/hj2-cons-obs.gc` | HJC | Construction site's silo doors and bomb elevator |
| `levels/havenj2/hj2-atoll-obs.gc` | HJL | Pumping station platforms and props |
| `levels/havenj2/hj2-mount-obs.gc` | HJM | Mountain platforms and props |
| `levels/havenj2/hj2-mount-ocean.gc` (generated) | HJM | The mountain's ocean map |
| `levels/havenj2/hj2-forest-part.gc` (generated) | HJF | Haven Forest's particles |
| `levels/havenj2/hj2-dig-obs.gc` | HJT | Dig platforms and props |
| `levels/havenj2/havenj2-ocean.gc` | GAME | Jak 2's city ocean map |
| `pc/features/jak2-haven-city-levels.gc` (generated) | GAME | 26 level-load-infos, 106 continue points, and the Freedom HQ's time gate arrival point |
| `pc/features/jak2-haven-city-world.gc` | GAME | Moods, time of day, weather driver, sprite pages, elevators, fortress gate, air trains, time gates, level callbacks, respawn, saves, traffic switch |
| `pc/features/jak2-haven-city-menu.gc` | GAME | Mods menu |

### 2.3 Design decisions

- **One monolithic city level.** Jak 3's PC level heap is 15 times the original on `master-dev`
  (`DEBUG_LEVEL_HEAP_MULT`), so a `large` level gets about 177 MB: enough for every Jak 2 city level
  at once.
- **One custom level per other place**, loaded and unloaded by Jak 2's own scripts
  ([6](#6-places-and-level-loading)).
- **Merge `.fr3` render trees instead of re-baking glTF.** The Jak 2 extraction already contains the
  tfrag, TIE and shrub trees with their time-of-day palettes, and a collision mesh with each
  triangle's surface type (`pat`).
- **Jak 2 world coordinates are kept.** Jak 3's own city sits at the same place, so these levels
  must never be loaded together with Jak 3's city levels.
- **What more than one level uses is in GAME** (moods, the ocean map, elevators, air trains). Jak 2
  unloads the city in several places, and a place must never depend on the city's code.
  `jak2-haven-city-world.o` sits after `elevator.o` in `game.gd`: a type's parent must be linked
  before it.
- **Generated, never edited by hand.** Rerunning the generators rebuilds every level file from
  Jak 2's data; a fix goes into a generator.

### 2.4 Worked example: the Hip Hog door

Every door, elevator and region of the mod follows the path of this one.

1. **Jak 2's data.** The entity dump `decompiler_out/jak2/entities/ctyport-actors.json` lists
   `hip-door-a-6`, a `hip-door-a` whose lumps hold scripts: `on-activate` (Jak comes near: load the
   Hip Hog next to the port district), `on-enter` (display it), `on-cross` (Jak is now in it),
   `on-deactivate` (hide it again), `on-notice` (the levels the door waits for before it opens) and
   `next-actor` (the Hip Hog's own door).
2. **Translation.** `gen_havenj2_links.py` reads the actor through `jak2_actors.py` and translates
   each script with `jak2_scripts.py`: `ctyport` becomes `havenj2` (the whole city), `hiphog`
   becomes `hj2-hiphog`.
3. **Level file.** The actor goes into `havenj2.jsonc` between the GENERATED markers, each script as
   a `["pair", "<script>"]` lump and the inner door as `["string", "hip-door-b-1"]`. The door's art
   group `hip-door-a-ag` goes into `art_groups`: Jak 3 only looks a process's art up in its own
   level.
4. **Build.** The level builder writes the lumps as GOAL pairs and strings in the bsp (`ResLump`).
5. **In game.** Jak 3's `hip-door-a` class (GAME, `airlock.gc`) runs the scripts. `hj2-hiphog`
   loads (its level-load-info is in `jak2-haven-city-levels.gc`, its DGO is `HJH`), the door opens
   once it is loaded, and the Hip Hog's door `hip-door-b-1` leads inside.

## 3. Rebuilding it step by step

1. **Build the tools.** The decompiler and `goalc` changed. The particle generator runs
   `fr3_check`, so build it too.

   ```bash
   task build-release-decomp
   task build-release-game
   cmake --build out/build/Release --target fr3_check --config Release
   ```

2. **Extract Jak 2.** `task extract` writes the `.fr3` files and the entity, camera and navigation
   dumps. The generators also read Jak 2's model rips, which the decompiler writes only with
   `rip_levels` on: set it to `true` in `decompiler/config/jak2/jak2_config.jsonc` for this
   extraction.

   ```bash
   task set-game-jak2
   task extract
   ```

3. **Extract Jak 3.** Some sprite textures come from Jak 3's `.fr3` files, and the Freedom HQ's
   `.fr3` must hold the time gate's model (`extra_art_groups_by_dgo` in `jak3_config.jsonc`,
   [9.2](#92-time-gates)).

   ```bash
   task set-game-jak3
   task extract
   ```

   On a Jak 3 already extracted, only the Freedom HQ needs extracting again (a few seconds):

   ```bash
   out/build/Release/bin/decompiler.exe ./decompiler/config/jak3/jak3_config.jsonc ./iso_data ./decompiler_out --version ntsc_v1 --config-override '{"decompile_code": false, "levels_extract": true, "allowed_objects": [], "levels_to_extract": ["FREEHQ.DGO"]}'
   ```

   The log shows `extra_art_groups_by_dgo: baking 'warp-gate-ag' into FREEHQ.DGO`. Without it
   the Freedom HQ has no gate (GAME checks that the model is there before spawning it).

4. **Run the generators** from the repository root, in this order:

   ```bash
   python custom_assets/jak3/levels/havenj2/gen_havenj2_water.py
   python custom_assets/jak3/levels/havenj2/gen_havenj2_mesh.py
   python custom_assets/jak3/levels/havenj2/gen_havenj2_ocean.py
   python custom_assets/jak3/levels/havenj2/gen_havenj2_links.py
   ```

5. **Build the levels and the code:** `task repl`, then `(mi)`. It builds the bsps, the `.fr3`
   files, the custom models and the DGOs.
6. **Check the result offline** (`total: 0 errors` expected):

   ```bash
   out/build/Release/bin/fr3_check.exe out/jak3/fr3/havenj2.fr3
   ```

7. **Play:** `task boot-game`, then L3 + SELECT, Mods, jak2-haven-city, Warp to Haven City (Jak 2).

What to redo after a change:

| You changed | Redo |
|---|---|
| A generator | Run `gen_havenj2_links.py` (or the one you changed), then `(mi)`. The generators only rewrite files whose content changed (`write_if_changed`), so only those levels rebuild |
| A `.gc` file | `(mi)` |
| The level builder (`goalc/build_level`) | `task build-release-game`, touch the level's `.jsonc`, `(mi)` |
| The decompiler | `task build-release-decomp`, extract the Jak 2 levels concerned again (below), rerun the generators, `(mi)` |
| `extra_art_groups_by_dgo` in `jak3_config.jsonc` | Extract the Jak 3 levels concerned again (step 3), `(mi)` |

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
by the particle generator). On a Jak 2 `.fr3` it prints the collision extent, to choose
`collision_bounds`, and the triangles tagged with a prototype.

## 5. The city level

### 5.1 Background and collision

- `import_fr3` merges the `.fr3` files of the 16 Jak 2 levels. Collision vertices keep their
  original `pat`: the `pat-surface` bit layout is identical in Jak 2 and Jak 3.
- `collision_bounds` drops unreachable backdrops, kilometers wide in `ctywide`, `palcab`, `atoll`
  and `mountain` (`atoll` alone made a 70 MB collide hash without it).
- **Story state.** Jak 2 shows or hides some TIE prototypes depending on the story
  (`prototypes-game-visible-set!`, which also disables their collision). `HIDDEN_PROTOTYPES` in
  `gen_havenj2_links.py` keeps the state most of the game shows: the palace plaza before Mar's tomb
  is found (the Baron's statue standing, no rubble), the market roof before the tanker crash, the
  Hip Hog's paintings before the nest boss, Dead Town's tower standing, the construction site before
  the Baron's fight.
- **Sky:** drawn only when an active level has the `sky` level flag (every outdoor place has it).

### 5.2 Props

- Jak 2 ignores the actor scale lump, so props keep their model size.
- 1126 market and farm props (crates, baskets, sacks, fruit stands, crops, sprinklers) are Jak 3's
  own classes: Jak 3 ships Jak 2's city props (`ctymark-obs`, `ctyfarm-obs` code, linked into HJ2;
  art from Jak 3's levels). They are solid and breakable; crops get a random yaw like Jak 2's.
- **Farm crops** (marrows, beetrees, cabbages, small cabbages, chilirots): Jak 3 keeps them as
  scenery, without collision. `havenj2-farm.gc` ports Jak 2's class as `hj2-farm-*`:
  - solid (a sphere per crop);
  - a light hit shakes its leaves (Jak 2's shakers);
  - a strong hit (a vehicle, a gun shot, a dark attack) bursts it into pieces and particles.

  The pieces are Jak 2's burst models, still in Jak 3's `farm-*-ag` art groups (elements 3 to 5),
  thrown by Jak 3's `joint-exploder`. The particles are Jak 2's, in `havenj2-part.gc`.
- The other static props and the pool surfaces are one mesh, `havenj2-mesh.glb`, lit like merc;
  solid ones get an invisible collision box.

### 5.3 Particles and sprite textures

- `gen_havenj2_particles.py` translates Jak 2's city part files into `havenj2-part.gc`: 674 parts
  and 178 groups, renumbered to ids no Jak 3 code in havenj2 uses. It places 3096 part spawners and
  the 3 neon signs.
- **Sprite textures.** Jak 2 draws particles from each level's sprite texture page, which Jak 3
  doesn't have. `sprite_textures` puts the textures in havenj2's `.fr3` under page 1566, and
  `hj2-sprite-page-*` (GAME) builds the matching texture page at load and makes it the level's
  sprite page while havenj2 is active.
- The page stays registered when the level is only deactivated (hidden while Jak is in the Hip Hog,
  the palace lobby...): a failed texture lookup gives particles `common-white`, drawn as squares.
- **Prop particles.** Jak 3's market and farm props break into sprite pieces and fruit, with
  textures of Jak 3's city sprite pages that Jak 3's `market-activate` and `farm-activate` set up.
  Those 15 textures are at the end of havenj2's page (`JAK3_PROP_TEXTURES`), and
  `hj2-prop-textures-on` points the parts to them when havenj2 is activated.
- **Two Jak 2 details changed meaning in Jak 3**, and the generator translates them (details in
  [10](#10-jak-2-and-jak-3-differences)):

  | Jak 2 detail | Symptom when copied as is | Translation |
  |---|---|---|
  | The smoke and fire texture groups (`birth-func-texture-group`) name textures by id, in Jak 2's `effects` page (id 12) | Squares in chimney smoke and fires: page 12 is Jak 3's font | Remapped by name to Jak 3's `level-default-sprite` (page 4) |
  | Particle flags 12, 16, 20 and 21 | Fountain drops flying in random directions: their acceleration turned with the spawner | Moved to Jak 3's bits 13, 17, 19 and 20 (`CPUINFO_FLAGS`) |

- `:part-engine-max 255` in havenj2's level-load-info, for the static lights.
- **The places' particles** (`PLACE_PARTICLES` in `gen_havenj2_particles.py`): the same translation
  for one place, in a `hj2-<place>-part.gc` linked into its DGO, with the place's own sprite page.
  Callbacks Jak 3 doesn't have are copied from Jak 2's file (`COPIED_FUNCS`): renamed `hj2-*`, their
  part ids moved, and Jak 2's matrix argument read as Jak 3's `sprite-vec-data-2d` (same layout).

  | Place | Particles | Parts, groups | Spawners | Texture page | Ids |
  |---|---|---|---|---|---|
  | `hj2-forest` | Waterfalls' spray and drops, butterflies, fireflies, cattails | 53, 17 | 60 | 1594 | parts 2600-2799, groups 800-839 |
  | `hj2-ruins` | Birds circling the moon, street lights' glows | 7, 2 | 90 | 1627 | parts 2800-2999, groups 840-879 |

  Each place has its own id ranges, past the city's (parts 1200-2599, groups 300-799), so that a
  place loaded with the city never overwrites the city's particles.
- **Choosing a texture page id.** The PC texture pool (`TexturePool`) gives each page of Jak 3's
  directory (`game/graphics/texture/jak3_tpage_dir.cpp`) as many slots as that page has textures,
  one after the other. An id Jak 3 never uses has 0 slots, so every unused id of a run (1566 to
  1572) starts at the same slot, and a page's textures spill over the slots of the pages after it.
  Two pages loaded together must not share slots: 1594 starts 311 slots after 1566 (the city uses
  206), 1627 starts 1309 after it. The first choice, 1567 and 1568, put texture 0 of the forest,
  of Dead Town and of the city in the same slot.

### 5.4 Water and ocean

- Jak 3's water is regions only. havenj2 has a city-wide ocean sphere and one volume per pool
  (palace plaza and stadium). Places get volumes from Jak 2's `water-vol` actors, and the ocean ones
  Jak 2's ocean water spheres.
- `*ocean-map-havenj2*` (GAME, `havenj2-ocean.gc`) is a generated copy of Jak 2's city ocean
  tables, used by havenj2, the palace roof and cable, the pumping station and Haven Forest.
- Dead Town's sea and the mountain's stream have maps of their own in Jak 2, copied by
  `gen_havenj2_ocean.py` into their level code (`*ocean-map-hj2-ruins*`, `*ocean-map-hj2-mount*`).
  Jak 3's `ocean-map` has no `ocean-spheres` field: the copy leaves them out.
- **Which map is drawn.** Jak 3 draws the ocean of the first displayed level, in draw order
  (`draw!` of `ocean`); levels are sorted by `draw-priority` (the city 9.0, the places 10.0), then by
  load slot. So a level with another map still displayed could hide the water of the level Jak is
  in: the mountain seen from Haven Forest. `hj2-update-ocean-order` (GAME, run by the respawn
  process every frame) sets the `draw-priority` of the level Jak is in to 8.5 when it has an ocean
  map, and the info's value back on the others.

### 5.5 Palace gate, propaganda speakers, neon signs

- **Palace gate.** Jak 3 has no palace door. `hj2-palace-door` is Jak 2's model and animation
  rebuilt by `build-actor`; it must really close, because the city is hidden in the lobby and
  unloaded above it. `build-actor` plays animations at 60 fps, so Jak 2's 15 fps frame numbers are
  scaled by 4 in `havenj2-obs.gc`. The glb holds only the vertices the gate uses and an invisible
  collision box bound to the sliding door joint.
- **Propaganda speakers** (`hj2-propa`): a pole projecting the Baron's hologram (a particle group
  turned towards the closest target), solid. Like in Jak 2, the first hit damages its projector and
  the second breaks it; a strong hit (a gun shot, a vehicle) breaks it at once. Each hit rings like
  an iron crate (Jak 3's `icrate-nobreak` and `icrate-break`). Jak 2 switches between its three
  looks with mesh masks, which build-actor's models don't have: the damaged and broken looks are
  models of their own (`hj2-propa-damaged`, `hj2-propa-broken`), drawn by a child process
  (`hj2-propa-look`) while the intact model is hidden. The Baron's speeches are Jak 2 voice
  streams, not in Jak 3.
- **Neon signs** (`havenj2-signs.gc`): the Baron's skull, Praxis' name and the Hip Hog's marquee,
  blinking random patterns like Jak 2's.

## 6. Places and level loading

### 6.1 How Jak 2 loads its levels

Jak 2 loads its levels with scripts in three places: doors and elevators (`on-activate`,
`on-enter`, `on-inside`...), invisible regions (planes crossed, volumes entered; Jak 2's region
database is `goal_src/jak2/tools/db-fixtures/fixture-region.sql`) and continue points. Jak 3 runs
the same script language and the same airlock, elevator, warp gate and region code, so the
generator ports them all. `jak2_scripts.py` translates them:

| In Jak 2's script | Becomes |
|---|---|
| A city level (`ctyport`, `ctywide`...) | `havenj2` |
| Another ported level | Its `hj2-*` level |
| A level that isn't ported | Dropped from lists; a door waiting for it stays shut |
| `want-display` of a city level, from a city script | Dropped: the whole city is one level, shown while Jak is in it. From another level it applies to `havenj2` |
| Story checks (`task-closed?`, `task-open?`) | Evaluated for the end of the game, except `palace-sneak-in-meeting` (kept open) and per-region exceptions (`REGION_OPEN_TASKS`) |
| Continue names (`want-continue`, warp gate destinations) | The mod's continue names |
| Sounds, sound banks, dialogs, cutscenes, settings other than fixed cameras, `task-close!` | Removed |

Region ids are Jak 2's plus 1000; water regions start at each level's `base_id`.

### 6.2 The levels and their memory

| Level | DGO | Jak 2 | Memory | Loaded with |
|---|---|---|---|---|
| `havenj2` | HJ2 | the city levels, `stadium` | large | one small-edge place |
| `hj2-hiphog`, `hj2-gun`, `hj2-vin`, `hj2-hide`, `hj2-oracle`, `hj2-garage` | HJH, HJG, HJV, HJD, HJO, HJK | interiors | small-edge | the city |
| `hj2-ruins` | HJR | `ruins` (Dead Town) | small-edge | the city, or `hj2-sage` deep in Dead Town |
| `hj2-sage` | HJW | `sagehut` (the Sage's hut, old Samos') | small-edge | `hj2-ruins` |
| `hj2-forta`, `hj2-fortb` | HJI, HJJ | `forresca`, `forrescb` (the inside of the fortress) | small-edge | `hj2-forta` with the city (the slums' fortress gate), then each other |
| `hj2-stadd` | HJZ | `stadiumd` (the stadium's race track) | small-edge | the city (the stadium's regions) |
| `hj2-consb`, `hj2-cons` | HJB, HJC | `consiteb`, `consite` | small-edge | `consiteb` with the city, then both without it |
| `hj2-pshaft` | HJS | `palshaft` (palace pillar) | small-edge | the city, or the roof and cable |
| `hj2-proof`, `hj2-pcab` | HJP, HJQ | `palroof`, `palcab` | small-center, small-edge | the pillar, never the city |
| `hj2-atollx` | HJA | `atollext` (the way to the pumping station) | small-edge | the city, or the station |
| `hj2-atoll` | HJL | `atoll` (the pumping station) | large | `hj2-atollx` |
| `hj2-mount` | HJM | `mountain` | small-edge | the city (its foot), `hj2-mtnx` or `hj2-forest` |
| `hj2-mtnx` | HJX | `mtnext` (the temple outside, a backdrop) | small-edge | `hj2-mount` |
| `hj2-forest`, `hj2-forstb` | HJF, HJN | `forest`, `forestb` (Haven Forest) | large, small-edge | `hj2-mount`, or each other |
| `hj2-caspad` | HJY | `caspad` (the castle pad) | small-edge | the city (air train), `hj2-atoll` (on foot) or `hj2-dig` |
| `hj2-dig`, `hj2-digb` | HJT, HJU | `dig3a`, `dig3b` (the dig) | large, small-edge | `hj2-caspad`, or each other |

Jak 3's level heap has 18 chunks: `large` takes 12, a `small-edge` 6 at either end, a
`small-center` the 6 in the middle. The generator checks every continue's level list against these
rules, and leaves out a Jak 2 continue whose levels don't fit (it prints them).

A custom level's name is at most 10 characters (the level builder asserts it): Jak 2's `sagehut`,
`forresca` and `forrescb` became `hj2-sage`, `hj2-forta` and `hj2-fortb`. Their continue points keep
Jak 2's names (`hj2-forresca-start`).

### 6.3 Doors and elevators

- **Stand-in doors.** `hip-door-b`, `hide-door`, `oracle-door` and `vin-door` use the closest Jak
  3 door class and model.
- **Keira's garage has no doors:** its two sliding doors aren't placed, and the region that loaded
  the garage also shows it now (`REGION_SCRIPT_OVERRIDES`, region 319): the door's `on-enter` did.
- **Fortress gates** (`hj2-fort-gate`, GAME): Jak 2's `fort-entry-gate` (Jak 3 has no such door),
  Jak 3's airlock with Jak 2's model and opening animation, each leaf solid on its joint. The slums'
  gate opens on the inside of the fortress: Jak 2 pairs it with the dump's gate (`fordumpa`, not
  ported), `NEXT_ACTOR_OVERRIDES` pairs it with `forresca`'s. The gates to the prison and to the
  fortress's exit stay shut.
- **Script changes by hand** (`SCRIPT_OVERRIDES`): a door script replaced or removed, by Jak 2 level
  and actor name. The only one: the palace roof and cable outer doors lose their `on-deactivate`
  ([10](#10-jak-2-and-jak-3-differences), "Airlock scripts at load").
- **Door translation.** A door's `on-notice` (the levels it waits for) is evaluated for the story
  state first (`strict_notice` in `jak2_scripts.py`): a branch naming a level that isn't ported
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
  as soon as Jak comes back in from the roof: the low-res city seen from the roof (`palcab`) is gone
  before the ride down goes through it.

### 6.4 Pumping station, mountain and Haven Forest

- **The way to Haven Forest.** In Jak 2 the gardens airlock opens on the mountain's foot, and a warp
  gate there is the only way up. Both warp gates are Jak 3's `warp-gate` (same `on-notice` format).
  At the top, Jak 2's `trans-plat` (ported as `hj2-trans-plat`) rides down the stream to the
  forest.
- **The iris doors stay shut:** Jak 2 opens them once Mar's tomb is found, the story state the
  palace plaza is kept in ([5.1](#51-background-and-collision)), and the canyon behind them isn't
  ported. The temple elevator is parked at the top (it only leads to an iris door).
- **Platforms and props** (`PORTED_ACTORS`, `hj2-atoll-obs.gc`, `hj2-mount-obs.gc`): Jak 2's
  classes ported as `hj2-*` (pistons, turbines, lift catwalks, rotating pipes, sliders, windmills,
  the temple's moving, long, flipping and buried platforms...), with Jak 2's models. Their story
  state is the end of the game: the station running, the temple's gap bridged.
- **Crates** of the pumping station, the mountain, the forest, the dig, Dead Town and the fortress
  are Jak 3's (wood look, art in GAME), their pickups translated: Jak 3 inserted `eco-pill-light`
  and `lightjak` in `pickup-type`.
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
- **The dig's warp gate** leads to Vin's room. The generator translates the level names of a warp
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

- **Not ported:** the enemies, the spiky spheres, the stomp blocks, the precursor orbs, the
  particles.

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

`write_actor_glb` (`gen_havenj2_props.py`) turns a Jak 2 model rip into a `build-actor` model:

- **Kept primitives:** only the parts of the model the actor uses.
- **Collision:** a box around the model, or the convex hull of the model (`convex_hull.py`, over
  the model's extreme points to stay under build-actor's 255 vertices per collide mesh), bound to
  the main joint like Jak 2's meshes.
- **Joint-bound collision:** a collide mesh can be a joint's part of the model (the vertices mostly
  weighted to it), written in that joint's space. The GOAL collide prim names the joint (transform
  index = joint index + 1); build-actor's collide joint id is unused at runtime.
- **Borrowed animations:** a model can take its animations from another rip with the same joints.
  Jak 2 keeps the trapeze's swings in the balloon lurker's art group, and the rip exports them
  there.
- **Rest pose:** `build-actor` needs at least one animation, and some rips have none (Dead Town's
  slabs, the construction site's doors). `write_actor_glb` then writes a one-frame animation of the
  skin's rest pose: each joint's local transform is the inverse bind matrix of its parent times
  the inverse of its own (`rest_pose_anim`).
- **Hull heights:** a hull can keep only the vertices between two heights (`{"hull": y_min,
  "y_max": y}`), to keep a platform without what hangs under it (the construction site's bomb
  elevator: its 20 m platform, not its 64 m screw).
- **Models without an actor of their own:** `EXTRA_MODELS` builds a model that a class spawns as a
  child (the bomb elevator's hinges).

### 6.8 Actors Jak 2 never spawns

An actor whose `kill-mask` has the task bit `never` is never born in Jak 2, but the entity dumps
still list it. Every generator reads Jak 2's actors through `jak2_actors.py`, which drops them: a
palace lobby airlock (`com-airlock-outer-20`, where Jak 2's way from the gate to the elevator is
open), a Hip Hog door, a burning bush and part spawners of other story states.

### 6.9 Dead Town

Dead Town (`hj2-ruins`) is reached through the slums' airlock. Its actors (`PORTED_ACTORS`,
`hj2-ruins-obs.gc`, models rebuilt from Jak 2's):

| In game | Jak 2 | Here |
|---|---|---|
| The sea | its own ocean map | `*ocean-map-hj2-ruins*` ([5.4](#54-water-and-ocean)) |
| Bars Jak swings from | `swingpole` | Jak 3's `swingpole` (the bars themselves are background) |
| Slabs on pillars and the tower's bridge, crumbling under Jak | `ruins-drop-plat`, `ruins-bridge` | `hj2-ruins-drop-plat-a/b/c`, `hj2-ruins-bridge` (the model letter picks the class). Jak 2 plays their fall from streamed animations Jak 3 doesn't have, and leaves them fallen. Here a slab shakes when Jak lands on it, falls 0.6 s later for 1.5 s, stays out of sight 5 s, then is back |
| Platforms floating on the water, sinking under Jak | `sinking-plat` | `hj2-ruins-sinking-plat`: Jak 3's `rigid-body-platform` with Jak 2's constants (`rigid-body-plat.o` linked in HJR) |
| The tower's beams, slipping down when Jak comes near | `beam` | `hj2-ruins-beam`: Jak 2's slide animation, once, when the camera is within 25 m |
| The tower's flag | `ruins-scenes.gc` | `hj2-ruins-flag`, its animation in a loop |
| Birds, street lights | `ruins-part` spawners | [5.3](#53-particles-and-sprite-textures) |
| The Sage's hut (old Samos') | `sagehut` | `hj2-sage`, loaded by Dead Town's regions, lit like Dead Town. Mods menu: Dead Town: the Sage's hut |

Not ported: the enemies, the walls and pillars the titan suit breaks (broken for good by the end of
the game), the push blocks, Jak 2's sounds.

### 6.10 Construction site, fortress and stadium

- **Construction site** (`hj2-cons`, `hj2-cons-obs.gc`): the silo doors (each leaf solid on its
  joint) and the bomb elevator (solid at its platform, its hinges drawn by a child process), still
  like at the end of the game.
- **The inside of the fortress** (`hj2-forta`, `hj2-fortb`, Jak 2's `forresca` and `forrescb`): the
  slums' fortress gate opens on it ([6.3](#63-doors-and-elevators)), and its regions load the far
  end. Their moods follow Jak 2's (the fortress's four light groups, flickering electricity).
  Mods menu: Inside the fortress.
- **The stadium's race track** (`hj2-stadd`, Jak 2's `stadiumd`): loaded by the stadium's regions,
  with Jak 2's lights and shimmering force field (palettes 5 and 6). Mods menu: Stadium race track.

## 7. Navigation and traffic

### 7.1 Navigation data

Jak 2 gives each city district its own `city-level-info` (the traffic data: a grid of cells holding
nav segments, and a nav graph of nodes and branches, linked to the neighbor districts') and its own
nav meshes. These structures have the same layout in Jak 2 and Jak 3.

1. **Export.** The decompiler copies them out of each bsp as they are (`extract_nav.cpp`): the
   objects the roots lead to, with their pointers, type tags and symbols. A res-lump's `data-top`
   points past its data (to the next object): it isn't followed, and is rebuilt.
2. **Merge.** A bsp holds one city-level-info, so `gen_havenj2_nav.py` merges the 15 districts'
   into one: a 34 x 58 grid of 50 m cells (Jak 2's districts use 25, 40 or 50 m cells), 8955
   segments, 2743 nodes, 3321 branches. The links between districts become plain branches, and the
   26 nav meshes keep their ids (the graph refers to them).
3. **Cells.** The traffic engine activates a cell by the camera's distance to its sphere (radius +
   20 m always, + 120 m for pedestrians, + 200 m for vehicles in view), keeps at most 255 active
   cells (it drops the others silently), and kills an object whose cell isn't active. Like Jak 2's,
   every merged cell a district covers has a sphere around the whole cell, centered at mid-height of
   its districts; each segment is in the cell holding its middle; cells outside the districts get a
   zero sphere far under the city. Border spawns use a segment's `from-cell` (the cell of the
   segment before it on its branch).
4. **Missing nav mesh.** 41 pedestrian segments (`ctygenc`, `ctyport`) are on a nav mesh no level
   has: they get nav mesh 0, which the traffic engine never spawns citizens on.
5. **Build.** The result (`havenj2-nav.json`, a 1 MB data blob) goes into havenj2's bsp through
   `nav_data`. Jak 3 initializes the nav meshes at level load (the same `initialize-mesh!` as Jak
   2), and its traffic engine links the city-level-info when the traffic starts.

### 7.2 Traffic

Jak 3's citizens (`citizen-norm`, `citizen-chick`, `citizen-fat`), Freedom League guards
(`crimson-guard`) and hover vehicles (`bikea` to `bikec`, `cara` to `carc`) run on havenj2's
navigation data, driven by Jak 3's traffic engine.

| Part | How |
|---|---|
| Code | HJ2 links the objects of Jak 3's city DGO (`cwi.gd`) in the same order (`traffic_code()` in `gen_havenj2_links.py`), without Jak 3's city itself: its props, particles, missions and scenes, its trail graph and its height map. The height map (how high the vehicles fly) is Jak 2's, `havenj2-height-map.gc` |
| Art | The traffic types' art groups (`TRAFFIC_ART`) are in HJ2 and in havenj2's `.fr3`, instead of the levels Jak 3's city borrows. The vehicle HUD's health bar is at the end of havenj2's texture page |
| Start and stop | `havenj2-login` (callback slot 33) allocates the traffic engine, the Freedom League squad and the attack controller in havenj2's heap; `havenj2-logout` (34) drops them. `havenj2-activate` starts the traffic: the traffic manager first (it clears every traffic type's level), then every attacker freed (`cty-attack-reset`), then havenj2 as the level of the citizens, guards and vehicles |
| No faction manager | Like Spargus (`waswide-init.gc`). Jak 3's faction manager runs its territories from the branches' `clock-type`, which Jak 2's graph uses for traffic lights, and it `break!`s on a level name it doesn't know. The traffic code checks that it exists everywhere but in the guards' post: a one-line vanilla edit in `guard.gc` adds the check (marked `og:jak2-haven-city added`) |
| Attack controller | A guard or a citizen takes an attacker from `*cty-attack-controller*` when it spawns. `crimson-guard` only checks that the controller is nonzero: with `#f` the first guard crashes the game. havenj2 allocates it like Jak 3's city does |
| Density | Jak 2's numbers, by Jak 3 type (`*havenj2-traffic-want-counts*`): 15 male, 15 female and 14 fat citizens, 9 guards, 8 of each hover bike and 7 of each car. Set before `restore-default-settings`, which derives the target and reserve counts from them. A type's `want-count` is an `int8`, at most 20 |
| Switch | Mods menu, City traffic (`*mod-jak2-haven-city-traffic*`, on by default): starts or stops it at once |
| Sounds | The vehicles', citizens' and guards' sound effects are in Jak 3's city half banks, which Jak 3's city loads through its borrow manager; havenj2 doesn't load them, so these effects are silent. Speech plays |

## 8. Moods, time of day and weather

### 8.1 Moods

Each level's mood (GAME) follows its Jak 2 mood. `update-mood-havenj2` follows Jak 2's
`update-mood-ctysluma` (palettes 5 street lights, 6 flames, 7 neon signs). The places follow
`palshaft`, `palroof`, `palcab`, `consite`, `consiteb`, `ruins` (Dead Town and the Sage's hut),
`atoll`, `atollext`, `mountain`, `forest`, `caspad`, `dig1` (red fog and lights), `forresca` and
`forrescb` (the fortress's light groups, flickering palettes) and `stadiumb` (the race track's
lights and force field); interiors use fixed palette weights. The dig's
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

## 9. Travelling

### 9.1 Mods menu

L3 + SELECT opens the Mods menu (retail and debug boots); the mod's entries are under
jak2-haven-city. Every warp goes through a continue point, never through `bg`: havenj2 needs a
`large` memory bank, never free while Jak 3's own city is loaded, and a continue point makes the
level system unload every level it doesn't want before loading the new ones.

| Entry | Contents |
|---|---|
| Warp to Haven City (Jak 2) | `havenj2-start` (Jak 2's `ctysluma-start`, in the slums near the hideout) |
| Warp to a district | Slums (the hideout, the fortress, the Oracle), Port, Bazaar (Brutter's stall, the east side), Industrial Section (Vin's side, the south side), Main Town (west side, cable pillar, east side), Gardens (mountain airlock, north side), Palace plaza, Stadium grounds: one of Jak 2's continues in each |
| Warp to a key place | In the city: construction site gate, in front of the palace, Mar's tomb, pillar to the palace (cable), Hip Hog saloon, gun course, air train (port), Vin's power station, the fortress. In their own level: underground hideout, palace roof, the Oracle, Keira's garage |
| Warp outside the city | Dead Town, Dead Town: the Sage's hut, inside the fortress, stadium race track, construction site, pumping station, mountain top, Haven Forest, castle pad, dig site |
| Warp to the Freedom HQ (Jak 3) | `freehq-start`, in the room where the time gate stands |
| Time of day | [8.2](#82-time-of-day) |
| Weather (whole game) | [8.3](#83-weather) |
| City traffic | [7.2](#72-traffic) |

The cable pillar's continue (`hj2-cable-pillar`) is one Jak 2 doesn't have (`EXTRA_CONTINUES`): 8 m
in front of the door, facing it, the camera behind Jak.

### 9.2 Time gates

Two teleporters link the worlds, both Jak 3's warp gate (its model, its particles and sound, its
conditions and Jak's jump into it, `target-warp-out`) as `hj2-time-gate` (GAME), with a prompt
naming the world they lead to:

| Gate | Stands | Prompt | Jak arrives |
|---|---|---|---|
| Freedom HQ (Jak 3) | on the free floor at the back of the main room (710, 80.34, −565 m, found on the HQ's collision dump) | Press triangle to travel through the time (Jak 2) | jumping out of the hideout's gate (`hj2-hideout-gate`) |
| Underground hideout (Jak 2) | in the free corner of the main room (`TIME_GATES`) | Press triangle to travel through the time (Jak 3) | standing in front of the Freedom HQ's gate (`hj2-freehq-gate`) |

How each part is made:

1. **The model in a vanilla level.** `freehq` is one of Jak 3's levels and doesn't ship the warp
   gate. Two vanilla edits bring it: `warp-gate-ag.go` in `goal_src/jak3/dgos/freehq.gd` (the art
   group, for the game), and `extra_art_groups_by_dgo` in `jak3_config.jsonc` (its geometry, baked
   into freehq's `.fr3` for the PC renderer: re-extract FREEHQ, [3](#3-rebuilding-it-step-by-step)).
2. **Spawning without an entity.** `freehq` has no level callbacks: GAME adds two to its
   level-load-info when it loads (slot 35 spawns the gate, slot 36 kills it), without editing
   `level-info.gc`. The gate is spawned into `*entity-pool*`, whose processes belong to the
   default level: `hj2-time-gate-init` sets the process's level to `freehq` before the skeleton is
   made, because a process looks its art up only in its own level. The gate only spawns when the
   model is in freehq's art (`hj2-level-has-art?`).
3. **The hideout's gate** is an actor of `hj2-hide`, written by the generator (`TIME_GATES`) with
   its `on-notice` (the destination) and `travel-name` lumps.
4. **The arrival points** (`GATE_CONTINUES`) stand 6 m in front of each gate, facing away from it,
   the camera behind. The hideout's has the `warp-gate` flag: Jak 3 then looks for the closest warp
   gate entity and plays Jak's jump out of it. The Freedom HQ's gate has no entity, so Jak just
   stands there; that continue is appended to freehq's continue list by GAME.

### 9.3 Respawn points

Jak 3 only picks the closest continue point when Jak enters a different level, and never one
flagged `no-auto`; havenj2 is one level for the whole city, and some places have only `no-auto`
continues (the palace roof). A process (`havenj2-continues-code`, GAME) runs while any of the mod's
levels is active and moves the current continue every frame:

- to the closest of Jak 2's continues of the level Jak is in (`no-auto` ones too), or of any
  active level of the mod when that level has none;
- never to an arrival through a gate (`warp-gate` flag) or a `change-continue` one.

Dying or saving respawns Jak near where he was, at one of Jak 2's own respawn points. Every place
keeps all of Jak 2's continues but the title, intro, demo and cutscene ones, with Jak 2's level
lists translated and Jak 2's `no-auto`, `warp-gate` and `no-blackout` flags (`KEPT_CONTINUE_FLAGS`).

The same process also puts the ocean of the level Jak is in first ([5.4](#54-water-and-ocean)).

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
| Particle flags | Same names in both games, but Jak 3's launcher reads some meanings at other bits (the particles' level index takes bits 9 to 12): Jak 2's 12 (time of day tint on relaunch), 16 (acceleration kept in world space), 20 (cone follows the launcher's yaw) and 21 (launch and cone scaled by the launcher's matrix) are Jak 3's 13, 17, 19 and 20 | `CPUINFO_FLAGS` in `gen_havenj2_particles.py` |
| Particle groups | Jak 3's `defpartgroup` doesn't define the group's name; the known names are constants in `part-groups.gc`. A new group is reached by id in `*part-group-id-table*` | The groups code uses: the speakers' hologram, the crops' bursts (`*hj2-*-group-ids*`) |
| Particle callbacks | A `:func` gets the particle's sprite data (`sprite-vec-data-2d`, or a vector); Jak 2's decompiled callbacks type it as a matrix, same layout (row 0 x y z sx, row 1 flag matrix rot sy) | Copied callbacks ([5.3](#53-particles-and-sprite-textures)) |
| Texture pool slots | The PC pool gives each page of Jak 3's directory as many slots as it has textures: page ids Jak 3 never uses share their first slot, and spill over the next pages' | Sprite page ids ([5.3](#53-particles-and-sprite-textures)) |
| Animated textures | Background draws name an animated texture slot of their game's slot table (`common/texture/texture_slots.cpp`), not a texture | Jak 2's waterfalls and lava ([4.2](#42-level-builder)) |
| Ocean map | Jak 3's `ocean-map` has no `ocean-spheres`; the map drawn is the first displayed level's, in draw order | [5.4](#54-water-and-ocean) |
| Airlock scripts at load | A door born closed (at level load) with Jak on its front side runs its `on-deactivate`, however far Jak is: the side is an infinite plane (`com-airlock-method-26`) | The palace elevator ([6.3](#63-doors-and-elevators)) |
| Continue auto-pick | Jak 3 picks a continue only when Jak enters a level, never a `no-auto` or `change-continue` one | Respawn process ([9.3](#93-respawn-points)) |
| Warp gate arrival | A continue with the `warp-gate` flag makes Jak jump out of the closest `warp-gate` entity (subtypes too); with none found, Jak just stands there | Time gates ([9.2](#92-time-gates)) |
| Processes without an entity | A process spawned into `*entity-pool*` belongs to the default level: set its `level` before `initialize-skeleton` | The Freedom HQ's gate |
| A model in a vanilla level | The art group's `.go` in the level's `.gd`, and its geometry baked into the level's `.fr3` by the decompiler (`extra_art_groups_by_dgo`) | `freehq` |
| Save header | `info-int32 4` of a save is unused; the save screen reads it back as `blind-data 4` of the slot's preview | [9.4](#94-saves) |
| Custom level names | At most 10 characters (level builder assert) | `hj2-sage`, `hj2-forta`, `hj2-fortb` |
| Process init | `process-spawn` without `:init` calls `<type>-init-by-other` | The time gate (`:init hj2-time-gate-init`) |
| Level callbacks | A level-load-info's `callback-list` holds (slot . function) pairs: 33 login, 34 logout, 35 activate, 36 deactivate. They can be added at runtime to one of Jak 3's own levels | Mod levels; `freehq` |
| Art lookup | A process looks its art up only in its own level | Each level lists the art groups of the doors and scenes it holds |
| Level heap | 18 chunks: `large` 12, `small-edge` 6 at either end, `small-center` the middle 6 | [6.2](#62-the-levels-and-their-memory) |
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
| build-actor | Plays animations at 60 fps; its collide joint id is unused at runtime (the GOAL prim's transform index, joint + 1, picks the joint) | Palace gate frames, joint-bound collision |
| Never-spawned actors | Jak 2's `kill-mask` task bit `never` keeps an actor unborn, but the entity dumps list it | `jak2_actors.py` |
| Actor scale | Jak 2 ignores the actor scale lump | Props |

## 11. Memory and performance

| Item | Size |
|---|---|
| `havenj2` bsp (collision and navigation data included) | 15.2 MB in the level heap |
| HJ2 DGO (bsp, traffic code and art included) | 19.6 MB |
| `havenj2.fr3` uncompressed | 285 MB |
| TIE after unpack | 21.6 M vertices, about 660 MB of GPU vertex data |
| Collision | 502 k triangles |
| Places | 13 KB (`hj2-atollx`) to 5.1 MB (`hj2-atoll`) |

This is roughly five times what Jak 2 keeps loaded in the city at once, so expect a lower frame
rate than in a stock city.

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
- **Check the generated files are up to date:** rerun the generators; if no file changes, the
  committed outputs match them.
- **Game log:** `log/jak3.<date>.log` records level loads and the levels Jak enters.
- **Silent crashes:** when the game is launched through `task`, a crash leaves no Windows error
  report and `task` prints only the low byte of the exit code: `exit status 5` is `0xC0000005`
  (access violation), `exit status 9` is `0xC0000409` (`abort`).
- **`(mi)` crashes after many levels:** each level with `art_groups` loads Jak 3's 274 DGOs again.
  After about ten in one run `goalc` can die (segmentation fault) with a level's `.go` written but
  not its `.fr3`: touch that level's `.jsonc` and run `(mi)` again.
- **Do not use `bg` from inside Jak 3's city:** it allocates the `large` bank while `ctywide`,
  `citycast` and `ctyport` are still loaded and hits `could not find free large bank` followed by a
  `break!`.
- **Find where the game crashes:** start the game (`task boot-game`), then `task repl`, `(lt)` and
  `(dbgc)` (attach the debugger and continue). After the crash, `(:di "log/crash.txt")` prints the
  registers and the stack. Without debug info (code not compiled in that `goalc` session) the stack
  is raw: the values equal to the EE base plus an offset are return addresses. `rip` equal to `r15`
  (the EE base) is a call through a null function pointer, often a method called on `#f`.
  `(:disasm <address> <size>)`, while the game is still halted, names the object and the offset of
  an address and disassembles it with symbol names.

## 13. Change history

Phase 1 is commit `de9ec6962`; phases 2 to 10 are commit `dd14a7829`; phase 11 is the commit that
adds its row. Phases 1 to 10 were played in game before the next one started; phase 11 is built
(`(mi)`, `fr3_check` and the texture pool check clean) but not played yet.

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

## 14. Not done yet

- **Not played in game yet (phase 11):** everything in its row of [13](#13-change-history).
- **Haven Forest's dark lake:** the forest's water is Jak 2's sea, drawn from the city's ocean map
  (its mask covers the lake, its height is 0 m like Jak 2's). Phase 10 had that map set and the
  lake still wasn't seen; the cause isn't found. Phase 11 adds the ocean order
  ([5.4](#54-water-and-ocean)), which fixes one possible cause (another level's map drawn first).
  To look in game, standing at the lake, in the REPL: `(= *ocean-map* *ocean-map-havenj2*)` should
  be `#t`.
- **Places not ported** (their doors stay shut): Mar's tomb, the canyon, the inside of the palace,
  the sewers, the underport, the fortress's dump and prison, Onin's tent, the kiosk.
- **Particles** of the other places (only the city, the forest and Dead Town have theirs): the
  construction site (135 spawners), the pumping station (197), the mountain (255), the dig (241),
  the palace roof, pillar and cable (545), the fortress (338), the stadium's race track (121), the
  interiors. Each is a `PLACE_PARTICLES` entry, with a texture page whose pool slots don't meet
  another loaded level's ([5.3](#53-particles-and-sprite-textures)).
- **Animated textures:** Jak 2's waterfalls and lava are still ([4.2](#42-level-builder)).
- **Dead Town:** its enemies, the walls and pillars the titan suit breaks, the push blocks.
- **The fortress:** its enemies, turrets and electric gates. **The stadium:** its races.
- **The construction site:** the Baron's fight (its breaking scaffolds, the bomb).
- **The farm:** the sprinklers' water.
- **The mountain:** its pools (`water-anim`), its enemies.
- **The dig:** its enemies, spiky spheres, stomp blocks and precursor orbs. Its fixed cameras and
  the castle pad's: Jak 2's `caspad`, `dig3a` and `dig3b` were extracted before the camera export
  existed (a new Jak 2 extraction of these levels adds them; their camera regions are dropped
  meanwhile).
- **Traffic:** the vehicles', citizens' and guards' sound effects ([7.2](#72-traffic)), Jak 2's
  citizen and guard models, the KG and Metal Head squads.
- **Sounds and voices:** the Baron's speeches, Jak 2's object sounds.
- **The save slot's picture** is Jak 3's choice ([9.4](#94-saves)).
