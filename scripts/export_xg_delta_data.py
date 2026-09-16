"""
Export xG Delta data for the SquadAI Form tab "Goals Imminent?" view.

xG Delta = Goals − xG (total over recent window).
Negative delta = player is scoring fewer goals than their xG -> due a goal.
Positive delta = overperforming their xG.

Only includes players with ≥ MIN_ATTEMPTS shots over the window.

Run from repo root:
    conda run -n fpl python FPL-Elo-Insights/scripts/export_xg_delta_data.py

Output: SquadAI-native/data/xgDeltaData.json
"""

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from data_utils import load_player_meta, accumulate_player_stats

REPO_ROOT   = Path(__file__).parent.parent.parent
DATA_26_27  = REPO_ROOT / "FPL-Elo-Insights" / "data" / "2026-2027"
OUTPUT_PATH = REPO_ROOT / "SquadAI-native" / "data" / "xgDeltaData.json"

# ── Season config ──────────────────────────────────────────────────────────────
LAST_COMPLETE_GW  = 4   # last GW with completed data
RECENT_GWS     = 4   # window for xG delta ranking
MIN_ATTEMPTS   = 3   # min shots to qualify (early season = lower threshold)
POSITIONS      = {"FWD", "MID", "DEF"}   # GKPs excluded
TOP_N          = 10

POS_LABEL = {"FWD": "Forward", "MID": "Midfielder", "DEF": "Defender", "GKP": "Goalkeeper"}


def main():
    recent_start = max(1, LAST_COMPLETE_GW - RECENT_GWS + 1)
    print(f"xG Delta — GW{recent_start}–GW{LAST_COMPLETE_GW}, min {MIN_ATTEMPTS} attempts")

    meta          = load_player_meta(DATA_26_27, LAST_COMPLETE_GW)
    recent_totals = accumulate_player_stats(recent_start, LAST_COMPLETE_GW, DATA_26_27)

    players = []
    for pid, r_tot in recent_totals.items():
        if r_tot["games"] == 0:
            continue
        m = meta.get(pid)
        if not m or m["position"] not in POSITIONS:
            continue

        total_shots = r_tot["total_shots"]
        if total_shots < MIN_ATTEMPTS:
            continue

        total_xg = r_tot["xg"]
        total_goals = r_tot["goals_scored"]
        xg_delta = round(total_goals - total_xg, 2)   # negative = lucky / due a goal

        players.append({
            "id":            int(pid),
            "name":          m["name"],
            "team":          m["team"],
            "position":      POS_LABEL.get(m["position"], m["position"]),
            "price":         m["price"],
            "ownership":     m["ownership"],
            "xgDelta":       xg_delta,
            "goals":         int(total_goals),
            "xg":            round(total_xg, 2),
            "totalShots":    int(total_shots),
            "shotsOnTarget": int(r_tot.get("shots_on_target", 0)),
            "attInBox":      int(r_tot["tib"]),
        })

    # Sort by xg_delta ascending (most negative = most due a goal = top of list)
    players.sort(key=lambda x: x["xgDelta"])
    players = players[:TOP_N]

    print(f"  Top xG delta players: {[p['name'] for p in players[:5]]}")

    output = {
        "gameweek":    LAST_COMPLETE_GW,
        "recentGws":   RECENT_GWS,
        "minAttempts": MIN_ATTEMPTS,
        "players":     players,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Saved -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
