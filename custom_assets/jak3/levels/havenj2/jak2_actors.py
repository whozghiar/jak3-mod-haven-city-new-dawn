"""Jak 2's actors of a level, as the decompiler dumps them (decompiler_out/jak2/entities/
<level>-actors.json), the ones Jak 2 spawns at the end of the game only.

Jak 2 births an actor when its kill-mask shares no bit with its level's task-mask
(goal_src/jak2/engine/entity/entity.gc). A level's task-mask is its base-task-mask, changed by the
closed story nodes of its task area (level-method-22, goal_src/jak2/engine/game/task/
task-control.gc: abs-task-mask sets it, set-task-mask adds bits, clear-task-mask removes them), plus
the bit `never`, always there. So the actors of a story state other than the end (the palace lobby
airlock where Jak 2 has an open doorway, burning bushes and part spawners of missions...) are left
out, and every generator of havenj2 reads the actors here.
"""

import functools
import json
import os
import re

ENTITIES = "decompiler_out/jak2/entities"
GAME_TASK = "goal_src/jak2/engine/game/task/game-task.gc"
LEVEL_INFO = "goal_src/jak2/engine/level/level-info.gc"

# The story state of every level of the mod: the end of the game, but for these story nodes, taken
# as still open (the palace stays reachable: Jak 2 closes its doors once this mission is over).
OPEN_TASKS = {"palace-sneak-in-meeting"}

# task-mask bits (goal_src/jak2/engine/level/level-h.gc)
TASK_MASK = {**{f"task{i}": 1 << i for i in range(8)}, "done": 1 << 8, "dummy0": 1 << 9,
             "dummy1": 1 << 10, "dummy2": 1 << 11, "special": 1 << 12, "primary0": 1 << 13,
             "ctywide": 1 << 14, "never": 1 << 15, "movie0": 1 << 16, "movie1": 1 << 17,
             "movie2": 1 << 18}
KILL_MASK_NEVER = TASK_MASK["never"]
# the bits the story sets (the rest comes from settings and the loaded levels, left as they are)
STORY_BITS = 0x1FF


def mask_bits(text):
    """A (task-mask ...) value's bits."""
    return sum(TASK_MASK[name] for name in text.split())


@functools.lru_cache(maxsize=None)
def task_nodes(root=""):
    """Jak 2's story nodes, in order: (task area, name, flags, task-mask)."""
    src = open(os.path.join(root, GAME_TASK), encoding="utf-8").read()
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
def level_tasks(root=""):
    """Jak 2 level -> (task area, base-task-mask)."""
    src = open(os.path.join(root, LEVEL_INFO), encoding="utf-8").read()
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
def end_task_mask(level, root=""):
    """A level's task-mask bits set by the story at the end of the game (OPEN_TASKS left open)."""
    area, base = level_tasks(root).get(level, (None, 0))
    mask = base & STORY_BITS
    for node_area, name, flags, bits in task_nodes(root)[1:]:
        if node_area != area or name in OPEN_TASKS:
            continue
        if "abs-task-mask" in flags:
            mask = bits
        elif "set-task-mask" in flags:
            mask |= bits
        elif "clear-task-mask" in flags:
            mask &= ~bits
    return mask & STORY_BITS


def spawned(actor, level, root=""):
    """Is this actor born in Jak 2 at the end of the game?"""
    kill = int(actor["lump"].get("kill-mask", 0) or 0)
    return not kill & (KILL_MASK_NEVER | end_task_mask(level, root))


def level_actors(level, root=""):
    """Jak 2's actors of a level that Jak 2 spawns at the end of the game (root: the project root,
    when the working directory isn't)."""
    with open(os.path.join(root, ENTITIES, level + "-actors.json")) as f:
        return [a for a in json.load(f) or [] if spawned(a, level, root)]
