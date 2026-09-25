#!/usr/bin/env python3
"""havenj2-mesh.glb: what havenj2 adds to the background merged from Jak 2's .fr3 files.

  - Jak 2's static props of the city that aren't actors here (yakows, street lamps, mission
    kiosks...). In Jak 2 they are actors; here they are part of the background, placed like Jak 2's
    actors: their ripped model (lod0) is
    transformed into world space and lit by the city's time of day. Jak 2 lights them per vertex
    (merc): an ambient color plus four sun directions (*mood-direction-table*). The background
    palettes follow the same layout (0 ambient, 1-4 the sun directions weighted by the hour), so
    each vertex gets palette 0 = ambient, palette 1-4 = its normal facing each sun direction, times
    the model's own vertex shading. Solid props also get an invisible collision box.
  - the pool and fountain surfaces of the palace plaza and the stadium (gen_havenj2_water.py),
    translucent, without collision, lit the same way.

The level builder turns the visible meshes into tfrag trees (by material), and the boxes into
collision.

Inputs: decompiler_out/jak2/entities/<level>-actors.json, the ripped models in
decompiler_out/jak2/levels/<level>/ (Jak 2 extraction with rip_levels enabled).

usage: python custom_assets/jak3/levels/havenj2/gen_havenj2_mesh.py   (from the project root)
"""

import hashlib
import json
import math
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_havenj2_water as water  # noqa: E402
import jak2_actors  # noqa: E402

ROOT = water.ROOT
RIPS = water.RIPS
OUT = os.path.join(HERE, "havenj2-mesh.glb")

# the levels merged into havenj2 (gen_havenj2_links.CITY_LEVELS)
CITY_LEVELS = [
    "ctywide", "ctysluma", "ctyslumb", "ctyslumc", "ctyport", "ctymarka", "ctymarkb", "ctyinda",
    "ctyindb", "ctygena", "ctygenb", "ctygenc", "ctyfarma", "ctyfarmb", "ctypal", "stadium",
]

# Jak 2 actor types kept as background props, with their collision:
#   "box":    the model's bounding box (oriented like the actor)
#   "post":   a thin column at the model's center, for poles with a head (street lamps)
#   None:     no collision (plants Jak walks through, props out of reach)
# material: the collision surface (Jak 1 pat material numbers, converted by the builder)
WOOD, METAL, STONE = 6, 16, 0
PROPS = {
    "yakow": ("box", STONE),
    # the streets
    "ctyn-lamp": ("post", METAL),
    "burning-bush": (None, None),
    "lurker-pipe-lid": (None, None),
    "baron-statue": (None, None),
    "barons-ship-lores": (None, None),
}
# Not kept: the market props, the farm crops and the propaganda speakers, which are actors
# (gen_havenj2_props.py), the
# force-field walls (security-wall, stadium-barrier: open or shut with the story), the searchlights
# and the guard turrets (they move, the turrets hide underground), the palace plaza after its
# destruction (ctypal-broke-wall, ctypal-baron-statue-broken), and the cutscene or mission actors
# (barge, air-train, farthy, mecha-daxter).

POST_WIDTH = 0.6  # meters
# Jak 2's sun directions (mood-tables.gc *mood-direction-table*), palettes 1-4
SUN_DIRECTIONS = [
    (0.906, 0.397, 0.143),
    (0.5, 0.814, 0.296),
    (-0.5, 0.814, 0.296),
    (-0.906, 0.397, 0.143),
]
# palette scales, for a vertex of full shading (merc vertex color 0.5): the city's background
# palettes have their ambient around 110/255 and their sun palettes up to about 100
AMBIENT = 110.0
SUN = 100.0


def normalize(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / n for c in v)


def palettes(shade, normal):
    """The 8 time of day colors (rgba bytes, 32 values) of a vertex: shade is the merc vertex color
    (0.5 = full), normal its world normal."""
    out = []
    k = [c * 2.0 for c in shade[:3]]
    weights = [AMBIENT] + [SUN * max(0.0, sum(normal[i] * d[i] for i in range(3)))
                           for d in SUN_DIRECTIONS] + [0.0, 0.0, 0.0]
    for w in weights:
        out += [max(0, min(255, int(round(w * c)))) for c in k] + [128]
    return out


# models ##########################################################################################


def find_rip(etype):
    for level in CITY_LEVELS + sorted(os.listdir(RIPS)):
        path = os.path.join(RIPS, level, etype + "-lod0.glb")
        if os.path.exists(path):
            return path
    return None


def load_model(etype):
    """A ripped model in its bind pose: vertices and one triangle list per material."""
    gltf, data, bin_start = water.read_glb(find_rip(etype))
    prims = []
    all_used = set()
    cache = {}

    def acc(i):
        if i not in cache:
            cache[i] = water.read_accessor(gltf, data, bin_start, i)
        return cache[i]

    for prim in gltf["meshes"][0]["primitives"]:
        mat = gltf["materials"][prim["material"]]
        pbr = mat.get("pbrMetallicRoughness", {})
        if "baseColorTexture" not in pbr:
            continue
        tex = gltf["textures"][pbr["baseColorTexture"]["index"]]
        idx = acc(prim["indices"])
        attrs = prim["attributes"]
        prims.append(dict(
            idx=idx, pos=acc(attrs["POSITION"]), nrm=acc(attrs["NORMAL"]),
            uv=acc(attrs["TEXCOORD_0"]), col=acc(attrs["COLOR_0"]),
            image=gltf["images"][tex["source"]]["uri"],
            sampler=gltf["samplers"][tex["sampler"]] if "sampler" in tex else None,
            alpha=mat.get("alphaMode", "OPAQUE"), cutoff=mat.get("alphaCutoff", 0.5),
            name=mat.get("name", "")))
        all_used |= set(idx)
    pos = prims[0]["pos"]
    points = [pos[i] for i in all_used]
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    return dict(prims=prims, lo=lo, hi=hi)


def actor_transform(actor):
    """The actor's rotation and position (meters): model space -> world space. Like Jak 2
    (process-drawable-from-entity!), the scale lump is ignored: the props are drawn at their size."""
    q = actor["quat"]
    t = actor["trans"][:3]

    def point(p):
        r = water.qrot(q, p)
        return tuple(r[i] + t[i] for i in range(3))

    def normal(n):
        return normalize(water.qrot(q, n))

    return point, normal


# glb writing #####################################################################################


class Glb:
    def __init__(self):
        self.blob = bytearray()
        self.views = []
        self.accessors = []
        self.images = {}      # data uri -> image index
        self.samplers = []
        self.textures = {}    # (image, sampler) -> texture index
        self.materials = {}   # key -> material index
        self.material_list = []

    def add(self, values, fmt, gltf_type, component, minmax=False, target=34962,
            normalized=False):
        raw = b"".join(struct.pack("<" + fmt, *v) for v in values)
        self.views.append({"buffer": 0, "byteOffset": len(self.blob), "byteLength": len(raw),
                           "target": target})
        self.blob.extend(raw + b"\0" * ((4 - len(raw) % 4) % 4))
        a = {"bufferView": len(self.views) - 1, "componentType": component,
             "count": len(values), "type": gltf_type}
        if normalized:
            a["normalized"] = True
        if minmax:
            a["min"] = [min(v[i] for v in values) for i in range(len(values[0]))]
            a["max"] = [max(v[i] for v in values) for i in range(len(values[0]))]
        self.accessors.append(a)
        return len(self.accessors) - 1

    def material(self, image, sampler, alpha, cutoff, name):
        key = (hashlib.sha1(image.encode()).hexdigest(), json.dumps(sampler, sort_keys=True), alpha,
               cutoff)
        if key in self.materials:
            return self.materials[key]
        if image not in self.images:
            self.images[image] = len(self.images)
        s = sampler or {"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}
        if s not in self.samplers:
            self.samplers.append(s)
        tkey = (self.images[image], self.samplers.index(s))
        if tkey not in self.textures:
            self.textures[tkey] = len(self.textures)
        mat = {"name": name, "alphaMode": alpha,
               "pbrMetallicRoughness": {"baseColorTexture": {"index": self.textures[tkey]},
                                        "metallicFactor": 0.0}}
        if alpha == "MASK":
            mat["alphaCutoff"] = cutoff
        if alpha == "BLEND":
            mat["doubleSided"] = True
        self.material_list.append(mat)
        self.materials[key] = len(self.material_list) - 1
        return self.materials[key]

    def colored_primitive(self, verts, tris, material):
        """verts: (pos, nrm, uv, 32 palette bytes)"""
        palette_names = ["_SUNRISE", "_MORNING", "_NOON", "_AFTERNOON", "_SUNSET", "_TWILIGHT",
                         "_EVENING", "_GREENSUN"]
        attrs = {
            "POSITION": self.add([v[0] for v in verts], "3f", "VEC3", 5126, minmax=True),
            "NORMAL": self.add([v[1] for v in verts], "3f", "VEC3", 5126),
            "TEXCOORD_0": self.add([tuple(v[2]) for v in verts], "2f", "VEC2", 5126),
        }
        for p, name in enumerate(palette_names):
            attrs[name] = self.add([tuple(v[3][4 * p:4 * p + 4]) for v in verts], "4B", "VEC4",
                                   5121, normalized=True)
        return {"attributes": attrs,
                "indices": self.add([(i,) for i in tris], "I", "SCALAR", 5125, target=34963),
                "material": material, "mode": 4}

    def write(self, path, nodes, meshes):
        images = [None] * len(self.images)
        for uri, i in self.images.items():
            images[i] = {"uri": uri}
        textures = [None] * len(self.textures)
        for (img, smp), i in self.textures.items():
            textures[i] = {"source": img, "sampler": smp}
        gltf = {
            "asset": {"version": "2.0", "generator": "gen_havenj2_mesh.py"},
            "scene": 0,
            "scenes": [{"nodes": list(range(len(nodes)))}],
            "nodes": nodes,
            "meshes": meshes,
            "materials": self.material_list,
            "textures": textures,
            "samplers": self.samplers,
            "images": images,
            "buffers": [{"byteLength": len(self.blob)}],
            "bufferViews": self.views,
            "accessors": self.accessors,
        }
        js = json.dumps(gltf, separators=(",", ":")).encode()
        js += b" " * ((4 - len(js) % 4) % 4)
        total = 12 + 8 + len(js) + 8 + len(self.blob)
        with open(path, "wb") as f:
            f.write(struct.pack("<III", 0x46546C67, 2, total))
            f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
            f.write(struct.pack("<II", len(self.blob), 0x004E4942) + bytes(self.blob))


# props ###########################################################################################


def box_corners(lo, hi):
    return [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]


BOX_QUADS = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]


def main():
    out = Glb()
    groups = {}  # material -> (verts, tris)
    boxes = {}   # collision material -> (points, tris)
    counts = {}
    models = {}

    def group(material):
        return groups.setdefault(material, ([], []))

    for level in CITY_LEVELS:
        for actor in jak2_actors.level_actors(level, ROOT):
            etype = actor["etype"]
            if etype not in PROPS:
                continue
            if etype not in models:
                models[etype] = load_model(etype)
            model = models[etype]
            point, normal = actor_transform(actor)
            for prim in model["prims"]:
                mat = out.material(prim["image"], prim["sampler"], prim["alpha"], prim["cutoff"],
                                   prim["name"])
                verts, tris = group(mat)
                remap = {}
                for i in prim["idx"]:
                    if i not in remap:
                        remap[i] = len(verts)
                        n = normal(prim["nrm"][i])
                        verts.append((point(prim["pos"][i]), n, prim["uv"][i],
                                      palettes(prim["col"][i], n)))
                    tris.append(remap[i])
            collide, material = PROPS[etype]
            if collide:
                lo, hi = list(model["lo"]), list(model["hi"])
                if collide == "post":
                    for axis in (0, 2):
                        mid = (lo[axis] + hi[axis]) / 2
                        lo[axis], hi[axis] = mid - POST_WIDTH / 2, mid + POST_WIDTH / 2
                points, btris = boxes.setdefault(material, ([], []))
                base = len(points)
                points += [point(c) for c in box_corners(lo, hi)]
                btris += [base + i for a, b, c, d in BOX_QUADS for i in (a, b, c, a, c, d)]
            counts[etype] = counts.get(etype, 0) + 1

    # the pools: translucent, lit facing up
    surfaces, _ = water.water_surfaces()
    for s in surfaces:
        mat = out.material(s["image_uri"], s["sampler"], "BLEND", 0.5, "havenj2-pool-water")
        verts, tris = group(mat)
        base = len(verts)
        for p, n, uv, c in zip(s["pos"], s["nrm"], s["uv"], s["col"]):
            verts.append((p, normalize(n), uv, palettes(c, normalize(n))))
        tris += [base + i for i in s["tris"]]

    meshes = []
    nodes = []
    prop_prims = [out.colored_primitive(v, t, m) for m, (v, t) in sorted(groups.items())]
    meshes.append({"name": "havenj2-props", "primitives": prop_prims})
    # the builder gives every unmarked mesh collision: the visible props and pools have none
    nodes.append({"name": "havenj2-props", "mesh": 0, "extras": {"set_collision": 1, "ignore": 1}})
    for material, (points, btris) in sorted(boxes.items()):
        center = [sum(p[i] for p in points) / len(points) for i in range(3)]
        nrm = [normalize([p[i] - center[i] for i in range(3)]) for p in points]
        prim = {"attributes": {
            "POSITION": out.add(points, "3f", "VEC3", 5126, minmax=True),
            "NORMAL": out.add(nrm, "3f", "VEC3", 5126)},
            "indices": out.add([(i,) for i in btris], "I", "SCALAR", 5125, target=34963),
            "mode": 4}
        meshes.append({"name": f"havenj2-props-collide-{material}", "primitives": [prim]})
        nodes.append({"name": f"havenj2-props-collide-{material}", "mesh": len(meshes) - 1,
                      "extras": {"set_invisible": 1, "set_collision": 1, "ignore": 0,
                                 "collide_material": material, "collide_event": 0,
                                 "nolineofsight": 0, "noedge": 0, "nocamera": 0, "noentity": 0}})
    out.write(OUT, nodes, meshes)
    nverts = sum(len(v) for v, _ in groups.values())
    ntris = sum(len(t) for _, t in groups.values()) // 3
    nboxes = sum(len(t) for _, t in boxes.values()) // 36
    print(f"{sum(counts.values())} props ({len(counts)} kinds), {len(surfaces)} pool surfaces: "
          f"{nverts} vertices, {ntris} triangles, {len(out.material_list)} materials, "
          f"{len(out.images)} textures, {nboxes} collision boxes")
    for etype, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {n:4d} {etype}")


if __name__ == "__main__":
    main()
