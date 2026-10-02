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

> **Contents:** [Overview](#overview) · [Key Features](#key-features) · [Controls](#controls) · [Modding Changes Log](#modding-changes-log) · [Download & Play](#download--play-via-opengoal-launcher-players) · [Developer Setup](#developer-setup--local-compilation) · [Demo Video](#demonstration-video) · [Compliance Checklist](#compliance-checklist) · [Technical Documentation](#technical-documentation)

---

> [!NOTE]
> This mod moved from the `jak3/features/jak2-haven-city` branch of [whozghiar/jak-project](https://github.com/whozghiar/jak-project) to this repository. Earlier releases stay installable from the launcher catalog.

## Overview
Brings Jak 2's Haven City and the places around it into Jak 3, as they are at the end of Jak 2:
the whole city as one walkable level, with its interiors, the palace, Dead Town, the pumping
station, the mountain, Haven Forest, the fortress and its prison, the stadium's race track and the
dig site, all rebuilt from Jak 2's own extracted data and linked the way Jak 2 links them.

- **Target Game:** Jak 3
- **Repository:** [`whozghiar/jak3-mod-jak2-haven-city`](https://github.com/whozghiar/jak3-mod-jak2-haven-city)

## Key Features
- **The whole city:** Jak 2's 14 districts, `ctywide` and the stadium grounds merged into one Jak 3
  level, with Jak 2's lighting, water, particles, neon signs and breakable market props.
- **The places around it:** 27 more levels (the Hip Hog, the hideout, the Oracle, Vin's power
  station, Keira's garage, the gun course, the palace pillar and roof, Dead Town with the Sage's
  hut, the construction site, the pumping station, the mountain, Haven Forest, the inside of the
  fortress, its prison and the way out, the stadium's race track, the castle pad and the dig),
  loaded through their doors, elevators, airlocks and gates like in Jak 2, in Jak 2's own memory
  modes, with their moving platforms, lifts, swinging bars and slides.
- **The end of Jak 2:** every level as it is once the game is finished: the Baron's statue in
  rubble, the market roof broken, Dead Town's tower fallen, only what Jak 2 still places then.
- **The fortress's escape:** its far gate opens on the prison (cells, torture machine, hanging
  cells), whose tunnels lead out of the fortress, back to the slums.
- **Breakable city:** the Baron's propaganda speakers break in two hits like in Jak 2, the farm
  crops are solid and burst when hit hard.
- **Air trains:** the port's air train takes Jak to the dig site and back, in a short fade.
- **City traffic:** Jak 3's citizens, Freedom League guards, hover bikes and cars, as many as in
  Jak 2.
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
| Warp to Haven City (Jak 2) | Warps to the city, in the slums |
| Warp to a district | Warps to one of 15 spots, at least one in each district (slums, port, bazaar, industrial section, main town, gardens, palace plaza, stadium grounds) |
| Warp to a key place | Warps in front of the construction site gate, the palace, Mar's tomb, the cable pillar, the Hip Hog, the gun course, the port's air train, Vin's power station or the fortress; or to the hideout, the palace roof, the Oracle or Keira's garage |
| Warp outside the city | Warps to Dead Town, the Sage's hut, the inside of the fortress, its prison, the way out of the fortress, the stadium's race track, the construction site, the pumping station, the mountain top, Haven Forest, the castle pad or the dig site |
| Warp to the Freedom HQ (Jak 3) | Warps back to Jak 3's world, in the room of the time gate |
| Time of day | 9:00, 12:00, 16:00 (default), 19:00, 23:00, or Jak 2's day and night |
| Weather (whole game) | Changing (Jak 3's weather, default), or a fixed one |
| City traffic | Switches the traffic on (default) or off |

## Modding Changes Log

| Phase | Changes |
|---|---|
| 1 | Jak 2's Haven City as one walkable Jak 3 level; warp from the Mods menu (commit `de9ec6962`) |
| 2 | Jak 2's sky, water and vegetation |
| 3 | Doors to the interiors; respawn next to Jak |
| 4 | Places loaded and unloaded like in Jak 2; the palace gate; props; time of day |
| 5 | Market and farm props, propaganda speakers, particles and neon signs, weather, fixed cameras; the pumping station, the mountain and Haven Forest |
| 6 | Jak 2's elevators; the platforms of the pumping station and the mountain; crates |
| 7, 8 | City traffic; its first crash fixed; the palace door that "never opens" explained (it doesn't exist in Jak 2) |
| 9 | Denser traffic without popping; the castle pad and the dig site; the port's air train |
| 10 | Weather for the whole game (8 choices, snow); smoke and fountains fixed; air train cutscenes; a time gate in Jak 3's Freedom HQ; warps to every district and key place (commit `dd14a7829`) |
| 11 | Palace elevator death fixed; Jak 2's respawn points everywhere; air train as a fade; time gates between the Freedom HQ and the hideout; saves; construction site models; two-hit speakers; farm crops; Dead Town's water, bars, slabs, platforms and the Sage's hut; particles of Haven Forest and Dead Town; the fortress and the stadium; Keira's garage open (commit `e769d5e2a`) |
| 12 | Dead Town and the Sage's hut as one level; Jak 2's memory modes; every level in its end-of-game state (actors, background, the broken statue); the fortress prison and the way out of the fortress, with their gates; crates, swinging bars and slides everywhere; the Freedom HQ time gate crash fixed (level heaps kept below 256 MB, checked in game); a crash report in the game's log (commit `051725569`) |
| 13 | No change in game: the level files are made by a generic tool (`scripts/level_port`) from the mod's data (`custom_assets/jak3/ports/jak2-haven-city`) |

Details, causes and fixes: [change history](docs/modding/current_mod/jak2_haven_city_readme.md#13-change-history).

## Download & Play via OpenGOAL Launcher (Players)

> [!WARNING]
> Not available through the launcher yet: the level is built from a local Jak 2 extraction, see
> [Developer Setup](#developer-setup--local-compilation).

> [!TIP]
> **No developer environment required!** Players can install and play this mod directly using the official OpenGOAL Launcher:

### Option A — Add Custom Mod Source (Recommended)
1. In the **OpenGOAL Launcher**, navigate to **Settings ▸ Mods ▸ Add Custom Mod Source**.
2. Paste this catalog URL:
   ```text
   https://raw.githubusercontent.com/whozghiar/jak-project/jak3/features/jak2-haven-city/index.json
   ```
3. Go to the **Mods** tab, locate **Jak2 Haven City**, and click **Install**.
4. Select your clean PS2 game ISO when prompted. The launcher will automatically extract assets and launch the game!

### Option B — Manual Installation from GitHub Releases
1. Download the pre-built package for your operating system from the [Releases](https://github.com/whozghiar/jak-project/releases) tab (`windows-v*.zip` or `linux-v*.zip`).
2. Extract the archive into your OpenGOAL Launcher features directory:
   - **Windows:** `%APPDATA%\OpenGOAL-Launcher\features\jak3\mods\_local\jak2_haven_city\`
   - **Linux:** `~/.config/OpenGOAL-Launcher/features/jak3/mods/_local/jak2_haven_city/`
3. Launch the game from the OpenGOAL Launcher.

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

### 3. Asset Extraction
- **Status:** Required for **both** Jak 2 and Jak 3.
- **Details:** the levels merge Jak 2's extracted `.fr3` files and take some sprite textures from
  Jak 3's, so both games must be extracted before building. Jak 3's Freedom HQ also gets the time
  gate's model at extraction (`extra_art_groups_by_dgo`): a Jak 3 extracted before this branch
  needs it again (the technical README gives a command for that level only). The generated level
  files are in the repository; regenerating them also needs Jak 2's model rips (`rip_levels`), see
  the technical README.
```bash
task set-game-jak2
task extract
task set-game-jak3
task extract
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

## Compliance Checklist
- [ ] **Native non-regression:** with the mod compiled but its toggle OFF, the game plays identically to stock.
  *Not yet: the time gate always stands in Jak 3's Freedom HQ, whatever the menu says. The only vanilla code change is a faction manager check in `guard.gc`, which changes nothing where Jak 3's faction manager exists (Jak 3's own city).*
- [x] **In-game Mods toggle [MANDATORY FOR FEATURES]:** the mod registers at least one enable/disable entry via `(mods-menu-register "jak2-haven-city" ...)` (Jak 2 / Jak 3, opens with **L3 + SELECT**, works in a retail boot) or a `jak2_haven_city`-prefixed **debug-only** submenu (Jak 1). See [`docs/modding/guides/mods_menu.md`](docs/modding/guides/mods_menu.md).
- [x] **No direct `default-menu*.gc` edits.**
- [ ] **Symbols prefixed** with the mod slug (`*mod-jak2_haven_city-*`, `mod-jak2_haven_city-*`).
  *Partly: the menu's settings use `mod-jak2-haven-city-`; the levels' code uses the level prefixes `havenj2-` and `hj2-`.*
- [ ] **Verified Lisp instructions** used by this mod are present in `docs/modding/lisp_instructions.md` (landed on `master-dev` via `task modding-land-doc`).
  *Not yet: the verified Jak 3 facts are listed in the technical README, [Jak 2 and Jak 3 differences](docs/modding/current_mod/jak2_haven_city_readme.md#10-jak-2-and-jak-3-differences).*
- [x] **In-code comments** on every new/overridden type, method, state, macro.
- [ ] **Mod cover thumbnail:** Optional cover image deposited at `docs/img/mod/mod_cover.png` for OpenGOAL Launcher display.

## Technical Documentation
For the complete technical breakdown, architecture, and developer notes, refer to:
- [`docs/modding/current_mod/jak2_haven_city_readme.md`](docs/modding/current_mod/jak2_haven_city_readme.md)

---
*(AI-assisted)*
