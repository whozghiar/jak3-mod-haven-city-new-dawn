"""Make a new Haven City: New Dawn texture pack: the latest pack's files, plus the color variants'
textures the level port wrote (paths.texture_variants of port.jsonc), named <texture>-<model>.

The pack's own replacements stay as they are: a variant texture with the same file name as one of
them is left out, and reported. Retouch a variant in the variants folder (or in an installed pack:
the level port then uses that file for the model), then run this script and commit the zip
(`git add -f`: the folder ignores zips). The release workflow uploads every zip of the folder and
registers it in index.json.

Usage, from the repository root:
    python custom_assets/jak3/ports/jak2-haven-city/make_texture_pack.py [--version 1.1.0] [--out <zip>]
"""
import argparse
import datetime
import glob
import json
import os
import re
import sys
import zipfile

PACKS = "docs/modding/current_mod/texture_packs"
PREFIX = "haven-city-new-dawn-textures-v"
VARIANTS = PACKS + "/variants/custom_assets/jak3/texture_replacements/_all"
IN_PACK = "custom_assets/jak3/texture_replacements/_all/"


def version_key(path):
    return tuple(int(x) for x in re.findall(r"v(\d+)\.(\d+)\.(\d+)\.zip$", path)[0])


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--version", help="the new pack's version (default: the latest's, minor + 1)")
    parser.add_argument("--out", help="the zip to write (default: the packs folder)")
    args = parser.parse_args()

    packs = sorted(glob.glob(f"{PACKS}/{PREFIX}*.zip"), key=version_key)
    if not packs:
        sys.exit(f"no {PREFIX}*.zip in {PACKS}")
    base = packs[-1]
    major, minor, _ = version_key(base)
    version = args.version or f"{major}.{minor + 1}.0"
    out = args.out or f"{PACKS}/{PREFIX}{version}.zip"
    if os.path.exists(out):
        sys.exit(f"{out} exists already")
    variants = sorted(glob.glob(f"{VARIANTS}/*.png"))
    if not variants:
        sys.exit(f"no texture in {VARIANTS}: run the level port first")

    with zipfile.ZipFile(base) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        kept = set(src.namelist())
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "metadata.json":
                meta = json.loads(data)
                meta["version"] = version
                meta["releaseDate"] = datetime.date.today().isoformat()
                meta["publishedDate"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                meta["description"] = meta["description"].rstrip(".") + \
                    ", and the red and blue versions of the turret, transport, guard bike and Hellcat."
                data = json.dumps(meta, indent=2).encode()
            dst.writestr(item, data)
        added, left_out = 0, []
        for path in variants:
            entry = IN_PACK + os.path.basename(path)
            if entry in kept:
                left_out.append(entry)
                continue
            dst.write(path, entry)
            added += 1
    print(f"{out}: {len(kept)} files of {os.path.basename(base)}, {added} variant textures added")
    for entry in left_out:
        print(f"  left out (the pack already has it): {entry}")


if __name__ == "__main__":
    main()
