# Haven City: New Dawn — Developer guide

This guide explains how Haven City: New Dawn works, for a developer who has never written GOAL
Lisp: the ideas the mod relies on, why each change was made, and how to make the common changes
yourself (a color variant, a new hook). The detailed reference, feature by feature, is
[`haven_city_new_dawn_reference.md`](haven_city_new_dawn_reference.md); the
[change log](#change-log) closes this guide. Players only need the root
[`README.md`](../../../README.md).

**Contents**

1. [The mod in one page](#1-the-mod-in-one-page)
2. [GOAL for this mod](#2-goal-for-this-mod)
3. [Changing Jak 3 without breaking it: hooks](#3-changing-jak-3-without-breaking-it-hooks)
4. [From Jak 2's disc to Jak 3 levels: the level port](#4-from-jak-2s-disc-to-jak-3-levels-the-level-port)
5. [The war mode, step by step](#5-the-war-mode-step-by-step)
6. [Color variants](#6-color-variants)
7. [What the repository holds, and what it doesn't](#7-what-the-repository-holds-and-what-it-doesnt)
8. [Building and testing](#8-building-and-testing)
9. [Known issues](#9-known-issues)
10. [Change log](#change-log)

## 1. The mod in one page

The mod puts Jak 2's Haven City and the places around it inside Jak 3, as they are at the end of
Jak 2, and adds a war mode where Jak 2's Krimzon Guards fight Jak 3's Freedom League. Three kinds
of work make it:

| Kind | Where | Made by |
|---|---|---|
| Level data: geometry, actors, doors, navigation, models, sounds | `custom_assets/jak3/levels/`, `custom_assets/jak3/models/custom_levels/` | Generated from your Jak 2 disc by the level port ([4](#4-from-jak-2s-disc-to-jak-3-levels-the-level-port)), never committed |
| The mod's GOAL code | `goal_src/jak3/pc/features/jak2-haven-city-*.gc`, `goal_src/jak3/levels/havenj2/`, `goal_src/jak3/levels/city/war/` | Written by hand |
| A few lines in Jak 3's own code | Lines marked `og:jak2-haven-city added` | Written by hand, each calling the mod ([3](#3-changing-jak-3-without-breaking-it-hooks)) |

Two rules shape every change:

- **Off by default.** The mod and its war mode are off at each boot. Off, Jak 3 behaves as the
  original game: every hook gives back Jak 3's own answer.
- **Generated data is never edited by hand.** A fix to a level goes into the port's manifest or
  into the level port itself, then the level port runs again.

## 2. GOAL for this mod

GOAL is the Lisp the Jak games are written in. You don't need all of it to work on this mod; these
are the ideas it uses most. Worked code examples live in the shared Lisp wiki
([`.agents/skills/goal-lisp/wiki/`](../../../.agents/skills/goal-lisp/wiki/index.md)); this guide
links to them instead of copying them.

### 2.1 Files, objects and DGOs

Each `.gc` file compiles to an object file (`.o`). Objects are shipped in packages:

- **GAME.CGO** is loaded once at boot and stays loaded. The mod's shared code is there: its menu,
  the war mode's switch, the weather, the doors used by several levels. A new GAME file is listed
  in `goal_src/jak3/dgos/game.gd`.
- **A level's DGO** (`HJ2.DGO` for the city hub, `HJR.DGO` for Dead Town...) is loaded and unloaded
  with its level. Code that only one level needs goes there.

Why it matters: when a level unloads, the types its code defined disappear. A class used by two
levels that can be loaded together, or by an actor that outlives a level, must live in GAME.

`goal_src/jak3/game.gp` holds the build steps; the mod adds one line there that loads the level
port's generated build file, `goal_src/jak3/levels/havenj2/jak2-haven-city.gp`.

### 2.2 Processes and states

Everything that moves in the game is a **process**: a guard, a door, a transport, the war's
director. A process has its own small memory (its heap) and runs a little each frame. Its
behavior is written as **states** (`defstate`): code run when it enters the state, every frame
while in it, and when it leaves. `go` switches to another state; `suspend` gives the frame back
and continues on the next one.

Example in the mod: the city's guard turret has an `idle` state (hidden under its lids) and a
`hostile` state (popped up, firing). Every frame in `idle`, it checks whether Jak drives a vehicle
nearby during an alert, and since change 33 whether its color must change
(`hj2-cty-guard-turret-color`, `goal_src/jak3/levels/havenj2/havenj2-obs.gc`).

A `defbehavior` is a function that runs as a process (it can read `self`). The war's death cloud
is one: `hj2-war-death-fx` runs 15 frames in a small process of its own, then exits.

### 2.3 Handles, not pointers

A process can die at any time, and its memory is then given to another process. Keeping a plain
pointer to it is a bug waiting to happen. A **handle** (`process->handle`) remembers the process
and its id; `handle->process` gives `#f` once that process is gone. The mod keeps handles
everywhere a process is remembered across frames: the death cloud keeps the dying guard's handle,
the transport its guards' handles, the war director its transport's.

### 2.4 Types, methods and `define-extern`

`deftype` declares a type (its fields and methods), `defmethod` writes one of its methods. A
child type can call its parent's version of a method (`method-of-type`), which is how the mod
changes a stock behavior from the outside: the wiki's
[Wrapping a stock method](../../../.agents/skills/goal-lisp/wiki/jak3.md#410-wrapping-a-stock-method-from-a-game-file)
shows it.

`define-extern` tells the compiler the type of a function or global written in another file, so
that a file can call code linked after it. Jak 3's `guard.gc` calls the mod's GAME functions this
way.

### 2.5 Models: art groups and skeleton groups

A model is an **art group** (`<name>-ag`): its skeleton, its meshes and its animation clips, in a
fixed order. A **skeleton group** (`defskelgroup`, or the shorter `def-actor`) says which art
group a class uses, its bounds and its mesh for each distance. A process gets its model once, at
init, with `initialize-skeleton`.

The mod rebuilds Jak 2's models with `build-actor`, OpenGOAL's tool for custom models: the level
port writes a `.glb` per model, and the build turns it into an art group. Two models built from
the same Jak 2 file share their skeleton and clips, which is what makes the color variants cheap
([6](#6-color-variants)) and lets a red guard play the blue guard's clips.

### 2.6 Particles, effects and clocks

- **Particles** (sparks, rain, smoke) come from launchers; each particle follows the clock of the
  process that launched it. The mod stops one of the game's clocks to hold the hour, which froze
  the rain in the air until the weather's particles were moved to the particle clock (change 32).
- **Effects** are events written into animation clips: a footstep sound at frame 12, the purple
  dissolve `death-default` at the end of a death clip. A model runs them only if it has an
  effect control, which `build-actor` models lack ([5.6](#56-death-the-purple-cloud)).

## 3. Changing Jak 3 without breaking it: hooks

Most of the mod's behavior changes in Jak 3's own code follow one pattern:

1. The mod writes a function in GAME that takes Jak 3's own answer and returns either that answer
   (mod or war off) or the mod's.
2. One line of Jak 3's code calls it, marked `;; og:jak2-haven-city added`.

**Example: a guard's weapon.** Every weapon change of a Jak 3 guard goes through
`crimson-guard-method-267` (`goal_src/jak3/levels/city/traffic/citizen/guard.gc`). The marked line
at its top passes the weapon Jak 3 picked to `hj2-war-guard-type`
(`goal_src/jak3/pc/features/jak2-haven-city-war.gc`), which returns:

| Guard | War off | War on |
|---|---|---|
| Blue (Freedom League) | Jak 3's choice | The rifle, or the grenade launcher for one guard in three |
| Red or yellow Krimzon Guard | (none exist) | Its model's weapon: rifle, or grenade launcher |

Why this way:

- **Native non-regression:** with the war off, the function returns its input, so Jak 3 runs as
  before.
- **Small diffs:** one marked line per hook in Jak 3's files; the logic lives in the mod's file.
  `git grep "og:jak2-haven-city added"` lists every change to Jak 3's code.
- **One place per rule:** every caller goes through the same method, so the rule can't be missed
  by a path nobody tested.

The hooks added in change 33:

| Jak 3 file | Calls | Purpose |
|---|---|---|
| `levels/city/common/guard-rifle.gc`, `guard-grenade.gc`, `guard-states.gc` | `hj2-war-melee-ok?` | No rifle butt during the war unless Jak is the guard's target |
| `levels/city/traffic/citizen/guard.gc` (`crimson-guard-method-270`) | `hj2-war-guard-type` | The off-screen weapon change compares the weapon the guard would really get ([5.3](#53-weapons)) |
| `engine/ai/enemy.gc` (`'death-start`) | `hj2-war-death-start` | A Krimzon Guard's purple death cloud |
| `levels/wascity/traffic-util.gc` | `hj2-war-cell-dist` | Units spawn further out during the war |
| `levels/city/traffic/traffic-engine.gc` | (a test, no call) | No pedestrian spawned when its navigation mesh isn't loaded |

## 4. From Jak 2's disc to Jak 3 levels: the level port

Nothing of the city is modeled by hand. The level port (`scripts/level_port`, a Python tool)
reads what the decompiler extracts from Jak 2's disc and writes Jak 3 custom levels. This mod is
not code in the tool: it is the tool's **manifest**,
`custom_assets/jak3/ports/jak2-haven-city/port.jsonc`, which lists the levels, the doors, the
models and the sounds to take.

```text
iso_data/jak2 (your disc's files)
   | decompiler (the port's extract step)
   v
decompiler_out/jak2/levels/<level>/*.glb      Jak 2's models ("rips")
out/jak2/fr3/<level>.fr3                       backgrounds, collision, textures
   | python scripts/level_port <manifest>
   v
custom_assets/jak3/levels/hj2-*/               level files
custom_assets/jak3/models/custom_levels/*.glb  models rebuilt for build-actor
goal_src/jak3/levels/havenj2/*-part.gc ...     particles, build steps (generated)
   | goalc (mi)
   v
out/jak3/iso/HJ*.DGO, out/jak3/fr3/*.fr3       what the game loads
```

A model entry of the manifest, the troop transport:

```json
"hj2-transport": {"model": "hj2-transport", "rip": "forestb/transport-lod0.glb",
                  "prims": null, "collide": null, "anims": ["idle", "hatch-open", "hatch-close"]}
```

`rip` is Jak 2's model as the decompiler exported it, `prims` the parts kept (`null`: all), `anims`
the clips kept in the order the GOAL code expects them. The level port writes
`hj2-transport.glb`; the build makes `hj2-transport-ag` of it.

Run it from the repository root (it extracts what is missing first):

```bash
task level-port -- custom_assets/jak3/ports/jak2-haven-city/port.jsonc
```

The reference explains each step and key: [2](haven_city_new_dawn_reference.md#2-how-it-is-built)
and [6.7](haven_city_new_dawn_reference.md#67-rebuilding-jak-2s-models).

## 5. The war mode, step by step

The war mode (Mods menu, "KG-Guard vs Freedom Fighters") puts Jak 2's Krimzon Guards against
Jak 3's Freedom League in Jak 2's city and in Jak 3's own. It reuses Jak 3's traffic code: the
guards are Jak 3's `crimson-guard`, the jetpack guards Jak 3's `flying-turret`. The mod only
changes how they look, which side they are on and a few rules.

![A red jetpack guard firing over the slums](images/war-jetpack-guard.jpg)

### 5.1 The switch

The menu's war entry is greyed out and can't be chosen while the mod is off. The shared menu file
draws a disabled flag like an enabled one, and the project rules forbid editing it, so the mod's
menu uses a flag type of its own that draws greyed out when disabled (`hj2-menu-flag`,
`jak2-haven-city-menu.gc`; the code is in the wiki,
[4.36](../../../.agents/skills/goal-lisp/wiki/jak3.md#436-the-mods-menu-a-greyed-out-flag)).

Switching the war rebuilds the traffic of the city loaded now, because a guard's look is chosen
when its process is made.

### 5.2 Looks and sides

During the war, each new guard takes the look that is furthest below its share: 10 blue, 4 red
rifles, 3 red grenade launchers, 2 yellow rifles, 1 yellow launcher, out of 20. A red or yellow
guard is drawn with Jak 2's model but plays the blue guard's clips, so it walks, shoots and dies
exactly like one.

Who fights whom comes from Jak 3's **attack controller**, a table of hatreds between kinds of
units. A Krimzon Guard registers as a Krimzon Guard robot, which Jak 3's guards already hate. For
the war the director adds entries (`hj2-war-hatred-set!`, `hj2-war-city.gc`):

| Who | Seeks | Hatred | Distance |
|---|---|---|---|
| Blue guards | Krimzon Guards | 0.9 | up to 160 m (full up to 100 m) |
| Krimzon Guards | Blue guards | 0.9 | up to 160 m |
| Krimzon Guards | Citizens | 0.7 | up to 100 m |

A unit picks the target with the best score, its hatred times a distance factor. With 0.4 the
Krimzon Guards never chose a citizen over a guard; 0.7 has 4 to 7 of them chasing citizens at once.
The stock table comes back when the war stops, unless a Jak 3 mission set its own.

### 5.3 Weapons

Blue guards fight with the rifle and the grenade launcher only ([3](#3-changing-jak-3-without-breaking-it-hooks)).
The hook alone was not enough: the traffic keeps guards in a pool and reuses them, and a pooled
guard keeps the weapon it had before the war. The director re-arms the tazer-armed ones every
0.5 s (`hj2-war-rearm-guards`). Test: 9 blue guards of 12 still had the tazer before, none after.

A lesson on hooks, from the war's worst bug. When a hook changes what a stock function decides,
read the callers of that function too. Off screen, every 16 frames, Jak 3 offers each guard
another weapon (`crimson-guard-method-270`): it calls the weapon method, then answers "changed",
and its callers send the guard to its hostile state again. With the hook, a Krimzon Guard keeps
its rifle, so nothing changed, yet the answer was still "changed": every Krimzon Guard out of view
restarted its attack state 4 times a second, and the city crashed within a minute or two, in
places that had nothing to do with it (the kernel, the minimap, the transport). A bisection found
it: Krimzon Guards with the squad's weapons ran 4 times without a crash, with rifles only they
crashed 3 times in 4. The fix is one marked line: the off-screen change compares the weapon the
guard would really get. Since then, 16 test runs of war, none crashed.

### 5.4 The rifle butt

Jak 3's guards strike with the rifle butt when their target is close. During the war two guards
of opposite sides meet often, and they spent the fight hitting each other. Now a guard strikes
only when its target is Jak (`hj2-war-melee-ok?`); against another guard it keeps shooting. Three
paths lead to the strike (the rifle's, the grenade launcher's, and the general check of a close
target in `guard-states.gc`); with the first two only, a guard still struck another one in about
one count in three. With the three: none in 24 counts of 60 s of war.

### 5.5 Spawn distance and density

Jak 3's traffic makes units appear in the street cells near the camera: within 20 m off screen for
guards and citizens, 120 m for vehicles. During the war the mod widens these to 80 m and 180 m
(`hj2-war-cell-dist`), so guards come from further away and the fights look larger. The number of
guards stays 20: with 30, the city's navigation meshes ran out of room for them (`unable to
allocate nav-mesh` in the log) and the game crashed.

### 5.6 Death: the purple cloud

A blue guard that dies dissolves in a purple cloud: its death clip carries Jak 3's `death-default`
effect. The red and yellow guards fell and stayed. Three causes, found one after the other:

1. **No effect control.** A `build-actor` model has none, so its clips' effects never ran. The mod
   makes one when the guard is created (`hj2-war-guard-clips`).
2. **A crash.** `death-default` then switched the model to the game's generic renderer, which
   can't draw a custom model: the game crashed. The mod cancels that switch and draws the cloud
   itself, sparks rising from the guard's joints for 15 frames (`hj2-war-death-fx`).
3. **Invisible sparks.** The spark particle has no texture of its own; the game adds it only when
   launching through `merc-death-spawn`. Launched any other way, nothing showed.

The code and the evidence are in the wiki,
[4.35](../../../.agents/skills/goal-lisp/wiki/jak3.md#435-build-actor-models-their-effects-the-death-cloud-another-mesh-at-runtime).

![A Krimzon Guard's death cloud](images/war-kg-death.jpg)

Checked side by side: a Krimzon Guard (top) and a blue guard (bottom) killed in front of Jak, shot
2, 8, 16 and 30 frames after their cloud starts. Both play the same death clip at the same pace,
and the cloud starts at the same clip frame (frame 81 and 84 after the kill in one test).

![A Krimzon Guard's death (top) and a blue guard's (bottom), at the same frames](images/war-death-compare.jpg)

### 5.7 Voice lines

Jak 2 waits, after a guard's line ends, for the next line's delay before starting it; Jak 3 counts
the delay from the last line of the same kind, so lines came one after the other, and its two
speech channels could talk at once. In Jak 2's city the mod applies Jak 2's rule and lets no line
start while the other channel speaks (`hj2-speech-ready?`). During the war the Krimzon Guards say
Jak 2's lines, the blue guards Jak 3's; a guard saying Jak 2's lines in a fight uses those Jak 2
had for a driving or a Dark Jak target when Jak is one. Every war line is picked at random among
its set.

| Lines a war guard can say (per voice, read in game) | Before | Now |
|---|---|---|
| Krimzon Guard | Jak 2's 222, in a fixed order | Jak 2's 261 (39 more for a driving or Dark Jak target), at random |
| Blue guard | The same 222 as the Krimzon Guards | Jak 3's 66, with Jak 3's voices, at random |

Measured in game, 2 minutes of war in the slums, the lines as before change 33 (the type hook off,
no random order) against now:

| | Before (2 runs) | Now (3 runs) |
|---|---|---|
| Lines heard | 39 and 24 | 21, 19 and 16 |
| Different lines | 35 and 24 | 19, 16 and 16 |
| Blue guards' lines from Jak 3 | 0 of 11, 0 of 8 | 8 of 8, 2 of 2 (no blue guard near in the third) |

One trap on the way: the blue guards first used Jak 3's speech tables as they are, whose own
spacing holds a type's next line 15 to 23 s for every guard; with Jak 2's spacing on top, they spoke
0 to 2 lines in 2 minutes and silenced the channel. They now use copies of those tables
(`*hj2-war-blue-speeches*`, `havenj2-traffic.gc`), spaced like Jak 2's line of the same type; Jak 3's
own tables stay as they are for Jak 3's city.

### 5.8 Transports and vehicles

A troop transport lands near Jak every 45 to 90 s and drops guards of its side, the two sides in
turn: a red Krimzon Guard ship with red and yellow guards, a blue Freedom Fighters ship with blue
guards. The Hellcats and guard bikes fly the lanes during the war too, half red, half blue.

![A Freedom Fighters transport dropping a blue guard](images/war-transport-blue.jpg)

## 6. Color variants

### 6.1 The models and their textures

The objects asked for, with the Jak 2 model each is rebuilt from (under
`decompiler_out/jak2/levels/`) and the models the level port writes (under
`custom_assets/jak3/models/custom_levels/`):

| Object | Jak 2 model (rip) | Generated models | Textures |
|---|---|---|---|
| Krimzon Guard (unit) | `forresca/crimson-guard-lod0.glb` | `hj2-kg-red`, `hj2-kg-red-gl`, `hj2-kg-yellow`, `hj2-kg-yellow-gl` | 46, among them the red armor `cguardgame-metalered-01`, `-shouldershield`, `-armshield`, `-scarf` and the yellow armor `darkguard-headshield`, `-scarf`, `-shouldershield`, `-armshield` |
| Krimzon Guard (jetpack) | `forresca/crimson-guard-hover-lod0.glb` | `hj2-hover-red`, `hj2-hover-blue` | 19, red: `cguardgame-metalered-01`, `cguardgame-shouldershield` |
| KG transport | `forestb/transport-lod0.glb` | `hj2-transport`, `hj2-transport-blue` | `kgtrns-side01`, `kgtrns-side01-envmap-strength`, `kgtrns-wing01`, `kgtrns-box01`, `kgtrns-topjet01`, `kgtrns-hatch01`, `war-armor-weathered` |
| City anti-air turret | `ctywide/cty-guard-turret-lod0.glb`, `ctywide/cty-guard-turret-explode-lod0.glb` | `hj2-cty-guard-turret`, `hj2-cty-guard-turret-explode`, `hj2-cty-guard-turret-blue`, `hj2-cty-guard-turret-explode-blue` | `kgt-ribs01`, `kgt-rim01`, `kgt-logo01`, `kgt-gun01` to `kgt-gun05` |
| Hellcat | `lwidea/hellcat-lod0.glb` | `hj2-hellcat-red`, `hj2-hellcat-blue` (out of the war: Jak 3's own `hellcat-ag`) | 23: `wing01`, `wing02`, `wing02grey01`, `jetTop01`, `jets01`, `backThing01`, `stripe03`, `hood01`, `grillRim01`, `post01`, `turret01`, `lightCase01`, `rail01`, `kcfrontend01`, `light01`, `dash01`, `gunBoxBack01`, `gunbox01`, `gunbox02`, `gunBoxFront01`, `seat01`, `gauge01`, `windshield01` |
| Krimzon Bike | `lwideb/crimson-bike-lod0.glb` | `hj2-guard-bike` (blue), `hj2-guard-bike-red` | `kcbackjet01`, `kccorg01`, `kcfrontend01`, `kcfrontgard01`, `kccushion01`, `bike-02` |

Where the game uses each color:

| Object | Out of the war | During the war |
|---|---|---|
| Anti-air turret | Blue | Red; a hidden turret switches as the war starts or stops |
| Transport | (none) | Red for the Krimzon Guard's ships, blue for the Freedom Fighters' |
| Hellcat | Jak 3's own | Half red, half blue (by process id) |
| Guard bike | Blue | Half red, half blue |
| Jetpack guard | (none) | Red or blue, by side |

![A blue anti-air turret, war mode off](images/turret-blue.jpg)

| | |
|---|---|
| ![A Krimzon Guard Hellcat, Jak at its controls](images/war-hellcat-red.jpg) | ![A Freedom Fighters Hellcat, Jak at its controls](images/war-hellcat-blue.jpg) |
| ![A Krimzon Guard transport dropping red guards](images/war-transport-red.jpg) | ![A Freedom Fighters transport dropping a blue guard](images/war-transport-blue.jpg) |

### 6.2 How a variant is made: `recolor`

A variant is one more model entry in the manifest, made from the same rip with a `recolor` rule.
A rule turns the hue of some texels: those whose hue is in a window, in degrees on the color
wheel (red is 0, blue about 217), and whose saturation is high enough (greys are left alone).
It changes no geometry and stores no texture in the repository: the recolored textures are made
on each machine from the player's own Jak 2.

The blue transport:

```json
"hj2-transport-blue": {"model": "hj2-transport-blue", "rip": "forestb/transport-lod0.glb",
                       "prims": null, "collide": null, "anims": ["idle", "hatch-open", "hatch-close"],
                       "recolor": {"hues": [-15, 15], "rotate": 217, "min_saturation": 0.3}}
```

The texels within 15 degrees of red, at 30 % saturation or more, turn by 217 degrees: blue. A
rule can be limited to some textures (`"textures": [...]`), and `recolor` can be a list of rules
applied in order.

Why the bike and Hellcat rules name their textures and go one way only: the mod's texture pack
paints some of those textures blue, and the rips are extracted with the pack when it is installed.
A red-to-blue rule leaves an already blue texel as it is, a blue-to-red rule turns it red, so
each variant comes out the same with or without the pack. Limiting the rule to the textures the
pack paints keeps the Hellcat's windshield, naturally bluish, as it is.

### 6.3 Making a new variant

1. **Find the hues.** List the textures of the rip and their main hues, from the repository root
   (a reading aid, nothing to commit):

   ```bash
   python -c "
   import base64, colorsys, json, struct, sys
   sys.path.insert(0, 'scripts')
   from level_port.common.glb import png_decode
   data = open(sys.argv[1], 'rb').read()
   gltf = json.loads(data[20:20 + struct.unpack_from('<I', data, 12)[0]])
   for im in gltf['images']:
       w, h, px = png_decode(base64.b64decode(im['uri'].split(',', 1)[1]))
       bins = {}
       for i in range(0, len(px), 4):
           hue, sat, val = colorsys.rgb_to_hsv(*(c / 255 for c in px[i:i + 3]))
           if sat >= 0.3:
               b = round(hue * 12) % 12 * 30
               bins[b] = bins.get(b, 0) + 1
       top = sorted(bins.items(), key=lambda kv: -kv[1])[:3]
       print(im['name'], f'{w}x{h}', ', '.join(f'{b} deg: {100 * n // (w * h)} %' for b, n in top))
   " decompiler_out/jak2/levels/forestb/transport-lod0.glb
   ```

   Each line names a texture and its most common saturated hues, in steps of 30 degrees (0: red,
   30: orange-brown, 60: yellow, 210: blue).

2. **Add the model** to the manifest's `models`: copy the original entry, give it a new `model`
   name and a `recolor` rule (or a list of rules).
3. **Load it** where the game needs it: add the name to the `models` list of the level that uses
   it (`havenj2` for the city; the war's `hj2-war` too for Jak 3's city, and its art group in
   `goal_src/jak3/dgos/ctypesa.gd` with a line in `game.gp`, as `hj2-transport-blue`), or to the
   original's `extras` to put it in the same levels.
4. **Declare it in GOAL** with `def-actor`, the same bounds and origin joint as the original, and
   choose it in the class's code: at init (the transport takes its side's,
   `hj2-transport-init-by-other`), or at runtime (the turret,
   [wiki 4.35](../../../.agents/skills/goal-lisp/wiki/jak3.md#435-build-actor-models-their-effects-the-death-cloud-another-mesh-at-runtime)).
5. **Build:** run the level port, then `(mi)` ([8](#8-building-and-testing)).

A rule only turns hues: a darker or lighter version needs a new key in `recolor_pixels`
(`scripts/level_port/common/glb.py`).

## 7. What the repository holds, and what it doesn't

The repository never holds what is made from the games' files. Each player's install makes it
from their own Jak 2 and Jak 3:

| In the repository | Made on each machine |
|---|---|
| The mod's GOAL code, the level port, the manifest | Every level file of `custom_assets/jak3/levels/hj2-*/` and `havenj2/` |
| Torn's voice lines for the speakers, the user's own recordings, and their encoder: `custom_assets/jak3/ports/jak2-haven-city/voices/` | Every model `.glb` of `custom_assets/jak3/models/custom_levels/hj2-*` (the variants included) |
| These screenshots (`docs/modding/current_mod/images/`) | The particles, sounds, music and voice lines taken from Jak 2 |
| The mod's texture pack as a zip (`texture_packs/`) | The extracted games (`iso_data/`, `decompiler_out/`, `out/`) |

How it stays that way: a full run of the level port writes the list of every file it generated
into a block of `.gitignore` (the manifest's `ignore_outputs`), so a new model is ignored as soon
as the port has made it once. At install, the launcher runs the mod's extractor, which runs the
level port on the player's discs; Jak 2 and Jak 3 must both be installed in the launcher first.
The texture pack is optional: the color variants come out the same without it.

Two things for the owner to decide before the repository goes public:

- **Old commits still hold `.glb` files** (124 of them: level meshes and models, added before they
  were generated at install). Removing them from GitHub means rewriting the history (for example
  `git filter-repo --path-glob '*.glb' --invert-paths`) and force-pushing, after which every clone
  must be made again. Not done.
- **The texture pack zip** (`docs/modding/current_mod/texture_packs/`) holds textures of the games,
  repainted. It is committed so that the release workflow finds it.

## 8. Building and testing

```bash
task set-game-jak3
task build-release-game       # the level builder and the runtime changed
task build-release-decomp     # the decompiler changed
task level-port -- custom_assets/jak3/ports/jak2-haven-city/port.jsonc
task compile-check            # headless (mi)
task boot-game                # debug boot; task boot-game-retail for the launcher's
```

After switching to this mod from another one in the same clone, force the first build with
`(make-group "iso" :force #t)`: the shared `out/` folders can hold the other mod's files.

**How changes 30 to 33 were tested.** A temporary GAME file (never committed) starts a process at
boot that switches the mod and the war on, warps Jak, moves models in front of the camera, counts
units and their targets, and takes screenshots (`pc-screen-shot`), printing `HJ2TEST` lines to the
log. A small Python script starts `gk` in debug mode (`-boot -fakeiso -debug`), reads the log and
stops the game at the end of the scenario or on a crash. The scenario process runs on the real
clock (`*display*`'s `real-clock`) so that it goes on while a menu pauses the game.

Each test run starts a fresh `gk` after the build, so it is a cold boot. The final run of change 33
was a retail boot (`task boot-game-retail`'s arguments, no debug segment): the mod and the war
switched on through the Mods menu's own entries, then 2 minutes of war. To see a vehicle up close,
the scenario puts Jak at its controls (`'change-mode 'pilot` with that vehicle): the camera follows
it.

A cold boot is the final check: code reloaded into a running game can look right while a fresh
start fails. Saves and settings stay from one boot to the next
(`%APPDATA%/OpenGOAL/jak3/saves/` and `settings/pc-settings.gc`).

## 9. Known issues

- **Not played by a player yet:** changes 30 to 33 were tested in boots driven by test scenarios,
  the last one a retail boot ([8](#8-building-and-testing)).
- **The repository's history and the texture pack** before going public: [7](#7-what-the-repository-holds-and-what-it-doesnt).
- More open points: [reference, 14](haven_city_new_dawn_reference.md#14-not-done-yet).

## Change log

Phase 1 is commit `de9ec6962`; phases 2 to 10 are commit `dd14a7829`; phase 11 is commit
`e769d5e2a`; phase 12 is commit `051725569`; phase 13 is commit `a1daec395`; phases 14, 15 and
15b are commit `a4f797fc4`; phase 16 is commit `9a8dd7043`; phases 17 to 19 are the commits that add their
rows. Phases 1 to
10 were played in game before the next one started; phase 11 was partly (the time gates both ways,
the new places through the Mods menu); phase 12 was partly: the Freedom HQ sequence that crashed
(Jak 3's city, the HQ's elevator, its time gate to the hideout) works. The rest of phase 12 is built
(`(mi)`, `fr3_check` and the lints clean) but not played yet. Phase 13 changes no level: its files
were checked against phase 12's, and `(mi)` builds them. Phase 14 was played once: the district
loading holes and the traffic over the void found then are fixed in phase 15. Phase 15 was played
once (the user's second test): what it found is fixed in phase 15b, which is built (`(mi)` clean,
`fr3_check` finds 0 errors on every level) but not played yet. Phase 16 is built (`(mi)` clean,
the audio copied and packed) but not played yet. Changes 29 to 33 were tested in debug
boots driven by temporary test scenarios ([8](#8-building-and-testing)).

| Phase | Asked | Done | Problems found: cause, fix |
|---|---|---|---|
| 1 | The whole city, walkable | `import_fr3`, `fr3_check`, Mods menu warp | Collide hash over 65535 items: `collision_bounds`, adaptive grid. Triangles lost far from the origin: local tests. First-frame crash: an empty TIE tree. Imported trees culled: all-visible list. `bg` from Jak 3's city fails: warp through a continue |
| 2 | Grey sky, no water | Jak 2's weather ranges, `sky` flag, ocean map, water regions, shrubs | Black 3D view: fog z equal to w. Jak fell through the water: the ocean region needs a placeholder argument |
| 3 | Interiors and the places around the city | Door scripts (`pair` and `string` lumps), `gen_havenj2_links.py`, the first places, respawn process | Door art missing: art groups listed per level |
| 4 | Follow Jak 2's loading exactly | Region scripts and translator, one level per place, memory modes, palace gate model, props mesh, time of day | Grey, flat light: frozen noon, now 16:00 |
| 5 | Props, speakers, particles, weather, cameras | Props as Jak 3 actors, propaganda speakers, particles and neon signs, weather menu, fixed cameras, story prototypes, pumping station, mountain, Haven Forest | Huge props: Jak 2 ignores the scale lump. Link error: a type's parent must be linked first in GAME |
| 6 | Doors, elevators, platforms, squares; prepare traffic | Jak 2's elevator model, platforms with convex hull collision, crates, prop particles, navigation data export and `nav_data` | Square particles: the sprite page was dropped on deactivation |
| 7 | City traffic | Jak 3's traffic code and art in HJ2, traffic callbacks, Mods menu switch | Faction manager `break!`: removed, `guard.gc` check. Nav mesh binary search: sorted by aid |
| 8 | Traffic crash, palace door | Attack controller, never-spawned actors filtered | First guard called a method on `#f`: allocate the attack controller. The palace door that "never opens" doesn't exist in Jak 2 (`kill-mask` never) |
| 9 | More traffic without blinking; the dig site; the port's air train | Jak 2's densities, 50 m cells with whole-cell spheres, castle pad and dig with their platforms, `hj2-air-train` | Traffic blinking: small spheres and empty cells made cells leave the active set |
| 10 | Weather everywhere, particle fixes, air train cutscenes, a time gate, warps | Weather driver and 8 weathers, texture id and flag remaps, 4 cutscenes, time gate, district and key place warps, `write_if_changed` | Squares: Jak 2's `effects` id is Jak 3's font page. Fountains: flag bits moved. Weather menu dead after a Jak 3 level: the weather was released to Jak 3's boot sky and nothing restored the choice, now held every frame |
| 11 | Palace respawns and elevator death; air train as a teleport; real teleporters between the Freedom HQ and the hideout; Jak 2's respawn points; construction site models; speakers breaking like Jak 2's; Dead Town's water, bars, slabs and hut; Haven Forest; the fortress and the stadium; no garage doors; farm crops; saves | Respawn by the level Jak is in, Jak 2's continue flags; air train fade; two `hj2-time-gate`s and their arrival points; silo doors and bomb elevator; two-hit speakers with three looks; ocean maps of Dead Town and the mountain, Dead Town's platforms, beams, flag, swing poles, Sage's hut; particles of the forest and Dead Town; animated texture slots mapped; ocean order; fortress gates, fortress and stadium levels; `hj2-farm-*`; save mark and slot label | Elevator death: the roof's door ran `on-deactivate` at load and turned the pillar off, script removed. Fortress gate shut: a branch of another story state named an unported level, `strict_notice`. Level names over 10 characters: renamed. Place sprite pages sharing texture pool slots with the city's: ids 1594 and 1627 |
| 12 | The crash of the Freedom HQ's time gate after walking in from Jak 3's city; Dead Town as one level with its hut; Jak 2's load mode for every level; every Jak 2 door to a level working; each level's elements in their most advanced state (the end of Jak 2); the prison | The hut merged into Dead Town (`merge`); Jak 2's memory modes placed exactly in Jak 3's heap (`memory_modes`); the end of the game everywhere: actors from Jak 2's story task masks (`jak2_actors.py`), background prototypes, the palace plaza's broken statue and wall; the fortress's escape (prison, way out, their gates); crates, swinging bars and slides in every place; a crash report in `gk` ([4.4](haven_city_new_dawn_reference.md#44-crash-report-gk)) | The hut missing near the city: it was a level of its own, loaded deeper in. Jak 2's Dead Town has no slabs, floating platforms, bridge or flag at the end: their ports removed. A merged level shown and hidden by the other's scripts: dropped (the translator's `source`). A `water-vol` without `water-height`: the top of its box. The Freedom HQ crash (only after its elevator, the HQ then in the top chunks): the HQ's borrowed `lfreeout` sat past 256 MB, its shaders were linked to wrong addresses, and unloading `freecast` wrote into GAME's code (`nav-mesh` `init-from-entity`), run at `havenj2`'s login. Found with the crash report and a write watch on that code: `DEBUG_LEVEL_HEAP_MULT` 10.0 keeps the level heaps below 256 MB ([11](haven_city_new_dawn_reference.md#11-memory-and-performance)) |
| 13 | Generic, reusable tools instead of the scripts of the havenj2 folder (Jak 2 → Jak 3 now, Jak 1 → Jak 3 and other directions later), with as little mod-specific code as possible; the level editor's submodule removed | The level port (`scripts/level_port`: games, game pairs, steps) and this mod's manifest (`custom_assets/jak3/ports/jak2-haven-city`); the levels' build steps generated (`jak2-haven-city.gp`, loaded by `game.gp`); the submodule link removed on branch `tools/open-goal-level-editor` | Every generated file compared with phase 12's: the same data, but for the order of two models in `hj2-dig`'s DGO, the order of lump keys in `hj2-forest` and `hj2-ruins` (the level builder sorts them) and the name of the palace gate's collision mesh (build-actor only prints it). One file had Windows line ends, now the same as the others |
| 14 | The city split like Jak 2's (the low-res city seen from the palace lobby); Jak 2's Hellcats in the traffic | The hub `havenj2` (Jak 2's `ctywide`, `small-center`, `not-physical`) and 15 district levels from the template `city-district` (`small-edge`, `display-wait`), Jak 2's load sets ([5](haven_city_new_dawn_reference.md#5-the-city-levels), [6.2](haven_city_new_dawn_reference.md#62-the-levels-and-their-memory)); the level port's `level_templates`, `hub`, `level_flags`, `nav.sources`, `particles.levels`, `hubs_var`, the hub first in every level list (`with_hubs`), Jak 2's district display scripts kept, the hub's `.jsonc` generated in full (the `section` mode and the `shown` key removed), the water step folded into `levels`, `part-engine-max` per level; districts drawing with the hub's sprite page, released at the hub's logout; respawn by hub group (`hj2-hub-of`); the Hellcats ([7.3](haven_city_new_dawn_reference.md#73-hellcats)) | The low-res city in the palace lobby: the pillar-top airlocks, born 420 m below with the default 10 km `vis-dist`, opened and showed `hj2-pcab` and `hj2-proof`; doors copy Jak 2's `vis-dist`. A district's actors need the hub's code: the hub loads first and unloads last, and stays loaded with Dead Town and the mountain (Jak 2 drops `ctywide` there). Jak 2's airlocks hide the hub while a district stays shown: the hub's sprite page is kept until it unloads. The Freedom League squad rewrites the `guard-car` target count every frame from its alert settings, which give the Hellcats none: its guard type 5 is held at 3 |
| 15 | After the first phase-14 test: districts never shown, traffic floating over the void, Hellcats chasing Jak. Every level complete like Jak 2's, with the same levels loaded: every hazard that hurts Jak, no enemies, the palace's inside as the low-res throne seen from the roof, the small places (kiosk, Onin's tent, the canyon), no orbs, the garage doors still removed | `hj2-swap-in-district` ([6.1](haven_city_new_dawn_reference.md#61-how-jak-2-loads-its-levels)); each district's own navigation (nav step `write_district`), the hub only the height map ([7.1](haven_city_new_dawn_reference.md#71-navigation-data)); the Hellcats' pursuit removed ([7.3](haven_city_new_dawn_reference.md#73-hellcats)); particles in 20 more places and the garage, `"auto"` pages and ids (`Allocator`), `skip_groups`, `defbehavior` callbacks copied ([5.3](haven_city_new_dawn_reference.md#53-particles-and-sprite-textures)); static decor in meshes, `hj2-common-obs.gc`, the palace cable's hazards, the city's actors (parking spots, force-field walls, searchlights, guard turrets, barges), the places' end states, hazards and decor ([5.6](haven_city_new_dawn_reference.md#56-city-actors), [6.12](haven_city_new_dawn_reference.md#612-hazards-and-decor-of-the-places)); the mountain's iris doors open on `hj2-mincan`, and `hj2-kiosk`, `hj2-onin` ([6.13](haven_city_new_dawn_reference.md#613-small-places)); the level port's lump kinds `string`, `symbol`, `type`, a ported actor's `art_groups` in its DGO, `ported_actors`, `region_script_overrides` for regions 429, 894, 177, 353 and 873; Jak 2's `GGA.DGO` and `ATE.DGO` extracted again with `rip_levels` | Districts never shown: some of Jak 2's loading faces can be walked around, and showing a level that isn't wanted is lost: the district asked is swapped in for a hidden one. The void traffic: the hub's merged navigation spawned it over districts not loaded; each district keeps Jak 2's own, and the engine links the 2 displayed ones. A crash going down the palace pillar (`h-bike-c`, `nav-branch` method 15): the traffic start unlinked a graph never linked, which corrupted it; only patched graphs are unlinked. Classes placed by levels loaded together (the windmills of the mountain and the cable, the flip steps of the cable and the roof) can't be linked by both: they moved to GAME |
| 33 | The war mode improved: blue guards with the rifle and grenade launcher only, more varied voice lines, guards from further away and denser, both sides attacking each other from further away, no rifle butt unless the target is Jak at close range, Krimzon Guards also targeting citizens and dying in the purple cloud like the blue guards, the war's menu entry greyed out with the mod off. The models and textures of the troop transport, the anti-air turret, the Hellcat, the Krimzon bike and the Krimzon Guard listed, with color variants: blue turrets out of the war, red and blue Hellcats, bikes and transports in it. No `.glb` in the repository, the assets still made for every player; Torn's voices kept. The README presenting the mod only, with screenshots; this guide for a developer new to GOAL | Blue guards re-armed by the director (`hj2-war-rearm-guards`); Jak 3's guard lines for the blue guards, every war line in random order; units spawn within 80 m and 180 m during the war (`hj2-war-cell-dist`); the war's hatred entries (`hj2-war-hatred-set!`); the rifle butt only on Jak (`hj2-war-melee-ok?`); the Krimzon Guards' effect control and death cloud (`hj2-war-death-start`, `hj2-war-death-fx`); `hj2-menu-flag`; `recolor` as a list of rules with a texture filter, 8 variant models, the turret's color switch, the transports of both sides in turn, the Hellcats and guard bikes flying in the war in both colors ([6](#6-color-variants)); the `.glb` files checked out of git (the port's ignore block), the history left as it is ([7](#7-what-the-repository-holds-and-what-it-doesnt)); the old technical README split into this guide and the [reference](haven_city_new_dawn_reference.md); 5 screenshots | Pooled blue guards kept their tazer: re-armed every 0.5 s. 30 guards ran out of the city's nav-controls (`unable to allocate nav-mesh`, then a crash in `setup-enemy!`): 20 kept. A pedestrian could spawn while its navigation mesh wasn't loaded: refused (`traffic-engine.gc`). The Krimzon Guards had no effect control; then the generic renderer crashed on their custom model; then the sparks were invisible (part 53 needs `merc-death-spawn`'s texture). The turret named its blue art group but drew the red mesh (`mgeo`). The war's crash (since change 31): the off-screen weapon change answered "changed" for a guard the war kept armed, which went hostile again 4 times a second; fixed in `crimson-guard-method-270`, 16 runs without a crash after it ([5.3](#53-weapons)). A third path to the rifle butt (`guard-states.gc`). The blue guards' Jak 3 lines spaced 15 to 23 s by Jak 3's tables, which silenced them: spaced copies ([5.7](#57-voice-lines)) |
| 32 | "The red and yellow guards' animations are played much too fast"; "the guards stand still after using their grenade launcher"; Jak 2's music in Jak 2's outer levels; "in the fortress, a door leading to the prison opens but overlaps another door that stays closed"; "static rain particles in the air" in Jak 2's city; the guards' lines at Jak 2's frequency, the blue guards speaking too (fight lines), never two lines at once | The places' soldiers blend their walk and run by speed (`hj2-kg-soldier-travel-anim`, Jak 3's citizen formula); a grenade guard of the war reloads twice as fast (`hj2-war-reload-speed`); the places keep Jak 2's music (the war's fight music in the cities only); the fortress gate's script fixed (`script_overrides`, `fort-entry-gate-9`); the weather's particles back on the particle clock (`hj2-weather-particle-unfreeze`); Jak 2's speech spacing and one channel at a time (`*speech-ready-hook*`, `*speech-type-hook*`, marked lines of `speech.gc`) | The rain froze: the time-of-day process launches the weather's particles on the clock the mod stops to hold the hour |
| 31 | After playing change 29: the turrets for Jak in a vehicle only, no gun on the troop transport, the Krimzon Guards' clips, the war's music, the citizens fleeing, fewer vehicles, the jetpacks' flames, the places' guards there when a place loads | The turrets keep Jak 2's rule; the transport without its chin turret, invulnerable, Krimzon Guard ships only; the red and yellow guards play the blue guard's clips (`hj2-war-guard-clips`); Jak 3's fight music for the whole war; every citizen on foot keeps fleeing (`'panic` every 0.5 s); 1 citizen and 1 vehicle of each type; the jetpack flames out of Jak 2's nozzles; the places' soldiers spawned as their level loads | A crash during the war, once in four runs without the test harness: found and fixed in change 33 ([5.3](#53-weapons)) |
| 30 | "You may launch the game yourself to test everything" | Every feature of change 29 tested in debug boots driven by a temporary test scenario (never committed, [14](haven_city_new_dawn_reference.md#14-not-done-yet)). The troop transport lands on Jak's far side from the camera (`hj2-transport-spawn`) | At its first landing the hull came down between Jak and the camera, which then showed only the hull |
| 29 | "A war mode in the mod's menu, KG-Guard vs Freedom Fighters, in Jak 2's world and Jak 3's: red and yellow Krimzon Guards from Jak 2 against the blue guards, the troop transport delivering guards of either side at times, the citizens frightened and fewer on foot and in vehicles, jetpack guards of either side at times, no Freedom League or Krimzon Guard ships but crimson bikes on the ground; in the places around the city, red and yellow Krimzon Guards on Jak 2's nav meshes in place of the entities Jak 2 put there. In Jak 2's city with the war off: Torn's voice on the speakers in French (the user's recordings), the defense turrets coming out when the alert starts and attacking Jak in a vehicle, Onin's game from her tent, Vin's game (Jak 3)" | The war mode ([7.5](haven_city_new_dawn_reference.md#75-war-mode-kg-guard-vs-freedom-fighters)): GAME switch and looks (`jak2-haven-city-war.gc`), marked hooks in `guard.gc`, `flying-turret.gc`, `kg-squad-member.gc`, `traffic-manager.gc`, `traffic-engine.gc`, its city director and Jak 2's transport ported (`levels/city/war/`, CWI and HJ2), the Krimzon Guards of the places (`jak2-haven-city-kg.gc`, the level port's `spawns`, places' nav meshes), the models built from Jak 2's data alone (`insert_joints`, `recolor`, `build_actor`, the art-only level `hj2-war`), CTYPESA and CTYPESC carrying the art in Jak 3's city. Torn's lines ([5.5](haven_city_new_dawn_reference.md#55-palace-gate-propaganda-speakers-neon-signs): `encode_vag.py`, `voice_files`, `pack-vags` file lines). The turrets' rule ([7.2](haven_city_new_dawn_reference.md#72-traffic)). Onin's game ([6.15](haven_city_new_dawn_reference.md#615-onins-bubble-game)), Vin's game ([6.16](haven_city_new_dawn_reference.md#616-vins-game): `borrow_sizes`). Built (`(mi)` clean, 3161 targets); tested in game by the agent ([14](haven_city_new_dawn_reference.md#14-not-done-yet)) | The mod's handles of its weather driver, time gate and respawn process were kept in `define`d globals, which keep 32 bits of a 64-bit handle (GOAL wiki common 1.4.17): each level activation started another weather driver and respawn process, each Freedom HQ activation another time gate. Now in a structure (`*hj2-handles*`). The level port wrote a build step for every `.gc` of the levels' code folder, so a file also in CWI was built twice: the war's city files are in `levels/city/war/`. A code review before the test: jetpack guards frozen after their first burst (the hover clip loop skipped the firing clip forever), `kg-squad-member` reading the absent faction manager in havenj2 (marked check), a war switch during a Jak 3 mission (now steps aside), parked crimson bikes without their pool, the panic's suppression boxes, Vin's game leaving Jak grabbed if killed while loading: fixed |
| 28 | "Delete the textures of the `_all` folder of custom assets to clean up the repository" | The 23 PNGs of `custom_assets/jak3/texture_replacements/_all` removed (`git rm`), with the `.gitignore` exception added for them in change 26; the pack stays in `docs/modding/current_mod/texture_packs/haven-city-new-dawn-textures-v1.0.0.zip` (sha256 `67737599…cca`, the `index.json` entry) and in the v1.0.0 release | By design, a launcher install of the mod no longer retextures anything (the guard bike, the turrets, the Hellcat, the fort and the signs keep the game's own textures); the PNGs stay in the git history (`2767c4b27` and earlier) and in the zip |
| 27 | The first launcher install of a player on Linux (a Steam Deck, Jak 2 and Jak 3 PAL) failed at the level port: `KeyError: 'animations'`, exit code 221 (4061 on 8 bits) | The decompiler's model rip no longer reads a dangling reference (`add_merc`, `fr3_to_gltf.cpp`: `node.skin` read by index); `glb.py` names the model, the rip and the animation when a borrowed animation is missing | `add_merc` kept `auto& node = model.nodes.emplace_back()` while adding one node per bone to the same vector: reading `node.skin` afterwards was undefined behavior. It worked on Windows (the freed memory kept its value) and failed on Linux for Jak 2's wren (`forest/wren-lod0.glb` ripped with no animation, then `rebuild_model` found none). Reproduced with the release's Linux extractor in an Ubuntu 22.04 container (834,356 bytes, 0 animations, against 870,256 and 7 on Windows), then fixed: the same build, patched, gives the Windows file. The Windows rips are byte-identical before and after the fix. Fixed in a release after v1.0.0 |
| 26 | "When I build the texture pack and link it to the mod, it seems tied to Jak 2 rather than Jak 3; it should be considered a Jak 3 texture pack" | The 23 PNGs moved to `custom_assets/jak3/texture_replacements/_all` (the `.gitignore` exception with them); decompiler config key `extra_texture_replacement_dirs`, folders searched after the game's own ([4.1](haven_city_new_dawn_reference.md#41-decompiler)); the level port's `extract` step passes the target game's folder when it extracts the source game, with the decompiler and with the extractor's `--decomp-config-override` (same config reader), and extracts again the source levels older than the newest PNG of either game's folder; the manifest's `texture_replacements` removed, the level builder applying Jak 3's folder by itself (the builder key stays, generic); `task modding-package-texture-pack -- --from-source` zips the Jak 3 folder (`supportedGames: ["jak3"]`) ([3](haven_city_new_dawn_reference.md#3-rebuilding-it-step-by-step)) | Extracting the 51 Jak 2 DGOs again logs every replacement from `custom_assets\jak3\texture_replacements\_all` (`city-fort-*`, `sign-crimson`, `sign-praxis-banner`, the guard bike's, the turret's `kgt-gun05`, the Hellcat's in Jak 2's atoll pages); the forced build replaces the 8 Hellcat textures of `hellcat-ag` (`desoasis-pris`) from the same folder. Side effect, by design: every Jak 3 extraction (the launcher's Decompile of this mod, `task extract`) applies the pack to Jak 3's own levels, so a texture of the same name (the Hellcat's in Jak 3's cars, `sign-crimson`, `city-fort-*` in Jak 3's slums) changes in Jak 3's own city too; `out/jak3` is shared by the Jak 3 worktrees, so Jak 3 wasn't extracted again here |
| 25 | In the hideout (`hj2-hide`), "the lamp over the central table shows its light as a big opaque dark-brown pyramid covering the table" (in Jak 2 a translucent light shaft) | The decompiler's rips keep a material's blend when it isn't the usual alpha blend (`"extras": {"ps2_alpha_blend": N}`, `fr3_to_gltf`, [4.1](haven_city_new_dawn_reference.md#41-decompiler)); `gltf_util::setup_alpha_from_material` applies it, for `build-actor` and the level builder; `build-actor` puts a model's translucent draws in a merc effect of their own, given texture-index 3 by Jak 3's `build-actor` (the alpha merc bucket, after the opaque geometry) ([4.2](haven_city_new_dawn_reference.md#42-level-builder)); the mesh step's props keep their rip material's `extras` (`glb.Glb.material`, [5.2](haven_city_new_dawn_reference.md#52-props)); the extract step also checks the rips of the models' `extras` (`hj2-hide-light-fog` is one); `fr3_check --draws` lists the merc draws with their blend ([4.3](haven_city_new_dawn_reference.md#43-fr3_check), [6.7](haven_city_new_dawn_reference.md#67-rebuilding-jak-2s-models)) | The cone is `hj2-hide-light-fog`, Jak 2's `hide-light-fog-lod0` rebuilt by `build-actor` and spawned on the lamp's bottom joint by `hj2-hide-light`. Jak 2 draws its one texture, `hideout-water/hidelight-ramp` (4x16, a brown ramp from (119, 90, 54) at the top to black, alpha 128 everywhere), additively: `fr3_check hideout.fr3 --draws "merc hide"` gives `ab 3` (`SRC_0_FIX_DST`, source plus destination). The rip only said `alphaMode: BLEND`, which `setup_alpha_from_material` turns into the usual alpha blend; with the texture's alpha of 128 (1.0) the cone was an opaque brown. It was also in the opaque merc bucket: Jak 3's `build-actor` writes texture-index 0 for every effect, Jak 2's cone is in the water bucket. Of all of Jak 2's `.fr3` files, the merc draws with a blend other than alpha (all `ab 3`): `hide-light-fog`, `searchlight` and `security-wall` (`ctywide`, `palcab`; the port uses Jak 3's art groups), `stadium-barrier`, `collectables-bomb-blast`, `precursor-stone`, `kor-break`, `kor-break-ray`, `kor-transform-monsterparts`, `metalkor-highres-wings`, `keira-highres` (her mask), `mech`, `mech-explode`: none of the others is rebuilt by the port, and no mesh prop is additive. The hideout rip extracted again (`HIDEOUT.DGO`), the port run, `task compile-check`: 1251 targets built, `hj2-hide-light-fog`: "1 translucent" draw |
| 24 | Haven Forest's particles drawn as squares, "like the smoke before"; the Baron's speaker logo blue like its halo, with the user's new texture `_all/baron-propoganda-logo.png`; "remove the terminals (question marks) in Jak 2's city"; the race posters spread around the city, at Jak 2's exact places, with `race-sign-04` instead of `race-sign-03`, as at the end of Jak 2; "Keira's garage doesn't spawn" | `hj2-sprite-page-register` (GAME, `jak2-haven-city-world.gc`): 11 registration slots, the level's own reused, else an empty one or one whose level is no longer loaded ([5.3](haven_city_new_dawn_reference.md#53-particles-and-sprite-textures)); `part_specs` 818 and 821 (the logo) blue, Jak 2's colors with red and blue swapped ([5.5](haven_city_new_dawn_reference.md#55-palace-gate-propaganda-speakers-neon-signs)); the pool slots of every mod page checked against all 326 Jak 3 `.fr3` files ([5.3](haven_city_new_dawn_reference.md#53-particles-and-sprite-textures)); texture notes ([3](haven_city_new_dawn_reference.md#3-rebuilding-it-step-by-step)); Jak 2's mission terminals (`burning-bush`) dropped from the manifest: no mesh prop, no hologram spawner (`kiosks`), no `extra_groups` array; the mesh step writes no glb, and the levels step no `gltf_file`, for a level with nothing in its mesh ([5.2](haven_city_new_dawn_reference.md#52-props)); `hj2-birth-func-race-poster` (`particle-callbacks.gc`) takes userdata entry 6, `race-sign-04` ([5.3](haven_city_new_dawn_reference.md#53-particles-and-sprite-textures)); the garage's camera volume (Jak 2's region 776, the one that makes it Jak's level) shows the garage as the camera enters, like the removed doors' `on-enter` (swapped in by `hj2-swap-in-district` when a script dropped it), and makes the stadium grounds Jak's level again as it leaves (`region_script_overrides`, [6.3](haven_city_new_dawn_reference.md#63-doors-and-elevators)); `hj2-note-asked` (GAME, `jak2-haven-city-world.gc`) also notes this mod's places, not only the districts | Squares: the sprite page table had 8 slots, taken for good by the first 8 levels with a page (15 have one), so from the 9th level visited on the page was never registered and the level's particles found no texture; the forest's texture groups (bigpuff, explosion-nebula) were already remapped, and its page 1594 shares no pool slot with GAME, another mod page or any Jak 3 level loaded with it. The logo: Jak 2's texture is grey (black background, alpha 128), and its red is the tint of parts 818 (r 192, g and b 0 to 64) and 821 (255, 32, 16); the user's PNG (2048x2048, grey, background grey 86 and alpha 255) was already in `ctywide.fr3` and in `havenj2.fr3`'s page 1566 (`fr3_check --textures`). Terminals: the "?" is the `burning-bush-off` sprite (`ctywide-sprite`) of `group-ctywide-burning-bush-holo-off`, the hologram the port put over each of Jak 2's 23 `burning-bush` kiosks, whose model was a mesh prop; once they were gone, 10 districts had an empty mesh and the builder failed (`invalid vector subscript`). Posters: Jak 2's `birth-func-race-poster` picks entry 3 + (`-03` by default, 3 once `stadium-race-class1-resolution` is closed, 0 after class 2, 1 after class 3) of the part's userdata; the port's copy kept the default (entry 5, `-03`); the 34 spawners' positions and quaternions match Jak 2's entities, and the 4 textures were already in page 1566 (`race-sign-04` index 8). Garage: the only log that reaches it (`jak3.2026-10-07T17-58-27.log`) shows region 1319 loading and showing it (Jak at 187.5 -542.8), then 5 s later `hj2: hj2-genb wanted in place of hj2-garage, ahead of Jak` and `Discarding level hj2-garage`: `hj2-load-ahead` took its slot (`hj2-genb`'s ground lies 25 m north of the garage) and nothing loaded it back, Jak 2's doors having been the ones that showed it. Commit b8a1767a5 (a shown place is never swapped out) already blocks that; its "asked for by a script" half never worked for places, since `hj2-note-asked` dropped every level that isn't a district. The garage's camera volume made it Jak's level (`want-vis`) and nothing reset it outside, so after leaving it the district guard stayed off (`not-in-city`). The warp (`hj2-garage-start-skate`: `havenj2`, `hj2-stdm`, `hj2-garage`, a small-center and two small-edge levels) fits the heap; `fr3_check hj2-garage.fr3`: 0 errors |
| 23 | The time gates of the hideout and the Freedom HQ seen side-on from their room: "it should face Jak more"; "door sounds are missing: the palace's big gate, the underground hideout's door, and the platforms that fall" (the palace cable's); then: the same check for every model rebuilt from a Jak 2 rip; then: "Import Jak 2's Hip Hog mini-game into Jak 3" (Whack-a-Metal-Head, no task, a best score per session); then, after a first game: "the stand is too big compared to its dimensions in Jak 2", "the scores are supposed to show on the screens", "the game must be identical to Jak 2 visually and in its mechanics", "the game can be interrupted by pressing a button"; then, after playing: "R3 must quit a game, with a hint at the bottom of the screen", "when I press triangle to start the game, Daxter immediately strikes the triangle hole"; then: "sometimes, while it rains, if I set the sunny weather (Mods menu > Weather), the rain particles freeze on screen: they no longer fall but stay visible" | Each gate's opening (its local x) turned toward its arrival point and the room: the hideout's `new_teleporters` `facing` (−0.692, −0.722), the Freedom HQ's `*hj2-hq-gate-yaw*` −155.3° ([9.2](haven_city_new_dawn_reference.md#92-time-gates)); the palace gate, the hideout's doors and the fortress gates ask for their bank and wait for it up to 2 s before opening (`*hj2-door-sound-banks*`, `hj2-door-sound-bank-ready?`), loaded first among the extra banks for 15 s (`hj2-update-extra-sound-bank`); the falling plats play their animations' `pal-falling-a`, `-b`, `-c` at Jak 2's frames ([8.4](haven_city_new_dawn_reference.md#84-sound-and-music)); the guard turret plays `guard-turret-up` as it rises and the gun buoy `buoy-guns-out` as it opens its guns; the sound check (`--steps sound`) lists every rebuilt model's animation sounds (`art_group_effects`, `anim_sounds` in `sound_check.py`; `RAW_OBJ` in `games/jak2.py`): played by the class, `UNPLAYED` or `NOBANK` ([8.4](haven_city_new_dawn_reference.md#84-sound-and-music)); the Hip Hog's Whack-a-Metal-Head ([6.14](haven_city_new_dawn_reference.md#614-the-hip-hogs-whack-a-metal-head)): `hj2-hiphog-obs.gc` (the cabinet, the game with Daxter, the metal heads and their gold twin, the hammer), the cabinet out of the Hip Hog's mesh and placed from Jak 2's actor, `lwhack` merged into `hj2-hiphog` (its camera), Daxter's model baked into Jak 2's `LWHACK` rip (`jak2_config.jsonc`), `whack.gc`'s particles, Tess's 54 lines, the `danger3` music; the level port's `extra_parts`, `sound.music`, `part-tracker-track-root` as a Jak 3 callback, `borrow` sources ignored by `memory_modes`, blend shape weights dropped from rebuilt animations; the cabinet's prejoint scale given back by `rebuild_model` (0.64, read from its bind pose), the hammer's animations rebuilt at Daxter's 30 frames per second (the model spec's new `anim_fps`), the cabinet colliding with Jak 2's three spheres instead of its model's box ([6.14](haven_city_new_dawn_reference.md#614-the-hip-hogs-whack-a-metal-head)); R3 quits a game (`hj2-whack-quit?` in the active and attack states, hint through `hj2-print-travel-prompt`, a new `quit` state: no Tess line, best score untouched, the usual fade and exit cleanup), and the start of a game clears the hit buttons and R3 from the pad's last 3 frames of presses ([6.14](haven_city_new_dawn_reference.md#614-the-hip-hogs-whack-a-metal-head)); a weather picked in the Mods menu, and the Mod enabled switch, take effect when the menu closes: `hj2-apply-weather` and `mod-jak2-haven-city-set-enabled` skip `hj2-weather-update` while `(paused?)`, and the weather driver (paused too) switches on the first frame the game runs again ([8.3](haven_city_new_dawn_reference.md#83-weather)) | Both gates had their local z toward the room; the warp gate's opening faces its local x, where Jak 3 puts its own arrival points (`vinroom`, `templex`, `templeb`, `volcanox` continues against their `warp-gate` entities); the door classes already played Jak 2's sounds, but their banks (`PALCAB1`, `HIDEOUT1`) were not loaded where the doors open: Jak 2 wants them only past the door, and in the city the traffic's 3 banks took the free slots before the level banks (the logs: no `j2palca1` load on entering `hj2-pal`, `j2hideo1` unloaded on leaving the hideout). The falling plats' own `pal-fall-plat` (`PALCAB3`) played; their other sounds are `effect-name` tags of Jak 2's animations (`pal-falling-plat-ag.go`, read from its `res-lump`s), which `build-actor` models don't carry. Same loss, not fixed: `cty-guard-turret`, `gun-buoy`, `yakow`. Of the 97 rips, 5 art groups have such tags: the falling plat, the turret, the buoy (its `buoy-guns-in` already played by code), the yakow (all its tags, `yakow-idle`, `yakow-grazing`, `yakow-kicked`, the steps, are in no bank of either game: silent in Jak 2 too), and `cty-guard-turret-button` (`gturret-button` on a press; the fortress buttons never go down). The parser reads the v4 object's link tables as the decompiler does (the v2 link header after the data is 12 bytes); Daxter's rebuilt model failed in build-actor ("animated node not in our skeleton"): his animations carry his face's blend shape weights on the mesh node. Part 3334 names `vinroom-sprite`'s `screen-00` (its first frame, the next ones are `whack-screen-*`): the Hip Hog's particles also read `vinroom`'s textures. Every whack sound is in `HIPHOG1`, but `whack-dizzy` (no bank). The decompiler's rips leave out each animation's first two joints (align and prejoint, matrices in the game: `add_animation_to_gltf` starts at joint 2); the cabinet's idle animation scales its prejoint by 0.64 and its other joints by 1.5625, so without the prejoint the cabinet, its holes and its scoreboards were 1.5625 times Jak 2's size next to Daxter and the metal heads (evidence: its main joint's bind pose is 0.64 times its idle pose, and the hammer's lowest points of its 8 swings fall on the holes scaled by 0.64), and the scoreboards' joint matrices kept a 1.5625 scale, from which the 3D particles take a rotation quaternion (likely why the screens stayed blank). Of the 97 rips, only the cabinet has such a prejoint. The hammer cloned Daxter's frame numbers on animations twice as short (its rip at 60 frames per second, his at 30). No button path ending a game was found in the code (Jak 2 has none, only its `*cheat-mode*` L1 and R1): not reproduced, the button to be named. The start press bug: the game reads presses from the last 3 frames (`button0-rel` 0 to 2, like Jak 2's `whack-a-metal-method-26`), and here the game starts 0 to 2 frames after the cabinet's triangle press, which Jak 2 never hit since its game starts after a talk. Jak 3's font has no R3 glyph: the hint uses the stick glyph and "R3", like the PC controls menu (`progress-generic-pc.gc`). The frozen drops: the Mods menu pauses the game (master mode `menu`), `part-clock` has `menu` in its mask so its `tick!` leaves `sparticle-data x` at 0, and `sp-process-block-2d` then skips the motion and the timer of every particle, while the mood still computes the sky and the rain amount: the sunny sky came at once, Jak 3's rain drops (parts 38/39, `update-rain`) hung in the air until the game resumed. Jak 3 never kills its rain drops (no launch control, 3-second timer, killed at the ground by `check-drop-level-rain`), so the fix keeps its stop path: the drops in flight fall once the game runs. Same for snow and for the return to the changing weather |
| 22 | Texture pack: the user's 22 PNGs in `custom_assets/jak2/texture_replacements/_all` (Jak 2 names) used by the mod, in development and at a launcher install | `TextureDB` takes several replacement folders, first match wins ([4.1](haven_city_new_dawn_reference.md#41-decompiler)); the level builder's `texture_replacements` key adds other games' folders after Jak 3's for the Jak 3 art groups it extracts ([4.2](haven_city_new_dawn_reference.md#42-level-builder)); the level port's manifest key of the same name, written into every level's `.jsonc`, set to `["jak2"]`; this worktree's `decompiler_out/jak2` and `out/jak2` made local, filled by the port's `extract` step through the extractor (50 DGOs, 110 s) ([3](haven_city_new_dawn_reference.md#3-rebuilding-it-step-by-step)) | Jak 2's extraction applies the pack to what comes from Jak 2: the backgrounds (`city-fort-*` in `ctysluma`/`ctyslumb`, `citywide-redwall`, `consiteb-barrel-01`), the sprite pages (`sign-crimson`, `sign-praxis-banner`), the rips (`kgt-gun05` on the city turret, `kcbackjet01`, `kcfrontgard01`, `kcfrontend01` on the guard bike). The Hellcat is Jak 3's `hellcat-ag`, extracted by the level builder with Jak 3's folder only: its 8 textures of the same names (`wing01`, `wing02`, `dash01`, `hood01`, `jetTop01`, `backThing01`, `kcfrontend01`, `stripe03`, page `desoasis-pris`) now take Jak 2's PNG. `barrel01`, `cas-crimson-barrel`, `tcas-kg-logo-01`, `thrm-banner-01` match nothing: their Jak 2 levels (`castle`, `throne`, `ctyasha`, `fordumpc`, `lwidesta`) aren't ported. The shared Jak 2 extraction already held 10 of the PNGs (the main folder has them), so the guard bike looked the same. The extractor needs the disc's `buildinfo.json`, which the copied `iso_data/jak2` lacks: a stand-in folder for the `extract` step. The fresh camera dumps add `hj2-digb`'s camera region (`camera-258`) |
| 21 | Installable from the launcher with nothing else to do: the Jak 2 content made on the player's machine, from the launcher-installed Jak 2, during the install | The extractor's `run_level_ports` before the compile ([4.6](haven_city_new_dawn_reference.md#46-launcher-install)), error codes 4060 and 4061; `level_port` options `--root`, `--iso`, `--extractor`, `--fr3-check` (dev defaults unchanged); the release builds `level_port` (PyInstaller) and `fr3_check` when a port manifest exists | The rip folders and source levels left out `textures_from` and `backdrop_levels` (`sewer`, `palout`): the extract step reads every level the manifest names whose DGO is on the disc. PyInstaller missed the manifest's dynamic imports: `PYTHONPATH=scripts` at build time. Checked on a fake launcher install (Windows): 300 of 306 generated files identical to the dev ones; the others differ by the dev checkout's untracked Jak 2 texture replacements, an older camera dump, and the build file's absolute sound paths |
| 20 | The Freedom HQ's time gate lost its base (its halo and jump still worked); level loading "still too slow at times", Jak 2's city sector loading imperatively respected; during the alert some sounds disappeared at times (turret shots, the guards' tazer and rifles, the vehicles' shots); the palace plaza as at the start of the game, without access to Mar's tomb; the draw range of the level elements too short (signs, the bazaar's baskets); the street poles near the stadium destructible like in Jak 2; the halo of the Baron's propaganda speakers blue; then the Baron's intact statue gone from the plaza; then the prison never reached from the fortress ("the door opens but another overlapping door stays closed"); then on the way out of the fortress, the plates Jak breaks with a dive attack missing, and Jak's slide down the ramp near the end missing; a smaller Mods menu (the mod's switch, then the warp to Jak 2's city, the warps by district, the warps outside, the weather), the guard vehicles and Jak 2's alert always on, no warp to the way out of the fortress, its trap doors whole again each time it loads; then "still many levels loading at the last moment" and, by the stadium, a level never loaded (Jak on a vehicle over the void, `log/jak3.2026-10-07T13-14-52.log`); then still districts showing late (one loaded but shown only once Jak stood on it; the slums from the industrial section loaded only once Jak was on them); then the palace plaza still loading under Jak, walking from the port; the guards' grenade launchers gone (wanted above the tazers' alert level); then levels overlapping and the stadium and the slums swapped back and forth; then "some object sounds are missing in the levels; every level must have all of its sounds, completely" | The level port's `extract` step extracts again any Jak 3 DGO whose `.fr3` lacks a model of `extra_art_groups_by_dgo` (`missing_baked_models`, `fr3_check --models`); its decompiler run with an absolute path ([9.2](haven_city_new_dawn_reference.md#92-time-gates), [4.3](haven_city_new_dawn_reference.md#43-fr3_check)); the loading of the city measured against Jak 2's (on PC: the same load-state logic, the renderer's `Loader` shared by every game) and Jak 2's scripts made the only ones to load and show the districts: phase 19's preload and showing ahead removed, the PC renderer loading the geometry of the districts near Jak ahead of the game (`*pc-renderer-prefetch*`, a vanilla `level.gc` edit, `hj2-renderer-prefetch`) ([6.1](haven_city_new_dawn_reference.md#61-how-jak-2-loads-its-levels)); the guards' bank `cityffh` wanted with whichever Jak 2 banks are wanted (`hj2-update-extra-sound-bank`), two overlord bank record fixes (`sbank.cpp`) ([8.4](haven_city_new_dawn_reference.md#84-sound-and-music), [4.5](haven_city_new_dawn_reference.md#45-sound)); the level port's `story.level_open_tasks` (story nodes open for one source level: its actors, background prototypes and scripts), Jak 2's prototype conditions (`STORY_PROTOTYPES`) and the actors hidden by their own code (`ACTOR_SHOWN_AFTER`) in `games/jak2.py`: the plaza before Mar's tomb is found ([6.8](haven_city_new_dawn_reference.md#68-the-end-of-the-game)); the props' and part spawners' `max_vis_dist` caps removed from the manifest: Jak 2's `vis-dist` everywhere ([11](haven_city_new_dawn_reference.md#11-memory-and-performance)); the street lamps (`ctyn-lamp`, 42 in `hj2-gena`, 42 in `hj2-genc`) left the district meshes for an actor, `hj2-ctyn-lamp` (`havenj2-obs.gc`, [5.6](haven_city_new_dawn_reference.md#56-city-actors)): Jak 2's pole and 4-piece explode model rebuilt by `build-actor`, snapped by any attack or vehicle; the speakers' halo and projector flare blue through the particle step's new `part_specs` (init-spec values replaced per source part, [5.5](haven_city_new_dawn_reference.md#55-palace-gate-propaganda-speakers-neon-signs)); the intact statue: `ctywide` added to `level_open_tasks`, the actors killed by their own code once a story node is closed (`ACTOR_GONE_AFTER`: `baron-statue`) and `baron-statue` baked into `havenj2`'s mesh ([6.8](haven_city_new_dawn_reference.md#68-the-end-of-the-game)); the doors of this mod's levels wait, shut, for the PC renderer to have the levels they show before they open (a wrapper of `com-airlock`'s `destination-loaded?`, `hj2-renderer-pending?`), so a door's level is shown as it opens ([6.1](haven_city_new_dawn_reference.md#61-how-jak-2-loads-its-levels), [6.11](haven_city_new_dawn_reference.md#611-the-prison-and-the-way-out-of-the-fortress)); the way out's trap doors (`hj2-fort-trap-door`, `hj2-fexb-obs.gc`: Jak 2's `fort-trap-door` on Jak 3's `fac-break-floor` pattern, its model and explode model rebuilt) and Jak's slide (`target-tube.o` in `hj2-fexb`'s `code`, `jak-tube+0-ag` in `art_groups` for `slide-control`) ([6.11](haven_city_new_dawn_reference.md#611-the-prison-and-the-way-out-of-the-fortress)); the Mods menu rewritten ([9.1](haven_city_new_dawn_reference.md#91-mods-menu)): `*mod-jak2-haven-city-enabled*` (off by default) gates the Freedom HQ's time gate and the weather, the other entries greyed out while it is off; Hellcats and guard bikes on by default, the traffic, Hellcats, guard bikes and alert entries removed (always on); the hideout as the city warp; `hj2-fort-trap-door` no longer calls `cleanup-for-death` (hidden and asleep until `hj2-fexb` unloads); the district map built from each district's collision ground (`fr3_check --squares`, the levels step's `ground_squares`), the traffic cells only where no district has ground; the district guard loading the district Jak will be over in 1.5 s hidden, at most every 3 s; the log printing the scripts' level lists and display requests and the guard's state, with where Jak is ([6.1](haven_city_new_dawn_reference.md#61-how-jak-2-loads-its-levels), [4.3](haven_city_new_dawn_reference.md#43-fr3_check)); the district guard shows a loaded hidden district under Jak or 1 s ahead at once (`hj2-show-if-loaded`) and loads the district 1 s or 2.5 s ahead in place of any district but the one under Jak (`hj2-load-ahead`) ([6.1](haven_city_new_dawn_reference.md#61-how-jak-2-loads-its-levels)); the guard also loads the nearest district whose ground is within 50 m (`hj2-near-district`); grenadiers at alert levels 2 to 4 (1, 2, 2) in `*hj2-alert-level-settings*` ([7.2](haven_city_new_dawn_reference.md#72-traffic)); the look-ahead capped at 60 m, districts shown or recently asked for within 100 m never swapped out, a loaded district shown early only within 25 m (`hj2-district-within?`); the level port's sound check (`steps/sound_check.py`, the `sound` step): the part spawners' `effect-name` lumps and the particles' `:sound` kept, the Jak 2 banks each level's content needs besides its wanted ones (`*hj2-level-sound-banks*`) loaded in the free half bank slots by `hj2-update-extra-sound-bank`, the castle pad elevator's own sounds, the added continues given the banks of their nearest continue ([8.4](haven_city_new_dawn_reference.md#84-sound-and-music)) | `freehq.fr3` (2026-10-04 22:05, with every other Jak 3 `.fr3`) came from a Jak 3 extraction made with a config without `extra_art_groups_by_dgo` (master-dev's or another Jak 3 mod's: `out/jak3` is shared by every worktree): its merc models had no `warp-gate-lod0`, while `warp-gate-ag.go` was still in FREEHQ.DGO, so `hj2-level-has-art?` let the gate spawn with no geometry to draw. FREEHQ.DGO extracted again: `warp-gate-lod0` is back. The step's `subprocess.run` of the decompiler by a relative path failed on Windows (`FileNotFoundError`); slow loading: the game loads a district in 0.05 to 0.3 s, the renderer its `.fr3` in 1.5 to 2.5 s (as in Jak 2, where the faces load seconds ahead), and the phase 19 preload fought Jak 2's scripts: `hj2-marka` and `hj2-port` swapped back and forth, `hj2-gena` and `hj2-genb` (loaded by Jak 2's faces 294 and 130) evicted, then loaded back by the guard; the showing ahead showed a market Jak 2 had just hidden. The hub's `.fr3` is 15.5 MB (1342 textures) against `ctywide`'s 2.4 MB: entering the city waits about 2 s for it; missing alert sounds: all are `guard-shot-fire` or `guard-zap`, in `cityffh`, `CTYWIDE3` and `CTYFARM1` only; `cityffh` was wanted only with `j2ctywi3`, and the overlord skipped reloading a bank it had unloaded (`LookupBank` ignored `in_use`) and failed half banks whose partner wasn't in its first record pair (a decompiled loop whose index never moved): `CITYFFH.SBK` read once in a session that loaded it four times, `j2ctywi3` never read again after the Freedom HQ; the plaza: Jak 2's `level-method-22` shows the wall under the Baron's statue and hides its rubble until `canyon-insert-items-shard` is closed, the broken statue (`no-draw`) and broken wall (left at the origin) wait for `canyon-insert-items-resolution` in their own code (`ctypal-obs.gc`), as does the tomb airlock's `on-notice`; the draw range: Jak 2 draws the market props up to their `vis-dist` lump (140 m: `setup-lods!` takes it for a 999999 m last lod, Jak 3's too) and births actors by its visibility data alone (the lump only counts without it), its signs are part spawners with a 384 m `vis-dist` (600 m in the port); phase 15b's caps (80 m props, 150 m spawners) made them vanish early; lamps not breaking: they were baked into the mesh as a `post` collision. Jak 3's vehicles never send `attack` to what they touch (their `touch-handler` does nothing), only `impact-impulse` from `rigid-body.gc`: the lamp handles both. The halo is particles (parts 819 and 822), not a texture; the intact statue is not the plaza's: it is `ctywide`'s `baron-statue` actor (250 m high, killed by `init-from-entity!` once `canyon-insert-items-resolution` is closed, `ctywide-obs.gc`), never ported since the port was at the end of the game; hiding the end's broken statue left the wall empty; the prison: `fort-entry-gate-11` (in `hj2-fortb`) and `fort-entry-gate-20` (in `hj2-prison`) stand back to back 2 m apart, and each opens toward Jak's back only once the other has set its `subtask-complete` (`next-actor`, Jak 3's `want-cross-airlock?` as Jak 2's). Gate 11 waits for the prison to be loaded, then shows it and opens; phase 19's `hj2-display-wait?` kept the prison hidden until the renderer had its 7.3 MB `.fr3`, up to 6 s (gate 9 loads the prison about when Jak reaches gate 11), and Jak 3's open state shuts a door whose level isn't shown, so gate 11 opened and shut in turn while gate 20 didn't exist yet. Jak walked through gate 11; when the prison appeared, gate 11 (Jak behind it) waited for gate 20 and closed, gate 20 (Jak behind it) waited for gate 11: both shut for good. It worked on 2026-10-06, before phase 19 (`log/jak3.2026-10-06T11-43-21.log`: `hj2-fortb`, then `hj2-prison`, then `hj2-fexa` walked through); the trap doors were left out on purpose (Jak 2 marks them dead once the escape breaks them); the slide: `slide-control` is defined by `target-tube.o`, which Jak 3 links only into `PRECC` and `VOCA` (Jak 2: `FEB`), not GAME, so `hj2-fexb`'s slide entity had no class and was never born, and Jak's tube animations (`jak-tube+0-ag`) were missing too ; the user's layout; the stadium: the only faces loading and showing `hj2-stdm` are `hj2-genb`'s 1130 and 1131, which run only while `hj2-genb` is shown, and `hj2-genb` is shown only by the camera face 1117 of `hj2-gena` (a street 300 m from the stadium). Jak came from the main town's north side (the log: `hj2-gena` shown, `hj2-genb` loaded hidden, the renderer loading `hj2-stdm` ahead), where the stadium's ground runs 250 m west of its streets (rows of squares the traffic cells gave `hj2-gena`): the guard saw Jak over a shown `hj2-gena` and did nothing. On the ground map those squares are `hj2-stdm`'s, and all 48 city continues still fall in their own district. Jak 2's city regions are all ported (the 4 missing load unported places) and run as in Jak 2 (the same `region-execute`, the target and camera positions); the late districts of the log are display faces reached by a street without a loading face (`hj2-farma` by `hj2-marka`'s face 1477 without crossing 1485), which the new log lines will place ; the guard waited 0.3 s on a loaded district, and loaded ahead only in place of a hidden district no script had asked for in the last 5 s (from the industrial section, both sections were wanted and recent) ; walking is too slow for the 2.5 s look-ahead; Jak 2's alert table has no grenadier at any level (Jak 3's sends 1 at rest) ; flying, the 2.5 s look-ahead reached the slums from the stadium's gate and evicted the shown stadium, which Jak 2's face then loaded back ; missing object sounds: the port dropped the part spawners' ambient sounds (380 spawners in 15 levels) and the particles' sounds; 23 sounds were in no want set of their level and 80 only in some (Jak 2 wants a bank only near its objects: the castle pad's airlock, the gun buoy, the fortress gates); `hj2-cpad-elevator` called `hj2-elevator`'s `init-sound!`, playing the palace elevator's sounds; two added continues wanted no bank |
| 19 | Jak 2's alert system in full; districts loading late ("in many places I must step onto the void for the level to load"): Jak 2's loading exactly; voice lines "sometimes a bit loud or repeat in a loop"; the stadium "has the same bug: I must be inside the level, visually bugged, for it to load correctly" | `ff-squad-control-method-45` replaced in havenj2's DGO: Jak as the squad's primary target, Jak 2's five alert levels and `update-alert-state` (Breath of Peace's port), Jak 2's alert music mode and alarm, the guards hunting, Dark Jak raising the alert; the Hellcats' and guard bikes' pursuit (`hj2-guard-vehicle-*`); their counts from the alert table ([7.2](haven_city_new_dawn_reference.md#72-traffic), [7.3](haven_city_new_dawn_reference.md#73-hellcats)); districts loaded ahead from the generated `*havenj2-district-preload*` (the manifest's `preload`), the swap-in and the guard never evicting a district a script asked for less than 5 s ago, no district shown before the PC renderer has its geometry (`*pc-renderer-display-wait?*`, `__pc-level-ready?` in `gk`) ([6.1](haven_city_new_dawn_reference.md#61-how-jak-2-loads-its-levels)); the minimap with Jak 2's maps (`source_textures`, `city_map_bits`, `hj2-minimap-page-on`, a one-line edit in `minimap.gc`), the guards' icons dropped when they go back to the traffic's pool, the Hellcats and guard bikes with the guards' blue icon and view cone, 1.4 times larger (`*hj2-guard-vehicle-minimap-class*`, `draw-frustum-2` following the class scale), the cones kept while Jak pilots in havenj2 ([7.4](haven_city_new_dawn_reference.md#74-minimap)); `pack-vags` ends each Jak 2 line with Jak 3's end frames (`add_vag_end_frames`) ([8.4](haven_city_new_dawn_reference.md#84-sound-and-music)); the stadium fix: districts loaded ahead shown when Jak comes within 50 m (`hj2-show-near-districts`), the preload no longer blocked by the district Jak left, at most one preload per 5 s, places loaded with the city swapped in at display time, the race track made Jak's level by region 1317 (`region_script_overrides`, `hj2-in-place?`), Jak waiting for the renderer in it, the renderer wait printed every second ([6.1](haven_city_new_dawn_reference.md#61-how-jak-2-loads-its-levels)) | The alert never rose in havenj2: only Jak 3's `ctywide` sets the squad's primary target (`*city-mode*` `'ctywide`), and `squad-control-method-18` ignores any other offender. Jak 3's guards ignore `'alert-begin`: `'member-attacked` instead. Jak 3's traffic manager `break!`s on `'increase-alert-level`: Dark Jak goes through `squad-control-method-18`. Late districts: Jak's route missed Jak 2's one-way loading faces, so the district loaded only when asked to be shown; the swap-in evicted hidden districts Jak 2's scripts had just loaded; the renderer's `.fr3` upload came after the load, with the collision already live. No minimap in havenj2: Jak 3 draws it only with a level named `ctywide` active, and no havenj2 level had `city-map-bits` or a minimap page. The guard vehicles' icons looked like the guards' (`draw-frustum-2` ignores the class scale) and no cone showed while Jak piloted (`frustum-alpha` 0 while piloting). Jak 2's voice lines have no ADPCM end flag: the voice ran past the line's end and looped the previous 8 KB chunk when the overlord's end check missed it; their position and loudness already matched Jak 3's lines. The stadium: on the main town's squares towards it the preload pair is `hj2-gena`/`hj2-stdm` and `hj2-gena`, left wanted hidden, blocked the preload, so the grounds loaded at Jak 2's face 1130 only 4 s before being shown; districts loaded ahead stayed hidden until Jak stood on them (`hj2-genb` loaded 12 s before being shown); the race track's tunnels lie on the main town's squares and Jak's level stayed `hj2-stdm` there, so the guard loaded `hj2-gena` over the track |
| 18 | After the user's fourth test: sounds missing in places (the gardens' sprinklers), the mountain's platform vanishing on arrival in Haven Forest, the dig not reached from the pumping station, the gardens loading late from the port, the gun buoy's shots through walls and the buoy indestructible; Jak 2's guard lines and alert (turrets firing at Jak in a vehicle); Jak 2's guard bikes with Freedom League pilots; the README to say Jak 2 is needed | `hj2-update-level-sounds` ([8.4](haven_city_new_dawn_reference.md#84-sound-and-music)); the actors' kill-mask bit `special` kept (`placed`, [6.4](haven_city_new_dawn_reference.md#64-pumping-station-mountain-and-haven-forest)); `hj2-atoll`'s collision box down to the castle pad's walkway; region 489 override, `hj2-swap-in-district` with an empty slot, the district map weighted by overlap and grown 3 rings ([6.1](haven_city_new_dawn_reference.md#61-how-jak-2-loads-its-levels)); the gun buoy's shots stopped by the background, its 12 hit points ([6.12](haven_city_new_dawn_reference.md#612-hazards-and-decor-of-the-places)); the guards' Jak 2 lines and Jak 2's alert ([7.2](haven_city_new_dawn_reference.md#72-traffic)); the guard bikes ([7.3](haven_city_new_dawn_reference.md#73-hellcats)); the README's Requirements | The platform: Jak 2 marks it alone with the kill-mask bit `special`, the only actors a `'special` backdrop keeps alive; the port dropped every kill-mask. The dig: the pumping station's `collision_bounds` cut the walkway to the castle pad (Jak fell through before the face showing the pad). The gardens: Jak 2's loading face can be walked around, the swap found no hidden district, and the map gave the port 50 m of the gardens' ground. The sprinklers: their bank's border was crossed before the gardens loaded |
| 17 | Nothing of Jak 2 or Jak 3 in the repository: the files made from them fetched and placed on each machine | The level port's `extract` step (the extractions checked, the decompiler run for what is missing: all of Jak 2 with its rips the first time, then only the DGOs missing), `task level-port`, the manifest's `ignore_outputs` (a full run lists its 301 outputs in a `.gitignore` block, removed from git), `game.gp` stopping with a message when they aren't generated ([3](haven_city_new_dawn_reference.md#3-rebuilding-it-step-by-step)) | A run on the existing extractions extracts nothing and rewrites no file: the outputs are the committed ones of phase 16 |
| 16 | Jak 2's sound in full: music, ambiences, object sounds, speeches and citizens' lines | The level port's `sound` step ([8.4](haven_city_new_dawn_reference.md#84-sound-and-music)): `want-sound` and `sound-play-loop` kept, banks and music renamed `j2*`, the levels' `:music-bank`, the hub's `:extra-sound-bank` (Jak 3's traffic banks), the copy and `pack-vags` build steps; Jak 3's overlord plays MIDI music, skips missing banks and reads a mod VAG directory, `goalc`'s `pack-vags`, GOOS `file-exists?` ([4.5](haven_city_new_dawn_reference.md#45-sound)); Jak 2's banks as half banks, the music flava, the speakers' speeches, the citizens' lines; Jak 2's object sounds in 35 `hj2-*` classes: the palace gate, hideout doors, fortress gates and elevators, the guard turrets, the atoll's pistons, turbines, pipes, sliders and gun buoy, the dig's platforms, balloon and stomp blocks, the fortress's lift, turrets and laser belt, the mountain's platforms, eco pool and avalanche, the palace cable's nuts, fans, rotating gun and turrets, the ruins' beams | Jak 2's voice lines start with a little-endian `pGAV` header (Jak 3's with `VAGp`): `pack-vags` reads both. Jak 2's names collide with Jak 3's (28 banks, the `CITY1` music, the `propa` speeches Jak 3's code still plays): every file renamed. A build step's `:dep` must be another step's output: the build file is `pack-vags`' third input instead |
| 15b | After the user's second test: death riding up the palace pillar, the mountain missing from Haven Forest, black props in the Hip Hog and Onin's tent, a crash entering the Hip Hog, the void from the port to the palace, black areas and lag while districts load, respawn points like Jak 2's, the tanker crash place removed, living yakows, Jak 2's original doors. Jak 2's music and sounds researched, pending a decision ([14](haven_city_new_dawn_reference.md#14-not-done-yet)) | Doors' height slice (`door_height`, `base_lumps`) and no `vis-dist` copied ([6.3](haven_city_new_dawn_reference.md#63-doors-and-elevators)); `'special` kept ([6.1](haven_city_new_dawn_reference.md#61-how-jak-2-loads-its-levels), [6.4](haven_city_new_dawn_reference.md#64-pumping-station-mountain-and-haven-forest)); `"sun": null` mesh palettes, `update-mood-hj2-onin` ([6.12](haven_city_new_dawn_reference.md#612-hazards-and-decor-of-the-places), [8.1](haven_city_new_dawn_reference.md#81-moods)); particle `data` copied for copied callbacks ([5.3](haven_city_new_dawn_reference.md#53-particles-and-sprite-textures)); the district guard with the generated district map and its 1.5 s look-ahead, the PC renderer told of loading levels (vanilla `level.gc` edit, off by default) ([6.1](haven_city_new_dawn_reference.md#61-how-jak-2-loads-its-levels)); `hj2-update-vis-nick` in place of the continue manager ([9.3](haven_city_new_dawn_reference.md#93-respawn-points)); spawn distance caps for the city's spawners and props ([11](haven_city_new_dawn_reference.md#11-memory-and-performance)); `hj2-yakow` ([5.6](haven_city_new_dawn_reference.md#56-city-actors)); 8 door classes from Jak 2's models for 42 doors ([6.3](haven_city_new_dawn_reference.md#63-doors-and-elevators)) | Pillar death: phase 14's copied `vis-dist` (200 m) made the pillar-top airlocks be born on the way up, and their `on-inside` loaded the bottom set: the top unloaded under Jak. Jak 3's airlock tests distance on x and z only; Jak 2 paused unseen doors through its visibility data: a height lump bounds it. The mountain: the translator turned `'special` into `#f`. Black props: their light was in palette 0 only, and interior moods light others. Hip Hog crash: `hj2-hiphog-mirror-sheen-func` read Jak 2's `*hiphog-mirror-sheen-waveform*`, never copied. The void: no loading face covers that street. Black areas: the renderer heard of a level only once it was loaded. The district map puts 46 of the 48 city continues in their own district, the other 2 in alleys outside it, none in another Then: Haven Forest's far end (`hj2-forstb`: the mother tree and the Precursor stone head) shown as soon as region 436 loads it (`region_script_overrides`; Jak 2 shows it only when the camera crosses the small face 434); `hj2-anim-loop` steps its animation once per frame like Jak 2's `med-res-level` (a seek-until-done loop never yields on a one-frame animation such as the low-res throne's); swingpoles (Dead Town, the palace cable, the fortress exit) and the dig's trapezes grabbable: Jak 3's target only takes `'pole-grab` while `jakb-pole-cycle-ja` is loaded, an animation of `jak-pole+0-ag` that its own levels with poles carry (halfpipe, precc, tema): the manifest's `art_groups` give it to `swingpole` and `hj2-dig-balloon-lurker` |
