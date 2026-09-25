# Dugout Atlas v1.41

v1.41 adds locale-aware player display names without changing identifiers used by MLB, FanGraphs, Baseball-Reference, or Baseball Savant.

## Player-name localization
- Curated 2026 seed: 24 KR/JP/TW players (6 Korean, 15 Japanese, 3 Taiwanese).
- English keeps MLB English identity names; Korean/Japanese UI uses curated display names and search aliases.
- MLB Korea/Japan player pages are checked best-effort for names missing from the curated seed and cached locally.
- Player, Compare, Lineup, Gameday and autocomplete are localized at the UI boundary.

## v1.41 corrections
- Jung Hoo Lee Japanese display is locked to **イ・ジョンフ**.
- Alias replacement ignores source strings contained in the target, preventing duplicated prefixes such as `イ イ・ジョンフ`.
- Hye-Seong Kim 2026 display team is **LAD**.
- Tsung-Che Cheng Korean display is **정쭝저**; `정종저` remains a search alias.

## Data integrity
Localization does not alter the English identity passed to FanGraphs/B-Ref/Savant. OAA remains official Baseball Savant OAA and bWAR remains Baseball-Reference bWAR.

## Validation
Regression coverage includes the 24-player seed, exact/idempotent Lee Japanese display, LAD team override, Tsung-Che Cheng Korean display, aliases and locale-title parsing.
