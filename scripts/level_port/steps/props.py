"""Props that stay actors in the port (the others are background, steps/mesh.py).

  - "props": source props the target game has a class and an art group for. Jak 3's Haven City
    reuses Jak 2's market props and farm crops: their art groups ship in Jak 3's DGOs and their code
    in Jak 3's level code, already compiled (out/jak3/obj), listed in the level's DGO ("code").
  - "custom_props": source props the target game has no art for: their model is rebuilt from the
    source game's ripped one (glb.rebuild_model), built by build-actor, and placed with a class of
    the mod. A prop with several looks (switched with setup-masks in the source game: build-actor
    models have no mask table) gets a model per look.

Manifest, on the level:
  "props": {
    "etypes": {"<source etype>": [our etype, its art group]},
    "code": [the target game's objects holding their classes, before the level's own code],
    "random_yaw": [source etypes turned to a random angle when they spawn: the angle is set here,
                   the same on every run],
    "base_aid": the actor id of the first one
  },
  "custom_props": {
    "etypes": {"<source etype>": {"etype": ours, "rip": "<level>/<model>-lod0.glb",
                                  "prims": [primitives kept], "looks": [[model, prims], ...]}},
    "base_aid": the actor id of the first one
  }
"""

import math
import zlib

from ..common import glb
from ..common.geometry import r4


def yaw_quat(name):
    """A fixed pseudo random rotation around y, from the actor name."""
    angle = (zlib.crc32(name.encode()) % 3600) / 10.0
    half = math.radians(angle) / 2
    return [0.0, r4(math.sin(half)), 0.0, r4(math.cos(half))]


def prop_actors(port, level):
    """(comment, actor) list, art groups, code objects and counts for the props of a level."""
    cfg = level["props"]
    etypes = cfg["etypes"]
    random_yaw = set(cfg.get("random_yaw", []))
    out = []
    art = []
    counts = {}
    for src in level.sources:
        for actor in port.story.level_actors(src):
            etype = actor["etype"]
            if etype not in etypes:
                continue
            our_etype, ag = etypes[etype]
            if ag not in art:
                art.append(ag)
            name = actor["lump"]["name"]
            lump = {"name": name}
            if "vis-dist" in actor["lump"]:
                lump["vis-dist"] = ["float", float(actor["lump"]["vis-dist"])]
            trans = [r4(x) for x in actor["trans"][:3]]
            quat = yaw_quat(name) if etype in random_yaw else [r4(x) for x in actor["quat"]]
            out.append((f"{port.source.TITLE}'s {name} ({src})", {
                "trans": trans,
                "etype": our_etype,
                "aid": cfg["base_aid"] + len(out),
                "game_task": 0,
                "quat": quat,
                "bsphere": trans + [r4(actor["bsphere"][3])],
                "lump": lump,
            }))
            counts[our_etype] = counts.get(our_etype, 0) + 1
    return out, art, list(cfg.get("code", [])), counts


def custom_prop_actors(port, level):
    """(comment, actor) list and model names of the props with a custom model."""
    cfg = level["custom_props"]
    etypes = cfg["etypes"]
    out = []
    models = []
    for spec in etypes.values():
        rip = port.rip(spec["rip"])
        glb.rebuild_model(rip, f"{port.models_dir}/{spec['etype']}.glb", spec["etype"],
                          spec["prims"])
        models.append(spec["etype"])
        for look, look_prims in spec.get("looks", []):
            glb.rebuild_model(rip, f"{port.models_dir}/{look}.glb", look, look_prims)
            models.append(look)
    for src in level.sources:
        for actor in port.story.level_actors(src):
            if actor["etype"] not in etypes:
                continue
            name = actor["lump"]["name"]
            lump = {"name": name}
            if "vis-dist" in actor["lump"]:
                lump["vis-dist"] = ["float", float(actor["lump"]["vis-dist"])]
            trans = [r4(x) for x in actor["trans"][:3]]
            out.append((f"{port.source.TITLE}'s {name} ({src})", {
                "trans": trans,
                "etype": etypes[actor["etype"]]["etype"],
                "aid": cfg["base_aid"] + len(out),
                "game_task": 0,
                "quat": [r4(x) for x in actor["quat"]],
                "bsphere": trans + [r4(actor["bsphere"][3])],
                "lump": lump,
            }))
    return out, models
