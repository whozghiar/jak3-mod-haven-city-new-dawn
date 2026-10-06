"""Traffic navigation data: the source levels' city-level-infos and nav meshes for one level
(<level>-nav.json, read by the level builder as the level .jsonc's "nav_data"): a level holding one
district gets that district's as they are, a level holding several gets them merged.

Jak 2 gives each district of its city its own city-level-info (the traffic: a grid of cells holding
the nav segments, and a nav graph of nodes and branches, linked to the neighbor districts' graphs)
and its own nav meshes (where citizens and guards walk). The traffic engine (Jak 2's and Jak 3's,
the same) links the city-level-infos of at most 2 displayed levels, its 2 districts, and only
spawns objects in their active cells: a district level keeps its own data, as it is (links to its
neighbors' graphs included, resolved by graph id when both are linked), so the traffic only lives
where the city is displayed. A level merging several districts (one bsp, one city-level-info) gets
them merged into one, over one grid covering them all, with one nav graph (the links between
districts become plain branches). The nav meshes are kept as they are (their ids too, which
the nav graph uses). Jak 2 and Jak 3 share these layouts (city-level-info, vis-cell, nav-segment,
nav-graph, nav-node, nav-branch, nav-graph-link, nav-mesh).

The traffic engine keeps a citizen or a vehicle alive only while it is in an active cell, and a
cell is active by the camera's distance to its sphere (and the view frustum), at most 255 at once.
Like Jak 2's, every cell has a sphere around the whole cell, empty or not: an object entering a
cell that is never active disappears in front of the player (and one appears again where its
segments are). Jak 2's districts have 25m, 40m or 50m cells; the merged grid has 50m cells (every
25m or 50m cell falls in one of them), and each segment goes in the cell that holds its middle.

It can also copy the source game's traffic height map (how high the vehicles fly) into the level's
code, in place of the target game's, which follows its own city.

Manifest, on the level:
  "nav": {
    "cell": 50.0,              meters, the merged grid's cells (the districts' grids are aligned on
                               multiples of their cell size)
    "outside_depth": 10000.0,  meters under the level of the spheres of cells no district covers
    "height_map": {"source": the source game's traffic-height-map.gc},
    "sources": [the source levels whose navigation it holds, else the level's own; none: only the
                height map (a city's hub: its districts hold their own)]
  }
Inputs: decompiler_out/<game>/entities/<level>-city.json and <level>-nav.json of the level's
sources (see decompiler/level_extractor/extract_nav.h).
"""

import json
import math
import os
import re
import struct

from ..common import data_blob
from ..common.data_blob import patch
from ..common.files import write_if_changed

# a branch's destination above this is ~(link index)
LINK_BASE = 100000
NO_CELL = 0xffff


def decode_city(blob):
    """The city-level-info of a blob: grid, cells, segments and nav graph, as dicts. In the file,
    the cells' segments, the segments' branches, the nodes' branches and the branches' nodes are
    indices (the traffic engine turns them into pointers when a level is linked, see
    traffic-engine level-link)."""
    base = blob.roots["city-level-info"]
    grid = {
        "axis_scale": [blob.f32(base + 4 * i) for i in range(3)],
        "dims": [blob.s8(base + 12 + i) for i in range(3)],
        "box_min": [blob.f32(base + 16 + 4 * i) for i in range(4)],
        "box_max": [blob.f32(base + 32 + 4 * i) for i in range(4)],
        "cell_size": [blob.f32(base + 48 + 4 * i) for i in range(4)],
    }
    cell_array = blob.ptr(base + 64)
    segment_count = blob.s16(base + 68)
    cell_count = blob.u16(base + 70)
    segment_array = blob.ptr(base + 72)
    graph = blob.ptr(base + 76)
    camera_ceiling = blob.f32(base + 80)
    cells = []
    for i in range(cell_count):
        c = cell_array + 32 * i
        cells.append({
            "sphere": [blob.f32(c + 4 * k) for k in range(4)],
            "segment_start": blob.u32(c + 16),
            "vis_id": blob.u16(c + 20),
            "id": blob.u16(c + 22),
            "incoming": blob.s8(c + 24),
            "segment_count": blob.s8(c + 25),
            "flags": blob.u8(c + 26),
            "pad": blob.u32(c + 28),
        })
    segments = []
    for i in range(segment_count):
        s = segment_array + 48 * i
        segments.append({
            "raw": blob.raw(s, 48),
            "v0": [blob.f32(s + 4 * k) for k in range(4)],
            "v1": [blob.f32(s + 16 + 4 * k) for k in range(4)],
            "branch": blob.u32(s + 32),
            "nav_mesh_id": blob.u32(s + 36),
            "id": blob.u16(s + 40),
            "cell_id": blob.u16(s + 42),
            "from_cell_id": blob.u16(s + 44),
            "tracker_id": blob.s8(s + 46),
        })
    # nav-graph (a basic: fields from its type tag, 4 bytes before the pointer)
    g = graph - 4
    node_count = blob.s16(g + 4)
    branch_count = blob.s16(g + 6)
    node_array = blob.ptr(g + 8)
    branch_array = blob.ptr(g + 12)
    link_count = blob.s16(g + 16)
    link_array = blob.ptr(g + 20)
    nodes = []
    for i in range(node_count):
        n = node_array + 32 * i
        nodes.append({
            "raw": blob.raw(n, 32),
            "pos": [blob.f32(n + 4 * k) for k in range(3)],
            "id": blob.u16(n + 14),
            "branch_count": blob.s8(n + 17),
            "branch_start": blob.u32(n + 20),
            "nav_mesh_id": blob.u32(n + 24),
            "level": blob.symbols.get((n + 28) // 4),
        })
    branches = []
    for i in range(branch_count):
        b = branch_array + 16 * i
        branches.append({
            "raw": blob.raw(b, 16),
            "src": blob.u32(b),
            "dest": blob.u32(b + 4),
        })
    links = []
    for i in range(link_count):
        k = link_array + 48 * i
        links.append({
            "id": blob.u32(k),
            "dest_graph_id": blob.u32(k + 4),
            "src_branch_id": blob.u16(k + 8),
            "dest_node_id": blob.u16(k + 10),
        })
    return {
        "grid": grid, "cells": cells, "segments": segments, "camera_ceiling": camera_ceiling,
        "graph": {"id": blob.u32(g + 32), "first_node": blob.s16(g + 24), "nodes": nodes,
                  "branches": branches, "links": links},
    }


def merge(districts, mesh_aids, cell_size, outside_depth):
    """One city (grid, cells, segments, nodes, branches) from the districts' decoded ones.
    mesh_aids: the aids of the nav meshes the level has. cell_size and outside_depth in game
    units."""
    CELL = cell_size
    lo = [min(c["grid"]["box_min"][i] for c in districts.values()) for i in range(3)]
    hi = [max(c["grid"]["box_max"][i] for c in districts.values()) for i in range(3)]
    lo[0] = math.floor(lo[0] / CELL) * CELL
    lo[2] = math.floor(lo[2] / CELL) * CELL
    dims = [math.ceil((hi[0] - lo[0]) / CELL), 1, math.ceil((hi[2] - lo[2]) / CELL)]
    assert max(dims) < 128, dims
    height = hi[1] - lo[1]

    def global_cell(x, z):
        ix = max(0, min(int((x - lo[0]) / CELL), dims[0] - 1))
        iz = max(0, min(int((z - lo[2]) / CELL), dims[2] - 1))
        return ix + iz * dims[0]

    graph_ids = {c["graph"]["id"]: name for name, c in districts.items()}
    node_base, branch_base = {}, {}
    n_nodes = n_branches = 0
    for name, c in districts.items():
        node_base[name] = n_nodes
        branch_base[name] = n_branches
        n_nodes += len(c["graph"]["nodes"])
        n_branches += len(c["graph"]["branches"])

    nodes, branches, placed = [], [], []
    for name, c in districts.items():
        for s in c["segments"]:
            branch = s["branch"] + branch_base[name]
            raw = patch(s["raw"], 32, "<I", branch)
            # a pedestrian segment on a nav mesh no level has (Jak 2's ctygenc has some): nav mesh
            # 0, which the traffic engine never spawns citizens on (a spawn needs its nav mesh)
            if s["tracker_id"] == 1 and s["nav_mesh_id"] not in mesh_aids:
                raw = patch(raw, 36, "<I", 0)
            v0 = struct.unpack_from("<3f", raw, 0)
            v1 = struct.unpack_from("<3f", raw, 16)
            cell = global_cell((v0[0] + v1[0]) / 2, (v0[2] + v1[2]) / 2)
            placed.append((branch, v0, v1, cell, s["from_cell_id"] != NO_CELL, raw))
        for n in c["graph"]["nodes"]:
            raw = patch(n["raw"], 14, "<H", len(nodes))
            raw = patch(raw, 20, "<I", n["branch_start"] + branch_base[name])
            nodes.append(raw)
        links = c["graph"]["links"]
        for b in c["graph"]["branches"]:
            src = b["src"] + node_base[name]
            if b["dest"] > LINK_BASE:
                link = links[0xffffffff - b["dest"]]
                dest_name = graph_ids[link["dest_graph_id"]]
                dest_ids = {n["id"]: node_base[dest_name] + i
                            for i, n in enumerate(districts[dest_name]["graph"]["nodes"])}
                dest = dest_ids[link["dest_node_id"]]
            else:
                dest = b["dest"] + node_base[name]
            raw = patch(b["raw"], 0, "<I", src)
            raw = patch(raw, 4, "<I", dest)
            branches.append(raw)

    # from-cell-id: the cell of the segment before it on its branch (Jak 2 splits a branch into one
    # segment per cell it crosses; the one before ends where it starts), none (#xffff) on the first.
    # The engine spawns objects at the edge of the active cells, on the segments coming from an
    # inactive cell.
    cell_before = {(branch, v1): cell for branch, _, v1, cell, _, _ in placed}
    cell_segments = {}
    for branch, v0, _, cell, follows, raw in placed:
        before = cell_before.get((branch, v0), NO_CELL) if follows else NO_CELL
        assert not follows or before != NO_CELL, "a segment without the one before it"
        raw = patch(raw, 42, "<H", cell)
        raw = patch(raw, 44, "<H", before)
        cell_segments.setdefault(cell, []).append(raw)

    # cells: their segments in a row, the ones coming from another cell first. A cell's sphere
    # (what the engine activates it by), like Jak 2's: the whole cell, from the bottom to the top of
    # the districts over it; far under the city for the cells no district covers.
    boxes = [(c["grid"]["box_min"], c["grid"]["box_max"]) for c in districts.values()]
    cells, segments = [], []
    for i in range(dims[0] * dims[2]):
        segs = cell_segments.get(i, [])
        incoming = [s for s in segs if struct.unpack_from("<H", s, 44)[0] not in (NO_CELL, i)]
        own = [s for s in segs if struct.unpack_from("<H", s, 44)[0] in (NO_CELL, i)]
        assert len(segs) < 128, f"cell {i}: {len(segs)} segments"
        start = len(segments)
        for s in incoming + own:
            segments.append(patch(s, 40, "<H", len(segments)))
        ix, iz = i % dims[0], i // dims[0]
        x0, z0 = lo[0] + ix * CELL, lo[2] + iz * CELL
        heights = [(b_lo[1], b_hi[1]) for b_lo, b_hi in boxes
                   if b_lo[0] < x0 + CELL and b_hi[0] > x0 and b_lo[2] < z0 + CELL and b_hi[2] > z0]
        center = [x0 + CELL / 2, lo[1] - outside_depth, z0 + CELL / 2]
        radius = 0.0
        if heights:
            y_lo, y_hi = min(h[0] for h in heights), max(h[1] for h in heights)
            center[1] = (y_lo + y_hi) / 2
            radius = math.sqrt(2 * (CELL / 2) ** 2 + ((y_hi - y_lo) / 2) ** 2)
        assert radius > 0 or not segs, f"cell {i}: segments out of every district"
        cells.append(struct.pack("<4fIHHbbBBI", *center, radius, start, 0, i, len(incoming),
                                 len(segs), 0, 0, 0))
    assert len(segments) < 32768
    grid = {"lo": lo, "hi": hi, "dims": dims, "height": height, "cell": CELL}
    return grid, cells, segments, nodes, branches


def write_city(w, grid, cells, segments, nodes, branches, camera_ceiling, level_name):
    """The merged city-level-info at the start of the writer's blob."""
    lo, hi, dims, height, CELL = grid["lo"], grid["hi"], grid["dims"], grid["height"], grid["cell"]
    info = w.bytes(bytes(144))
    w.blob.roots["city-level-info"] = info
    header = struct.pack("<3f3bB", 1.0 / CELL, 1.0 / height, 1.0 / CELL, dims[0], dims[1], dims[2],
                         0)
    header += struct.pack("<4f4f4f", lo[0], lo[1], lo[2], 1.0, hi[0], hi[1], hi[2], 1.0,
                          CELL, height, CELL, 1.0)
    header += struct.pack("<IhHIIf", 0, len(segments), len(cells), 0, 0, camera_ceiling)
    w.blob.words[info // 4: info // 4 + len(header) // 4] = list(
        struct.unpack("<%dI" % (len(header) // 4), header))
    w.align()
    cell_array = w.bytes(b"".join(cells))
    w.align()
    segment_array = w.bytes(b"".join(segments))
    # nav-graph, a basic: its type tag at a 16-byte boundary
    w.align()
    tag = w.pos()
    w.bytes(bytes(64))
    w.blob.types[tag // 4] = "nav-graph"
    graph = tag + 4
    struct_words = struct.pack("<hhIIhHIhHII", len(nodes), len(branches), 0, 0, 0, 0, 0, 0, 0, 0,
                               1000)
    w.blob.words[(tag + 4) // 4: (tag + 4) // 4 + len(struct_words) // 4] = list(
        struct.unpack("<%dI" % (len(struct_words) // 4), struct_words))
    w.blob.symbols[(tag + 28) // 4] = "#f"  # patched
    w.align()
    node_array = w.bytes(b"".join(nodes))
    for i in range(len(nodes)):
        w.blob.symbols[(node_array + 32 * i + 28) // 4] = level_name
    w.align()
    branch_array = w.bytes(b"".join(branches))
    w.pointer(info + 64, cell_array)
    w.pointer(info + 72, segment_array)
    w.pointer(info + 76, graph)
    w.pointer(tag + 8, node_array)
    w.pointer(tag + 12, branch_array)


def height_map_path(port, level):
    return f"{port.code_dir}/{level.name}-height-map.gc"


def write_height_map(port, level, source):
    """The source game's *traffic-height-map* as a target game source file (same xz-height-map
    layout), its heights one grid row per line. Returns the grid's dimensions."""
    text = open(source).read()
    start = text.index("(define *traffic-height-map*")
    data = text.index(":data (new 'static 'array int8", start)
    header = text[start:text.index("\n", data)]
    dims = [int(v.replace("#x", "0x"), 0)
            for v in re.search(r":dim \(new 'static 'array int16 2 (\S+) (\S+)\)", header).groups()]
    count = int(re.search(r"array int8 (\d+)", header[data - start:]).group(1))
    values = re.findall(r"-?\d+", text[text.index("\n", data): text.rindex(")", 0,
                                                                          text.rindex(")"))])
    assert count == dims[0] * dims[1] == len(values), (count, dims, len(values))
    indent = " " * 33
    rows = [indent + " ".join(values[i: i + dims[0]]) for i in range(0, count, dims[0])]
    name = f"{level.name}-height-map"
    out = [
        ";;-*-Lisp-*-",
        "(in-package goal)",
        "",
        f";; name: {name}.gc",
        f";; name in dgo: {name}",
        f";; dgos: {level.dgo}",
        "",
        *port.generated_lines(),
        f";; {port.source.TITLE}'s traffic height map ({source}): the height the",
        f";; vehicles fly at. {level.name}'s DGO has it in place of {port.target.TITLE}'s.",
        "",
        header,
        *rows,
        "                                 )",
        "                               )",
        "        )",
        "",
    ]
    write_if_changed(height_map_path(port, level), "\n".join(out))
    return dims


def nav_path(level):
    return f"{level.folder}/{level.name}-nav.json"


def city_sources(port, level):
    """The source levels of a level's "nav" that have navigation data (empty: no nav_data)."""
    if "nav" not in level:
        return []
    return [src for src in sorted(level["nav"].get("sources", level.sources))
            if os.path.exists(os.path.join(port.source.ENTITIES, src + "-city.json"))]


def write_district(port, level, src):
    """One source level's city-level-info and nav meshes, as they are: its own grid, cells and nav
    graph, with its links to its neighbors' graphs. Its node levels (the level it was loaded in, a
    symbol) become ours: when a level is unloaded, the traffic engine stops the vehicles heading to
    a node of that level by its name (deactivate-all-from-level). Its pedestrian segments on a nav
    mesh it doesn't have go to nav mesh 0, which no citizen spawns on."""
    entities = port.source.ENTITIES
    city = data_blob.Blob(os.path.join(entities, src + "-city.json"))
    nav_file = os.path.join(entities, src + "-nav.json")
    meshes = data_blob.Blob(nav_file) if os.path.exists(nav_file) else None
    mesh_aids = {meshes.u32(byte + 44) for byte in meshes.roots.values()} if meshes else set()
    for w, name in city.symbols.items():
        if name == src:
            city.symbols[w] = level.name
    base = city.roots["city-level-info"]
    segment_count = city.s16(base + 68)
    segment_array = city.ptr(base + 72)
    moved = 0
    for i in range(segment_count):
        seg = segment_array + 48 * i
        if city.s8(seg + 46) == 1 and city.u32(seg + 36) not in mesh_aids | {0}:
            city.words[(seg + 36) // 4] = 0
            moved += 1
    w = data_blob.Writer()
    offset = w.append_blob(city)
    w.blob.roots["city-level-info"] = base + offset
    if meshes:
        offset = w.append_blob(meshes)
        for root, byte in meshes.roots.items():
            w.blob.roots[f"nav-mesh-{src}-{root}"] = byte + offset
    write_if_changed(nav_path(level), json.dumps(w.blob.to_json(), separators=(",", ":")))
    info = decode_city(city)
    print(f"  {level.name}: {src}'s navigation as it is: grid {info['grid']['dims']}, "
          f"{len(info['cells'])} cells, {segment_count} segments ({moved} on no nav mesh), "
          f"{len(info['graph']['nodes'])} nodes, {len(info['graph']['links'])} links, "
          f"{len(mesh_aids)} nav meshes, {len(w.blob.words) * 4 // 1024} KB")


def write_level(port, level):
    cfg = level["nav"]
    meter = port.source.METER
    entities = port.source.ENTITIES
    if "height_map" in cfg:
        dims = write_height_map(port, level, cfg["height_map"]["source"])
        print(f"  wrote {height_map_path(port, level)} ({dims[0]} x {dims[1]} heights)")
    sources = city_sources(port, level)
    if len(sources) == 1:
        write_district(port, level, sources[0])
        return
    if not sources:
        return
    districts, meshes = {}, {}
    for src in sources:
        city_path = os.path.join(entities, src + "-city.json")
        districts[src] = decode_city(data_blob.Blob(city_path))
        nav_path_src = os.path.join(entities, src + "-nav.json")
        if os.path.exists(nav_path_src):
            meshes[src] = data_blob.Blob(nav_path_src)
    mesh_aids = {blob.u32(byte + 44) for blob in meshes.values() for byte in blob.roots.values()}
    grid, cells, segments, nodes, branches = merge(districts, mesh_aids, cfg["cell"] * meter,
                                                   cfg["outside_depth"] * meter)
    w = data_blob.Writer()
    write_city(w, grid, cells, segments, nodes, branches,
               max(c["camera_ceiling"] for c in districts.values()), level.name)
    n_meshes = 0
    for src, blob in meshes.items():
        base = w.append_blob(blob)
        for root, byte in blob.roots.items():
            w.blob.roots[f"nav-mesh-{src}-{root}"] = byte + base
            n_meshes += 1
    write_if_changed(nav_path(level), json.dumps(w.blob.to_json(), separators=(",", ":")))
    print(f"  {level.name}: {len(districts)} districts: grid {grid['dims']}, {len(cells)} cells, "
          f"{len(segments)} segments, {len(nodes)} nodes, {len(branches)} branches, "
          f"{n_meshes} nav meshes, {len(w.blob.words) * 4 // 1024} KB")


def run(port):
    for level in port.levels:
        if "nav" in level:
            write_level(port, level)
