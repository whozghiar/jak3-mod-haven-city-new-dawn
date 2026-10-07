"""python scripts/level_port <port manifest> [--steps mesh,levels,...]

Runs the port's steps (see steps/__init__.py) from the repository root. Generated files are only
rewritten when their content changes, so goalc only rebuilds the levels that changed.

A mod release runs it too, as a one-file executable next to its extractor, which calls it before
its compile (decompiler/extractor/main.cpp, run_level_ports): --root is then the mod's data/
folder, --iso the games' extracted discs of the player's launcher install, and the extractor
itself extracts the source game's levels (see steps/extract.py)."""

import argparse
import importlib
import os
import sys
import time

if not __package__:
    # run as `python scripts/level_port`: import the package from its parent folder
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "level_port"

from level_port.common import files  # noqa: E402


def main():
    parser = argparse.ArgumentParser(prog="python scripts/level_port",
                                     description="Turns levels of one Jak game into custom levels "
                                                 "of another, as a port manifest describes.")
    parser.add_argument("manifest", help="the port's manifest, e.g. "
                                         "custom_assets/jak3/ports/jak2-haven-city/port.jsonc")
    parser.add_argument("--steps", help="the steps to run, comma separated (default: all)")
    parser.add_argument("--root", help="the folder every path of the port is relative to (default: "
                                       "the repository root; a mod release's data/ folder)")
    parser.add_argument("--iso", action="append", default=[], metavar="GAME=PATH",
                        help="a game's extracted disc (default: iso_data/<game>), repeatable")
    parser.add_argument("--extractor", help="extract the source game's levels with this OpenGOAL "
                                            "extractor (a mod release's) instead of the "
                                            "decompiler of out/build/Release/bin")
    parser.add_argument("--fr3-check", help="the fr3_check executable (default: "
                                            "out/build/Release/bin/fr3_check)")
    args = parser.parse_args()
    manifest = os.path.abspath(args.manifest)
    # the launcher's UI shows the output while it runs, mixed with the extractor's
    sys.stdout.reconfigure(line_buffering=True)
    # the tools and the discs, absolute (as given from here): every path of the port is relative
    # to the root
    isos = {}
    for item in args.iso:
        game, sep, path = item.partition("=")
        if not sep:
            parser.error(f"--iso {item}: expected GAME=PATH")
        # "/" separators: the build file the port writes quotes them in GOAL strings
        isos[game] = os.path.abspath(path).replace(os.sep, "/")
    tools = {"EXTRACTOR": args.extractor, "FR3_CHECK": args.fr3_check}
    tools = {k: os.path.abspath(v) for k, v in tools.items() if v}
    if args.root:
        files.ROOT = os.path.abspath(args.root)
    os.chdir(files.ROOT)
    from level_port.steps import extract
    for name, path in tools.items():
        setattr(extract, name, path)
    for game, path in isos.items():
        importlib.import_module(f"level_port.games.{game}").ISO = path
    from level_port.manifest import Port
    from level_port.steps import STEPS
    port = Port(manifest)
    steps = args.steps.split(",") if args.steps else list(STEPS)
    for name in steps:
        if name not in STEPS:
            parser.error(f"unknown step {name} (steps: {', '.join(STEPS)})")
    for name in steps:
        start = time.time()
        print(f"{name}:")
        STEPS[name](port)
        print(f"  ({time.time() - start:.1f} s)")
    # a full run knows every generated file: the manifest's "ignore_outputs" .gitignore lists them
    # (in a git checkout only: a mod release's data/ folder has no .gitignore to keep)
    if not args.steps and port.get("ignore_outputs") and \
            os.path.exists(os.path.join(files.ROOT, ".git")):
        if files.write_ignore_block(port["ignore_outputs"], port["tag"], files.OUTPUTS):
            print(f"{port['ignore_outputs']}: {len(files.OUTPUTS)} generated files listed")


if __name__ == "__main__":
    main()
