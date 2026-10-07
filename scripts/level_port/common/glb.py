"""Binary glTF (.glb): reading the decompiler's model rips, writing meshes and models for the
level builder and build-actor."""

import hashlib
import json
import math
import struct

from . import geometry
from . import hull
from .files import write_if_changed

GENERATOR = "level_port"

GLTF_TYPES = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
GLTF_FORMATS = {5126: ("f", 4), 5125: ("I", 4), 5123: ("H", 2), 5121: ("B", 1)}


# reading #########################################################################################


def read_glb(path):
    """(gltf json, file data, offset of the binary chunk's data)."""
    data = open(path, "rb").read()
    json_len = struct.unpack_from("<I", data, 12)[0]
    gltf = json.loads(data[20:20 + json_len])
    bin_start = 20 + json_len + 8
    return gltf, data, bin_start


def read_accessor(gltf, data, bin_start, idx):
    """An accessor's values: tuples, or numbers for a scalar accessor."""
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


def load_glb(path):
    """(gltf json, read) of a .glb file: read(accessor index) is the accessor's values, as
    tuples."""
    data = open(path, "rb").read()
    json_len = struct.unpack_from("<I", data, 12)[0]
    gltf = json.loads(data[20:20 + json_len])
    bin_start = 20 + json_len + 8
    bin_len = struct.unpack_from("<I", data, 20 + json_len)[0]
    blob = bytes(data[bin_start:bin_start + bin_len])

    def read(idx):
        acc = gltf["accessors"][idx]
        view = gltf["bufferViews"][acc["bufferView"]]
        fmt, size = GLTF_FORMATS[acc["componentType"]]
        n = GLTF_TYPES[acc["type"]]
        stride = view.get("byteStride", size * n)
        base = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
        return [struct.unpack_from("<%d%s" % (n, fmt), blob, base + i * stride)
                for i in range(acc["count"])]

    return gltf, read


def glb_bytes(gltf, blob):
    """A .glb file from its json and binary chunk."""
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    return (struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(blob))
            + struct.pack("<II", len(js), 0x4E4F534A) + js
            + struct.pack("<II", len(blob), 0x004E4942) + bytes(blob))


# a mesh for the level builder ####################################################################


class Glb:
    """A background mesh: primitives with time of day palettes, and invisible collision meshes."""

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
            "asset": {"version": "2.0", "generator": GENERATOR},
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
        write_if_changed(path, glb_bytes(gltf, self.blob))


# a model for build-actor #########################################################################


def rebuild_model(src, path, name, keep_prims, collide=None, anims=None):
    """<name>.glb for build-actor (written to path) from a model ripped by the decompiler: the kept
    primitives (None: all) with only the vertices they use (the rip shares one buffer), its first
    animation renamed <name>-idle (the name build-actor's def-actor looks up), no collision from
    the render mesh, and invisible collision meshes (build-actor's gen-mesh makes one collide mesh
    per node, in order). collide:
      None: one box around the model,
      {"hull": y_min}: the convex hull of the model's vertices above y_min (None: all), and below
        "y_max" when given, for the models of a single joint (hull.py),
      a list of meshes, each a list of boxes (lo, hi) in the model's space, or {"hull": y_min,
        "joint": name}: the hull of that joint's vertices (its part of the model), in the joint's
        space (the game moves a collide mesh with the joint its prim names: transform index =
        joint index + 1), or {"joint_box": name}: the box around that joint's vertices, in the
        model's space.
    anims: the animations to keep instead, [(rip, animation, our name)], from rips of models with
    the same joints (a rip's joint nodes are its joints + 1): a model whose animations its game
    keeps in another model's art group.
    Returns (vertex count, lo, hi) of the kept vertices."""
    gltf, read = load_glb(src)
    sizes = GLTF_TYPES

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

    def box_mesh(mesh_name, boxes):
        corners, normals, indices = [], [], []
        for b_lo, b_hi in boxes:
            base = len(corners)
            center = [(b_lo[i] + b_hi[i]) / 2 for i in range(3)]
            for p in geometry.box_corners(b_lo, b_hi):
                d = [p[i] - center[i] for i in range(3)]
                n = math.sqrt(sum(c * c for c in d)) or 1.0
                corners.append(p)
                normals.append(tuple(c / n for c in d))
            indices += [(base + i,) for a, b, c, d in geometry.BOX_QUADS
                        for i in (a, b, c, a, c, d)]
        return {"name": mesh_name, "primitives": [{
            "attributes": {"POSITION": add(corners, "3f", "VEC3", 5126, minmax=True),
                           "NORMAL": add(normals, "3f", "VEC3", 5126),
                           "COLOR_0": add([(0.5, 0.5, 0.5, 1.0)] * len(corners), "4f", "VEC4",
                                          5126)},
            "indices": add(indices, "I", "SCALAR", 5125, target=34963),
            "mode": 4}]}

    skin = dict(gltf["skins"][0])
    joint_names = [gltf["nodes"][j].get("name") for j in skin["joints"]]

    def joint_vertices(joint):
        """The indices of the vertices mostly weighted to a joint."""
        k = joint_names.index(joint)
        return [v for v, (j, w) in enumerate(zip(columns["JOINTS_0"], columns["WEIGHTS_0"]))
                if j[max(range(4), key=lambda i: w[i])] == k]

    def joint_points(joint):
        """The vertices of a joint, in its space (its inverse bind matrix, column major,
        applied)."""
        m = read(skin["inverseBindMatrices"])[joint_names.index(joint)]
        return [tuple(m[r] * p[0] + m[4 + r] * p[1] + m[8 + r] * p[2] + m[12 + r] for r in range(3))
                for p in (pts[v] for v in joint_vertices(joint))]

    def hull_mesh(mesh_name, spec):
        y_min = spec["hull"]
        y_max = spec.get("y_max")
        points = joint_points(spec["joint"]) if "joint" in spec else pts
        verts, tris = hull.hull_mesh(
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

    def collide_mesh(mesh_name, spec):
        if isinstance(spec, dict) and "joint_box" in spec:
            points = [pts[v] for v in joint_vertices(spec["joint_box"])]
            return box_mesh(mesh_name, [([min(p[i] for p in points) for i in range(3)],
                                         [max(p[i] for p in points) for i in range(3)])])
        if isinstance(spec, dict):
            return hull_mesh(mesh_name, spec)
        return box_mesh(mesh_name, spec)

    if isinstance(collide, dict):
        collide_meshes = [collide_mesh(f"{name}-collide-0", collide)]
    else:
        collide_meshes = [collide_mesh(f"{name}-collide-{i}", spec)
                          for i, spec in enumerate(collide or [[(lo, hi)]])]

    def copy_anim(anim, anim_gltf, anim_read, new_name):
        # the joints' channels only: a face's blend shape weights (Daxter's) are on the mesh node,
        # which build-actor doesn't animate
        kept = [c for c in anim["channels"] if c["target"]["path"] != "weights"]
        anim = {"channels": [dict(c, sampler=i) for i, c in enumerate(kept)],
                "samplers": [anim["samplers"][c["sampler"]] for c in kept]}
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
        ibms = [geometry.mat_from_gltf(m) for m in read(skin["inverseBindMatrices"])]
        parent = {}
        for j, node_idx in enumerate(joints):
            for child in gltf["nodes"][node_idx].get("children", []):
                if child in joints:
                    parent[joints.index(child)] = j
        time = add([(0.0,)], "f", "SCALAR", 5126, minmax=True, target=None)
        channels, samplers = [], []
        for j, node_idx in enumerate(joints):
            local = geometry.mat_inverse(ibms[j])
            if j in parent:
                local = geometry.mat_mul(ibms[parent[j]], local)
            trans, rot, scale = geometry.mat_decompose(local)
            for path_name, value, fmt, kind in (("translation", trans, "3f", "VEC3"),
                                                ("rotation", rot, "4f", "VEC4"),
                                                ("scale", scale, "3f", "VEC3")):
                samplers.append({"input": time,
                                 "output": add([tuple(value)], fmt, kind, 5126, target=None),
                                 "interpolation": "LINEAR"})
                channels.append({"sampler": len(samplers) - 1,
                                 "target": {"node": node_idx, "path": path_name}})
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
    for i, collide_mesh_json in enumerate(collide_meshes):
        nodes.append({"name": collide_mesh_json["name"], "mesh": 1 + i,
                      "extras": {"set_invisible": 1}})
        scene_nodes.append(len(nodes) - 1)
    out = {
        "asset": {"version": "2.0", "generator": GENERATOR},
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
    write_if_changed(path, glb_bytes(out, out_blob))
    return len(used), [round(v, 2) for v in lo], [round(v, 2) for v in hi]
