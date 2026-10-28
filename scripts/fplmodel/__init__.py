"""fplmodel — canonical data, models, backtests and exports for SquadAI predictions.

Timing convention used everywhere: a prediction for (season, gw t) may only use
results from gameweeks < t, the FPL snapshot captured after gw t-1 (status,
chance of playing, price, FPL's own ep_next), and the fixture list itself.
"""
