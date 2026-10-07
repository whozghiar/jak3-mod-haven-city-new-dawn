"""Sound check: the sounds each level's content can play, the sound banks holding them, and the
source game's banks each level needs besides the ones its scripts and continues want.

A sound plays only while a loaded bank has it. The levels load the banks the source game's
continues and region scripts want (3 at once, steps/sound.py), and the target game's
always-loaded ones (its games/<target>.py ALWAYS_LOADED_BANKS). This check lists, per level:
  - the sounds its content can play: the scripts of its regions and actors (sound-play,
    sound-play-loop), its part spawners' ambient sounds (effect-name) and particle sounds (:sound
    of the parts their groups launch), and the code of its classes (sound-play, static-sound-spec,
    static-sound-name... in the forms of each placed class, the definitions they name in the
    level code, the mod's GAME code (the "sound" block's "game_code") and their parent classes'
    forms they don't override); a hub and its districts also run the hub's traffic (its "traffic"
    block's code and the classes of its art),
  - the banks holding each sound (the name tables of the .SBK files of both games' discs, the
    source game's renamed as the build copies them),
  - the banks it loads: the want-sound of each of its continues and scripts (a level without any
    takes those of the levels whose scripts load it), the hub's "extra_banks".
Its result, per level: the source game's banks holding the sounds its content plays that a want
set lacks, best first (the bank covering most of them first), which the mod's code loads with the
wanted banks while Jak is in the level and a bank slot is free (the "sound" block's
"level_banks_var": a GOAL list of (level bank...), in the level-info file).

`python scripts/level_port <manifest> --steps sound` prints the whole check of the generated
levels: per level, the sounds no wanted bank has (MISSING), the ones only some of its want sets
have (partial, often the source game's own choice: a door's bank wanted by the region at the
door), the ones in no bank of either game (NOBANK: silent in the source game too). Then the sounds the
source game's animations of the rebuilt models play (their art groups' effect-name tags, which
build-actor's models lack): played by their class's code, UNPLAYED, or NOBANK.
"""

import collections
import glob
import os
import re
import struct

from . import sound as sound_step

# the most banks a level loads at once, in half banks (a full bank takes two), and the most extra
# banks listed for a level
MAX_LEVEL_BANKS = 6


# sound banks #####################################################################################


def sbk_names(path):
    """The sound names of a .SBK file (its SFX name table, the one the sound player searches:
    game/sound/989snd/loader.cpp), an empty set for a bank without one."""
    with open(path, "rb") as f:
        d = f.read()
    o = d.find(b"SBlk")
    if o < 0 or len(d) < o + 0x80:
        return set()
    version = struct.unpack_from("<I", d, o + 4)[0]
    names = o + struct.unpack_from("<I", d, o + (56 if version >= 2 else 52))[0]
    table = names + struct.unpack_from("<I", d, names + 8)[0]
    out = set()
    for h in struct.unpack_from("<32h", d, names + 0x18):
        p = table + h * 0x14
        while p + 0x14 <= len(d) and d[p] != 0:
            out.add(d[p:p + 16].split(b"\0")[0].decode("latin1"))
            p += 0x14
    return out


def table_name(name):
    """A GOAL sound name as the banks' tables have it (the overlord's strcpy_toupper: upper case,
    '_' for '-', 16 characters)."""
    return name.upper().replace("-", "_")[:16]


# the effect-name values that aren't sounds (Jak 2's effect-control do-effect): particle groups,
# events, footsteps by surface, the camera shake, scripts
NOT_SOUND = re.compile(r"^(group-|event-|effect-)|^(camera-shake|script)$")


def art_group_effects(path):
    """{animation: (frames, [(frame, effect name)])}: the effect-name tags of the art-joint-anims of
    an art group (a decompiler raw object -ag.go, a v4 object file), each at its animation's frame
    (the tag's artist frame, less artist-base, over artist-step). The link data read as the
    decompiler does (decompiler/ObjectFile/LinkedObjectFileCreation.cpp, link_v2_or_v4)."""
    with open(path, "rb") as f:
        d = f.read()
    _, _, version, size = struct.unpack_from("<IIHxxI", d, 0)
    if version != 4:
        return {}
    co = 16
    p = co + size + 12  # past the data and the v2 link header (12 bytes)
    ptrs = set()  # data offsets of the pointers
    if d[p] == 0:
        p += 1
    else:
        cp, fixing = co, False
        while True:
            while True:
                c = d[p]
                p += 1
                if fixing:
                    ptrs.update(cp - co + 4 * i for i in range(c))
                cp += 4 * c
                if c != 0xff:
                    break
                if d[p] == 0:
                    p += 1
                    fixing = not fixing
            fixing = not fixing
            if d[p] == 0:
                break
        p += 1
    syms = {}  # data offset -> the symbol or type linked there
    while d[p] != 0:
        if d[p] & 0x80:  # a type: its method count first
            p += 1
        e = d.index(b"\0", p)
        name, p, cp = d[p:e].decode("latin1"), e + 1, co
        while True:
            seek, n = d[p], 1
            if seek & 3:
                seek, n = seek | d[p + 1] << 8, 2
                if seek & 2:
                    seek, n = seek | d[p + 2] << 16, 3
                    if seek & 1:
                        seek, n = seek | d[p + 3] << 24, 4
            p += n
            cp += seek & ~3
            syms[cp - co] = name
            if d[p] == 0:
                break
        p += 1
    data = d[co:]

    def u32(o):
        return struct.unpack_from("<I", data, o)[0]

    out = {}
    # an art-joint-anim (type word at o): name 8, extra (res-lump) 16, artist-base 24, artist-step
    # 28, frames 44; a res-lump: tag count 4, data-base 12, tags 28 (fields from the type word)
    for o, kind in syms.items():
        if kind != "art-joint-anim" or o + 16 not in ptrs or o + 8 not in ptrs:
            continue
        s, lump = u32(o + 8), u32(o + 16)
        anim = data[s + 4:s + 4 + u32(s)].split(b"\0")[0].decode("latin1")
        base, step = struct.unpack_from("<ff", data, o + 24)
        frames = struct.unpack_from("<H", data, u32(o + 44))[0] if o + 44 in ptrs else 0
        base_data, tags = u32(lump + 8), u32(lump + 24)
        fx = []
        for i in range(u32(lump)):
            t = tags + 16 * i
            if syms.get(t) == "effect-name":
                key = struct.unpack_from("<f", data, t + 4)[0]
                fx.append(((key - base) / step if step else key,
                           syms.get(base_data + (u32(t + 12) & 0xffff), "?")))
        if fx:
            out[anim] = (frames, fx)
    return out


class Banks:
    """The sound banks of both games' discs: target game's by their name, source game's by their
    new name (steps/sound.py renamed); which banks hold a sound."""

    def __init__(self, port):
        prefix = port["sound"]["prefix"]
        self.source = {}  # new name -> source name
        self.names = {}
        for path in glob.glob(f"{port.target.ISO}/SBK/*.SBK"):
            self.names[os.path.basename(path)[:-4].lower()] = sbk_names(path)
        for path in glob.glob(f"{port.source.ISO}/SBK/*.SBK"):
            src = os.path.basename(path)[:-4].lower()
            new = sound_step.renamed(prefix, src)
            self.source[new] = src
            self.names[new] = sbk_names(path)
        self.by_sound = collections.defaultdict(set)
        for bank, names in self.names.items():
            for n in names:
                self.by_sound[n].add(bank)
        # the target game's alternate banks of a language (commonj: Japanese)
        self.ignored = set(getattr(port.target, "LANGUAGE_BANKS", []))

    def of(self, sound):
        return self.by_sound.get(table_name(sound), set()) - self.ignored


# GOAL code #######################################################################################


def top_forms(text):
    """The top-level forms of a GOAL file, as text."""
    i, n, depth, start, out = 0, len(text), 0, None, []
    while i < n:
        c = text[i]
        if c == ";":
            i = text.find("\n", i)
            i = n if i < 0 else i
            continue
        if text.startswith("#|", i):
            i = text.find("|#", i) + 2
            continue
        if text.startswith("#\\", i):
            i += 3
            continue
        if c == '"':
            i += 1
            while i < n and text[i] != '"':
                i += 2 if text[i] == "\\" else 1
        elif c == "(":
            if depth == 0:
                start = i
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0 and start is not None:
                out.append(text[start:i + 1])
                start = None
        i += 1
    return out


SOUND = re.compile(r"\((?:sound-play|sound-play-loop|static-sound-spec|static-sound-name|"
                   r"string->sound-name|new '(?:process|static) 'ambient-sound)\s+\"([\w-]+)\"")
SYMBOL = re.compile(r"[^\s()'\"`,;]+")
STRING = re.compile(r'"(?:[^"\\]|\\.)*"')
COMMENT = re.compile(r";[^\n]*")
CALLS_PARENT = re.compile(r"call-parent-method|call-parent-state-handler|find-parent-method")


def sounds_in(text):
    return set(SOUND.findall(text))


class Def:
    """A top-level form: the name it defines (a type for its methods and states), its kind, the
    method or state it defines, its file and text."""

    def __init__(self, name, kind, member, path, text):
        self.name, self.kind, self.member, self.path, self.text = name, kind, member, path, text


class Code:
    """The definitions of GOAL files, by name: types (with their methods and states), functions,
    behaviors, globals and particle groups (with the sounds of the parts they launch)."""

    def __init__(self):
        self.defs = collections.defaultdict(list)
        self.parent = {}
        self.files = set()
        self.file_defs = collections.defaultdict(set)
        self.parts = {}  # (file, part id) -> sounds
        self.groups = {}  # group -> (file, part ids)

    def add(self, path):
        if path in self.files or not os.path.exists(path):
            return
        self.files.add(path)
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        for form in top_forms(text):
            head = re.match(r"\((\S+)\s+(\S+)", form)
            if not head:
                continue
            kind, name, member = head.group(1), head.group(2), None
            if kind == "deftype":
                parent = re.match(r"\(deftype\s+\S+\s+\(([^\s()]+)", form)
                if parent:
                    self.parent[name] = parent.group(1)
            elif kind == "defmethod":
                m = re.match(r"\(defmethod\s+(\S+)\s+\(\(\S+\s+([^)\s]+)\)", form)
                if not m:
                    continue
                member, name = m.groups()
            elif kind == "defstate":
                m = re.match(r"\(defstate\s+(\S+)\s+\((\S+)\)", form)
                if not m:
                    continue
                member, name = m.groups()
            elif kind == "defpart":
                if name.isdigit():
                    self.parts[(path, int(name))] = sounds_in(form)
                continue
            elif kind == "defpartgroup":
                self.groups[name] = (path, [int(x) for x in re.findall(r"\(sp-item\s+(\d+)", form)])
            elif kind not in ("defun", "defbehavior", "define", "define-perm"):
                continue
            self.defs[name].append(Def(name, kind, member, path, form))
            self.file_defs[path].add(name)

    def group_sounds(self, name):
        path, ids = self.groups.get(name, (None, []))
        return set().union(*[self.parts.get((path, i), set()) for i in ids])

    def closure(self, roots, follow):
        """The sounds the roots can play: sound -> the definitions playing it. A definition names
        others: followed when they're in the follow files (types, functions, behaviors, groups; a
        global's own sounds only). A type's parent classes are followed, but for the methods and
        states its descendants override (unless they call the parent's)."""
        out = collections.defaultdict(set)
        seen = set()
        stack = [(r, frozenset()) for r in roots]
        while stack:
            name, overridden = stack.pop()
            if name in seen:
                continue
            seen.add(name)
            members = set(overridden)
            for d in self.defs.get(name, []):
                if d.member in overridden:
                    continue
                body = COMMENT.sub("", STRING.sub('""', d.text))
                if d.member and not CALLS_PARENT.search(body):
                    members.add(d.member)
                for s in sounds_in(d.text) | (self.group_sounds(name) if d.kind == "defpartgroup"
                                              else set()):
                    out[s].add(name)
                if d.path not in follow or d.kind in ("define", "define-perm"):
                    continue
                # its parent is followed below, without the members it overrides
                for sym in set(SYMBOL.findall(body)) - {self.parent.get(name)}:
                    if sym not in seen and any(x.path in follow for x in self.defs.get(sym, [])):
                        stack.append((sym, frozenset()))
            parent = self.parent.get(name)
            if parent:
                stack.append((parent, frozenset(members)))
        return out

    def engine_only(self, name, engine_dir):
        return all(d.path.startswith(engine_dir) for d in self.defs.get(name, [])) and \
            name in self.defs


def gd_objects(path):
    """The code objects (.o, without it) of a DGO definition file."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [o[:-2] for o in re.findall(r'"([^"]+\.o)"', f.read())]


# levels ##########################################################################################


WANT_SOUND = re.compile(r"\(want-sound((?: (?:'[\w-]+|#f))+)\)")
SCRIPT_SOUND = re.compile(r'\(sound-play(?:-loop)? \\?"([\w-]+)\\?"')
EFFECT = re.compile(r'"effect-name": \["symbol", "([\w-]+)"\]')
ART = re.compile(r'"art-name": "([^"]+)"')
ETYPE = re.compile(r'"etype": "([^"]+)"')


def level_texts(level):
    """The generated .jsonc and region files of a level, as one text."""
    out = []
    for path in sorted(glob.glob(f"{level.folder}/{level.name}.jsonc") +
                       glob.glob(f"{level.folder}/*regions*.json")):
        with open(path, encoding="utf-8") as f:
            out.append(f.read())
    return "\n".join(out)


def script_sets(text):
    """The want-sound sets of a level's scripts."""
    return [("script", tuple(b.strip("'") for b in m.split() if b != "#f"))
            for m in WANT_SOUND.findall(text)]


class Check:
    """The sound check of a port's generated levels (their files written)."""

    def __init__(self, port):
        self.port = port
        cfg = port["sound"]
        self.banks = Banks(port)
        self.always = set(port.target.ALWAYS_LOADED_BANKS)
        self.state_banks = {b for b in self.banks.names
                            if any(b.startswith(p) for p in port.target.STATE_BANK_PREFIXES)}
        target = port.target.NAME
        self.engine_dir = f"goal_src/{target}/engine/"
        index = {}
        for path in glob.glob(f"goal_src/{target}/**/*.gc", recursive=True):
            index.setdefault(os.path.basename(path)[:-3], path.replace(os.sep, "/"))
        self.index = index
        self.code = Code()
        for obj in gd_objects(f"goal_src/{target}/dgos/game.gd"):
            if obj in index:
                self.code.add(index[obj])
        self.game_code = list(cfg.get("game_code", []))
        self.mod_files = set(self.game_code) | {p for p in index.values()
                                                if p.startswith(port.code_dir + "/")}
        self.texts = {lv.name: level_texts(lv) for lv in port.levels}
        self.dgo = {}
        for lv in port.levels:
            self.dgo[lv.name] = [index[o] for o in gd_objects(f"{lv.folder}/{lv.name}.gd")
                                 if o in index]
            for path in self.dgo[lv.name]:
                self.code.add(path)
        # the target game banks loaded with the source's while a hub is (its traffic's)
        self.hub_banks = list(dict.fromkeys(b for v in cfg.get("extra_banks", {}).values()
                                            for b in v))
        self.city = set(port.hubs) | set(port.hubs.values())

    def traffic_roots(self, hub):
        """The definitions of a hub's traffic code, and its traffic classes (its art's)."""
        traffic = self.port.level(hub).get("traffic", {})
        roots = {a[:-3] if a.endswith("-ag") else a for a in traffic.get("art", [])}
        for obj in traffic.get("code", []):
            path = self.index.get(obj[:-2] if obj.endswith(".o") else obj)
            if path:
                roots |= self.code.file_defs[path]
        return roots

    def needs(self, level):
        """(sound -> where it comes from: definitions, "script", "effect-name", particle groups),
        what the level's content can play, and the classes placed in it with their parents."""
        name = level.name
        text = self.texts[name]
        hub = self.port.hubs.get(name, name if name in self.port.hubs.values() else None)
        follow = set(self.dgo[name]) | set(self.game_code)
        roots = set(ETYPE.findall(text))
        if name != hub:
            for path in self.dgo[name]:
                roots |= self.code.file_defs[path]
        if hub:
            follow |= set(self.dgo[hub])
            roots |= self.traffic_roots(hub)
        placed = set(ETYPE.findall(text))
        chain = set()
        for t in placed:
            while t and t not in chain:
                chain.add(t)
                t = self.code.parent.get(t)
        out = collections.defaultdict(set)
        for s, defs in self.code.closure(roots, follow).items():
            # the target game's engine code alone (the player's states, enemy defaults): its sounds
            # are the target game's own, not the level's
            if all(self.code.engine_only(d, self.engine_dir) and d not in chain for d in defs):
                continue
            out[s] |= defs
        for s in SCRIPT_SOUND.findall(text):
            out[s].add("script")
        for s in EFFECT.findall(text):
            out[s].add("effect-name")
        for g in set(ART.findall(text)):
            for s in self.code.group_sounds(g):
                out[s].add(g)
        return out, chain

    def from_mod(self, sources, placed=()):
        """Do these sources include the port's own content (its scripts, part spawners, particle
        groups, the classes it places, or its code: the levels' code folder and its GAME code)?"""
        for s in sources:
            if s in ("script", "effect-name") or s in self.code.groups or s in placed:
                return True
            if any(d.path in self.mod_files for d in self.code.defs.get(s, [])):
                return True
        return False

    def run(self, continue_sets):
        """{level: report} for every level. continue_sets: {level: [(label, banks, levels)]}, the
        want-sound of its continues and the levels they load."""
        port = self.port
        sets = {lv.name: [(label, banks) for label, banks, _ in continue_sets.get(lv.name, [])] +
                script_sets(self.texts[lv.name]) for lv in port.levels}
        # with a hub: a city level, or a level a continue of which loads a hub
        hubs = set(port.hubs.values())
        with_hub = {lv.name for lv in port.levels if lv.name in self.city or any(
            set(levels) & hubs for _, _, levels in continue_sets.get(lv.name, []))}
        # a level without want sets (or continues) keeps the banks of the levels whose scripts
        # load it, and is loaded with a hub when they are
        for lv in port.levels:
            quoted = re.compile(rf"'{re.escape(lv.name)}\b")
            loaders = [o.name for o in port.levels
                       if o.name != lv.name and quoted.search(self.texts[o.name])]
            if not sets[lv.name]:
                sets[lv.name] = [x for o in loaders for x in sets[o]]
            if not continue_sets.get(lv.name) and set(loaders) & with_hub:
                with_hub.add(lv.name)
        self.used = {b for st in sets.values() for _, banks in st for b in banks}
        # a hub is loaded with one of its districts: theirs are its sets
        for hub in hubs:
            sets[hub] = [x for lv, h in port.hubs.items() if h == hub for x in sets[lv]]
        return {lv.name: self.level_report(lv, sets[lv.name], lv.name in with_hub)
                for lv in port.levels}

    def loaded(self, level, banks, level_banks, with_hub):
        """The banks loaded while Jak is in the level and its want-sound is banks: those, and the
        extra ones in the free half bank slots (each a half bank): the hub's first in a city level,
        the level's own first in a place loaded with a hub (hj2-update-extra-sound-bank)."""
        hub = self.hub_banks if with_hub else []
        order = hub + level_banks if level.name in self.city else level_banks + hub
        free = MAX_LEVEL_BANKS - len(banks) if banks else 0
        extra = [b for b in dict.fromkeys(order) if b not in banks][:max(free, 0)]
        return set(banks) | set(extra)

    def level_report(self, level, sets, with_hub):
        free = self.always | (set(self.hub_banks) if with_hub else set())
        wanted = set().union(*[set(s) for _, s in sets]) if sets else set()
        always_wanted = set.intersection(*[set(s) for _, s in sets]) if sets else set()
        rep = {"missing": {}, "partial": {}, "nobank": {}, "target": {}, "sets": sets,
               "before": collections.Counter()}
        uncovered = {}  # sound -> source banks that could play it (for the extra banks)
        content = {}  # sound -> (sources, banks)
        needs, placed = self.needs(level)
        for s, src in sorted(needs.items()):
            banks = self.banks.of(s)
            if banks & self.always or (banks and banks <= self.state_banks):
                continue
            engine = all(self.code.engine_only(d, self.engine_dir) for d in src)
            if not self.from_mod(src, placed) or (engine and not banks & set(self.banks.source)):
                # the target game's code the port links but doesn't place (the traffic's), or its
                # engine classes' own sounds (a crate's kinds): they play as in the target game
                rep["target"][s] = sorted(src)
                continue
            if not banks:
                rep["nobank"][s] = sorted(src)
                continue
            content[s] = (sorted(src), banks)
            if banks & free:
                continue
            absent = [label for label, st in sets if not banks & set(st)]
            if not banks & wanted:
                rep["before"]["missing"] += 1
            elif absent:
                rep["before"]["partial"] += 1
            source_banks = {b for b in banks if b in self.banks.source}
            if (absent or not sets) and source_banks and not source_banks & always_wanted:
                uncovered[s] = source_banks
        rep["level_banks"] = cover(uncovered, wanted, self.used)
        # with the extra banks, in each want set
        loaded = [self.loaded(level, st, rep["level_banks"], with_hub) for _, st in sets]
        for s, (src, banks) in content.items():
            absent = sum(1 for ld in loaded if not banks & (ld | self.always))
            if not sets or absent == len(sets):
                rep["missing"][s] = (src, sorted(banks))
            elif absent:
                rep["partial"][s] = (src, sorted(banks & set().union(*loaded)), absent, len(sets))
        return rep

    def anim_sounds(self):
        """[(class, sound, "animation@frame/frames", banks, played by the class's code?)]: the
        sounds the source game's animations of the port's rebuilt models play (their art groups'
        effect-name tags), which build-actor's models lack: the "models" and the levels'
        "custom_props". Empty without the decompiler's raw objects (the source game's RAW_OBJ)."""
        raw = getattr(self.port.source, "RAW_OBJ", None)
        if not raw or not os.path.isdir(raw):
            return []
        models = list(self.port.get("models", {}).items())
        for lv in self.port.levels:
            models += [(v["etype"], v) for v in lv.get("custom_props", {}).get("etypes", {}).values()]
        out, seen = [], set()
        for cls, spec in models:
            played = self.code.closure({cls}, self.mod_files)
            for rip in [spec["rip"]] + [e["rip"] for e in spec.get("extras", [])]:
                # the rip's art group: <model>-ag.go, or a shorter name's (an extra's parent)
                name = os.path.basename(rip).replace("-lod0.glb", "")
                while "-" in name and not os.path.exists(f"{raw}/{name}-ag.go"):
                    name = name.rsplit("-", 1)[0]
                ag = f"{raw}/{name}-ag.go"
                if (cls, ag) in seen or not os.path.exists(ag):
                    continue
                seen.add((cls, ag))
                for anim, (frames, fx) in art_group_effects(ag).items():
                    for frame, s in fx:
                        if not NOT_SOUND.search(s):
                            out.append((cls, s, f"{anim}@{frame:g}/{frames}",
                                        sorted(self.banks.of(s)), s in played))
        return out


def cover(uncovered, wanted, used=()):
    """The banks holding the uncovered sounds, best first: each the one holding most sounds the
    ones before it don't (on a tie: a bank the level wants in some places, then one another level
    wants, then the first by name)."""
    left = dict(uncovered)
    out = []
    while left and len(out) < MAX_LEVEL_BANKS:
        count = collections.Counter(b for banks in left.values() for b in banks)
        best = min(count, key=lambda b: (-count[b], b not in wanted, b not in used, b))
        out.append(best)
        left = {s: banks for s, banks in left.items() if best not in banks}
    return out


def continue_sets_written(port):
    """{level: [(label, banks, levels)]}: the want-sound of the continues of the level-info file,
    and the levels they load."""
    with open(port["level_info"]["file"], encoding="utf-8") as f:
        text = f.read()
    out = collections.defaultdict(list)
    for block in text.split("(new 'static 'continue-point")[1:]:
        name = re.search(r':name "([^"]+)"', block).group(1)
        level = re.search(r":level '(\S+)", block).group(1)
        banks = re.search(r":want-sound \(new 'static 'array symbol 3 ([^)]*)\)", block)
        out[level].append((f"continue {name}", tuple(
            b.strip("'") for b in (banks.group(1).split() if banks else []) if b != "#f"),
            re.findall(r"level-buffer-state-small :name '(\S+)", block)))
    return out


def level_banks(ctx, continue_sets):
    """The levels step's part: {level: its extra source banks}, registered for the build (each a
    bank the build copies), with a line per level that has some. continue_sets: as Check.run."""
    check = Check(ctx.port)
    reports = check.run(continue_sets)
    out = {}
    for name, rep in reports.items():
        if rep["level_banks"]:
            out[name] = [ctx.sound.bank(check.banks.source[b]) for b in rep["level_banks"]]
            print(f"  {name} sound: also loads {' '.join(out[name])} when a bank slot is free")
    return out


def level_banks_lines(ctx, banks):
    """GOAL text: the "level_banks_var" list of (level bank...)."""
    var = ctx.port["sound"].get("level_banks_var")
    if not var:
        return []
    return [f";; the {ctx.title} sound banks holding sounds of each level's content that some of "
            "its want sets lack,",
            ";; best first (scripts/level_port/steps/sound_check.py), loaded with the wanted "
            "banks while Jak is in it",
            f"(define {var} '(" + " ".join(f"({lv} {' '.join(b)})" for lv, b in banks.items())
            + "))", ""]


def print_report(reports):
    totals = collections.Counter()
    for name, rep in reports.items():
        for key in ("missing", "partial", "nobank", "target"):
            totals[key] += len(rep[key])
        for key in ("missing", "partial"):
            totals[key + " without extra banks"] += rep["before"][key]
        if not (rep["missing"] or rep["partial"] or rep["nobank"] or rep["before"]):
            continue
        print(f"  {name}: {len(rep['missing'])} missing, {len(rep['partial'])} partial "
              f"(without its extra banks: {rep['before']['missing']} missing, "
              f"{rep['before']['partial']} partial), {len(rep['nobank'])} in no bank; extra banks: "
              f"{' '.join(rep['level_banks']) or '-'}")
        if rep["target"]:
            print(f"    {len(rep['target'])} of target game code it links but doesn't place (as in "
                  f"the target game): {' '.join(sorted(rep['target']))}")
        for s, (src, banks) in rep["missing"].items():
            print(f"    MISSING {s:20} in {','.join(banks):32} ({','.join(src[:3])})")
        for s, (src, banks, n, total) in rep["partial"].items():
            print(f"    partial {s:20} in {','.join(banks):32} not in {n}/{total} sets "
                  f"({','.join(src[:3])})")
        for s, src in rep["nobank"].items():
            print(f"    NOBANK  {s:20} ({','.join(src[:3])})")
    print(f"  total: {dict(totals)}")


def print_anim_sounds(rows):
    if not rows:
        return
    print("  animation sounds of the rebuilt models (the source art groups' effect-name tags: "
          "build-actor's models have none, their class must play them):")
    for cls, s, where, banks, played in rows:
        state = "played" if played else ("NOBANK" if not banks else "UNPLAYED")
        print(f"    {state:8} {s:20} {where:40} in {','.join(banks) or '-':24} ({cls})")


def run(port):
    """The "sound" step: the check of the generated levels, printed (writes nothing)."""
    check = Check(port)
    print_report(check.run(continue_sets_written(port)))
    print_anim_sounds(check.anim_sounds())


if __name__ == "__main__":
    # self-check (from scripts/: python -m level_port.steps.sound_check): the form reader, a child
    # overriding its parent's sounds, the greedy cover
    import tempfile
    src = '''(deftype a (process) ())
(defmethod init-sound! ((this a)) "doc (call-parent-method)" (sound-play "a-snd"))
(defmethod go! ((this a)) (sound-play "a-go"))
(deftype b (a) ())
(defmethod init-sound! ((this b)) (static-sound-spec "b-snd" :group 0))
(defun helper () (sound-play "helper-snd"))
(defstate idle (b) :code (behavior () (helper)))
'''
    with tempfile.NamedTemporaryFile("w", suffix=".gc", delete=False) as f:
        f.write(src)
    code = Code()
    code.add(f.name)
    os.unlink(f.name)
    got = code.closure({"b"}, {f.name})
    assert set(got) == {"b-snd", "a-go", "helper-snd"}, got
    assert table_name("guard-shot-fire") == "GUARD_SHOT_FIRE"
    assert cover({"x": {"k1", "k2"}, "y": {"k2"}, "z": {"k3"}}, set()) == ["k2", "k3"]
    # an art group's animation sounds (with Jak 2 decompiled: the palace cable's falling plat)
    ag = "../decompiler_out/jak2/raw_obj/pal-falling-plat-ag.go"
    if os.path.exists(ag):
        fx = {a: [(round(f, 1), s) for f, s in x] for a, (_, x) in art_group_effects(ag).items()}
        assert fx == {"pal-falling-plat-idle": [(0.2, "pal-falling-b"), (26.1, "pal-falling-c")],
                      "pal-falling-plat-shake": [(0.2, "pal-falling-a")]}, fx
    print("ok")
