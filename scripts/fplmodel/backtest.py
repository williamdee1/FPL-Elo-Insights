"""Rolling-origin backtests for player expected-points models.

For each target (season, gw t) and horizon h, a model is given a `Context`:
history strictly before the information cutoff (gw t-h, i.e. the last completed
gameweek when the prediction would have been made), the full fixture schedule
with results only up to the cutoff, and candidate rows for the target week
containing only pre-deadline fields. Outcome columns are never present in the
candidate rows, so leakage fails loudly instead of inflating scores.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import polars as pl

from . import data

OUTCOME_COLS = ["points", "minutes", "starts", "goals", "assists", "cs", "gc", "saves", "bonus",
                "bps", "yellow", "red", "own_goals", "pen_missed", "pen_saved", "xg", "xa", "xgc", "dc"]
SNAP_COLS = ["snap_status", "snap_chance_next", "snap_ep_next", "snap_price", "snap_selected",
             "snap_transfers_in", "snap_transfers_out"]


@dataclass(frozen=True)
class Context:
    season: str
    target_gw: int
    cutoff_gw: int                 # last completed gw of `season` usable (target_gw - horizon)
    players: pl.DataFrame          # player_gw history: earlier seasons + season gws <= cutoff
    fixtures: pl.DataFrame         # all fixtures; results masked after cutoff in `season`
    candidates: pl.DataFrame       # one row per candidate for target_gw, pre-deadline fields only

    @property
    def horizon(self) -> int:
        return self.target_gw - self.cutoff_gw


Model = Callable[[Context], pl.DataFrame]  # returns columns: code, pred


def _mask_results(fx: pl.DataFrame, season: str, cutoff: int) -> pl.DataFrame:
    stat_cols = [c for c in fx.columns if c.startswith(("home_", "away_")) and not c.endswith("_elo")]
    future = (pl.col("season") == season) & (pl.col("gw") > cutoff)
    return fx.with_columns(
        *[pl.when(future).then(None).otherwise(pl.col(c)).alias(c) for c in stat_cols],
        pl.when(future).then(False).otherwise(pl.col("finished")).alias("finished"),
        # pre-match Elo is published before kickoff, so it stays visible
    )


def build_context(players: pl.DataFrame, fixtures: pl.DataFrame, season: str,
                  target_gw: int, horizon: int = 1) -> Context:
    cutoff = target_gw - horizon
    seasons = sorted(players["season"].unique().to_list())
    earlier = [s for s in seasons if s < season]
    hist = players.filter(pl.col("season").is_in(earlier) |
                          ((pl.col("season") == season) & (pl.col("gw") <= cutoff)))
    target = players.filter((pl.col("season") == season) & (pl.col("gw") == target_gw))
    # Pre-deadline info for the candidate = snapshot after the cutoff gw (if any).
    snap = hist.filter((pl.col("season") == season) & (pl.col("gw") == cutoff)).select("code", *SNAP_COLS)
    counts = data.team_fixture_counts(season).filter(pl.col("gw") == target_gw).select("team", "n_fixtures")
    candidates = (target.drop(OUTCOME_COLS + SNAP_COLS)
                  .with_columns(pl.when(pl.lit(horizon) == 1).then(pl.col("fpl_ep")).otherwise(None).alias("fpl_ep"))
                  .join(snap, on="code", how="left")
                  .join(counts, on="team", how="left")
                  .with_columns(pl.col("n_fixtures").fill_null(0)))
    return Context(season, target_gw, cutoff, hist, _mask_results(fixtures, season, cutoff), candidates)


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 3:
        return float("nan")
    ra = pl.Series(a).rank().to_numpy()
    rb = pl.Series(b).rank().to_numpy()
    return float(np.corrcoef(ra, rb)[0, 1])


def score_gw(pred: pl.DataFrame, actual: pl.DataFrame) -> dict:
    """Metrics for one gameweek. `actual` has code, points, minutes, pos."""
    df = actual.join(pred.select("code", "pred"), on="code", how="left").with_columns(
        pl.col("pred").fill_null(0.0))
    y, p = df["points"].to_numpy(), df["pred"].to_numpy()
    played = df["minutes"].to_numpy() > 0
    order = np.argsort(-p, kind="stable")
    top_actual = set(df["code"].to_numpy()[np.argsort(-y, kind="stable")[:20]])
    top_pred = df["code"].to_numpy()[order[:20]]
    return {
        "n": len(df),
        "mae": float(np.mean(np.abs(y - p))),
        "rmse": float(np.sqrt(np.mean((y - p) ** 2))),
        "mae_played": float(np.mean(np.abs(y[played] - p[played]))) if played.any() else float("nan"),
        "spearman": _spearman(p, y),
        "top20_precision": len(top_actual.intersection(top_pred)) / 20,
        "captain_pts": float(y[order[0]]),
        "top11_pts": float(y[order[:11]].sum()),
        "bias": float(np.mean(p - y)),
    }


def run(model: Model, targets: list[tuple[str, int]], horizon: int = 1,
        players: pl.DataFrame | None = None, fixtures: pl.DataFrame | None = None) -> pl.DataFrame:
    if players is None or fixtures is None:
        players, fixtures = data.load_all()
    rows = []
    for season, gw in targets:
        if gw - horizon < 1:
            continue
        ctx = build_context(players, fixtures, season, gw, horizon)
        if ctx.candidates.height == 0:
            continue
        pred = model(ctx)
        actual = players.filter((pl.col("season") == season) & (pl.col("gw") == gw)).select(
            "code", "points", "minutes", "pos")
        rows.append({"season": season, "gw": gw, "horizon": horizon, **score_gw(pred, actual)})
    return pl.DataFrame(rows)


def summarise(results: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """Mean metrics per model (rows) across all scored gameweeks."""
    out = []
    for name, df in results.items():
        if df.height == 0:
            continue
        out.append({"model": name, "gws": df.height,
                    **{m: df[m].mean() for m in ["mae", "rmse", "mae_played", "spearman",
                                                   "top20_precision", "captain_pts", "top11_pts", "bias"]}})
    return pl.DataFrame(out)


def default_targets(season: str, start: int = 2, end: int | None = None) -> list[tuple[str, int]]:
    gws = sorted(data.load_player_gw(season)["gw"].unique().to_list())
    end = end or max(gws)
    return [(season, g) for g in gws if start <= g <= end]
