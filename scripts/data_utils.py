"""
data_utils.py — shared data-loading helpers for all SquadAI export scripts.

All functions take a `data_base: Path` argument pointing to the season data dir,
e.g. REPO_ROOT / "FPL-Elo-Insights" / "data" / "2026-2027".

Player IDs are FPL IDs (same as the FotMob IDs in players.csv / playermatchstats.csv).
"""

import csv
from pathlib import Path
from collections import defaultdict

# ── Position helpers ──────────────────────────────────────────────────────────

POS_MAP = {"Goalkeeper": "GKP", "Defender": "DEF", "Midfielder": "MID", "Forward": "FWD"}


def load_teams(data_base: Path) -> dict:
    """Return {team_code_str: short_name} from teams.csv."""
    result = {}
    with open(data_base / "teams.csv", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            result[row["code"]] = row["short_name"]
    return result


def load_player_meta(data_base: Path, latest_gw: int) -> dict:
    """
    Return {player_id_str: {name, team, position, price, ownership, status}}
    sourced from GW{latest_gw}/players.csv  +  GW{latest_gw}/player_gameweek_stats.csv.
    """
    teams = load_teams(data_base)

    # team_code + position from per-GW players.csv (FotMob IDs = FPL IDs)
    player_tp: dict = {}
    players_file = data_base / "By Gameweek" / f"GW{latest_gw}" / "players.csv"
    with open(players_file, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            player_tp[row["player_id"]] = {
                "team": teams.get(row["team_code"], "?"),
                "position": POS_MAP.get(row["position"], "?"),
            }

    # price / ownership / status / name from GW player_gameweek_stats.csv
    stats_file = data_base / "By Gameweek" / f"GW{latest_gw}" / "player_gameweek_stats.csv"
    meta: dict = {}
    with open(stats_file, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            pid = row["id"]
            tp = player_tp.get(pid, {"team": "?", "position": "?"})
            meta[pid] = {
                "name":      row.get("web_name", ""),
                "team":      tp["team"],
                "position":  tp["position"],
                "price":     float(row.get("now_cost") or 0),
                "ownership": float(row.get("selected_by_percent") or 0),
                "status":    row.get("status", "a"),
            }
    return meta


def _float(val) -> float:
    """Safe float conversion for potentially-empty CSV values."""
    if val is None or val == "":
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def load_gw_player_stats(gw: int, data_base: Path) -> dict:
    """
    Return {player_id_str: dict_of_floats} for all players who appeared in GW{gw}.
    Returns empty dict if file missing or has no rows.
    """
    path = data_base / "By Gameweek" / f"GW{gw}" / "player_gameweek_stats.csv"
    if not path.exists():
        return {}
    result = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            if _float(row.get("minutes")) > 0:
                result[row["id"]] = row
    return result


def load_gw_matchstats(gw: int, data_base: Path) -> dict:
    """
    Return {player_id_str: {xg, xa, total_shots, tib, key_passes, ...}} for GW{gw}.
    Sums across multiple matches (DGWs). Returns empty dict if file missing.
    """
    path = data_base / "By Gameweek" / f"GW{gw}" / "playermatchstats.csv"
    if not path.exists():
        return {}

    SUM_COLS = [
        "minutes_played", "goals", "assists",
        "total_shots", "xg", "xa",
        "shots_on_target", "touches_opposition_box", "chances_created",
        "tackles_won", "interceptions", "recoveries", "clearances", "blocks",
    ]
    accum: dict = defaultdict(lambda: {c: 0.0 for c in SUM_COLS})
    with open(path, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            pid = row["player_id"]
            for col in SUM_COLS:
                accum[pid][col] += _float(row.get(col))
    return dict(accum)


def accumulate_player_stats(
    gw_start: int,
    gw_end: int,
    data_base: Path,
) -> dict:
    """
    Aggregate player stats over GW{gw_start}..GW{gw_end} (inclusive).

    Returns {player_id_str: stats_dict} where each stats_dict contains:
      From player_gameweek_stats (per-GW sums):
        minutes, goals_scored, assists, clean_sheets, goals_conceded_total,
        saves_total, bonus, expected_goals_conceded, clearances_blocks_interceptions,
        event_points, games

      From playermatchstats (per-GW sums):
        xg, xa, total_shots, shots_on_target, tib (touches_opposition_box), key_passes (chances_created)
    """
    totals: dict = defaultdict(lambda: {
        "minutes": 0.0,
        "goals_scored": 0.0,
        "assists": 0.0,
        "clean_sheets": 0.0,
        "goals_conceded_total": 0.0,
        "saves_total": 0.0,
        "bonus": 0.0,
        "expected_goals_conceded": 0.0,
        "clearances_blocks_interceptions": 0.0,
        "event_points": 0.0,
        "games": 0,
        # from matchstats
        "xg": 0.0,
        "xa": 0.0,
        "total_shots": 0.0,
        "shots_on_target": 0.0,
        "tib": 0.0,
        "key_passes": 0.0,
        # track GW-by-GW event_points for sparkline
        "points_history": [],
    })

    for gw in range(gw_start, gw_end + 1):
        gw_stats   = load_gw_player_stats(gw, data_base)
        gw_matches = load_gw_matchstats(gw, data_base)

        for pid, row in gw_stats.items():
            t = totals[pid]
            t["minutes"]                   += _float(row.get("minutes"))
            t["goals_scored"]              += _float(row.get("goals_scored"))
            t["assists"]                   += _float(row.get("assists"))
            t["clean_sheets"]              += _float(row.get("clean_sheets"))
            t["goals_conceded_total"]      += _float(row.get("goals_conceded"))
            t["saves_total"]               += _float(row.get("saves"))
            t["bonus"]                     += _float(row.get("bonus"))
            t["expected_goals_conceded"]   += _float(row.get("expected_goals_conceded"))
            t["clearances_blocks_interceptions"] += _float(row.get("clearances_blocks_interceptions"))
            ep = _float(row.get("event_points"))
            t["event_points"]              += ep
            t["games"]                     += 1
            t["points_history"].append(ep)

            # Merge matchstats if available
            ms = gw_matches.get(pid)
            if ms:
                t["xg"]              += ms.get("xg", 0.0)
                t["xa"]              += ms.get("xa", 0.0)
                t["total_shots"]     += ms.get("total_shots", 0.0)
                t["shots_on_target"] += ms.get("shots_on_target", 0.0)
                t["tib"]             += ms.get("touches_opposition_box", 0.0)
                t["key_passes"]      += ms.get("chances_created", 0.0)

    return dict(totals)


def compute_player_stat_record(totals: dict) -> dict:
    """
    Convert raw accumulated totals into a normalised per-game / per-90 record
    suitable for playerStatsData.json.
    """
    games   = max(totals["games"], 1)
    minutes = max(totals["minutes"], 1)

    saves  = totals["saves_total"]
    gc     = totals["goals_conceded_total"]
    xgc    = totals["expected_goals_conceded"]

    return {
        "xgi":         round((totals["xg"] + totals["xa"]) / games, 3),
        "shots":       round(totals["total_shots"] / games, 2),
        "tib":         round(totals["tib"] / games, 2),
        "key_passes":  round(totals["key_passes"] / games, 2),
        # Goals prevented per game: xGC - actual goals conceded
        "g_prev":      round((xgc - gc) / games, 4),
        "defcon":      round(totals["clearances_blocks_interceptions"], 1),
        "saves":       round(saves, 1),
        "goals_conceded": round(gc, 1),
        "save_pct":    round(saves / (saves + gc), 3) if (saves + gc) > 0 else 0.0,
        "bonus":       round(totals["bonus"], 1),
        "cs":          round(totals["clean_sheets"], 1),
        "xcg_per90":   round(xgc / minutes * 90, 3),
        "minutes":     round(totals["minutes"], 1),
        "games":       totals["games"],
    }
