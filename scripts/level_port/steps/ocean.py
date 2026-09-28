"""Ocean maps: a level's own ocean map, copied from the source game's code.

A level that draws a sea or a stream with an ocean map of its own (Jak 2's Dead Town and mountain:
*ocean-map-ruins* in levels/ruins/ruins-ocean.gc...) gets it copied, renamed, into its level code
(<level>-ocean.gc, in the level's DGO), with what the target game's ocean-map lacks left out (see
the game pair's ocean_map_forms). The level-load-info names it (the level's "ocean"); the level
defines it each time it loads, like the source game's.

Manifest, on the level:
  "ocean": "<our map name>",
  "ocean_source": {"file": the source game's .gc file, "name": the source map's name (ruins)}
"""

import re

from ..common.files import write_if_changed


def write_level(port, level):
    src = level["ocean_source"]
    source_name = src["name"]
    map_name = level["ocean"]
    text = open(src["file"], encoding="utf-8").read()
    out = "\n\n".join(port.pair.ocean_map_forms(text, source_name))
    out = out.replace(f"*ocean-map-{source_name}*", map_name)
    out = re.sub(r"\*ocean-([a-z-]+)-" + re.escape(source_name) + r"\*",
                 lambda m: f"*{level.name}-ocean-{m.group(1)}*", out)
    name = f"{level.name}-ocean"
    header = "\n".join([
        ";;-*-Lisp-*-",
        "(in-package goal)",
        "",
        f";; name: {name}.gc",
        f";; name in dgo: {name}",
        f";; dgos: {level.dgo}",
        "",
        *port.generated_lines(),
        f";; {port.source.TITLE}'s ocean map of {source_name} ({map_name}), copied from",
        f";; {src['file']}",
        f";; without what {port.target.TITLE}'s ocean-map lacks. {level.name}'s level-load-info "
        "names it.",
        "",
        "",
    ])
    path = f"{port.code_dir}/{name}.gc"
    write_if_changed(path, header + out + "\n")
    return path


def run(port):
    for level in port.levels:
        if "ocean_source" in level:
            print("  wrote", write_level(port, level))
