"""Jak 2's city navigation data, as exported by the decompiler (decompiler_out/jak2/entities/
<level>-nav.json: a relocatable copy of a bsp's city-level-info and nav meshes, see
decompiler/level_extractor/extract_nav.h), decoded and written back.

A blob is: words, pointers (word index -> byte offset in the blob), types and symbols (word index ->
name), empty lists, and roots (name -> byte offset). Jak 2 and Jak 3 share the layouts of
city-level-info, vis-cell, nav-segment, nav-graph, nav-node, nav-branch, nav-graph-link and nav-mesh.
In the file, the cells' segments, the segments' branches, the nodes' branches and the branches'
nodes are indices (the traffic engine turns them into pointers when a level is linked, see
traffic-engine level-link); a branch's destination above 100000 is ~link index.
"""

import json
import struct

LINK_BASE = 100000


class Blob:
    def __init__(self, path=None):
        self.words = []
        self.pointers = {}  # word index -> byte
        self.types = {}     # word index -> name
        self.symbols = {}   # word index -> name
        self.empty_lists = set()
        self.roots = {}
        if path:
            d = json.load(open(path))
            self.words = d["words"]
            self.pointers = {w: b for w, b in d["pointers"]}
            self.types = {w: n for w, n in d["types"]}
            self.symbols = {w: n for w, n in d["symbols"]}
            self.empty_lists = set(d["empty_lists"])
            self.roots = d["roots"]

    # reading ####################################################################################

    def u32(self, byte):
        return self.words[byte // 4]

    def s16(self, byte):
        w = self.words[byte // 4]
        v = (w >> (8 * (byte % 4))) & 0xffff
        return v - 0x10000 if v & 0x8000 else v

    def u16(self, byte):
        return (self.words[byte // 4] >> (8 * (byte % 4))) & 0xffff

    def u8(self, byte):
        return (self.words[byte // 4] >> (8 * (byte % 4))) & 0xff

    def s8(self, byte):
        v = self.u8(byte)
        return v - 0x100 if v & 0x80 else v

    def f32(self, byte):
        return struct.unpack("<f", struct.pack("<I", self.words[byte // 4]))[0]

    def ptr(self, byte):
        """Byte offset a pointer word points to, None if it isn't a pointer."""
        return self.pointers.get(byte // 4)

    def raw(self, byte, size):
        """size bytes from byte, as bytes (plain data only)."""
        return b"".join(struct.pack("<I", self.words[(byte + i) // 4]) for i in range(0, size, 4))

    def to_json(self):
        return {"words": self.words, "pointers": sorted(self.pointers.items()),
                "types": sorted(self.types.items()), "symbols": sorted(self.symbols.items()),
                "empty_lists": sorted(self.empty_lists), "roots": self.roots}


# city-level-info #################################################################################

def decode_city(blob):
    """The city-level-info of a blob: grid, cells, segments and nav graph, as dicts."""
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
