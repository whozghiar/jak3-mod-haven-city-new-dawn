#!/usr/bin/env python3
"""Links Jak 2's Haven City (the havenj2 custom level) to the places reached from it, loading and
unloading them the way Jak 2 does.

Jak 2 loads its levels with scripts: in doors and elevators (on-activate, on-enter, on-inside...),
in invisible regions (a plane crossed in a street, a volume entered...) and in its continue points.
This script ports all of them, translated by jak2_scripts.py: havenj2 stands for every city level
(Jak 2 streamed the districts, havenj2 is the whole city at once), every other place is one custom
level per Jak 2 level, and the level sets Jak 2 loads together are kept.

Generates, from Jak 2's extracted data:
  - the doors and elevators of havenj2 (the "actors" section of havenj2.jsonc, between the
    GENERATED markers), havenj2.gd (with the traffic's code and art, see TRAFFIC_CODE_DGO) and
    havenj2-regions.json (the city's load regions),
  - one custom level per destination (custom_assets/jak3/levels/hj2-*/: .jsonc, .gd, regions),
  - every level's level-load-info with its continue points
    (goal_src/jak3/pc/features/jak2-haven-city-levels.gc),
  - the palace gate model (custom_assets/jak3/models/custom_levels/hj2-palace-door.glb).

Inputs (run a Jak 2 `task extract` first):
  decompiler_out/jak2/entities/<level>-actors.json   door/elevator placement and scripts
  decompiler_out/jak2/levels/ctypal/palace-door-lod0.glb   the palace gate
  goal_src/jak2/tools/db-fixtures/fixture-region.sql  Jak 2's regions and their scripts
  goal_src/jak2/engine/level/level-info.gc          continue points

Run from the repository root: python custom_assets/jak3/levels/havenj2/gen_havenj2_links.py
The level build steps (goal_src/jak3/game.gp) are written by hand.
"""

import glob
import json
import math
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jak2_scripts import Translator  # noqa: E402
import jak2_actors  # noqa: E402
from gen_util import write_if_changed  # noqa: E402
import gen_havenj2_props as props_gen  # noqa: E402
import gen_havenj2_particles as particles_gen  # noqa: E402
import gen_havenj2_nav as nav_gen  # noqa: E402

ENTITIES = "decompiler_out/jak2/entities"
JAK2_LEVEL_INFO = "goal_src/jak2/engine/level/level-info.gc"
JAK2_REGIONS = "goal_src/jak2/tools/db-fixtures/fixture-region.sql"
LEVELS_DIR = "custom_assets/jak3/levels"
HAVENJ2_JSONC = f"{LEVELS_DIR}/havenj2/havenj2.jsonc"
NAV_DATA = f"{LEVELS_DIR}/havenj2/havenj2-nav.json"
LEVEL_INFO_OUT = "goal_src/jak3/pc/features/jak2-haven-city-levels.gc"
PALACE_DOOR_SRC = "decompiler_out/jak2/levels/ctypal/palace-door-lod0.glb"
PALACE_DOOR_OUT = "custom_assets/jak3/models/custom_levels/hj2-palace-door.glb"
METER = 4096.0

# levels ##########################################################################################

CITY = "havenj2"
# Jak 2's levels merged into havenj2. The stadium grounds are one more district: Jak 2 loaded them
# next to its streets like the others.
CITY_LEVELS = [
    "ctywide", "ctysluma", "ctyslumb", "ctyslumc", "ctyport", "ctymarka", "ctymarkb", "ctyinda",
    "ctyindb", "ctygena", "ctygenb", "ctygenc", "ctyfarma", "ctyfarmb", "ctypal", "stadium",
]

# One custom level per Jak 2 place reached from the city.
#   memory: the level-memory-mode. Jak 3's level heap has 18 chunks: havenj2 (large) takes 12,
#           a small-edge 6 (at either end), a small-center the 6 in the middle. So a place loaded
#           next to the city must be small-edge, and each set of three places Jak 2 loads without
#           the city needs one small-center: palroof is, its partners (palshaft, palcab) aren't.
#   sky:    Jak 2's :sky (the sky is only drawn when an active level has it)
PLACES = [
    dict(name="hj2-hiphog", nick="hjh", iso="HJ2HIPHG", index=0x12A, base_id=21500,
         jak2="hiphog", what="the Hip Hog saloon", sky=False),
    dict(name="hj2-gun", nick="hjg", iso="HJ2GUN", index=0x12B, base_id=21600,
         jak2="gungame", what="the gun course", sky=False),
    dict(name="hj2-vin", nick="hjv", iso="HJ2VIN", index=0x12C, base_id=21700,
         jak2="vinroom", what="Vin's power station room", sky=False),
    dict(name="hj2-hide", nick="hjd", iso="HJ2HIDE", index=0x12D, base_id=21800,
         jak2="hideout", what="the Underground's hideout", sky=False),
    dict(name="hj2-oracle", nick="hjo", iso="HJ2ORACL", index=0x12E, base_id=21900,
         jak2="oracle", what="the Oracle", sky=False),
    dict(name="hj2-garage", nick="hjk", iso="HJ2GARAG", index=0x12F, base_id=22000,
         jak2="garage", what="Keira's garage, behind the stadium grounds", sky=False),
    dict(name="hj2-ruins", nick="hjr", iso="HJ2RUINS", index=0x131, base_id=22200,
         jak2="ruins", what="Dead Town, through the slums airlock", sky=True),
    dict(name="hj2-consb", nick="hjb", iso="HJ2CONSB", index=0x133, base_id=22300,
         jak2="consiteb", what="the tunnel to the construction site, from the industrial section",
         sky=True),
    dict(name="hj2-cons", nick="hjc", iso="HJ2CONS", index=0x134, base_id=22400,
         jak2="consite", what="the construction site", sky=True),
    dict(name="hj2-pshaft", nick="hjs", iso="HJ2PSHFT", index=0x135, base_id=22500,
         jak2="palshaft", what="the palace pillars: the palace lobby and the cable pillar",
         sky=True),
    dict(name="hj2-proof", nick="hjp", iso="HJ2PROOF", index=0x136, base_id=22600,
         jak2="palroof", memory="small-center", what="the palace roof", sky=True),
    # palcab's backdrop (the city seen from above) spreads over kilometers, collision included: keep
    # the collision of the palace top, the pillar tops and the cable between them, else the collide
    # hash grid alone makes a 67MB level
    dict(name="hj2-pcab", nick="hjq", iso="HJ2PCAB", index=0x137, base_id=22700,
         jak2="palcab", what="the palace cable, between the pillar tops", sky=True,
         collision_bounds=[0, 200, -250, 400, 620, 800]),
    # the pumping station: the slums airlock opens on atollext (the way to it, loaded next to the
    # city), whose far airlock leads to atoll (the station itself, loaded without the city).
    #   ocean: Jak 2's :ocean (the city's ocean map, havenj2-ocean.gc in GAME)
    dict(name="hj2-atollx", nick="hja", iso="HJ2ATOLX", index=0x138, base_id=22800,
         jak2="atollext", what="the way to the pumping station, from the slums airlock", sky=True),
    # like palcab, the collision of their backdrops spreads over kilometers: keep the playable area
    dict(name="hj2-atoll", nick="hjl", iso="HJ2ATOLL", index=0x139, base_id=22900,
         jak2="atoll", memory="large", what="the pumping station", sky=True, ocean=True,
         code=["hj2-atoll-obs.o"], collision_bounds=[120, -80, -1420, 900, 250, -660]),
    # Haven Forest: the gardens airlock opens on the foot of the mountain (mountain), whose warp gate
    # leads to its top (mountain again, with the temple outside, mtnext, as a backdrop); there
    # Jak 2's trans-plat rides down to Haven Forest (forest, then forestb at its far end).
    dict(name="hj2-mount", nick="hjm", iso="HJ2MOUNT", index=0x13A, base_id=23000,
         jak2="mountain", what="the mountain, from the gardens airlock to the way to Haven Forest",
         sky=True, code=["hj2-mount-obs.o"], collision_bounds=[-1050, -60, -200, -330, 340, 620]),
    dict(name="hj2-mtnx", nick="hjx", iso="HJ2MTNX", index=0x13B, base_id=23100,
         jak2="mtnext", what="the outside of the mountain temple, seen from the mountain top",
         sky=True),
    dict(name="hj2-forest", nick="hjf", iso="HJ2FORST", index=0x13C, base_id=23200,
         jak2="forest", memory="large", what="Haven Forest", sky=True, ocean=True),
    dict(name="hj2-forstb", nick="hjn", iso="HJ2FORSB", index=0x13D, base_id=23300,
         jak2="forestb", what="the far end of Haven Forest", sky=True, ocean=True),
    # the dig: the castle pad (caspad), reached by the port's air train (AIR_TRAINS) or on foot from
    # the pumping station, whose elevator goes down to the dig (dig3a, loaded without the city,
    # then dig3b, its far end). Jak 2 ends the dig with the warp gate to Vin's room.
    dict(name="hj2-caspad", nick="hjy", iso="HJ2CASPD", index=0x13E, base_id=23400,
         jak2="caspad", what="the castle pad, above the dig", sky=True),
    dict(name="hj2-dig", nick="hjt", iso="HJ2DIG", index=0x13F, base_id=23500,
         jak2="dig3a", memory="large", what="the dig", sky=False,
         code=["rigid-body-plat.o", "hj2-dig-obs.o"]),
    dict(name="hj2-digb", nick="hju", iso="HJ2DIGB", index=0x140, base_id=23600,
         jak2="dig3b", what="the far end of the dig", sky=False),
    # Not ported: the inside of the palace (palent, throne), only reached in Jak 2's missions.
]
PLACE_BY_NAME = {p["name"]: p for p in PLACES}
LEVEL_MAP = {lev: CITY for lev in CITY_LEVELS}
LEVEL_MAP.update({p["jak2"]: p["name"] for p in PLACES})
MEMORY = {CITY: "large"}
MEMORY.update({p["name"]: p.get("memory", "small-edge") for p in PLACES})
# Jak 2 levels that are only a backdrop: a door waiting for them to be loaded doesn't need them
BACKDROP_LEVELS = {"palout"}

# The story state the scripts are evaluated in: the end of the game, except for the palace, which
# is kept open (Jak 2 closes its doors once the sneak-in mission is over).
OPEN_TASKS = {"palace-sneak-in-meeting"}
# Per region, tasks taken as not done yet, to pick another of Jak 2's branches:
#   528: the palace pillar elevator goes to the roof first (see PALACE_ELEVATOR), so passing this
#        plane on the way up loads the roof, like before the sneak-in mission
REGION_OPEN_TASKS = {528: {"palace-sneak-in-introduction"}}

# doors ###########################################################################################
# Jak 2's doors and elevators placed in each level, by their Jak 2 level and name. Their scripts
# are Jak 2's, translated. A door that only leads to a place that isn't ported stays shut (no
# scripts), like one listed in CLOSED.

DOORS = [
    # the Hip Hog and the gun course, in the port
    ("ctyport", "hip-door-a-6"), ("hiphog", "hip-door-b-1"),
    ("ctyport", "hip-door-a-10"), ("gungame", "hip-door-a-9"),
    # Vin's room and the construction site, in the industrial section
    ("ctyinda", "vin-door-ctyinda-1"), ("vinroom", "vin-door-5"),
    ("ctyinda", "vin-door-ctyinda-2"), ("consiteb", "vin-door-ctyinda-5"),
    ("consiteb", "com-airlock-inner-40"), ("consite", "com-airlock-outer-34"),
    # the hideout and the Oracle, in the slums
    ("ctysluma", "hide-door-a-3"), ("hideout", "hide-door-b-2"),
    ("ctyslumc", "oracle-door-3"), ("oracle", "oracle-door-1"),
    # the Dead Town airlock: city door (outer + inner halves), then the Dead Town door
    ("ctyslumb", "com-airlock-outer-9"), ("ctyslumb", "com-airlock-inner-11"),
    ("ctyslumb", "com-airlock-inner-12"), ("ruins", "com-airlock-outer-2"),
    # Keira's garage, in the stadium grounds
    ("stadium", "gar-door-3"), ("stadium", "gar-door-4"),
    # the palace: the gate to the lobby of the palace pillar, the airlock to the cable pillar, and
    # at the top of the pillars the doors to the roof and the cable
    ("ctypal", "palace-door-1"), ("palshaft", "com-airlock-inner-26"),
    ("ctygenb", "com-airlock-outer-15"), ("palshaft", "com-airlock-inner-22"),
    ("palshaft", "com-elevator-1"),
    ("palshaft", "com-airlock-inner-25"), ("palroof", "com-airlock-outer-18"),
    ("palshaft", "com-airlock-inner-23"), ("palcab", "com-airlock-outer-17"),
    # the pumping station: the slums door, the two inner doors of atollext's airlock, the station's
    # door
    ("ctyslumc", "com-airlock-outer-12"), ("atollext", "com-airlock-inner-17"),
    ("atollext", "com-airlock-inner-18"), ("atoll", "com-airlock-outer-1"),
    # the mountain: the gardens airlock (city door, inner halves) and the mountain door
    ("ctyfarma", "com-airlock-outer-32"), ("ctyfarma", "com-airlock-inner-20"),
    ("ctyfarma", "com-airlock-inner-38"), ("mountain", "com-airlock-outer-4"),
    # the castle pad's elevator down to the dig
    ("caspad", "cpad-elevator-1"),
]
CLOSED = [
    # the castle (not ported), from the castle pad
    ("caspad", "cas-front-door-1"),
    # Mar's tomb, the sewers, the underport
    ("ctypal", "com-airlock-outer-22"), ("ctypal", "com-airlock-inner-28"),
    ("ctypal", "com-airlock-inner-27"),
    ("ctyindb", "com-airlock-outer-13"),
    ("ctyport", "hip-door-a-20"), ("ctyport", "hip-door-a-21"),
    # the pillar doors to the palace entrance hall (the inside of the palace isn't a place of its
    # own here). Not placed at all, like every actor Jak 2 never spawns (jak2_actors.py): the lobby
    # airlock com-airlock-outer-20 (Jak 2's doorway there is open) and the Hip Hog's hip-door-a-7.
    ("palshaft", "com-airlock-inner-36"), ("palshaft", "com-airlock-inner-37"),
]
# script changes, by (Jak 2 level, name): script -> replacement (None removes it)
SCRIPT_OVERRIDES = {}

# Jak 3 has no class for some of Jak 2's doors: they get the closest Jak 3 door (every com-airlock
# child runs the same scripts). All these classes are in Jak 3's GAME (airlock.gc), except the ones
# in levels/havenj2/havenj2-obs.gc.
JAK3_ETYPE = {
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
    # Jak 2's own gate, rebuilt from its model (see write_palace_door)
    "palace-door": "hj2-palace-door",
    # Jak 3 has no com-elevator: hj2-elevator is Jak 3's elevator with Jak 2's model (ACTOR_MODELS)
    "com-elevator": "hj2-elevator",
    "cpad-elevator": "hj2-cpad-elevator",
}
# Jak 2's elevators among the DOORS (see make_elevator)
ELEVATOR_ETYPES = {"com-elevator", "cpad-elevator"}
# models of havenj2's custom actors, built by build-actor (goal_src/jak3/game.gp), added to its fr3
CITY_CUSTOM_MODELS = ["hj2-palace-door"]

# Haven City's traffic (goal_src/jak3/levels/havenj2/havenj2-traffic.gc): Jak 3's traffic code, the
# objects of ctywide's DGO (CWI) but those of Jak 3's city itself (its props, particles, missions,
# scenes, trail graph and height map), which havenj2's DGO links in the same order...
TRAFFIC_CODE_DGO = "goal_src/jak3/dgos/cwi.gd"
TRAFFIC_CODE_SKIPPED = {
    "ctywide-texture", "ctywide-part", "ctywide-obs", "ctywide-tasks", "ctywide-scenes",
    "ctyport-obs", "mhcity-part", "mhcity-obs", "mhcity-obs2", "krimson-wall", "searchlight",
    "trail", "trail-graph",
    # Jak 2's height map instead (havenj2-height-map.gc, written by gen_havenj2_nav.py)
    "traffic-height-map",
}
TRAFFIC_CODE_REPLACED = {"traffic-height-map": "havenj2-height-map"}
# ...and the art of the traffic types havenj2 spawns (the level of each is set by
# havenj2-traffic-start): Jak 3's citizens (CTYPEPA), Freedom League guards and their shields
# (CTYPESA), the city's hover cars (CTYCARA) and bikes (CTYCARB), their pilots, the vehicles'
# explosion and Jak's animations in a vehicle (CWI)
TRAFFIC_ART = [
    "citizen-norm-ag", "citizen-fat-ag", "citizen-chick-ag",
    "crimson-guard-ag", "shield-sphere-ag", "shield-sphere-distort-ag", "shield-sphere-explode-ag",
    "cara-ag", "carb-ag", "carc-ag", "bikea-ag", "bikeb-ag", "bikec-ag",
    "citizen-norm-rider-ag", "vehicle-explosion-ag",
    "jak-pilot+0-ag", "jak-pilot-hcar+0-ag", "jak-pilot-gun+0-ag",
]
ART_GROUP = {
    "hip-door-a": "hip-door-a-ag",
    "cty-door": "cty-door-ag",
    "vin-door-ctyinda": "vin-door-ctyinda-ag",
    "com-airlock-outer": "com-airlock-outer-ag",
    "com-airlock-inner": "com-airlock-inner-ag",
    "warp-gate": "warp-gate-ag",
    "hj2-air-train": "air-train-ag",
    "scene-stage": None,
    # built by build-actor (goal_src/jak3/game.gp), not extracted from Jak 3
    "hj2-palace-door": None,
    "hj2-elevator": None,
    "hj2-cpad-elevator": None,
    "hj2-trans-plat": None,
    "hj2-iris-door": None,
    "hj2-mtn-elevator": None,
}
# Jak 2's com-elevator: a 12 x 13m platform, floor at its origin's height, from 0.85m behind its
# origin to 12m in front (skel bounds: 5.6m in front). Its collision: the floor, and a fence along
# its edges that is only solid during the ride (Jak 3's elevator fence, prim id #xfe000000), so Jak
# can walk on it without falling between it and the shaft.
COM_ELEVATOR_COLLIDE = [
    [((-6.0, -1.0, -0.85), (6.0, 0.0, 12.0))],
    [((-6.0, 0.0, -0.85), (-5.7, 3.0, 12.0)), ((5.7, 0.0, -0.85), (6.0, 3.0, 12.0)),
     ((-6.0, 0.0, -0.85), (6.0, 3.0, -0.55)), ((-6.0, 0.0, 11.7), (6.0, 3.0, 12.0))],
]
# Jak 2's cpad-elevator (the castle pad down to the dig): a 24 x 24m platform, floor at its origin's
# height. Its collision, like the com-elevator's: the floor, and a fence along its edges, solid
# during the ride only.
CPAD_ELEVATOR_COLLIDE = [
    [((-12.2, -1.0, -12.3), (12.2, 0.0, 12.3))],
    [((-12.2, 0.0, -12.3), (-11.9, 3.0, 12.3)), ((11.9, 0.0, -12.3), (12.2, 3.0, 12.3)),
     ((-12.2, 0.0, -12.3), (12.2, 3.0, -12.0)), ((-12.2, 0.0, 12.0), (12.2, 3.0, 12.3))],
]
# elevator-flags of Jak 2's elevators: running, teleport (starts at the stop closest to Jak) and
# fence (above). No prevent-jump: Jak moves freely on the platform.
ELEVATOR_FLAGS = 1 | 16 | 256

# The places' own actors, by Jak 2 level and name. The mountain's: the warp gates between its foot
# (the gardens airlock) and its top, Jak 2's only way up; the trans-plat riding from the top down to
# Haven Forest; the iris doors, shut like before Mar's tomb is found (the story state of the palace
# plaza, see HIDDEN_PROTOTYPES; they lead to the canyon, which isn't ported); and the temple
# elevator, parked at the top (it only goes down to the far iris door). Their classes are in
# goal_src/jak3/levels/havenj2/hj2-mount-obs.gc, but Jak 3's warp-gate. The dig's warp gate, to Vin's
# room.
PLACE_ACTORS = [
    ("mountain", "warp-gate-10"), ("mountain", "warp-gate-11"), ("mountain", "trans-plat-1"),
    ("mountain", "mtn-iris-door-2"), ("mountain", "mtn-iris-door-3"),
    ("mountain", "mtn-plat-elevator-1"),
    ("dig3a", "warp-gate-28"),
]
PLACE_ETYPE = {"trans-plat": "hj2-trans-plat", "mtn-iris-door": "hj2-iris-door",
               "mtn-plat-elevator": "hj2-mtn-elevator"}

# Jak 2's air trains between the port and the castle pad, as hj2-air-train (Jak 3's air train, in
# GAME: jak2-haven-city-world.gc). Riding one plays Jak 3's own air train cutscenes (Jak 2's aren't
# in Jak 3), their copies in jak2-haven-city-world.gc: Jak 3's air train stands at Jak 2's port, and
# its desert one 28m high like the castle pad's, so Jak 3's scenes of those two places play around
# ours. Its on-notice is Jak 3's: '("continue" (scene-play '(scenes)) #f (want-anim first scene)).
# Jak 2 hides the port's once the game is over: here both always run. By Jak 2 level and name:
# (Jak 2 continue, our scenes, the first scene's animation, the place named by the prompt).
AIR_TRAINS = [
    # to the dig: Jak boards at the port, then gets off on the castle pad
    ("ctyport", "air-train-1", "caspad-warp", ["hj2-air-train-port-out", "hj2-air-train-caspad-in"],
     "city-air-train-in-desert", "the Dig Site"),
    # back to the port
    ("caspad", "air-train-3", "ctyport-warp", ["hj2-air-train-caspad-out", "hj2-air-train-port-in"],
     "desert-air-train-in", "Haven City"),
]
# the scenes' actors (Jak, Daxter, the particle helper) are Jak 3's cutscene models, in the level
# each scene plays in; the port's scenes take place at Jak 3's scene-stage-87, copied into havenj2
AIR_TRAIN_SCENE_ART = ["jakc-highres-ag", "daxter-highres-ag", "particleman-ag"]
JAK3_ENTITIES = "decompiler_out/jak3/entities"
AIR_TRAIN_SCENE_STAGES = [("ctyport", "scene-stage-87")]

# Models rebuilt from Jak 2's, by our etype: (model, Jak 2's rip, the primitives kept, collision:
# None for a box around the model, else its meshes of boxes). Written by
# gen_havenj2_props.write_actor_glb, built by build-actor (goal_src/jak3/game.gp).
RIPS = "decompiler_out/jak2/levels"
ACTOR_MODELS = {
    "hj2-elevator": ("hj2-com-elevator", f"{RIPS}/palshaft/com-elevator-lod0.glb", [0, 1, 2, 3, 4],
                     COM_ELEVATOR_COLLIDE),
    "hj2-trans-plat": ("hj2-trans-plat", f"{RIPS}/mountain/mtn-plat-return-lod0.glb", [0, 1, 2, 3],
                       None),
    "hj2-iris-door": ("hj2-iris-door", f"{RIPS}/mountain/mtn-iris-door-lod0.glb", [0, 1], None),
    "hj2-mtn-elevator": ("hj2-mtn-elevator", f"{RIPS}/mountain/mtn-plat-elevator-lod0.glb",
                         [0, 1, 2], None),
    # PORTED_ACTORS (None: every primitive; {"hull": y}: the convex hull above y as collision)
    "hj2-piston": ("hj2-piston", f"{RIPS}/atoll/piston-lod0.glb", None, {"hull": None}),
    "hj2-turbine": ("hj2-turbine", f"{RIPS}/atoll/turbine-lod0.glb", None, {"hull": None}),
    # its base (at its origin) isn't solid, only the walkway, 8m above
    "hj2-liftcat": ("hj2-liftcat", f"{RIPS}/atoll/liftcat-lod0.glb", None, {"hull": 7.5}),
    "hj2-atollrotpipe": ("hj2-atollrotpipe", f"{RIPS}/atoll/atollrotpipe-lod0.glb", None,
                         {"hull": None}),
    "hj2-slider": ("hj2-slider", f"{RIPS}/atoll/slider-lod0.glb", None, {"hull": None}),
    "hj2-atoll-windmill": ("hj2-atoll-windmill", f"{RIPS}/atoll/atoll-windmill-lod0.glb", None,
                           None),
    "hj2-atoll-valve": ("hj2-atoll-valve", f"{RIPS}/atoll/atoll-valve-lod0.glb", None, None),
    "hj2-atoll-hatch": ("hj2-atoll-hatch", f"{RIPS}/atoll/atoll-hatch-lod0.glb", None, None),
    "hj2-atoll-mar-symbol": ("hj2-atoll-mar-symbol", f"{RIPS}/atoll/atoll-mar-symbol-lod0.glb",
                             None, None),
    "hj2-mtn-plat-updown": ("hj2-mtn-plat-updown", f"{RIPS}/mountain/mtn-plat-updown-lod0.glb", None,
                            {"hull": None}),
    "hj2-mtn-plat-long": ("hj2-mtn-plat-long", f"{RIPS}/mountain/mtn-plat-long-lod0.glb", None,
                          {"hull": None}),
    "hj2-mtn-plat-shoot": ("hj2-mtn-plat-shoot", f"{RIPS}/mountain/mtn-plat-shoot-lod0.glb", None,
                           {"hull": None}),
    "hj2-mtn-plat-buried": ("hj2-mtn-plat-buried", f"{RIPS}/mountain/mtn-plat-buried-lod0.glb",
                            None, {"hull": None}),
    "hj2-pal-windmill": ("hj2-pal-windmill", f"{RIPS}/mountain/pal-windmill-lod0.glb", None, None),
    # the model of the trans-plat
    "hj2-mtn-plat-gap": ("hj2-trans-plat", f"{RIPS}/mountain/mtn-plat-return-lod0.glb",
                         [0, 1, 2, 3], None),
    "hj2-cpad-elevator": ("hj2-cpad-elevator", f"{RIPS}/caspad/cpad-elevator-lod0.glb", None,
                          CPAD_ELEVATOR_COLLIDE),
    # the dig (hj2-dig-obs.gc)
    "hj2-dig-sinking-plat": ("hj2-dig-sinking-plat", f"{RIPS}/dig3a/dig-sinking-plat-lod0.glb",
                             None, {"hull": None}),
    "hj2-dig-tipping-rock": ("hj2-dig-tipping-rock", f"{RIPS}/dig3a/dig-tipping-rock-lod0.glb",
                             None, {"hull": None}),
    "hj2-dig-spikey-step": ("hj2-dig-spikey-step", f"{RIPS}/dig3a/dig-spikey-step-lod0.glb", None,
                            {"hull": None}),
    # the two steps turn with the wheel (Jak 2's collide meshes: platform_a, platform_b, the wheel)
    "hj2-dig-wheel-step": ("hj2-dig-wheel-step", f"{RIPS}/dig3a/dig-wheel-step-lod0.glb", None,
                           [{"hull": None, "joint": "platform_a"},
                            {"hull": None, "joint": "platform_b"},
                            {"hull": None, "joint": "wheel"}]),
    # the balloon's collision is spheres (hj2-dig-obs.gc)
    "hj2-dig-balloon-lurker": ("hj2-dig-balloon-lurker",
                               f"{RIPS}/dig3a/dig-balloon-lurker-lod0.glb", None, None),
    "hj2-dig-log": ("hj2-dig-log", f"{RIPS}/dig3a/dig-log-lod0.glb", None, {"hull": None}),
    "hj2-dig-button": ("hj2-dig-button", f"{RIPS}/dig3a/dig-button-lod0.glb", None,
                       {"hull": None}),
    "hj2-dig-totem": ("hj2-dig-totem", f"{RIPS}/dig3a/dig-totem-lod0.glb", None, {"hull": None}),
    "hj2-dig-sphere-door": ("hj2-dig-sphere-door",
                            f"{RIPS}/dig3a/dig-spikey-sphere-door-lod0.glb", None, None),
}
# the balloon lurker's trapeze (spawned by hj2-dig-balloon-lurker, no actor of its own): Jak 2 keeps
# its swings (Jak off and on the bar) in the balloon lurker's art group, (model, rip, animations)
DIG_TRAPEZE_MODEL = ("hj2-dig-trapeze", f"{RIPS}/dig3a/dig-balloon-lurker-trapeze-lod0.glb", [
    (f"{RIPS}/dig3a/dig-balloon-lurker-lod0.glb", "dig-balloon-lurker-trapeze-jak-off",
     "hj2-dig-trapeze-idle"),
    (f"{RIPS}/dig3a/dig-balloon-lurker-lod0.glb", "dig-balloon-lurker-trapeze-jak-on",
     "hj2-dig-trapeze-jak-on"),
])

# Jak 2's platforms and props of the pumping station, the mountain and the dig, ported with their
# models (ACTOR_MODELS), by Jak 2 etype: (our etype, the lumps kept: name -> res type). Their
# classes are in goal_src/jak3/levels/havenj2/hj2-atoll-obs.gc, hj2-mount-obs.gc and
# hj2-dig-obs.gc. Not ported from the dig: its enemies, the spiky spheres its doors roll (the doors
# stay, still) and the stomp blocks.
PORTED_LEVELS = {"atoll", "mountain", "dig3a"}
PORTED_ACTORS = {
    "piston": ("hj2-piston", {"move-range": "float", "sync": "float"}),
    "turbine": ("hj2-turbine", {"rotspeed": "float", "rise-height": "float"}),
    "liftcat": ("hj2-liftcat", {"trans-offset": "vector", "scale-mult": "vector"}),
    "atollrotpipe": ("hj2-atollrotpipe", {"cycle-speed": "float"}),
    "slider": ("hj2-slider", {"path": "vector", "sync": "float"}),
    "atoll-windmill": ("hj2-atoll-windmill", {"sync": "float"}),
    "atoll-valve": ("hj2-atoll-valve", {}),
    "atoll-hatch": ("hj2-atoll-hatch", {}),
    "atoll-mar-symbol": ("hj2-atoll-mar-symbol", {}),
    "mtn-plat-updown": ("hj2-mtn-plat-updown", {"path": "vector", "sync": "float"}),
    "mtn-plat-long": ("hj2-mtn-plat-long", {"sync": "float"}),
    "mtn-plat-shoot": ("hj2-mtn-plat-shoot",
                       {"path": "vector", "path-k": "float", "sync": "float", "delay": "float"}),
    "mtn-plat-buried": ("hj2-mtn-plat-buried", {}),
    "pal-windmill": ("hj2-pal-windmill", {}),
    # at the top of its path: raised over the gap (see hj2-mount-obs.gc)
    "mtn-plat-gap": ("hj2-mtn-plat-gap", {}),
    "dig-sinking-plat": ("hj2-dig-sinking-plat", {}),
    "dig-tipping-rock": ("hj2-dig-tipping-rock", {}),
    "dig-spikey-step": ("hj2-dig-spikey-step", {"cycle-speed": "float"}),
    "dig-wheel-step": ("hj2-dig-wheel-step", {"rotspeed": "float"}),
    "dig-balloon-lurker": ("hj2-dig-balloon-lurker",
                           {"options": "int32", "path": "vector", "sync": "float"}),
    # the log is raised and the buttons down, like once Jak 2's dig is done
    "dig-log": ("hj2-dig-log", {}),
    "dig-button": ("hj2-dig-button", {}),
    "dig-totem": ("hj2-dig-totem", {}),
    "dig-spikey-sphere-door": ("hj2-dig-sphere-door", {}),
}

# Jak 2's crates of the places, as Jak 3's (a wood crate, its art in GAME), with their pickups. Jak 3
# added eco-pill-light (8) and lightjak (14) to pickup-type, and three guns of each color.
CRATE_LEVELS = {"atoll", "mountain", "forest", "dig3a"}
JAK2_PICKUP = {**{n: n for n in range(8)},
               8: 9, 9: 10, 10: 11, 11: 12, 12: 13, 13: 15, 14: 16, 15: 17, 16: 18, 17: 19, 18: 20,
               19: 21, 20: 22, 21: 23, 22: 24, 23: 25, 24: 26, 25: 29, 26: 32, 27: 35}

# The palace pillar had two elevators in one shaft: com-elevator-3 from the lobby to the palace
# entrance hall (346m), used by the sneak-in mission, and com-elevator-2 between the lobby and the
# roof door (417m), used after the palace boss. The inside of the palace isn't ported: only
# com-elevator-2 is, lobby <-> roof door, with its ride cameras. What each ride loads is set by
# Jak 2's scripts: region 528 loads the roof on the way up, the pillar top airlock (on-inside of
# com-airlock-inner-25) reloads the city as soon as Jak is back in from the roof, before the ride
# down (the low-res city seen from the roof must be gone before he goes through it).
PALACE_ELEVATOR = dict(level="palshaft", name="com-elevator-2")
# scripts sending events to Jak 2's elevators by name: they now go to the one that's left (the
# palace gate calls com-elevator-3 down to the lobby)
RENAMES = {"com-elevator-3": PALACE_ELEVATOR["name"], "com-elevator-2": PALACE_ELEVATOR["name"]}
DROP_EVENTS = []

# regions #########################################################################################
# Regions added to Jak 2's, by Jak 2 level: dict(id, like (a horizontal plane region to copy), y,
# tree, on_enter, on_exit).
EXTRA_REGIONS = {}
# Jak 2 region ids are unique over the whole game; ours are offset past the water regions
REGION_ID_OFFSET = 1000

# story state of the background ###################################################################
# Jak 2 shows or hides some background prototypes (TIE, shrub) depending on the story, in
# level-method-22 (engine/game/task/task-control.gc, prototypes-game-visible-set!), which also
# disables their collision. Kept here: the state before the event that changes them, the one most
# of the game shows. By Jak 2 level, the prototypes left out (the builder drops their collision
# too, tagged by the decompiler).
HIDDEN_PROTOTYPES = {
    # the palace plaza before Mar's tomb is found (canyon-insert-items-shard): the Baron's statue
    # stands on its wall, no rubble
    "ctypal": ["ctyp-statue-rubble-a.mb", "ctyp-statue-rubble-b.mb", "ctyp-statue-rubble-big-a.mb"],
    # the market roof before the tanker crashes into it (city-intercept-tanker)
    "ctymarkb": ["city-mark-roof-broken.mb"],
    # the Hip Hog's paintings before the nest boss (nest-boss-resolution)
    "hiphog": ["hip-paintings-bar-b.mb", "hip-paintings-wall-reflection-b.mb",
               "hip-paintings-wall-b.mb"],
    # Dead Town's tower still standing (ruins-tower)
    "ruins": ["ruins-board-task2.mb", "ruins-lgcollision-task2.mb", "ruins-plank-task2.mb",
              "ruins-smlcollision-task2.mb", "ruins-support-task2.mb", "ruin-tower-junk.mb"],
    # the construction site before the Baron's fight (consite-find-baron-resolution)
    "consite": ["consite-barrel-broken.mb", "consite-cor-sheet-8x16-hi-broken.mb",
                "consite-scaffold-assmb-24m-mid-broken.mb", "consite-scaffold-beam-4m-broken.mb",
                "consite-scaffold-beam-8m-broken.mb", "consite-scaffold-i-hook-broken.mb",
                "consite-scaffold-i-span-broken.mb", "consite-scaffold-t-connector-broken.mb",
                "consite-scaffold-x-connector-corner-broken.mb",
                "consite-scaffold-x-connector-corner-out-broken.mb",
                "consite-plank-double-broken.mb", "consite-plank-single-broken.mb",
                "consite-rope-14m-broken.mb", "consite-rope-8m-broken.mb",
                "consite-rope-ring-broken.mb", "consite-scaffold-x-connector-broken.mb"],
}

# continues #######################################################################################
# continue points of havenj2 (Jak 2 names). Every district's own continue, the mission starts
# (burning bushes, well spread over the streets) and the stadium's. havenj2-start (ctysluma-start)
# stays first: the Mods menu warp uses it.
CITY_CONTINUES = [
    "ctysluma-start", "ctysluma-alley", "ctyslumb-start", "ctyslumb-fort", "ctyslumc-start",
    "ctyslumc-slums", "ctyport-start", "ctyport-hiphog", "ctyport-gungame", "ctyport-warp",
    "ctyport-under", "ctyfarma-start", "ctyfarmb-start", "ctyinda-start", "ctyinda-vinroom",
    "ctyinda-consite", "ctyindb-start", "ctymarka-brutter", "ctymarkb-tanker", "ctypal-shaft",
    "ctypal-tomb", "ctygena-start", "ctygenb-start", "ctygenc-start",
    "ctysluma-burning-bush", "ctyslumb-burning-bush", "ctyslumb-burning-bush-2",
    "ctyslumc-burning-bush", "ctyport-burning-bush", "ctyport-burning-bush-3",
    "ctyfarma-burning-bush", "ctyfarmb-burning-bush", "ctyinda-burning-bush",
    "ctyindb-burning-bush", "ctymarka-burning-bush", "ctymarkb-burning-bush",
    "ctymarkb-burning-bush-2", "ctypal-burning-bush", "ctypal-burning-bush-2",
    "ctygena-burning-bush", "ctygena-burning-bush-2", "ctygenb-burning-bush",
    "ctygenb-burning-bush-2", "ctygenc-burning-bush", "ctygenc-burning-bush-2",
    "stadium-start", "stadium-burning-bush",
    # ours (EXTRA_CONTINUES)
    "cable-pillar",
]
# continues Jak 2 doesn't have, for the Mods menu's key places: in front of a door, facing it, by
# name: (Jak 2 level, the door, how far in front, in meters)
EXTRA_CONTINUES = {
    # the airlock of the palace's cable pillar, in the city's center
    "cable-pillar": ("ctygenb", "com-airlock-outer-15", 8.0),
}
# continues of the other places: all of Jak 2's for that level, but the cutscene and demo ones
SKIPPED_CONTINUE_FLAGS = {"demo", "demo-end", "warp-gate", "scene-wait", "title", "intro",
                          "change-continue"}
SKIPPED_CONTINUE_NAMES = ("movie", "demo")
# kept anyway: the destinations of the warp gates (the mountain's, the dig's to Vin's room) and of
# the port's air train
KEPT_CONTINUES = {"mountain-warp-top", "mountain-warp-bottom", "vinroom-warp", "caspad-warp"}
# a continue's level list, when Jak 2's doesn't suit
CONTINUE_WANTS = {
    # Jak 2's is for the sneak-in mission, with the city unloaded: here the lobby gate opens on it
    "palshaft-lobby": [("palshaft", "'display"), ("ctypal", "#f")],
}


def continue_name(jak2_name):
    return "havenj2-start" if jak2_name == "ctysluma-start" else f"hj2-{jak2_name}"


# Jak 2 data ######################################################################################


def load_actors():
    by_name = {}
    for path in glob.glob(f"{ENTITIES}/*-actors.json"):
        level = os.path.basename(path)[: -len("-actors.json")]
        for actor in jak2_actors.level_actors(level):
            by_name[(level, actor["lump"].get("name"))] = actor
    return by_name


def load_cameras():
    """Jak 2's fixed cameras (decompiler_out/jak2/entities/<level>-cameras.json, lumps typed for the
    builder) of the levels that are ported, by our level. Their ids are left to the builder."""
    out = {}
    for jak2_level, ours in sorted(LEVEL_MAP.items()):
        path = f"{ENTITIES}/{jak2_level}-cameras.json"
        if not os.path.exists(path):
            continue
        for cam in json.load(open(path)):
            out.setdefault(ours, []).append({
                "trans": [r4(x) for x in cam["trans"][:3]],
                "quat": [r4(x) for x in cam["quat"]],
                "lump": cam["lump"],
            })
    return out


def load_all_levels():
    """Every Jak 2 level name (a level-load-info's :name is alone on its line, unlike the level
    names in the continues' level lists)."""
    src = open(JAK2_LEVEL_INFO, encoding="utf-8").read()
    return set(re.findall(r"^\s*:name '([a-z0-9-]+)\s*$", src, re.M))


def parse_vector(block, key):
    m = re.search(r":" + key + r" \(new 'static 'vector([^)]*)\)", block)
    values = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 0.0}
    for k, v in re.findall(r":([xyzw]) (-?[0-9.e+-]+)", m.group(1)):
        values[k] = float(v)
    return [values["x"], values["y"], values["z"], values["w"]]


def load_continues():
    src = open(JAK2_LEVEL_INFO, encoding="utf-8").read()
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
            trans=parse_vector(head, "trans"),
            quat=parse_vector(head, "quat"),
            camera_trans=parse_vector(head, "camera-trans"),
            camera_rot=[float(x) for row in rot[:3] for x in row],
            flags=set(flags.group(1).split()) if flags else set(),
            wants=wants,
        )
    return result


def extra_continues(actors):
    """EXTRA_CONTINUES as Jak 2 continues (game units): Jak in front of the door, facing it, the
    camera behind him."""
    out = {}
    for name, (level, door_name, distance) in EXTRA_CONTINUES.items():
        door = actors[(level, door_name)]
        fx, _, fz = front(door)
        pos = [door["trans"][0] + fx * distance, door["trans"][1], door["trans"][2] + fz * distance]
        # facing the door: yaw of (-fx, -fz)
        yaw = math.atan2(-fx, -fz)
        quat = [0.0, math.sin(yaw / 2), 0.0, math.cos(yaw / 2)]
        cam = [pos[0] + fx * 8.0, pos[1] + 3.5, pos[2] + fz * 8.0]
        look = [pos[0] - cam[0], pos[1] + 1.5 - cam[1], pos[2] - cam[2]]
        n = math.sqrt(sum(c * c for c in look))
        f = [c / n for c in look]
        r = [f[2], 0.0, -f[0]]  # cross(y, f)
        n = math.sqrt(sum(c * c for c in r))
        r = [c / n for c in r]
        u = [f[1] * r[2] - f[2] * r[1], f[2] * r[0] - f[0] * r[2], f[0] * r[1] - f[1] * r[0]]
        out[name] = dict(
            level=level,
            trans=[c * METER for c in pos] + [1.0],
            quat=quat,
            camera_trans=[c * METER for c in cam] + [1.0],
            camera_rot=r + u + f,
            flags=set(),
            wants=[("ctywide", "'display"), (level, "'display")],
        )
    return out


def load_regions():
    src = open(JAK2_REGIONS, encoding="utf-8").read()
    regions = {}
    for m in re.finditer(
            r"INSERT INTO `region` \(`region_id`, `level_name`, `tree`, `on_enter`, `on_exit`, "
            r"`on_inside`\) values \((\d+), '([^']*)', '([^']*)', '((?:[^']|'')*)', "
            r"'((?:[^']|'')*)', '((?:[^']|'')*)'\);", src):
        rid, level, tree, on_enter, on_exit, on_inside = m.groups()
        regions[int(rid)] = dict(
            id=int(rid), level=level, tree=tree, faces={}, sphere=None,
            scripts={k: v.replace("''", "'") for k, v in (
                ("on-enter", on_enter), ("on-exit", on_exit), ("on-inside", on_inside)) if v})
    face_owner = {}
    num = r"(-?[\d.e+-]+)"
    for m in re.finditer(
            r"INSERT INTO `region_face` \([^)]*\) values \((\d+), (\d+), '([^']*)', '([^']*)', "
            + ", ".join([num] * 8) + r"\);", src):
        fid, rid = int(m.group(1)), int(m.group(2))
        regions[rid]["faces"][fid] = dict(kind=m.group(3),
                                          normal=[float(m.group(i)) for i in range(5, 9)],
                                          points=[])
        face_owner[fid] = rid
    for m in re.finditer(
            r"INSERT INTO `region_point` \(`region_face_id`, `idx`, `x`, `y`, `z`, `w`\) values "
            r"\((\d+), (\d+), " + ", ".join([num] * 4) + r"\);", src):
        fid = int(m.group(1))
        regions[face_owner[fid]]["faces"][fid]["points"].append(
            (int(m.group(2)), [float(m.group(i)) / METER for i in range(3, 6)]))
    for m in re.finditer(
            r"INSERT INTO `region_sphere` \(`region_id`, `x`, `y`, `z`, `r`\) values \((\d+), "
            + ", ".join([num] * 4) + r"\);", src):
        regions[int(m.group(1))]["sphere"] = [float(m.group(i)) / METER for i in range(2, 6)]
    for r in regions.values():
        for f in r["faces"].values():
            f["points"] = [p for _, p in sorted(f["points"])]
    return regions


# math ############################################################################################


def quat_rotate(q, v):
    """v rotated by the quaternion q (x y z w), like GOAL's quaternion->matrix."""
    qx, qy, qz, qw = q
    # t = 2 * cross(q.xyz, v); v' = v + w * t + cross(q.xyz, t)
    tx = 2 * (qy * v[2] - qz * v[1])
    ty = 2 * (qz * v[0] - qx * v[2])
    tz = 2 * (qx * v[1] - qy * v[0])
    return [
        v[0] + qw * tx + (qy * tz - qz * ty),
        v[1] + qw * ty + (qz * tx - qx * tz),
        v[2] + qw * tz + (qx * ty - qy * tx),
    ]


def front(actor):
    return quat_rotate(actor["quat"], [0.0, 0.0, 1.0])


def r4(x):
    return round(x, 4)


def bounding_sphere(points, pad=0.0):
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    center = [(lo[i] + hi[i]) / 2 for i in range(3)]
    radius = max(math.dist(center, p) for p in points)
    return [r4(c) for c in center] + [r4(radius + pad)]


# scripts #########################################################################################


class Context:
    def __init__(self, actors):
        self.actors = actors
        self.all_levels = load_all_levels() | set(LEVEL_MAP)
        self.continues = load_continues()
        self.continues.update(extra_continues(actors))
        self.continue_names = {}  # Jak 2 name -> ours, filled by the continue selection
        self.aid_to_name = {a["aid"]: name for (lev, name), a in actors.items() if "aid" in a}
        self.cameras = load_cameras()
        self.camera_names = {c["lump"]["name"] for cams in self.cameras.values() for c in cams}

    def translator(self, jak2_level, open_tasks=()):
        closed = lambda task: task not in OPEN_TASKS and task not in open_tasks  # noqa: E731
        return Translator(LEVEL_MAP, self.all_levels | BACKDROP_LEVELS, CITY, LEVEL_MAP[jak2_level],
                          closed, self.continue_names, RENAMES, DROP_EVENTS, self.camera_names)


def translate_notice(tr, text):
    """on-notice: the levels a door waits for. A level that isn't ported (but a backdrop) keeps the
    door shut: behind it there's nothing to walk on."""
    for sym in re.findall(r"'\(([^()]*)\)", text):
        for lev in sym.split():
            if lev in LEVEL_MAP or lev in BACKDROP_LEVELS:
                continue
            if lev in tr.all_levels:
                return None
    return tr.script(text, value=True)


def translate_lumps(ctx, jak2_level, name, lump):
    """The translated scripts of one of Jak 2's doors or elevators."""
    tr = ctx.translator(jak2_level)
    out = {}
    for key in sorted(k for k in lump if k.startswith("on-")):
        if key == "on-notice":
            text = translate_notice(tr, lump[key])
        else:
            text = tr.script(lump[key])
        if text:
            out[key] = text
    for key, text in SCRIPT_OVERRIDES.get((jak2_level, name), {}).items():
        if text is None:
            out.pop(key, None)
        else:
            out[key] = text
    return out


def script(text):
    return ["pair", text]


# actors ##########################################################################################


def next_actor(actor):
    """The actor id of a door's pair (Jak 2 stores it alone or as the first of four words)."""
    value = actor["lump"].get("next-actor")
    return value[0] if isinstance(value, list) else value


def base_lumps(actor):
    """Door settings from Jak 2 (res units)."""
    lump = {"name": actor["lump"]["name"]}
    for key in ("distance", "idle-distance", "height"):
        if key in actor["lump"]:
            value = actor["lump"][key]
            values = value if isinstance(value, list) else [value]
            lump[key] = ["float"] + [float(v) for v in values]
    if "options" in actor["lump"]:
        # bit 0: inner door (runs on-inside)
        lump["options"] = ["uint32", int(actor["lump"]["options"])]
    if "open-test" in actor["lump"]:
        lump["open-test"] = script(actor["lump"]["open-test"])
    return lump


def make_door(ctx, jak2_level, name, closed):
    actor = ctx.actors[(jak2_level, name)]
    etype = JAK3_ETYPE[actor["etype"]]
    lump = base_lumps(actor)
    scripts = {} if closed else translate_lumps(ctx, jak2_level, name, actor["lump"])
    if "on-notice" not in scripts:
        # never opens: nothing else to run either
        scripts = {}
        closed = True
    for key, text in scripts.items():
        lump[key] = script(text)
    pair = ctx.aid_to_name.get(next_actor(actor))
    if pair and not closed:
        lump["next-actor"] = ["string", pair]
    trans = [r4(x) for x in actor["trans"][:3]]
    return etype, closed, {
        "trans": trans,
        "etype": etype,
        "game_task": 0,
        "quat": [r4(x) for x in actor["quat"]],
        "bsphere": trans + [r4(actor["bsphere"][3])],
        "lump": lump,
    }


def elevator_actor(actor, path_points, name, scripts):
    """hj2-elevator from Jak 2's com-elevator, or hj2-cpad-elevator from its cpad-elevator (its
    model, so its origin), with its path (game units)."""
    src = actor["lump"]
    trans = [r4(x) for x in actor["trans"][:3]]
    path = ["vector"] + [[r4(c) for c in p[:3]] + [1.0] for p in path_points]
    lump = {
        "name": name,
        "path": path,
        "elevator-flags": ["uint32", ELEVATOR_FLAGS],
        "elevator-move-rate": ["float", float(src.get("elevator-move-rate", 25600.0))],
    }
    for key in ("elevator-xz-threshold", "elevator-y-threshold"):
        if key in src:
            lump[key] = ["float", float(src[key])]
    for key, text in scripts.items():
        lump[key] = script(text)
    return {
        "trans": trans,
        "etype": JAK3_ETYPE[actor["etype"]],
        "game_task": 0,
        "quat": [r4(x) for x in actor["quat"]],
        "bsphere": trans + [r4(actor["bsphere"][3])],
        "lump": lump,
    }


def make_elevator(ctx, jak2_level, name):
    actor = ctx.actors[(jak2_level, name)]
    scripts = translate_lumps(ctx, jak2_level, name, actor["lump"])
    # Jak 2's elevator on-notice meant "don't ride", Jak 3's elevator only runs it
    scripts.pop("on-notice", None)
    # its two ends: Jak 2's elevators ride from the first point to the last (the cpad-elevator's
    # points in between are on the way), Jak 3's stops at each point
    path = actor["lump"]["path"]
    return elevator_actor(actor, [path[0], path[-1]], name, scripts)


def make_palace_elevator(ctx):
    level = PALACE_ELEVATOR["level"]
    name = PALACE_ELEVATOR["name"]
    main = ctx.actors[(level, name)]
    # its ride cameras (camera-191 down, camera-192 up)
    scripts = translate_lumps(ctx, level, name, main["lump"])
    scripts.pop("on-notice", None)
    actor = elevator_actor(main, main["lump"]["path"], name, scripts)
    # called from both floors: close enough in xz
    actor["lump"]["elevator-xz-threshold"] = ["float", 20.0 * METER]
    actor["lump"]["elevator-y-threshold"] = ["float", 10.0 * METER]
    return actor


def make_place_actor(ctx, jak2_level, name):
    """One of PLACE_ACTORS: (comment, actor)."""
    actor = ctx.actors[(jak2_level, name)]
    src = actor["lump"]
    lump = {"name": name}
    if actor["etype"] == "warp-gate":
        # Jak 3's warp gate reads the same on-notice as Jak 2's: '("destination" on-activate
        # wait-for), the continue name translated, and the level names of the quoted script and
        # level list (the translator leaves quoted data as it is)
        etype = "warp-gate"
        notice = ctx.translator(jak2_level).script(src["on-notice"], value=True)
        if notice:
            notice = re.sub(r"(?<=[\s'(])([a-z0-9-]+)(?=[\s)])",
                            lambda m: LEVEL_MAP.get(m.group(1), m.group(1)), notice)
            lump["on-notice"] = script(notice)
        comment = f"Jak 2's {name} ({jak2_level})"
    else:
        etype = PLACE_ETYPE[actor["etype"]]
        comment = f"Jak 2's {name} ({jak2_level}) [as {etype}]"
    if actor["etype"] == "trans-plat":
        # its ride (game units), Jak 2's curve knots and speed
        lump["path"] = ["vector"] + [[r4(c) for c in p[:3]] + [1.0] for p in src["path"]]
        lump["path-k"] = ["float"] + [float(k) for k in src["path-k"]]
        lump["speed"] = ["float", float(src["speed"])]
    trans = [r4(x) for x in actor["trans"][:3]]
    return comment, {
        "trans": trans,
        "etype": etype,
        "game_task": 0,
        "quat": [r4(x) for x in actor["quat"]],
        "bsphere": trans + [r4(actor["bsphere"][3])],
        "lump": lump,
    }


def make_air_train(ctx, jak2_level, name, dest, scenes, anim, travel_name):
    """One of AIR_TRAINS: (comment, actor). Its on-notice is Jak 3's air train's: '("continue"
    on-activate wait-for on-close)."""
    actor = ctx.actors[(jak2_level, name)]
    dest_name = continue_name(dest)
    assert dest in ctx.continue_names, f"{name}: continue {dest} isn't ported"
    scene_list = " ".join(f'"{sc}"' for sc in scenes)
    lump = {
        "name": name,
        "on-notice": script(f"'(\"{dest_name}\" (scene-play '({scene_list})) #f "
                            f"(want-anim \"{anim}\"))"),
        # how close Jak must be to get on (Jak 2's)
        "distance": ["float", float(actor["lump"].get("distance", 20480.0))],
        # the prompt: Press <triangle> to travel to <travel-name>
        "travel-name": ["string", travel_name],
    }
    comment = f"Jak 2's {name} ({jak2_level}) [as hj2-air-train]: to {dest_name}"
    trans = [r4(x) for x in actor["trans"][:3]]
    return comment, {
        "trans": trans,
        "etype": "hj2-air-train",
        "game_task": 0,
        "quat": [r4(x) for x in actor["quat"]],
        "bsphere": trans + [r4(actor["bsphere"][3])],
        "lump": lump,
    }


def make_jak3_scene_stage(jak3_level, name):
    """(comment, actor): a Jak 3 scene-stage (a cutscene's origin), where Jak 3 has it."""
    with open(f"{JAK3_ENTITIES}/{jak3_level}-actors.json") as f:
        actor = next(a for a in json.load(f) if a["lump"].get("name") == name)
    trans = [r4(x) for x in actor["trans"][:3]]
    return f"Jak 3's {name} ({jak3_level}): the origin of its air train cutscenes", {
        "trans": trans,
        "etype": "scene-stage",
        "game_task": 0,
        "quat": [r4(x) for x in actor["quat"]],
        "bsphere": trans + [8.0],
        "lump": {"name": name},
    }


def make_actors(ctx, our_level):
    """The doors and elevators of one of our levels: (comment, actor) list and art groups."""
    out = []
    art = []

    def add(comment, actor):
        out.append((comment, actor))
        ag = ART_GROUP[actor["etype"]]
        if ag and ag not in art:
            art.append(ag)

    for jak2_level, name, closed in [(lv, nm, False) for lv, nm in DOORS] + [
            (lv, nm, True) for lv, nm in CLOSED]:
        if LEVEL_MAP[jak2_level] != our_level:
            continue
        etype_src = ctx.actors[(jak2_level, name)]["etype"]
        if etype_src in ELEVATOR_ETYPES:
            actor = make_elevator(ctx, jak2_level, name)
            add(f"Jak 2's {name} ({jak2_level}) [as {actor['etype']}]", actor)
            continue
        etype, is_closed, actor = make_door(ctx, jak2_level, name, closed)
        comment = f"Jak 2's {name} ({jak2_level})" + (", shut" if is_closed else "")
        if etype_src != etype:
            comment += f" [as {etype}]"
        add(comment, actor)
    if LEVEL_MAP[PALACE_ELEVATOR["level"]] == our_level:
        add("Jak 2's com-elevator-2 (palshaft): lobby <-> roof door", make_palace_elevator(ctx))
    for jak2_level, name in PLACE_ACTORS:
        if LEVEL_MAP[jak2_level] == our_level:
            add(*make_place_actor(ctx, jak2_level, name))
    for jak2_level, name, dest, scenes, anim, travel_name in AIR_TRAINS:
        if LEVEL_MAP[jak2_level] == our_level:
            add(*make_air_train(ctx, jak2_level, name, dest, scenes, anim, travel_name))
            art += [ag for ag in AIR_TRAIN_SCENE_ART if ag not in art]
    for jak3_level, name in AIR_TRAIN_SCENE_STAGES:
        if LEVEL_MAP[jak3_level] == our_level:
            add(*make_jak3_scene_stage(jak3_level, name))
    return out, art


def res_lump(kind, value):
    """A Jak 2 lump value (a number or list) as a builder res lump of that type."""
    if kind == "vector":
        vectors = value if isinstance(value[0], list) else [value]
        return ["vector"] + [[float(c) for c in v] for v in vectors]
    values = value if isinstance(value, list) else [value]
    return [kind] + [float(v) if kind == "float" else int(v) for v in values]


def ported_actors(ctx, place):
    """(comment, actor) list of Jak 2's platforms, props (PORTED_ACTORS) and crates of a place."""
    out = []
    for (level, name), actor in sorted(ctx.actors.items(), key=lambda kv: str(kv[0])):
        if level != place["jak2"]:
            continue
        src = actor["lump"]
        trans = [r4(x) for x in actor["trans"][:3]]
        if actor["etype"] == "crate" and level in CRATE_LEVELS:
            lump = {"name": name}
            if src.get("eco-info"):
                kind, amount = src["eco-info"][:2]
                lump["eco-info"] = ["int32", JAK2_PICKUP.get(int(kind), 0), int(amount)]
            etype = "crate"
        elif actor["etype"] in PORTED_ACTORS and level in PORTED_LEVELS:
            etype, kept = PORTED_ACTORS[actor["etype"]]
            lump = {"name": name}
            for key, kind in kept.items():
                if key in src:
                    lump[key] = res_lump(kind, src[key])
            if actor["etype"] == "mtn-plat-gap":
                trans = [r4(c / METER) for c in src["path"][0][:3]]
        else:
            continue
        out.append((f"Jak 2's {name} ({level})", {
            "trans": trans,
            "etype": etype,
            "game_task": 0,
            "quat": [r4(x) for x in actor["quat"]],
            "bsphere": trans + [r4(actor["bsphere"][3])],
            "lump": lump,
        }))
    return out


def custom_models(actor_list):
    """The models rebuilt from Jak 2's (ACTOR_MODELS) that these actors use, written for
    build-actor."""
    models = []
    for etype, (model, src, prims, collide) in ACTOR_MODELS.items():
        if model not in models and any(actor["etype"] == etype for _, actor in actor_list):
            verts, lo, hi = props_gen.write_actor_glb(src, model, prims, collide)
            print(f"  {model}: {verts} vertices, bounds {lo} - {hi}")
            models.append(model)
    if "hj2-dig-balloon-lurker" in models:
        model, src, anims = DIG_TRAPEZE_MODEL
        verts, lo, hi = props_gen.write_actor_glb(src, model, None, anims=anims)
        print(f"  {model}: {verts} vertices, bounds {lo} - {hi}")
        models.append(model)
    return models


def check_pairs(ctx):
    """Paired doors must face away from each other: on-cross runs when Jak goes from a door's
    front to its back."""
    for jak2_level, name in DOORS:
        actor = ctx.actors[(jak2_level, name)]
        pair = ctx.aid_to_name.get(next_actor(actor))
        if not pair:
            continue
        other = next(a for (lev, nm), a in ctx.actors.items() if nm == pair)
        to_other = [other["trans"][i] - actor["trans"][i] for i in range(3)]
        if sum(front(actor)[i] * to_other[i] for i in range(3)) > 0:
            print(f"note: {name} faces its pair {pair}")


# regions #########################################################################################


def region_json(region, rid, scripts):
    """One of Jak 2's regions in the builder's format (meters)."""
    out = {"id": rid}
    if region["sphere"]:
        out["shape"] = "sphere"
        out["bsphere"] = [r4(c) for c in region["sphere"]]
    else:
        faces = [
            {"normal": [round(c, 6) for c in f["normal"][:3]] + [round(f["normal"][3] / METER, 6)],
             "points": [[r4(c) for c in p] for p in f["points"]]}
            for f in region["faces"].values()
        ]
        points = [p for f in faces for p in f["points"]]
        out["bsphere"] = bounding_sphere(points, 0.5)
        if len(faces) == 1 and next(iter(region["faces"].values()))["kind"] == "plane":
            out["shape"] = "face"
            out["face"] = faces[0]
        else:
            out["shape"] = "volume"
            out["volume"] = {"faces": faces}
    out.update(scripts)
    return out


def shifted_region(region, y):
    """A copy of a horizontal plane region, moved to the height y (meters)."""
    face = next(iter(region["faces"].values()))
    points = [[p[0], y, p[2]] for p in face["points"]]
    normal = face["normal"][:3]
    w = sum(normal[i] * points[0][i] for i in range(3)) * METER
    return dict(region, sphere=None,
                faces={0: dict(kind=face["kind"], normal=normal + [w], points=points)})


def make_regions(ctx, regions, our_level):
    """Jak 2's target and camera regions of the levels merged into our_level, translated. Regions
    whose scripts are all gone are dropped."""
    trees = {}
    for region in sorted(regions.values(), key=lambda r: r["id"]):
        if region["tree"] not in ("target", "camera") or LEVEL_MAP.get(region["level"]) != our_level:
            continue
        tr = ctx.translator(region["level"], REGION_OPEN_TASKS.get(region["id"], ()))
        scripts = {}
        for key, text in region["scripts"].items():
            out = tr.script(text)
            if out:
                scripts[key] = out
        if scripts:
            trees.setdefault(region["tree"], []).append(
                region_json(region, region["id"] + REGION_ID_OFFSET, scripts))
    for jak2_level, extras in EXTRA_REGIONS.items():
        if LEVEL_MAP[jak2_level] != our_level:
            continue
        tr = ctx.translator(jak2_level)
        for extra in extras:
            region = shifted_region(regions[extra["like"]], extra["y"])
            scripts = {key: tr.script(extra[key.replace("-", "_")])
                       for key in ("on-enter", "on-exit") if extra.get(key.replace("-", "_"))}
            trees.setdefault(extra["tree"], []).append(region_json(region, extra["id"], scripts))
    out = {}
    for tree, items in trees.items():
        points = []
        for r in items:
            c, rad = r["bsphere"][:3], r["bsphere"][3]
            points += [[c[0] + dx * rad, c[1] + dy * rad, c[2] + dz * rad]
                       for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0),
                                          (0, 0, 1), (0, 0, -1))]
        out[tree] = {"bsphere": bounding_sphere(points, 1.0), "regions": items}
    return out


# water ###########################################################################################


def box_faces(lo, hi):
    """Outward faces of an axis-aligned box (the game's inside test only uses their planes)."""
    faces = []
    for axis in range(3):
        u, v = [i for i in range(3) if i != axis]
        for sign, value in ((1.0, hi[axis]), (-1.0, lo[axis])):
            normal = [0.0, 0.0, 0.0]
            normal[axis] = sign
            points = []
            for a in (lo[u], hi[u]):
                for b in (lo[v], hi[v]):
                    p = [0.0, 0.0, 0.0]
                    p[axis], p[u], p[v] = value, a, b
                    points.append(p)
            d = sum(normal[i] * points[0][i] for i in range(3))
            faces.append({"normal": [round(c, 6) for c in normal] + [round(d, 6)],
                          "points": [[round(c, 6) for c in p] for p in points]})
    return faces


def water_regions(place, actors, jak2_regions):
    """Jak 2's water-vol actors of a place as Jak 3 'water' regions (Jak 3's water is regions
    only). A water-vol is an axis-aligned box of 6 planes (outside where dot(p, n) > d) with its
    water height; the region goes from the box bottom to 2m above the water. A place with the
    ocean also gets Jak 2's ocean water regions (spheres: swimming at the ocean's height)."""
    regions = []
    if place.get("ocean"):
        for region in sorted(jak2_regions.values(), key=lambda r: r["id"]):
            if (region["level"] != place["jak2"] or region["tree"] != "water" or
                    not region["sphere"] or
                    not region["scripts"].get("on-inside", "").startswith("(water ocean")):
                continue
            sphere = [r4(x) for x in region["sphere"]]
            regions.append({
                "id": place["base_id"] + len(regions),
                "shape": "sphere",
                "trans": sphere[:3],
                "bsphere": sphere,
                "on-inside": "(water ocean 0.0 (swim wade))",
            })
    for (level, _), actor in sorted(actors.items(), key=lambda kv: str(kv[0])):
        if level != place["jak2"] or actor["etype"] != "water-vol" or "vol" not in actor["lump"]:
            continue
        lo = [-1e9] * 3
        hi = [1e9] * 3
        for plane in actor["lump"]["vol"]:
            axis = max(range(3), key=lambda i: abs(plane[i]))
            limit = plane[3] / plane[axis] / METER
            if plane[axis] > 0:
                hi[axis] = min(hi[axis], limit)
            else:
                lo[axis] = max(lo[axis], limit)
        height = actor["lump"]["water-height"][0] / METER
        hi[1] = max(hi[1], height + 2.0)
        center = [(lo[i] + hi[i]) / 2 for i in range(3)]
        radius = sum((hi[i] - center[i]) ** 2 for i in range(3)) ** 0.5
        regions.append({
            "id": place["base_id"] + len(regions),
            "shape": "volume",
            "bsphere": [r4(c) for c in center] + [r4(radius + 0.5)],
            "on-inside": f"(water height {height:.4f} (swim wade))",
            "volume": {"faces": box_faces(lo, hi)},
        })
    if not regions:
        return None
    points = [r["bsphere"][:3] for r in regions]
    radius = max(r["bsphere"][3] for r in regions)
    sphere = bounding_sphere(points, radius)
    return {"water": {"bsphere": sphere, "regions": regions}}


# palace gate #####################################################################################


def write_palace_door():
    """hj2-palace-door.glb for build-actor, from Jak 2's palace gate: its skeleton, textures and
    opening animation (renamed hj2-palace-door-idle, the name com-airlock looks up), with only the
    vertices it uses (the rip shares one buffer between its draws), plus a collision box around
    the sliding door. The box is invisible and bound to the door joint by build-actor; the gate
    mesh itself has no collision."""
    data = open(PALACE_DOOR_SRC, "rb").read()
    json_len = struct.unpack_from("<I", data, 12)[0]
    gltf = json.loads(data[20:20 + json_len])
    bin_start = 20 + json_len + 8
    bin_len = struct.unpack_from("<I", data, 20 + json_len)[0]
    blob = bytearray(data[bin_start:bin_start + bin_len])

    fmts = {5126: ("f", 4), 5125: ("I", 4), 5123: ("H", 2), 5121: ("B", 1)}
    sizes = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}

    def read(idx):
        acc = gltf["accessors"][idx]
        view = gltf["bufferViews"][acc["bufferView"]]
        fmt, size = fmts[acc["componentType"]]
        n = sizes[acc["type"]]
        stride = view.get("byteStride", size * n)
        base = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
        return [struct.unpack_from("<%d%s" % (n, fmt), blob, base + i * stride)
                for i in range(acc["count"])]

    views, accessors = [], []
    out_blob = bytearray()

    def add(values, fmt, gltf_type, component, minmax=False, target=34962):
        raw = b"".join(struct.pack("<" + fmt, *v) for v in values)
        views.append({"buffer": 0, "byteOffset": len(out_blob), "byteLength": len(raw),
                      **({"target": target} if target else {})})
        out_blob.extend(raw + b"\0" * ((4 - len(raw) % 4) % 4))
        acc = {"bufferView": len(views) - 1, "componentType": component, "count": len(values),
               "type": gltf_type}
        if minmax:
            acc["min"] = [min(v[i] for v in values) for i in range(len(values[0]))]
            acc["max"] = [max(v[i] for v in values) for i in range(len(values[0]))]
        accessors.append(acc)
        return len(accessors) - 1

    mesh = gltf["meshes"][0]
    attrs = mesh["primitives"][0]["attributes"]
    all_idx = [read(p["indices"]) for p in mesh["primitives"]]
    used = sorted({i[0] for idx in all_idx for i in idx})
    remap = {old: new for new, old in enumerate(used)}
    new_attrs = {}
    kinds = {"POSITION": ("3f", "VEC3", 5126), "NORMAL": ("3f", "VEC3", 5126),
             "TEXCOORD_0": ("2f", "VEC2", 5126), "COLOR_0": ("4f", "VEC4", 5126),
             "JOINTS_0": ("4B", "VEC4", 5121), "WEIGHTS_0": ("4f", "VEC4", 5126)}
    columns = {}
    for key, (fmt, typ, comp) in kinds.items():
        values = read(attrs[key])
        columns[key] = [values[i] for i in used]
        new_attrs[key] = add(columns[key], fmt, typ, comp, minmax=key == "POSITION")
    prims = []
    for prim, idx in zip(mesh["primitives"], all_idx):
        a_idx = add([(remap[i[0]],) for i in idx], "I", "SCALAR", 5125, target=34963)
        prims.append({"attributes": dict(new_attrs), "indices": a_idx,
                      "material": prim["material"], "mode": 4})

    # collision box: the vertices of the sliding door (joint "door"), as a slab around its plane
    joint_nodes = gltf["skins"][0]["joints"]
    door_joint = next(j for j, node in enumerate(joint_nodes) if gltf["nodes"][node]["name"] == "door")
    door_pts = [p for p, j, w in zip(columns["POSITION"], columns["JOINTS_0"], columns["WEIGHTS_0"])
                if j[max(range(4), key=lambda k: w[k])] == door_joint]
    lo = [min(p[i] for p in door_pts) for i in range(3)]
    hi = [max(p[i] for p in door_pts) for i in range(3)]
    corners = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    box_idx = [(i,) for a, b, c, d in quads for i in (a, b, c, a, c, d)]
    center = [(lo[i] + hi[i]) / 2 for i in range(3)]
    box_nrm = []
    for p in corners:
        d = [p[i] - center[i] for i in range(3)]
        n = math.sqrt(sum(c * c for c in d)) or 1.0
        box_nrm.append(tuple(c / n for c in d))
    box_mesh = {"name": "hj2-palace-door-collide", "primitives": [{
        "attributes": {"POSITION": add(corners, "3f", "VEC3", 5126, minmax=True),
                       "NORMAL": add(box_nrm, "3f", "VEC3", 5126),
                       "COLOR_0": add([(0.5, 0.5, 0.5, 1.0)] * 8, "4f", "VEC4", 5126)},
        "indices": add(box_idx, "I", "SCALAR", 5125, target=34963), "mode": 4}]}

    anims = []
    for anim in gltf.get("animations", []):
        samplers = []
        for s in anim["samplers"]:
            inp = read(s["input"])
            outp = read(s["output"])
            out_acc = gltf["accessors"][s["output"]]
            fmt = "%df" % sizes[out_acc["type"]]
            samplers.append({"input": add(inp, "f", "SCALAR", 5126, minmax=True, target=None),
                             "output": add(outp, fmt, out_acc["type"], 5126, target=None),
                             "interpolation": s.get("interpolation", "LINEAR")})
        anims.append({"name": "hj2-palace-door-idle", "channels": anim["channels"],
                      "samplers": samplers})

    skin = dict(gltf["skins"][0])
    if "inverseBindMatrices" in skin:
        mats = read(skin["inverseBindMatrices"])
        skin["inverseBindMatrices"] = add(mats, "16f", "MAT4", 5126, target=None)

    nodes = [dict(n) for n in gltf["nodes"]]
    mesh_node = next(i for i, n in enumerate(nodes) if "mesh" in n)
    nodes[mesh_node]["name"] = "hj2-palace-door-lod0"
    # no collision from the gate mesh (and its shared buffer is too big for a collide mesh)
    nodes[mesh_node]["extras"] = {"set_collision": 1, "ignore": 1}
    nodes.append({"name": "hj2-palace-door-collide", "mesh": 1, "extras": {"set_invisible": 1}})
    scene_nodes = list(gltf["scenes"][gltf.get("scene", 0)]["nodes"]) + [len(nodes) - 1]

    out = {
        "asset": {"version": "2.0", "generator": "gen_havenj2_links.py"},
        "scene": 0,
        "scenes": [{"nodes": scene_nodes}],
        "nodes": nodes,
        "meshes": [{"name": "hj2-palace-door-lod0", "primitives": prims}, box_mesh],
        "skins": [skin],
        "animations": anims,
        "materials": gltf["materials"],
        "textures": gltf["textures"],
        "samplers": gltf.get("samplers", []),
        "images": gltf["images"],
        "buffers": [{"byteLength": len(out_blob)}],
        "bufferViews": views,
        "accessors": accessors,
    }
    js = json.dumps(out, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(out_blob)
    os.makedirs(os.path.dirname(PALACE_DOOR_OUT), exist_ok=True)
    write_if_changed(PALACE_DOOR_OUT, struct.pack("<III", 0x46546C67, 2, total)
                     + struct.pack("<II", len(js), 0x4E4F534A) + js
                     + struct.pack("<II", len(out_blob), 0x004E4942) + bytes(out_blob))
    return len(used), [round(v, 2) for v in lo], [round(v, 2) for v in hi]


# continues #######################################################################################


def translate_wants(jak2_wants):
    """A continue's Jak 2 level list for our levels: the city levels are havenj2 (shown if one of
    them was), the levels that aren't ported are dropped."""
    out = {}
    for lev, disp in jak2_wants:
        ours = LEVEL_MAP.get(lev)
        if not ours:
            continue
        shown = disp == "'display"
        out[ours] = out.get(ours, False) or shown
    return [(lev, "'display" if shown else "#f") for lev, shown in out.items()]


def check_memory(levels):
    """Jak 3's level heap: 18 chunks, large = 12 (either end), small-edge = 6 at an end,
    small-center = the 6 in the middle."""
    modes = [MEMORY[lv] for lv in levels]
    large, center, edge = modes.count("large"), modes.count("small-center"), modes.count("small-edge")
    ok = large <= 1 and center <= 1 and edge <= 2 and not (large and center) and not (
        large and edge > 1)
    if not ok:
        raise ValueError(f"levels {levels} don't fit in the level heap together")


def select_continues(ctx):
    """(our level, continue name, Jak 2 continue) for every continue point to write."""
    chosen = []
    for jak2_name in CITY_CONTINUES:
        chosen.append((CITY, continue_name(jak2_name), jak2_name))
    for place in PLACES:
        for jak2_name, cont in ctx.continues.items():
            if cont["level"] != place["jak2"]:
                continue
            if jak2_name not in CONTINUE_WANTS and jak2_name not in KEPT_CONTINUES and (
                    cont["flags"] & SKIPPED_CONTINUE_FLAGS or
                    any(word in jak2_name for word in SKIPPED_CONTINUE_NAMES)):
                continue
            chosen.append((place["name"], continue_name(jak2_name), jak2_name))
    for _, ours, jak2_name in chosen:
        ctx.continue_names[jak2_name] = ours
    return chosen


def int16(x):
    return max(-32768, min(32767, int(round(x * 32767))))


def continue_point(ctx, level, cont_name, jak2_name):
    jak2 = ctx.continues[jak2_name]
    wants = translate_wants(CONTINUE_WANTS.get(jak2_name, jak2["wants"]))
    if not any(lev == level for lev, _ in wants):
        wants.insert(0, (level, "'display"))
    check_memory([lev for lev, _ in wants])
    t = jak2["trans"]
    c = jak2["camera_trans"]
    q = jak2["quat"]
    rot = " ".join(str(int16(x)) for x in jak2["camera_rot"])
    want_lines = "\n".join(
        f"          (new 'static 'level-buffer-state-small :name '{name} :display? {disp})"
        for name, disp in wants
    )
    # no-auto: Jak 3 never picks it by itself (Jak 2's special spots)
    flags = [f for f in ("no-auto",) if f in jak2["flags"]]
    flags_line = f"        :flags (continue-flags {' '.join(flags)})\n" if flags else ""
    return f"""      (new 'static 'continue-point
        :name "{cont_name}"
        :level '{level}
        :trans (static-vectorm {t[0] / METER:.4f} {t[1] / METER:.4f} {t[2] / METER:.4f})
        :camera-trans (static-vectorm {c[0] / METER:.4f} {c[1] / METER:.4f} {c[2] / METER:.4f})
        :quat (new 'static 'vector4h :data (new 'static 'array int16 4 {int16(q[0])} {int16(q[1])} {int16(q[2])} {int16(q[3])}))
        :camera-rot (new 'static 'array int16 9 {rot})
{flags_line}        :on-goto #f
        :vis-nick '{level}
        :vehicle-type #x1b
        :want-count {len(wants)}
        :want (new 'static 'inline-array level-buffer-state-small {len(wants)}
{want_lines}
          )
        :want-sound (new 'static 'array symbol 3 #f #f #f)
        )"""


# outputs #########################################################################################


GENERATED_BEGIN = "  // BEGIN GENERATED by gen_havenj2_links.py: doors and elevators, edit the script"
GENERATED_END = "  // END GENERATED by gen_havenj2_links.py"
GENERATED_HEADER = "GENERATED by custom_assets/jak3/levels/havenj2/gen_havenj2_links.py, edit the script."


def actors_json(actor_list, indent):
    pad = " " * indent
    lines = []
    for i, (comment, actor) in enumerate(actor_list):
        lines.append(f"{pad}// {comment}")
        text = json.dumps(actor, separators=(", ", ": "))
        lines.append(pad + text + ("," if i + 1 < len(actor_list) else ""))
    return "\n".join(lines)


def write_regions(folder, name, trees):
    path = f"{folder}/{name}-regions.json"
    write_if_changed(path, json.dumps(trees, indent=2))
    return path


def hidden_prototypes(jak2_levels):
    out = []
    for lev in jak2_levels:
        out += [p for p in HIDDEN_PROTOTYPES.get(lev, []) if p not in out]
    return out


def cameras_json(cameras, indent):
    pad = " " * indent
    return ",\n".join(pad + json.dumps(c, separators=(", ", ": ")) for c in cameras)


def traffic_code():
    """The object files of havenj2's traffic, in link order (see TRAFFIC_CODE_DGO)."""
    objs = re.findall(r'"([^"]+)\.o"', open(TRAFFIC_CODE_DGO).read())
    code = [TRAFFIC_CODE_REPLACED.get(o, o) for o in objs
            if o not in TRAFFIC_CODE_SKIPPED or o in TRAFFIC_CODE_REPLACED]
    return [f"{o}.o" for o in code] + ["havenj2-traffic.o"]


def write_havenj2(ctx, regions):
    actor_list, art = make_actors(ctx, CITY)
    # the props that are actors (market, farms), with Jak 3's classes and models
    props, prop_art, prop_code, prop_counts = props_gen.city_prop_actors(CITY_LEVELS)
    actor_list += props
    art += [ag for ag in prop_art if ag not in art]
    # the traffic's citizens, guards and vehicles (havenj2-traffic.gc)
    art += [ag for ag in TRAFFIC_ART if ag not in art]
    code = [obj for obj in traffic_code() if obj not in prop_code] + prop_code
    # Jak 2's particle effects (signs, lights, smoke...): part spawners and animated neon signs,
    # with havenj2-part.gc and the sprite textures of havenj2's own texture page
    part_actors, sprite_textures, part_stats = particles_gen.write(CITY_LEVELS)
    actor_list += part_actors
    # props with a model rebuilt from Jak 2's (the propaganda speakers)
    custom_props, custom_models = props_gen.city_custom_prop_actors(CITY_LEVELS)
    actor_list += custom_props
    models = CITY_CUSTOM_MODELS + [m for m in custom_models if m not in CITY_CUSTOM_MODELS]
    import_fr3 = {
        "game": "jak2",
        "levels": CITY_LEVELS,
        "tfrag": True,
        "tie": True,
        "shrub": True,
        "collision": True,
        # [xmin, ymin, zmin, xmax, ymax, zmax] in meters: the playable collision with a margin, up
        # to the top of the palace pillars. Drops ctywide's backdrop mountains (x < -3000m, up to
        # 1500m high), unreachable, that would otherwise blow the collide hash grid up.
        "collision_bounds": [-700, -200, -1000, 1400, 470, 2150],
        "hide_prototypes": hidden_prototypes(CITY_LEVELS),
    }
    section = [
        GENERATED_BEGIN,
        "  // the whole background (tfrag/tie/shrub render trees + collision with its original pat),",
        "  // merged from Jak 2's extracted .fr3 files (out/jak2/fr3/<level>.fr3). The palace pillars",
        "  // (palshaft) are a level of their own, hj2-pshaft, like in Jak 2.",
        '  "import_fr3": ' + json.dumps(import_fr3) + ",",
        "  // Jak 2's city navigation: its nav meshes and its districts' traffic data merged into one",
        "  // city-level-info (gen_havenj2_nav.py)",
        f'  "nav_data": "{NAV_DATA}",',
        "  // the sprite textures of Jak 2's city particles, as texture page "
        f"{sprite_textures['page']} (havenj2-part.gc)",
        '  "sprite_textures": ' + json.dumps(sprite_textures) + ",",
        '  "cameras": [',
        cameras_json(ctx.cameras.get(CITY, []), 4),
        "  ],",
        '  "custom_models": ' + json.dumps(models) + ",",
        "  // Jak 3's models of the doors, props and traffic, extracted from Jak 3's DGOs",
        '  "art_groups": ' + json.dumps(art) + ",",
        '  "actors": [',
        actors_json(actor_list, 4),
        "  ]",
        GENERATED_END,
    ]
    text = open(HAVENJ2_JSONC, encoding="utf-8").read()
    begin = text.index(GENERATED_BEGIN)
    end = text.index(GENERATED_END) + len(GENERATED_END)
    text = text[:begin] + "\n".join(section) + text[end:]
    write_if_changed(HAVENJ2_JSONC, text)

    trees = make_regions(ctx, regions, CITY)
    write_regions(f"{LEVELS_DIR}/havenj2", "havenj2", trees)

    gd = [
        f";; {GENERATED_HEADER}",
        ";; DGO definition file for havenj2: Jak 2's Haven City as a Jak 3 custom level.",
        ";; the actual file name still needs to be 8.3",
        '("HJ2.DGO"',
        " (",
    ]
    gd += [f'  "{ag}.go"' for ag in art]
    gd += [f'  "{m}-ag.go"' for m in models]
    # the traffic code (TRAFFIC_CODE_DGO), then the props' (Jak 3's market and farms)
    gd += [f'  "{obj}"' for obj in code]
    # the ocean map (havenj2-ocean.o) is in GAME: the pumping station and the forest use it too
    gd += ['  "havenj2-part.o"', '  "havenj2-signs.o"', '  "havenj2-obs.o"', '  "havenj2.go"', "  ))",
           ""]
    print("  props as actors: " + ", ".join(f"{n} {e}" for e, n in sorted(prop_counts.items())))
    print(f"  particles: {part_stats}")
    write_if_changed(f"{LEVELS_DIR}/havenj2/havenj2.gd", "\n".join(gd))
    return len(actor_list), sum(len(t["regions"]) for t in trees.values())


def write_place(ctx, place, regions):
    actor_list, art = make_actors(ctx, place["name"])
    actor_list += ported_actors(ctx, place)
    models = custom_models(actor_list)
    folder = f"{LEVELS_DIR}/{place['name']}"
    os.makedirs(folder, exist_ok=True)
    import_fr3 = {
        "game": "jak2",
        "levels": [place["jak2"]],
        "tfrag": True,
        "tie": True,
        "shrub": True,
        "collision": True,
    }
    if "collision_bounds" in place:
        import_fr3["collision_bounds"] = place["collision_bounds"]
    hidden = hidden_prototypes([place["jak2"]])
    if hidden:
        import_fr3["hide_prototypes"] = hidden
    region_files = []
    trees = make_regions(ctx, regions, place["name"])
    if trees:
        region_files.append(write_regions(folder, place["name"], trees))
    water = water_regions(place, ctx.actors, regions)
    if water:
        path = f"{folder}/{place['name']}-water-regions.json"
        write_if_changed(path, json.dumps(water, indent=2))
        region_files.append(path)
    region_lines = []
    if region_files:
        region_lines = [
            "  // Jak 2's load regions of this place (translated), and its water volumes (water-vol)",
            '  "region_tree_files": ' + json.dumps(region_files) + ",",
        ]
    what = place["what"][0].upper() + place["what"][1:]
    lines = [
        "{",
        f"  // {GENERATED_HEADER}",
        f"  // {what}, reached from havenj2 (Jak 2's Haven City),",
        f"  // imported from Jak 2's extracted {place['jak2']}.",
        f'  "long_name": "{place["name"]}",',
        f'  "iso_name": "{place["iso"]}",',
        f'  "nickname": "{place["nick"]}",',
        '  "import_fr3": ' + json.dumps(import_fr3) + ",",
        *region_lines,
        f'  "base_id": {place["base_id"]},',
        f'  "base_region_id": {place["base_id"]},',
        "  // Jak 2's fixed cameras of this place (elevator rides, camera regions)",
        '  "cameras": [',
        cameras_json(ctx.cameras.get(place["name"], []), 4),
        "  ],",
        *(["  // models of its custom actors, built by build-actor (goal_src/jak3/game.gp)",
           '  "custom_models": ' + json.dumps(models) + ","] if models else []),
        '  "art_groups": ' + json.dumps(art) + ",",
        '  "actors": [',
        actors_json(actor_list, 4),
        "  ]",
        "}",
        "",
    ]
    write_if_changed(f"{folder}/{place['name']}.jsonc", "\n".join(lines))
    gd = [
        f";; {GENERATED_HEADER}",
        f";; DGO definition file for {place['name']}: {place['what']}.",
        f'("{place["nick"].upper()}.DGO"',
        " (",
    ]
    gd += [f'  "{ag}.go"' for ag in art]
    gd += [f'  "{m}-ag.go"' for m in models]
    gd += [f'  "{obj}"' for obj in place.get("code", [])]
    gd += [f'  "{place["name"]}.go"', "  ))", ""]
    write_if_changed(f"{folder}/{place['name']}.gd", "\n".join(gd))
    return len(actor_list), sum(len(t["regions"]) for t in trees.values())


def level_info(name, nick, index, memory_mode, flags, mood, continues, callbacks, ocean, comment,
               draw_priority, outdoor, part_engine_max=0):
    flags_line = f"    :level-flags (level-flags {flags})\n" if flags else ""
    if outdoor:
        # Jak 2's weather for its outdoor levels: clouds and fog anywhere in 0..1, rain when both
        # are high (see hj2-apply-weather in jak2-haven-city-world.gc)
        weather = ("    :max-rain 1.0\n"
                   "    :mood-range (new 'static 'mood-range :max-cloud 1.0 :max-fog 1.0)\n")
    else:
        weather = "    :max-rain 0.0\n    :mood-range (new 'static 'mood-range)\n"
    ocean_value = f"'{ocean}" if ocean else "#f"
    callback_list = (
        "'(" + " ".join(f"({slot} . {fn})" for slot, fn in callbacks) + ")" if callbacks else "'()"
    )
    return f"""{comment}
(define {name}
  (new 'static 'level-load-info
    :name '{name}
    :visname '{name}-vis
    :nickname '{nick}
    :dbname '{name}
    :taskname 'default
    :index #x{index:x}
    :master-level #f
{flags_line}    :packages '()
    :run-packages '("common")
    :memory-mode (level-memory-mode {memory_mode})
    :music-bank #f
    :extra-sound-bank #f
    :mood-func '{mood}
    :special-mood #f
    :ocean {ocean_value}
    :ocean-alpha 1.0
    :priority 100
    :draw-priority {draw_priority}
    :part-engine-max {part_engine_max}
    :base-task-mask (task-mask task0)
    :bigmap-id (bigmap-id none)
    :continues '(
{chr(10).join(continues)}
      )
    :callback-list {callback_list}
    :borrow #f
    :bottom-height (meters -100)
    :fog-height (meters 80)
{weather}    :fog-mult 1.0
    )
  )

(cons! *level-load-list* '{name})
"""


def write_level_info(ctx, chosen):
    out = [
        ";;-*-Lisp-*-",
        "(in-package goal)",
        "",
        ";; name: jak2-haven-city-levels.gc",
        ";; name in dgo: jak2-haven-city-levels",
        ";; dgos: GAME",
        "",
        f";; og:jak2-haven-city {GENERATED_HEADER}",
        ";; The level-load-info of havenj2 (Jak 2's Haven City) and of the places reached from it,",
        ";; with their continue points taken from Jak 2's. They're in GAME so the continues are known",
        ";; at boot (warps, saves). Moods and callbacks: jak2-haven-city-world.gc.",
        "",
        ";; every level of this mod (the clock stays as set while one of them is active)",
        "(define *havenj2-levels* '(" + " ".join([CITY] + [p["name"] for p in PLACES]) + "))",
        "",
    ]
    city = [continue_point(ctx, lv, name, j2) for lv, name, j2 in chosen if lv == CITY]
    out.append(level_info(
        CITY, "hj2", 0x129, "large", "sky ocean-near-translucent", "update-mood-havenj2", city,
        [(33, "havenj2-login"), (34, "havenj2-logout"), (35, "havenj2-activate"),
         (36, "havenj2-deactivate")], "*ocean-map-havenj2*",
        ";; Jak 2's whole Haven City as one custom level (custom_assets/jak3/levels/havenj2). Kept at\n"
        ";; Jak 2's world coordinates, so it must never be loaded together with Jak 3's own city levels.\n"
        ";; sky: the sky is only drawn when an active level has this flag.\n"
        ";; part-engine-max: the static particles of Jak 2's lights (x16, see part-spawner).\n"
        ";; login/logout: the traffic engine, in havenj2's own code (havenj2-traffic.gc).",
        "9.0", True, 255))
    for place in PLACES:
        conts = [continue_point(ctx, lv, name, j2) for lv, name, j2 in chosen
                 if lv == place["name"]]
        what = place["what"][0].upper() + place["what"][1:]
        memory = MEMORY[place["name"]]
        flags = " ".join(["sky"] * place["sky"] +
                         ["ocean-near-translucent"] * bool(place.get("ocean")))
        out.append(level_info(
            place["name"], place["nick"], place["index"], memory,
            flags or None, f"update-mood-{place['name']}", conts,
            [(35, "hj2-place-activate"), (36, "hj2-place-deactivate")],
            "*ocean-map-havenj2*" if place.get("ocean") else None,
            f";; {what} (custom_assets/jak3/levels/{place['name']}), Jak 2's {place['jak2']}.\n"
            f";; memory: {memory} (see PLACES in gen_havenj2_links.py).",
            "10.0", place["sky"]))
    write_if_changed(LEVEL_INFO_OUT, "\n".join(out))


def main():
    actors = load_actors()
    ctx = Context(actors)
    regions = load_regions()
    chosen = select_continues(ctx)
    check_pairs(ctx)
    nav_gen.main()
    verts, lo, hi = write_palace_door()
    print(f"palace gate: {verts} vertices, collision box {lo} - {hi}")
    count, nreg = write_havenj2(ctx, regions)
    print(f"havenj2: {count} actors, {nreg} regions")
    for place in PLACES:
        count, nreg = write_place(ctx, place, regions)
        print(f"{place['name']}: {count} actors, {nreg} regions ({place['jak2']})")
    write_level_info(ctx, chosen)
    print(f"wrote {LEVEL_INFO_OUT} ({len(chosen)} continues)")


if __name__ == "__main__":
    main()
