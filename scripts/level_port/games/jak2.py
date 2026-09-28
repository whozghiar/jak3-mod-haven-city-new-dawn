"""Jak 2 as a source game: where its extracted data is, and how to read it.

  - decompiler_out/jak2/entities/<level>-actors.json, -cameras.json, -nav.json, -city.json: the
    decompiler's dumps of each level's bsp,
  - decompiler_out/jak2/levels/<level>/*.glb: its model rips (rip_levels in jak2_config.jsonc),
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

ENTITIES = "decompiler_out/jak2/entities"
RIPS = "decompiler_out/jak2/levels"
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
# level-method-22 (prototypes-game-visible-set!), which also disables their collision. By level, the
# prototypes hidden at the end of the game, every task done. The ones shown then (the construction
# site's broken scaffolding, the statue's rubble...) need nothing: every prototype is shown by
# default.
END_HIDDEN_PROTOTYPES = {
    # the palace plaza once Mar's tomb is found (canyon-insert-items-shard): the wall under the
    # Baron's statue is gone, the statue lies in rubble
    "ctypal": ["ctyp-statue-wall-breakable.mb"],
    # the market roof broken by the tanker (city-intercept-tanker-roof-explode)
    "ctymarkb": ["city-mark-roof-before-broken.mb"],
    # the Hip Hog's paintings changed after the nest boss (nest-boss-resolution)
    "hiphog": ["hip-paintings-bar-a.mb", "hip-paintings-wall-reflection-a.mb",
               "hip-paintings-wall-a.mb"],
    # Dead Town's tower fallen (ruins-tower): its standing pieces and the swinging bars on it
    "ruins": ["ruin-balcony-01-tower.mb", "ruin-balcony-02-tower.mb", "ruin-bar-01-tower.mb",
              "ruin-bar-02-tower.mb", "ruin-bar-03-tower.mb", "ruin-bridge-01-tower.mb",
              "ruin-lamp-post-01-tower.mb", "ruin-lamp-post-03-tower.mb",
              "ruin-lamp-post-04-tower.mb", "ruin-lampbase-02-tower.mb",
              "ruin-lamplite-01-tower.mb", "ruin-pillar-broken-01-tower.mb",
              "ruin-pillar-broken-03-tower.mb", "ruin-top-tower.mb", "ruin-tower-window-01.mb",
              "ruin-window-01-tower.mb", "ruins-city-corner-roof-tower.mb",
              "ruins-city-roof-01-tower.mb", "ruins-cracked-roof-tower.mb",
              "ruins-pipe-2m-end-tower.mb", "ruins-pipe-elbow-tower.mb", "ruins-pipe-mid-tower.mb",
              "ruins-pipe-ring-tower.mb", "ruins-support-01-tower.mb", "ruins-support-02-tower.mb",
              "swingpole-geo.mb", "ruin-top-brick-01.mb", "ruin-brick-side-01.mb"],
    # the pumping station: Sig's tank gone (atoll-sig), and the castle seen in the distance, blown
    # up (castle-boss-resolution)
    "atoll": ["atoll-tank.mb", "lowres-casboss.mb"],
    # the castle pad after the castle boss: its tanks, crane, tower and scaffolding are gone
    "caspad": ["cpad-bigtank-side.mb", "cpad-bigtank-top.mb", "cpad-bigtank-top-details.mb",
               "cpad-crane.mb", "cpad-crane-base.mb", "cpad-elev-scaffolding.mb",
               "cpad-elev-shaft-ex.mb", "cpad-elev-shaft-ex-detail.mb", "cpad-elev-shaft-roof.mb",
               "cpad-liltank-side.mb", "cpad-liltank-top.mb", "cpad-pipe-base.mb",
               "cpad-pipe-flat.mb", "cpad-pipe-lil-elbo.mb", "cpad-pipe-lil-strt.mb",
               "cpad-pipe-med-elbo.mb", "cpad-pipe-med-strt.mb", "cpad-pipe-tank-45.mb",
               "cpad-pipe-tank-strt.mb", "cpad-scaffold-structure.mb", "cpad-scaff-x-beam.mb",
               "cpad-stonework.mb", "cpad-top.mb", "cpad-tower-bottom.mb",
               "cpad-tower-centrifuse.mb", "cpad-tower-generator.mb",
               "cpad-tower-generator-panels.mb", "cpad-tower-smokestack.mb",
               "cpad-tower-supports-lower.mb", "cpad-tower-turbine.mb",
               "cpad-tower-walkway-lower.mb", "cpad-x-beam.mb"],
    # the sewers: the door of the hover-board mission (sewer-board) is gone
    "sewer": ["sewer-hover-door.mb"],
    "sewerb": ["sewer-hover-door.mb"],
    "sewesc": ["sewer-hover-door.mb"],
    "sewescb": ["sewer-hover-door.mb"],
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
    doors once its sneak-in mission is over, for example)."""

    def __init__(self, state="end", open_tasks=()):
        if state != "end":
            raise ValueError(f"jak2: unknown story state {state!r} (known: end)")
        self.open_tasks = set(open_tasks)
        self._masks = {}

    def closed(self, task, open_tasks=()):
        """Is this task done in this story state (open_tasks: more tasks taken as open)?"""
        return task not in self.open_tasks and task not in open_tasks

    def task_mask(self, level):
        """A level's task-mask bits set by the story."""
        if level not in self._masks:
            area, base = level_tasks().get(level, (None, 0))
            mask = base & STORY_BITS
            for node_area, name, flags, bits in task_nodes()[1:]:
                if node_area != area or name in self.open_tasks:
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
        """Is this actor born in this story state?"""
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
            out += [p for p in END_HIDDEN_PROTOTYPES.get(lev, []) if p not in out]
        return out


# levels ##########################################################################################


def level_names():
    """Every Jak 2 level name (a level-load-info's :name is alone on its line, unlike the level
    names in the continues' level lists)."""
    src = open(LEVEL_INFO, encoding="utf-8").read()
    return set(re.findall(r"^\s*:name '([a-z0-9-]+)\s*$", src, re.M))


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
        result[name] = dict(
            level=re.search(r":level '([a-z0-9-]+)", head).group(1),
            trans=_parse_vector(head, "trans"),
            quat=_parse_vector(head, "quat"),
            camera_trans=_parse_vector(head, "camera-trans"),
            camera_rot=[float(x) for row in rot[:3] for x in row],
            flags=set(flags.group(1).split()) if flags else set(),
            wants=wants,
        )
    return result


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
