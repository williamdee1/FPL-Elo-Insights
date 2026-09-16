"""
Export per-player match stats for SquadAI Form tab radar charts.

Produces three windows:
  season     — all completed GWs (GW1..LAST_COMPLETE_GW)
  recent     — last RECENT_GWS gameweeks
  formRecent — last FORM_RECENT_GWS gameweeks (used for hot/cold sparklines)

Run from repo root:
    conda run -n fpl python FPL-Elo-Insights/scripts/export_player_stats.py

Output: SquadAI-native/data/playerStatsData.json
"""

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from data_utils import (
    load_player_meta,
    accumulate_player_stats,
    compute_player_stat_record,
)

REPO_ROOT   = Path(__file__).parent.parent.parent
DATA_26_27  = REPO_ROOT / "FPL-Elo-Insights" / "data" / "2026-2027"
OUTPUT_PATH = REPO_ROOT / "SquadAI-native" / "data" / "playerStatsData.json"

# ── Season config ──────────────────────────────────────────────────────────────
# Update LAST_COMPLETE_GW each gameweek as new data lands.
LAST_COMPLETE_GW   = 4    # last GW with completed player_gameweek_stats data
RECENT_GWS      = 5    # "recent" window for radar baseline
FORM_RECENT_GWS = 3    # short window for hot/cold sparkline


def main():
    print(f"Season GW1–GW{LAST_COMPLETE_GW}, recent={RECENT_GWS}, formRecent={FORM_RECENT_GWS}")

    # ── Player metadata (name, team, position, price, ownership) ──────────────
    meta = load_player_meta(DATA_26_27, LAST_COMPLETE_GW)
    print(f"Loaded metadata for {len(meta)} players")

    # ── Season window (all GWs) ───────────────────────────────────────────────
    season_totals = accumulate_player_stats(1, LAST_COMPLETE_GW, DATA_26_27)

    # ── Recent window ─────────────────────────────────────────────────────────
    recent_start = max(1, LAST_COMPLETE_GW - RECENT_GWS + 1)
    recent_totals = accumulate_player_stats(recent_start, LAST_COMPLETE_GW, DATA_26_27)

    # ── Form recent window ────────────────────────────────────────────────────
    form_start = max(1, LAST_COMPLETE_GW - FORM_RECENT_GWS + 1)
    form_totals = accumulate_player_stats(form_start, LAST_COMPLETE_GW, DATA_26_27)

    # ── Build output ──────────────────────────────────────────────────────────
    season_out     = {}
    recent_out     = {}
    form_out       = {}

    all_pids = set(season_totals) | set(recent_totals) | set(form_totals)
    for pid in all_pids:
        if pid not in meta:
            continue  # skip players with no metadata

        if pid in season_totals and season_totals[pid]["games"] > 0:
            season_out[pid] = compute_player_stat_record(season_totals[pid])

        if pid in recent_totals and recent_totals[pid]["games"] > 0:
            recent_out[pid] = compute_player_stat_record(recent_totals[pid])

        if pid in form_totals and form_totals[pid]["games"] > 0:
            form_out[pid] = compute_player_stat_record(form_totals[pid])

    output = {
        "gameweek":      LAST_COMPLETE_GW,
        "recentGws":     RECENT_GWS,
        "formRecentGws": FORM_RECENT_GWS,
        "season":        season_out,
        "recent":        recent_out,
        "formRecent":    form_out,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Saved {len(season_out)} players -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
