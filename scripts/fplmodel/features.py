"""Player features, each computed only from the player's earlier gameweek rows.

`player_features(frame, fixture_feats)` takes canonical player_gw rows (history
plus, optionally, candidate rows whose outcome columns are null) and returns one
feature row per input row. Rolling statistics use `shift(1)` within each player
so a row never sees its own outcome. The pre-deadline snapshot (status, chance
of playing, price) is the previous row's `snap_*` when that row is the
immediately preceding gameweek of the same season.
"""

from __future__ import annotations

import polars as pl

DC_THRESHOLD = {"GK": 999, "DEF": 10, "MID": 12, "FWD": 12}  # 2025-26 defensive contribution rule
DC_SEASONS_FROM = "2025-2026"
STATUS_CODES = {"a": 0, "d": 1, "i": 2, "s": 3, "u": 4, "n": 5}


def _roll(expr: pl.Expr, n: int, how: str = "mean") -> pl.Expr:
    prior = expr.shift(1)
    return (prior.rolling_mean(n, min_samples=1) if how == "mean" else prior.rolling_sum(n, min_samples=1)).over("code")


def _per90(num: str, n: int) -> pl.Expr:
    mins = _roll(pl.col("minutes"), n, "sum")
    return pl.when(mins >= 90).then(_roll(pl.col(num), n, "sum") / mins * 90).otherwise(None)


def fixture_features(match_preds: pl.DataFrame) -> pl.DataFrame:
    """(season, gw, team) -> fixture count and summed/averaged match-model outputs.

    `ref_*` is the team's rolling mean of its own pre-match forecasts (last 10
    fixtures). Player rates already reflect their team's usual strength, so the
    component model scales them by lambda / ref rather than by raw lambda.
    """
    refs = match_preds.sort("team", "season", "gw").with_columns(
        pl.col("lam_npxg").rolling_mean(10, min_samples=1).over("team").alias("ref_npxg"),
        pl.col("lam_goals_against").rolling_mean(10, min_samples=1).over("team").alias("ref_against"),
    )
    return refs.group_by("season", "gw", "team").agg(
        pl.len().alias("n_fix"),
        pl.col("lam_npxg").sum().alias("fx_lam_npxg"),
        pl.col("lam_goals").sum().alias("fx_lam_goals"),
        pl.col("lam_goals_against").sum().alias("fx_lam_against"),
        pl.col("p_cs").sum().alias("fx_cs"),
        pl.col("is_home").mean().alias("fx_home"),
        pl.col("ref_npxg").last(), pl.col("ref_against").last(),
    )


def player_features(frame: pl.DataFrame, fixture_feats: pl.DataFrame) -> pl.DataFrame:
    df = frame.sort("code", "season", "gw").with_columns(
        pl.col("minutes").fill_null(0).alias("_m"),
        (pl.col("minutes") > 0).cast(pl.Float64).alias("_app"),
        (pl.col("minutes") >= 60).cast(pl.Float64).alias("_m60"),
        pl.col("pos").replace_strict(DC_THRESHOLD, default=999).alias("_dct"),
    ).with_columns(
        pl.when(pl.col("season") >= DC_SEASONS_FROM)
          .then((pl.col("dc") >= pl.col("_dct")).cast(pl.Float64)).otherwise(None).alias("_dchit"),
        pl.when(pl.col("season") >= DC_SEASONS_FROM).then(pl.col("_m60")).otherwise(None).alias("_m60dc"),
    )
    prev_season = pl.col("season").shift(1).over("code")
    prev_gw = pl.col("gw").shift(1).over("code")
    adjacent = (prev_season == pl.col("season")) & (prev_gw == pl.col("gw") - 1)
    feats = df.with_columns(
        # availability / minutes
        _roll(pl.col("minutes"), 1).alias("mins_l1"),
        _roll(pl.col("minutes"), 3).alias("mins_l3"),
        _roll(pl.col("minutes"), 6).alias("mins_l6"),
        _roll(pl.col("_app"), 6).alias("app_l6"),
        _roll(pl.col("_m60"), 6).alias("m60_l6"),
        _roll(pl.col("starts"), 6).alias("starts_l6"),
        _roll(pl.col("_m60"), 20).alias("m60_l20"),
        # points form
        _roll(pl.col("points"), 3).alias("pts_l3"),
        _roll(pl.col("points"), 6).alias("pts_l6"),
        _roll(pl.col("points"), 20).alias("pts_l20"),
        _roll(pl.col("bps"), 6).alias("bps_l6"),
        # per-90 rates (null until 90 minutes in the window)
        _per90("xg", 10).alias("xg90_l10"), _per90("xa", 10).alias("xa90_l10"),
        _per90("xg", 30).alias("xg90_l30"), _per90("xa", 30).alias("xa90_l30"),
        _per90("goals", 30).alias("g90_l30"), _per90("assists", 30).alias("a90_l30"),
        _per90("saves", 20).alias("sv90_l20"), _per90("bonus", 20).alias("bon90_l20"),
        _per90("yellow", 30).alias("yc90_l30"), _per90("xgc", 10).alias("xgc90_l10"),
        _roll(pl.col("_m"), 30, "sum").alias("mins_sum_l30"),
        # defensive contribution hit rate among 60+ minute appearances
        pl.when(_roll(pl.col("_m60dc"), 20, "sum") > 0)
          .then(_roll(pl.col("_dchit") * pl.col("_m60dc"), 20, "sum") / _roll(pl.col("_m60dc"), 20, "sum"))
          .otherwise(None).alias("dc_rate_l20"),
        _roll(pl.col("_m60dc"), 20, "sum").alias("dc_n_l20"),
        # season-to-date context
        pl.col("gw").rank("ordinal").over("code", "season").cast(pl.Float64).sub(1).alias("rows_this_season"),
        # pre-deadline snapshot from the previous gameweek's file
        pl.when(adjacent).then(pl.col("snap_status").shift(1).over("code")).otherwise(None).alias("pre_status"),
        pl.when(adjacent).then(pl.col("snap_chance_next").shift(1).over("code")).otherwise(None).alias("pre_chance"),
        pl.when(adjacent).then(pl.col("snap_transfers_in").shift(1).over("code")).otherwise(None).alias("pre_tin"),
        pl.when(adjacent).then(pl.col("snap_transfers_out").shift(1).over("code")).otherwise(None).alias("pre_tout"),
        pl.when(adjacent).then(pl.col("snap_selected").shift(1).over("code")).otherwise(None).alias("pre_selected"),
    ).with_columns(
        pl.col("pre_status").replace_strict(STATUS_CODES, default=None).cast(pl.Float64).alias("status_code"),
        pl.when(pl.col("pre_chance").is_not_null()).then(pl.col("pre_chance"))
          .when(pl.col("pre_status") == "a").then(100.0).otherwise(None).alias("chance"),
        pl.col("pos").replace_strict({"GK": 0, "DEF": 1, "MID": 2, "FWD": 3}, default=None).cast(pl.Float64).alias("pos_code"),
    )
    out = feats.join(fixture_feats, on=["season", "gw", "team"], how="left").with_columns(
        pl.col("n_fix").fill_null(0))
    return out.drop("_m", "_app", "_m60", "_dct", "_dchit", "_m60dc")


FEATURES = ["mins_l1", "mins_l3", "mins_l6", "app_l6", "m60_l6", "starts_l6", "m60_l20",
            "pts_l3", "pts_l6", "pts_l20", "bps_l6", "xg90_l10", "xa90_l10", "xg90_l30", "xa90_l30",
            "g90_l30", "a90_l30", "sv90_l20", "bon90_l20", "yc90_l30", "xgc90_l10", "mins_sum_l30",
            "dc_rate_l20", "dc_n_l20", "rows_this_season", "status_code", "chance", "pre_tin",
            "pre_tout", "pre_selected", "pos_code", "price",
            "n_fix", "fx_lam_npxg", "fx_lam_goals", "fx_lam_against", "fx_cs", "fx_home"]
