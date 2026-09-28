"""Relocatable GOAL data, as the decompiler exports it and the level builder reads it back.

The decompiler copies the data a bsp points to (a level's nav meshes, its city-level-info...) to
decompiler_out/<game>/entities/<level>-<what>.json, see decompiler/level_extractor/extract_nav.h.
The level builder writes such a blob into a bsp as it is ("nav_data" in a level .jsonc, see
goalc/build_level/common/DataBlob.h).

A blob is: words, pointers (word index -> byte offset in the blob), types and symbols (word index ->
name), empty lists, and roots (name -> byte offset).
"""

import json
import struct


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


class Writer:
    """Builds a blob (words, pointers, types, symbols) at 16-byte aligned places."""

    def __init__(self):
        self.blob = Blob()

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


def patch(raw, offset, fmt, value):
    """raw (bytes) with a value packed at offset."""
    b = bytearray(raw)
    struct.pack_into(fmt, b, offset, value)
    return bytes(b)
