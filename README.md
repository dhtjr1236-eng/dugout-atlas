# ⚾ Dugout Atlas

A Windows desktop app for exploring MLB games and player data. Follow games and lineups during the season, or compare favorite players and past seasons during the offseason.

**[Download for Windows](https://github.com/dhtjr1236-eng/dugout-atlas/releases/download/v1.92/DugoutAtlas-v1.92-Setup.exe)** · [한국어](README.ko.md) · [User guide](docs/USER_GUIDE.md) · [Changelog](CHANGELOG.md) · [All releases](https://github.com/dhtjr1236-eng/dugout-atlas/releases)

[v1.92 release and assets](https://github.com/dhtjr1236-eng/dugout-atlas/releases/tag/v1.92)

Windows 10/11 x64 · No Python installation required

## Features

- **Player profiles:** MLB portraits, summary cards, batting and pitching metrics, and season trends.
- **Advanced Compare:** Choose a season for each of two to four players, compare metrics and percentiles, and export the tables to CSV.
- **Season Race:** Compare same-season fWAR or OPS trends for players A and B, optionally including player C, and save an animation.
- **Games and lineups:** Explore schedules, scores, base runners, and player records.
- **Offseason home:** Filter favorites by player name or team and browse saved season records. Collapse the games sidebar when it is not needed.
- **Themes and languages:** Light and dark themes, a Neon accent, and Korean, English, and Japanese interfaces.

## Install and launch

1. Download the installer using **Windows download** above.
2. Run `DugoutAtlas-v1.92-Setup.exe` and follow the installation wizard.
3. Launch Dugout Atlas when installation is complete.

An internet connection is required to retrieve statistics and game information. Some records or photos may be unavailable depending on data providers. Close the app before updating; the installed app keeps user data in the user folder.

To run from source, extract `DugoutAtlas-v1.92-source.zip` and run `install.bat`, then `run.bat` on Windows with Python 3.12 or newer. The release also includes `DugoutAtlas-v1.92-SHA256SUMS.txt` for verifying the downloads.

## Data and sources

Dugout Atlas uses MLB Stats API, FanGraphs, Baseball-Reference, and Baseball Savant / Statcast. Partial source failures do not hide successful data from other sources.

For storage locations and source behavior, see [USER_GUIDE.md](docs/USER_GUIDE.md) and [ARCHITECTURE.md](ARCHITECTURE.md).

---

Not an official client of MLB, FanGraphs, Baseball-Reference, or Baseball Savant.
