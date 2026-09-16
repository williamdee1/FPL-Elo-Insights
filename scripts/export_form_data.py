"""
Export hot/cold form data for the SquadAI Form tab position views.

Hot  = players whose recent FPL points/game (last RECENT_GWS) are rising
       vs their comparison window (COMPARISON_GWS prior to that).
Cold = players who were performing well earlier but have declined recently.

Early season (< FORM_UNLOCKS_GW completed GWs): hot/cold lists are empty —
the app's EarlyRankedView takes over instead (uses live bootstrap data).

Run from repo root:
    conda run -n fpl python FPL-Elo-Insights/scripts/export_form_data.py

Output: SquadAI-native/data/formData.json
"""

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from data_utils import load_player_meta, accumulate_player_stats, _float

REPO_ROOT   = Path(__file__).parent.parent.parent
DATA_26_27  = REPO_ROOT / "FPL-Elo-Insights" / "data" / "2026-2027"
OUTPUT_PATH = REPO_ROOT / "SquadAI-native" / "data" / "formData.json"

# ── Season config ──────────────────────────────────────────────────────────────
LAST_COMPLETE_GW    = 4   # last GW with completed data
RECENT_GWS       = 3   # "recent" window for trend
COMPARISON_GWS   = 4   # "comparison" window before that
FORM_UNLOCKS_GW  = 7   # hot/cold needs this many GWs total (RECENT + COMPARISON)
TOP_N            = 20  # players per position per mode


def _build_form_players(gw_end, recent_gws, comparison_gws, data_base, meta):
    """
    Compute hot/cold lists for each position.

    recent window:     GW(gw_end - recent_gws + 1) .. gw_end
    comparison window: GW(gw_end - recent_gws - comparison_gws + 1) .. GW(gw_end - recent_gws)

    Returns {pos: {hot: [...], cold: [...]}}
    """
    recent_start     = max(1, gw_end - recent_gws + 1)
    comparison_start = max(1, gw_end - recent_gws - comparison_gws + 1)
    comparison_end   = max(0, gw_end - recent_gws)

    if comparison_end < comparison_start:
        # Not enough history — return empty lists
        return {pos: {"hot": [], "cold": []} for pos in ("FWD", "MID", "DEF", "GKP")}

    recent_totals  = accumulate_player_stats(recent_start,     gw_end,       data_base)
    earlier_totals = accumulate_player_stats(comparison_start, comparison_end, data_base)

    # Group players by position
    pos_players: dict = {pos: [] for pos in ("FWD", "MID", "DEF", "GKP")}

    for pid, r_tot in recent_totals.items():
        if r_tot["games"] == 0:
            continue
        m = meta.get(pid)
        if not m or m["position"] not in pos_players:
            continue

        recent_avg = r_tot["event_points"] / r_tot["games"]

        e_tot = earlier_totals.get(pid)
        if not e_tot or e_tot["games"] == 0:
            continue
        earlier_avg = e_tot["event_points"] / e_tot["games"]

        if earlier_avg == 0:
            trend_pct = 100.0 if recent_avg > 0 else 0.0
        else:
            trend_pct = (recent_avg - earlier_avg) / earlier_avg * 100.0

        # GW-by-GW history for sparkline (recent window only)
        history = r_tot["points_history"]

        pos_players[m["position"]].append({
            "id":         int(pid),
            "name":       m["name"],
            "team":       m["team"],
            "price":      m["price"],
            "ownership":  m["ownership"],
            "recentAvg":  round(recent_avg, 2),
            "earlierAvg": round(earlier_avg, 2),
            "trendPct":   round(trend_pct, 1),
            "history":    [round(v, 1) for v in history],
            "status":     m["status"],
        })

    result = {}
    for pos, players in pos_players.items():
        # Hot: rising trend, ranked by trendPct desc — must have positive trend
        hot = sorted(
            [p for p in players if p["trendPct"] > 0 and p["recentAvg"] >= 3],
            key=lambda x: -x["trendPct"],
        )[:TOP_N]

        # Cold: formerly strong (earlierAvg >= 5), now declining
        cold = sorted(
            [p for p in players if p["trendPct"] < 0 and p["earlierAvg"] >= 5],
            key=lambda x: x["trendPct"],
        )[:TOP_N]

        result[pos] = {"hot": hot, "cold": cold}

    return result


def main():
    print(f"Season GW{LAST_COMPLETE_GW}, recent={RECENT_GWS}, comparison={COMPARISON_GWS}")

    meta = load_player_meta(DATA_26_27, LAST_COMPLETE_GW)
    print(f"Loaded metadata for {len(meta)} players")

    total_gws_needed = RECENT_GWS + COMPARISON_GWS

    if LAST_COMPLETE_GW >= FORM_UNLOCKS_GW:
        print(f"Building hot/cold lists (GW{LAST_COMPLETE_GW} >= GW{FORM_UNLOCKS_GW}) ...")
        pos_data = _build_form_players(
            LAST_COMPLETE_GW, RECENT_GWS, COMPARISON_GWS, DATA_26_27, meta
        )
    else:
        print(
            f"Early season (GW{LAST_COMPLETE_GW} < GW{FORM_UNLOCKS_GW}) — "
            f"hot/cold lists will be empty (app shows EarlyRankedView)"
        )
        pos_data = {pos: {"hot": [], "cold": []} for pos in ("FWD", "MID", "DEF", "GKP")}

    output = {
        "gameweek": LAST_COMPLETE_GW,
        **pos_data,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    for pos in ("FWD", "MID", "DEF", "GKP"):
        hot_n  = len(pos_data[pos]["hot"])
        cold_n = len(pos_data[pos]["cold"])
        print(f"  {pos}: {hot_n} hot, {cold_n} cold")

    print(f"\nSaved -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
