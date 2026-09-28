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
  - sounds are dropped (they are the source game's).
The part spawners become the target game's part-spawner actors.

Writes <level>-part.gc into the level's code (its DGO) and returns the actors and the sprite
texture list to the levels step, which writes the level's .jsonc.

Manifest:
  "particles": {                       the port's
    "copied_callbacks": [source callbacks copied into the level code, see copied_func_text],
    "level_callbacks": [callbacks of the target game's level code the port's levels include],
    "reserved": {"parts": [first, last], "groups": [first, last]}    ids never taken
  }
  "particles": {                       on a level
    "files": [the source game's particle files],
    "textures_from": [the source .fr3 files the sprite textures come from],
    "page": its texture page: a texture-page-dir entry the target game never uses,
    "parts": [first id, end], "groups": [first id, end]      the ids the definitions move to
    optional:
    "target_textures": [[target .fr3 level, tpage, [names]]]  added at the end of the page
    "base_aid": the actor id of the first part spawner (else the level builder numbers them),
    "ported_callbacks": {"<source callback>": ours}, with "callbacks_file": their text,
    "data": {"<source define>": ours}          data arrays copied (the neon signs' timings),
    "group_arrays": {"<source array>": ours}   group id arrays, their ids moved,
    "extra_groups": {"<source group>": our array}   groups the mod's code launches, with an array
    "sign_actors": {"<source etype>": ours}    actors with their own particle code, kept
    "kiosks": {"<source etype>": {"group": source group, "suffix": name suffix,
                                  "vis_dist": default vis-dist}}   actors whose hologram is a group
  }
"""

import os
import re
import subprocess
import textwrap

from ..common import goal_lisp as gl
from ..common.files import write_if_changed
from ..common.goal_lisp import Atom, QUOTE

FR3_CHECK = os.path.abspath("out/build/Release/bin/fr3_check" + (".exe" if os.name == "nt" else ""))


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
    return subprocess.run([FR3_CHECK, f"out/{game}/fr3/{level}.fr3", "--textures", filter_text],
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
                elif head == "defun":
                    self.funcs[str(form[1])] = form
                    self.func_files[str(form[1])] = path
                elif head == "define":
                    self.data[str(form[1])] = form


def walk(form):
    yield form
    if isinstance(form, list):
        for f in form:
            yield from walk(f)


class Translator:
    def __init__(self, port, level_cfg, defs, textures):
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
        self.part_map = {}
        self.group_map = {}  # source group name -> (new name, new id)
        self.part_range = range(*level_cfg["parts"])
        self.group_range = range(*level_cfg["groups"])
        reserved = glob.get("reserved", {})
        rp = reserved.get("parts", [1, 0])
        rg = reserved.get("groups", [1, 0])
        self.part_ids = iter([i for i in self.part_range if not rp[0] <= i <= rp[1]])
        self.group_ids = iter([i for i in self.group_range if not rg[0] <= i <= rg[1]])
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
        for spec in gl.keyword_args(self.defs.parts[pid], 2)[":init-specs"]:
            field = str(spec[0])
            if field == ":sound":
                continue  # the source game's sounds
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
        """An sp-item, None for one launching a part the source game never defines."""
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
                value = Atom(str(self.part(int(value))))
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


def part_actors(port, level, cfg, tr):
    """The level's part spawners (and sign and kiosk actors): (comment, actor) list."""
    base_aid = cfg.get("base_aid")
    signs = cfg.get("sign_actors", {})
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
            if "vis-dist" in lump:
                entity["lump"]["vis-dist"] = ["float", float(lump["vis-dist"])]
            if ((etype.endswith("-part") or etype == "part-spawner")
                    and lump.get("art-name") in tr.defs.groups):
                new_name, _ = tr.group(lump["art-name"])
                entity["etype"] = "part-spawner"
                entity["lump"]["art-name"] = new_name
                out.append((f"{title}'s {name} ({src}): {lump['art-name']}", entity))
            elif etype in signs:
                entity["etype"] = signs[etype]
                out.append((f"{title}'s {name} ({src})", entity))
            elif etype in kiosks:
                kiosk = kiosks[etype]
                new_name, _ = tr.group(kiosk["group"])
                entity["etype"] = "part-spawner"
                entity["lump"]["name"] = name + kiosk["suffix"]
                entity["lump"]["art-name"] = new_name
                entity["lump"].setdefault("vis-dist", ["float", kiosk["vis_dist"]])
                out.append((f"{title}'s {name} ({src}): its hologram", entity))
    return out


def static_launchers(port, defs, actors):
    """How many launchers the static part spawners (the pair's STATIC_GROUP_FLAG) hand to their
    level's part engine: Jak 3 gives each level part-engine-max x 16 of them."""
    total = 0
    by_new = {}
    for name in defs.groups:
        by_new[f"group-{port.prefix}" + name[len("group-"):]] = name
    for _, actor in actors:
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


def write_level(port, level):
    """<level>-part.gc and the level's part spawners. Returns (actors, sprite_textures,
    part-engine-max, stats)."""
    cfg = level["particles"]
    name = level.name
    defs = Defs(cfg["files"])
    textures = Textures(port, cfg["textures_from"], cfg["page"])
    tr = Translator(port, cfg, defs, textures)
    actors = part_actors(port, level, cfg, tr)
    group_arrays = cfg.get("group_arrays", {})
    extra_groups = cfg.get("extra_groups", {})
    for source_name in group_arrays:
        for i in defs.data[source_name][2][5:]:
            tr.group(defs.group_ids[int(gl.parse_int(i))])
    for group in extra_groups:
        tr.group(group)
    # data arrays (the neon signs': bit masks and timings, no ids)
    data_text = [gl.pretty([Atom("define"), Atom(ours)] + defs.data[source_name][2:])
                 for source_name, ours in cfg.get("data", {}).items()]

    # parts in id order, their groups after them (the part ids must be set when a group launches)
    parts_text = [tr.part_text(pid) for pid in sorted(tr.part_map, key=lambda p: tr.part_map[p])]
    groups_text = [tr.group_text(n) for n in sorted(tr.group_map, key=lambda n: tr.group_map[n][1])]
    arrays = [group_array_text(defs, tr, src, ours) for src, ours in group_arrays.items()]
    arrays += [f"(define {ours} (new 'static 'boxed-array :type int32 {tr.group(group)[1]}))"
               for group, ours in extra_groups.items()]
    drop_text = [port.pair.drop_func_text(n, launched, tr.part_map)
                 for n, launched in sorted(tr.drop_funcs.values())]
    source_dir = f"goal_src/{port.source.NAME}"
    copied_text = [port.pair.copied_func_text(
        defs.funcs[n], tr.copied_funcs[n], tr.part_map,
        os.path.relpath(defs.func_files[n], source_dir).replace(os.sep, "/"))
        for n in sorted(tr.copied_funcs)]
    ported_text = []
    if "callbacks_file" in cfg:
        ported_text = [open(port.port_file(cfg["callbacks_file"]), encoding="utf-8").read()]
    for target_level, tpage, names in cfg.get("target_textures", []):
        textures.add_target(target_level, tpage, names)

    files = ", ".join(os.path.relpath(f, source_dir).replace(os.sep, "/") for f in cfg["files"])
    title = port.source.TITLE
    summary = (f"{title}'s particle effects of {', '.join(cfg.get('levels', level.sources))}: "
               f"{len(tr.part_map)} parts (ids {tr.part_range.start}-{tr.part_range.stop - 1}), "
               f"{len(tr.group_map)} groups (ids {tr.group_range.start}-"
               f"{tr.group_range.stop - 1}), {len(textures.page)} sprite texture(s) in its own "
               f"texture page, translated from {title}'s {files}.")
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
            f";; {name}'s texture page {cfg['page']}: the sprite textures of its particles (their "
            "pixels are in its",
            f";; fr3, see sprite_textures in {name}.jsonc), as names and sizes (w | h << 16)",
            f"(define {var}-names* (new 'static 'boxed-array :type string {names}))",
            "",
            f"(define {var}-sizes* (new 'static 'boxed-array :type uint32 {sizes}))",
            "",
            ";; made while the level loads, handed to the texture system when it is activated",
            f"({port.prefix}sprite-page-register '{name} ({port.prefix}sprite-page-new "
            f"{cfg['page']} {var}-names* {var}-sizes*))",
            "",
        ]
    lines += [section("callbacks"), ""]
    lines += [t + "\n" for t in ported_text + copied_text + drop_text]
    if data_text:
        lines += [section("data"), ""] + [t + "\n" for t in data_text]
    lines += [section("parts"), ""] + [t + "\n" for t in parts_text]
    lines += [section("groups"), ""] + [t + "\n" for t in groups_text]
    if arrays:
        lines += [f";; group ids used by {name}'s actors"] + arrays
    write_if_changed(f"{port.code_dir}/{name}-part.gc", "\n".join(lines).rstrip() + "\n")

    source_game = port.source.NAME
    sprite_textures = {"page": cfg["page"], "game": source_game,
                       "textures": [[t[0], t[1], t[2]] + ([t[5]] if t[5] != source_game else [])
                                    for t in textures.page]}
    launchers = static_launchers(port, defs, actors)
    return actors, sprite_textures, (launchers + 15) // 16, dict(
        parts=len(tr.part_map), groups=len(tr.group_map), textures=len(textures.page),
        actors=len(actors), static_launchers=launchers)
