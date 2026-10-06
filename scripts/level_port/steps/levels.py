"""The port's levels: their actors, regions, continue points, memory modes and level files.

The source game loads its levels with scripts: in doors and elevators (on-activate, on-enter,
on-inside...), in invisible regions (a plane crossed in a street, a volume entered...) and in its
continue points. This step ports all of them, translated by convert/scripts.py: each source level
becomes the port's level holding it (a level merging several source levels stands for all of
them), and the level sets the source game loads together are kept.

A level with a hub (the manifest's "hub": a city's districts and their city-wide level) is always
loaded after its hub: every level list naming it gets the hub, first (convert/scripts.py with_hubs).

Writes, for each level of the manifest:
  - its .jsonc and .gd,
  - its regions (<level>-regions.json) and water regions (<level>-water-regions.json),
  - the models its actors use (models_dir/<model>.glb, for build-actor),
and every level's level-load-info with its continue points (the manifest's "level_info" file).

Inputs (a source game extraction first):
  decompiler_out/<game>/entities/<level>-actors.json, -cameras.json     actors, fixed cameras
  decompiler_out/<game>/levels/<level>/<model>-lod0.glb     models rebuilt for build-actor
  the source game's regions and continue points (games/<source>.py)
"""

import json
import math
import os
import re

from ..common import glb
from ..common.files import write_if_changed
from ..common.geometry import bounding_sphere, box_faces, front, r4
from ..convert.scripts import Translator, with_hubs
from ..manifest import nested
from . import mesh as mesh_step
from . import nav as nav_step
from . import particles
from . import props as props_step
from . import sound as sound_step
from . import water as water_step


def script(text):
    return ["pair", text]


class Context:
    def __init__(self, port):
        self.port = port
        self.pair = port.pair
        self.meter = port.source.METER
        self.title = port.source.TITLE
        self.actors = port.story.all_actors()
        self.all_levels = port.source.level_names() | set(port.level_map)
        self.backdrops = set(port.get("backdrop_levels", []))
        conts = port["continues"]
        self.continue_prefix = conts["prefix"]
        self.continue_renames = conts.get("names", {})
        self.continues = port.source.continues()
        self.continues.update(door_continues(self))
        self.continues.update(new_continues(self))
        self.continue_names = {}  # source name -> ours, filled by the continue selection
        self.aid_to_name = {a["aid"]: name for (lev, name), a in self.actors.items() if "aid" in a}
        self.cameras = load_cameras(port)
        self.camera_names = {c["lump"]["name"] for cams in self.cameras.values() for c in cams}
        self.regions = port.source.regions()
        # our level -> its level-memory-mode: fixed in the manifest, else set by memory_modes
        self.memory = {lv.name: lv["memory"] for lv in port.levels if "memory" in lv}
        # part-engine-max of the levels with part spawners (their static ones), and the spawners
        # and sprite textures of the levels' particles (write_particles)
        self.part_engine_max = {}
        self.part_actors = {}
        self.sprite_textures = {}
        self.etypes = {**self.pair.DOOR_ETYPES, **port.get("etypes", {})}
        self.models = port.get("models", {})
        self.doors = [tuple(d) for d in port.get("doors", [])]
        self.closed_doors = [tuple(d) for d in port.get("closed_doors", [])]
        self.elevators = port.get("elevators", [])
        # the source game's sound banks and music (None: the levels are silent)
        self.sound = sound_step.Sound(port) if "sound" in port.data else None

    def continue_name(self, source_name):
        return self.continue_renames.get(source_name, self.continue_prefix + source_name)

    def translator(self, source_level, open_tasks=()):
        port = self.port
        story = port.story
        return Translator(self.pair, port.level_map, self.all_levels | self.backdrops, port.hubs,
                          port.level_map[source_level],
                          lambda task: story.closed(task, open_tasks), self.continue_names,
                          port.get("renames", {}), [tuple(e) for e in port.get("drop_events", [])],
                          self.camera_names, source=source_level, sound=self.sound)

    def art_group(self, etype):
        """The art group of a class, from the target game's DGOs (None: built by build-actor)."""
        extra = self.port.get("art_groups", {})
        if etype in extra:
            return extra[etype]
        if etype in self.pair.ART_GROUPS:
            return self.pair.ART_GROUPS[etype]
        if etype in self.models:
            return None
        raise KeyError(f"no art group known for {etype}: add it to the manifest's art_groups")


# source data #####################################################################################


def load_cameras(port):
    """The source game's fixed cameras (lumps typed for the builder) of the levels that are ported,
    by our level. Their ids are left to the builder."""
    out = {}
    for src, ours in sorted(port.level_map.items()):
        for cam in port.source.cameras(src):
            out.setdefault(ours, []).append({
                "trans": [r4(x) for x in cam["trans"][:3]],
                "quat": [r4(x) for x in cam["quat"]],
                "lump": cam["lump"],
            })
    return out


def look_at(pos, cam, height):
    """The camera-rot rows (right, up, forward) of a camera at cam looking at pos + height."""
    look = [pos[0] - cam[0], pos[1] + height - cam[1], pos[2] - cam[2]]
    n = math.sqrt(sum(c * c for c in look))
    f = [c / n for c in look]
    r = [f[2], 0.0, -f[0]]  # cross(y, f)
    n = math.sqrt(sum(c * c for c in r))
    r = [c / n for c in r]
    u = [f[1] * r[2] - f[2] * r[1], f[2] * r[0] - f[0] * r[2], f[0] * r[1] - f[1] * r[0]]
    return r + u + f


def door_continues(ctx):
    """The manifest's door continues, as source continues (game units): Jak in front of the door,
    facing it, the camera behind him."""
    out = {}
    meter = ctx.meter
    for name, spec in ctx.port["continues"].get("door_continues", {}).items():
        level, distance = spec["level"], spec["distance"]
        door = ctx.actors[(level, spec["door"])]
        fx, _, fz = front(door)
        pos = [door["trans"][0] + fx * distance, door["trans"][1], door["trans"][2] + fz * distance]
        # facing the door: yaw of (-fx, -fz)
        yaw = math.atan2(-fx, -fz)
        quat = [0.0, math.sin(yaw / 2), 0.0, math.cos(yaw / 2)]
        cam = [pos[0] + fx * 8.0, pos[1] + 3.5, pos[2] + fz * 8.0]
        out[name] = dict(
            level=level,
            trans=[c * meter for c in pos] + [1.0],
            quat=quat,
            camera_trans=[c * meter for c in cam] + [1.0],
            camera_rot=look_at(pos, cam, 1.5),
            flags=set(),
            wants=spec["wants"],
        )
    return out


def facing_continue(meter, pos, facing, distance, flags, wants):
    """A continue (source format, game units) in front of a gate at pos (m) facing (unit xz): Jak
    stands distance meters in front of it, facing away from it, the camera behind him."""
    fx, fz = facing
    at = [pos[0] + fx * distance, pos[1], pos[2] + fz * distance]
    yaw = math.atan2(fx, fz)
    quat = [0.0, math.sin(yaw / 2), 0.0, math.cos(yaw / 2)]
    cam = [at[0] - fx * 4.5, at[1] + 3.0, at[2] - fz * 4.5]
    return dict(trans=[c * meter for c in at] + [1.0], quat=quat,
                camera_trans=[c * meter for c in cam] + [1.0], camera_rot=look_at(at, cam, 1.5),
                flags=set(flags), wants=wants)


def new_continues(ctx):
    """The manifest's continues at a position in a source level, as source continues."""
    out = {}
    for name, spec in ctx.port["continues"].get("new_continues", {}).items():
        cont = facing_continue(ctx.meter, spec["pos"], spec["facing"], spec["distance"],
                               spec.get("flags", []), spec["wants"])
        cont["level"] = spec["level"]
        out[name] = cont
    return out


# scripts #########################################################################################


def translate_lumps(ctx, source_level, name, lump):
    """The translated scripts of one of the source game's doors or elevators."""
    tr = ctx.translator(source_level)
    out = {}
    for key in sorted(k for k in lump if k.startswith("on-")):
        if key == "on-notice":
            # the levels a door waits for: a level that isn't ported (but a backdrop) keeps the
            # door shut, behind it there's nothing to walk on (only the branch the story state
            # reaches counts, see Translator.strict_notice)
            text = tr.strict_notice(lump[key], ctx.backdrops)
        else:
            text = tr.script(lump[key])
        if text:
            out[key] = text
    overrides = nested(ctx.port.get("script_overrides", {}), source_level, name) or {}
    for key, text in overrides.items():
        if text is None:
            out.pop(key, None)
        else:
            out[key] = text
    return out


# actors ##########################################################################################


def next_actor(actor):
    """The actor id of a door's pair (Jak 2 stores it alone or as the first of four words)."""
    value = actor["lump"].get("next-actor")
    return value[0] if isinstance(value, list) else value


def base_lumps(actor, door_height=None, meter=4096.0):
    """Door settings from the source game (res units). door_height: [above, below] meters, the
    height lump of a door that has none (the manifest's "door_height"): the target game's airlock
    only opens and runs its scripts while Jak is between door y - below and door y + above. The
    source game paused the actors it didn't see (its levels' visibility data); the port's levels
    have none, so without it a door right above Jak (the top of the palace pillars, 420m up) acts
    on him from the street below: it only tests the distance on x and z."""
    lump = {"name": actor["lump"]["name"]}
    for key in ("distance", "idle-distance", "height"):
        if key in actor["lump"]:
            value = actor["lump"][key]
            values = value if isinstance(value, list) else [value]
            lump[key] = ["float"] + [float(v) for v in values]
    if "height" not in lump and door_height:
        lump["height"] = ["vector", [door_height[0] * meter, door_height[1] * meter, 0.0, 0.0]]
    if "options" in actor["lump"]:
        # bit 0: inner door (runs on-inside)
        lump["options"] = ["uint32", int(actor["lump"]["options"])]
    if "open-test" in actor["lump"]:
        lump["open-test"] = script(actor["lump"]["open-test"])
    return lump


def placed(actor, etype, lump, trans=None):
    """An actor of the level .jsonc, placed like the source actor. Its vis-dist isn't copied: the
    source game only used it in levels without visibility data, never here (a door born on the way
    up a pillar would run its scripts there)."""
    trans = trans or [r4(x) for x in actor["trans"][:3]]
    return {
        "trans": trans,
        "etype": etype,
        "game_task": 0,
        "quat": [r4(x) for x in actor["quat"]],
        "bsphere": trans + [r4(actor["bsphere"][3])],
        "lump": lump,
    }


def make_door(ctx, source_level, name, closed):
    actor = ctx.actors[(source_level, name)]
    etype = ctx.etypes[actor["etype"]]
    lump = base_lumps(actor, ctx.port.get("door_height"), ctx.meter)
    scripts = {} if closed else translate_lumps(ctx, source_level, name, actor["lump"])
    if "on-notice" not in scripts:
        # never opens: nothing else to run either
        scripts = {}
        closed = True
    for key, text in scripts.items():
        lump[key] = script(text)
    pair = nested(ctx.port.get("next_actor_overrides", {}), source_level, name) or \
        ctx.aid_to_name.get(next_actor(actor))
    if pair and pair in {nm for _, nm in ctx.doors} and not closed:
        lump["next-actor"] = ["string", pair]
    return etype, closed, placed(actor, etype, lump)


def elevator_actor(ctx, actor, path_points, name, scripts):
    """The target game's elevator from a source elevator (its model, so its origin), with its path
    (game units)."""
    src = actor["lump"]
    path = ["vector"] + [[r4(c) for c in p[:3]] + [1.0] for p in path_points]
    lump = {
        "name": name,
        "path": path,
        "elevator-flags": ["uint32", ctx.pair.ELEVATOR_FLAGS],
        "elevator-move-rate": ["float", float(src.get("elevator-move-rate", 25600.0))],
    }
    for key in ("elevator-xz-threshold", "elevator-y-threshold"):
        if key in src:
            lump[key] = ["float", float(src[key])]
    for key, text in scripts.items():
        lump[key] = script(text)
    return placed(actor, ctx.etypes[actor["etype"]], lump)


def make_elevator(ctx, source_level, name):
    actor = ctx.actors[(source_level, name)]
    scripts = translate_lumps(ctx, source_level, name, actor["lump"])
    # Jak 2's elevator on-notice meant "don't ride", Jak 3's elevator only runs it
    scripts.pop("on-notice", None)
    # its two ends: Jak 2's elevators ride from the first point to the last (points in between are
    # on the way), Jak 3's stops at each point
    path = actor["lump"]["path"]
    return elevator_actor(ctx, actor, [path[0], path[-1]], name, scripts)


def make_stopping_elevator(ctx, spec):
    """One of the manifest's "elevators": an elevator stopping at every point of its path."""
    level, name = spec["level"], spec["name"]
    main = ctx.actors[(level, name)]
    scripts = translate_lumps(ctx, level, name, main["lump"])
    scripts.pop("on-notice", None)
    actor = elevator_actor(ctx, main, main["lump"]["path"], name, scripts)
    # called from every floor: its thresholds (meters)
    actor["lump"]["elevator-xz-threshold"] = ["float", spec["xz_threshold"] * ctx.meter]
    actor["lump"]["elevator-y-threshold"] = ["float", spec["y_threshold"] * ctx.meter]
    return actor


def lump_value(ctx, kind, value):
    """A source lump value (a number or list) as a builder res lump: "float", "int32", "uint32",
    "vector" (as they are), "path" (points rounded, w = 1), or "string", "symbol", "type" (names,
    passed through: the art-name of a prop, for instance)."""
    if kind in ("string", "symbol", "type"):
        return [kind] + [str(v) for v in (value if isinstance(value, list) else [value])]
    if kind == "path":
        return ["vector"] + [[r4(c) for c in p[:3]] + [1.0] for p in value]
    if kind == "vector":
        vectors = value if isinstance(value[0], list) else [value]
        return ["vector"] + [[float(c) for c in v] for v in vectors]
    values = value if isinstance(value, list) else [value]
    return [kind] + [float(v) if kind == "float" else int(v) for v in values]


def make_named_actor(ctx, source_level, name):
    """One of the manifest's "named_actors": (comment, actor)."""
    actor = ctx.actors[(source_level, name)]
    src = actor["lump"]
    lump = {"name": name}
    if actor["etype"] in ctx.pair.WARP_GATE_ETYPES:
        # the target game's warp gate reads the same on-notice: '("destination" on-activate
        # wait-for), the continue name translated, and the level names of the quoted script and
        # level list (the translator leaves quoted data as it is)
        etype = ctx.pair.WARP_GATE_ETYPES[actor["etype"]]
        notice = ctx.translator(source_level).script(src["on-notice"], value=True)
        if notice:
            notice = re.sub(r"(?<=[\s'(])([a-z0-9-]+)(?=[\s)])",
                            lambda m: ctx.port.level_map.get(m.group(1), m.group(1)), notice)
            lump["on-notice"] = script(notice)
        comment = f"{ctx.title}'s {name} ({source_level})"
    else:
        spec = ctx.port["named_etypes"][actor["etype"]]
        etype = spec["etype"]
        comment = f"{ctx.title}'s {name} ({source_level}) [as {etype}]"
        for key, kind in spec.get("lumps", {}).items():
            lump[key] = lump_value(ctx, kind, src[key])
    return comment, placed(actor, etype, lump)


def make_teleporter(ctx, spec):
    """One of the manifest's "teleporters" (a source actor replaced by a teleporter class):
    (comment, actor). Its on-notice is the target game's air train's: '("continue" on-activate
    wait-for)."""
    level, name = spec["level"], spec["name"]
    actor = ctx.actors[(level, name)]
    dest_name = ctx.continue_name(spec["dest"])
    assert spec["dest"] in ctx.continue_names, f"{name}: continue {spec['dest']} isn't ported"
    lump = {
        "name": name,
        "on-notice": script(f"'(\"{dest_name}\" #f #f)"),
        # how close Jak must be to get on (the source actor's)
        "distance": ["float", float(actor["lump"].get("distance", 20480.0))],
        # the prompt: Press <triangle> to travel to <travel-name>
        "travel-name": ["string", spec["travel_name"]],
    }
    comment = f"{ctx.title}'s {name} ({level}) [as {spec['etype']}]: to {dest_name}"
    return comment, placed(actor, spec["etype"], lump)


def make_new_teleporter(spec):
    """One of the manifest's "new_teleporters" (a teleporter at a position, facing (unit xz)):
    (comment, actor)."""
    yaw = math.atan2(spec["facing"][0], spec["facing"][1])
    trans = [r4(c) for c in spec["pos"]]
    return spec.get("comment", f"{spec['name']}: to {spec['dest']}"), {
        "trans": trans,
        "etype": spec["etype"],
        "game_task": 0,
        "quat": [0.0, r4(math.sin(yaw / 2)), 0.0, r4(math.cos(yaw / 2))],
        "bsphere": trans + [spec["radius"]],
        "lump": {
            "name": spec["name"],
            "on-notice": script(f"'(\"{spec['dest']}\" #f #f)"),
            "travel-name": ["string", spec["travel_name"]],
        },
    }


def make_actors(ctx, level):
    """The doors, elevators and other named actors of one of our levels: (comment, actor) list and
    art groups."""
    port = ctx.port
    out = []
    art = []

    def add(comment, actor):
        out.append((comment, actor))
        ag = ctx.art_group(actor["etype"])
        if ag and ag not in art:
            art.append(ag)

    elevator_etypes = set(port.get("elevator_etypes", []))
    for source_level, name, closed in [(lv, nm, False) for lv, nm in ctx.doors] + [
            (lv, nm, True) for lv, nm in ctx.closed_doors]:
        if port.level_map[source_level] != level.name:
            continue
        etype_src = ctx.actors[(source_level, name)]["etype"]
        if etype_src in elevator_etypes:
            actor = make_elevator(ctx, source_level, name)
            add(f"{ctx.title}'s {name} ({source_level}) [as {actor['etype']}]", actor)
            continue
        etype, is_closed, actor = make_door(ctx, source_level, name, closed)
        comment = f"{ctx.title}'s {name} ({source_level})" + (", shut" if is_closed else "")
        if etype_src != etype:
            comment += f" [as {etype}]"
        add(comment, actor)
    for spec in ctx.elevators:
        if port.level_map[spec["level"]] == level.name:
            add(f"{ctx.title}'s {spec['name']} ({spec['level']}): {spec['comment']}",
                make_stopping_elevator(ctx, spec))
    for source_level, name in port.get("named_actors", []):
        if port.level_map[source_level] == level.name:
            add(*make_named_actor(ctx, source_level, name))
    for spec in port.get("teleporters", []):
        if port.level_map[spec["level"]] == level.name:
            add(*make_teleporter(ctx, spec))
    for spec in port.get("new_teleporters", []):
        if port.level_map[spec["level"]] == level.name:
            add(*make_new_teleporter(spec))
    return out, art


def ported_actors(ctx, level):
    """(comment, actor) list of the source game's platforms, props (the manifest's
    "ported_etypes") and crates of a level."""
    port = ctx.port
    ported = port.get("ported_etypes", {})
    ported_levels = set(port.get("ported_levels", []))
    everywhere = set(port.get("ported_everywhere", []))
    out = []
    for (src_level, name), actor in sorted(ctx.actors.items(), key=lambda kv: str(kv[0])):
        if src_level not in level.sources:
            continue
        src = actor["lump"]
        trans = [r4(x) for x in actor["trans"][:3]]
        if actor["etype"] in ctx.pair.CRATES:
            lump = {"name": name}
            if src.get("eco-info"):
                kind, amount = src["eco-info"][:2]
                lump["eco-info"] = ["int32", ctx.pair.PICKUPS.get(int(kind), 0), int(amount)]
            etype = ctx.pair.CRATES[actor["etype"]]
        elif actor["etype"] in ported and (src_level in ported_levels or
                                           actor["etype"] in everywhere):
            spec = ported[actor["etype"]]
            etype = spec["etype"]
            lump = {"name": name}
            for key, kind in spec.get("lumps", {}).items():
                if key in src:
                    lump[key] = lump_value(ctx, kind, src[key])
            if spec.get("trans") == "path_start":
                trans = [r4(c / ctx.meter) for c in src["path"][0][:3]]
        else:
            continue
        out.append((f"{ctx.title}'s {name} ({src_level})", placed(actor, etype, lump, trans)))
    return out


def model_spec(ctx, model):
    return next(spec for spec in ctx.models.values() if spec["model"] == model)


def build_model(ctx, spec):
    """<model>.glb for build-actor, rebuilt from the source game's rip."""
    port = ctx.port
    anims = [(port.rip(rip), anim, ours) for rip, anim, ours in spec.get("anims", [])] or None
    verts, lo, hi = glb.rebuild_model(port.rip(spec["rip"]),
                                      f"{port.models_dir}/{spec['model']}.glb", spec["model"],
                                      spec.get("prims"), spec.get("collide"), anims=anims)
    print(f"    {spec['model']}: {verts} vertices, bounds {lo} - {hi}")


def custom_models(ctx, actor_list):
    """The models rebuilt from the source game's (the manifest's "models") that these actors use,
    written for build-actor."""
    models = []
    for etype, spec in ctx.models.items():
        if spec["model"] not in models and any(actor["etype"] == etype
                                               for _, actor in actor_list):
            build_model(ctx, spec)
            models.append(spec["model"])
            for extra in spec.get("extras", []):
                build_model(ctx, extra)
                models.append(extra["model"])
    return models


def check_pairs(ctx):
    """Paired doors must face away from each other: on-cross runs when Jak goes from a door's
    front to its back."""
    for source_level, name in ctx.doors:
        actor = ctx.actors[(source_level, name)]
        pair = ctx.aid_to_name.get(next_actor(actor))
        if not pair:
            continue
        other = next(a for (lev, nm), a in ctx.actors.items() if nm == pair)
        to_other = [other["trans"][i] - actor["trans"][i] for i in range(3)]
        if sum(front(actor)[i] * to_other[i] for i in range(3)) > 0:
            print(f"  note: {name} faces its pair {pair}")


# regions #########################################################################################


def region_json(ctx, region, rid, scripts):
    """One of the source game's regions in the builder's format (meters)."""
    out = {"id": rid}
    if region["sphere"]:
        out["shape"] = "sphere"
        out["bsphere"] = [r4(c) for c in region["sphere"]]
    else:
        faces = [
            {"normal": [round(c, 6) for c in f["normal"][:3]]
             + [round(f["normal"][3] / ctx.meter, 6)],
             "points": [[r4(c) for c in p] for p in f["points"]]}
            for f in region["faces"].values()
        ]
        points = [p for f in faces for p in f["points"]]
        out["bsphere"] = bounding_sphere(points, 0.5)
        if len(faces) == 1 and next(iter(region["faces"].values()))["kind"] == "plane":
            out["shape"] = "face"
            out["face"] = faces[0]
        else:
            out["shape"] = "volume"
            out["volume"] = {"faces": faces}
    out.update(scripts)
    return out


def region_open_tasks(ctx, region):
    return ctx.port.get("region_open_tasks", {}).get(str(region["id"]), ())


def region_overrides(ctx, region):
    return ctx.port.get("region_script_overrides", {}).get(str(region["id"]), {})


def make_regions(ctx, level):
    """The source game's target and camera regions of the levels merged into ours, translated.
    Regions whose scripts are all gone are dropped."""
    trees = {}
    offset = ctx.port.get("region_id_offset", 0)
    for region in sorted(ctx.regions.values(), key=lambda r: r["id"]):
        if (region["tree"] not in ("target", "camera") or
                ctx.port.level_map.get(region["level"]) != level.name):
            continue
        tr = ctx.translator(region["level"], region_open_tasks(ctx, region))
        scripts = {}
        for key, text in region["scripts"].items():
            out = tr.script(text)
            if out:
                scripts[key] = out
        scripts.update(region_overrides(ctx, region))
        if scripts:
            trees.setdefault(region["tree"], []).append(
                region_json(ctx, region, region["id"] + offset, scripts))
    out = {}
    for tree, items in trees.items():
        points = []
        for r in items:
            c, rad = r["bsphere"][:3], r["bsphere"][3]
            points += [[c[0] + dx * rad, c[1] + dy * rad, c[2] + dz * rad]
                       for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0),
                                          (0, 0, 1), (0, 0, -1))]
        out[tree] = {"bsphere": bounding_sphere(points, 1.0), "regions": items}
    return out


def water_regions(ctx, level):
    """The source game's water-vol actors of a level as the target game's 'water' regions (Jak 3's
    water is regions only). A water-vol is an axis-aligned box of 6 planes (outside where
    dot(p, n) > d) with its water height; the region goes from the box bottom to 2m above the
    water. A level with a "water" block gets its regions (steps/water.py: its ocean sphere and its
    pools), else a level with the ocean gets the source game's ocean water regions (spheres:
    swimming at the ocean's height)."""
    regions = []
    meter = ctx.meter
    if "water" in level:
        regions += water_step.surfaces(ctx.port, level)[1]
    elif level.get("ocean"):
        for region in sorted(ctx.regions.values(), key=lambda r: r["id"]):
            if (region["level"] not in level.sources or region["tree"] != "water" or
                    not region["sphere"] or
                    not region["scripts"].get("on-inside", "").startswith("(water ocean")):
                continue
            sphere = [r4(x) for x in region["sphere"]]
            regions.append({
                "shape": "sphere",
                "trans": sphere[:3],
                "bsphere": sphere,
                "on-inside": "(water ocean 0.0 (swim wade))",
            })
    for (src_level, _), actor in sorted(ctx.actors.items(), key=lambda kv: str(kv[0])):
        if (src_level not in level.sources or actor["etype"] != "water-vol" or
                "vol" not in actor["lump"]):
            continue
        lo = [-1e9] * 3
        hi = [1e9] * 3
        for plane in actor["lump"]["vol"]:
            axis = max(range(3), key=lambda i: abs(plane[i]))
            limit = plane[3] / plane[axis] / meter
            if plane[axis] > 0:
                hi[axis] = min(hi[axis], limit)
            else:
                lo[axis] = max(lo[axis], limit)
        # its water height, else the top of its box (a pool whose surface is a water-anim)
        height = (actor["lump"]["water-height"][0] / meter if "water-height" in actor["lump"]
                  else hi[1])
        hi[1] = max(hi[1], height + 2.0)
        center = [(lo[i] + hi[i]) / 2 for i in range(3)]
        radius = sum((hi[i] - center[i]) ** 2 for i in range(3)) ** 0.5
        regions.append({
            "shape": "volume",
            "bsphere": [r4(c) for c in center] + [r4(radius + 0.5)],
            "on-inside": f"(water height {height:.4f} (swim wade))",
            "volume": {"faces": box_faces(lo, hi)},
        })
    if not regions:
        return None
    regions = [{"id": level["base_id"] + i, **r} for i, r in enumerate(regions)]
    points = [r["bsphere"][:3] for r in regions]
    radius = max(r["bsphere"][3] for r in regions)
    sphere = bounding_sphere(points, radius)
    return {"water": {"bsphere": sphere, "regions": regions}}


# continues #######################################################################################


def translate_wants(ctx, source_wants, owner=None):
    """A continue's source level list for our levels: a level merging several source levels is
    shown if one of them was, the levels that aren't ported are dropped; the continue's own level
    (owner) is shown if it's missing, and the hubs come first (with_hubs), hidden if missing."""
    out = {}
    for lev, disp in source_wants:
        ours = ctx.port.level_map.get(lev)
        if not ours:
            continue
        # 'display, else 'special (drawn as a backdrop), else hidden
        rank = {"'display": 2, "'special": 1}.get(disp, 0)
        out[ours] = max(out.get(ours, 0), rank)
    if owner and owner not in out:
        out = {owner: 2, **out}
    return [(lev, {2: "'display", 1: "'special"}.get(out.get(lev, 0), "#f"))
            for lev in with_hubs(list(out), ctx.port.hubs)]


def continue_wants(ctx, source_name, cont):
    return ctx.port["continues"].get("wants", {}).get(source_name, cont["wants"])


def continue_candidates(ctx):
    """(our level, source continue, the levels it loads) for the continues of the levels without
    a continue list of their own: all of their source levels', but the title, intro, demo and
    cutscene ones."""
    conts = ctx.port["continues"]
    kept = set(conts.get("kept", []))
    wants_overrides = conts.get("wants", {})
    for level in ctx.port.levels:
        if "continues" in level:
            continue
        for source_name, cont in ctx.continues.items():
            if cont["level"] not in level.sources:
                continue
            if source_name not in wants_overrides and source_name not in kept and (
                    cont["flags"] & ctx.pair.SKIPPED_CONTINUE_FLAGS or
                    any(word in source_name for word in ctx.pair.SKIPPED_CONTINUE_NAMES)):
                continue
            wants = translate_wants(ctx, continue_wants(ctx, source_name, cont), level.name)
            yield level.name, source_name, [lev for lev, _ in wants]


def listed_continues(ctx):
    """(our level, source continue, the levels it loads) for the continues the levels list."""
    for level in ctx.port.levels:
        for source_name in level.get("continues", []):
            cont = ctx.continues[source_name]
            wants = translate_wants(ctx, continue_wants(ctx, source_name, cont), level.name)
            yield level.name, source_name, [lev for lev, _ in wants]


def select_continues(ctx):
    """(our level, continue name, source continue) for every continue point to write."""
    chosen = []
    for level, source_name, _ in listed_continues(ctx):
        chosen.append((level, ctx.continue_name(source_name), source_name))
    for level, source_name, levels in continue_candidates(ctx):
        try:
            check_memory(ctx, levels)
        except ValueError:
            print(f"  continue {source_name}: its levels {levels} don't fit together, left out")
            continue
        chosen.append((level, ctx.continue_name(source_name), source_name))
    for _, ours, source_name in chosen:
        ctx.continue_names[source_name] = ours
    return chosen


def continue_point(ctx, level, cont_name, source_name):
    cont = ctx.continues[source_name]
    wants = translate_wants(ctx, continue_wants(ctx, source_name, cont), level)
    check_memory(ctx, [lev for lev, _ in wants])
    flags = [f for f in ctx.pair.KEPT_CONTINUE_FLAGS if f in cont["flags"]]
    banks = cont.get("want_sound", [None] * 3) if ctx.sound else [None] * 3
    want_sound = " ".join(f"'{ctx.sound.bank(b)}" if b else "#f" for b in banks)
    return ctx.port.target.continue_point(cont_name, level, cont["trans"], cont["camera_trans"],
                                          cont["quat"], cont["camera_rot"], flags, wants,
                                          want_sound=want_sound)


def target_continue(ctx, spec):
    """One of the manifest's "target_continues": a continue of a target game level, defined in the
    level-info file for the mod's code (in front of a gate, facing away from it)."""
    cont = facing_continue(ctx.meter, spec["pos"], spec["facing"], spec["distance"], set(),
                           spec["wants"])
    comment = "\n".join(f";; {line}" for line in spec.get("comment", []))
    text = ctx.port.target.continue_point(
        spec["name"], spec["level"], cont["trans"], cont["camera_trans"], cont["quat"],
        cont["camera_rot"], spec.get("flags", []), spec["wants"],
        want_sound=" ".join(f"'{s}" if s != "#f" else s
                            for s in spec.get("want_sound", ["#f"] * 3)),
        indent=2)
    return f"{comment}\n(define {spec['var']}\n{text}\n  )\n"


# memory ##########################################################################################


WANT_LOAD = re.compile(r"\(want-load((?: '[\w-]+)+)\)")


def check_memory(ctx, levels):
    if not ctx.port.target.fits([ctx.memory[lv] for lv in levels]):
        raise ValueError(f"levels {levels} don't fit in the level heap together")


def load_sets(ctx):
    """Every set of our levels loaded together: the want-load lists of the translated door,
    elevator and region scripts, and the levels of the continues."""
    sets = set()

    def add_script(text):
        for m in WANT_LOAD.finditer(text or ""):
            levels = tuple(sorted(set(re.findall(r"'([\w-]+)", m.group(1)))))
            if len(levels) > 1:
                sets.add(levels)

    for source_level, name in ctx.doors + [(e["level"], e["name"]) for e in ctx.elevators]:
        actor = ctx.actors[(source_level, name)]
        for text in translate_lumps(ctx, source_level, name, actor["lump"]).values():
            add_script(text)
    for region in ctx.regions.values():
        if region["tree"] not in ("target", "camera") or region["level"] not in ctx.port.level_map:
            continue
        tr = ctx.translator(region["level"], region_open_tasks(ctx, region))
        for text in region["scripts"].values():
            add_script(tr.script(text))
        for text in region_overrides(ctx, region).values():
            add_script(text)
    for _, _, levels in list(continue_candidates(ctx)) + list(listed_continues(ctx)):
        if len(set(levels)) > 1:
            sets.add(tuple(sorted(set(levels))))
    for levels in sets:
        for lev in levels:
            if lev in ctx.port.hubs and ctx.port.hubs[lev] not in levels:
                raise ValueError(f"{levels}: {lev} is loaded without its hub {ctx.port.hubs[lev]}")
    return sets


def memory_modes(ctx):
    """Each level's memory mode: the source game's (the largest of its levels'), unless a set of
    levels it's loaded with (load_sets) can't fit in the heap. Then, set by set, the change that
    makes it fit with the fewest sets left that don't: a level loaded next to a large one can
    only be small, for example. Levels with a memory mode in the manifest keep it."""
    target = ctx.port.target
    source_modes = ctx.port.source.memory_modes()
    order = target.MEMORY_ORDER
    fixed = set(ctx.memory)
    modes = dict(ctx.memory)
    for level in ctx.port.levels:
        if level.name not in fixed:
            modes[level.name] = max((source_modes.get(lv, "small-edge") for lv in level.sources),
                                    key=order.index)
    sets = sorted(load_sets(ctx))

    def failing():
        return [s for s in sets if not target.fits([modes[lv] for lv in s])]

    for _ in range(100):
        bad = failing()
        if not bad:
            return {lv: m for lv, m in modes.items() if lv not in fixed}
        options = []
        for lv in bad[0]:
            if lv in fixed:
                continue
            old = modes[lv]
            for alt in order:
                if alt == old or target.CHUNK_COUNT[alt] > target.CHUNK_COUNT[old]:
                    continue
                modes[lv] = alt
                if target.fits([modes[x] for x in bad[0]]):
                    options.append((len(failing()), -target.CHUNK_COUNT[alt], lv, alt))
                modes[lv] = old
        if not options:
            raise ValueError(f"levels {bad[0]} can't fit in the level heap together")
        _, _, lv, alt = min(options)
        others = ", ".join(x for x in bad[0] if x != lv)
        print(f"  memory: {lv} {modes[lv]} -> {alt}, loaded with {others}")
        modes[lv] = alt
    raise ValueError("memory modes: no solution")


# outputs #########################################################################################


def actors_json(actor_list, indent):
    pad = " " * indent
    lines = []
    for i, (comment, actor) in enumerate(actor_list):
        lines.append(f"{pad}// {comment}")
        text = json.dumps(actor, separators=(", ", ": "))
        lines.append(pad + text + ("," if i + 1 < len(actor_list) else ""))
    return "\n".join(lines)


def cameras_json(cameras, indent):
    pad = " " * indent
    return ",\n".join(pad + json.dumps(c, separators=(", ", ": ")) for c in cameras)


def traffic_code(level):
    """The object files of a level's traffic, in link order: the target game's traffic code, taken
    from one of its DGOs ("code_from") but for the objects it skips (the target game's city itself:
    its props, particles, missions, scenes...) or replaces, then the level's own ("code")."""
    cfg = level["traffic"]
    skipped = set(cfg.get("skip", []))
    replaced = cfg.get("replace", {})
    objs = re.findall(r'"([^"]+)\.o"', open(cfg["code_from"]).read())
    code = [replaced.get(o, o) for o in objs if o not in skipped or o in replaced]
    return [f"{o}.o" for o in code] + list(cfg.get("code", []))


def import_fr3(ctx, level):
    out = {
        "game": ctx.port.source.NAME,
        "levels": level.sources,
        "tfrag": True,
        "tie": True,
        "shrub": True,
        "collision": True,
    }
    if "collision_bounds" in level:
        # [xmin, ymin, zmin, xmax, ymax, zmax] in meters: the playable collision with a margin.
        # Unreachable backdrops (kilometers of mountains) would blow the collide hash grid up.
        out["collision_bounds"] = level["collision_bounds"]
    hidden = ctx.port.story.hidden_prototypes(level.sources)
    if hidden:
        out["hide_prototypes"] = hidden
    return out


def write_regions(level, trees):
    path = f"{level.folder}/{level.name}-regions.json"
    write_if_changed(path, json.dumps(trees, indent=2))
    return path


def build_level(ctx, level):
    """A level's actors, models, art groups, code, sprite textures and regions."""
    port = ctx.port
    actor_list, art = make_actors(ctx, level)
    if level.get("ported_actors", True):
        ported = ported_actors(ctx, level)
        actor_list += ported
        # the target game's art group of a ported class that uses one (the manifest's
        # "art_groups": a searchlight, a barge); classes with a rebuilt model bring theirs through
        # custom_models, and the others (a slide, a swinging bar) have none
        art_groups = port.get("art_groups", {})
        for _, actor in ported:
            ag = art_groups.get(actor["etype"])
            if ag and ag not in art:
                art.append(ag)
    prop_code = []
    if "props" in level:
        # the props that are actors, with the target game's classes and models
        prop_list, prop_art, prop_code, prop_counts = props_step.prop_actors(port, level)
        actor_list += prop_list
        art += [ag for ag in prop_art if ag not in art]
        print("  props as actors: " + ", ".join(f"{n} {e}" for e, n in sorted(prop_counts.items())))
    code = []
    if "traffic" in level:
        # the traffic's citizens, guards and vehicles
        art += [ag for ag in level["traffic"].get("art", []) if ag not in art]
        code = [obj for obj in traffic_code(level) if obj not in prop_code]
    code += prop_code + list(level.get("code", []))
    # the source game's particle effects (write_particles): the part spawners of the level, and
    # for a level with particles, <level>-part.gc and the sprite textures of its own texture page
    actor_list += ctx.part_actors.get(level.name, [])
    sprite_textures = ctx.sprite_textures.get(level.name)
    if "particles" in level and f"{level.name}-part.o" not in code:
        code.append(f"{level.name}-part.o")
    models = []
    for model in level.get("models", []):
        build_model(ctx, model_spec(ctx, model))
        models.append(model)
    if "custom_props" in level:
        # props with a model rebuilt from the source game's
        custom_props, prop_models = props_step.custom_prop_actors(port, level)
        actor_list += custom_props
        models += [m for m in prop_models if m not in models]
    models += [m for m in custom_models(ctx, actor_list) if m not in models]
    trees = make_regions(ctx, level)
    return dict(actors=actor_list, art=art, code=code, models=models,
                sprite_textures=sprite_textures, trees=trees)


def write_gd(ctx, level, built, comment):
    gd = [
        f";; {ctx.port.generated}",
        f";; DGO definition file for {level.name}: {comment}.",
        f'("{level.dgo}.DGO"',
        " (",
    ]
    gd += [f'  "{ag}.go"' for ag in built["art"]]
    gd += [f'  "{m}-ag.go"' for m in built["models"]]
    gd += [f'  "{obj}"' for obj in built["code"]]
    gd += [f'  "{level.name}.go"', "  ))", ""]
    write_if_changed(f"{level.folder}/{level.name}.gd", "\n".join(gd))


def write_full_level(ctx, level):
    """A level whose .jsonc is generated whole, with its regions and its .gd."""
    port = ctx.port
    built = build_level(ctx, level)
    title = port.source.TITLE
    region_files = []
    if built["trees"]:
        region_files.append(write_regions(level, built["trees"]))
    water = water_regions(ctx, level)
    if water:
        path = f"{level.folder}/{level.name}-water-regions.json"
        write_if_changed(path, json.dumps(water, indent=2))
        region_files.append(path)
    region_lines = []
    if region_files:
        region_lines = [
            f"  // {title}'s load regions of this level (translated), and its water volumes",
            '  "region_tree_files": ' + json.dumps(region_files) + ",",
        ]
    sprite_lines = []
    if built["sprite_textures"] and built["sprite_textures"]["textures"]:
        sprite_lines = [
            "  // the sprite textures of its particles, as texture page "
            f"{built['sprite_textures']['page']} ({level.name}-part.gc)",
            '  "sprite_textures": ' + json.dumps(built["sprite_textures"]) + ",",
        ]
    mesh_lines = []
    if "mesh" in level:
        mesh_lines = [
            f"  // {title}'s static props that aren't actors here, and its pools' surfaces, as one "
            "mesh (the mesh step)",
            f'  "gltf_file": "{mesh_step.mesh_path(level)}",',
        ]
    nav_lines = []
    if nav_step.city_sources(port, level):
        nav_lines = [
            f"  // {title}'s navigation: its nav meshes and its traffic data (its city-level-info,",
            "  // the nav step)",
            f'  "nav_data": "{nav_step.nav_path(level)}",',
        ]
    what = level.what[0].upper() + level.what[1:]
    lines = [
        "{",
        f"  // {port.generated}",
        f"  // {what},",
        f"  // imported from {title}'s extracted {', '.join(level.sources)}.",
        f'  "long_name": "{level.name}",',
        f'  "iso_name": "{level["iso"]}",',
        f'  "nickname": "{level.nick}",',
        '  "import_fr3": ' + json.dumps(import_fr3(ctx, level)) + ",",
        *mesh_lines,
        *nav_lines,
        *region_lines,
        *sprite_lines,
        f'  "base_id": {level["base_id"]},',
        f'  "base_region_id": {level["base_id"]},',
        f"  // {title}'s fixed cameras of this level (elevator rides, camera regions)",
        '  "cameras": [',
        cameras_json(ctx.cameras.get(level.name, []), 4),
        "  ],",
        *([f"  // models of its custom actors, built by build-actor",
           '  "custom_models": ' + json.dumps(built["models"]) + ","] if built["models"] else []),
        '  "art_groups": ' + json.dumps(built["art"]) + ",",
        '  "actors": [',
        actors_json(built["actors"], 4),
        "  ]",
        "}",
        "",
    ]
    write_if_changed(f"{level.folder}/{level.name}.jsonc", "\n".join(lines))
    write_gd(ctx, level, built, level.what)
    return built


def district_map(ctx, cfg):
    """GOAL data: which level with a hub (a city district) holds each square of a grid over the
    levels' navigation, from the source game's traffic cells (they cover a district's streets): the
    cell squares holding segments, each grid square going to the district with the most segments
    there. cfg: "var" (the prefix of the defines), "cell" (meters)."""
    port = ctx.port
    meter = ctx.meter
    size = cfg["cell"] * meter
    squares = {}  # (ix, iz) -> {level: segments}
    names = []
    for level in port.levels:
        if level.name not in port.hubs:
            continue
        for src in nav_step.city_sources(port, level):
            city = nav_step.decode_city(nav_step.data_blob.Blob(
                os.path.join(port.source.ENTITIES, src + "-city.json")))
            half = city["grid"]["cell_size"][0] / 2
            for cell in city["cells"]:
                if cell["segment_count"] <= 0:
                    continue
                x, _, z, _ = cell["sphere"]
                for ix in range(math.floor((x - half) / size), math.floor((x + half) / size) + 1):
                    for iz in range(math.floor((z - half) / size),
                                    math.floor((z + half) / size) + 1):
                        counts = squares.setdefault((ix, iz), {})
                        counts[level.name] = counts.get(level.name, 0) + cell["segment_count"]
            if level.name not in names:
                names.append(level.name)
    x0 = min(ix for ix, _ in squares)
    z0 = min(iz for _, iz in squares)
    nx = max(ix for ix, _ in squares) - x0 + 1
    nz = max(iz for _, iz in squares) - z0 + 1
    cells = [0] * (nx * nz)
    for (ix, iz), counts in squares.items():
        best = max(sorted(counts), key=lambda lv: counts[lv])
        cells[(ix - x0) + (iz - z0) * nx] = names.index(best) + 1
    # one square more around the streets (sidewalks, alleys): an empty square takes the district
    # most of its 8 neighbors hold
    grown = list(cells)
    for iz in range(nz):
        for ix in range(nx):
            if cells[ix + iz * nx]:
                continue
            near = [cells[jx + jz * nx] for jz in range(max(0, iz - 1), min(nz, iz + 2))
                    for jx in range(max(0, ix - 1), min(nx, ix + 2)) if cells[jx + jz * nx]]
            if near:
                grown[ix + iz * nx] = max(sorted(set(near)), key=near.count)
    cells = grown
    var = cfg["var"]
    rows = [" ".join(str(c) for c in cells[i:i + 40]) for i in range(0, len(cells), 40)]
    return [
        f";; the city's districts, and which of them holds each {cfg['cell']}m square of the city's "
        "streets (1 + its",
        f";; index in {var}-names*, 0: none), from {port.source.TITLE}'s traffic cells. The grid: "
        "x and z of its first",
        ";; square (game units), square size, squares per row.",
        f"(define {var}-names* (new 'static 'boxed-array :type symbol " +
        " ".join(f"'{n}" for n in names) + "))",
        "",
        f"(define {var}-grid* (new 'static 'vector :x {x0 * size} :y {z0 * size} :z {size} "
        f":w {float(nx)}))",
        "",
        f"(define {var}-cells* (new 'static 'boxed-array :type uint8",
        *["  " + r for r in rows],
        "  ))",
        "",
    ]


def write_level_info(ctx, chosen):
    port = ctx.port
    cfg = port["level_info"]
    defaults = port.get("level_defaults", {}).get("level_info", {})
    stem = cfg["file"].rsplit("/", 1)[-1][: -len(".gc")]
    out = [
        ";;-*-Lisp-*-",
        "(in-package goal)",
        "",
        f";; name: {stem}.gc",
        f";; name in dgo: {stem}",
        ";; dgos: GAME",
        "",
        *port.generated_lines(),
        *[f";; {line}" for line in cfg.get("comment", [])],
        "",
    ]
    if "levels_var" in cfg:
        out += [f";; {cfg['levels_var_comment']}",
                f"(define {cfg['levels_var']} '(" + " ".join(lv.name for lv in port.levels) + "))",
                ""]
    if "hubs_var" in cfg:
        out += [f";; {cfg['hubs_var_comment']}",
                f"(define {cfg['hubs_var']} '(" + " ".join(f"({lv} . {hub})" for lv, hub in
                                                           port.hubs.items()) + "))",
                ""]
    if "district_map" in cfg:
        out += district_map(ctx, cfg["district_map"])
    if ctx.sound and ctx.sound.voices:
        out += [f";; {ctx.title}'s voice lines the mod plays (packed by the build: "
                "scripts/level_port/steps/sound.py)", *ctx.sound.voice_defines()]
    for level in port.levels:
        info = {**defaults, **level.get("level_info", {})}
        conts = [continue_point(ctx, lv, name, src) for lv, name, src in chosen
                 if lv == level.name]
        memory = ctx.memory[level.name]
        ocean = level.get("ocean")
        flags = " ".join(["sky"] * bool(level.get("sky")) +
                         ["ocean-near-translucent"] * bool(ocean) + level.get("level_flags", []))
        if "comment" in info:
            comment = "\n".join(f";; {line}" for line in info["comment"])
        else:
            what = level.what[0].upper() + level.what[1:]
            comment = (f";; {what} ({level.folder}), {port.source.TITLE}'s "
                       f"{', '.join(level.sources)}.\n"
                       f";; memory: {memory} ({port.source.TITLE}'s where the level heap allows, "
                       "see the\n;; level port's memory_modes).")
        out.append(port.target.level_load_info(
            level.name, level.nick, int(level["index"], 0), memory, flags or None,
            info.get("mood", "update-mood-{name}").format(name=level.name), conts,
            [tuple(cb) for cb in info.get("callbacks", [])],
            (ocean if isinstance(ocean, str) else port.get("ocean_map") if ocean else None),
            comment, info["draw_priority"], bool(level.get("sky")),
            info.get("part_engine_max", ctx.part_engine_max.get(level.name, 0)),
            *level_sound(ctx, level)))
    for spec in port["continues"].get("target_continues", []):
        out.append(target_continue(ctx, spec))
    write_if_changed(cfg["file"], "\n".join(out))
    print(f"  wrote {cfg['file']} ({len(chosen)} continues)")


def level_sound(ctx, level):
    """A level's :music-bank and :extra-sound-bank (GOAL text): the music of its first source level
    that has one, and for a hub the target game banks loaded with the source game's."""
    if not ctx.sound:
        return "#f", "#f"
    music = ctx.port.source.music_banks()
    names = [music[src] for src in level.sources if src in music]
    extra = ctx.sound.extra_sound_bank() if level.name in ctx.port.hubs.values() else "#f"
    return (f"'{ctx.sound.music_bank(names[0])}" if names else "#f"), extra


def write_build_file(ctx, built_levels):
    """The goalc build steps of the levels (the manifest's "build" file, loaded by the target
    game's game.gp): each level's models (build-actor), level code (goal-src: the objects of its
    DGO found in the levels' code folder) and the level itself (build-custom-level, and its DGO)."""
    port = ctx.port
    cfg = port["build"]
    default_deps = cfg.get("default_deps", [])
    code_deps = cfg.get("code_deps", {})
    src_root = f"goal_src/{port.target.NAME}/"
    assert port.code_dir.startswith(src_root), port.code_dir
    code_rel = port.code_dir[len(src_root):]
    lines = [
        ";;-*-Lisp-*-",
        "",
        *port.generated_lines(),
        f";; The goalc build steps of its levels, loaded by goal_src/{port.target.NAME}/game.gp:",
        ";; each level's models (build-actor), level code (goal-src) and the level with its DGO.",
    ]
    declared = set()
    for level, built in built_levels:
        lines += ["", f";; {level.name}: {level.what} ({', '.join(level.sources)})"]
        for model in built["models"]:
            if model not in declared:
                declared.add(model)
                lines.append(f'(build-actor "{model}" :gen-mesh #t)')
        for obj in built["code"]:
            stem = obj[: -len(".o")] if obj.endswith(".o") else obj
            if stem in declared or not os.path.exists(f"{port.code_dir}/{stem}.gc"):
                continue
            declared.add(stem)
            deps = " ".join(f'"{d}"' for d in code_deps.get(stem, default_deps))
            lines.append(f'(goal-src "{code_rel}/{stem}.gc"' + (f" {deps}" if deps else "") + ")")
        lines.append(f'(build-custom-level "{level.name}")')
        lines.append(f'(custom-level-cgo "{level.dgo}.DGO" "{level.name}/{level.name}.gd")')
    if ctx.sound:
        lines += ctx.sound.build_lines()
    write_if_changed(cfg["file"], "\n".join(lines) + "\n")
    print(f"  wrote {cfg['file']} ({len(built_levels)} levels)")


def write_particles(ctx):
    """The particles of the levels with a "particles" block: <level>-part.gc, the part spawners (in
    the levels holding their source levels) and the sprite textures."""
    alloc = particles.Allocator(ctx.port)
    # the levels with a fixed texture page first: the "auto" ones are chosen around them
    with_particles = [lv for lv in ctx.port.levels if "particles" in lv]
    for level in sorted(with_particles, key=lambda lv: lv["particles"]["page"] == "auto"):
        by_level, sprite_textures, engine_max, stats = particles.write_level(ctx.port, level, alloc)
        print(f"  {level.name} particles: {stats}")
        for lv, actors in by_level.items():
            ctx.part_actors.setdefault(lv, []).extend(actors)
        ctx.part_engine_max.update(engine_max)
        ctx.sprite_textures[level.name] = sprite_textures


def run(port):
    ctx = Context(port)
    ctx.memory.update(memory_modes(ctx))
    print("  memory: " + ", ".join(f"{lv.name} {ctx.memory[lv.name]}" for lv in port.levels))
    chosen = select_continues(ctx)
    check_pairs(ctx)
    write_particles(ctx)
    built_levels = []
    for level in port.levels:
        built = write_full_level(ctx, level)
        built_levels.append((level, built))
        nreg = sum(len(t["regions"]) for t in built["trees"].values())
        print(f"  {level.name}: {len(built['actors'])} actors, {nreg} regions "
              f"({', '.join(level.sources)})")
    write_level_info(ctx, chosen)
    if "build" in port.data:
        write_build_file(ctx, built_levels)
