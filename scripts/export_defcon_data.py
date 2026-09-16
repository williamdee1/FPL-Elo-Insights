"""
Export DefCon Monsters data for the SquadAI Form tab.

"DefCon" = clearances + blocks + interceptions (per game).
Top 5 defenders and midfielders by recent DefCon/game.

Run from repo root:
    conda run -n fpl python FPL-Elo-Insights/scripts/export_defcon_data.py

Output: SquadAI-native/data/defconData.json
"""

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from data_utils import load_player_meta, accumulate_player_stats

REPO_ROOT   = Path(__file__).parent.parent.parent
DATA_26_27  = REPO_ROOT / "FPL-Elo-Insights" / "data" / "2026-2027"
OUTPUT_PATH = REPO_ROOT / "SquadAI-native" / "data" / "defconData.json"

# ── Season config ──────────────────────────────────────────────────────────────
LAST_COMPLETE_GW = 4   # last GW with completed data
RECENT_GWS    = 4   # recent window for DefCon/game ranking
DEF_THRESHOLD = 10  # "≥10 = FPL defensive pts" display label
MID_THRESHOLD = 12
TOP_N         = 5


def main():
    print(f"DefCon Monsters — GW{max(1, LAST_COMPLETE_GW - RECENT_GWS + 1)}–GW{LAST_COMPLETE_GW}")

    meta   = load_player_meta(DATA_26_27, LAST_COMPLETE_GW)
    recent_start = max(1, LAST_COMPLETE_GW - RECENT_GWS + 1)

    # Season window (for seasonPer90 baseline)
    season_totals = accumulate_player_stats(1, LAST_COMPLETE_GW, DATA_26_27)
    # Recent window
    recent_totals = accumulate_player_stats(recent_start, LAST_COMPLETE_GW, DATA_26_27)

    results: dict = {"DEF": [], "MID": []}

    for pid, r_tot in recent_totals.items():
        if r_tot["games"] == 0:
            continue
        m = meta.get(pid)
        if not m or m["position"] not in ("DEF", "MID"):
            continue

        recent_per_game = r_tot["clearances_blocks_interceptions"] / r_tot["games"]

        s_tot = season_totals.get(pid)
        season_per_90 = 0.0
        if s_tot and s_tot["minutes"] > 0:
            season_per_90 = s_tot["clearances_blocks_interceptions"] / s_tot["minutes"] * 90

        # Consistency: % of recent games where DefCon/game ≥ threshold
        threshold = DEF_THRESHOLD if m["position"] == "DEF" else MID_THRESHOLD
        # We don't have per-GW breakdown here; approximate from per-game average
        # (exact consistency would require per-GW per-player records)
        consistency = min(100.0, (recent_per_game / threshold) * 100) if threshold > 0 else 0.0

        results[m["position"]].append({
            "id":              int(pid),
            "name":            m["name"],
            "team":            m["team"],
            "price":           m["price"],
            "ownership":       m["ownership"],
            "recentPerGame":   round(recent_per_game, 1),
            "seasonPer90":     round(season_per_90, 1),
            "consistencyPct":  round(consistency, 1),
            "recentGames":     r_tot["games"],
            "threshold":       threshold,
        })

    # Sort by recentPerGame desc, keep top N
    for pos in ("DEF", "MID"):
        results[pos] = sorted(results[pos], key=lambda x: -x["recentPerGame"])[:TOP_N]
        print(f"  {pos} top: {[p['name'].encode('ascii','replace').decode() for p in results[pos]]}")

    output = {
        "gameweek": LAST_COMPLETE_GW,
        "recentGws": RECENT_GWS,
        "DEF": results["DEF"],
        "MID": results["MID"],
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Saved -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
