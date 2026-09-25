"""havenj2's navigation data, from Jak 2's city: gen_havenj2_nav.py writes havenj2-nav.json, read by
the level builder ("nav_data" in havenj2.jsonc), which puts it in havenj2's bsp.

Jak 2 gives each district its own city-level-info (the traffic: a grid of cells holding the nav
segments, and a nav graph of nodes and branches, linked to the neighbor districts' graphs) and its
own nav meshes (where citizens and guards walk). havenj2 is one level, and a bsp has one
city-level-info: the districts' are merged here into one, over one grid covering the city, with one
nav graph (the links between districts become plain branches). The nav meshes are kept as they are
(their ids too, which the nav graph uses), all in havenj2's nav-meshes.

The traffic engine keeps a citizen or a vehicle alive only while it is in an active cell, and a
cell is active by the camera's distance to its sphere (and the view frustum), at most 255 at once.
Like Jak 2's, every cell of the city has a sphere around the whole cell, empty or not: an object
entering a cell that is never active disappears in front of the player (and one appears again
where its segments are). Jak 2's districts have 25m, 40m or 50m cells; the merged grid has 50m
cells (every 25m or 50m cell falls in one of them, 36 to 76 active cells at most), and each segment
goes in the cell that holds its middle.

Inputs: decompiler_out/jak2/entities/<district>-city.json and <district>-nav.json (Jak 2
extraction, see decompiler/level_extractor/extract_nav.h).

It also writes havenj2-height-map.gc: Jak 2's traffic height map (the height the city's vehicles fly
at), in place of Jak 3's, which follows Jak 3's city.

usage: python custom_assets/jak3/levels/havenj2/gen_havenj2_nav.py   (from the project root)
"""

import json
import math
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nav_blob  # noqa: E402
from gen_util import write_if_changed  # noqa: E402

ENTITIES = "decompiler_out/jak2/entities"
OUT = "custom_assets/jak3/levels/havenj2/havenj2-nav.json"
HEIGHT_MAP_JAK2 = "goal_src/jak2/levels/city/traffic/traffic-height-map.gc"
HEIGHT_MAP_OUT = "goal_src/jak3/levels/havenj2/havenj2-height-map.gc"
METER = 4096.0
# the traffic cells, aligned on multiples of 50m (the districts' grids are on multiples of their
# cell size)
CELL = 50.0 * METER
# the level the nav graph's nodes belong to
LEVEL = "havenj2"
NO_CELL = 0xffff
# how far under the city the sphere of a cell no district covers is (never active)
OUTSIDE_CELL_DEPTH = 10000.0 * METER


def patch(raw, offset, fmt, value):
    b = bytearray(raw)
    struct.pack_into(fmt, b, offset, value)
    return bytes(b)


class Writer:
    """Builds a blob (words, pointers, types, symbols) at 16-byte aligned places."""

    def __init__(self):
        self.blob = nav_blob.Blob()

    def pos(self):
        return len(self.blob.words) * 4

    def align(self, mod=0):
        while (self.pos() - mod) % 16:
            self.blob.words.append(0)

    def bytes(self, data):
        assert len(data) % 4 == 0
        start = self.pos()
        self.blob.words += list(struct.unpack("<%dI" % (len(data) // 4), data))
        return start

    def pointer(self, byte, target):
        self.blob.pointers[byte // 4] = target

    def append_blob(self, other):
        """Another blob at the end of this one (at its 16-byte alignment): its byte offset."""
        self.align()
        base = self.pos()
        self.blob.words += other.words
        for w, b in other.pointers.items():
            self.blob.pointers[w + base // 4] = b + base
        for w, n in other.types.items():
            self.blob.types[w + base // 4] = n
        for w, n in other.symbols.items():
            self.blob.symbols[w + base // 4] = n
        for w in other.empty_lists:
            self.blob.empty_lists.add(w + base // 4)
        return base


def merge(districts, mesh_aids):
    """One city (grid, cells, segments, nodes, branches) from the districts' decoded ones. mesh_aids:
    the aids of the nav meshes havenj2 has."""
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
            # a pedestrian segment on a nav mesh no level has (ctygenc has some): nav mesh 0, which
            # the traffic engine never spawns citizens on (a spawn needs its nav mesh)
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
            if b["dest"] > nav_blob.LINK_BASE:
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
        center = [x0 + CELL / 2, lo[1] - OUTSIDE_CELL_DEPTH, z0 + CELL / 2]
        radius = 0.0
        if heights:
            y_lo, y_hi = min(h[0] for h in heights), max(h[1] for h in heights)
            center[1] = (y_lo + y_hi) / 2
            radius = math.sqrt(2 * (CELL / 2) ** 2 + ((y_hi - y_lo) / 2) ** 2)
        assert radius > 0 or not segs, f"cell {i}: segments out of every district"
        cells.append(struct.pack("<4fIHHbbBBI", *center, radius, start, 0, i, len(incoming),
                                 len(segs), 0, 0, 0))
    assert len(segments) < 32768
    grid = {"lo": lo, "hi": hi, "dims": dims, "height": height}
    return grid, cells, segments, nodes, branches


def write_city(w, grid, cells, segments, nodes, branches, camera_ceiling):
    """The merged city-level-info at the start of the writer's blob."""
    lo, hi, dims, height = grid["lo"], grid["hi"], grid["dims"], grid["height"]
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
        w.blob.symbols[(node_array + 32 * i + 28) // 4] = LEVEL
    w.align()
    branch_array = w.bytes(b"".join(branches))
    w.pointer(info + 64, cell_array)
    w.pointer(info + 72, segment_array)
    w.pointer(info + 76, graph)
    w.pointer(tag + 8, node_array)
    w.pointer(tag + 12, branch_array)


def write_height_map():
    """Jak 2's *traffic-height-map* as a Jak 3 source file (same xz-height-map layout), its 8960
    heights one grid row per line. Returns the grid's dimensions."""
    text = open(HEIGHT_MAP_JAK2).read()
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
    out = [
        ";;-*-Lisp-*-",
        "(in-package goal)",
        "",
        ";; name: havenj2-height-map.gc",
        ";; name in dgo: havenj2-height-map",
        ";; dgos: HJ2",
        "",
        ";; og:jak2-haven-city generated by custom_assets/jak3/levels/havenj2/gen_havenj2_nav.py, do",
        ";; not edit. Jak 2's traffic height map (goal_src/jak2/levels/city/traffic/",
        ";; traffic-height-map.gc): the height the city's vehicles fly at, over Jak 2's city. havenj2's",
        ";; DGO has it in place of Jak 3's (traffic-height-map.gc, CWI), which follows Jak 3's city.",
        "",
        header,
        *rows,
        "                                 )",
        "                               )",
        "        )",
        "",
    ]
    write_if_changed(HEIGHT_MAP_OUT, "\n".join(out))
    return dims


def main():
    dims = write_height_map()
    print(f"wrote {HEIGHT_MAP_OUT} ({dims[0]} x {dims[1]} heights)")
    districts, meshes = {}, {}
    for name in sorted(os.listdir(ENTITIES)):
        if name.endswith("-city.json"):
            level = name[: -len("-city.json")]
            districts[level] = nav_blob.decode_city(nav_blob.Blob(os.path.join(ENTITIES, name)))
            nav_path = os.path.join(ENTITIES, level + "-nav.json")
            if os.path.exists(nav_path):
                meshes[level] = nav_blob.Blob(nav_path)
    mesh_aids = {blob.u32(byte + 44) for blob in meshes.values() for byte in blob.roots.values()}
    grid, cells, segments, nodes, branches = merge(districts, mesh_aids)
    w = Writer()
    write_city(w, grid, cells, segments, nodes, branches,
               max(c["camera_ceiling"] for c in districts.values()))
    n_meshes = 0
    for level, blob in meshes.items():
        base = w.append_blob(blob)
        for root, byte in blob.roots.items():
            w.blob.roots[f"nav-mesh-{level}-{root}"] = byte + base
            n_meshes += 1
    write_if_changed(OUT, json.dumps(w.blob.to_json(), separators=(",", ":")))
    print(f"{len(districts)} districts: grid {grid['dims']}, {len(cells)} cells, "
          f"{len(segments)} segments, {len(nodes)} nodes, {len(branches)} branches, "
          f"{n_meshes} nav meshes, {len(w.blob.words) * 4 // 1024} KB")


if __name__ == "__main__":
    main()
