"""Jak 2's city props that are actors in havenj2, like in Jak 2.

Jak 3's own Haven City reuses Jak 2's market props and farm crops: their art groups ship in Jak 3's
DGOs (the Spargus market WCA/WCB, the farms CFA/CFB) and their code in Jak 3's level code, already
compiled (out/jak3/obj). So Jak 2's actors are placed with Jak 3's classes and models:
  - the market crates, baskets, pots and sacks (ctymark-obs.o: Jak 3's market-object, a crate
    child): solid, and broken by any attack, with their debris,
  - the fruit stands (ctymark-obs.o: fruit-stand),
  - the farm crops and sprinkler barrels (ctyfarm-obs.o).
The other props stay part of the background (gen_havenj2_mesh.py).

Used by gen_havenj2_links.py, which writes them into havenj2.jsonc and havenj2.gd.
"""

import json
import math
import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jak2_actors  # noqa: E402
from gen_util import write_if_changed  # noqa: E402


# Jak 2 etype -> (Jak 3 etype, Jak 3 art group). The art is extracted from the Jak 3 ISO into
# havenj2's fr3 by the level builder and its .go goes in havenj2.gd.
ACTOR_PROPS = {
    "market-crate": ("market-crate", "market-crate-ag"),
    "market-basket-a": ("market-basket-a", "market-basket-a-ag"),
    "market-basket-b": ("market-basket-b", "market-basket-b-ag"),
    "market-sack-a": ("market-sack-a", "market-sack-a-ag"),
    "market-sack-b": ("market-sack-b", "market-sack-b-ag"),
    "cty-fruit-stand": ("fruit-stand", "cty-fruit-stand-ag"),
    # the crops: Jak 3's art (it still has Jak 2's burst models), Jak 2's behavior (solid, shaken
    # by hits, burst by strong ones): havenj2-farm.gc
    "farm-marrow": ("hj2-farm-marrow", "farm-marrow-ag"),
    "farm-beetree": ("hj2-farm-beetree", "farm-beetree-ag"),
    "farm-chilirots": ("hj2-farm-chilirots", "farm-chilirots-ag"),
    "farm-cabbage": ("hj2-farm-cabbage", "farm-cabbage-ag"),
    "farm-small-cabbage": ("hj2-farm-small-cabbage", "farm-small-cabbage-ag"),
    "farm-sprinkler-barrels": ("farm-sprinkler-barrels", "farm-sprinkler-barrels-ag"),
}
# Jak 3 level code holding those classes, compiled with Jak 3 (listed in havenj2.gd, before the
# level's own code)
CODE = ["ctymark-obs-h.o", "ctymark-obs.o", "ctyfarm-obs.o"]
# Jak 2 turned its crops to a random angle when they spawned (farm-marrow etc. init-from-entity!):
# the angle is set here, the same on every run.
RANDOM_YAW = {"farm-marrow", "farm-beetree", "farm-chilirots", "farm-cabbage", "farm-small-cabbage"}
# actor ids of havenj2's props, past every custom level's own ids
BASE_AID = 40000


def r4(x):
    return round(x, 4)


def yaw_quat(name):
    """A fixed pseudo random rotation around y, from the actor name."""
    angle = (zlib.crc32(name.encode()) % 3600) / 10.0
    half = math.radians(angle) / 2
    return [0.0, r4(math.sin(half)), 0.0, r4(math.cos(half))]


def city_prop_actors(city_levels):
    """(comment, actor) list, art groups and code objects for the props of the city levels."""
    out = []
    art = []
    counts = {}
    for level in city_levels:
        for actor in jak2_actors.level_actors(level):
            etype = actor["etype"]
            if etype not in ACTOR_PROPS:
                continue
            jak3_etype, ag = ACTOR_PROPS[etype]
            if ag not in art:
                art.append(ag)
            name = actor["lump"]["name"]
            lump = {"name": name}
            if "vis-dist" in actor["lump"]:
                lump["vis-dist"] = ["float", float(actor["lump"]["vis-dist"])]
            trans = [r4(x) for x in actor["trans"][:3]]
            quat = yaw_quat(name) if etype in RANDOM_YAW else [r4(x) for x in actor["quat"]]
            out.append((f"Jak 2's {name} ({level})", {
                "trans": trans,
                "etype": jak3_etype,
                "aid": BASE_AID + len(out),
                "game_task": 0,
                "quat": quat,
                "bsphere": trans + [r4(actor["bsphere"][3])],
                "lump": lump,
            }))
            counts[jak3_etype] = counts.get(jak3_etype, 0) + 1
    return out, art, list(CODE), counts


# custom models ###################################################################################
# Props Jak 3 has no art for: their model is rebuilt from Jak 2's ripped one by build-actor
# (goal_src/jak3/game.gp) and placed with a hj2- class of havenj2-obs.gc.

MODELS_DIR = "custom_assets/jak3/models/custom_levels"
# Jak 2 etype -> (our etype, the rip, the primitives kept). Jak 2's propaganda speaker has three
# looks switched with setup-masks (intact: primitives 3 and 4, damaged: 1 and 2, broken: 0, the
# stump); build-actor models have no mask table, so each look is a model of its own
# (CUSTOM_PROP_LOOKS), drawn by a child process (havenj2-obs.gc).
CUSTOM_PROPS = {
    "propa": ("hj2-propa", "decompiler_out/jak2/levels/ctywide/propa-lod0.glb", [3, 4]),
}
CUSTOM_PROP_LOOKS = {
    "hj2-propa": [("hj2-propa-damaged", [1, 2]), ("hj2-propa-broken", [0])],
}
# actor ids of the custom props
CUSTOM_BASE_AID = 44000


GLB_SIZES = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def load_glb(path):
    """(gltf json, read) of a .glb file: read(accessor index) is the accessor's values, as tuples."""
    import struct
    data = open(path, "rb").read()
    json_len = struct.unpack_from("<I", data, 12)[0]
    gltf = json.loads(data[20:20 + json_len])
    bin_start = 20 + json_len + 8
    bin_len = struct.unpack_from("<I", data, 20 + json_len)[0]
    blob = bytes(data[bin_start:bin_start + bin_len])
    fmts = {5126: ("f", 4), 5125: ("I", 4), 5123: ("H", 2), 5121: ("B", 1)}

    def read(idx):
        acc = gltf["accessors"][idx]
        view = gltf["bufferViews"][acc["bufferView"]]
        fmt, size = fmts[acc["componentType"]]
        n = GLB_SIZES[acc["type"]]
        stride = view.get("byteStride", size * n)
        base = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
        return [struct.unpack_from("<%d%s" % (n, fmt), blob, base + i * stride)
                for i in range(acc["count"])]

    return gltf, read


def mat_from_gltf(m):
    """A glTF matrix (16 floats, column major) as rows."""
    return [[m[c * 4 + r] for c in range(4)] for r in range(4)]


def mat_mul(a, b):
    return [[sum(a[r][k] * b[k][c] for k in range(4)) for c in range(4)] for r in range(4)]


def mat_inverse(m):
    """Gauss-Jordan inverse of a 4x4 matrix (rows)."""
    a = [list(row) + [1.0 if i == j else 0.0 for j in range(4)] for i, row in enumerate(m)]
    for col in range(4):
        pivot = max(range(col, 4), key=lambda r: abs(a[r][col]))
        a[col], a[pivot] = a[pivot], a[col]
        f = a[col][col]
        a[col] = [x / f for x in a[col]]
        for r in range(4):
            if r != col and a[r][col] != 0.0:
                g = a[r][col]
                a[r] = [x - g * y for x, y in zip(a[r], a[col])]
    return [row[4:] for row in a]


def mat_decompose(m):
    """(translation, rotation quaternion x y z w, scale) of an affine matrix (rows)."""
    trans = [m[0][3], m[1][3], m[2][3]]
    cols = [[m[r][c] for r in range(3)] for c in range(3)]
    scale = [math.sqrt(sum(x * x for x in col)) or 1.0 for col in cols]
    r = [[cols[c][row] / scale[c] for c in range(3)] for row in range(3)]
    tr = r[0][0] + r[1][1] + r[2][2]
    if tr > 0:
        s4 = math.sqrt(tr + 1.0) * 2
        q = [(r[2][1] - r[1][2]) / s4, (r[0][2] - r[2][0]) / s4, (r[1][0] - r[0][1]) / s4, 0.25 * s4]
    elif r[0][0] > r[1][1] and r[0][0] > r[2][2]:
        s4 = math.sqrt(1.0 + r[0][0] - r[1][1] - r[2][2]) * 2
        q = [0.25 * s4, (r[0][1] + r[1][0]) / s4, (r[0][2] + r[2][0]) / s4, (r[2][1] - r[1][2]) / s4]
    elif r[1][1] > r[2][2]:
        s4 = math.sqrt(1.0 + r[1][1] - r[0][0] - r[2][2]) * 2
        q = [(r[0][1] + r[1][0]) / s4, 0.25 * s4, (r[1][2] + r[2][1]) / s4, (r[0][2] - r[2][0]) / s4]
    else:
        s4 = math.sqrt(1.0 + r[2][2] - r[0][0] - r[1][1]) * 2
        q = [(r[0][2] + r[2][0]) / s4, (r[1][2] + r[2][1]) / s4, 0.25 * s4, (r[1][0] - r[0][1]) / s4]
    n = math.sqrt(sum(x * x for x in q)) or 1.0
    return trans, [x / n for x in q], scale


def write_actor_glb(src, name, keep_prims, collide=None, anims=None):
    """<name>.glb for build-actor from a ripped Jak 2 model: the kept primitives with only the
    vertices they use (the rip shares one buffer), its first animation renamed <name>-idle (the
    name build-actor's def-actor looks up), no collision from the render mesh, and invisible
    collision meshes (build-actor's gen-mesh makes one collide mesh per node, in order). collide:
      None: one box around the model,
      {"hull": y_min}: the convex hull of the model's vertices above y_min (None: all), and below
        "y_max" when given, for the models of a single joint (convex_hull.py),
      a list of meshes, each a list of boxes (lo, hi) in the model's space, or {"hull": y_min,
        "joint": name}: the hull of that joint's vertices (its part of the model), in the joint's
        space (the game moves a collide mesh with the joint its prim names: transform index =
        joint index + 1).
    anims: the animations to keep instead, [(rip, animation, our name)], from rips of models with
    the same joints (a rip's joint nodes are its joints + 1): a model whose animations Jak 2 keeps
    in another model's art group."""
    import struct
    gltf, read = load_glb(src)
    sizes = GLB_SIZES

    views, accessors = [], []
    out_blob = bytearray()

    def add(values, fmt, gltf_type, component, minmax=False, target=34962):
        raw = b"".join(struct.pack("<" + fmt, *v) for v in values)
        views.append({"buffer": 0, "byteOffset": len(out_blob), "byteLength": len(raw),
                      **({"target": target} if target else {})})
        out_blob.extend(raw + b"\0" * ((4 - len(raw) % 4) % 4))
        acc = {"bufferView": len(views) - 1, "componentType": component, "count": len(values),
               "type": gltf_type}
        if minmax:
            acc["min"] = [min(v[i] for v in values) for i in range(len(values[0]))]
            acc["max"] = [max(v[i] for v in values) for i in range(len(values[0]))]
        accessors.append(acc)
        return len(accessors) - 1

    mesh = gltf["meshes"][0]
    kept = [p for i, p in enumerate(mesh["primitives"]) if keep_prims is None or i in keep_prims]
    attrs = kept[0]["attributes"]
    all_idx = [read(p["indices"]) for p in kept]
    used = sorted({i[0] for idx in all_idx for i in idx})
    remap = {old: new for new, old in enumerate(used)}
    kinds = {"POSITION": ("3f", "VEC3", 5126), "NORMAL": ("3f", "VEC3", 5126),
             "TEXCOORD_0": ("2f", "VEC2", 5126), "COLOR_0": ("4f", "VEC4", 5126),
             "JOINTS_0": ("4B", "VEC4", 5121), "WEIGHTS_0": ("4f", "VEC4", 5126)}
    new_attrs = {}
    columns = {}
    for key, (fmt, typ, comp) in kinds.items():
        values = read(attrs[key])
        columns[key] = [values[i] for i in used]
        new_attrs[key] = add(columns[key], fmt, typ, comp, minmax=key == "POSITION")
    prims = []
    for prim, idx in zip(kept, all_idx):
        prims.append({"attributes": dict(new_attrs),
                      "indices": add([(remap[i[0]],) for i in idx], "I", "SCALAR", 5125,
                                     target=34963),
                      "material": prim["material"], "mode": 4})

    pts = columns["POSITION"]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]

    def box_mesh(mesh_name, boxes):
        corners, normals, indices = [], [], []
        for b_lo, b_hi in boxes:
            base = len(corners)
            center = [(b_lo[i] + b_hi[i]) / 2 for i in range(3)]
            for p in [(x, y, z) for x in (b_lo[0], b_hi[0]) for y in (b_lo[1], b_hi[1])
                      for z in (b_lo[2], b_hi[2])]:
                d = [p[i] - center[i] for i in range(3)]
                n = math.sqrt(sum(c * c for c in d)) or 1.0
                corners.append(p)
                normals.append(tuple(c / n for c in d))
            indices += [(base + i,) for a, b, c, d in quads for i in (a, b, c, a, c, d)]
        return {"name": mesh_name, "primitives": [{
            "attributes": {"POSITION": add(corners, "3f", "VEC3", 5126, minmax=True),
                           "NORMAL": add(normals, "3f", "VEC3", 5126),
                           "COLOR_0": add([(0.5, 0.5, 0.5, 1.0)] * len(corners), "4f", "VEC4",
                                          5126)},
            "indices": add(indices, "I", "SCALAR", 5125, target=34963),
            "mode": 4}]}

    skin = dict(gltf["skins"][0])
    joint_names = [gltf["nodes"][j].get("name") for j in skin["joints"]]

    def joint_points(joint):
        """The vertices mostly weighted to a joint, in its space (its inverse bind matrix, column
        major, applied)."""
        k = joint_names.index(joint)
        m = read(skin["inverseBindMatrices"])[k]
        out = []
        for p, j, w in zip(pts, columns["JOINTS_0"], columns["WEIGHTS_0"]):
            if j[max(range(4), key=lambda i: w[i])] == k:
                out.append(tuple(m[r] * p[0] + m[4 + r] * p[1] + m[8 + r] * p[2] + m[12 + r]
                                 for r in range(3)))
        return out

    def hull_mesh(mesh_name, spec):
        import convex_hull
        y_min = spec["hull"]
        y_max = spec.get("y_max")
        points = joint_points(spec["joint"]) if "joint" in spec else pts
        verts, tris = convex_hull.hull_mesh(
            [tuple(p) for p in points
             if (y_min is None or p[1] >= y_min) and (y_max is None or p[1] <= y_max)])
        center = [sum(v[i] for v in verts) / len(verts) for i in range(3)]
        normals = []
        for v in verts:
            d = [v[i] - center[i] for i in range(3)]
            n = math.sqrt(sum(c * c for c in d)) or 1.0
            normals.append(tuple(c / n for c in d))
        return {"name": mesh_name, "primitives": [{
            "attributes": {"POSITION": add(verts, "3f", "VEC3", 5126, minmax=True),
                           "NORMAL": add(normals, "3f", "VEC3", 5126),
                           "COLOR_0": add([(0.5, 0.5, 0.5, 1.0)] * len(verts), "4f", "VEC4",
                                          5126)},
            "indices": add([(i,) for t in tris for i in t], "I", "SCALAR", 5125, target=34963),
            "mode": 4}]}

    if isinstance(collide, dict):
        collide_meshes = [hull_mesh(f"{name}-collide-0", collide)]
    else:
        collide_meshes = [hull_mesh(f"{name}-collide-{i}", mesh) if isinstance(mesh, dict)
                          else box_mesh(f"{name}-collide-{i}", mesh)
                          for i, mesh in enumerate(collide or [[(lo, hi)]])]

    def copy_anim(anim, anim_gltf, anim_read, new_name):
        samplers = []
        for s in anim["samplers"]:
            out_acc = anim_gltf["accessors"][s["output"]]
            samplers.append({"input": add(anim_read(s["input"]), "f", "SCALAR", 5126, minmax=True,
                                          target=None),
                             "output": add(anim_read(s["output"]), "%df" % sizes[out_acc["type"]],
                                           out_acc["type"], 5126, target=None),
                             "interpolation": s.get("interpolation", "LINEAR")})
        return {"name": new_name, "channels": anim["channels"], "samplers": samplers}

    def rest_pose_anim(new_name):
        """One frame holding every joint at its bind pose, for a rip without animations: build-actor
        needs one (def-actor looks up <name>-idle). A joint's pose relative to its parent is
        IBM(parent) x inverse(IBM(joint))."""
        joints = skin["joints"]
        ibms = [mat_from_gltf(m) for m in read(skin["inverseBindMatrices"])]
        parent = {}
        for j, node_idx in enumerate(joints):
            for child in gltf["nodes"][node_idx].get("children", []):
                if child in joints:
                    parent[joints.index(child)] = j
        time = add([(0.0,)], "f", "SCALAR", 5126, minmax=True, target=None)
        channels, samplers = [], []
        for j, node_idx in enumerate(joints):
            local = mat_inverse(ibms[j])
            if j in parent:
                local = mat_mul(ibms[parent[j]], local)
            trans, rot, scale = mat_decompose(local)
            for path, value, fmt, kind in (("translation", trans, "3f", "VEC3"),
                                           ("rotation", rot, "4f", "VEC4"),
                                           ("scale", scale, "3f", "VEC3")):
                samplers.append({"input": time,
                                 "output": add([tuple(value)], fmt, kind, 5126, target=None),
                                 "interpolation": "LINEAR"})
                channels.append({"sampler": len(samplers) - 1,
                                 "target": {"node": node_idx, "path": path}})
        return {"name": new_name, "channels": channels, "samplers": samplers}

    if anims:
        out_anims = []
        for rip, anim_name, new_name in anims:
            anim_gltf, anim_read = load_glb(rip)
            anim = next(a for a in anim_gltf["animations"] if a["name"] == anim_name)
            out_anims.append(copy_anim(anim, anim_gltf, anim_read, new_name))
    else:
        out_anims = [copy_anim(anim, gltf, read, f"{name}-idle")
                     for anim in gltf.get("animations", [])[:1]]
        if not out_anims and "inverseBindMatrices" in skin:
            out_anims = [rest_pose_anim(f"{name}-idle")]

    if "inverseBindMatrices" in skin:
        skin["inverseBindMatrices"] = add(read(skin["inverseBindMatrices"]), "16f", "MAT4", 5126,
                                          target=None)
    nodes = [dict(n) for n in gltf["nodes"]]
    mesh_node = next(i for i, n in enumerate(nodes) if "mesh" in n)
    nodes[mesh_node]["name"] = f"{name}-lod0"
    nodes[mesh_node]["extras"] = {"set_collision": 1, "ignore": 1}
    scene_nodes = list(gltf["scenes"][gltf.get("scene", 0)]["nodes"])
    for i, mesh in enumerate(collide_meshes):
        nodes.append({"name": mesh["name"], "mesh": 1 + i, "extras": {"set_invisible": 1}})
        scene_nodes.append(len(nodes) - 1)
    out = {
        "asset": {"version": "2.0", "generator": "gen_havenj2_props.py"},
        "scene": 0,
        "scenes": [{"nodes": scene_nodes}],
        "nodes": nodes,
        "meshes": [{"name": f"{name}-lod0", "primitives": prims}] + collide_meshes,
        "skins": [skin],
        "animations": out_anims,
        "materials": gltf["materials"],
        "textures": gltf["textures"],
        "samplers": gltf.get("samplers", []),
        "images": gltf["images"],
        "buffers": [{"byteLength": len(out_blob)}],
        "bufferViews": views,
        "accessors": accessors,
    }
    js = json.dumps(out, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    path = os.path.join(MODELS_DIR, name + ".glb")
    write_if_changed(path, struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(out_blob))
                     + struct.pack("<II", len(js), 0x4E4F534A) + js
                     + struct.pack("<II", len(out_blob), 0x004E4942) + bytes(out_blob))
    return len(used), [round(v, 2) for v in lo], [round(v, 2) for v in hi]


def city_custom_prop_actors(city_levels):
    """(comment, actor) list and model names of the props with a custom model (CUSTOM_PROPS)."""
    out = []
    models = []
    for etype, (ours, src, prims) in CUSTOM_PROPS.items():
        write_actor_glb(src, ours, prims)
        models.append(ours)
        for look, look_prims in CUSTOM_PROP_LOOKS.get(ours, []):
            write_actor_glb(src, look, look_prims)
            models.append(look)
    for level in city_levels:
        for actor in jak2_actors.level_actors(level):
            if actor["etype"] not in CUSTOM_PROPS:
                continue
            name = actor["lump"]["name"]
            lump = {"name": name}
            if "vis-dist" in actor["lump"]:
                lump["vis-dist"] = ["float", float(actor["lump"]["vis-dist"])]
            trans = [r4(x) for x in actor["trans"][:3]]
            out.append((f"Jak 2's {name} ({level})", {
                "trans": trans,
                "etype": CUSTOM_PROPS[actor["etype"]][0],
                "aid": CUSTOM_BASE_AID + len(out),
                "game_task": 0,
                "quat": [r4(x) for x in actor["quat"]],
                "bsphere": trans + [r4(actor["bsphere"][3])],
                "lump": lump,
            }))
    return out, models
