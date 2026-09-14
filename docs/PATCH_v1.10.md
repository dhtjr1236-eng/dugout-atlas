# Dugout Atlas v1.10

## Compare tab

A new **Compare** tab is placed beside Player.

- Player A and Player B each have an independent autocomplete search box.
- Hitter vs hitter comparisons show batting, FanGraphs, Baseball-Reference, Statcast and defense metrics.
- Pitcher vs pitcher comparisons show pitching, FanGraphs, Baseball-Reference and Statcast metrics.
- Hitter vs pitcher comparisons intentionally fall back to metrics that are meaningful for both roles instead of forcing role-specific values into the same label.
- Comparison player loads use the same `PlayerService.get_bundle()` path as the normal Player page, so source integrity rules such as fWAR != bWAR and OAA != Runs Prevented remain unchanged.

## Pitcher Statcast Yearly / Monthly / Daily

Pitchers now have their own Statcast period selector directly below the Statcast section.

### Yearly

Uses the existing selected-season Statcast metrics, pitch arsenal and velocity history.

### Monthly

- Uses the calendar month containing the pitcher's latest actual Statcast appearance in the selected season.
- This prevents a current-calendar-month off period from displaying an artificial empty panel.
- Statcast metrics, pitch arsenal, pitch usage, Run Value, Whiff% and velocity are all recalculated from the same filtered pitch-level rows.
- Velocity is shown by appearance date inside that month.

### Daily

- Uses the latest actual Statcast appearance date in the selected season.
- All pitch-level metrics and pitch-type tables are restricted to that date.
- Velocity displays the selected day's primary fastball value.

Monthly/Daily period payloads use a versioned `statcast_pitcher_period_v1` cache and the existing Savant freshness policy.

## Data integrity

- No period value is labeled as official Savant xERA unless that value is actually supplied by the canonical season source. Arbitrary Monthly/Daily xERA therefore remains unavailable when there is no exact official value.
- Run Value keeps the existing pitcher-positive sign convention.
- The latest actual appearance is used instead of assuming today's date.

## UI / concurrency

- Statcast period work runs outside the Qt UI thread.
- Rapid period changes keep the latest pending period and load it after the active request completes.
- Existing batter WAR/wRC+ Yearly / Monthly / Daily behavior remains unchanged.

## Tests

`tests/test_v110_compare_pitcher_periods.py` adds regression coverage for:

- latest-active-month slicing;
- latest-appearance-day slicing;
- period velocity rows;
- role-aware Compare metric contracts.
