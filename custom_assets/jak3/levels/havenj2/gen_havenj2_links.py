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
#   memory: the level-memory-mode, Jak 2's by default (see memory_modes)
#   merge:  more Jak 2 levels merged into this one (their background, actors and regions)
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
    # Dead Town, with the Sage's hut at its far end: Jak 2's continues load the hut with Dead Town
    # (shown 'special: drawn, not a level Jak is in), so they're one level here. Its sea is Jak 2's
    # own ocean map (hj2-ruins-ocean.gc), its beams Jak 2's (hj2-ruins-obs.gc)
    dict(name="hj2-ruins", nick="hjr", iso="HJ2RUINS", index=0x131, base_id=22200,
         jak2="ruins", merge=["sagehut"], what="Dead Town and the Sage's hut, through the slums airlock",
         sky=True, ocean="*ocean-map-hj2-ruins*", code=["hj2-ruins-ocean.o", "hj2-ruins-obs.o"]),
    dict(name="hj2-consb", nick="hjb", iso="HJ2CONSB", index=0x133, base_id=22300,
         jak2="consiteb", what="the tunnel to the construction site, from the industrial section",
         sky=True),
    dict(name="hj2-cons", nick="hjc", iso="HJ2CONS", index=0x134, base_id=22400,
         jak2="consite", what="the construction site", sky=True, code=["hj2-cons-obs.o"]),
    dict(name="hj2-pshaft", nick="hjs", iso="HJ2PSHFT", index=0x135, base_id=22500,
         jak2="palshaft", what="the palace pillars: the palace lobby and the cable pillar",
         sky=True),
    dict(name="hj2-proof", nick="hjp", iso="HJ2PROOF", index=0x136, base_id=22600,
         jak2="palroof", what="the palace roof", sky=True, ocean=True),
    # palcab's backdrop (the city seen from above) spreads over kilometers, collision included: keep
    # the collision of the palace top, the pillar tops and the cable between them, else the collide
    # hash grid alone makes a 67MB level
    dict(name="hj2-pcab", nick="hjq", iso="HJ2PCAB", index=0x137, base_id=22700,
         jak2="palcab", what="the palace cable, between the pillar tops", sky=True, ocean=True,
         collision_bounds=[0, 200, -250, 400, 620, 800]),
    # the pumping station: the slums airlock opens on atollext (the way to it, loaded next to the
    # city), whose far airlock leads to atoll (the station itself, loaded without the city).
    #   ocean: Jak 2's :ocean: True for the city's ocean map (havenj2-ocean.gc in GAME), else the
    #          name of the level's own (written by gen_havenj2_ocean.py, in the level's code)
    dict(name="hj2-atollx", nick="hja", iso="HJ2ATOLX", index=0x138, base_id=22800,
         jak2="atollext", what="the way to the pumping station, from the slums airlock", sky=True),
    # like palcab, the collision of their backdrops spreads over kilometers: keep the playable area
    dict(name="hj2-atoll", nick="hjl", iso="HJ2ATOLL", index=0x139, base_id=22900,
         jak2="atoll", what="the pumping station", sky=True, ocean=True,
         code=["hj2-atoll-obs.o"], collision_bounds=[120, -80, -1420, 900, 250, -660]),
    # Haven Forest: the gardens airlock opens on the foot of the mountain (mountain), whose warp gate
    # leads to its top (mountain again, with the temple outside, mtnext, as a backdrop); there
    # Jak 2's trans-plat rides down to Haven Forest (forest, then forestb at its far end).
    dict(name="hj2-mount", nick="hjm", iso="HJ2MOUNT", index=0x13A, base_id=23000,
         jak2="mountain", what="the mountain, from the gardens airlock to the way to Haven Forest",
         sky=True, ocean="*ocean-map-hj2-mount*", code=["hj2-mount-ocean.o", "hj2-mount-obs.o"],
         collision_bounds=[-1050, -60, -200, -330, 340, 620]),
    dict(name="hj2-mtnx", nick="hjx", iso="HJ2MTNX", index=0x13B, base_id=23100,
         jak2="mtnext", what="the outside of the mountain temple, seen from the mountain top",
         sky=True),
    dict(name="hj2-forest", nick="hjf", iso="HJ2FORST", index=0x13C, base_id=23200,
         jak2="forest", what="Haven Forest", sky=True, ocean=True),
    dict(name="hj2-forstb", nick="hjn", iso="HJ2FORSB", index=0x13D, base_id=23300,
         jak2="forestb", what="the far end of Haven Forest", sky=True, ocean=True),
    # the dig: the castle pad (caspad), reached by the port's air train (AIR_TRAINS) or on foot from
    # the pumping station, whose elevator goes down to the dig (dig3a, loaded without the city,
    # then dig3b, its far end). Jak 2 ends the dig with the warp gate to Vin's room.
    dict(name="hj2-caspad", nick="hjy", iso="HJ2CASPD", index=0x13E, base_id=23400,
         jak2="caspad", what="the castle pad, above the dig", sky=True),
    dict(name="hj2-dig", nick="hjt", iso="HJ2DIG", index=0x13F, base_id=23500,
         jak2="dig3a", what="the dig", sky=False,
         code=["rigid-body-plat.o", "hj2-dig-obs.o"]),
    dict(name="hj2-digb", nick="hju", iso="HJ2DIGB", index=0x140, base_id=23600,
         jak2="dig3b", what="the far end of the dig", sky=False),
    # the fortress: its gate in the slums opens on forresca (the way of Jak 2's rescue of his
    # friends, loaded next to the city), whose far end loads forrescb without the city
    dict(name="hj2-forta", nick="hji", iso="HJ2FORRA", index=0x142, base_id=23800,
         jak2="forresca", what="the fortress, behind its gate in the slums", sky=False),
    dict(name="hj2-fortb", nick="hjj", iso="HJ2FORRB", index=0x143, base_id=23900,
         jak2="forrescb", what="the far end of the fortress", sky=False),
    # the fortress's far gate opens on the prison (its cells, torture machine, warp gate), whose
    # tunnels lead to Jak 2's way out of the fortress: forexita (its lifts), then forexitb (the pool
    # under the broken trap doors, the slide), whose gate opens on the slums. Jak 2's escape from
    # the fortress, open at the end of the game. Actor ids: 1000 per place (the prison's particles
    # alone are 382 part spawners).
    dict(name="hj2-prison", nick="hke", iso="HJ2PRISN", index=0x145, base_id=50000,
         jak2="prison", what="the fortress prison, behind the far gate of the fortress", sky=False,
         code=["hj2-prison-obs.o"]),
    dict(name="hj2-fexa", nick="hkf", iso="HJ2FEXA", index=0x146, base_id=51000,
         jak2="forexita", what="the way out of the fortress, from the prison", sky=False,
         code=["hj2-fexa-obs.o"]),
    dict(name="hj2-fexb", nick="hkg", iso="HJ2FEXB", index=0x147, base_id=52000,
         jak2="forexitb", what="the end of the way out of the fortress, with its gate to the slums",
         sky=False, code=["hj2-fexb-obs.o"]),
    # the stadium's race track (the class 1 race's, the one Jak 2 loads at the end of the game),
    # loaded with the city when Jak comes near the stadium
    dict(name="hj2-stadd", nick="hjz", iso="HJ2STADD", index=0x144, base_id=24000,
         jak2="stadiumd", what="the stadium's race track, behind the stadium grounds", sky=True),
    # Not ported: the inside of the palace (palent, throne), only reached in Jak 2's missions.
]
PLACE_BY_NAME = {p["name"]: p for p in PLACES}


def place_levels(place):
    """The Jak 2 levels of a place: its own, then the ones merged into it."""
    return [place["jak2"]] + place.get("merge", [])


LEVEL_MAP = {lev: CITY for lev in CITY_LEVELS}
LEVEL_MAP.update({lev: p["name"] for p in PLACES for lev in place_levels(p)})
# our level -> its level-memory-mode: the city's, the places' are set by memory_modes
MEMORY = {CITY: "large"}
# part-engine-max of the places with particles (write_place): their static part spawners
PART_ENGINE_MAX = {}
# Jak 2 levels that are only a backdrop: a door waiting for them to be loaded doesn't need them
BACKDROP_LEVELS = {"palout"}

# The story state the scripts are evaluated in, the one the actors are placed in too
# (jak2_actors.py): the end of the game, except for the palace, which is kept open (Jak 2 closes its
# doors once the sneak-in mission is over).
OPEN_TASKS = jak2_actors.OPEN_TASKS
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
    # Keira's garage: no doors, its doorways are open (region 319 loads and shows it)
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
    # the fortress: its gate in the slums, the same gate from inside, and the gates between its two
    # parts
    ("ctysluma", "fort-entry-gate-17"), ("forresca", "fort-entry-gate-7"),
    ("forrescb", "fort-entry-gate-8"), ("forrescb", "fort-entry-gate-9"),
    # the prison: the fortress's far gate and its other side; the way out of the fortress: its gate
    # and the slums' gate it opens on
    ("forrescb", "fort-entry-gate-11"), ("prison", "fort-entry-gate-20"),
    ("forexitb", "fort-entry-gate-5"), ("ctyslumb", "fort-entry-gate-19"),
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
SCRIPT_OVERRIDES = {
    # The outer doors of the roof and of the cable hide the pillar (want-display hj2-pshaft #f) when
    # they close. A door is born closed when its level loads, and runs that script if Jak is in
    # front of it, however far: riding the cable pillar's elevator up loads the roof, whose door
    # (570m away) then turned off hj2-pshaft, the elevator Jak stood on and the shaft around him.
    # The pillar stays shown (it's loaded with the roof and the cable anyway).
    ("palroof", "com-airlock-outer-18"): {"on-deactivate": None},
    ("palcab", "com-airlock-outer-17"): {"on-deactivate": None},
}
# a door's pair (next-actor), when Jak 2's isn't placed: by (Jak 2 level, name)
NEXT_ACTOR_OVERRIDES = {
    # Jak 2 pairs the slums' fortress gate with the dump's (fordumpa, not ported); the rescue's gate
    # (forresca) is its other side at the end of the game
    ("ctysluma", "fort-entry-gate-17"): "fort-entry-gate-7",
}
# region script changes, by Jak 2 region id: script -> replacement (translated)
REGION_SCRIPT_OVERRIDES = {
    # Keira's garage has no doors (their on-enter showed it): the region that loads it shows it
    319: {"on-enter": "(begin (want-load 'havenj2 'hj2-garage) (want-display 'hj2-garage 'display))"},
}

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
    # Jak 2's fortress gate, rebuilt from its model (ACTOR_MODELS), class in GAME
    "fort-entry-gate": "hj2-fort-gate",
    # Jak 3 has no com-elevator: hj2-elevator is Jak 3's elevator with Jak 2's model (ACTOR_MODELS)
    "com-elevator": "hj2-elevator",
    "cpad-elevator": "hj2-cpad-elevator",
}
# Jak 2's elevators among the DOORS (see make_elevator)
ELEVATOR_ETYPES = {"com-elevator", "cpad-elevator"}
# models of havenj2's custom actors, built by build-actor (goal_src/jak3/game.gp), added to its fr3
# (the other ones, like the fortress gate's, come with their actors: ACTOR_MODELS)
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
    "hj2-time-gate": "warp-gate-ag",
    "swingpole": None,
    # built by build-actor (goal_src/jak3/game.gp), not extracted from Jak 3
    "hj2-palace-door": None,
    "hj2-elevator": None,
    "hj2-cpad-elevator": None,
    "hj2-trans-plat": None,
    "hj2-iris-door": None,
    "hj2-mtn-elevator": None,
    "hj2-fort-gate": None,
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
# GAME: jak2-haven-city-world.gc). Riding one is a teleport, a short fade to the continue next to the
# other air train. Its on-notice is Jak 3's: '("continue" #f #f). Jak 2 hides the port's once the game
# is over: here both always run. By Jak 2 level and name: (Jak 2 continue, the place named by the
# prompt).
AIR_TRAINS = [
    # to the dig: the castle pad above it
    ("ctyport", "air-train-1", "caspad-warp", "the Dig Site"),
    # back to the port
    ("caspad", "air-train-3", "ctyport-warp", "Haven City"),
]

# The time gates between the worlds (hj2-time-gate, Jak 3's warp gate, in GAME): the one in Jak 2's
# hideout, an actor of hj2-hide, to the Freedom HQ (its arrival point, hj2-freehq-gate, is added to
# Jak 3's freehq by GAME); the Freedom HQ's is spawned by GAME (no entity) and goes to the hideout's
# arrival point. By Jak 2 level: (our actor name, position (m), facing (unit xz), destination, the
# world named by the prompt). The hideout's stands in the free corner of its main room, facing the
# room's middle.
TIME_GATES = [
    ("hideout", "hj2-time-gate-1", (1207.0, 3.1, 53.0), (-0.722, 0.692), "hj2-freehq-gate", "Jak 3"),
]
# The arrival points of the time gates: in front of the gate, facing away from it, the camera
# behind. By our continue name: (Jak 2 level (None: a Jak 3 level), gate position, facing, how far
# in front (m), Jak 3 level list). Jak jumps out of the hideout's gate (warp-gate flag); the Freedom
# HQ's has no entity for Jak 3 to find, Jak just stands there.
GATE_CONTINUES = {
    "hj2-hideout-gate": ("hideout", (1207.0, 3.1, 53.0), (-0.722, 0.692), 6.0, None),
    "hj2-freehq-gate": (None, (710.0, 80.338, -565.0), (-0.908, 0.418), 6.0,
                        [("freehq", "'display"), ("ctyslumc", "#f"), ("freecast", "'special")]),
}

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
    # the fortress gate: its two leaves, each solid, bound to its joint
    "hj2-fort-gate": ("hj2-fort-gate", f"{RIPS}/ctysluma/fort-entry-gate-lod0.glb", None,
                      [{"hull": None, "joint": "frontdoorL"}, {"hull": None, "joint": "frontdoorR"}]),
    # the construction site (hj2-cons-obs.gc)
    # the silo doors: each leaf bound to its joint, like Jak 2's collide meshes
    "hj2-cons-silo-doors": ("hj2-cons-silo-doors", f"{RIPS}/consite/consite-silo-doors-lod0.glb",
                            None, [{"hull": None, "joint": "top_left"},
                                   {"hull": None, "joint": "top_right"}]),
    # the bomb elevator: a 20m platform on a screw 64m long, solid at the platform only (Jak 2's
    # collide mesh)
    "hj2-cons-bomb-elevator": ("hj2-cons-bomb-elevator",
                               f"{RIPS}/consite/consite-bomb-elevator-lod0.glb", None,
                               {"hull": -5.0, "y_max": 4.5}),
    # the prison (hj2-prison-obs.gc)
    "hj2-prsn-cell-door": ("hj2-prsn-cell-door", f"{RIPS}/prison/prsn-cell-door-lod0.glb", None,
                           {"hull": None}),
    "hj2-prsn-vent-fan": ("hj2-prsn-vent-fan", f"{RIPS}/prison/prsn-vent-fan-lod0.glb", None, None),
    # the torture machine: its body and its three arms, each part solid on its joint, like Jak 2's
    # collide meshes (TORTURE_JOINTS)
    "hj2-prsn-torture": ("hj2-prsn-torture", f"{RIPS}/prison/prsn-torture-lod0.glb", None,
                         [{"hull": None, "joint": joint} for joint in (
                             "main", "C_arm_shoulder", "C_arm_elbow", "R_shoulder", "R_arm_elbow",
                             "R_hand_extender_main_END", "L_shoulder", "L_arm_elbow",
                             "L_hand_extender_main_END")]),
    "hj2-prsn-hang-cell": ("hj2-prsn-hang-cell", f"{RIPS}/prison/prsn-hang-cell-lod0.glb", None,
                           None),
    # the warp gate without its energy (primitives 0 and 1, drawn by Jak 2 only while the gate goes
    # somewhere)
    "hj2-warp-gate-b": ("hj2-warp-gate-b", f"{RIPS}/prison/warp-gate-b-lod0.glb", [2, 3],
                        {"hull": None}),
    # the way out of the fortress (hj2-fexa-obs.gc, hj2-fexb-obs.gc): the lift's deck (the joint
    # platscale, rideable), its arm and its base, like Jak 2's collide meshes; the pool's surface
    "hj2-fort-lift-plat": ("hj2-fort-lift-plat", f"{RIPS}/forexita/fort-lift-plat-lod0.glb", None,
                           [{"hull": None, "joint": "platscale"},
                            {"hull": None, "joint": "armrotate"},
                            {"hull": None, "joint": "main"}]),
    "hj2-fort-pool": ("hj2-fort-pool", f"{RIPS}/forexitb/water-anim-fortress-exitb-pool-lod0.glb",
                      None, None),
}
# models with more than their first animation: by model, [(rip, animation, our name)]
MODEL_ANIMS = {
    # the beams slide when Jak comes near (hj2-ruins-obs.gc)
    "hj2-ruins-beam": [(f"{RIPS}/ruins/beam-lod0.glb", "beam-idle", "hj2-ruins-beam-idle"),
                       (f"{RIPS}/ruins/beam-lod0.glb", "beam-slide-center", "hj2-ruins-beam-slide")],
    # the lift raising its deck, and its pose while it rides its path (hj2-fexa-obs.gc)
    "hj2-fort-lift-plat": [
        (f"{RIPS}/forexita/fort-lift-plat-lod0.glb", "fort-lift-plat-idle", "hj2-fort-lift-plat-idle"),
        (f"{RIPS}/forexita/fort-lift-plat-lod0.glb", "fort-lift-plat-scale",
         "hj2-fort-lift-plat-scale")],
}
ACTOR_MODELS["hj2-ruins-beam"] = ("hj2-ruins-beam", f"{RIPS}/ruins/beam-lod0.glb", None, None)
# the bomb elevator's hinges, a model of their own drawn with it (no actor)
EXTRA_MODELS = {
    "hj2-cons-bomb-elevator": [("hj2-cons-bomb-hinges",
                                f"{RIPS}/consite/consite-bomb-elevator-hinges-lod0.glb", None, None)],
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
PORTED_LEVELS = {"atoll", "mountain", "dig3a", "ruins", "consite", "prison", "forexita",
                 "forexitb"}
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
    # Dead Town's beams (at the end of the game, its slabs, bridge, floating platforms and flag are
    # gone with the tower: Jak 2 only spawns them before the tower falls, see jak2_actors.py)
    "beam": ("hj2-ruins-beam", {}),
    # the swinging bars, in every place (GENERIC_ETYPES): Jak 3's swingpole (the bar itself is
    # background), same lumps
    "swingpole": ("swingpole", {}),
    # the slides, in every place: Jak 3's slide-control (target-tube.gc, the same as Jak 2's), its
    # curve
    "slide-control": ("slide-control", {"path": "vector", "path-k": "float"}),
    # the prison: its cell doors (shut), vent fans, torture machine, hanging cells (on their rail,
    # the path) and warp gate (going nowhere until the strip mine is ported)
    "prsn-cell-door": ("hj2-prsn-cell-door", {}),
    "prsn-vent-fan": ("hj2-prsn-vent-fan", {}),
    "prsn-torture": ("hj2-prsn-torture", {}),
    "prsn-hang-cell": ("hj2-prsn-hang-cell", {"path": "vector"}),
    "warp-gate-b": ("hj2-warp-gate-b", {}),
    # the way out of the fortress: its lifts (Jak 3's plat, the user18 option raises the deck in
    # place) and the pool's surface. Its trap doors are broken for good by the escape (Jak 2 marks
    # them dead), so they're left out.
    "fort-lift-plat": ("hj2-fort-lift-plat", {"path": "vector", "sync": "float", "options": "uint32",
                                              "initial-spline-pos": "float"}),
    "water-anim-fortress": ("hj2-fort-pool", {}),
    # the construction site's silo doors and bomb elevator
    "consite-silo-doors": ("hj2-cons-silo-doors", {}),
    "consite-bomb-elevator": ("hj2-cons-bomb-elevator", {}),
}

# PORTED_ACTORS placed in every place, not only in PORTED_LEVELS (Jak 3 has their class in GAME)
GENERIC_ETYPES = {"swingpole", "slide-control"}
# Jak 2's crates of every place, as Jak 3's (a wood crate, its art in GAME), with their pickups.
# Jak 3 added eco-pill-light (8) and lightjak (14) to pickup-type, and three guns of each color.
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
# disables their collision. Kept here: their state at the end of the game, every task done. By Jak 2
# level, the prototypes hidden then (the builder drops their collision too, tagged by the
# decompiler). The ones shown at the end (the construction site's broken scaffolding, the statue's
# rubble...) need nothing: every prototype is shown by default.
HIDDEN_PROTOTYPES = {
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
    # the pumping station: Sig's tank gone (atoll-sig), and the castle seen in the distance, blown up
    # (castle-boss-resolution)
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
# continues of the other places: all of Jak 2's for that level (the respawn points, see
# havenj2-update-continue in GAME), but the title, intro, new game (the prison), demo and cutscene
# ones (scene-wait: waiting for a cutscene)
SKIPPED_CONTINUE_FLAGS = {"demo", "demo-end", "title", "intro", "game-start", "scene-wait"}
SKIPPED_CONTINUE_NAMES = ("movie", "demo")
# the continue flags kept from Jak 2's: no-auto (Jak 3 never picks it by itself), warp-gate (Jak
# arrives jumping out of the closest warp gate), no-blackout
KEPT_CONTINUE_FLAGS = ("no-auto", "warp-gate", "no-blackout")
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


def facing_continue(pos, facing, distance, flags, wants):
    """A continue (Jak 2 format, game units) in front of a gate at pos (m) facing (unit xz): Jak
    stands distance meters in front of it, facing away from it, the camera behind him."""
    fx, fz = facing
    at = [pos[0] + fx * distance, pos[1], pos[2] + fz * distance]
    yaw = math.atan2(fx, fz)
    quat = [0.0, math.sin(yaw / 2), 0.0, math.cos(yaw / 2)]
    cam = [at[0] - fx * 4.5, at[1] + 3.0, at[2] - fz * 4.5]
    look = [at[0] - cam[0], at[1] + 1.5 - cam[1], at[2] - cam[2]]
    n = math.sqrt(sum(c * c for c in look))
    f = [c / n for c in look]
    r = [f[2], 0.0, -f[0]]  # cross(y, f)
    n = math.sqrt(sum(c * c for c in r))
    r = [c / n for c in r]
    u = [f[1] * r[2] - f[2] * r[1], f[2] * r[0] - f[0] * r[2], f[0] * r[1] - f[1] * r[0]]
    return dict(trans=[c * METER for c in at] + [1.0], quat=quat,
                camera_trans=[c * METER for c in cam] + [1.0], camera_rot=r + u + f,
                flags=set(flags), wants=wants)


def gate_continues():
    """The time gates' arrival points in Jak 2's levels (GATE_CONTINUES), as Jak 2 continues: the
    hideout's, Jak arriving by its gate (warp-gate flag)."""
    out = {}
    for name, (level, pos, facing, distance, _) in GATE_CONTINUES.items():
        if level:
            cont = facing_continue(pos, facing, distance, {"warp-gate"},
                                   [(level, "'display"), ("ctywide", "'display"),
                                    ("ctysluma", "'display")])
            cont["level"] = level
            out[name[len("hj2-"):]] = cont
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
        self.continues.update(gate_continues())
        self.continue_names = {}  # Jak 2 name -> ours, filled by the continue selection
        self.aid_to_name = {a["aid"]: name for (lev, name), a in actors.items() if "aid" in a}
        self.cameras = load_cameras()
        self.camera_names = {c["lump"]["name"] for cams in self.cameras.values() for c in cams}

    def translator(self, jak2_level, open_tasks=()):
        closed = lambda task: task not in OPEN_TASKS and task not in open_tasks  # noqa: E731
        return Translator(LEVEL_MAP, self.all_levels | BACKDROP_LEVELS, CITY, LEVEL_MAP[jak2_level],
                          closed, self.continue_names, RENAMES, DROP_EVENTS, self.camera_names,
                          source=jak2_level)


def translate_notice(tr, text):
    """on-notice: the levels a door waits for. A level that isn't ported (but a backdrop) keeps the
    door shut: behind it there's nothing to walk on (only the branch the story state reaches
    counts, see Translator.strict_notice)."""
    return tr.strict_notice(text, BACKDROP_LEVELS)


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
    pair = NEXT_ACTOR_OVERRIDES.get((jak2_level, name), ctx.aid_to_name.get(next_actor(actor)))
    placed = {nm for _, nm in DOORS}
    if pair and pair in placed and not closed:
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


def make_air_train(ctx, jak2_level, name, dest, travel_name):
    """One of AIR_TRAINS: (comment, actor). Its on-notice is Jak 3's air train's: '("continue"
    on-activate wait-for)."""
    actor = ctx.actors[(jak2_level, name)]
    dest_name = continue_name(dest)
    assert dest in ctx.continue_names, f"{name}: continue {dest} isn't ported"
    lump = {
        "name": name,
        "on-notice": script(f"'(\"{dest_name}\" #f #f)"),
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


def make_time_gate(name, pos, facing, dest, travel_name):
    """One of TIME_GATES: (comment, actor), Jak 3's warp gate model facing the room."""
    yaw = math.atan2(facing[0], facing[1])
    trans = [r4(c) for c in pos]
    return f"the time gate to {dest} (hj2-time-gate, Jak 3's warp gate)", {
        "trans": trans,
        "etype": "hj2-time-gate",
        "game_task": 0,
        "quat": [0.0, r4(math.sin(yaw / 2)), 0.0, r4(math.cos(yaw / 2))],
        "bsphere": trans + [8.0],
        "lump": {
            "name": name,
            "on-notice": script(f"'(\"{dest}\" #f #f)"),
            "travel-name": ["string", travel_name],
        },
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
    for jak2_level, name, dest, travel_name in AIR_TRAINS:
        if LEVEL_MAP[jak2_level] == our_level:
            add(*make_air_train(ctx, jak2_level, name, dest, travel_name))
    for jak2_level, name, pos, facing, dest, travel_name in TIME_GATES:
        if LEVEL_MAP[jak2_level] == our_level:
            add(*make_time_gate(name, pos, facing, dest, travel_name))
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
        if level not in place_levels(place):
            continue
        src = actor["lump"]
        trans = [r4(x) for x in actor["trans"][:3]]
        if actor["etype"] == "crate":
            lump = {"name": name}
            if src.get("eco-info"):
                kind, amount = src["eco-info"][:2]
                lump["eco-info"] = ["int32", JAK2_PICKUP.get(int(kind), 0), int(amount)]
            etype = "crate"
        elif actor["etype"] in PORTED_ACTORS and (level in PORTED_LEVELS or
                                                  actor["etype"] in GENERIC_ETYPES):
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
            verts, lo, hi = props_gen.write_actor_glb(src, model, prims, collide,
                                                      anims=MODEL_ANIMS.get(model))
            print(f"  {model}: {verts} vertices, bounds {lo} - {hi}")
            models.append(model)
            for extra, extra_src, extra_prims, extra_collide in EXTRA_MODELS.get(model, []):
                verts, lo, hi = props_gen.write_actor_glb(extra_src, extra, extra_prims,
                                                          extra_collide)
                print(f"  {extra}: {verts} vertices, bounds {lo} - {hi}")
                models.append(extra)
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
        scripts.update(REGION_SCRIPT_OVERRIDES.get(region["id"], {}))
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
            if (region["level"] not in place_levels(place) or region["tree"] != "water" or
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
        if (level not in place_levels(place) or actor["etype"] != "water-vol" or
                "vol" not in actor["lump"]):
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
        # its water height, else the top of its box (a pool whose surface is a water-anim)
        height = (actor["lump"]["water-height"][0] / METER if "water-height" in actor["lump"]
                  else hi[1])
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


def continue_candidates(ctx):
    """(our level, Jak 2 continue, the levels it loads) for the continues of the places, but the
    title, intro, demo and cutscene ones."""
    for place in PLACES:
        for jak2_name, cont in ctx.continues.items():
            if cont["level"] not in place_levels(place):
                continue
            if jak2_name not in CONTINUE_WANTS and jak2_name not in KEPT_CONTINUES and (
                    cont["flags"] & SKIPPED_CONTINUE_FLAGS or
                    any(word in jak2_name for word in SKIPPED_CONTINUE_NAMES)):
                continue
            wants = translate_wants(CONTINUE_WANTS.get(jak2_name, cont["wants"]))
            levels = [lev for lev, _ in wants]
            if place["name"] not in levels:
                levels.append(place["name"])
            yield place["name"], jak2_name, levels


def select_continues(ctx):
    """(our level, continue name, Jak 2 continue) for every continue point to write."""
    chosen = []
    for jak2_name in CITY_CONTINUES:
        chosen.append((CITY, continue_name(jak2_name), jak2_name))
    for level, jak2_name, levels in continue_candidates(ctx):
        try:
            check_memory(levels)
        except ValueError:
            print(f"  continue {jak2_name}: its levels {levels} don't fit together, left out")
            continue
        chosen.append((level, continue_name(jak2_name), jak2_name))
    for _, ours, jak2_name in chosen:
        ctx.continue_names[jak2_name] = ours
    return chosen


# memory ##########################################################################################
# Jak 3's level heap is 18 chunks. A level of each memory mode takes one of these chunk sets (the
# plain case of level-group::alloc-levels!, goal_src/jak3/engine/level/level.gc, no micro or tiny
# level loaded), so levels fit together when they can take chunk sets that don't overlap. Jak 2's
# load-buffer-mode has the same four names (small-edge when a level has none).
CHUNKS = {
    "large": [0xFFF, 0x3FFC0],
    "medium": [0x1FF, 0x3FE00],
    "small-center": [0xFC0],
    "small-edge": [0x3F, 0x3F000],
}
CHUNK_COUNT = {mode: bin(masks[0]).count("1") for mode, masks in CHUNKS.items()}
WANT_LOAD = re.compile(r"\(want-load((?: '[\w-]+)+)\)")


def fits(modes):
    """Can levels of these memory modes be loaded together?"""
    def place(i, used):
        return i == len(modes) or any(not mask & used and place(i + 1, used | mask)
                                      for mask in CHUNKS[modes[i]])
    return place(0, 0)


def check_memory(levels):
    if not fits([MEMORY[lv] for lv in levels]):
        raise ValueError(f"levels {levels} don't fit in the level heap together")


def jak2_memory_modes():
    """Jak 2 level -> its load-buffer-mode."""
    src = open(JAK2_LEVEL_INFO, encoding="utf-8").read()
    out = {}
    for block in re.split(r"\n\(define ", src):
        name = re.search(r":name '([\w-]+)", block)
        if not name or "level-load-info" not in block[:200]:
            continue
        mode = re.search(r":memory-mode \(load-buffer-mode ([\w-]+)\)", block)
        out[name.group(1)] = mode.group(1) if mode else "small-edge"
    return out


def load_sets(ctx, regions):
    """Every set of our levels loaded together: the want-load lists of the translated door,
    elevator and region scripts, and the levels of the continues."""
    sets = set()

    def add_script(text):
        for m in WANT_LOAD.finditer(text or ""):
            levels = tuple(sorted(set(re.findall(r"'([\w-]+)", m.group(1)))))
            if len(levels) > 1:
                sets.add(levels)

    for jak2_level, name in DOORS + [(PALACE_ELEVATOR["level"], PALACE_ELEVATOR["name"])]:
        actor = ctx.actors[(jak2_level, name)]
        for text in translate_lumps(ctx, jak2_level, name, actor["lump"]).values():
            add_script(text)
    for region in regions.values():
        if region["tree"] not in ("target", "camera") or region["level"] not in LEVEL_MAP:
            continue
        tr = ctx.translator(region["level"], REGION_OPEN_TASKS.get(region["id"], ()))
        for text in region["scripts"].values():
            add_script(tr.script(text))
        for text in REGION_SCRIPT_OVERRIDES.get(region["id"], {}).values():
            add_script(text)
    for _, _, levels in continue_candidates(ctx):
        if len(set(levels)) > 1:
            sets.add(tuple(sorted(set(levels))))
    return sets


def memory_modes(ctx, regions):
    """Each place's memory mode: Jak 2's (the largest of its levels'), unless a set of levels it's
    loaded with (load_sets) can't fit in the heap. Then, set by set, the change that makes it fit
    with the fewest sets left that don't: a place loaded next to the city (12 chunks) can only be
    small-edge, the third place of a set loaded without it small-center."""
    jak2 = jak2_memory_modes()
    order = ["small-edge", "small-center", "medium", "large"]
    modes = {CITY: "large"}
    for p in PLACES:
        modes[p["name"]] = max((jak2.get(lv, "small-edge") for lv in place_levels(p)),
                               key=order.index)
    sets = sorted(load_sets(ctx, regions))

    def failing():
        return [s for s in sets if not fits([modes[lv] for lv in s])]

    for _ in range(100):
        bad = failing()
        if not bad:
            return {lv: m for lv, m in modes.items() if lv != CITY}
        options = []
        for lv in bad[0]:
            if lv == CITY:
                continue
            old = modes[lv]
            for alt in order:
                if alt == old or CHUNK_COUNT[alt] > CHUNK_COUNT[old]:
                    continue
                modes[lv] = alt
                if fits([modes[x] for x in bad[0]]):
                    options.append((len(failing()), -CHUNK_COUNT[alt], lv, alt))
                modes[lv] = old
        if not options:
            raise ValueError(f"levels {bad[0]} can't fit in the level heap together")
        _, _, lv, alt = min(options)
        others = ", ".join(x for x in bad[0] if x != lv)
        print(f"  memory: {lv} {modes[lv]} -> {alt}, loaded with {others}")
        modes[lv] = alt
    raise ValueError("memory modes: no solution")


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
    flags = [f for f in KEPT_CONTINUE_FLAGS if f in jak2["flags"]]
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
    custom_props, prop_models = props_gen.city_custom_prop_actors(CITY_LEVELS)
    actor_list += custom_props
    models = CITY_CUSTOM_MODELS + [m for m in prop_models if m not in CITY_CUSTOM_MODELS]
    # the doors rebuilt from Jak 2's models (the fortress gate, ACTOR_MODELS)
    models += [m for m in custom_models(actor_list) if m not in models]
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
    gd += ['  "havenj2-part.o"', '  "havenj2-signs.o"', '  "havenj2-obs.o"', '  "havenj2-farm.o"',
           '  "havenj2.go"', "  ))", ""]
    print("  props as actors: " + ", ".join(f"{n} {e}" for e, n in sorted(prop_counts.items())))
    print(f"  particles: {part_stats}")
    write_if_changed(f"{LEVELS_DIR}/havenj2/havenj2.gd", "\n".join(gd))
    return len(actor_list), sum(len(t["regions"]) for t in trees.values())


def write_place(ctx, place, regions):
    actor_list, art = make_actors(ctx, place["name"])
    actor_list += ported_actors(ctx, place)
    models = custom_models(actor_list)
    code = list(place.get("code", []))
    # Jak 2's particle effects of the place (PLACE_PARTICLES in gen_havenj2_particles.py): its part
    # spawners, <place>-part.gc and the sprite textures of its own texture page
    sprite_lines = []
    if place["name"] in particles_gen.PLACE_PARTICLES:
        part_actors, sprite_textures, engine_max, stats = particles_gen.write_place(place["name"])
        print(f"  {place['name']} particles: {stats}")
        actor_list += part_actors
        PART_ENGINE_MAX[place["name"]] = engine_max
        code.append(f"{place['name']}-part.o")
        if sprite_textures["textures"]:
            sprite_lines = [
                "  // the sprite textures of its particles, as texture page "
                f"{sprite_textures['page']} ({place['name']}-part.gc)",
                '  "sprite_textures": ' + json.dumps(sprite_textures) + ",",
            ]
    folder = f"{LEVELS_DIR}/{place['name']}"
    os.makedirs(folder, exist_ok=True)
    import_fr3 = {
        "game": "jak2",
        "levels": place_levels(place),
        "tfrag": True,
        "tie": True,
        "shrub": True,
        "collision": True,
    }
    if "collision_bounds" in place:
        import_fr3["collision_bounds"] = place["collision_bounds"]
    hidden = hidden_prototypes(place_levels(place))
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
        f"  // imported from Jak 2's extracted {', '.join(place_levels(place))}.",
        f'  "long_name": "{place["name"]}",',
        f'  "iso_name": "{place["iso"]}",',
        f'  "nickname": "{place["nick"]}",',
        '  "import_fr3": ' + json.dumps(import_fr3) + ",",
        *region_lines,
        *sprite_lines,
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
    gd += [f'  "{obj}"' for obj in code]
    gd += [f'  "{place["name"]}.go"', "  ))", ""]
    write_if_changed(f"{folder}/{place['name']}.gd", "\n".join(gd))
    return len(actor_list), sum(len(t["regions"]) for t in trees.values())


def freehq_gate_continue():
    """The Freedom HQ's arrival point from the hideout's time gate (GATE_CONTINUES), added to Jak 3's
    freehq by GAME (jak2-haven-city-world.gc): in front of the HQ's gate, with Jak 3's freehq-start
    level list and sounds."""
    _, pos, facing, distance, wants = GATE_CONTINUES["hj2-freehq-gate"]
    cont = facing_continue(pos, facing, distance, set(), wants)
    t, c, q = cont["trans"], cont["camera_trans"], cont["quat"]
    rot = " ".join(str(int16(x)) for x in cont["camera_rot"])
    want_lines = "\n".join(
        f"      (new 'static 'level-buffer-state-small :name '{name} :display? {disp})"
        for name, disp in wants)
    return f""";; the Freedom HQ's arrival point from Jak 2's hideout (its time gate), in front of the HQ's
;; gate (GAME adds it to freehq's continues)
(define *hj2-freehq-gate-continue*
  (new 'static 'continue-point
    :name "hj2-freehq-gate"
    :level 'freehq
    :trans (static-vectorm {t[0] / METER:.4f} {t[1] / METER:.4f} {t[2] / METER:.4f})
    :camera-trans (static-vectorm {c[0] / METER:.4f} {c[1] / METER:.4f} {c[2] / METER:.4f})
    :quat (new 'static 'vector4h :data (new 'static 'array int16 4 {int16(q[0])} {int16(q[1])} {int16(q[2])} {int16(q[3])}))
    :camera-rot (new 'static 'array int16 9 {rot})
    :flags (continue-flags no-auto)
    :on-goto #f
    :vis-nick 'freehq
    :vehicle-type #x1b
    :want-count {len(wants)}
    :want (new 'static 'inline-array level-buffer-state-small {len(wants)}
{want_lines}
      )
    :want-sound (new 'static 'array symbol 3 'cityhq1 'cityhq2 'ctyslmch)
    )
  )
"""


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
            (place["ocean"] if isinstance(place.get("ocean"), str) else
             "*ocean-map-havenj2*" if place.get("ocean") else None),
            f";; {what} (custom_assets/jak3/levels/{place['name']}), Jak 2's "
            f"{', '.join(place_levels(place))}.\n"
            f";; memory: {memory} (Jak 2's where the level heap allows, see memory_modes in\n"
            ";; gen_havenj2_links.py).",
            "10.0", place["sky"], PART_ENGINE_MAX.get(place["name"], 0)))
    out.append(freehq_gate_continue())
    write_if_changed(LEVEL_INFO_OUT, "\n".join(out))


def main():
    actors = load_actors()
    ctx = Context(actors)
    regions = load_regions()
    MEMORY.update(memory_modes(ctx, regions))
    print("memory: " + ", ".join(f"{p['name']} {MEMORY[p['name']]}" for p in PLACES))
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
