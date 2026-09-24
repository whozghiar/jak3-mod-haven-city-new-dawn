# Jak 2 Haven City in Jak 3 — Technical README

This document covers how the `jak3/features/jak2-haven-city` branch rebuilds Jak 2's whole Haven
City as the Jak 3 custom level `havenj2`: the data pipeline, the level builder changes it needed,
the level's GOAL code, and how to debug it. Player-facing setup is in the root `README.md`.

## 1. Architecture

| Layer | Change |
|---|---|
| Level builder (`goalc/build_level`) | New `import_fr3` input merging existing `.fr3` files; Jak 3 bsp fixes for empty TIE/shrub trees, vis list, regions, large collide hashes |
| Tools | `tools/fr3_check.cpp`: offline validator for a generated `.fr3` |
| Level data | `custom_assets/jak3/levels/havenj2/` (`havenj2.jsonc`, `havenj2.gd`) |
| Level code (HJ2.DGO) | `goal_src/jak3/levels/havenj2/havenj2-obs.gc` (mood), `havenj2-ocean.gc` (ocean map) |
| Game code (GAME.CGO) | `level-info.gc` entry, `pc/features/jak2-haven-city-menu.gc` (Mods menu warp) |

Design decisions:

- **One monolithic level**, not 15. Jak 3's PC level heap is 15x the original on `master-dev`
  (`DEBUG_LEVEL_HEAP_MULT`), so a `large` level gets about 177 MB.
- **Merge `.fr3` render trees instead of re-baking glTF.** The Jak 2 extraction already contains
  tfrag, TIE and shrub trees with their time-of-day palettes, and a collision mesh with each
  triangle's `pat` value. Re-baking through Blender would lose the palettes and the instancing.
- **Jak 2 world coordinates are kept.** Jak 3's own city sits at the same place, so `havenj2` must
  never be loaded together with Jak 3's city levels.

## 2. Data pipeline

1. `task extract` for Jak 2 writes `out/jak2/fr3/<level>.fr3` for every city level.
2. `havenj2.jsonc` lists those levels under `import_fr3`. The builder
   (`goalc/build_level/common/fr3_import.cpp`) appends each level's trees and textures to the
   custom level's `.fr3`, deduplicating textures by tpage and name.
3. Only `normal`, `trans` and `water` tfrag trees are kept: the Jak 3 renderer has no lowres bucket.
4. Collision vertices keep their original `pat`: the `pat-surface` bit layout is identical in Jak 2
   and Jak 3. `collision_bounds` drops `ctywide`'s unreachable backdrop mountains (about 3000
   triangles up to 1500 m high), which otherwise inflate the collide hash grid.
5. The builder writes `out/jak3/obj/havenj2.go` (bsp) and `out/jak3/fr3/havenj2.fr3`, then
   `custom-level-cgo` packs `HJ2.DGO` with the level code first and the bsp last.

## 3. Builder changes and why

| Problem | Fix |
|---|---|
| Collide hash item array over 65535 entries (the game reads bucket indices as u16) | Main grid cell size grows by 25% until the array fits; fragments go straight into the cells their bbox overlaps |
| Triangles missing from collision fragments far from the origin | Fragment grid tests run relative to the fragment corner, with 1-unit padding |
| Crash on the first frame | `drawable-tree-instance-tie` was emitted with a length of 0; Jak 3's draw reads `data[length - 1]` and the proxy's `prototype-max-qwc`. Jak 3 now gets a tree with one empty instance array and a full-size proxy |
| Imported geometry culled | Imported trees keep their BVH vis ids, and a level without vis info copies `all-visible-list` into its vis bits each frame. The bsp now carries a 2048-byte all-visible list when `import_fr3` is used |
| Shrubs not drawn | Jak 3 bsp gets an empty `drawable-tree-instance-shrub` (length 1, info with an empty prototype array), which makes the game send the shrub bucket |
| Crash with a json without `region_trees` | `RegionArray` pointers were uninitialized; they now default to null |

The Jak 2 builder has the same empty-TIE-tree layout problem; it is left unchanged here.

## 4. Level code and settings

- **Mood:** `update-mood-havenj2` copies the exterior mood and drives Jak 2's city palettes: 5 street
  lights, 6 flames, 7 neon signs (Jak 3's `update-mood-ctywide` leaves palette 7 dark). It follows
  Jak 2's `update-mood-ctysluma`.
- **Weather:** Jak 2's range (clouds and fog both free between 0 and 1). Jak 3's city uses a minimum
  fog of 0.5, which keeps it overcast and often rainy.
- **Sky:** drawn only when an active level has the `sky` level flag.
- **Ocean:** `*ocean-map-havenj2*` is a generated copy of Jak 2's city ocean tables. Jak 3's own
  `*ocean-map-city*` describes Jak 3's reworked city.

## 5. Warping

The Mods menu button restarts play at the `havenj2-start` continue point. Loading through a continue
point makes `load-state` unload every level the continue doesn't want before adding a new one.

Do not use `bg` from inside Jak 3's city: it allocates the `large` bank while `ctywide`, `citycast`
and `ctyport` are still loaded and hits `could not find free large bank` followed by a `break!`.
Also, `bg` only loads the nickname DGO (`HJ2.DGO`) when given the vis name (`havenj2-vis`).

## 6. Memory and performance

| Item | Size |
|---|---|
| bsp (`havenj2.go`, collision included) | 12.8 MB in the level heap |
| `.fr3` uncompressed | 231 MB (75 MB compressed) |
| TIE after unpack | 21.1 M vertices, about 650 MB of GPU vertex data |
| Collision | 475 k triangles |

This is roughly five times what Jak 2 keeps loaded in the city at once, so expect a lower frame
rate than in a stock city.

## 7. Debugging

- **Validate a generated `.fr3` offline:** build the `fr3_check` target and run it on
  `out/jak3/fr3/havenj2.fr3`. It reloads the file like the game's loader, checks the references
  the renderer follows without bounds checks, and runs the same unpack step.
- **Rebuild the level without the REPL:** build the `build_level` target and run it with
  `-g jak3`, the level's `.jsonc`, the output bsp path and `--fr3`.
- **Silent crashes:** when the game is launched through `task`, a crash leaves no Windows error
  report and `task` prints only the low byte of the exit code: `exit status 5` is `0xC0000005`
  (access violation), `exit status 9` is `0xC0000409` (`abort`). `gk` has no crash handler, so
  attach the goalc debugger before reproducing a crash.
- **`(mi)` does not rebuild the level** when only the builder changed: touch `havenj2.jsonc`.

## 8. Not done yet

- Jak 2 actors (4557 of 61 types: market props, farm plants, lamps, statues, doors, airlocks,
  palace fountains).
- Swimmable water: the ocean is drawn but has no water volume.
- Doors and elevators to interiors and other levels.
- Nav meshes and traffic.
