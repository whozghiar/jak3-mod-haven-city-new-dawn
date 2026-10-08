"""The background mesh a level adds to the background merged from the source game's .fr3 files
(<level>-mesh.glb, the level .jsonc's "gltf_file"):

  - the source game's static props that aren't actors in the port (yakows, street lamps, mission
    kiosks...). In the source game they are actors; here they are part of the background, placed
    like its actors: their ripped model (lod0) is transformed into world space and lit by the
    level's time of day. Jak 2 lights them per vertex (merc): an ambient color plus four sun
    directions (the source game's SUN_DIRECTIONS). The background palettes follow the same layout
    (0 ambient, 1-4 the sun directions weighted by the hour), so each vertex gets palette 0 =
    ambient, palette 1-4 = its normal facing each sun direction, times the model's own vertex
    shading. Solid props also get an invisible collision box.
  - the pool and fountain surfaces of the level's "water" block (steps/water.py), translucent,
    without collision, lit the same way.

The level builder turns the visible meshes into tfrag trees (by material), and the boxes into
collision.

Manifest, on the level:
  "mesh": {
    "props": {"<source etype>": [collision, pat material]},
      collision: "box" (the model's bounding box, oriented like the actor), "post" (a thin column at
      the model's center, for poles with a head, like street lamps) or null (no collision: plants
      Jak walks through, props out of reach). The material is a Jak 1 pat material number,
      converted by the builder.
    "post_width": meters,
    "palette": {"ambient": 110.0, "sun": 100.0}     palette scales, for a vertex of full shading
  }
Inputs: the source game's actors, and the ripped models in decompiler_out/<game>/levels/.
"""

import os

from ..common import geometry as geo
from ..common import glb
from . import water


def palettes(sun_directions, ambient, sun, shade, normal):
    """The 8 time of day colors (rgba bytes, 32 values) of a vertex: shade is the merc vertex color
    (0.5 = full), normal its world normal."""
    out = []
    k = [c * 2.0 for c in shade[:3]]
    if sun is None:
        # an interior: its moods light any of the 8 palettes (the Hip Hog only palette 1), the
        # props have the same light in all of them
        weights = [ambient] * 8
    else:
        weights = [ambient] + [sun * max(0.0, sum(normal[i] * d[i] for i in range(3)))
                               for d in sun_directions] + [0.0, 0.0, 0.0]
    for w in weights:
        out += [max(0, min(255, int(round(w * c)))) for c in k] + [128]
    return out


def find_rip(port, level, etype):
    rips = port.source.RIPS
    for src in level.sources + sorted(os.listdir(rips)):
        path = os.path.join(rips, src, etype + "-lod0.glb")
        if os.path.exists(path):
            return path
    return None


def load_model(port, level, etype):
    """A ripped model in its bind pose: vertices and one triangle list per material."""
    gltf, data, bin_start = glb.read_glb(find_rip(port, level, etype))
    prims = []
    all_used = set()
    cache = {}

    def acc(i):
        if i not in cache:
            cache[i] = glb.read_accessor(gltf, data, bin_start, i)
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
            name=mat.get("name", ""), extras=mat.get("extras")))
        all_used |= set(idx)
    pos = prims[0]["pos"]
    points = [pos[i] for i in all_used]
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    return dict(prims=prims, lo=lo, hi=hi)


def actor_transform(actor):
    """The actor's rotation and position (meters): model space -> world space. Like Jak 2
    (process-drawable-from-entity!), the scale lump is ignored: the props are drawn at their
    size."""
    q = actor["quat"]
    t = actor["trans"][:3]

    def point(p):
        r = geo.quat_rotate(q, p)
        return tuple(r[i] + t[i] for i in range(3))

    def normal(n):
        return geo.normalize(geo.quat_rotate(q, n))

    return point, normal


def mesh_path(level):
    return f"{level.folder}/{level.name}-mesh.glb"


def write_level(port, level):
    cfg = level["mesh"]
    props = cfg["props"]
    suns = port.source.SUN_DIRECTIONS
    ambient, sun = cfg["palette"]["ambient"], cfg["palette"]["sun"]
    out = glb.Glb()
    groups = {}  # material -> (verts, tris)
    boxes = {}   # collision material -> (points, tris)
    counts = {}
    models = {}

    def group(material):
        return groups.setdefault(material, ([], []))

    for src in level.sources:
        for actor in port.story.level_actors(src):
            etype = actor["etype"]
            if etype not in props:
                continue
            if etype not in models:
                models[etype] = load_model(port, level, etype)
            model = models[etype]
            point, normal = actor_transform(actor)
            for prim in model["prims"]:
                mat = out.material(prim["image"], prim["sampler"], prim["alpha"], prim["cutoff"],
                                   prim["name"], prim["extras"])
                verts, tris = group(mat)
                remap = {}
                for i in prim["idx"]:
                    if i not in remap:
                        remap[i] = len(verts)
                        n = normal(prim["nrm"][i])
                        verts.append((point(prim["pos"][i]), n, prim["uv"][i],
                                      palettes(suns, ambient, sun, prim["col"][i], n)))
                    tris.append(remap[i])
            collide, material = props[etype]
            if collide:
                lo, hi = list(model["lo"]), list(model["hi"])
                if collide == "post":
                    for axis in (0, 2):
                        mid = (lo[axis] + hi[axis]) / 2
                        half = cfg["post_width"] / 2
                        lo[axis], hi[axis] = mid - half, mid + half
                points, btris = boxes.setdefault(material, ([], []))
                base = len(points)
                points += [point(c) for c in geo.box_corners(lo, hi)]
                btris += [base + i for a, b, c, d in geo.BOX_QUADS for i in (a, b, c, a, c, d)]
            counts[etype] = counts.get(etype, 0) + 1

    # the pools: translucent, lit facing up
    surfaces, _ = water.surfaces(port, level) if "water" in level else ([], [])
    for s in surfaces:
        mat = out.material(s["image_uri"], s["sampler"], "BLEND", 0.5, f"{level.name}-pool-water")
        verts, tris = group(mat)
        base = len(verts)
        for p, n, uv, c in zip(s["pos"], s["nrm"], s["uv"], s["col"]):
            verts.append((p, geo.normalize(n), uv,
                          palettes(suns, ambient, sun, c, geo.normalize(n))))
        tris += [base + i for i in s["tris"]]

    # nothing to draw nor collide (a district whose only props were dropped): no mesh at all, the
    # level file then has no "gltf_file" (the builder fails on a mesh without primitives)
    if not groups and not boxes:
        if os.path.exists(mesh_path(level)):
            os.remove(mesh_path(level))
        print(f"  {level.name}: no props, no pool surfaces: no mesh")
        return

    name = f"{level.name}-props"
    meshes = []
    nodes = []
    prop_prims = [out.colored_primitive(v, t, m) for m, (v, t) in sorted(groups.items())]
    meshes.append({"name": name, "primitives": prop_prims})
    # the builder gives every unmarked mesh collision: the visible props and pools have none
    nodes.append({"name": name, "mesh": 0, "extras": {"set_collision": 1, "ignore": 1}})
    for material, (points, btris) in sorted(boxes.items()):
        center = [sum(p[i] for p in points) / len(points) for i in range(3)]
        nrm = [geo.normalize([p[i] - center[i] for i in range(3)]) for p in points]
        prim = {"attributes": {
            "POSITION": out.add(points, "3f", "VEC3", 5126, minmax=True),
            "NORMAL": out.add(nrm, "3f", "VEC3", 5126)},
            "indices": out.add([(i,) for i in btris], "I", "SCALAR", 5125, target=34963),
            "mode": 4}
        meshes.append({"name": f"{name}-collide-{material}", "primitives": [prim]})
        nodes.append({"name": f"{name}-collide-{material}", "mesh": len(meshes) - 1,
                      "extras": {"set_invisible": 1, "set_collision": 1, "ignore": 0,
                                 "collide_material": material, "collide_event": 0,
                                 "nolineofsight": 0, "noedge": 0, "nocamera": 0, "noentity": 0}})
    out.write(mesh_path(level), nodes, meshes)
    nverts = sum(len(v) for v, _ in groups.values())
    ntris = sum(len(t) for _, t in groups.values()) // 3
    nboxes = sum(len(t) for _, t in boxes.values()) // 36
    print(f"  {level.name}: {sum(counts.values())} props ({len(counts)} kinds), {len(surfaces)} "
          f"pool surfaces: {nverts} vertices, {ntris} triangles, {len(out.material_list)} "
          f"materials, {len(out.images)} textures, {nboxes} collision boxes")


def run(port):
    for level in port.levels:
        if "mesh" in level:
            write_level(port, level)
