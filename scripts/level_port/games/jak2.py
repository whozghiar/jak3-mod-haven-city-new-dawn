"""Jak 2 as a source game: where its extracted data is, and how to read it.

  - decompiler_out/jak2/entities/<level>-actors.json, -cameras.json, -nav.json, -city.json: the
    decompiler's dumps of each level's bsp,
  - decompiler_out/jak2/levels/<level>/*.glb: its model rips (rip_levels in jak2_config.jsonc),
  - decompiler_out/jak2/raw_obj/<name>-ag.go: its art groups (their animations' sounds),
  - out/jak2/fr3/<level>.fr3: its background, collision and textures,
  - goal_src/jak2: its decompiled code (story, level-info, regions, particles...).
"""

import functools
import glob
import json
import os
import re

NAME = "jak2"
TITLE = "Jak 2"
METER = 4096.0

ISO = "iso_data/jak2"
ENTITIES = "decompiler_out/jak2/entities"
RIPS = "decompiler_out/jak2/levels"
RAW_OBJ = "decompiler_out/jak2/raw_obj"
FR3 = "out/jak2/fr3"
GAME_TASK = "goal_src/jak2/engine/game/task/game-task.gc"
LEVEL_INFO = "goal_src/jak2/engine/level/level-info.gc"
REGIONS = "goal_src/jak2/tools/db-fixtures/fixture-region.sql"

# the sun directions of Jak 2's moods (mood-tables.gc *mood-direction-table*): palettes 1-4 of the
# background's time of day
SUN_DIRECTIONS = [
    (0.906, 0.397, 0.143),
    (0.5, 0.814, 0.296),
    (-0.5, 0.814, 0.296),
    (-0.906, 0.397, 0.143),
]

# story ###########################################################################################
# Jak 2 births an actor when its kill-mask shares no bit with its level's task-mask
# (goal_src/jak2/engine/entity/entity.gc). A level's task-mask is its base-task-mask, changed by the
# closed story nodes of its task area (level-method-22, goal_src/jak2/engine/game/task/
# task-control.gc: abs-task-mask sets it, set-task-mask adds bits, clear-task-mask removes them),
# plus the bit `never`, always there.

# task-mask bits (goal_src/jak2/engine/level/level-h.gc)
TASK_MASK = {**{f"task{i}": 1 << i for i in range(8)}, "done": 1 << 8, "dummy0": 1 << 9,
             "dummy1": 1 << 10, "dummy2": 1 << 11, "special": 1 << 12, "primary0": 1 << 13,
             "ctywide": 1 << 14, "never": 1 << 15, "movie0": 1 << 16, "movie1": 1 << 17,
             "movie2": 1 << 18}
KILL_MASK_NEVER = TASK_MASK["never"]
# the bits the story sets (the rest comes from settings and the loaded levels, left as they are)
STORY_BITS = 0x1FF

# Jak 2 shows or hides some background prototypes (TIE, shrub) depending on the story, in
# level-method-22 (prototypes-game-visible-set!), which also disables their collision. By level:
# (prototypes, shown(closed)), its conditions as they are there, closed(node) telling whether a story
# node is closed (task-complete? of a task: its close-task node, <task>-resolution). Every prototype
# is shown by default: only the ones whose condition is false are hidden.
_R = "-resolution"
STORY_PROTOTYPES = {
    # the palace plaza: once Mar's tomb is found (canyon-insert-items-shard) the wall under the
    # Baron's statue is gone and its rubble lies there
    "ctypal": [(["ctyp-statue-wall-breakable.mb"], lambda c: not c("canyon-insert-items-shard")),
               (["ctyp-statue-rubble-a.mb", "ctyp-statue-rubble-b.mb",
                 "ctyp-statue-rubble-big-a.mb"], lambda c: c("canyon-insert-items-shard"))],
    # the market roof broken by the tanker
    "ctymarkb": [(["city-mark-roof-before-broken.mb"],
                  lambda c: not c("city-intercept-tanker-roof-explode")),
                 (["city-mark-roof-broken.mb"], lambda c: c("city-intercept-tanker-introduction"))],
    # the Hip Hog's paintings changed after the nest boss
    "hiphog": [(["hip-paintings-bar-a.mb", "hip-paintings-wall-reflection-a.mb",
                 "hip-paintings-wall-a.mb"], lambda c: not c("nest-boss" + _R)),
               (["hip-paintings-bar-b.mb", "hip-paintings-wall-reflection-b.mb",
                 "hip-paintings-wall-b.mb"], lambda c: c("nest-boss" + _R))],
    # Dead Town's tower fallen (ruins-tower): its standing pieces and the swinging bars on it
    "ruins": [(["ruins-board-task2.mb", "ruins-lgcollision-task2.mb", "ruins-plank-task2.mb",
                "ruins-smlcollision-task2.mb", "ruins-support-task2.mb"],
               lambda c: c("ruins-tower" + _R) and c("ruins-enemy-introduction")),
              (["ruin-tower-junk.mb"], lambda c: c("ruins-tower" + _R)),
              (["ruin-balcony-01-tower.mb", "ruin-balcony-02-tower.mb", "ruin-bar-01-tower.mb",
                "ruin-bar-02-tower.mb", "ruin-bar-03-tower.mb", "ruin-bridge-01-tower.mb",
                "ruin-lamp-post-01-tower.mb", "ruin-lamp-post-03-tower.mb",
                "ruin-lamp-post-04-tower.mb", "ruin-lampbase-02-tower.mb",
                "ruin-lamplite-01-tower.mb", "ruin-pillar-broken-01-tower.mb",
                "ruin-pillar-broken-03-tower.mb", "ruin-top-tower.mb", "ruin-tower-window-01.mb",
                "ruin-window-01-tower.mb", "ruins-city-corner-roof-tower.mb",
                "ruins-city-roof-01-tower.mb", "ruins-cracked-roof-tower.mb",
                "ruins-pipe-2m-end-tower.mb", "ruins-pipe-elbow-tower.mb",
                "ruins-pipe-mid-tower.mb", "ruins-pipe-ring-tower.mb", "ruins-support-01-tower.mb",
                "ruins-support-02-tower.mb", "swingpole-geo.mb", "ruin-top-brick-01.mb",
                "ruin-brick-side-01.mb"], lambda c: not c("ruins-tower" + _R))],
    # the pumping station: Sig's tank gone, and the castle seen in the distance, blown up
    "atoll": [(["atoll-tank.mb"], lambda c: not c("atoll-sig" + _R) and not c("atoll-sig-tank")),
              (["lowres-casboss.mb"], lambda c: not c("castle-boss" + _R))],
    # the castle pad after the castle boss: its tanks, crane, tower and scaffolding are gone
    "caspad": [(["cpad-bigtank-side.mb", "cpad-bigtank-top.mb", "cpad-bigtank-top-details.mb",
                 "cpad-crane.mb", "cpad-crane-base.mb", "cpad-elev-scaffolding.mb",
                 "cpad-elev-shaft-ex.mb", "cpad-elev-shaft-ex-detail.mb",
                 "cpad-elev-shaft-roof.mb", "cpad-liltank-side.mb", "cpad-liltank-top.mb",
                 "cpad-pipe-base.mb", "cpad-pipe-flat.mb", "cpad-pipe-lil-elbo.mb",
                 "cpad-pipe-lil-strt.mb", "cpad-pipe-med-elbo.mb", "cpad-pipe-med-strt.mb",
                 "cpad-pipe-tank-45.mb", "cpad-pipe-tank-strt.mb", "cpad-scaffold-structure.mb",
                 "cpad-scaff-x-beam.mb", "cpad-stonework.mb", "cpad-top.mb",
                 "cpad-tower-bottom.mb", "cpad-tower-centrifuse.mb", "cpad-tower-generator.mb",
                 "cpad-tower-generator-panels.mb", "cpad-tower-smokestack.mb",
                 "cpad-tower-supports-lower.mb", "cpad-tower-turbine.mb",
                 "cpad-tower-walkway-lower.mb", "cpad-x-beam.mb"],
                lambda c: not c("castle-boss" + _R))],
}


def _sewer_board_on(c):
    """The sewers' hover-board mission is on: its door shown, the connecting door hidden."""
    return (c("sewer-enemy" + _R) and c("sewer-board-introduction")
            and not c("sewer-board" + _R))


for _lev in ("sewer", "sewerb", "sewesc", "sewescb"):
    STORY_PROTOTYPES[_lev] = [(["sewer-c-connect-door.mb"], lambda c: not _sewer_board_on(c)),
                              (["sewer-hover-door.mb"], _sewer_board_on)]

# Actors whose own code hides them until a story node is closed, whatever their kill-mask: by class,
# that node. The palace plaza's broken statue (no-draw) and broken wall (left at the origin:
# process-drawable-from-entity! only runs then) wait for Mar's tomb (ctypal-obs.gc).
ACTOR_SHOWN_AFTER = {
    "ctypal-baron-statue-broken": "canyon-insert-items-resolution",
    "ctypal-broke-wall": "canyon-insert-items-resolution",
}

# And the actors whose own code kills them once a story node is closed: by class, that node. The
# Baron's intact statue on the palace plaza's wall (ctywide's baron-statue, ctywide-obs.gc), until
# Mar's tomb is found.
ACTOR_GONE_AFTER = {
    "baron-statue": "canyon-insert-items-resolution",
}


def mask_bits(text):
    """A (task-mask ...) value's bits."""
    return sum(TASK_MASK[name] for name in text.split())


@functools.lru_cache(maxsize=None)
def task_nodes():
    """Jak 2's story nodes, in order: (task area, name, flags, task-mask)."""
    src = open(GAME_TASK, encoding="utf-8").read()
    nodes = []
    for chunk in src.split("(new 'static 'game-task-node-info")[1:]:
        # the node's own fields come before its info (which has a :level of its own)
        head = re.split(r"\n\s*:(?:on-open|info) ", chunk, maxsplit=1)[0]
        level = re.search(r":level '([\w-]+)", head)
        name = re.search(r':name "([^"]+)"', head)
        flags = re.search(r":flags \(game-task-node-flag([^)]*)\)", head)
        mask = re.search(r":task-mask \(task-mask([^)]*)\)", head)
        nodes.append((level.group(1) if level else None, name.group(1) if name else None,
                      set(flags.group(1).split()) if flags else set(),
                      mask_bits(mask.group(1)) if mask else 0))
    return nodes


@functools.lru_cache(maxsize=None)
def level_tasks():
    """Jak 2 level -> (task area, base-task-mask)."""
    src = open(LEVEL_INFO, encoding="utf-8").read()
    out = {}
    for block in re.split(r"\n\(define ", src):
        if "level-load-info" not in block[:200]:
            continue
        name = re.search(r":name '([\w-]+)", block)
        area = re.search(r":taskname '([\w-]+)", block)
        base = re.search(r":base-task-mask \(task-mask([^)]*)\)", block)
        if name and area:
            out[name.group(1)] = (area.group(1), mask_bits(base.group(1)) if base else 0)
    return out


@functools.lru_cache(maxsize=None)
def _level_actor_dump(level):
    with open(os.path.join(ENTITIES, level + "-actors.json")) as f:
        return json.load(f) or []


class Story:
    """A state of Jak 2's story: the actors Jak 2 spawns then, the background it shows, and the
    answer of its scripts' story checks (task-closed?). Only the end of the game (every task
    done) is known here; open_tasks are story nodes taken as still open (Jak 2 closes the palace's
    doors once its sneak-in mission is over, for example), level_open_tasks more of them for one
    source level only ({level: [nodes]}: its actors, background prototypes and scripts; the palace
    plaza before Mar's tomb is found, for example)."""

    def __init__(self, state="end", open_tasks=(), level_open_tasks=None):
        if state != "end":
            raise ValueError(f"jak2: unknown story state {state!r} (known: end)")
        self.open_tasks = set(open_tasks)
        self.level_open_tasks = {lev: set(t) for lev, t in (level_open_tasks or {}).items()}
        self._masks = {}

    def _open(self, level):
        """The story nodes taken as open for a source level (None: the global ones only)."""
        return self.open_tasks | self.level_open_tasks.get(level, set())

    def closed(self, task, open_tasks=(), level=None):
        """Is this task done in this story state, for this source level (open_tasks: more tasks
        taken as open)?"""
        return task not in self._open(level) and task not in open_tasks

    def task_mask(self, level):
        """A level's task-mask bits set by the story."""
        if level not in self._masks:
            area, base = level_tasks().get(level, (None, 0))
            mask = base & STORY_BITS
            opened = self._open(level)
            for node_area, name, flags, bits in task_nodes()[1:]:
                if node_area != area or name in opened:
                    continue
                if "abs-task-mask" in flags:
                    mask = bits
                elif "set-task-mask" in flags:
                    mask |= bits
                elif "clear-task-mask" in flags:
                    mask &= ~bits
            self._masks[level] = mask & STORY_BITS
        return self._masks[level]

    def spawned(self, actor, level):
        """Is this actor born (and shown) in this story state?"""
        after = ACTOR_SHOWN_AFTER.get(actor["etype"])
        if after and not self.closed(after, level=level):
            return False
        gone = ACTOR_GONE_AFTER.get(actor["etype"])
        if gone and self.closed(gone, level=level):
            return False
        kill = int(actor["lump"].get("kill-mask", 0) or 0)
        return not kill & (KILL_MASK_NEVER | self.task_mask(level))

    def level_actors(self, level):
        """The actors of a level Jak 2 spawns in this story state (the decompiler's dump)."""
        return [a for a in _level_actor_dump(level) if self.spawned(a, level)]

    def all_actors(self):
        """{(level, name): actor} for every extracted level."""
        by_name = {}
        for path in glob.glob(f"{ENTITIES}/*-actors.json"):
            level = os.path.basename(path)[: -len("-actors.json")]
            for actor in self.level_actors(level):
                by_name[(level, actor["lump"].get("name"))] = actor
        return by_name

    def hidden_prototypes(self, levels):
        """The background prototypes of these levels Jak 2 hides in this story state."""
        out = []
        for lev in levels:
            for protos, shown in STORY_PROTOTYPES.get(lev, []):
                if not shown(lambda node, lev=lev: self.closed(node, level=lev)):
                    out += [p for p in protos if p not in out]
        return out


# levels ##########################################################################################


def level_names():
    """Every Jak 2 level name (a level-load-info's :name is alone on its line, unlike the level
    names in the continues' level lists)."""
    src = open(LEVEL_INFO, encoding="utf-8").read()
    return set(re.findall(r"^\s*:name '([a-z0-9-]+)\s*$", src, re.M))


@functools.cache
def _nicknames():
    src = open(LEVEL_INFO, encoding="utf-8").read()
    return dict(re.findall(r"^\s*:name '([a-z0-9-]+)\s*\n(?:.*\n){0,8}?\s*:nickname '([a-z0-9-]+)",
                           src, re.M))


def dgo_of(level):
    """The DGO holding a level: its nickname's (ctysluma: CTA.DGO)."""
    return _nicknames()[level].upper() + ".DGO"


def memory_modes():
    """Jak 2 level -> its load-buffer-mode."""
    src = open(LEVEL_INFO, encoding="utf-8").read()
    out = {}
    for block in re.split(r"\n\(define ", src):
        name = re.search(r":name '([\w-]+)", block)
        if not name or "level-load-info" not in block[:200]:
            continue
        mode = re.search(r":memory-mode \(load-buffer-mode ([\w-]+)\)", block)
        out[name.group(1)] = mode.group(1) if mode else "small-edge"
    return out


def cameras(level):
    """A level's fixed cameras (<level>-cameras.json, lumps typed for the level builder), [] if it
    has none."""
    path = f"{ENTITIES}/{level}-cameras.json"
    if not os.path.exists(path):
        return []
    return json.load(open(path))


def _parse_vector(block, key):
    m = re.search(r":" + key + r" \(new 'static 'vector([^)]*)\)", block)
    values = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 0.0}
    for k, v in re.findall(r":([xyzw]) (-?[0-9.e+-]+)", m.group(1)):
        values[k] = float(v)
    return [values["x"], values["y"], values["z"], values["w"]]


def continues():
    """Jak 2's continue points: name -> level, trans, quat, camera_trans, camera_rot (game units),
    flags, wants (the level list: (level, display?))."""
    src = open(LEVEL_INFO, encoding="utf-8").read()
    result = {}
    for block in re.split(r"\(new 'static 'continue-point", src)[1:]:
        head, _, rest = block.partition(":want")
        name = re.search(r':name "([^"]+)"', head).group(1)
        rot = re.findall(r"array float 3 (-?[0-9.]+) (-?[0-9.]+) (-?[0-9.]+)", head)
        flags = re.search(r":flags \(continue-flags([^)]*)\)", head)
        wants = re.findall(r"level-buffer-state :name '([a-z0-9-]+) :display\? ('?[a-z#]+)",
                           rest.split(":want-sound")[0])
        sounds = re.search(r":want-sound \(new 'static 'array symbol 3 ([^)]*)\)", rest)
        result[name] = dict(
            level=re.search(r":level '([a-z0-9-]+)", head).group(1),
            trans=_parse_vector(head, "trans"),
            quat=_parse_vector(head, "quat"),
            camera_trans=_parse_vector(head, "camera-trans"),
            camera_rot=[float(x) for row in rot[:3] for x in row],
            flags=set(flags.group(1).split()) if flags else set(),
            wants=wants,
            # its 3 sound banks (None: no bank)
            want_sound=[None if x == "#f" else x.lstrip("'") for x in sounds.group(1).split()]
            if sounds else [None] * 3,
        )
    return result


def music_banks():
    """Jak 2 level -> its music (level-load-info :music-bank), for the levels with one."""
    src = open(LEVEL_INFO, encoding="utf-8").read()
    out = {}
    for block in re.split(r"\n\(define ", src):
        name = re.search(r":name '([\w-]+)", block)
        music = re.search(r":music-bank '([\w-]+)", block)
        if name and music and "level-load-info" in block[:200]:
            out[name.group(1)] = music.group(1)
    return out


def regions():
    """Jak 2's regions (tools/db-fixtures/fixture-region.sql): id -> level, tree, faces (by id:
    kind, normal, points in meters) or sphere (meters), scripts (on-enter, on-exit, on-inside)."""
    src = open(REGIONS, encoding="utf-8").read()
    out = {}
    for m in re.finditer(
            r"INSERT INTO `region` \(`region_id`, `level_name`, `tree`, `on_enter`, `on_exit`, "
            r"`on_inside`\) values \((\d+), '([^']*)', '([^']*)', '((?:[^']|'')*)', "
            r"'((?:[^']|'')*)', '((?:[^']|'')*)'\);", src):
        rid, level, tree, on_enter, on_exit, on_inside = m.groups()
        out[int(rid)] = dict(
            id=int(rid), level=level, tree=tree, faces={}, sphere=None,
            scripts={k: v.replace("''", "'") for k, v in (
                ("on-enter", on_enter), ("on-exit", on_exit), ("on-inside", on_inside)) if v})
    face_owner = {}
    num = r"(-?[\d.e+-]+)"
    for m in re.finditer(
            r"INSERT INTO `region_face` \([^)]*\) values \((\d+), (\d+), '([^']*)', '([^']*)', "
            + ", ".join([num] * 8) + r"\);", src):
        fid, rid = int(m.group(1)), int(m.group(2))
        out[rid]["faces"][fid] = dict(kind=m.group(3),
                                      normal=[float(m.group(i)) for i in range(5, 9)],
                                      points=[])
        face_owner[fid] = rid
    for m in re.finditer(
            r"INSERT INTO `region_point` \(`region_face_id`, `idx`, `x`, `y`, `z`, `w`\) values "
            r"\((\d+), (\d+), " + ", ".join([num] * 4) + r"\);", src):
        fid = int(m.group(1))
        out[face_owner[fid]]["faces"][fid]["points"].append(
            (int(m.group(2)), [float(m.group(i)) / METER for i in range(3, 6)]))
    for m in re.finditer(
            r"INSERT INTO `region_sphere` \(`region_id`, `x`, `y`, `z`, `r`\) values \((\d+), "
            + ", ".join([num] * 4) + r"\);", src):
        out[int(m.group(1))]["sphere"] = [float(m.group(i)) / METER for i in range(2, 6)]
    for r in out.values():
        for f in r["faces"].values():
            f["points"] = [p for _, p in sorted(f["points"])]
    return out
