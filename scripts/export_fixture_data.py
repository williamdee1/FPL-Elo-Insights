"""
Export fixture analysis data for the SquadAI Teams tab.

Uses blended team ratings (2025-26 end-of-season baseline + 2026-27 current season
at 3× weight) and 2026-27 upcoming fixtures from the live FPL API.

The current/next gameweek is detected automatically from the FPL bootstrap-static
endpoint, so this script never needs a hardcoded GW number.

Run from repo root:
    conda run -n fpl python FPL-Elo-Insights/scripts/export_fixture_data.py

Output: SquadAI/src/data/fixtureData.json
        SquadAI-native/data/fixtureData.json
"""

import json
import sys
import requests
from pathlib import Path
from collections import defaultdict

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from fixture_analysis import (
    load_team_map,
    load_team_ratings,
    load_upcoming_fixtures,
    build_team_schedule,
    team_totals,
    score_fixture,
    atk_raw,
    def_raw,
)

REPO_ROOT        = Path(__file__).parent.parent.parent
DATA_25_26       = REPO_ROOT / "FPL-Elo-Insights" / "data" / "2025-2026"
DATA_26_27       = REPO_ROOT / "FPL-Elo-Insights" / "data" / "2026-2027"
OUTPUT_PATH        = REPO_ROOT / "SquadAI"        / "src" / "data" / "fixtureData.json"
OUTPUT_PATH_NATIVE = REPO_ROOT / "SquadAI-native" / "data" / "fixtureData.json"

PLANNING_GWS_COUNT = 6   # upcoming GWs to include in fixture grid

# 2025-26 prior baseline for ratings blend
PRIOR_GW_START = 33
PRIOR_GW_END   = 38
PRIOR_CUTOFF   = 37

# 2026-27 current season for ratings blend
CURRENT_GW_START = 1
CURRENT_GW_END   = 2     # update each week alongside other export scripts

PRIOR_WEIGHT   = 1.0
CURRENT_WEIGHT = 3.0     # each current-season game counts 3× vs prior


# ── Blended ratings (mirrors export_team_ratings.py) ─────────────────────────

def _blend_ratings(prior_ratings, current_ratings):
    blank = lambda: {k: 0.0 for k in [
        "xg_h","xga_h","bc_h","bcc_h","sot_h","sotc_h","gc_h","tib_h","n_h",
        "xg_a","xga_a","bc_a","bcc_a","sot_a","sotc_a","gc_a","tib_a","n_a",
    ]}
    merged = defaultdict(blank)

    for ratings, w in [(prior_ratings, PRIOR_WEIGHT), (current_ratings, CURRENT_WEIGHT)]:
        for code, r in ratings.items():
            s = merged[code]
            n_h = r.get("n_home", 0)
            if n_h > 0:
                ww = n_h * w
                for src, dst in [("xg_home","xg_h"),("xga_home","xga_h"),("bc_home","bc_h"),
                                  ("bcc_home","bcc_h"),("sot_home","sot_h"),("sotc_home","sotc_h"),
                                  ("gc_home","gc_h"),("tib_home","tib_h")]:
                    s[dst] += r[src] * ww
                s["n_h"] += ww
            n_a = r.get("n_away", 0)
            if n_a > 0:
                ww = n_a * w
                for src, dst in [("xg_away","xg_a"),("xga_away","xga_a"),("bc_away","bc_a"),
                                  ("bcc_away","bcc_a"),("sot_away","sot_a"),("sotc_away","sotc_a"),
                                  ("gc_away","gc_a"),("tib_away","tib_a")]:
                    s[dst] += r[src] * ww
                s["n_a"] += ww

    def pg(s, key, n_key):
        n = s[n_key]
        return s[key] / n if n > 0 else 0.0

    blended = {}
    for code, s in merged.items():
        blended[code] = {
            "xg_home":   pg(s,"xg_h","n_h"),   "xg_away":   pg(s,"xg_a","n_a"),
            "xga_home":  pg(s,"xga_h","n_h"),  "xga_away":  pg(s,"xga_a","n_a"),
            "bc_home":   pg(s,"bc_h","n_h"),    "bc_away":   pg(s,"bc_a","n_a"),
            "bcc_home":  pg(s,"bcc_h","n_h"),   "bcc_away":  pg(s,"bcc_a","n_a"),
            "sot_home":  pg(s,"sot_h","n_h"),   "sot_away":  pg(s,"sot_a","n_a"),
            "sotc_home": pg(s,"sotc_h","n_h"),  "sotc_away": pg(s,"sotc_a","n_a"),
            "gc_home":   pg(s,"gc_h","n_h"),    "gc_away":   pg(s,"gc_a","n_a"),
            "tib_home":  pg(s,"tib_h","n_h"),   "tib_away":  pg(s,"tib_a","n_a"),
            "n_home":    s["n_h"],               "n_away":    s["n_a"],
        }

    atk_h = [atk_raw(r,"home") for r in blended.values()]
    atk_a = [atk_raw(r,"away") for r in blended.values()]
    def_h = [def_raw(r,"home") for r in blended.values()]
    def_a = [def_raw(r,"away") for r in blended.values()]

    def norm(val, vals, lo=1.0, hi=10.0):
        mn, mx = min(vals), max(vals)
        return 5.0 if mx == mn else lo + (val - mn) / (mx - mn) * (hi - lo)

    for code, r in blended.items():
        r["atk_home_score"] = norm(atk_raw(r,"home"), atk_h)
        r["atk_away_score"] = norm(atk_raw(r,"away"), atk_a)
        r["def_home_score"] = norm(def_raw(r,"home"), def_h, lo=10.0, hi=1.0)
        r["def_away_score"] = norm(def_raw(r,"away"), def_a, lo=10.0, hi=1.0)

    return blended


# ── FPL API: detect the next gameweek ────────────────────────────────────────

def get_next_gw() -> int:
    """Return the next GW from FPL bootstrap-static. Falls back to CURRENT_GW_END+1."""
    try:
        data = requests.get(
            "https://fantasy.premierleague.com/api/bootstrap-static/",
            timeout=15,
        ).json()
        events = data.get("events", [])
        next_gw = next((e["id"] for e in events if e.get("is_next")), None)
        if next_gw:
            return next_gw
        current_gw = next((e["id"] for e in events if e.get("is_current")), None)
        if current_gw:
            return current_gw + 1
    except Exception as exc:
        print(f"  Warning: FPL API unavailable ({exc}), falling back to GW{CURRENT_GW_END + 1}")
    return CURRENT_GW_END + 1


# ── Fixture builder ───────────────────────────────────────────────────────────

def build_entry(team_code, metric, schedule, planning_gws, code_to_short):
    total_atk, total_def, n_games = team_totals(schedule, team_code, planning_gws)
    total = total_atk if metric == "attacking" else total_def
    fixtures_by_gw = {}
    for gw in planning_gws:
        gw_fixtures = schedule[team_code].get(gw, [])
        fixtures_by_gw[str(gw)] = [
            {
                "score": round(f["attacker" if metric == "attacking" else "defender"], 1),
                "opponent": code_to_short.get(f["opponent"], "???"),
                "ha": f["ha"],
            }
            for f in gw_fixtures
        ]
    return {
        "team":       code_to_short.get(team_code, str(team_code)),
        "totalScore": round(total, 1),
        "nGames":     n_games,
        "fixtures":   fixtures_by_gw,
    }


def main():
    next_gw = get_next_gw()
    planning_gws = list(range(next_gw, next_gw + PLANNING_GWS_COUNT))
    print(f"Planning GWs: {planning_gws}")

    # ── Blended ratings ───────────────────────────────────────────────────────
    print(f"Loading 2025-26 prior ratings  GW{PRIOR_GW_START}–GW{PRIOR_GW_END} ...")
    prior_ratings = load_team_ratings(PRIOR_GW_START, PRIOR_GW_END, PRIOR_CUTOFF, base=DATA_25_26)

    print(f"Loading 2026-27 current ratings GW{CURRENT_GW_START}–GW{CURRENT_GW_END} ...")
    current_ratings = load_team_ratings(CURRENT_GW_START, CURRENT_GW_END, CURRENT_GW_START, base=DATA_26_27)

    print("Blending seasons ...")
    ratings = _blend_ratings(prior_ratings, current_ratings)

    # ── Team map from current season ──────────────────────────────────────────
    code_to_short = load_team_map(CURRENT_GW_END, base=DATA_26_27)

    # ── Upcoming 2026-27 fixtures ─────────────────────────────────────────────
    fixtures = load_upcoming_fixtures(planning_gws, base=DATA_26_27)
    print(f"Loaded {len(fixtures)} upcoming fixtures for GW{planning_gws[0]}–GW{planning_gws[-1]}")

    schedule = build_team_schedule(fixtures, ratings, code_to_short)
    all_teams = list(code_to_short.keys())

    attacking = sorted(
        [build_entry(t, "attacking", schedule, planning_gws, code_to_short) for t in all_teams],
        key=lambda x: x["totalScore"], reverse=True,
    )
    defensive = sorted(
        [build_entry(t, "defensive", schedule, planning_gws, code_to_short) for t in all_teams],
        key=lambda x: x["totalScore"], reverse=True,
    )
    for rank, entry in enumerate(attacking, 1): entry["rank"] = rank
    for rank, entry in enumerate(defensive, 1): entry["rank"] = rank

    output = {
        "gameweek":    next_gw,
        "planningGws": planning_gws,
        "attacking":   attacking,
        "defensive":   defensive,
    }

    for path in (OUTPUT_PATH, OUTPUT_PATH_NATIVE):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        print(f"Saved -> {path}")

    print(f"  Top attacking: {attacking[0]['team']} ({attacking[0]['totalScore']})")
    print(f"  Top defensive: {defensive[0]['team']} ({defensive[0]['totalScore']})")


if __name__ == "__main__":
    main()
