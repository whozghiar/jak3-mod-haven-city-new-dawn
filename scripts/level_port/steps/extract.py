"""The games' extractions the port reads, checked first and made when missing.

A mod made with the port commits its manifest and its own code, never what the port makes from the
games' files (the generated files are kept out of git, see __main__.py). Its setup is this tool's
full run on the player's own extractions: this step checks them and runs the decompiler for what is
missing.

  - the source game: each level's entity dumps and background (<level>-actors.json, <level>.fr3)
    and the model rips the manifest uses (rip_levels). With no rip at all, the whole game is
    extracted with its rips (once, long: Jak 2's take 11 GB); else only the DGOs of the levels
    whose files are missing, or older than a texture replacement of the source or target game
    (custom_assets/<game>/texture_replacements: the decompiler applies the source game's, then
    the target game's, passed as its extra_texture_replacement_dirs): editing one re-extracts the
    levels and rips the port reads, once. A texture pack of the target game thus also retextures
    what the port takes from the source game;
  - the target game: its backgrounds (the particles' textures, the levels the build borrows from),
    with the models its decompiler config bakes into its levels (extra_art_groups_by_dgo): a level
    whose .fr3 lacks one is extracted again. out/<game> is shared by every worktree of the
    repository, so an extraction made with another config (master-dev's, another mod's) rewrites
    the .fr3 without them.

The games' disc files must be in iso_data/<game> (copied from the disc, like for `task extract`).
The decompiler runs with its config's default version (ntsc_v1): the one the level port's paths
follow (decompiler_out/<game>, out/<game>/fr3).

At a mod's install (the port run by a mod release's extractor, __main__.py --extractor), that
extractor extracts instead of the decompiler: from the discs --iso gives (the player's launcher
install), with the disc's own version (its buildinfo.json), into the root (the mod's data/ folder).
It extracts only the source game's DGOs the port reads, never the whole game.
"""

import importlib
import json
import os
import subprocess
import sys

from ..common.files import read_jsonc

EXE = ".exe" if os.name == "nt" else ""
DECOMPILER = f"out/build/Release/bin/decompiler{EXE}"
FR3_CHECK = f"out/build/Release/bin/fr3_check{EXE}"
# a mod release's extractor (__main__.py --extractor), extracting in the decompiler's place
EXTRACTOR = None
VERSION = "ntsc_v1"


def fail(lines):
    print("\n".join(["", "The level port can't run yet:"] + [f"  - {x}" for x in lines]))
    sys.exit(1)


def decompile(game, overrides):
    """Run the decompiler on iso_data/<game> with these config overrides (or the extractor on the
    game's disc, writing into the root, when there is one: EXTRACTOR)."""
    if EXTRACTOR:
        iso = importlib.import_module(f"level_port.games.{game}").ISO
        cmd = [EXTRACTOR, os.path.abspath(iso), "--folder", "--decompile", "--game", game,
               "--proj-path", os.getcwd(), "--decomp-config-override", json.dumps(overrides)]
        print("  running: " + " ".join(cmd))
        subprocess.run(cmd, check=True)
        return
    # an absolute path: Windows' CreateProcess doesn't find a relative one with "/" separators
    cmd = [os.path.abspath(DECOMPILER), f"./decompiler/config/{game}/{game}_config.jsonc",
           "./iso_data", "./decompiler_out", "--version", VERSION, "--config-override",
           json.dumps(overrides)]
    print("  running: " + " ".join(cmd))
    subprocess.run(cmd, check=True)


def newest_replacement(game):
    """The modification time of the game's newest texture replacement PNG, 0 with none."""
    root = f"custom_assets/{game}/texture_replacements"
    return max((os.path.getmtime(os.path.join(d, f)) for d, _, fs in os.walk(root)
                for f in fs if f.lower().endswith(".png")), default=0)


def manifest_levels(port):
    """Every source level the manifest names anywhere (the particles' "textures_from",
    "backdrop_levels", the rips' folders...): a string, key or value, that is one, or a path that
    starts with one, and whose DGO is on the source game's disc (Jak 2's level-info names levels it
    doesn't ship, like Jak 3's wasall). A few may be the target game's levels of the same name:
    extracted for nothing."""
    src = port.source
    names = {lv for lv in src.level_names() if os.path.exists(f"{src.ISO}/DGO/{src.dgo_of(lv)}")}
    found = set()

    def walk(x):
        if isinstance(x, dict):
            x = [*x, *x.values()]
        if isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, str) and x.split("/")[0] in names:
            found.add(x.split("/")[0])

    walk(port.data)
    return found


def source_needs(port):
    """The source game's files the port reads: source level -> its files missing or older than
    the newest texture replacement of the source or target game (to extract again)."""
    src = port.source
    newest = max(newest_replacement(src.NAME), newest_replacement(port.target.NAME))

    def stale(path):
        return not os.path.exists(path) or os.path.getmtime(path) < newest

    levels = {s for lv in port.levels for s in lv.sources} | set(port.get("ported_levels", []))
    levels |= manifest_levels(port)
    missing = {}
    for lv in sorted(levels):
        for path in (f"{src.ENTITIES}/{lv}-actors.json", f"{src.FR3}/{lv}.fr3"):
            if stale(path):
                missing.setdefault(lv, []).append(path)
    # the models and their extra models (a lamp's cone of light...)
    for model in [m for top in port.get("models", {}).values()
                  for m in [top] + top.get("extras", [])]:
        if "rip" in model and stale(port.rip(model["rip"])):
            missing.setdefault(model["rip"].split("/")[0], []).append(port.rip(model["rip"]))
    return missing


def missing_baked_models(game):
    """The game's DGOs whose .fr3 lacks a model its decompiler config bakes into it
    (extra_art_groups_by_dgo, entries "<art-group>[:<HOME.DGO>]", the model "<art group>-lod0")."""
    config = read_jsonc(f"decompiler/config/{game.NAME}/{game.NAME}_config.jsonc")
    stale = []
    for dgo, entries in sorted(config.get("extra_art_groups_by_dgo", {}).items()):
        fr3 = f"{game.FR3}/{dgo[:-4].lower()}.fr3"
        models = set()
        if os.path.exists(fr3):
            out = subprocess.run([os.path.abspath(FR3_CHECK), fr3, "--models", "-lod0"],
                                 capture_output=True, text=True)
            if out.returncode:
                fail([f"{FR3_CHECK} has no --models (rebuild it: cmake --build out/build/Release "
                      f"--target fr3_check --config Release)"])
            models = set(out.stdout.split())
        if any(e.split(":")[0].removesuffix("-ag") + "-lod0" not in models for e in entries):
            stale.append(dgo)
    return stale


def run(port):
    src, dst = port.source, port.target
    problems = [f"no {tool} (build it: {how})" for tool, how in (
        (EXTRACTOR or DECOMPILER, "task build-release-decomp"),
        (FR3_CHECK, "cmake --build out/build/Release --target fr3_check --config Release"))
        if not os.path.exists(tool)]
    for game in (src, dst):
        if not os.path.isdir(game.ISO):
            problems.append(f"no {game.ISO}: copy {game.TITLE}'s disc files there (the folder "
                            f"`task extract` reads)")
    if problems:
        fail(problems)

    # the source game: everything with its rips when nothing was ripped, else the missing DGOs
    missing = source_needs(port)
    if missing:
        # (never with the extractor: the player's install extracts only what the port reads)
        whole = not EXTRACTOR and (not os.path.isdir(src.RIPS) or not os.listdir(src.RIPS))
        # the target game's texture pack too, after the source game's own (first match wins)
        overrides = {"decompile_code": False, "levels_extract": True, "allowed_objects": [],
                     "rip_levels": True, "extra_texture_replacement_dirs":
                     [f"custom_assets/{dst.NAME}/texture_replacements"]}
        if whole:
            print(f"  {src.TITLE} isn't extracted with its model rips: extracting it all")
        else:
            dgos = sorted({src.dgo_of(lv) for lv in missing})
            print(f"  {src.TITLE}: {len(missing)} levels to extract again (missing files or new "
                  f"texture replacements: {', '.join(dgos)}); then build with "
                  f"(make-group \"iso\" :force #t)")
            overrides["levels_to_extract"] = dgos
        decompile(src.NAME, overrides)
        still = source_needs(port)
        if still:
            fail([f"{src.TITLE}'s extraction has no {p}" for ps in still.values() for p in ps])
    print(f"  {src.TITLE}: extracted")

    # the target game: its backgrounds, then the levels missing a model its config bakes in
    if not os.path.isdir(dst.FR3) or not any(f.endswith(".fr3") for f in os.listdir(dst.FR3)):
        print(f"  {dst.TITLE} isn't extracted: extracting it")
        decompile(dst.NAME, {"decompile_code": False, "levels_extract": True,
                             "allowed_objects": []})
    stale = missing_baked_models(dst)
    if stale:
        print(f"  {dst.TITLE}: {', '.join(stale)} lack the models extra_art_groups_by_dgo bakes "
              f"in (extracted with another config): extracting them again")
        decompile(dst.NAME, {"decompile_code": False, "levels_extract": True,
                             "allowed_objects": [], "levels_to_extract": stale})
        if missing_baked_models(dst):
            fail([f"{dst.TITLE}'s extraction of {', '.join(stale)} still lacks its "
                  f"extra_art_groups_by_dgo models (see the decompiler's warnings)"])
    print(f"  {dst.TITLE}: extracted")
