#!/usr/bin/env python3
"""Jak 2's particle effects of the city for havenj2: signs and posters, neon signs, street lights
and glows, chimney smoke, steam, fountains, drips, fires, the Baron's propaganda holograms...

Jak 2 draws a lot of its city with particles: every sign and poster is a 3D sprite, every lamp a
glow, launched by part-spawner actors (the <level>-part etypes) placed in the level. Jak 3 has the
same particle system, so Jak 2's definitions are kept and translated:
  - part and group ids are moved to ids Jak 3's code doesn't use while havenj2 is loaded (Jak 3's
    GAME ids, and the ones of the Jak 3 level code havenj2 includes, are avoided),
  - group names get a hj2- prefix, the group and item flags Jak 3's bit names,
  - textures: Jak 2's common effects are Jak 3's own (level-default-sprite) when Jak 3 has them;
    every other one (the sprite pages of Jak 2's city levels) goes in a texture page of havenj2's
    own (sprite_textures in havenj2.jsonc: the builder copies them from Jak 2's .fr3 files, the
    level code makes the texture-page at runtime, see hj2-sprite-page-new),
  - the callbacks (:func, :birth-func) are Jak 3's when Jak 3 has them, else ported here,
  - sounds are dropped (they are Jak 2's).
The part spawners become Jak 3 part-spawner actors, and the three animated neon signs (the Baron,
Praxis, the Hip Hog marquee) the hj2- types of havenj2-signs.gc.

Writes goal_src/jak3/levels/havenj2/havenj2-part.gc (level code, HJ2) and returns the actors and
the sprite texture list to gen_havenj2_links.py, which writes havenj2.jsonc.
"""

import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import goal_lisp as gl  # noqa: E402
from goal_lisp import Atom, Str, QUOTE  # noqa: E402
import jak2_actors  # noqa: E402
from gen_util import write_if_changed  # noqa: E402

FR3_CHECK = os.path.abspath("out/build/Release/bin/fr3_check.exe")
OUT_GC = "goal_src/jak3/levels/havenj2/havenj2-part.gc"

# Jak 2's particle definitions of the city
JAK2_PART_FILES = [
    "goal_src/jak2/levels/city/ctywide-part.gc",
    "goal_src/jak2/levels/city/slums/ctysluma-part.gc",
    "goal_src/jak2/levels/city/slums/ctyslumb-part.gc",
    "goal_src/jak2/levels/city/slums/ctyslumc-part.gc",
    "goal_src/jak2/levels/city/slums/neon-baron-part.gc",
    "goal_src/jak2/levels/city/port/ctyport-part.gc",
    "goal_src/jak2/levels/city/market/ctymarka-part.gc",
    "goal_src/jak2/levels/city/market/ctymarkb-part.gc",
    "goal_src/jak2/levels/city/industrial/ctyinda-part.gc",
    "goal_src/jak2/levels/city/industrial/ctyindb-part.gc",
    "goal_src/jak2/levels/city/generic/ctygena-part.gc",
    "goal_src/jak2/levels/city/generic/ctygenb-part.gc",
    "goal_src/jak2/levels/city/generic/ctygenc-part.gc",
    "goal_src/jak2/levels/city/generic/neon-praxis-part.gc",
    "goal_src/jak2/levels/city/farm/ctyfarma-part.gc",
    "goal_src/jak2/levels/city/farm/ctyfarmb-part.gc",
    "goal_src/jak2/levels/city/palace/ctypal-part.gc",
    "goal_src/jak2/levels/stadium/stadium-part.gc",
]
# Jak 2 .fr3 files the sprite textures are taken from (each level's own sprite page is in its fr3,
# Jak 2's common effects in GAME)
TEXTURE_FR3 = [
    "GAME", "ctywide", "ctysluma", "ctyslumb", "ctyslumc", "ctyport", "ctymarka", "ctymarkb",
    "ctyinda", "ctyindb", "ctygena", "ctygenb", "ctygenc", "ctyfarma", "ctyfarmb", "ctypal",
    "stadium",
]

# Jak 3 textures added at the end of havenj2's page, by Jak 3 .fr3 file and tpage: the sprite
# pieces of Jak 3's market and farm props (breaking crates, pots, crops, the fruit stands' fruit),
# which Jak 3 takes from its own city levels' sprite pages (hj2-prop-textures-on in
# jak2-haven-city-world.gc finds them by name), and the health bar of the vehicle Jak drives
# (vehicle-hud.gc finds it by name: Jak 3's city takes it from the levels it borrows)
JAK3_PROP_TEXTURES = [
    ("waswide", "waswide-sprite", ["wood-plain-debris", "clay-pot-debris-01", "rope-mesh-debris-01",
                                   "basket-debris-01", "straw-bit", "straw-ground",
                                   "cotton-wrap-debris", "cherry", "fruit1"]),
    ("ctyfarma", "ctyfarma-sprite", ["ctyfarm-cab-body", "ctyfarm-chili-leaf", "ctyfarm-chili-stem",
                                     "ctyfarm-eggplant-body", "ctyfarm-eggplant-leaf-1",
                                     "ctyfarm-eggplant-leaf-2"]),
    ("wasall", "wasall-minimap", ["hud-small-vehicle-health-bar-01"]),
]

# havenj2's texture page: a texture-page-dir entry Jak 3 never uses, under 2048 so that its texture
# ids stay positive in the int32 and binteger arrays of the particle data (hj2-sprite-page-new)
SPRITE_PAGE = 1566
# ids the definitions are moved to. Taken: Jak 3's GAME (parts up to 899, groups up to 221), and
# the Jak 3 level code in havenj2 (ctymark-obs: parts 1117-1162, groups 248-253; ctyfarm-obs: parts
# 4001-4047, groups 1134-1145; the traffic's vehicle-part: parts 916-952, groups 224-225, and
# cty-guard-projectile: parts 1163-1164, group 254). The rest is free while havenj2 is loaded: no
# Jak 3 level can be.
PART_IDS = range(1200, 4000)
GROUP_IDS = range(300, 1100)

# Jak 2 -> Jak 3 flag names (same bits)
GROUP_FLAGS = {"use-local-clock": "sp0", "always-draw": "sp1", "screen-space": "sp2",
               "unk-3": "sp3", "unk-4": "sp4", "unk-5": "sp5", "unk-6": "sp6", "unk-7": "sp7",
               "unk-8": "sp8"}
ITEM_FLAGS = {"is-3d": "is-3d", "bit1": "sp1", "start-dead": "sp2", "launch-asap": "sp3",
              "bit6": "sp6", "bit7": "sp7", "bit8": "sp8"}
# Particle (cpuinfo) flags: Jak 3 keeps Jak 2's names (sparticle-h.gc) but moved some meanings to
# other bits (its particles' level index takes bits 9 to 12, one more than Jak 2's). By what the
# launcher code (sparticle-launcher.gc) does with them, Jak 2 name -> Jak 3 name:
#   12 (sp-cpuinfo-flag-12): the time of day tints the color when the particle is relaunched
#   16 (use-global-acc): the acceleration stays in world space (gravity falls down whatever the
#      launcher's orientation: a fountain's drops)
#   20 (set-conerot): the cone angle follows the launcher's yaw
#   21 (sp-cpuinfo-flag-21): the launch and cone angles scale with the launcher's matrix
# The others mean the same (the rain's flag 14, glow, distort, left-multiply-quat...).
CPUINFO_FLAGS = {"sp-cpuinfo-flag-12": "sp-cpuinfo-flag-13", "use-global-acc": "launch-along-z",
                 "set-conerot": "right-multiply-quat", "sp-cpuinfo-flag-21": "set-conerot"}
# Jak 3 texture pages (goal_src/jak3/engine/data/tpages.gc): Jak 2's effects and common textures
# are taken from Jak 3's pages of the same names when it has them
JAK3_TPAGES = {"level-default-sprite": 4, "common": 1}
# callbacks Jak 3 has (GAME, or ctyfarm-obs which havenj2 includes)
JAK3_FUNCS = {"sparticle-mode-animate", "sparticle-texture-day-night", "birth-func-texture-group",
              "sparticle-texture-animate", "check-drop-level-rain2", "sparticle-motion-blur",
              "birth-func-ctyfarma-drip", "birth-func-ctyfarmb-drip"}
# ported here
PORTED_FUNCS = {
    "birth-func-ctywide-baron-propoganda-ticker-rotate": "hj2-birth-func-baron-ticker-rotate",
    "birth-func-race-poster": "hj2-birth-func-race-poster",
}
# data arrays of the animated neon signs, renamed
DATA = {"*baron-neon-skull*": "*hj2-baron-neon-skull*", "*praxis*": "*hj2-praxis*",
        "*praxis-backing*": "*hj2-praxis-backing*",
        "*hiphog-exterior-marquee*": "*hj2-hiphog-exterior-marquee*"}
# group id arrays of the animated neon signs and of the other actors using particles
GROUP_ARRAYS = {
    "*city-baron-group-ids*": "*hj2-baron-group-ids*",
    "*city-neon-praxis-group-ids*": "*hj2-neon-praxis-group-ids*",
    "*hiphog-exterior-marquee-group-ids*": "*hj2-hiphog-marquee-group-ids*",
}
EXTRA_GROUPS = {
    # the Baron's hologram over his propaganda speakers (hj2-propa)
    "group-ctywide-baron-propoganda-holo": "*hj2-propa-holo-group-ids*",
    # the mission kiosks' hologram (burning-bush, shown off)
    "group-ctywide-burning-bush-holo-off": "*hj2-burning-bush-holo-group-ids*",
}
# actors with their own particle code (havenj2-signs.gc)
SIGN_ACTORS = {"neon-baron": "hj2-neon-baron", "city-neon-praxis": "hj2-neon-praxis",
               "hiphog-exterior-marquee": "hj2-hiphog-marquee"}
# actor ids, past the props' (gen_havenj2_props.py)
BASE_AID = 45000


# Jak 2 / Jak 3 texture tables ####################################################################


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


def fr3_texture_index():
    """{(tpage, name): (fr3 level, w, h)} for the Jak 2 textures in TEXTURE_FR3."""
    out = {}
    for level in TEXTURE_FR3:
        text = subprocess.run([FR3_CHECK, f"out/jak2/fr3/{level}.fr3", "--textures", "/"],
                              capture_output=True, text=True, check=True).stdout
        for m in re.finditer(r"^(\S+)/(\S+)\s+(\d+)x(\d+)\s", text, re.M):
            key = (m.group(1), m.group(2))
            if key not in out:
                out[key] = (level, int(m.group(3)), int(m.group(4)))
    return out


class Textures:
    def __init__(self):
        self.j2_pages = load_tpages("jak2")
        self.j2_page_names = {v: k for k, v in self.j2_pages.items()}
        self.j2_tex = load_textures("jak2")
        self.j2_by_id = {(self.j2_pages[tp], idx): (tp, nm) for (tp, nm), idx in self.j2_tex.items()
                         if tp in self.j2_pages}
        self.j3_tex = load_textures("jak3")
        self.fr3 = fr3_texture_index()
        self.page = []  # (fr3 level, tpage, name, w, h, game)
        self.page_index = {}

    def in_page(self, tpage, name):
        """Index of a Jak 2 texture in havenj2's page (added on first use)."""
        key = (tpage, name)
        if key not in self.page_index:
            if key not in self.fr3:
                raise KeyError(f"no Jak 2 fr3 has the texture {tpage}/{name}")
            level, w, h = self.fr3[key]
            self.page_index[key] = len(self.page)
            self.page.append((level, tpage, name, w, h, "jak2"))
        return self.page_index[key]

    def add_jak3(self, level, tpage, names):
        """Jak 3 textures of a Jak 3 .fr3, at the end of the page."""
        text = subprocess.run([FR3_CHECK, f"out/jak3/fr3/{level}.fr3", "--textures", tpage + "/"],
                              capture_output=True, text=True, check=True).stdout
        sizes = {m.group(1): (int(m.group(2)), int(m.group(3))) for m in re.finditer(
            r"^" + re.escape(tpage) + r"/(\S+)\s+(\d+)x(\d+)\s", text, re.M)}
        for name in names:
            if name not in sizes:
                raise KeyError(f"no texture {tpage}/{name} in Jak 3's {level}.fr3")
            w, h = sizes[name]
            self.page.append((level, tpage, name, w, h, "jak3"))

    def texture_form(self, name, tpage):
        """The :texture argument for Jak 3."""
        if tpage == "effects" and ("level-default-sprite", name) in self.j3_tex:
            return [Atom(name), Atom("level-default-sprite")]
        if tpage == "common" and ("common", name) in self.j3_tex:
            return [Atom(name), Atom("common")]
        idx = self.in_page(tpage, name)
        return [Atom("new"), [QUOTE, Atom("static")], [QUOTE, Atom("texture-id")],
                Atom(":index"), Atom(str(idx)), Atom(":page"), Atom(str(SPRITE_PAGE))]

    def remap_id(self, value):
        """A Jak 2 texture-id value -> ours, or None if it isn't one. The texture groups of the
        smoke and fires (birth-func-texture-group) name Jak 2's effects textures: Jak 3's of the
        same name (Jak 2's effects page id is Jak 3's font page)."""
        if not value or value & 0xff:
            return None
        value &= 0xffffffff
        key = (value >> 20, (value >> 8) & 0xfff)
        if key not in self.j2_by_id:
            return None
        tpage, name = self.j2_by_id[key]
        jak3_tpage = {"effects": "level-default-sprite", "common": "common"}.get(tpage)
        if jak3_tpage and (jak3_tpage, name) in self.j3_tex:
            return (JAK3_TPAGES[jak3_tpage] << 20) | (self.j3_tex[(jak3_tpage, name)] << 8)
        idx = self.in_page(tpage, name)
        return (SPRITE_PAGE << 20) | (idx << 8)


# Jak 2 definitions ###############################################################################


class Defs:
    def __init__(self):
        self.parts = {}    # id -> form
        self.groups = {}   # name -> form
        self.group_ids = {}  # id -> name
        self.funcs = {}    # name -> form
        self.data = {}     # define name -> form
        for path in JAK2_PART_FILES:
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
                elif head == "define":
                    self.data[str(form[1])] = form


def walk(form):
    yield form
    if isinstance(form, list):
        for f in form:
            yield from walk(f)


class Translator:
    def __init__(self, defs, textures):
        self.defs = defs
        self.tex = textures
        self.part_map = {}
        self.group_map = {}  # jak 2 group name -> (new name, new id)
        self.part_ids = iter([i for i in PART_IDS if not 1117 <= i <= 1162])
        self.group_ids = iter([i for i in GROUP_IDS if not 1134 <= i <= 1145])
        self.drop_funcs = {}  # jak 2 name -> (new name, launched parts [(id, 3d?)])
        self.missing = set()  # parts referred to but never defined

    # ids

    def part(self, pid):
        """Our id for a Jak 2 part, None for one Jak 2 never defines (a few next-launchers point
        to nothing: the particle system then stops there)."""
        if pid not in self.part_map:
            if pid not in self.defs.parts:
                self.missing.add(pid)
                return None
            self.part_map[pid] = next(self.part_ids)
            self.scan_part(pid)
        return self.part_map[pid]

    def group(self, name):
        if name not in self.group_map:
            self.group_map[name] = ("group-hj2-" + name[len("group-"):], next(self.group_ids))
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
        if name in JAK3_FUNCS:
            return name
        if name in PORTED_FUNCS:
            return PORTED_FUNCS[name]
        m = re.fullmatch(r"check-drop-level-([a-z0-9]+)-drop-userdata", name)
        if m:
            if name not in self.drop_funcs:
                launched = []
                for f in walk(self.defs.funcs[name]):
                    if gl.is_list(f, "launch-particles"):
                        three_d = any(a == Atom("*sp-particle-system-3d*") for a in f)
                        ref = next(a for a in f if gl.is_list(a, "->"))
                        launched.append((int(ref[2]), three_d))
                self.drop_funcs[name] = (f"hj2-check-drop-level-{m.group(1)}", launched)
                for pid, _ in launched:
                    self.part(pid)
            return self.drop_funcs[name][0]
        raise KeyError(f"particle callback {name} isn't ported")

    # translation

    def userdata(self, value):
        """(:userdata :data (new 'static 'boxed-array :type int32/object ...)) with Jak 2 texture ids
        and data names remapped."""
        if not gl.is_list(value, "new"):
            return value
        out = []
        for item in value:
            if gl.is_list(item) and item[:1] == [QUOTE] and str(item[1]) in DATA:
                out.append([QUOTE, Atom(DATA[str(item[1])])])
            elif gl.is_list(item, "the") and item[1] == Atom("binteger"):
                raw = gl.parse_int(item[2])
                new = self.tex.remap_id(raw * 8) if raw is not None else None
                out.append([Atom("the"), Atom("binteger"), Atom(str(new // 8))] if new else item)
            elif isinstance(item, Atom) and gl.parse_int(item) is not None and item not in ("int32",):
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
                continue  # Jak 2's sounds
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
                spec = [spec[0], [Atom(CPUINFO_FLAGS.get(str(f), str(f))) for f in spec[1]]]
            specs.append(spec)
        return specs

    def item_form(self, item):
        """An sp-item, None for one launching a part Jak 2 never defines."""
        launcher = self.part(int(item[1]))
        if launcher is None:
            return None
        out = [Atom("sp-item"), Atom(str(launcher))]
        args = item[2:]
        i = 0
        while i < len(args):
            key, value = str(args[i]), args[i + 1]
            if key == ":flags":
                value = [Atom(ITEM_FLAGS[str(f)]) for f in value]
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
            flags = " ".join(GROUP_FLAGS[str(f)] for f in args[":flags"])
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


# callbacks #######################################################################################


def drop_func_text(name, launched, part_map):
    """A splash for the drops falling to their userdata height (Jak 2's check-drop-level-*-drop-
    userdata, in Jak 3's form: the particle position is now a vector)."""
    lines = [
        f"(defun {name} ((arg0 sparticle-system) (arg1 sparticle-cpuinfo) (arg2 vector))",
        "  (when (< (-> arg2 y) (-> arg1 user-float))",
        "    (let ((s3-0 (new 'stack-no-clear 'vector)))",
        "      (sp-kill-particle arg0 arg1)",
        "      (set-vector! s3-0 (-> arg2 x) (-> arg1 user-float) (-> arg2 z) 1.0)",
    ]
    for pid, three_d in launched:
        system = ":system *sp-particle-system-3d* " if three_d else ""
        lines.append(f"      (launch-particles {system}(-> *part-id-table* {part_map[pid]}) s3-0)")
    lines += ["      )", "    )", "  (sparticle-motion-blur arg0 arg1 arg2)", "  (none)", "  )"]
    return "\n".join(lines)


PORTED_TEXT = """\
(defun hj2-birth-func-baron-ticker-rotate ((arg0 sparticle-system)
                                           (arg1 sparticle-cpuinfo)
                                           (arg2 sprite-vec-data-3d)
                                           (arg3 sparticle-launcher)
                                           (arg4 sparticle-launch-state)
                                           )
  "Jak 3's birth-func-ctywide-baron-propoganda-ticker-rotate (levels/city/ctywide-part.gc): the
tickers turning around the Baron's hologram."
  (local-vars (v1-6 float) (v1-7 float))
  (rlet ((vf0 :class vf)
         (vf1 :class vf)
         (vf2 :class vf)
         )
    (init-vf0-vector)
    (let ((s5-0 (-> arg4 sprite)))
      (let ((s4-0 (new 'stack-no-clear 'quaternion)))
        (let* ((v1-0 arg2)
               (f0-0 (-> v1-0 qx-qy-qz-sy x))
               (f1-0 (-> v1-0 qx-qy-qz-sy y))
               (f2-0 (-> v1-0 qx-qy-qz-sy z))
               )
          (set! (-> s4-0 x) f0-0)
          (set! (-> s4-0 y) f1-0)
          (set! (-> s4-0 z) f2-0)
          (set! (-> s4-0 w) (sqrtf (- (- (- 1.0 (square f2-0)) (square f1-0)) (square f0-0))))
          )
        (quaternion-rotate-y! s4-0 s4-0 (+ 8192.0 (-> s5-0 sprite flag-rot-sy z)))
        (let ((v1-5 arg2))
          (cond
            ((< (-> s4-0 w) 0.0)
             (.lvf vf1 (&-> v1-5 qx-qy-qz-sy quad))
             (.lvf vf2 (&-> s4-0 quad))
             (.sub.vf.xyz vf1 vf0 vf2)
             (.svf (&-> v1-5 qx-qy-qz-sy quad) vf1)
             (.mov v1-6 vf1)
             )
            (else
              (.lvf vf1 (&-> v1-5 qx-qy-qz-sy quad))
              (.lvf vf2 (&-> s4-0 quad))
              (.add.vf.xyz vf1 vf0 vf2)
              (.svf (&-> v1-5 qx-qy-qz-sy quad) vf1)
              (.mov v1-7 vf1)
              )
            )
          )
        )
      (set! (-> arg2 r-g-b-a w) (-> s5-0 sprite r-g-b-a w))
      )
    0
    (none)
    )
  )

(defun hj2-birth-func-race-poster ((arg0 sparticle-system)
                                   (arg1 sparticle-cpuinfo)
                                   (arg2 sprite-vec-data-3d)
                                   (arg3 sparticle-launcher)
                                   (arg4 sparticle-launch-state)
                                   )
  "Jak 2's birth-func-race-poster (levels/city/ctywide-part.gc): the stadium race posters. Jak 2
picks one of four textures from the race won last; here the first one, before any race. They fade
out far away (always drawn on PC unless ps2-parts)."
  (let ((s4-0 (the-as object (-> arg1 user-float))))
    (when (nonzero? (the-as float s4-0))
      (let ((s4-1 (-> (the-as (array int32) s4-0) 5)))
        (when (nonzero? s4-1)
          (let* ((f30-0 200.0)
                 (f28-0 (floor f30-0))
                 (f1-0 (* 0.00024414062 (vector-vector-distance (-> arg2 x-y-z-sx) (math-camera-pos))))
                 (f0-1 (/ f1-0 f28-0))
                 )
            (set! (-> arg2 r-g-b-a w) (if (>= f30-0 f1-0)
                                          (* 128.0 (- 1.0 f0-1))
                                          0.0
                                          )
                  )
            )
          (#when PC_PORT
            (unless (-> *pc-settings* ps2-parts?)
              (set! (-> arg2 r-g-b-a w) 128.0)
              )
            )
          (particle-adgif-callback (-> arg1 adgif) (the-as texture-id s4-1))
          )
        )
      )
    )
  (none)
  )
"""


# actors ##########################################################################################


def city_part_actors(city_levels, tr):
    """part-spawner and neon sign actors of the city: (comment, actor) list."""
    out = []
    for level in city_levels:
        for actor in jak2_actors.level_actors(level):
            etype = actor["etype"]
            lump = actor["lump"]
            name = lump["name"]
            trans = [round(x, 4) for x in actor["trans"][:3]]
            entity = {
                "trans": trans,
                "etype": None,
                "aid": BASE_AID + len(out),
                "game_task": 0,
                "quat": [round(x, 4) for x in actor["quat"]],
                "bsphere": trans + [round(actor["bsphere"][3], 4)],
                "lump": {"name": name},
            }
            if "vis-dist" in lump:
                entity["lump"]["vis-dist"] = ["float", float(lump["vis-dist"])]
            if etype.endswith("-part") and lump.get("art-name") in tr.defs.groups:
                new_name, _ = tr.group(lump["art-name"])
                entity["etype"] = "part-spawner"
                entity["lump"]["art-name"] = new_name
                out.append((f"Jak 2's {name} ({level}): {lump['art-name']}", entity))
            elif etype in SIGN_ACTORS:
                entity["etype"] = SIGN_ACTORS[etype]
                out.append((f"Jak 2's {name} ({level})", entity))
            elif etype == "burning-bush":
                # the mission kiosk's hologram (the kiosk itself is part of the background)
                new_name, _ = tr.group("group-ctywide-burning-bush-holo-off")
                entity["etype"] = "part-spawner"
                entity["lump"]["name"] = name + "-holo"
                entity["lump"]["art-name"] = new_name
                entity["lump"].setdefault("vis-dist", ["float", 819200.0])
                out.append((f"Jak 2's {name} ({level}): its hologram", entity))
    return out


# output ##########################################################################################


def group_array_text(defs, tr, jak2_name, ours):
    ids = [int(gl.parse_int(x)) for x in defs.data[jak2_name][2][5:]]
    new = " ".join(str(tr.group(defs.group_ids[i])[1]) for i in ids)
    return f"(define {ours} (new 'static 'boxed-array :type int32 {new}))"


def write(city_levels):
    defs = Defs()
    textures = Textures()
    tr = Translator(defs, textures)
    actors = city_part_actors(city_levels, tr)
    for jak2_name in GROUP_ARRAYS:
        for i in defs.data[jak2_name][2][5:]:
            tr.group(defs.group_ids[int(gl.parse_int(i))])
    for name in EXTRA_GROUPS:
        tr.group(name)
    # the data arrays of the neon signs: bit masks and timings, no ids
    data_text = []
    for jak2_name, ours in DATA.items():
        form = defs.data[jak2_name]
        data_text.append(gl.pretty([Atom("define"), Atom(ours)] + form[2:]))

    # parts in id order, their groups after them (the part ids must be set when a group launches)
    parts_text = [tr.part_text(pid) for pid in sorted(tr.part_map, key=lambda p: tr.part_map[p])]
    groups_text = [tr.group_text(name) for name in sorted(tr.group_map, key=lambda n: tr.group_map[n][1])]
    arrays = [group_array_text(defs, tr, j2, ours) for j2, ours in GROUP_ARRAYS.items()]
    arrays += [f"(define {ours} (new 'static 'boxed-array :type int32 {tr.group(name)[1]}))"
               for name, ours in EXTRA_GROUPS.items()]
    drop_text = [drop_func_text(n, launched, tr.part_map)
                 for n, launched in sorted(tr.drop_funcs.values())]
    for level, tpage, names_j3 in JAK3_PROP_TEXTURES:
        textures.add_jak3(level, tpage, names_j3)
    names = " ".join(f'"{t[2]}"' for t in textures.page)
    sizes = " ".join(f"#x{(t[4] << 16) | t[3]:x}" for t in textures.page)

    text = f""";;-*-Lisp-*-
(in-package goal)

;; name: havenj2-part.gc
;; name in dgo: havenj2-part
;; dgos: HJ2

;; og:jak2-haven-city GENERATED by custom_assets/jak3/levels/havenj2/gen_havenj2_particles.py, edit
;; the script. Jak 2's particle effects of the city (signs, neon signs, lights, smoke, steam,
;; fountains...), translated from Jak 2's <level>-part.gc files: {len(tr.part_map)} parts,
;; {len(tr.group_map)} groups, {len(textures.page)} textures in havenj2's own texture page.

;; havenj2's texture page {SPRITE_PAGE}: the sprite textures of Jak 2's city, then those of Jak 3's
;; market and farm props (their pixels are in havenj2's fr3, see sprite_textures in havenj2.jsonc),
;; as names and sizes (w | h << 16)
(define *havenj2-sprite-names* (new 'static 'boxed-array :type string {names}))

(define *havenj2-sprite-sizes* (new 'static 'boxed-array :type uint32 {sizes}))

;; made while the level loads, handed to the texture system when it is activated (GAME,
;; jak2-haven-city-world.gc)
(hj2-sprite-page-register 'havenj2 (hj2-sprite-page-new {SPRITE_PAGE} *havenj2-sprite-names* *havenj2-sprite-sizes*))

;; callbacks ///////////////////////////////////////////////////////////////////////////////////////

{PORTED_TEXT}
{chr(10).join(t + chr(10) for t in drop_text)}
;; the animated neon signs' data (havenj2-signs.gc) /////////////////////////////////////////////////

{chr(10).join(t + chr(10) for t in data_text)}
;; parts ///////////////////////////////////////////////////////////////////////////////////////////

{chr(10).join(t + chr(10) for t in parts_text)}
;; groups //////////////////////////////////////////////////////////////////////////////////////////

{chr(10).join(t + chr(10) for t in groups_text)}
;; group ids used by havenj2's actors
{chr(10).join(arrays)}
"""
    write_if_changed(OUT_GC, text)
    sprite_textures = {"page": SPRITE_PAGE, "game": "jak2",
                       "textures": [[t[0], t[1], t[2]] + ([t[5]] if t[5] != "jak2" else [])
                                    for t in textures.page]}
    return actors, sprite_textures, dict(parts=len(tr.part_map), groups=len(tr.group_map),
                                         textures=len(textures.page), actors=len(actors))


if __name__ == "__main__":
    import gen_havenj2_links as links
    actors, sprites, stats = write(links.CITY_LEVELS)
    print(stats)
