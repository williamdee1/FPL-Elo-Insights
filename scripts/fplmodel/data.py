"""Canonical, season-agnostic tables built from the raw FPL-Elo-Insights CSVs.

Two tables feed every model:

player_gw  one row per (season, gw, code): FPL points and per-GW stats, the
           player's team that week, and `snap_*` fields captured *after* that
           gameweek (usable as pre-deadline information for gw + 1).
fixtures   one row per Premier League match: teams, scores, xG and team stats.

Source layouts differ by season:
  2024-2025  gws/merged_gw.csv (one row per player-fixture) + matches/GW*/matches.csv
  2025-2026+ By Gameweek/GW*/{player_gameweek_stats,players,fixtures}.csv
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import polars as pl

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
PL_TOURNAMENTS = {"prem", "premier-league"}
PEN_XG_PER_MATCH = 0.11  # mean (player xG sum - match npxG), 2025-26

POS_MAP = {
    "GK": "GK", "GKP": "GK", "Goalkeeper": "GK",
    "DEF": "DEF", "Defender": "DEF",
    "MID": "MID", "Midfielder": "MID",
    "FWD": "FWD", "Forward": "FWD",
}

PLAYER_GW_SCHEMA = {
    "season": pl.Utf8, "gw": pl.Int64, "element": pl.Int64, "code": pl.Int64,
    "name": pl.Utf8, "pos": pl.Utf8, "team": pl.Int64,
    "points": pl.Float64, "minutes": pl.Float64, "starts": pl.Float64,
    "goals": pl.Float64, "assists": pl.Float64, "cs": pl.Float64, "gc": pl.Float64,
    "saves": pl.Float64, "bonus": pl.Float64, "bps": pl.Float64,
    "yellow": pl.Float64, "red": pl.Float64, "own_goals": pl.Float64,
    "pen_missed": pl.Float64, "pen_saved": pl.Float64,
    "xg": pl.Float64, "xa": pl.Float64, "xgc": pl.Float64, "dc": pl.Float64,
    "price": pl.Float64,
    # FPL's own pre-deadline expected points for *this* gw (baseline; null if unknown)
    "fpl_ep": pl.Float64,
    # snapshot captured after this gw — information available before gw + 1
    "snap_status": pl.Utf8, "snap_chance_next": pl.Float64, "snap_ep_next": pl.Float64,
    "snap_price": pl.Float64, "snap_selected": pl.Float64,
    "snap_transfers_in": pl.Float64, "snap_transfers_out": pl.Float64,
}

FIXTURE_STATS = {
    # canonical suffix -> raw column suffix (home_/away_ prefixed in source)
    "goals": "score", "xg": "expected_goals_xg", "npxg": "non_penalty_xg",
    "xgot": "xg_on_target_xgot", "xg_sp": "xg_set_play", "shots": "total_shots",
    "sot": "shots_on_target", "big_chances": "big_chances",
    "box_touches": "touches_in_opposition_box", "possession": "possession",
    "keeper_saves": "keeper_saves", "elo": "team_elo",
}


def seasons_available() -> list[str]:
    return sorted(p.name for p in DATA_DIR.iterdir() if p.is_dir() and p.name[:4].isdigit())


def _gw_dirs(season: str) -> list[tuple[int, Path]]:
    base = DATA_DIR / season / "By Gameweek"
    if not base.exists():
        return []
    dirs = [(int(p.name[2:]), p) for p in base.iterdir() if p.is_dir() and p.name.startswith("GW")]
    return sorted(dirs)


def _read(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, infer_schema_length=0, encoding="utf8-lossy")


def _num(col: str) -> pl.Expr:
    return pl.col(col).cast(pl.Float64, strict=False)


def _conform(df: pl.DataFrame) -> pl.DataFrame:
    exprs = []
    for name, dtype in PLAYER_GW_SCHEMA.items():
        if name in df.columns:
            exprs.append(pl.col(name).cast(dtype, strict=False))
        else:
            exprs.append(pl.lit(None, dtype=dtype).alias(name))
    return df.select(exprs)


# ── player_gw ────────────────────────────────────────────────────────────────

def _player_gw_legacy(season: str) -> pl.DataFrame:
    root = DATA_DIR / season
    teams = pl.read_csv(root / "teams" / "teams.csv").select(
        pl.col("name").alias("team_name"), pl.col("code").cast(pl.Int64).alias("team"))
    players = pl.read_csv(root / "players" / "players.csv").select(
        pl.col("player_id").cast(pl.Int64).alias("element"),
        pl.col("player_code").cast(pl.Int64).alias("code"),
        pl.col("web_name").alias("name"))
    raw = _read(root / "gws" / "merged_gw.csv").filter(pl.col("position") != "AM")
    per_fixture = raw.select(
        pl.col("element").cast(pl.Int64), pl.col("GW").cast(pl.Int64).alias("gw"),
        pl.col("position").replace(POS_MAP).alias("pos"), pl.col("team").alias("team_name"),
        _num("total_points").alias("points"), _num("minutes"), _num("starts"),
        _num("goals_scored").alias("goals"), _num("assists"), _num("clean_sheets").alias("cs"),
        _num("goals_conceded").alias("gc"), _num("saves"), _num("bonus"), _num("bps"),
        _num("yellow_cards").alias("yellow"), _num("red_cards").alias("red"),
        _num("own_goals"), _num("penalties_missed").alias("pen_missed"),
        _num("penalties_saved").alias("pen_saved"),
        _num("expected_goals").alias("xg"), _num("expected_assists").alias("xa"),
        _num("expected_goals_conceded").alias("xgc"),
        (_num("value") / 10).alias("price"), _num("xP").alias("fpl_ep"),
        _num("selected").alias("snap_selected"),
        _num("transfers_in").alias("snap_transfers_in"),
        _num("transfers_out").alias("snap_transfers_out"),
    )
    summed = ["points", "minutes", "starts", "goals", "assists", "cs", "gc", "saves", "bonus",
              "bps", "yellow", "red", "own_goals", "pen_missed", "pen_saved", "xg", "xa", "xgc"]
    agg = per_fixture.group_by("element", "gw").agg(
        pl.col("pos").first(), pl.col("team_name").last(),
        *[pl.col(c).sum() for c in summed],
        # xP is reported per fixture row but already covers the whole gameweek
        pl.col("fpl_ep").first(), pl.col("price").last(), pl.col("snap_selected").last(),
        pl.col("snap_transfers_in").last(), pl.col("snap_transfers_out").last(),
    )
    out = (agg.join(teams, on="team_name", how="left")
              .join(players, on="element", how="left")
              .with_columns(pl.lit(season).alias("season"), pl.col("price").alias("snap_price")))
    return _conform(out)


def _player_gw_modern(season: str) -> pl.DataFrame:
    frames = []
    for gw, folder in _gw_dirs(season):
        pgs_path = folder / "player_gameweek_stats.csv"
        ply_path = folder / "players.csv"
        if not pgs_path.exists() or not ply_path.exists():
            continue
        pgs = _read(pgs_path)
        if pgs.height == 0:
            continue
        ply = _read(ply_path).select(
            pl.col("player_id").cast(pl.Int64).alias("element"),
            pl.col("player_code").cast(pl.Int64).alias("code"),
            pl.col("team_code").cast(pl.Float64).cast(pl.Int64).alias("team"),
            pl.col("position").replace(POS_MAP).alias("pos"),
        ).unique("element")
        frame = pgs.select(
            pl.col("id").cast(pl.Int64).alias("element"), pl.col("web_name").alias("name"),
            _num("total_points").alias("points"), _num("minutes"), _num("starts"),
            _num("goals_scored").alias("goals"), _num("assists"), _num("clean_sheets").alias("cs"),
            _num("goals_conceded").alias("gc"), _num("saves"), _num("bonus"), _num("bps"),
            _num("yellow_cards").alias("yellow"), _num("red_cards").alias("red"),
            _num("own_goals"), _num("penalties_missed").alias("pen_missed"),
            _num("penalties_saved").alias("pen_saved"),
            _num("expected_goals").alias("xg"), _num("expected_assists").alias("xa"),
            _num("expected_goals_conceded").alias("xgc"),
            _num("defensive_contribution").alias("dc"),
            pl.col("status").alias("snap_status"),
            _num("chance_of_playing_next_round").alias("snap_chance_next"),
            _num("ep_next").alias("snap_ep_next"), _num("now_cost").alias("snap_price"),
            _num("selected_by_percent").alias("snap_selected"),
            _num("transfers_in_event").alias("snap_transfers_in"),
            _num("transfers_out_event").alias("snap_transfers_out"),
        ).join(ply, on="element", how="left").with_columns(
            pl.lit(season).alias("season"), pl.lit(gw).cast(pl.Int64).alias("gw"))
        frames.append(frame)
    if not frames:
        return _conform(pl.DataFrame())
    out = pl.concat(frames, how="diagonal_relaxed").filter(pl.col("pos").is_in(list(set(POS_MAP.values()))))
    # Pre-deadline price and FPL ep for gw t come from the snapshot after gw t-1.
    out = out.sort("code", "gw").with_columns(
        pl.col("snap_ep_next").shift(1).over("code").alias("fpl_ep"),
        pl.col("snap_price").shift(1).over("code").fill_null(pl.col("snap_price")).alias("price"),
    )
    return _conform(out)


@lru_cache(maxsize=8)
def load_player_gw(season: str) -> pl.DataFrame:
    root = DATA_DIR / season
    df = _player_gw_legacy(season) if (root / "gws" / "merged_gw.csv").exists() and not _gw_dirs(season) \
        else _player_gw_modern(season)
    return df.filter(pl.col("code").is_not_null()).unique(["season", "gw", "code"], keep="last") \
             .sort("gw", "code")


# ── fixtures ─────────────────────────────────────────────────────────────────

def _fixture_frame(raw: pl.DataFrame, season: str, gw_hint: int | None) -> pl.DataFrame:
    if "tournament" in raw.columns:
        raw = raw.filter(pl.col("tournament").is_in(list(PL_TOURNAMENTS)))
    cols = [
        pl.lit(season).alias("season"),
        (_num("gameweek").cast(pl.Int64) if "gameweek" in raw.columns else pl.lit(gw_hint)).alias("gw"),
        pl.col("match_id"), pl.col("kickoff_time").alias("kickoff"),
        _num("home_team").cast(pl.Int64).alias("home"), _num("away_team").cast(pl.Int64).alias("away"),
        (pl.col("finished").str.to_lowercase() == "true").alias("finished"),
    ]
    for canon, raw_suffix in FIXTURE_STATS.items():
        for side in ("home", "away"):
            src = f"{side}_{raw_suffix}"
            cols.append((_num(src) if src in raw.columns else pl.lit(None, pl.Float64)).alias(f"{side}_{canon}"))
    return raw.select(cols)


@lru_cache(maxsize=8)
def load_fixtures(season: str) -> pl.DataFrame:
    root = DATA_DIR / season
    frames = []
    if _gw_dirs(season):
        for gw, folder in _gw_dirs(season):
            path = folder / "fixtures.csv"
            if path.exists():
                raw = _read(path)
                if raw.height:
                    frames.append(_fixture_frame(raw, season, gw).with_columns(pl.lit(gw).alias("_src")))
    else:
        for folder in sorted((root / "matches").glob("GW*")):
            path = folder / "matches.csv"
            if path.exists():
                gw = int(folder.name[2:])
                raw = _read(path)
                if raw.height:
                    frames.append(_fixture_frame(raw, season, gw).with_columns(pl.lit(gw).alias("_src")))
    df = pl.concat(frames, how="diagonal_relaxed")
    # A rescheduled match can appear in several folders: keep the latest observation.
    df = df.sort("_src").unique("match_id", keep="last").drop("_src")
    df = df.filter(pl.col("home").is_not_null() & pl.col("away").is_not_null())
    df = df.with_columns(pl.when(pl.col("finished")).then(pl.lit("match_stats"))
                           .otherwise(pl.lit(None, pl.Utf8)).alias("result_source"))
    return _repair_from_players(df, load_player_gw(season)).sort("gw", "kickoff")


def _repair_from_players(fx: pl.DataFrame, players: pl.DataFrame) -> pl.DataFrame:
    """Fill results the match scraper missed using FPL player data.

    Only for gameweeks with player stats and only where both teams played exactly
    once that week, so per-team sums are exactly one match. Goals are exact
    (player goals + opponent own goals); xG is FPL's player xG sum (r=0.993 with
    match xG on 2025-26). Penalty attempts are not in the player table, so npxG
    subtracts the measured average penalty xG per team-match (0.11).
    """
    played_gws = set(players["gw"].unique().to_list())
    team_gw = players.group_by("gw", "team").agg(
        pl.col("goals").sum().alias("g"), pl.col("own_goals").sum().alias("og"),
        pl.col("xg").sum().alias("xg"), pl.col("minutes").sum().alias("mins"))
    counts = pl.concat([fx.select("gw", pl.col("home").alias("team")),
                        fx.select("gw", pl.col("away").alias("team"))]).group_by("gw", "team").len()
    single = counts.filter(pl.col("len") == 1).select("gw", "team")
    need = fx.filter(~pl.col("finished") & pl.col("gw").is_in(list(played_gws)))
    if need.height == 0:
        return fx
    h = team_gw.join(single, on=["gw", "team"]).rename({"team": "home", "g": "hg", "og": "hog", "xg": "hxg", "mins": "hmins"})
    a = team_gw.join(single, on=["gw", "team"]).rename({"team": "away", "g": "ag", "og": "aog", "xg": "axg", "mins": "amins"})
    fixed = (need.join(h, on=["gw", "home"]).join(a, on=["gw", "away"])
                 .filter((pl.col("hmins") > 0) & (pl.col("amins") > 0))
                 .with_columns(
                     (pl.col("hg") + pl.col("aog")).alias("home_goals"),
                     (pl.col("ag") + pl.col("hog")).alias("away_goals"),
                     pl.col("hxg").alias("home_xg"), pl.col("axg").alias("away_xg"),
                     (pl.col("hxg") - PEN_XG_PER_MATCH).clip(0).alias("home_npxg"),
                     (pl.col("axg") - PEN_XG_PER_MATCH).clip(0).alias("away_npxg"),
                     pl.lit(True).alias("finished"), pl.lit("player_sum").alias("result_source"))
                 .select(fx.columns))
    return pl.concat([fx.filter(~pl.col("match_id").is_in(fixed["match_id"])), fixed], how="vertical_relaxed")


def team_fixture_counts(season: str) -> pl.DataFrame:
    """(season, gw, team, n_fixtures) for every scheduled PL fixture (finished or not)."""
    fx = load_fixtures(season)
    long = pl.concat([fx.select("season", "gw", pl.col("home").alias("team")),
                      fx.select("season", "gw", pl.col("away").alias("team"))])
    return long.group_by("season", "gw", "team").agg(pl.len().cast(pl.Int64).alias("n_fixtures"))


def load_all(seasons: list[str] | None = None) -> tuple[pl.DataFrame, pl.DataFrame]:
    seasons = seasons or seasons_available()
    players = pl.concat([load_player_gw(s) for s in seasons], how="vertical_relaxed")
    fixtures = pl.concat([load_fixtures(s) for s in seasons], how="diagonal_relaxed")
    return players, fixtures
