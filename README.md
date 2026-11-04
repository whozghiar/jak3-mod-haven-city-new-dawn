# Haven City: New Dawn — Jak 3

<p align="center">
  <img src="https://img.shields.io/badge/OpenGOAL-Mod-blue.svg" alt="OpenGOAL Mod">
  <img src="https://img.shields.io/badge/Game-Jak%203-orange.svg" alt="Target Game">
  <img src="https://img.shields.io/badge/AI--assisted-Modding-purple.svg" alt="AI Assisted">
</p>

> **Contents:** [Overview](#overview) · [Requirements](#requirements) · [Key Features](#key-features) · [Controls](#controls) · [Download & Play](#download--play-via-opengoal-launcher-players) · [Developer Setup](#developer-setup--local-compilation) · [Demo Video](#demonstration-video) · [Technical Documentation](#technical-documentation)

---

## Overview
Jak 2's Haven City and the places around it, playable inside Jak 3, as they are at the end of
Jak 2: the city district by district, its interiors, the palace, Dead Town, the pumping station,
the mountain, Haven Forest, the fortress and its prison, the stadium and the dig site. Everything
is rebuilt from your own copy of Jak 2. A war mode sets Jak 2's Krimzon Guards against Jak 3's
Freedom League.

- **Target Game:** Jak 3
- **Repository:** [`whozghiar/jak3-mod-haven-city-new-dawn`](https://github.com/whozghiar/jak3-mod-haven-city-new-dawn)

## Requirements

> [!IMPORTANT]
> You need your own copy of **both Jak 2 and Jak 3** (discs, or ISOs made from them). Made and
> tested with the European Jak 2 (PAL, SCES-51608) and the American Jak 3 (NTSC-U, SCUS-97330).
> The mod contains nothing of either game: its levels, models, textures, music and voices are
> made on your machine from your games.

## Key Features
- **Jak 2's city:** its districts and the stadium, loaded district by district like in Jak 2.
- **30 places around it:** the Hip Hog, the palace, Dead Town, the pumping station, Haven Forest,
  the fortress and its prison, the dig site and more, reached through Jak 2's doors.
- **The end of Jak 2:** every level as the game leaves it, with its hazards and no enemies.
- **A living city:** citizens, guards and vehicles, Jak 2's Hellcats and guard bikes, Jak 2's alert.
- **War mode:** Jak 2's Krimzon Guards against Jak 3's Freedom League, in Jak 2's city and the
  places around it.
- **Jak 2's sound:** its music, ambiences and voices.
- **Mini-games:** Whack-a-Metal-Head, Onin's bubble game, Vin's game.
- **Time and weather** set from the menu; the weather works with the mod off too.
- **Travelling:** warps to every place, time gates between the two games, saving anywhere.

## Controls

| Action | How |
|---|---|
| Open the mod's menu | L3 + SELECT, then Mods ▸ Haven City: New Dawn |
| Take an air train or a time gate, play a mini-game | Triangle when the prompt shows; R3 quits a game |

| Menu entry | Does |
|---|---|
| Mod enabled | Switches the mod on or off (off at each boot); off, Jak 3 is unchanged |
| KG-Guard vs Freedom Fighters | Switches the war mode on or off (off at each boot) |
| Warp to Haven City (Jak 2) | Warp to Jak 2 (the underground hideout), Warp to a district, Warp outside the city (or back to Jak 3's Freedom HQ) |
| Weather | The weather in the whole game, and the hour in Jak 2's levels; usable with the mod off |

The war and the warps are greyed out while the mod is off.

## Download & Play via OpenGOAL Launcher (Players)

Install Jak 2 and Jak 3 in the OpenGOAL Launcher first, each from your own ISO. While the launcher
installs the mod, it makes the mod's levels from your installed Jak 2 (a minute or two more than
a usual mod); without Jak 2 the install stops with error code 4060.

Each release also carries the mod's texture pack (`haven-city-new-dawn-textures-v*.zip`). It is
optional: the mod's models and their colors are made without it.

### Option A — Add Custom Mod Source (Recommended)
1. In the **OpenGOAL Launcher**, open **Settings ▸ Mods ▸ Add Custom Mod Source**.
2. Paste this catalog URL:
   ```text
   https://raw.githubusercontent.com/whozghiar/jak3-mod-haven-city-new-dawn/main/index.json
   ```
3. In the **Mods** tab, find **Haven City: New Dawn** and click **Install**.

### Option B — Manual Installation from GitHub Releases
1. Download the package for your system from the [Releases](https://github.com/whozghiar/jak3-mod-haven-city-new-dawn/releases) tab (`windows-haven-city-new-dawn-v*.zip` or `linux-haven-city-new-dawn-v*.zip`).
2. Extract it into `<launcher installation folder>/features/jak3/mods/_local/haven-city-new-dawn/`.
3. Run the mod's decompile and compile from the launcher, then launch the game.

---

## Developer Setup & Local Compilation

1. Copy each disc's files into `iso_data/jak2` and `iso_data/jak3`.
2. Build the tools and generate the levels (the first run extracts all of Jak 2, about 11 GB):
   ```bash
   task set-game-jak3
   task build-release-game
   task build-release-decomp
   task level-port -- custom_assets/jak3/ports/jak2-haven-city/port.jsonc
   ```
3. Build and run: `task repl`, then `(mi)`, then `task boot-game`. In the game, open the Mods menu
   and warp to Haven City.

## Demonstration Video

[![Demonstration Video](https://img.youtube.com/vi/1_B4fGxRQZ0/maxresdefault.jpg)](https://youtu.be/1_B4fGxRQZ0)

**[Watch the demonstration video on YouTube](https://youtu.be/1_B4fGxRQZ0)**

## Technical Documentation
- [`docs/modding/current_mod/haven_city_new_dawn_readme.md`](docs/modding/current_mod/haven_city_new_dawn_readme.md): the developer guide (GOAL basics, hooks, the war mode, color variants).
- [`docs/modding/current_mod/haven_city_new_dawn_reference.md`](docs/modding/current_mod/haven_city_new_dawn_reference.md): how each feature works, for a beginner.

---
*(AI-assisted)*
