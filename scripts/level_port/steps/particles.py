"""Particles: a level's particle effects, translated from the source game's definitions.

Jak 2 draws a lot of its world with particles: every sign and poster of its city is a 3D sprite,
every lamp a glow, launched by part-spawner actors (the <level>-part etypes) placed in the level.
Jak 3 has the same particle system, so the source game's definitions (defpart, defpartgroup) are
kept and translated:
  - part and group ids are moved to ids the target game's code doesn't use while the level is
    loaded (the level's "parts" and "groups" ranges),
  - group names get the port's prefix, the group and item flags the target game's bit names,
  - textures: the source game's common effects are the target game's own when it has them (the
    game pair's TPAGE_EQUIVALENTS); every other one goes in a texture page of the level's own
    (sprite_textures in its .jsonc: the level builder copies them from the source game's .fr3
    files, the level code makes the texture-page at runtime with the mod's <prefix>sprite-page-new
    and hands it to <prefix>sprite-page-register),
  - the callbacks (:func, :birth-func) are the target game's when it has them, else ported by the
    mod ("ported_callbacks", their text in the port's folder) or copied (the manifest's
    "copied_callbacks", and the source game's splash callbacks, check-drop-level-*),
  - sounds (:sound) are kept: the same static-sound-spec in both games, played from the source
    game's banks the level wants (steps/sound.py),
The part spawners become the target game's part-spawner actors, with their ambient sound
(effect_lumps).

Writes <level>-part.gc into the level's code (its DGO) and returns the actors and the sprite
texture list to the levels step, which writes the level's .jsonc. A part spawner goes to the level
holding its source level: with "levels" naming other levels' sources (a city's districts, whose hub
holds the particle code and texture page), each of those levels gets its own spawners.

Manifest:
  "particles": {                       the port's
    "copied_callbacks": [source callbacks copied into the level code, see copied_func_text],
    "level_callbacks": [callbacks of the target game's level code the port's levels include],
    "reserved": {"parts": [[first, last], ...], "groups": [[first, last], ...]}  ids never
                                       taken (the target game's level code linked with the levels)
    "auto_start": {"parts": id, "groups": id}   where "auto" ids start
  }
"auto" (Allocator): the ids are taken from auto_start up, past every reserved and fixed range,
and the page is an id the target game's texture directory gives no texture, whose texture pool
slots (the PC pool lays each page's textures out after the ones of the pages before it, a page
spilling over the slots of the next ones) are free: no texture of GAME.fr3 there, and no other
level's sprite page, so no two levels' particles ever share a slot or an id.
  "particles": {                       on a level
    "files": [the source game's particle files],
    "textures_from": [the source .fr3 files the sprite textures come from],
    "page": its texture page: a texture-page-dir entry the target game never uses, or "auto",
    "parts": [first id, end], "groups": [first id, end]      the ids the definitions move to, or
                                                             "auto"
    optional:
    "target_textures": [[target .fr3 level, tpage, [names]]]  added at the end of the page
    "source_textures": [[source tpage, [names]]]  source game textures (from textures_from) added
                   after them, for the mod's code to find by name (a city's minimap)
    "levels": [the source levels whose part spawners are placed, else the level's own],
    "max_vis_dist": [meters, [source levels kept as they are]]   how far from the camera a spawner
                   is born at most (the source game's vis-dist only mattered with its levels'
                   visibility data, which the port's levels don't have: without a cap, every
                   spawner of a district is alive and spawning),
    "base_aid": the actor id of the first part spawner (else the level builder numbers them),
    "ported_callbacks": {"<source callback>": ours}, with "callbacks_file": their text,
    "data": {"<source define>": ours}          data arrays copied (the neon signs' timings),
    "group_arrays": {"<source array>": ours}   group id arrays, their ids moved,
    "extra_groups": {"<source group>": our array}   groups the mod's code launches, with an array
    "extra_parts": {"<source part id>": our define}   parts the mod's code launches by id (outside
                   any group: the whack-a-metal's miss marks), our id as an int
    "sign_actors": {"<source etype>": ours}    actors with their own particle code, kept
    "skip_groups": [source groups whose part spawners aren't placed (a race's scoreboard)],
    "kiosks": {"<source etype>": {"group": source group, "suffix": name suffix,
                                  "vis_dist": default vis-dist}}   actors whose hologram is a group
    "part_specs": {"<source part id>": {"<init-spec field>": [its values, as written]}}  the
                   values of these fields replaced (a color changed: ":r": ["32.0", "64.0"])
  }
"""

import os
import re
import subprocess
import textwrap

from ..common import goal_lisp as gl
from ..common.files import write_if_changed
from ..common.goal_lisp import Atom, QUOTE
from . import extract as extract_step


# texture tables ##################################################################################


def load_tpages(game):
    ids = {}
    for name, idx in re.findall(r"\(defconstant ([a-z0-9-]+) (\d+)\)",
                                open(f"goal_src/{game}/engine/data/tpages.gc").read()):
        ids[name] = int(idx)
    return ids


def load_textures(game):
    """{(tpage, name): index}"""
    out = {}
    for name, tpage, idx in re.findall(r"\(def-tex ([^\s()]+) ([^\s()]+) (\d+)\)",
                                       open(f"goal_src/{game}/engine/data/textures.gc").read()):
        out[(tpage, name)] = int(idx)
    return out


def fr3_textures(game, level, filter_text):
    """fr3_check's texture list of a .fr3 file."""
    return subprocess.run([os.path.abspath(extract_step.FR3_CHECK), f"out/{game}/fr3/{level}.fr3",
                           "--textures", filter_text],
                          capture_output=True, text=True, check=True).stdout


def fr3_texture_index(game, levels):
    """{(tpage, name): (fr3 level, w, h)} for the textures of these levels' fr3 files."""
    out = {}
    for level in levels:
        text = fr3_textures(game, level, "/")
        for m in re.finditer(r"^(\S+)/(\S+)\s+(\d+)x(\d+)\s", text, re.M):
            key = (m.group(1), m.group(2))
            if key not in out:
                out[key] = (level, int(m.group(3)), int(m.group(4)))
    return out


class Textures:
    """The level's texture page: the source textures its particles use, then target ones."""

    def __init__(self, port, fr3_levels, page):
        self.port = port
        self.pair = port.pair
        self.sprite_page = page
        src, dst = port.source.NAME, port.target.NAME
        self.src_pages = load_tpages(src)
        self.src_tex = load_textures(src)
        self.src_by_id = {(self.src_pages[tp], idx): (tp, nm)
                          for (tp, nm), idx in self.src_tex.items() if tp in self.src_pages}
        self.dst_tex = load_textures(dst)
        self.fr3 = fr3_texture_index(src, fr3_levels)
        self.page = []  # (fr3 level, tpage, name, w, h, game)
        self.page_index = {}

    def in_page(self, tpage, name):
        """Index of a source texture in the level's page (added on first use)."""
        key = (tpage, name)
        if key not in self.page_index:
            if key not in self.fr3:
                raise KeyError(f"no {self.port.source.TITLE} fr3 has the texture {tpage}/{name}")
            level, w, h = self.fr3[key]
            self.page_index[key] = len(self.page)
            self.page.append((level, tpage, name, w, h, self.port.source.NAME))
        return self.page_index[key]

    def add_target(self, level, tpage, names):
        """Textures of a target game .fr3, at the end of the page."""
        game = self.port.target.NAME
        text = fr3_textures(game, level, tpage + "/")
        sizes = {m.group(1): (int(m.group(2)), int(m.group(3))) for m in re.finditer(
            r"^" + re.escape(tpage) + r"/(\S+)\s+(\d+)x(\d+)\s", text, re.M)}
        for name in names:
            if name not in sizes:
                raise KeyError(f"no texture {tpage}/{name} in {self.port.target.TITLE}'s "
                               f"{level}.fr3")
            w, h = sizes[name]
            self.page.append((level, tpage, name, w, h, game))

    def texture_form(self, name, tpage):
        """The :texture argument for the target game."""
        ours = self.pair.TPAGE_EQUIVALENTS.get(tpage)
        if ours and (ours, name) in self.dst_tex:
            return [Atom(name), Atom(ours)]
        idx = self.in_page(tpage, name)
        return [Atom("new"), [QUOTE, Atom("static")], [QUOTE, Atom("texture-id")],
                Atom(":index"), Atom(str(idx)), Atom(":page"), Atom(str(self.sprite_page))]

    def remap_id(self, value):
        """A source texture-id value -> ours, or None if it isn't one. The texture groups of the
        smoke and fires (birth-func-texture-group) name the source game's effects textures: the
        target game's of the same name."""
        if not value or value & 0xff:
            return None
        value &= 0xffffffff
        key = (value >> 20, (value >> 8) & 0xfff)
        if key not in self.src_by_id:
            return None
        tpage, name = self.src_by_id[key]
        ours = self.pair.TPAGE_EQUIVALENTS.get(tpage)
        if ours and (ours, name) in self.dst_tex:
            return (self.pair.TARGET_TPAGES[ours] << 20) | (self.dst_tex[(ours, name)] << 8)
        idx = self.in_page(tpage, name)
        return (self.sprite_page << 20) | (idx << 8)


# source definitions ##############################################################################


class Defs:
    def __init__(self, files):
        self.parts = {}    # id -> form
        self.groups = {}   # name -> form
        self.group_ids = {}  # id -> name
        self.funcs = {}    # name -> form
        self.data = {}     # define name -> form
        self.func_files = {}  # name -> path
        for path in files:
            for form in gl.read_all(open(path, encoding="utf-8").read()):
                if not gl.is_list(form):
                    continue
                head = str(form[0])
                if head == "defpart":
                    self.parts[int(form[1])] = form
                elif head == "defpartgroup":
                    self.groups[str(form[1])] = form
                    self.group_ids[int(gl.keyword_args(form, 2)[":id"])] = str(form[1])
                elif head in ("defun", "defbehavior"):
                    # a behavior callback that doesn't use its process (palcab's bird bob) is
                    # copied as a function
                    if head == "defbehavior":
                        form = [Atom("defun"), form[1]] + form[3:]
                    self.funcs[str(form[1])] = form
                    self.func_files[str(form[1])] = path
                elif head == "define":
                    self.data[str(form[1])] = form


def walk(form):
    yield form
    if isinstance(form, list):
        for f in form:
            yield from walk(f)


def reserved_ranges(glob, kind):
    """The manifest's reserved [first, last] ranges of part or group ids (one, or a list)."""
    ranges = glob.get("reserved", {}).get(kind, [])
    return [ranges] if ranges and isinstance(ranges[0], int) else ranges


class Allocator:
    """The texture pages and the part and group ids of the levels whose particles say "auto"."""

    LIMITS = {"parts": 5500, "groups": 1700}  # the target game's part and group id tables

    def __init__(self, port):
        glob = port.get("particles", {})
        self.used = {kind: set() for kind in self.LIMITS}
        for kind in self.LIMITS:
            for a, b in reserved_ranges(glob, kind):
                self.used[kind] |= set(range(a, b + 1))
            for level in port.levels:
                rng = level.get("particles", {}).get(kind)
                if isinstance(rng, list):
                    self.used[kind] |= set(range(*rng))
        self.start = glob.get("auto_start", {"parts": 1, "groups": 1})
        sizes = tpage_dir_sizes(port.target.NAME)
        self.sizes = sizes
        self.base = [0]
        for n in sizes:
            self.base.append(self.base[-1] + n)
        # the slots and pages GAME's textures take (always loaded)
        self.slots = set()
        self.pages = set()
        for m in re.finditer(r"combo 0x([0-9a-f]{8}) pool true",
                             fr3_textures(port.target.NAME, "GAME", "")):
            combo = int(m.group(1), 16)
            self.pages.add(combo >> 16)
            self.slots.add(self.base[combo >> 16] + (combo & 0xffff))

    def ids(self, kind, commit):
        """The free ids of a kind, from auto_start up; commit: taken as they are given."""
        i = self.start[kind]
        while True:
            if i >= self.LIMITS[kind]:
                raise ValueError(f"no {kind} id left under {self.LIMITS[kind]}")
            if i not in self.used[kind]:
                if commit:
                    self.used[kind].add(i)
                yield i
            i += 1

    def take_page(self, page, count):
        """A page used by a level (its slots and its directory entry)."""
        slots = set(range(self.base[page], self.base[page] + count))
        if page in self.pages or slots & self.slots:
            raise ValueError(f"texture page {page} ({count} textures) overlaps another page's "
                             "texture pool slots or directory entry")
        self.pages.add(page)
        self.slots |= slots

    def page(self, count):
        """A free page for count textures: an id with no texture in the target game, from 1500
        up (below 2048: particle data keeps texture ids in signed fields)."""
        for page in list(range(1500, 2048)) + list(range(1, 1500)):
            if self.sizes[page] == 0 and page not in self.pages and not (
                    set(range(self.base[page], self.base[page] + count)) & self.slots):
                self.take_page(page, count)
                return page
        raise ValueError(f"no free texture page for {count} textures")


def tpage_dir_sizes(game):
    """The texture count of each page of the target game's texture directory (the PC texture
    pool's layout, game/graphics/texture/<game>_tpage_dir.cpp)."""
    text = open(f"game/graphics/texture/{game}_tpage_dir.cpp").read()
    body = text[text.index("{", text.index("tpage_dir")) + 1:text.index("};")]
    return [int(x, 16) if x.startswith("0x") else 0
            for x in re.findall(r"0x[0-9a-fA-F]+|[A-Z_]+_COUNT", body)]


class Translator:
    def __init__(self, port, level_cfg, defs, textures, ids=None):
        self.port = port
        self.pair = port.pair
        self.prefix = port.prefix
        glob = port.get("particles", {})
        self.defs = defs
        self.tex = textures
        self.data_names = level_cfg.get("data", {})
        self.target_callbacks = self.pair.TARGET_CALLBACKS | set(glob.get("level_callbacks", []))
        self.ported_callbacks = level_cfg.get("ported_callbacks", {})
        self.copied_names = set(glob.get("copied_callbacks", []))
        self.part_specs = level_cfg.get("part_specs", {})
        self.part_map = {}
        self.group_map = {}  # source group name -> (new name, new id)
        # the ids: the level's ranges but the reserved ones, or the allocator's ("auto")
        if ids:
            self.part_ids, self.group_ids = ids
            self.part_range = self.group_range = "auto"
        else:
            self.part_range = range(*level_cfg["parts"])
            self.group_range = range(*level_cfg["groups"])
            rp, rg = reserved_ranges(glob, "parts"), reserved_ranges(glob, "groups")
            self.part_ids = iter([i for i in self.part_range if not any(a <= i <= b for a, b in rp)])
            self.group_ids = iter([i for i in self.group_range
                                   if not any(a <= i <= b for a, b in rg)])
        self.drop_funcs = {}  # source name -> (new name, launched parts [(id, 3d?)])
        self.copied_funcs = {}  # source name -> new name
        self.missing = set()  # parts referred to but never defined

    # ids

    def part(self, pid):
        """Our id for a source part, None for one the source game never defines (a few
        next-launchers point to nothing: the particle system then stops there)."""
        if pid not in self.part_map:
            if pid not in self.defs.parts:
                self.missing.add(pid)
                return None
            new = next(self.part_ids, None)
            if new is None:
                raise ValueError(f"no part id left in {self.part_range}")
            self.part_map[pid] = new
            self.scan_part(pid)
        return self.part_map[pid]

    def group(self, name):
        if name not in self.group_map:
            new = next(self.group_ids, None)
            if new is None:
                raise ValueError(f"no group id left in {self.group_range}")
            self.group_map[name] = (f"group-{self.prefix}" + name[len("group-"):], new)
            for item in gl.keyword_args(self.defs.groups[name], 2)[":parts"]:
                self.part(int(item[1]))
                args = gl.keyword_args(item, 2)
                if ":binding" in args:
                    self.part(int(args[":binding"]))
        return self.group_map[name]

    def scan_part(self, pid):
        """The parts and callbacks a part refers to."""
        for spec in gl.keyword_args(self.defs.parts[pid], 2)[":init-specs"]:
            field = str(spec[0])
            if field == ":next-launcher":
                self.part(int(spec[1]))
            if field in (":func", ":birth-func"):
                self.func(str(spec[1][1]))

    def func(self, name):
        if name in self.target_callbacks:
            return name
        if name in self.ported_callbacks:
            return self.ported_callbacks[name]
        if name in self.copied_names and name in self.defs.funcs:
            if name not in self.copied_funcs:
                self.copied_funcs[name] = self.prefix + name
                for f in walk(self.defs.funcs[name]):
                    if gl.is_list(f, "->") and len(f) == 3 and f[1] == Atom("*part-id-table*"):
                        self.part(int(f[2]))
            return self.copied_funcs[name]
        m = self.pair.DROP_FUNC.fullmatch(name)
        if m:
            if name not in self.drop_funcs:
                launched = []
                for f in walk(self.defs.funcs[name]):
                    if gl.is_list(f, "launch-particles"):
                        three_d = any(a == Atom("*sp-particle-system-3d*") for a in f)
                        ref = next(a for a in f if gl.is_list(a, "->"))
                        launched.append((int(ref[2]), three_d))
                self.drop_funcs[name] = (f"{self.prefix}check-drop-level-{m.group(1)}", launched)
                for pid, _ in launched:
                    self.part(pid)
            return self.drop_funcs[name][0]
        raise KeyError(f"particle callback {name} isn't ported")

    # translation

    def userdata(self, value):
        """(:userdata :data (new 'static 'boxed-array :type int32/object ...)) with source texture
        ids and data names remapped."""
        if not gl.is_list(value, "new"):
            return value
        out = []
        for item in value:
            if gl.is_list(item) and item[:1] == [QUOTE] and str(item[1]) in self.data_names:
                out.append([QUOTE, Atom(self.data_names[str(item[1])])])
            elif gl.is_list(item, "the") and item[1] == Atom("binteger"):
                raw = gl.parse_int(item[2])
                new = self.tex.remap_id(raw * 8) if raw is not None else None
                out.append([Atom("the"), Atom("binteger"), Atom(str(new // 8))] if new else item)
            elif (isinstance(item, Atom) and gl.parse_int(item) is not None
                  and item not in ("int32",)):
                new = self.tex.remap_id(gl.parse_int(item))
                # an int32 array: page ids from 2048 up give a negative value
                out.append(Atom(str(new - (1 << 32) if new >= 1 << 31 else new)) if new else item)
            else:
                out.append(item)
        return out

    def part_form(self, pid):
        specs = []
        replaced = self.part_specs.get(str(pid), {})
        for spec in gl.keyword_args(self.defs.parts[pid], 2)[":init-specs"]:
            field = str(spec[0])
            if field in replaced:
                spec = [spec[0]] + [Atom(v) for v in replaced[field]]
            if field == ":texture":
                spec = [spec[0], self.tex.texture_form(str(spec[1][0]), str(spec[1][1]))]
            elif field == ":next-launcher":
                target = self.part(int(spec[1]))
                if target is None:
                    continue
                spec = [spec[0], Atom(str(target))]
            elif field in (":func", ":birth-func"):
                spec = [spec[0], [QUOTE, Atom(self.func(str(spec[1][1])))]]
            elif field == ":userdata" and len(spec) > 2 and spec[1] == Atom(":data"):
                spec = [spec[0], spec[1], self.userdata(spec[2])]
            elif field == ":flags":
                spec = [spec[0], [Atom(self.pair.CPUINFO_FLAGS.get(str(f), str(f)))
                                  for f in spec[1]]]
            specs.append(spec)
        return specs

    def item_form(self, item):
        """An sp-item, None for one launching (or bound to) a part the source game never defines."""
        launcher = self.part(int(item[1]))
        if launcher is None:
            return None
        out = [Atom("sp-item"), Atom(str(launcher))]
        args = item[2:]
        i = 0
        while i < len(args):
            key, value = str(args[i]), args[i + 1]
            if key == ":flags":
                value = [Atom(self.pair.ITEM_FLAGS[str(f)]) for f in value]
            elif key == ":binding":
                bound = self.part(int(value))
                if bound is None:
                    return None
                value = Atom(str(bound))
            out += [Atom(key), value]
            i += 2
        return out

    def group_text(self, name):
        form = self.defs.groups[name]
        new_name, new_id = self.group_map[name]
        args = gl.keyword_args(form, 2)
        lines = [f"(defpartgroup {new_name}", f"  :id {new_id}"]
        for key in (":duration", ":linger-duration"):
            if key in args:
                lines.append(f"  {key} {gl.dump(args[key])}")
        if ":flags" in args:
            flags = " ".join(self.pair.GROUP_FLAGS[str(f)] for f in args[":flags"])
            lines.append(f"  :flags ({flags})")
        for key in (":bounds", ":rotate", ":scale"):
            if key in args:
                lines.append(f"  {key} {gl.dump(args[key])}")
        items = [gl.dump(f) for f in (self.item_form(it) for it in args[":parts"]) if f]
        lines.append("  :parts (" + ("\n          ".join(items)) + ")")
        lines.append("  )")
        return "\n".join(lines)

    def part_text(self, pid):
        specs = self.part_form(pid)
        body = "\n    ".join(gl.dump(s) for s in specs)
        return f"(defpart {self.part_map[pid]}\n  :init-specs ({body})\n  )"


# actors ##########################################################################################


def vis_dist(cfg, src, lump, meter):
    """A spawner's vis-dist (game units): the source's, capped by cfg's "max_vis_dist" but in its
    exempt source levels; None: the target game's default (10km)."""
    value = float(lump["vis-dist"]) if "vis-dist" in lump else None
    cap = cfg.get("max_vis_dist")
    if not cap or src in cap[1]:
        return value
    return min(value, cap[0] * meter) if value is not None else cap[0] * meter


def effect_lumps(lump):
    """A part spawner's ambient sound, as the source game's lumps give it: effect-name (the
    sound), effect-param (its sound-spec parameters) and cycle-speed (seconds between plays and
    their random part, -1: looped). The target game's part-spawner plays it from the same lumps
    (ambient-sound, gsound.gc); the sound is in the source game's banks the level wants."""
    out = {}
    if "effect-name" in lump:
        out["effect-name"] = ["symbol", str(lump["effect-name"]).lstrip("'")]
        for key in ("effect-param", "cycle-speed"):
            if key in lump:
                out[key] = ["float"] + [float(v) for v in lump[key]]
    return out


def part_actors(port, level, cfg, tr):
    """The level's part spawners (and sign and kiosk actors): (source level, comment, actor)
    list."""
    base_aid = cfg.get("base_aid")
    signs = cfg.get("sign_actors", {})
    skipped = set(cfg.get("skip_groups", []))
    kiosks = cfg.get("kiosks", {})
    title = port.source.TITLE
    out = []
    for src in cfg.get("levels", level.sources):
        for actor in port.story.level_actors(src):
            etype = actor["etype"]
            lump = actor["lump"]
            name = lump["name"]
            trans = [round(x, 4) for x in actor["trans"][:3]]
            entity = {"trans": trans, "etype": None}
            if base_aid is not None:
                entity["aid"] = base_aid + len(out)
            entity.update({
                "game_task": 0,
                "quat": [round(x, 4) for x in actor["quat"]],
                "bsphere": trans + [round(actor["bsphere"][3], 4)],
                "lump": {"name": name},
            })
            vis = vis_dist(cfg, src, lump, port.source.METER)
            if vis is not None:
                entity["lump"]["vis-dist"] = ["float", vis]
            if lump.get("art-name") in skipped:
                continue
            if ((etype.endswith("-part") or etype == "part-spawner")
                    and lump.get("art-name") in tr.defs.groups):
                new_name, _ = tr.group(lump["art-name"])
                entity["etype"] = "part-spawner"
                entity["lump"]["art-name"] = new_name
                entity["lump"].update(effect_lumps(lump))
                out.append((src, f"{title}'s {name} ({src}): {lump['art-name']}", entity))
            elif etype in signs:
                entity["etype"] = signs[etype]
                out.append((src, f"{title}'s {name} ({src})", entity))
            elif etype in kiosks:
                kiosk = kiosks[etype]
                new_name, _ = tr.group(kiosk["group"])
                entity["etype"] = "part-spawner"
                entity["lump"]["name"] = name + kiosk["suffix"]
                entity["lump"]["art-name"] = new_name
                entity["lump"].setdefault("vis-dist", ["float", kiosk["vis_dist"]])
                out.append((src, f"{title}'s {name} ({src}): its hologram", entity))
    return out


def static_launchers(port, defs, actors):
    """How many launchers the static part spawners (the pair's STATIC_GROUP_FLAG) hand to their
    level's part engine: Jak 3 gives each level part-engine-max x 16 of them."""
    total = 0
    by_new = {}
    for name in defs.groups:
        by_new[f"group-{port.prefix}" + name[len("group-"):]] = name
    for _, _, actor in actors:
        if "art-name" not in actor["lump"]:
            continue
        form = defs.groups[by_new[actor["lump"]["art-name"]]]
        args = gl.keyword_args(form, 2)
        if any(str(f) == port.pair.STATIC_GROUP_FLAG for f in args.get(":flags", [])):
            total += len(args[":parts"])
    return total


# output ##########################################################################################


def group_array_text(defs, tr, source_name, ours):
    ids = [int(gl.parse_int(x)) for x in defs.data[source_name][2][5:]]
    new = " ".join(str(tr.group(defs.group_ids[i])[1]) for i in ids)
    return f"(define {ours} (new 'static 'boxed-array :type int32 {new}))"


def section(title):
    return f";; {title} " + "/" * (100 - 4 - len(title))


def translate(port, level, page, ids):
    """The level's particles translated for a texture page and ids (None: its own ranges)."""
    cfg = level["particles"]
    defs = Defs(cfg["files"])
    textures = Textures(port, cfg["textures_from"], page)
    tr = Translator(port, cfg, defs, textures, ids)
    actors = part_actors(port, level, cfg, tr)
    group_arrays = cfg.get("group_arrays", {})
    extra_groups = cfg.get("extra_groups", {})
    for source_name in group_arrays:
        for i in defs.data[source_name][2][5:]:
            tr.group(defs.group_ids[int(gl.parse_int(i))])
    for group in extra_groups:
        tr.group(group)
    extra_parts = cfg.get("extra_parts", {})
    for pid in extra_parts:
        tr.part(int(pid))
    # data arrays (the neon signs': bit masks and timings, no ids)
    data_text = [gl.pretty([Atom("define"), Atom(ours)] + defs.data[source_name][2:])
                 for source_name, ours in cfg.get("data", {}).items()]

    # parts in id order, their groups after them (the part ids must be set when a group launches)
    parts_text = [tr.part_text(pid) for pid in sorted(tr.part_map, key=lambda p: tr.part_map[p])]
    groups_text = [tr.group_text(n) for n in sorted(tr.group_map, key=lambda n: tr.group_map[n][1])]
    arrays = [group_array_text(defs, tr, src, ours) for src, ours in group_arrays.items()]
    arrays += [f"(define {ours} (new 'static 'boxed-array :type int32 {tr.group(group)[1]}))"
               for group, ours in extra_groups.items()]
    arrays += [f"(define {ours} {tr.part(int(pid))})" for pid, ours in extra_parts.items()]
    drop_text = [port.pair.drop_func_text(n, launched, tr.part_map)
                 for n, launched in sorted(tr.drop_funcs.values())]
    source_dir = f"goal_src/{port.source.NAME}"
    copied_text = [port.pair.copied_func_text(
        defs.funcs[n], tr.copied_funcs[n], tr.part_map,
        os.path.relpath(defs.func_files[n], source_dir).replace(os.sep, "/"), cfg.get("data", {}))
        for n in sorted(tr.copied_funcs)]
    ported_text = []
    if "callbacks_file" in cfg:
        ported_text = [open(port.port_file(cfg["callbacks_file"]), encoding="utf-8").read()]
    for target_level, tpage, names in cfg.get("target_textures", []):
        textures.add_target(target_level, tpage, names)
    for tpage, names in cfg.get("source_textures", []):
        for name in names:
            textures.in_page(tpage, name)
    return dict(defs=defs, textures=textures, tr=tr, actors=actors, data_text=data_text,
                parts_text=parts_text, groups_text=groups_text, arrays=arrays, drop_text=drop_text,
                copied_text=copied_text, ported_text=ported_text, page=page)


def write_level(port, level, alloc):
    """<level>-part.gc and the part spawners. Returns ({our level: actors}, sprite_textures,
    {our level: part-engine-max}, stats). alloc: the Allocator of the "auto" pages and ids."""
    cfg = level["particles"]
    name = level.name
    auto_ids = cfg["parts"] == "auto"
    assert auto_ids == (cfg["groups"] == "auto"), f"{name}: parts and groups both auto or not"

    def ids(commit):
        return (alloc.ids("parts", commit), alloc.ids("groups", commit)) if auto_ids else None

    if cfg["page"] == "auto":
        # a first pass counts the textures, the page is chosen, the second pass uses it
        count = len(translate(port, level, 0, ids(False))["textures"].page)
        page = alloc.page(count)
        st = translate(port, level, page, ids(True))
    else:
        page = cfg["page"]
        st = translate(port, level, page, ids(True))
        alloc.take_page(page, len(st["textures"].page))
    defs, textures, tr, actors = st["defs"], st["textures"], st["tr"], st["actors"]
    data_text, parts_text, groups_text = st["data_text"], st["parts_text"], st["groups_text"]
    arrays, drop_text = st["arrays"], st["drop_text"]
    copied_text, ported_text = st["copied_text"], st["ported_text"]
    source_dir = f"goal_src/{port.source.NAME}"

    def id_span(ids_used):
        return f"{min(ids_used)}-{max(ids_used)}" if ids_used else "none"

    files = ", ".join(os.path.relpath(f, source_dir).replace(os.sep, "/") for f in cfg["files"])
    title = port.source.TITLE
    summary = (f"{title}'s particle effects of {', '.join(cfg.get('levels', level.sources))}: "
               f"{len(tr.part_map)} parts (ids {id_span(tr.part_map.values())}), "
               f"{len(tr.group_map)} groups (ids {id_span([g[1] for g in tr.group_map.values()])}"
               f"), {len(textures.page)} sprite texture(s) in its own texture page {page}, "
               f"translated from {title}'s {files}.")
    lines = [
        ";;-*-Lisp-*-",
        "(in-package goal)",
        "",
        f";; name: {name}-part.gc",
        f";; name in dgo: {name}-part",
        f";; dgos: {level.dgo}",
        "",
        *port.generated_lines(),
        *[";; " + line for line in textwrap.wrap(summary, 97, break_on_hyphens=False,
                                                   break_long_words=False)],
        "",
    ]
    if textures.page:
        names = " ".join(f'"{t[2]}"' for t in textures.page)
        sizes = " ".join(f"#x{(t[4] << 16) | t[3]:x}" for t in textures.page)
        var = f"*{name}-sprite"
        lines += [
            f";; {name}'s texture page {page}: the sprite textures of its particles (their "
            "pixels are in its",
            f";; fr3, see sprite_textures in {name}.jsonc), as names and sizes (w | h << 16)",
            f"(define {var}-names* (new 'static 'boxed-array :type string {names}))",
            "",
            f"(define {var}-sizes* (new 'static 'boxed-array :type uint32 {sizes}))",
            "",
            ";; made while the level loads, handed to the texture system when it is activated",
            f"({port.prefix}sprite-page-register '{name} ({port.prefix}sprite-page-new "
            f"{page} {var}-names* {var}-sizes*))",
            "",
        ]
    # the data first: the copied callbacks may read it
    if data_text:
        lines += [section("data"), ""] + [t + "\n" for t in data_text]
    lines += [section("callbacks"), ""]
    lines += [t + "\n" for t in ported_text + copied_text + drop_text]
    lines += [section("parts"), ""] + [t + "\n" for t in parts_text]
    lines += [section("groups"), ""] + [t + "\n" for t in groups_text]
    if arrays:
        lines += [f";; group ids used by {name}'s actors"] + arrays
    write_if_changed(f"{port.code_dir}/{name}-part.gc", "\n".join(lines).rstrip() + "\n")

    source_game = port.source.NAME
    sprite_textures = {"page": page, "game": source_game,
                       "textures": [[t[0], t[1], t[2]] + ([t[5]] if t[5] != source_game else [])
                                    for t in textures.page]}
    by_level = {}
    for src, comment, actor in actors:
        by_level.setdefault(port.level_map[src], []).append((src, comment, actor))
    # each level's part engine gets 16 launchers per part-engine-max (a uint8)
    engine_max = {lv: min(255, (static_launchers(port, defs, acts) + 15) // 16)
                  for lv, acts in by_level.items()}
    return ({lv: [(c, a) for _, c, a in acts] for lv, acts in by_level.items()},
            sprite_textures, engine_max,
            dict(page=page, parts=len(tr.part_map), groups=len(tr.group_map),
                 textures=len(textures.page), actors=len(actors),
                 static_launchers=static_launchers(port, defs, actors)))
