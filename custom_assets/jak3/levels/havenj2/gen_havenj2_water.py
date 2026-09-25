"""The water of the havenj2 custom level, from a Jak 2 extraction.

Writes havenj2-water-regions.json next to this script: the "water" region tree, loaded through
"region_tree_files" in havenj2.jsonc (Jak 3's water is regions only): one sphere covering the whole
city that takes its height from the ocean map, plus one volume per pool.

The pool surfaces themselves (Jak 2's water-anim actors of the palace plaza and the stadium) are
meshes: water_surfaces() gives them to gen_havenj2_mesh.py, which writes them into havenj2-mesh.glb
with Jak 2's props.

Inputs: decompiler_out/jak2/entities/<level>-actors.json and the pool meshes ripped to
decompiler_out/jak2/levels/<level>/ (Jak 2 extraction with rip_levels enabled).

usage: python custom_assets/jak3/levels/havenj2/gen_havenj2_water.py   (from the project root)
"""

import json
import math
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jak2_actors  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RIPS = os.path.join(ROOT, "decompiler_out", "jak2", "levels")
METERS = 4096.0

# Jak 2's water-anim actors: level, etype, and per *water-anim-look* index the mesh and the water
# flags of its region (None: a surface only, e.g. a fountain's top basin Jak 2 gave no water)
POOLS = [
    ("ctypal", "water-anim-ctypal", {
        29: ("water-anim-ctypal-lrgsqr-pool", "(swim wade)"),
        30: ("water-anim-ctypal-smlsqr-pool", "(swim wade)"),
        31: ("water-anim-ctypal-lrgfloor-pool", "(swim wade)"),
        32: ("water-anim-ctypal-smlground-pool", "(swim wade)"),
        33: ("water-anim-ctypal-middle-fountain", "(swim wade)"),
        34: ("water-anim-ctypal-long-grnd-pool", "(swim wade)"),
    }),
    # the three fountains of the stadium grounds: top basin, middle pool, floor pool. Jak 2 only
    # had water (wading, no swimming) in the middle and floor ones.
    ("stadium", "water-anim-stadium", {
        16: ("water-anim-stadium-middle-pool", "(wade)"),
        17: ("water-anim-stadium-top-fountain", None),
        18: ("water-anim-stadium-floor-pool", "(wade)"),
    }),
]

# region ids: 1 is the city-wide ocean region, pools follow
OCEAN_REGION = {"center": [350.0, 0.0, 575.0], "radius": 1950.0}
REGION_BELOW = 3.0  # meters of water volume below each pool surface (pools are at most 2m deep)
REGION_ABOVE = 2.0  # and above it

GLTF_TYPES = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
GLTF_FORMATS = {5126: ("f", 4), 5125: ("I", 4), 5123: ("H", 2), 5121: ("B", 1)}


def read_glb(path):
    data = open(path, "rb").read()
    json_len = struct.unpack_from("<I", data, 12)[0]
    gltf = json.loads(data[20:20 + json_len])
    bin_start = 20 + json_len + 8
    return gltf, data, bin_start


def read_accessor(gltf, data, bin_start, idx):
    acc = gltf["accessors"][idx]
    view = gltf["bufferViews"][acc["bufferView"]]
    fmt, size = GLTF_FORMATS[acc["componentType"]]
    n = GLTF_TYPES[acc["type"]]
    stride = view.get("byteStride", size * n)
    base = bin_start + view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    out = []
    for i in range(acc["count"]):
        vals = struct.unpack_from("<%d%s" % (n, fmt), data, base + i * stride)
        out.append(vals if n > 1 else vals[0])
    return out


def load_mesh(level, name):
    """A ripped pool mesh, keeping only the vertices its triangles use."""
    gltf, data, bin_start = read_glb(os.path.join(RIPS, level, name + "-lod0.glb"))
    prim = gltf["meshes"][0]["primitives"][0]
    attrs = prim["attributes"]
    indices = read_accessor(gltf, data, bin_start, prim["indices"])
    pos = read_accessor(gltf, data, bin_start, attrs["POSITION"])
    nrm = read_accessor(gltf, data, bin_start, attrs["NORMAL"])
    uv = read_accessor(gltf, data, bin_start, attrs["TEXCOORD_0"])
    col = read_accessor(gltf, data, bin_start, attrs["COLOR_0"])
    used = sorted(set(indices))
    remap = {old: new for new, old in enumerate(used)}
    material = gltf["materials"][prim["material"]]
    tex = gltf["textures"][material["pbrMetallicRoughness"]["baseColorTexture"]["index"]]
    return {
        "pos": [pos[i] for i in used],
        "nrm": [nrm[i] for i in used],
        "uv": [uv[i] for i in used],
        "col": [col[i] for i in used],
        "tris": [remap[i] for i in indices],
        "image_uri": gltf["images"][tex["source"]]["uri"],
        "sampler": gltf["samplers"][tex["sampler"]] if "sampler" in tex else None,
    }


def qrot(q, v):
    """Rotate v by quaternion q = (x, y, z, w). Matches GOAL's quaternion->matrix applied to a point."""
    x, y, z, w = q
    tx = 2 * (y * v[2] - z * v[1])
    ty = 2 * (z * v[0] - x * v[2])
    tz = 2 * (x * v[1] - y * v[0])
    return (v[0] + w * tx + (y * tz - z * ty),
            v[1] + w * ty + (z * tx - x * tz),
            v[2] + w * tz + (x * ty - y * tx))


def convex_hull_xz(points):
    """Counter-clockwise convex hull (monotone chain) of (x, z) points."""
    pts = sorted(set((round(p[0], 3), round(p[1], 3)) for p in points))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def face(normal, points):
    d = sum(normal[i] * points[0][i] for i in range(3))
    return {"normal": [round(c, 6) for c in normal] + [round(d, 6)],
            "points": [[round(c, 6) for c in p] for p in points]}


def prism_faces(hull, lo_y, hi_y):
    """Outward faces of the vertical prism with the given xz hull, between lo_y and hi_y. The game's
    inside test only uses the face planes (drawable-region-volume within-area?)."""
    cx = sum(p[0] for p in hull) / len(hull)
    cz = sum(p[1] for p in hull) / len(hull)
    faces = [face([0.0, 1.0, 0.0], [[p[0], hi_y, p[1]] for p in hull]),
             face([0.0, -1.0, 0.0], [[p[0], lo_y, p[1]] for p in hull])]
    for i in range(len(hull)):
        a, b = hull[i], hull[(i + 1) % len(hull)]
        nx, nz = b[1] - a[1], -(b[0] - a[0])
        length = math.hypot(nx, nz)
        nx, nz = nx / length, nz / length
        if nx * (a[0] - cx) + nz * (a[1] - cz) < 0:
            nx, nz = -nx, -nz
        faces.append(face([nx, 0.0, nz], [[a[0], lo_y, a[1]], [a[0], hi_y, a[1]],
                                          [b[0], lo_y, b[1]], [b[0], hi_y, b[1]]]))
    center = [cx, (lo_y + hi_y) / 2, cz]
    radius = max(math.dist(center, [p[0], y, p[1]]) for p in hull for y in (lo_y, hi_y))
    return faces, center, radius


def water_surfaces():
    """The pool surfaces in world space and their water regions.
    Returns (surfaces, regions): each surface has pos/nrm/uv/col lists, tris (indices into them),
    image_uri and sampler."""
    meshes = {}
    surfaces = []
    regions = [{
        "id": 1,
        "shape": "sphere",
        "trans": OCEAN_REGION["center"],
        "bsphere": OCEAN_REGION["center"] + [OCEAN_REGION["radius"]],
        # height taken from the ocean map; no ocean at a point means no water there. The game always
        # reads the flag list as the 3rd argument (water-info<-region), so "ocean" needs a
        # placeholder before it: without it, Jak touches the water but can't swim and falls through.
        "on-inside": "(water ocean 0.0 (swim wade))",
    }]
    for level, etype, looks in POOLS:
        actors = [a for a in jak2_actors.level_actors(level, ROOT) if a["etype"] == etype]
        for actor in sorted(actors, key=lambda a: a["lump"]["name"]):
            lump = actor["lump"]
            name, flags = looks[lump["look"]]
            if name not in meshes:
                meshes[name] = load_mesh(level, name)
            mesh = meshes[name]
            q = actor["quat"]
            offset = [c / METERS for c in lump.get("trans-offset", [0, 0, 0, 0])[:3]]
            trans = [actor["trans"][i] + offset[i] for i in range(3)]
            pos = []
            nrm = []
            for p, nr in zip(mesh["pos"], mesh["nrm"]):
                r = qrot(q, p)
                pos.append(tuple(r[i] + trans[i] for i in range(3)))
                nrm.append(qrot(q, nr))
            surfaces.append(dict(pos=pos, nrm=nrm, uv=list(mesh["uv"]), col=list(mesh["col"]),
                                 tris=list(mesh["tris"]), image_uri=mesh["image_uri"],
                                 sampler=mesh["sampler"], name=lump["name"]))
            if not flags:
                continue
            # water volume: a prism on the convex hull of the surface footprint, from below to
            # above the lump's water height. A bounding box would spill over the lower ground around
            # non-rectangular pools, where Jak would then swim in the air.
            height = lump["water-height"][0] / METERS
            hull = convex_hull_xz([(p[0], p[2]) for p in pos])
            faces, center, radius = prism_faces(hull, height - REGION_BELOW, height + REGION_ABOVE)
            regions.append({
                "id": len(regions) + 1,
                "shape": "volume",
                "bsphere": [round(c, 4) for c in center] + [round(radius + 0.5, 4)],
                "on-inside": "(water height %.4f %s)" % (height, flags),
                "volume": {"faces": faces},
            })
    return surfaces, regions


def main():
    surfaces, regions = water_surfaces()
    tree = {"water": {"bsphere": OCEAN_REGION["center"] + [OCEAN_REGION["radius"] + 50.0],
                      "regions": regions}}
    with open(os.path.join(HERE, "havenj2-water-regions.json"), "w") as f:
        json.dump(tree, f, indent=2)
    print("%d pool surfaces, %d regions (the surfaces are written by gen_havenj2_mesh.py)" %
          (len(surfaces), len(regions)))


if __name__ == "__main__":
    main()
