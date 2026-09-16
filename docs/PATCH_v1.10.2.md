# Dugout Atlas v1.10.2

## FanGraphs OAA in Defense

The Defense panel now shows five metrics instead of four:

1. OAA — official Baseball Savant OAA leaderboard value
2. FanGraphs OAA — FanGraphs Fielding leaderboard Statcast OAA
3. Runs Prevented
4. Fielding Run Value
5. Arm Value

FanGraphs OAA is fetched separately from the FanGraphs fielding leaderboard (`stats=fld`, `type=1`) and is never used to overwrite the Baseball Savant OAA value. Both values retain separate source provenance. Current-season FanGraphs OAA uses the same short freshness policy as other current FanGraphs data.

The FanGraphs value is kept as a floating-point number when the provider returns decimals. If FanGraphs is unavailable or does not return OAA for the player, the Baseball Savant defense data continues to display and the FanGraphs OAA cell remains unavailable rather than substituting another metric.
