"""The games' extractions the port reads, checked first and made when missing.

A mod made with the port commits its manifest and its own code, never what the port makes from the
games' files (the generated files are kept out of git, see __main__.py). Its setup is this tool's
full run on the player's own extractions: this step checks them and runs the decompiler for what is
missing.

  - the source game: each level's entity dumps and background (<level>-actors.json, <level>.fr3)
    and the model rips the manifest uses (rip_levels). With no rip at all, the whole game is
    extracted with its rips (once, long: Jak 2's take 11 GB); else only the DGOs of the levels
    whose files are missing, or older than a texture replacement of the source game
    (custom_assets/<game>/texture_replacements, which the decompiler applies when it extracts):
    editing one re-extracts the levels and rips the port reads, once;
  - the target game: its backgrounds (the particles' textures, the levels the build borrows from).

The games' disc files must be in iso_data/<game> (copied from the disc, like for `task extract`).
The decompiler runs with its config's default version (ntsc_v1): the one the level port's paths
follow (decompiler_out/<game>, out/<game>/fr3).
"""

import json
import os
import subprocess
import sys

EXE = ".exe" if os.name == "nt" else ""
DECOMPILER = f"out/build/Release/bin/decompiler{EXE}"
FR3_CHECK = f"out/build/Release/bin/fr3_check{EXE}"
VERSION = "ntsc_v1"


def fail(lines):
    print("\n".join(["", "The level port can't run yet:"] + [f"  - {x}" for x in lines]))
    sys.exit(1)


def decompile(game, overrides):
    """Run the decompiler on iso_data/<game> with these config overrides."""
    cmd = [DECOMPILER, f"./decompiler/config/{game}/{game}_config.jsonc", "./iso_data",
           "./decompiler_out", "--version", VERSION, "--config-override", json.dumps(overrides)]
    print("  running: " + " ".join(cmd))
    subprocess.run(cmd, check=True)


def newest_replacement(game):
    """The modification time of the game's newest texture replacement PNG, 0 with none."""
    root = f"custom_assets/{game}/texture_replacements"
    return max((os.path.getmtime(os.path.join(d, f)) for d, _, fs in os.walk(root)
                for f in fs if f.lower().endswith(".png")), default=0)


def source_needs(port):
    """The source game's files the port reads: source level -> its files missing or older than
    the newest texture replacement (to extract again)."""
    src = port.source
    newest = newest_replacement(src.NAME)

    def stale(path):
        return not os.path.exists(path) or os.path.getmtime(path) < newest

    levels = {s for lv in port.levels for s in lv.sources} | set(port.get("ported_levels", []))
    missing = {}
    for lv in sorted(levels):
        for path in (f"{src.ENTITIES}/{lv}-actors.json", f"{src.FR3}/{lv}.fr3"):
            if stale(path):
                missing.setdefault(lv, []).append(path)
    for model in port.get("models", {}).values():
        if "rip" in model and stale(port.rip(model["rip"])):
            missing.setdefault(model["rip"].split("/")[0], []).append(port.rip(model["rip"]))
    return missing


def run(port):
    src, dst = port.source, port.target
    problems = [f"no {tool} (build it: {how})" for tool, how in (
        (DECOMPILER, "task build-release-decomp"),
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
        whole = not os.path.isdir(src.RIPS) or not os.listdir(src.RIPS)
        overrides = {"decompile_code": False, "levels_extract": True, "allowed_objects": [],
                     "rip_levels": True}
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

    # the target game: its backgrounds
    if not os.path.isdir(dst.FR3) or not any(f.endswith(".fr3") for f in os.listdir(dst.FR3)):
        print(f"  {dst.TITLE} isn't extracted: extracting it")
        decompile(dst.NAME, {"decompile_code": False, "levels_extract": True,
                             "allowed_objects": []})
    print(f"  {dst.TITLE}: extracted")
