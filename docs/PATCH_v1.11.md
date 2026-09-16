# Dugout Atlas v1.11

## Running section

The Player page now adds a dedicated **Running** panel directly below Defense for hitters.

Running shows four metrics:

1. **Sprint Speed** — official Baseball Savant Sprint Speed leaderboard value, displayed with the unit `ft/s`.
2. **SB** — stolen bases from the FanGraphs Major League batter leaderboard.
3. **CS** — caught stealing from the same FanGraphs player row.
4. **SB Success %** — calculated as `SB / (SB + CS) * 100` when at least one steal attempt exists.

Sprint Speed is read from Baseball Savant's official `/leaderboard/sprint_speed` leaderboard for the selected season. It is not estimated from pitch-level or batted-ball data.

## Defense rollback

The temporary v1.10.2 **FanGraphs OAA** fifth Defense card has been removed. Defense returns to the four metrics used before that patch:

- OAA — official Baseball Savant OAA leaderboard
- Runs Prevented
- Fielding Run Value
- Arm Value

The Baseball Savant OAA source policy introduced in v1.10.1 remains unchanged.

## Data behavior

- Running metrics load off the UI thread with the rest of the player sources.
- Current FanGraphs baserunning freshness follows the existing short current-season FanGraphs cache policy.
- Sprint Speed follows the existing Baseball Savant freshness policy.
- A failure in Sprint Speed or baserunning does not blank the rest of the player page; unavailable metrics remain `—` and the source error is surfaced.
