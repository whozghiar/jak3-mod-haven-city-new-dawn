# level_port

Turns levels of one Jak game into custom levels of another, from the source game's extracted data:
background and collision, actors, doors and elevators with their level loading scripts, regions,
fixed cameras, particles, traffic navigation, models rebuilt for `build-actor`, continue points and
level-load-infos. A mod describes its port in a manifest; the tool writes every level file from it.

What it knows today: **Jak 2 → Jak 3** (the `jak3/features/jak2-haven-city` mod,
`custom_assets/jak3/ports/jak2-haven-city/port.jsonc`). The code is split so that another source
game, target game or game pair is added next to the existing ones (see
[Adding a game](#adding-a-game-or-a-game-pair)).

## Running it

From the repository root:

```bash
python scripts/level_port custom_assets/jak3/ports/jak2-haven-city/port.jsonc
python scripts/level_port <manifest> --steps levels      # only some steps
```

It needs:

- the source game extracted (`task extract`), with `rip_levels` on in its decompiler config (the
  model rips of `decompiler_out/<game>/levels/`),
- the target game extracted (some textures and art come from it),
- `fr3_check` built (`cmake --build out/build/Release --target fr3_check`): the particle step lists
  the textures of `.fr3` files with it,
- the C++ side: the decompiler's exports (fixed cameras, navigation data, TIE collision tags) and the
  level builder's keys the generated `.jsonc` files use (`import_fr3`, `nav_data`, `cameras`,
  `region_tree_files`, `sprite_textures`, `pair` and `string` lumps). Today they exist for Jak 3's
  level builder only (`goalc/build_level/jak3`).

Then `(mi)` in `goalc` builds the levels. A generated file is only rewritten when its content
changes, so `goalc` only rebuilds the levels that changed.

## What it writes

| Step | Writes |
|---|---|
| `mesh` | `<level>-mesh.glb`: the source props kept as background, and the pool surfaces (`mesh`, `water`) |
| `ocean` | `<level>-ocean.gc`: a level's own ocean map, copied from the source game (`ocean_source`) |
| `nav` | `<level>-nav.json`: the traffic navigation data merged for the level (`nav`), and its height map |
| `levels` | Each level's `.jsonc` and `.gd`, its regions and water regions (`<level>-water-regions.json`), its particles (`<level>-part.gc`), the models its actors use (`<model>.glb`), the level-load-infos and continue points (`level_info`), and the levels' `goalc` build steps (`build`) |

Every generated file says so in its first lines. A fix goes into the manifest or the tool, never
into a generated file.

## How it is made

```text
scripts/level_port/
  __main__.py            the command
  manifest.py            reads a port manifest
  common/                what doesn't depend on a game: glTF (reading rips, rebuilding models for
                         build-actor), geometry, convex hulls, the GOAL reader, relocatable data
                         blobs, writing generated files
  games/<game>.py        what the tool knows of a game: as a source, where its extraction is and how
                         to read it (its story, level list, continue points, regions, cameras); as a
                         target, its level heap and the GOAL text of its level-load-infos
  convert/scripts.py     the translator of entity and region scripts (want-load, want-display...)
  convert/<a>_<b>.py     what changes between two games: door classes, pickup ids, particle flag
                         names and callbacks, continue flags, ocean maps...
  steps/                 the steps, run in order: mesh, ocean, nav, levels (which runs
                         props.py, particles.py and water.py for the levels)
```

The data of a mod (its level names and ids, the doors it keeps, its own classes, its models...) is
only in its manifest. The steps' docstrings describe their manifest blocks in detail.

## The manifest

A `.jsonc` file (JSON with comments), `custom_assets/<target>/ports/<port>/port.jsonc`; the files it
names (`callbacks_file`) are in the same folder. Top-level keys:

| Key | Meaning |
|---|---|
| `name`, `source_game`, `target_game` | The port, and the games (`games/<game>.py`, `convert/<source>_<target>.py`) |
| `tag`, `prefix` | The mark of the mod's generated files (`og:<mod>`), and the prefix of what the port names: continues, particle groups and callbacks. The mod's GAME code defines `<prefix>sprite-page-new` and `<prefix>sprite-page-register` for the particles' texture pages |
| `paths` | `levels` (custom levels), `models` (build-actor models), `code` (the levels' GOAL code) |
| `story` | The source game's story state the levels are ported in: `state` (`end`: every task done) and `open_tasks` |
| `build` | The `goalc` build steps file (`file`), loaded by the target game's `game.gp`, and the dependencies of the level code (`default_deps`, `code_deps`) |
| `level_info` | The GOAL file of the level-load-infos (`file`), its `comment`, `levels_var`: a list of every level of the port, and `hubs_var`: the list of `(level . hub)` pairs (each with a `..._comment`) |
| `level_defaults` | The `level_info` of a level unless it says otherwise (`callbacks`, `draw_priority`, `mood`: `update-mood-{name}` by default) |
| `level_templates` | Named sets of level keys: a level with `template` takes the keys of that set it doesn't set itself (the districts of a city) |
| `ocean_map` | The ocean map of the levels whose `ocean` is `true` |
| `levels` | The levels, below |
| `particles` | For every level: `copied_callbacks`, `level_callbacks`, `reserved` ids ([steps/particles.py](steps/particles.py)) |
| `doors`, `closed_doors` | Source doors and elevators placed, as `[source level, name]`; the closed ones never open |
| `etypes`, `elevator_etypes`, `elevators` | The mod's classes for source doors (added to the pair's `DOOR_ETYPES`); the source classes that are elevators; elevators stopping at every point of their path |
| `renames`, `drop_events` | Events sent by name to renamed entities; events to remove |
| `script_overrides`, `next_actor_overrides` | Per source level and name: scripts replaced (`null` removes one); a door's pair |
| `backdrop_levels` | Source levels that are only a backdrop: a door waiting for them doesn't need them |
| `art_groups` | The target game art group of the mod's classes (the pair's `ART_GROUPS` and the classes with a model need none) |
| `named_actors`, `named_etypes` | Source actors placed by name, and their classes and lumps (`path`, `float`, `int32`, `uint32`, `vector`, `string`, `symbol`, `type`) |
| `teleporters`, `new_teleporters` | A source actor replaced by a teleporter class; a teleporter at a position. Their `dest` is a continue |
| `ported_levels`, `ported_etypes`, `ported_everywhere` | Source actors placed by class: in these source levels, or everywhere. Crates always are (the pair's `CRATES`). A placed class's `art_groups` entry goes into the level's DGO |
| `models` | Models rebuilt from source rips for `build-actor`, by the class using them: `rip`, `prims`, `collide`, `anims`, `extras` ([common/glb.py](common/glb.py) `rebuild_model`) |
| `region_id_offset`, `region_open_tasks`, `region_script_overrides` | Our region ids; per source region, tasks taken as open, scripts replaced |
| `continues` | Our continue names (`prefix`, `names`), the source continues `kept` anyway, level lists (`wants`), and continues added: in front of a door (`door_continues`), at a position in a source level (`new_continues`), in a target game level (`target_continues`) |

A level:

| Key | Meaning |
|---|---|
| `name`, `nick`, `iso`, `index`, `base_id` | The level's name (10 characters at most), nickname (its DGO is `<NICK>.DGO`), ISO name, level index (a string, `"0x12A"`), first actor and region id |
| `what` | What it is, for the comments |
| `sources` | The source levels merged into it: its own, then the others |
| `template` | The `level_templates` set it takes its other keys from |
| `hub` | The level it is always loaded after (a city district and its city-wide level, holding their shared code, traffic and navigation): every translated level list naming it gets the hub, first, hidden when the source game didn't show it. The generation fails if a set of levels loads it without its hub |
| `level_flags` | Level flags added to its level-load-info (`not-physical`, `display-wait`...) |
| `memory` | A fixed level-memory-mode; else the source's, changed only where a set of levels loaded together doesn't fit the target's level heap |
| `sky`, `ocean`, `ocean_source` | Its sky (and weather), its ocean map (`true`: `ocean_map`), where its own map comes from |
| `collision_bounds` | `[xmin, ymin, zmin, xmax, ymax, zmax]` meters: the imported collision kept |
| `ported_actors` | `false`: none of the `ported_*` actors (the default is `true`) |
| `particles` (on a level) | [steps/particles.py](steps/particles.py): `"page"`, `"parts"`, `"groups"` can be `"auto"` (a free texture page and ids, chosen by the step), `skip_groups` (source groups whose spawners aren't placed), `levels` |
| `continues` | Its continues, as source names; without it, all its source levels' but the title, intro, demo and cutscene ones |
| `code`, `models` | Objects of its DGO after the art groups; models built for it besides its actors' |
| `level_info` | Its level-load-info: `callbacks`, `draw_priority`, `part_engine_max`, `comment`, `mood` |
| `water`, `mesh`, `ocean_source`, `nav` | [steps/water.py](steps/water.py), [steps/mesh.py](steps/mesh.py), [steps/ocean.py](steps/ocean.py), [steps/nav.py](steps/nav.py) (`nav.sources`: the source levels whose navigation it holds; one is kept as it is, several are merged; none: only the height map) |
| `traffic` | The target game's traffic code taken from one of its DGOs (`code_from`, `skip`, `replace`), the level's own (`code`), the traffic's art groups (`art`) |
| `props`, `custom_props` | [steps/props.py](steps/props.py) |
| `particles` | [steps/particles.py](steps/particles.py) (`particles.levels`: the part spawners of other levels' sources go to those levels) |

## Adding a game or a game pair

- **A source game**: `games/<game>.py` with what `games/jak2.py` gives: `NAME`, `TITLE`, `METER`,
  the extraction paths (`ENTITIES`, `RIPS`), `SUN_DIRECTIONS`, a `Story` class (`closed`,
  `level_actors`, `all_actors`, `hidden_prototypes`), `level_names`, `memory_modes`, `continues`,
  `regions`, `cameras`. The decompiler must export the data the steps read for that game.
- **A target game**: `games/<game>.py` with what `games/jak3.py` gives: its level heap (`CHUNKS`,
  `CHUNK_COUNT`, `MEMORY_ORDER`, `fits`), `continue_point` and `level_load_info`. Its level builder
  (`goalc/build_level/<game>`) must have the keys the generated `.jsonc` files use.
- **A game pair**: `convert/<source>_<target>.py` with the tables of `convert/jak2_jak3.py`.

Not everything carries over as it is. Jak 1 has no entity or region loading scripts (it loads its
levels by load boundaries), no traffic data, other continue points and actor lumps: a Jak 1 source
needs its own reader of those, and the `levels` step's doors and continues their Jak 1 counterparts.
Jak 1 and Jak 2 as targets need the level builder's import features in their own
`goalc/build_level/jak1` and `jak2`.

## Checking a change

The generated files are committed. After a change of the tool, run it and look at `git diff`: a
change that only reorganizes the code must leave them as they were (the tool's own comments aside).
