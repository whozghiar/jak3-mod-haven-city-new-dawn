"""Pools: the water of a level's water-anim actors (the source game's pools and fountains).

For each level with a "water" block, writes <level>-water-regions.json: the "water" region tree the
level .jsonc loads through "region_tree_files" (Jak 3's water is regions only): one sphere covering
the level that takes its height from the ocean map, plus one volume per pool. The pool surfaces
themselves are meshes: surfaces() gives them to the mesh step, which writes them into the level's
background mesh.

Manifest, on the level:
  "water": {
    "ocean_region": {"center": [x, y, z], "radius": r},     meters
    "below": 3.0, "above": 2.0,     meters of water volume below and above each pool surface
    "pools": [{"level": source level, "etype": the water-anim class,
               "looks": {"<look>": [ripped mesh, water flags of its region, or null]}}]
  }
Inputs: the source game's actors, and the pool meshes ripped to decompiler_out/<game>/levels/.
"""

import functools
import json

from ..common import geometry as geo
from ..common import glb
from ..common.files import write_if_changed


def load_mesh(port, level, name):
    """A ripped pool mesh, keeping only the vertices its triangles use."""
    gltf, data, bin_start = glb.read_glb(port.rip(f"{level}/{name}-lod0.glb"))
    prim = gltf["meshes"][0]["primitives"][0]
    attrs = prim["attributes"]
    indices = glb.read_accessor(gltf, data, bin_start, prim["indices"])
    pos = glb.read_accessor(gltf, data, bin_start, attrs["POSITION"])
    nrm = glb.read_accessor(gltf, data, bin_start, attrs["NORMAL"])
    uv = glb.read_accessor(gltf, data, bin_start, attrs["TEXCOORD_0"])
    col = glb.read_accessor(gltf, data, bin_start, attrs["COLOR_0"])
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


@functools.lru_cache(maxsize=None)
def _surfaces(port, level_name):
    level = port.level(level_name)
    cfg = level["water"]
    meter = port.source.METER
    ocean = cfg["ocean_region"]
    meshes = {}
    surfaces = []
    regions = [{
        "id": 1,
        "shape": "sphere",
        "trans": ocean["center"],
        "bsphere": ocean["center"] + [ocean["radius"]],
        # height taken from the ocean map; no ocean at a point means no water there. The game always
        # reads the flag list as the 3rd argument (water-info<-region), so "ocean" needs a
        # placeholder before it: without it, Jak touches the water but can't swim and falls through.
        "on-inside": "(water ocean 0.0 (swim wade))",
    }]
    for pool in cfg["pools"]:
        src_level, etype, looks = pool["level"], pool["etype"], pool["looks"]
        actors = [a for a in port.story.level_actors(src_level) if a["etype"] == etype]
        for actor in sorted(actors, key=lambda a: a["lump"]["name"]):
            lump = actor["lump"]
            name, flags = looks[str(lump["look"])]
            if name not in meshes:
                meshes[name] = load_mesh(port, src_level, name)
            mesh = meshes[name]
            q = actor["quat"]
            offset = [c / meter for c in lump.get("trans-offset", [0, 0, 0, 0])[:3]]
            trans = [actor["trans"][i] + offset[i] for i in range(3)]
            pos = []
            nrm = []
            for p, nr in zip(mesh["pos"], mesh["nrm"]):
                r = geo.quat_rotate(q, p)
                pos.append(tuple(r[i] + trans[i] for i in range(3)))
                nrm.append(geo.quat_rotate(q, nr))
            surfaces.append(dict(pos=pos, nrm=nrm, uv=list(mesh["uv"]), col=list(mesh["col"]),
                                 tris=list(mesh["tris"]), image_uri=mesh["image_uri"],
                                 sampler=mesh["sampler"], name=lump["name"]))
            if not flags:
                continue
            # water volume: a prism on the convex hull of the surface footprint, from below to
            # above the lump's water height. A bounding box would spill over the lower ground around
            # non-rectangular pools, where Jak would then swim in the air.
            height = lump["water-height"][0] / meter
            hull = geo.convex_hull_xz([(p[0], p[2]) for p in pos])
            faces, center, radius = geo.prism_faces(hull, height - cfg["below"],
                                                    height + cfg["above"])
            regions.append({
                "id": len(regions) + 1,
                "shape": "volume",
                "bsphere": [round(c, 4) for c in center] + [round(radius + 0.5, 4)],
                "on-inside": "(water height %.4f %s)" % (height, flags),
                "volume": {"faces": faces},
            })
    return surfaces, regions


def surfaces(port, level):
    """The pool surfaces of a level in world space and their water regions: (surfaces, regions).
    Each surface has pos/nrm/uv/col lists, tris (indices into them), image_uri and sampler."""
    return _surfaces(port, level.name)


def regions_path(level):
    return f"{level.folder}/{level.name}-water-regions.json"


def run(port):
    for level in port.levels:
        if "water" not in level:
            continue
        cfg = level["water"]
        surf, regions = surfaces(port, level)
        ocean = cfg["ocean_region"]
        tree = {"water": {"bsphere": ocean["center"] + [ocean["radius"] + 50.0],
                          "regions": regions}}
        write_if_changed(regions_path(level), json.dumps(tree, indent=2))
        print(f"  {level.name}: {len(surf)} pool surfaces, {len(regions)} water regions")
