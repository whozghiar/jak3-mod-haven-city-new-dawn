# Jak2 Haven City — Jak 3

<p align="center">
  <img src="https://img.shields.io/badge/OpenGOAL-Mod-blue.svg" alt="OpenGOAL Mod">
  <img src="https://img.shields.io/badge/Game-Jak%203-orange.svg" alt="Target Game">
  <img src="https://img.shields.io/badge/AI--assisted-Modding-purple.svg" alt="AI Assisted">
</p>

<p align="center">

[![Branch Sync Check](https://github.com/whozghiar/jak-project/actions/workflows/branch-sync-check.yaml/badge.svg?branch=jak3%2Ffeatures%2Fjak2-haven-city)](https://github.com/whozghiar/jak-project/actions/workflows/branch-sync-check.yaml?query=branch%3Ajak3%2Ffeatures%2Fjak2-haven-city)

</p>

> [!NOTE]
> The badge above is a native **GitHub Actions status badge** for
> [`branch-sync-check.yaml`](https://github.com/whozghiar/jak-project/actions/workflows/branch-sync-check.yaml),
> scoped to this branch — GitHub renders it live from that workflow's own run history,
> nothing generates or rewrites this image by hand. It goes green the moment this branch
> next merges `master-dev` cleanly (usually via the daily automated sync), and can turn
> red if someone pushes commits here without syncing first. It cannot turn red purely
> because `master-dev` moved on without a new push landing here — run `task modding-branch-status`
> or check GitHub Actions to audit fleet-wide mergeability.

> **Contents:** [Overview](#overview) · [Requirements](#requirements) · [Key Features](#key-features) · [Controls](#controls) · [Download & Play](#download--play-via-opengoal-launcher-players) · [Developer Setup](#developer-setup--local-compilation) · [Demo Video](#demonstration-video) · [Technical Documentation](#technical-documentation)

---

> [!NOTE]
> This mod moved from the `jak3/features/jak2-haven-city` branch of [whozghiar/jak-project](https://github.com/whozghiar/jak-project) to this repository. Earlier releases stay installable from the launcher catalog.

## Overview
Brings Jak 2's Haven City and the places around it into Jak 3, as they are at the end of Jak 2:
the whole city, district by district like in Jak 2, with its interiors, the palace, Dead Town, the pumping
station, the mountain, Haven Forest, the fortress and its prison, the stadium's race track and the
dig site, all rebuilt from Jak 2's own extracted data and linked the way Jak 2 links them.

- **Target Game:** Jak 3
- **Repository:** [`whozghiar/jak3-mod-jak2-haven-city`](https://github.com/whozghiar/jak3-mod-jak2-haven-city)

## Requirements

> [!IMPORTANT]
> **You need an official copy of both Jak 2 and Jak 3**: your own PS2 discs, or ISOs dumped
> from them. It is made and tested with the European Jak 2 (PAL, SCES-51608) and the American
> Jak 3 (NTSC-U, SCUS-97330); other regions are untested. The mod contains nothing of
> either game: its levels, models, textures, music, sounds and voices are all made on your machine
> from your own Jak 2 and Jak 3. Owning Jak 3 alone is not enough.
>
> - **From the OpenGOAL Launcher:** install Jak 2 and Jak 3 in the launcher first (each from your
>   own ISO), then the mod. Its install makes the levels from your installed Jak 2 by itself
>   ([Download & Play](#download--play-via-opengoal-launcher-players)).
> - **From source:** both games must be **extracted before the mod is built**:
>
> 1. copy each disc's files (the content of the ISO) into `iso_data/jak2` and `iso_data/jak3`;
> 2. run `task level-port -- custom_assets/jak3/ports/jak2-haven-city/port.jsonc`: it extracts
>    what it needs from both games (the first time, all of Jak 2 with its models: long, about
>    11 GB) and generates the levels;
> 3. build and play ([Developer Setup](#developer-setup--local-compilation)).
>
> Without Jak 2, the mod can't be built.

## Key Features
- **The whole city:** Jak 2's 14 districts, `ctywide` and the stadium grounds, loaded district by
  district through Jak 2's own doors and regions, with Jak 2's lighting, water, particles, neon
  signs and breakable market props.
- **The places around it:** 30 more levels (the Hip Hog, the hideout, the Oracle, Vin's power
  station, Keira's garage, the gun course, the palace pillar and roof, Dead Town with the Sage's
  hut, the construction site, the pumping station, the mountain and the canyon behind its iris
  doors, Haven Forest, the inside of the fortress, its prison and the way out, the stadium's race
  track, the castle pad and the dig, the bazaar's stall, Onin's tent), loaded through their doors, elevators, airlocks, gates and regions like in Jak 2, in
  Jak 2's own memory modes, with their moving platforms, lifts, swinging bars and slides.
- **The end of Jak 2:** every level as it is once the game is finished: the Baron's statue in
  rubble, the market roof broken, Dead Town's tower and pillars fallen, the mountain temple's
  puzzles solved, only what Jak 2 still places then.
- **Complete levels:** Jak 2's particles in every place, and every hazard that hurts Jak (the
  palace cable's electric fans, falling platforms and gun turrets, the fortress's laser turrets,
  the avalanche, the dark eco pool, the gun buoy, the city's guard turrets), without enemies; the
  city's searchlights, force-field walls, parked vehicles and barges, the gardens' yakows; Jak 2's
  own doors and airlocks; the places' decor (banners, lamps, turbines, birds and fish).
- **The fortress's escape:** its far gate opens on the prison (cells, torture machine, hanging
  cells), whose tunnels lead out of the fortress, back to the slums.
- **Breakable city:** the Baron's propaganda speakers break in two hits like in Jak 2, the farm
  crops are solid and burst when hit hard.
- **Air trains:** the port's air train takes Jak to the dig site and back, in a short fade.
- **City traffic:** Jak 3's citizens, Freedom League guards, hover bikes and cars, as many as in
  Jak 2; Jak 2's Freedom League Hellcats: they fly with the traffic, and Jak can steal one and fire
  its front gun; Jak 2's Crimson Guard bikes, ridden by Freedom League guards.
- **Jak 2's alert:** Jak 2's five alert levels. Hitting a citizen or a guard, hitting a guard
  vehicle or turning into Dark Jak raises the alert; the guards hunt Jak, the Hellcats and guard
  bikes chase and shoot him from level 2, the city music plays its alert mode and the minimap
  flashes. It ends 30 s after the last offence, once no guard hunts any more. The city's guard
  turrets pop up and fire at Jak while he flies a vehicle near them.
- **Minimap:** Jak 2's city maps on Jak 3's minimap, with the guards, Hellcats and guard bikes as
  blue icons with their view cone.
- **Jak 2's sound:** each place's Jak 2 music (with its variations when Jak draws his gun, rides
  the board, turns dark or drives), ambiences and object sounds, the Baron's speeches from his
  propaganda speakers, the citizens' and the guards' lines (the Freedom League guards speak like
  Jak 2's Crimson Guards), taken from your Jak 2 extraction.
- **Time and weather:** a fixed hour or Jak 2's day and night; Jak 3's changing weather or a fixed
  one (sunny, cloudy, foggy, light rain, rain, thunderstorm, snow) in the whole game.
- **Travelling:** warps to every district, key places and places outside the city; two time gates,
  one in Jak 3's Freedom HQ and one in Jak 2's underground hideout, lead to each other; dying
  respawns Jak at Jak 2's closest respawn point.
- **Saves:** save anywhere in Jak 2's world; the save screen shows "Haven City (Jak 2)" on the
  slot.

## Controls

| Action | How |
|---|---|
| Open the mod's menu | L3 + SELECT, then Mods ▸ jak2-haven-city (retail and debug boots) |
| Take an air train or a time gate | Triangle, when the prompt shows |

The menu's entries:

| Entry | Does |
|---|---|
| Mod enabled | Switches the mod on or off (off by default). On: the time gate stands in Jak 3's Freedom HQ, and the entries below can be used. Off: Jak 3 as it is |
| Warp to Haven City (Jak 2) | Warps to the underground hideout |
| Warp to a district | Warps to a spot in each district (slums, port, bazaar, industrial section, main town, gardens, palace plaza and roof, stadium grounds) or to a place in it (the Hip Hog, the gun course, the port's air train, Vin's power station, the construction site gate, the cable pillar, the fortress gate, the Oracle, Keira's garage) |
| Warp outside the city | Warps to Dead Town, the Sage's hut, the inside of the fortress, its prison, the stadium's race track, the construction site, the pumping station, the mountain top, Haven Forest, the castle pad, the dig site, or back to Jak 3's Freedom HQ |
| Weather | Changing (Jak 3's weather, default) or a fixed one, in the whole game; and the time of day in Jak 2's levels: 9:00, 12:00, 16:00 (default), 19:00, 23:00, or Jak 2's day and night |

## Download & Play via OpenGOAL Launcher (Players)

> [!WARNING]
> Not published yet: this repository has no release of the mod, and the launcher only installs
> releases of a public repository (this one is private). Until then, build it from source
> ([Developer Setup](#developer-setup--local-compilation)).

**Install Jak 2 and Jak 3 in the OpenGOAL Launcher first**, each from your own ISO, and let each
install finish. Then install the mod: nothing else to do. While the launcher compiles the mod, the
mod's extractor reads your installed Jak 2 and makes its levels, models and sounds (a minute or two
more than a usual mod). If Jak 2 isn't installed, the install stops with an error code (4060): the
launcher's log says to install Jak 2, then to reinstall the mod.

### Option A — Add Custom Mod Source (Recommended)
1. In the **OpenGOAL Launcher**, navigate to **Settings ▸ Mods ▸ Add Custom Mod Source**.
2. Paste this catalog URL:
   ```text
   https://raw.githubusercontent.com/whozghiar/jak-project/jak3/features/jak2-haven-city/index.json
   ```
3. Go to the **Mods** tab, locate **Jak2 Haven City**, and click **Install**.
4. If Jak 3 isn't installed yet, the launcher asks for your Jak 3 ISO. It then extracts, generates
   the Jak 2 levels from your installed Jak 2 and compiles the mod.

### Option B — Manual Installation from GitHub Releases
1. Download the pre-built package for your operating system from the [Releases](https://github.com/whozghiar/jak-project/releases) tab (`windows-v*.zip` or `linux-v*.zip`).
2. Extract the archive into the `features` folder of the launcher's installation folder (the one
   chosen in its settings): `<installation folder>/features/jak3/mods/_local/jak2_haven_city/`.
3. Run the mod's decompile and compile from the OpenGOAL Launcher (the compile generates the Jak 2
   levels), then launch the game.

---

## Developer Setup & Local Compilation

If you want to modify or compile this mod locally from source:

### 1. Select the Active Game
Make sure your environment is targeting Jak 3:
```bash
task set-game-jak3
```

### 2. Binary Compilation
- **Status:** `task build-release-game` and `task build-release-decomp`: the custom level builder
  in `goalc` and the decompiler changed.
- **Details:** see [Rebuilding it step by step](docs/modding/current_mod/jak2_haven_city_readme.md#3-rebuilding-it-step-by-step)
  in the technical README.
```bash
task build-release-game
task build-release-decomp
```

### 3. Asset Extraction and Level Generation
- **Status:** Required for **both** Jak 2 and Jak 3, from official copies (tested: Jak 2 PAL SCES-51608, Jak 3 NTSC-U SCUS-97330).
- **Details:** nothing of Jak 2 or Jak 3 is in the repository: the levels, models and level code
  are made on your machine from your own discs or ISOs. Copy each disc's files into `iso_data/jak2` and
  `iso_data/jak3`, then run the level port: it extracts what it needs (the first time, all of
  Jak 2 with its models: long, 11 GB) and generates the levels. The build then copies Jak 2's
  music, sound banks and voice lines from `iso_data/jak2`. Jak 3's Freedom HQ needs the time gate's
  model at extraction: a Jak 3 extracted before this branch needs that level again (the technical
  README gives the command).
```bash
task level-port -- custom_assets/jak3/ports/jak2-haven-city/port.jsonc
```

### 4. Launch the Game
Build with `task repl` then `(mi)`, and run the game natively:
```bash
task boot-game
```
Then warp from the Mods menu (L3 + SELECT, Mods ▸ jak2-haven-city ▸ Warp to Haven City (Jak 2)).

## Demonstration Video

[![Demonstration Video](https://img.youtube.com/vi/YOUR_VIDEO_ID/maxresdefault.jpg)](https://youtu.be/YOUR_VIDEO_ID)

**[Watch the demonstration video on YouTube](https://youtu.be/YOUR_VIDEO_ID)**

> [!NOTE]
> *Demonstration videos must be hosted externally on YouTube to prevent repository bloating. Replace `YOUR_VIDEO_ID` with your YouTube video ID (e.g. `MnqnybexhSA` from `https://youtu.be/MnqnybexhSA`).*

## Technical Documentation
For the complete technical breakdown, architecture, and developer notes, refer to:
- [`docs/modding/current_mod/jak2_haven_city_readme.md`](docs/modding/current_mod/jak2_haven_city_readme.md)

---
*(AI-assisted)*
