"""Jak 2's actors of a level, as the decompiler dumps them (decompiler_out/jak2/entities/
<level>-actors.json), without the ones Jak 2 never spawns.

An actor whose kill-mask has the task-mask bit `never` (goal_src/jak2/engine/level/level-h.gc) is
never born: Jak 2's levels always have that bit in their task-mask. The dumps still list them
(leftovers such as a palace lobby airlock where Jak 2 has an open doorway, a Hip Hog door, burning
bushes and part spawners of other story states), so every generator of havenj2 reads the actors here.
"""

import json
import os

ENTITIES = "decompiler_out/jak2/entities"
# (task-mask never)
KILL_MASK_NEVER = 0x8000


def spawned(actor):
    """Is this actor ever born in Jak 2?"""
    return not int(actor["lump"].get("kill-mask", 0) or 0) & KILL_MASK_NEVER


def level_actors(level, root=""):
    """Jak 2's actors of a level that Jak 2 spawns (root: the project root, when the working
    directory isn't)."""
    with open(os.path.join(root, ENTITIES, level + "-actors.json")) as f:
        return [a for a in json.load(f) or [] if spawned(a)]
