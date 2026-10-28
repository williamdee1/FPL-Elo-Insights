"""Reference predictors every model must beat in the backtest."""

from __future__ import annotations

import polars as pl

from .backtest import Context

PRIOR_WEIGHT_GWS = 3.0  # prior-season ppg counts as this many current-season gameweeks


def recent_points_per_gw(ctx: Context, n: int = 5) -> pl.DataFrame:
    """code -> recent points per gameweek, shrunk toward last season early on."""
    cur = ctx.players.filter(pl.col("season") == ctx.season)
    recent = (cur.sort("gw").group_by("code").tail(n)
                 .group_by("code").agg(pl.col("points").mean().alias("cur_ppg"), pl.len().alias("cur_n")))
    prev_seasons = [s for s in ctx.players["season"].unique().to_list() if s < ctx.season]
    if prev_seasons:
        prev = (ctx.players.filter(pl.col("season") == max(prev_seasons))
                   .group_by("code").agg(pl.col("points").mean().alias("prev_ppg")))
        recent = recent.join(prev, on="code", how="full", coalesce=True)
    else:
        recent = recent.with_columns(pl.lit(None, pl.Float64).alias("prev_ppg"))
    return recent.with_columns(
        pl.col("cur_n").fill_null(0),
    ).with_columns(
        ((pl.col("cur_ppg").fill_null(0) * pl.col("cur_n")
          + pl.col("prev_ppg").fill_null(0) * pl.when(pl.col("prev_ppg").is_null()).then(0).otherwise(PRIOR_WEIGHT_GWS))
         / (pl.col("cur_n") + pl.when(pl.col("prev_ppg").is_null()).then(0).otherwise(PRIOR_WEIGHT_GWS)))
        .fill_nan(0).alias("ppg")
    ).select("code", "ppg")


def form5(ctx: Context) -> pl.DataFrame:
    ppg = recent_points_per_gw(ctx, 5)
    return (ctx.candidates.select("code", "n_fixtures").join(ppg, on="code", how="left")
            .select("code", (pl.col("ppg").fill_null(0) * pl.col("n_fixtures")).alias("pred")))


def fpl_ep(ctx: Context) -> pl.DataFrame:
    """FPL's own ep_next from the snapshot before the deadline (horizon 1 only)."""
    fallback = form5(ctx).rename({"pred": "fb"})
    return (ctx.candidates.select("code", "fpl_ep").join(fallback, on="code", how="left")
            .select("code", pl.coalesce("fpl_ep", "fb").alias("pred")))
