"""
Export per-team attack/defense ratings for SquadAI Teams and Squad tabs.

Strategy: blend two seasons to balance recency with sample size.
  - 2025-26 GW33-38 (last 6 GWs of prior season) — prior / baseline
  - 2026-27 GW1-2   (current season so far)       — current form, 3× weight

With only 2 GWs of current-season data each team has played at most 1 home and
1 away game, so pure 2026-27 ratings would be too noisy. The blend keeps ratings
meaningful while prioritising new-season evidence.

Run from repo root:
    conda run -n fpl python FPL-Elo-Insights/scripts/export_team_ratings.py

Output: SquadAI-native/data/teamRatingsData.json
"""

import json
import sys
import csv
import datetime
from pathlib import Path
from collections import defaultdict

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from fixture_analysis import load_team_map, load_team_ratings, atk_raw, def_raw

REPO_ROOT   = Path(__file__).parent.parent.parent
DATA_25_26  = REPO_ROOT / "FPL-Elo-Insights" / "data" / "2025-2026"
DATA_26_27  = REPO_ROOT / "FPL-Elo-Insights" / "data" / "2026-2027"
OUTPUT_PATH = REPO_ROOT / "SquadAI-native" / "data" / "teamRatingsData.json"

# 2025-26 prior: last 6 GWs of the season, recent 2 weighted ×2
PRIOR_GW_START   = 33
PRIOR_GW_END     = 38
PRIOR_CUTOFF     = 37  # GW37-38 weighted ×2 within the prior block
PRIOR_WEIGHT     = 1.0

# 2026-27 current: all completed GWs so far, uniform weight per game
CURRENT_GW_START = 1
CURRENT_GW_END   = 2
CURRENT_WEIGHT   = 3.0  # each current-season game counts 3× vs a prior-season game


_FIELDS_H = ["xg_h","xga_h","bc_h","bcc_h","sot_h","sotc_h","gc_h","tib_h","n_h"]
_FIELDS_A = ["xg_a","xga_a","bc_a","bcc_a","sot_a","sotc_a","gc_a","tib_a","n_a"]

def _accumulate(stats_out, ratings_in, season_weight):
    """Merge raw per-game averages back into a stats accumulator."""
    for team_code, r in ratings_in.items():
        s = stats_out[team_code]
        # home
        n_h = r.get("n_home", 0)
        if n_h > 0:
            w = n_h * season_weight
            s["xg_h"]   += r["xg_home"]   * w
            s["xga_h"]  += r["xga_home"]  * w
            s["bc_h"]   += r["bc_home"]   * w
            s["bcc_h"]  += r["bcc_home"]  * w
            s["sot_h"]  += r["sot_home"]  * w
            s["sotc_h"] += r["sotc_home"] * w
            s["gc_h"]   += r["gc_home"]   * w
            s["tib_h"]  += r["tib_home"]  * w
            s["n_h"]    += w
        # away
        n_a = r.get("n_away", 0)
        if n_a > 0:
            w = n_a * season_weight
            s["xg_a"]   += r["xg_away"]   * w
            s["xga_a"]  += r["xga_away"]  * w
            s["bc_a"]   += r["bc_away"]   * w
            s["bcc_a"]  += r["bcc_away"]  * w
            s["sot_a"]  += r["sot_away"]  * w
            s["sotc_a"] += r["sotc_away"] * w
            s["gc_a"]   += r["gc_away"]   * w
            s["tib_a"]  += r["tib_away"]  * w
            s["n_a"]    += w


def blend_ratings(prior_ratings, current_ratings):
    """
    Merge prior (2025-26) and current (2026-27) per-game averages into a single
    blended stats dict, then re-normalise to 1-10.
    """
    blank = lambda: {k: 0.0 for k in _FIELDS_H + _FIELDS_A}
    merged = defaultdict(blank)

    _accumulate(merged, prior_ratings,   PRIOR_WEIGHT)
    _accumulate(merged, current_ratings, CURRENT_WEIGHT)

    # Recompute per-game averages
    def pg(s, key, n_key):
        n = s[n_key]
        return s[key] / n if n > 0 else 0.0

    blended = {}
    for team, s in merged.items():
        blended[team] = {
            "xg_home":   pg(s, "xg_h",   "n_h"),
            "xg_away":   pg(s, "xg_a",   "n_a"),
            "xga_home":  pg(s, "xga_h",  "n_h"),
            "xga_away":  pg(s, "xga_a",  "n_a"),
            "bc_home":   pg(s, "bc_h",   "n_h"),
            "bc_away":   pg(s, "bc_a",   "n_a"),
            "bcc_home":  pg(s, "bcc_h",  "n_h"),
            "bcc_away":  pg(s, "bcc_a",  "n_a"),
            "sot_home":  pg(s, "sot_h",  "n_h"),
            "sot_away":  pg(s, "sot_a",  "n_a"),
            "sotc_home": pg(s, "sotc_h", "n_h"),
            "sotc_away": pg(s, "sotc_a", "n_a"),
            "gc_home":   pg(s, "gc_h",   "n_h"),
            "gc_away":   pg(s, "gc_a",   "n_a"),
            "tib_home":  pg(s, "tib_h",  "n_h"),
            "tib_away":  pg(s, "tib_a",  "n_a"),
            "n_home":    s["n_h"],
            "n_away":    s["n_a"],
        }

    atk_h_vals = [atk_raw(r, "home") for r in blended.values()]
    atk_a_vals = [atk_raw(r, "away") for r in blended.values()]
    def_h_vals = [def_raw(r, "home") for r in blended.values()]
    def_a_vals = [def_raw(r, "away") for r in blended.values()]

    def normalise(val, vals, lo=1.0, hi=10.0):
        mn, mx = min(vals), max(vals)
        if mx == mn:
            return 5.0
        return lo + (val - mn) / (mx - mn) * (hi - lo)

    for team, r in blended.items():
        r["atk_home_score"] = normalise(atk_raw(r, "home"), atk_h_vals)
        r["atk_away_score"] = normalise(atk_raw(r, "away"), atk_a_vals)
        r["def_home_score"] = normalise(def_raw(r, "home"), def_h_vals, lo=10.0, hi=1.0)
        r["def_away_score"] = normalise(def_raw(r, "away"), def_a_vals, lo=10.0, hi=1.0)

    return blended


def main():
    print(f"Loading 2025-26 prior  GW{PRIOR_GW_START}–GW{PRIOR_GW_END} ...")
    prior_ratings = load_team_ratings(
        PRIOR_GW_START, PRIOR_GW_END, PRIOR_CUTOFF,
        base=DATA_25_26,
    )

    print(f"Loading 2026-27 current GW{CURRENT_GW_START}–GW{CURRENT_GW_END} ...")
    current_ratings = load_team_ratings(
        CURRENT_GW_START, CURRENT_GW_END, CURRENT_GW_START,
        base=DATA_26_27,
    )

    print("Blending seasons (prior ×1, current ×3 per game) ...")
    blended = blend_ratings(prior_ratings, current_ratings)

    # Use 2026-27 GW2 teams.csv for the short-name map (current season codes)
    code_to_short = load_team_map(CURRENT_GW_END, base=DATA_26_27)

    output_ratings: dict[str, dict] = {}
    for team_code, r in blended.items():
        short = code_to_short.get(team_code)
        if not short:
            continue
        output_ratings[short] = {
            "atk_home": round(r["atk_home_score"], 2),
            "atk_away": round(r["atk_away_score"], 2),
            "def_home": round(r["def_home_score"], 2),
            "def_away": round(r["def_away_score"], 2),
        }

    output = {
        "generatedAt": datetime.date.today().isoformat(),
        "basedOnGws":  f"2025-26 GW{PRIOR_GW_START}-{PRIOR_GW_END} (prior) + 2026-27 GW{CURRENT_GW_START}-{CURRENT_GW_END} (3× weight)",
        "season":      "2026-27",
        "note":        f"Blended: prior-season baseline + {CURRENT_GW_END} GWs of current season at 3× weight",
        "ratings":     output_ratings,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved {len(output_ratings)} teams -> {OUTPUT_PATH}")
    print("\nTop attacking teams (home):")
    for team, r in sorted(output_ratings.items(), key=lambda x: -x[1]["atk_home"])[:5]:
        print(f"  {team}: {r['atk_home']}")
    print("\nTop defensive teams (home):")
    for team, r in sorted(output_ratings.items(), key=lambda x: -x[1]["def_home"])[:5]:
        print(f"  {team}: {r['def_home']}")
    print("\nTop attacking teams (away):")
    for team, r in sorted(output_ratings.items(), key=lambda x: -x[1]["atk_away"])[:5]:
        print(f"  {team}: {r['atk_away']}")


if __name__ == "__main__":
    main()
