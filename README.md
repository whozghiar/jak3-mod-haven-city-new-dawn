# Jak2 Haven City — Jak 3

<p align="center">
  <img src="https://img.shields.io/badge/OpenGOAL-Mod-blue.svg" alt="OpenGOAL Mod">
  <img src="https://img.shields.io/badge/Game-Jak%203-orange.svg" alt="Target Game">
  <img src="https://img.shields.io/badge/Branch-jak3%2Ffeatures%2Fjak2-haven-city-green.svg" alt="Branch">
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

> **Contents:** [Overview](#overview) · [Key Features](#key-features) · [Download & Play](#download--play-via-opengoal-launcher-players) · [Developer Setup](#developer-setup--local-compilation) · [Demo Video](#demonstration-video) · [Compliance Checklist](#compliance-checklist) · [Technical Documentation](#technical-documentation)

---

## Overview
Brings Jak 2's whole Haven City into Jak 3 as one walkable custom level, `havenj2`, built from
Jak 2's own extracted background data.

- **Target Game:** Jak 3
- **Active Branch:** `jak3/features/jak2-haven-city`

## Key Features
- **The whole city:** the 15 Jak 2 city levels (`ctywide` plus the 14 districts) merged into one
  Jak 3 level, with their collision and surface types.
- **Jak 2 lighting:** Jak 2's time-of-day palettes, with street lights, flames and neon signs
  driven at night.
- **Vegetation and details:** Jak 2's shrubs (plants, small props) are drawn.
- **Warp from anywhere:** L3 + SELECT, then Mods ▸ jak2-haven-city ▸ Warp to Haven City (Jak 2).

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
- **Status:** `task build-release-game` (the custom level builder in `goalc` changed).
- **Details:** see [the technical README](docs/modding/current_mod/jak2_haven_city_readme.md).
```bash
task build-release-game
```

### 3. Asset Extraction
- **Status:** Required for **both** Jak 2 and Jak 3.
- **Details:** the level merges Jak 2's extracted `out/jak2/fr3/cty*.fr3` files, so Jak 2 must be
  extracted once before building the Jak 3 level.
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
Then warp from the Mods menu (retail boot, L3 + SELECT) or, with the REPL connected, restart
play at the `havenj2-start` continue point, the same call as the menu button in
`goal_src/jak3/pc/features/jak2-haven-city-menu.gc`.

## Demonstration Video

[![Demonstration Video](https://img.youtube.com/vi/YOUR_VIDEO_ID/maxresdefault.jpg)](https://youtu.be/YOUR_VIDEO_ID)

**[Watch the demonstration video on YouTube](https://youtu.be/YOUR_VIDEO_ID)**

> [!NOTE]
> *Demonstration videos must be hosted externally on YouTube to prevent repository bloating. Replace `YOUR_VIDEO_ID` with your YouTube video ID (e.g. `MnqnybexhSA` from `https://youtu.be/MnqnybexhSA`).*

## Compliance Checklist
- [ ] **Native non-regression:** with the mod compiled but its toggle OFF, the game plays identically to stock.
- [ ] **In-game Mods toggle [MANDATORY FOR FEATURES]:** the mod registers at least one enable/disable entry via `(mods-menu-register "jak2_haven_city" ...)` (Jak 2 / Jak 3, opens with **L3 + SELECT**, works in a retail boot) or a `jak2_haven_city`-prefixed **debug-only** submenu (Jak 1). See [`docs/modding/guides/mods_menu.md`](docs/modding/guides/mods_menu.md).
- [ ] **No direct `default-menu*.gc` edits.**
- [ ] **Symbols prefixed** with the mod slug (`*mod-jak2_haven_city-*`, `mod-jak2_haven_city-*`).
- [ ] **Verified Lisp instructions** used by this mod are present in `docs/modding/lisp_instructions.md` (landed on `master-dev` via `task modding-land-doc`).
- [ ] **In-code comments** on every new/overridden type, method, state, macro.
- [ ] **Mod cover thumbnail:** Optional cover image deposited at `docs/img/mod/mod_cover.png` for OpenGOAL Launcher display.

## Technical Documentation
For the complete technical breakdown, architecture, and developer notes, refer to:
- [`docs/modding/current_mod/jak2_haven_city_readme.md`](docs/modding/current_mod/jak2_haven_city_readme.md)

---
*(AI-assisted)*
