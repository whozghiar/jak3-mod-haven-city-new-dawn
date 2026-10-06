"""Jak 2 -> Jak 3: what changes between the two games, for the port's steps.

Jak 2 and Jak 3 share a lot: the entity and region script language, the ocean map, the traffic's
navigation data layouts (city-level-info, nav-graph, nav-mesh), the background's pat surface bits,
the particle system. This module holds the differences the steps translate. What a mod adds on top
(its own classes, what it keeps or drops) is in its port manifest.
"""

import re

from ..common import goal_lisp as gl
from ..common.goal_lisp import Atom, Str

SOURCE = "jak2"
TARGET = "jak3"

# scripts #########################################################################################
# (convert/scripts.py)

# calls that do nothing in Jak 3 (or only concern what isn't ported): removed
DROPPED_CALLS = {
    "want-sound", "want-anim", "want-force-vis", "want-force-inside", "task-close!",
    "setting-unset", "talker-spawn", "scene-play", "part-tracker", "sound-play-loop", "alive",
    "yes-play!", "mark-played!", "endlessfall", "show-hud", "entity-status?", "setting-value",
    "print", "want-vehicle",
}
# events of Jak 3's com-airlock and elevator kept when a script sends them to itself
KEPT_SELF_EVENTS = {"front", "back", "distance", "player-ridden?", "query", "sound", "status?"}
KEPT_QUERIES = {"going-up?", "going-down?", "player-standing-on?"}
# events kept when sent to another (renamed) entity
KEPT_OTHER_EVENTS = {"query", "jump-to", "trigger"}
# (focus-test? ...) flags that never hold in Jak 3: Jak has no mech
ABSENT_FOCUS = {"mech"}

# actors ##########################################################################################

# Jak 3's class for Jak 2's doors: Jak 3 has no class for some of them, they get the closest Jak 3
# door (every com-airlock child runs the same scripts). All in Jak 3's GAME (airlock.gc).
DOOR_ETYPES = {
    "hip-door-a": "hip-door-a",
    "hip-door-b": "hip-door-a",
    "hide-door-a": "cty-door",
    "hide-door-b": "hip-door-a",
    "oracle-door": "cty-door",
    "vin-door": "vin-door-ctyinda",
    "vin-door-ctyinda": "vin-door-ctyinda",
    "com-airlock-outer": "com-airlock-outer",
    "com-airlock-inner": "com-airlock-inner",
    "gar-door": "com-airlock-outer",
    "pal-throne-door": "com-airlock-outer",
    "pal-ent-door": "cty-door",
    # Jak 2's castle door is a com-airlock-outer (same model)
    "cas-front-door": "com-airlock-outer",
}
# the art group of Jak 3's classes (extracted from Jak 3's DGOs into the level's fr3). None: the
# class needs no art group of its level (swingpole: the bar is background).
ART_GROUPS = {
    "hip-door-a": "hip-door-a-ag",
    "cty-door": "cty-door-ag",
    "vin-door-ctyinda": "vin-door-ctyinda-ag",
    "com-airlock-outer": "com-airlock-outer-ag",
    "com-airlock-inner": "com-airlock-inner-ag",
    "warp-gate": "warp-gate-ag",
    "swingpole": None,
}
# Jak 2's warp gates are Jak 3's: the same on-notice ('("destination" on-activate wait-for))
WARP_GATE_ETYPES = {"warp-gate": "warp-gate"}
# Jak 2's crates are Jak 3's (a wood crate, its art in GAME), with their pickups (PICKUPS)
CRATES = {"crate": "crate"}
# Jak 2's pickup-type -> Jak 3's: Jak 3 added eco-pill-light (8) and lightjak (14) to pickup-type,
# and three guns of each color
PICKUPS = {**{n: n for n in range(8)},
           8: 9, 9: 10, 10: 11, 11: 12, 12: 13, 13: 15, 14: 16, 15: 17, 16: 18, 17: 19, 18: 20,
           19: 21, 20: 22, 21: 23, 22: 24, 23: 25, 24: 26, 25: 29, 26: 32, 27: 35}
# elevator-flags of Jak 2's elevators as Jak 3 elevators: running, teleport (starts at the stop
# closest to Jak) and fence (only solid during the ride). No prevent-jump: Jak moves freely on the
# platform.
ELEVATOR_FLAGS = 1 | 16 | 256

# continues #######################################################################################

# the continue flags kept from Jak 2's: no-auto (Jak 3 never picks it by itself), warp-gate (Jak
# arrives jumping out of the closest warp gate), no-blackout
KEPT_CONTINUE_FLAGS = ("no-auto", "warp-gate", "no-blackout")
# Jak 2's continues left out: the title, intro, new game (the prison), demo and cutscene ones
# (scene-wait: waiting for a cutscene)
SKIPPED_CONTINUE_FLAGS = {"demo", "demo-end", "title", "intro", "game-start", "scene-wait"}
SKIPPED_CONTINUE_NAMES = ("movie", "demo")

# particles #######################################################################################
# (steps/particles.py)

# Jak 2 -> Jak 3 flag names (same bits)
GROUP_FLAGS = {"use-local-clock": "sp0", "always-draw": "sp1", "screen-space": "sp2",
               "unk-3": "sp3", "unk-4": "sp4", "unk-5": "sp5", "unk-6": "sp6", "unk-7": "sp7",
               "unk-8": "sp8"}
ITEM_FLAGS = {"is-3d": "is-3d", "bit1": "sp1", "start-dead": "sp2", "launch-asap": "sp3",
              "bit6": "sp6", "bit7": "sp7", "bit8": "sp8"}
# the group flag of the static part spawners (Jak 2's unk-8): their launchers go to their level's
# part engine
STATIC_GROUP_FLAG = "unk-8"
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
# Jak 2's texture pages whose textures Jak 3 has in a page of its own, by name: Jak 2's common
# effects are Jak 3's level-default-sprite (Jak 2's effects page id is Jak 3's font page)
TPAGE_EQUIVALENTS = {"effects": "level-default-sprite", "common": "common"}
# the ids of those Jak 3 pages (goal_src/jak3/engine/data/tpages.gc)
TARGET_TPAGES = {"level-default-sprite": 4, "common": 1}
# particle callbacks Jak 3 has in GAME, by the same name
TARGET_CALLBACKS = {
    "sparticle-mode-animate", "sparticle-texture-day-night", "birth-func-texture-group",
    "sparticle-texture-animate", "check-drop-level-rain2", "sparticle-motion-blur",
    # the sprinklers' drops (water.gc)
    "check-water-level-drop-motion",
    "birth-func-copy-rot-color", "birth-func-copy2-rot-color", "birth-func-copy-omega-to-z",
    "birth-func-random-next-time", "check-drop-group-center",
    # the palace roof's rain (weather-part.gc)
    "birth-func-omega-normal-orient",
}
# Jak 2's splash callbacks (check-drop-level-<level>-drop-userdata): written in Jak 3's form
# (drop_func_text)
DROP_FUNC = re.compile(r"check-drop-level-([a-z0-9]+)-drop-userdata")
# Jak 2 matrix rows read by a copied callback -> Jak 3's sprite-vec-data-2d fields
SPRITE_ROWS = {(0, "x"): "x", (0, "y"): "y", (0, "z"): "z", (0, "w"): "sx", (1, "z"): "rot",
               (1, "w"): "sy", (2, "x"): "r", (2, "y"): "g", (2, "z"): "b", (2, "w"): "a"}
SPRITE_VECTORS = {0: "x-y-z-sx", 1: "flag-rot-sy", 2: "r-g-b-a"}


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


def copied_func_text(form, new_name, part_map, where, data_names=None):
    """A particle callback copied from Jak 2 (form: its defun) in Jak 3's form: renamed, its part
    ids moved (part_map), its matrix argument typed sprite-vec-data-2d (Jak 3 hands the particle's
    sprite data, the same layout: x y z sx, then flag matrix rot sy), the source data it reads
    renamed to the copies (data_names: the level's "data", source define -> ours). where: its Jak 2
    file."""
    data_names = data_names or {}
    name = str(form[1])
    sprite = None
    args = []
    for arg in form[2]:
        if gl.is_list(arg) and len(arg) == 2 and arg[1] == Atom("matrix"):
            sprite = arg[0]
            arg = [arg[0], Atom("sprite-vec-data-2d")]
        args.append(arg)

    def fix(f):
        if not isinstance(f, list):
            if isinstance(f, Atom) and str(f) in data_names:
                return Atom(data_names[str(f)])
            return f
        if (sprite is not None and gl.is_list(f, "->") and len(f) == 3 and f[1] == sprite
                and f[2] == Atom("vector")):
            # the matrix's rows (their first: the particle position)
            return [Atom("->"), sprite, Atom(SPRITE_VECTORS[0])]
        if (sprite is not None and gl.is_list(f, "->") and len(f) == 4 and f[1] == sprite
                and f[2] == Atom("vector") and int(f[3]) in SPRITE_VECTORS):
            # a whole row (the particle position: Jak 2's matrix row 0)
            return [Atom("->"), sprite, Atom(SPRITE_VECTORS[int(f[3])])]
        if sprite is not None and gl.is_list(f, "->") and len(f) == 5 and f[1] == sprite:
            key = (int(f[3]), str(f[4]))
            if f[2] != Atom("vector") or key not in SPRITE_ROWS:
                raise KeyError(f"{name}: no Jak 3 field for {gl.dump(f)}")
            return [Atom("->"), sprite, Atom(SPRITE_ROWS[key])]
        if gl.is_list(f, "->") and len(f) == 3 and f[1] == Atom("*part-id-table*"):
            return [Atom("->"), f[1], Atom(str(part_map[int(f[2])]))]
        if gl.is_list(f, "sound-play"):
            raise KeyError(f"{name} plays a sound (Jak 2's): not copied")
        return [fix(x) for x in f]

    body = form[3:]
    if body and isinstance(body[0], Str):
        body = body[1:]  # Jak 2's docstring
    lines = [f"(defun {new_name} {gl.dump(args)}", f'  "Jak 2\'s {name} ({where})."']
    lines += ["  " + gl.pretty(fix(b), 2) for b in body]
    lines.append("  )")
    return "\n".join(lines)


# ocean ###########################################################################################
# (steps/ocean.py)


def ocean_map_forms(text, source_name):
    """The top-level forms of a Jak 2 ocean map source file to keep for Jak 3: all but the
    in-package and the ocean-spheres (Jak 3's ocean-map has none)."""
    body = text[text.index(";; DECOMP BEGINS") + len(";; DECOMP BEGINS"):] \
        if ";; DECOMP BEGINS" in text else text
    kept = []
    for start, end in top_level_forms(body):
        form = body[start:end]
        if f"*ocean-spheres-{source_name}*" in form:
            continue
        if form.startswith("(in-package"):
            continue
        kept.append(form)
    return kept


def top_level_forms(text):
    """(start, end) of each top-level form of a GOAL file."""
    forms = []
    depth = 0
    start = None
    i = 0
    in_string = False
    while i < len(text):
        c = text[i]
        if in_string:
            if c == "\\":
                i += 1
            elif c == '"':
                in_string = False
        elif c == ";":
            i = text.index("\n", i) if "\n" in text[i:] else len(text)
            continue
        elif c == '"':
            in_string = True
        elif c == "(":
            if depth == 0:
                start = i
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                forms.append((start, i + 1))
        i += 1
    return forms
