"""python scripts/level_port <port manifest> [--steps mesh,levels,...]

Runs the port's steps (see steps/__init__.py) from the repository root. Generated files are only
rewritten when their content changes, so goalc only rebuilds the levels that changed."""

import argparse
import os
import sys
import time

if not __package__:
    # run as `python scripts/level_port`: import the package from its parent folder
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "level_port"

from level_port.common.files import OUTPUTS, ROOT, write_ignore_block  # noqa: E402


def main():
    parser = argparse.ArgumentParser(prog="python scripts/level_port",
                                     description="Turns levels of one Jak game into custom levels "
                                                 "of another, as a port manifest describes.")
    parser.add_argument("manifest", help="the port's manifest, e.g. "
                                         "custom_assets/jak3/ports/jak2-haven-city/port.jsonc")
    parser.add_argument("--steps", help="the steps to run, comma separated (default: all)")
    args = parser.parse_args()
    manifest = os.path.abspath(args.manifest)
    # every path of the port is relative to the repository root
    os.chdir(ROOT)
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
    if not args.steps and port.get("ignore_outputs"):
        if write_ignore_block(port["ignore_outputs"], port["tag"], OUTPUTS):
            print(f"{port['ignore_outputs']}: {len(OUTPUTS)} generated files listed")


if __name__ == "__main__":
    main()
