"""Match model: expected non-penalty xG for each side of every fixture.

Replaces the abstract 0-10 fixture difficulty with quantities FPL decisions
need: each team's expected goals (lambda) and clean-sheet probability
P(CS) = exp(-lambda_opponent_goals).

Members (each predicts a team's npxG in a fixture, from data up to a cutoff):
  strength  time-decayed Poisson regression: attack(team) + defence(opp) + home
            + promoted-side terms. Works from GW1 because every team has history
            or a promoted-team prior.
  window    LightGBM on the recovered original design: rolling 3/8-match and
            same-venue context windows of team and opponent stats, plus Elo.
  elo       Poisson regression on pre-match Elo difference and home advantage.
The ensemble is a non-negative blend learned from rolling-origin predictions.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import polars as pl
from sklearn.linear_model import PoissonRegressor

KNOWN_PROMOTED = {"2024-2025": {40, 13, 20}}  # first season in data has no prior to diff against

WINDOW_STATS = ["npxg_for", "npxg_against", "goals_for", "goals_against", "xgot_for",
                "sot_for", "big_chances_for", "box_touches_for", "possession"]
SHORT, LONG, CTX = 3, 8, 4


# ── team-match table ─────────────────────────────────────────────────────────

def promoted_teams(fixtures: pl.DataFrame) -> dict[str, set[int]]:
    seasons = sorted(fixtures["season"].unique().to_list())
    teams = {s: set(fixtures.filter(pl.col("season") == s)["home"].to_list()) for s in seasons}
    out = {}
    for i, s in enumerate(seasons):
        out[s] = KNOWN_PROMOTED.get(s, set()) if i == 0 else teams[s] - teams[seasons[i - 1]]
    return out


def team_matches(fixtures: pl.DataFrame) -> pl.DataFrame:
    """Two rows per fixture (one per side). Stats are null for unplayed fixtures."""
    promo = promoted_teams(fixtures)
    sides = []
    for side, other, home in (("home", "away", 1.0), ("away", "home", 0.0)):
        sides.append(fixtures.select(
            "season", "gw", "match_id", "kickoff", "finished",
            pl.col(side).alias("team"), pl.col(other).alias("opp"), pl.lit(home).alias("is_home"),
            pl.col(f"{side}_npxg").alias("npxg_for"), pl.col(f"{other}_npxg").alias("npxg_against"),
            pl.col(f"{side}_goals").alias("goals_for"), pl.col(f"{other}_goals").alias("goals_against"),
            pl.col(f"{side}_xgot").alias("xgot_for"), pl.col(f"{side}_sot").alias("sot_for"),
            pl.col(f"{side}_big_chances").alias("big_chances_for"),
            pl.col(f"{side}_box_touches").alias("box_touches_for"),
            pl.col(f"{side}_possession").alias("possession"),
            pl.col(f"{side}_elo").alias("elo"), pl.col(f"{other}_elo").alias("opp_elo"),
        ))
    tm = pl.concat(sides).with_columns(
        pl.col("kickoff").str.replace(" ", "T").str.slice(0, 16).str.to_datetime("%Y-%m-%dT%H:%M", strict=False).alias("ts"))
    promo_rows = pl.DataFrame([{"season": s, "team": t} for s, ts in promo.items() for t in ts],
                              schema={"season": pl.Utf8, "team": pl.Int64})
    flag = promo_rows.with_columns(pl.lit(1.0).alias("promoted"))
    tm = (tm.join(flag, on=["season", "team"], how="left")
            .join(flag.rename({"team": "opp", "promoted": "opp_promoted"}), on=["season", "opp"], how="left")
            .with_columns(pl.col("promoted").fill_null(0.0), pl.col("opp_promoted").fill_null(0.0)))
    return tm.sort("ts", "match_id", "is_home")


def _played(tm: pl.DataFrame) -> pl.DataFrame:
    return tm.filter(pl.col("finished") & pl.col("npxg_for").is_not_null())


# ── members ──────────────────────────────────────────────────────────────────

class StrengthModel:
    name = "strength"

    def __init__(self, half_life_days: float = 240.0, alpha: float = 2e-2):
        self.half_life_days, self.alpha = half_life_days, alpha

    def _design(self, df: pl.DataFrame) -> np.ndarray:
        X = np.zeros((df.height, 2 * len(self.teams) + 3))
        idx = {t: i for i, t in enumerate(self.teams)}
        for r, (t, o) in enumerate(zip(df["team"].to_list(), df["opp"].to_list())):
            if t in idx:
                X[r, idx[t]] = 1.0
            if o in idx:
                X[r, len(self.teams) + idx[o]] = 1.0
        X[:, -3] = df["is_home"].to_numpy()
        X[:, -2] = df["promoted"].to_numpy()
        X[:, -1] = df["opp_promoted"].to_numpy()
        return X

    def fit(self, hist: pl.DataFrame) -> "StrengthModel":
        played = _played(hist)
        self.teams = sorted(set(played["team"].to_list()))
        ref = played["ts"].max()
        age = (ref - played["ts"]).dt.total_seconds().to_numpy() / 86400.0
        w = 0.5 ** (age / self.half_life_days)
        self.model = PoissonRegressor(alpha=self.alpha, max_iter=1000)
        self.model.fit(self._design(played), played["npxg_for"].to_numpy(), sample_weight=w)
        return self

    def predict(self, rows: pl.DataFrame) -> np.ndarray:
        return self.model.predict(self._design(rows))


class EloModel:
    name = "elo"

    def _X(self, df):
        return np.column_stack([(df["elo"] - df["opp_elo"]).fill_null(0).to_numpy() / 100.0,
                                df["is_home"].to_numpy()])

    def fit(self, hist):
        played = _played(hist).filter(pl.col("elo").is_not_null() & pl.col("opp_elo").is_not_null())
        self.model = PoissonRegressor(alpha=1e-4, max_iter=1000).fit(self._X(played), played["npxg_for"].to_numpy())
        return self

    def predict(self, rows):
        return self.model.predict(self._X(rows))


def window_features(tm: pl.DataFrame) -> pl.DataFrame:
    """Rolling features from each team's *prior* played matches, attached to every row.

    Unplayed rows get the team's latest values, which is exactly what a forecast
    made at the cutoff would know.
    """
    base = tm.with_row_index("_row")
    played = _played(base)
    feats = []
    for key, prefix in (("team", "t"), ("opp", "o")):
        p = played.select("_row", "ts", pl.col(key).alias("k"), "is_home", *WINDOW_STATS) if key == "team" else \
            played.select("_row", "ts", pl.col("team").alias("k"), "is_home", *WINDOW_STATS)
        p = p.sort("ts")
        exprs = []
        for n, tag in ((SHORT, "s"), (LONG, "l")):
            exprs += [pl.col(s).rolling_mean(n, min_samples=1).over("k").alias(f"{prefix}_{s}_{tag}") for s in WINDOW_STATS]
        roll = p.with_columns(exprs)
        ctx = p.with_columns([pl.col(s).rolling_mean(CTX, min_samples=1).over("k", "is_home").alias(f"{prefix}_{s}_c")
                              for s in WINDOW_STATS])
        roll_cols = [c for c in roll.columns if c.startswith(f"{prefix}_")]
        ctx_cols = [c for c in ctx.columns if c.endswith("_c")]
        # as-of join: for each row, latest stats strictly before its kickoff
        left = base.select("_row", "ts", pl.col(key).alias("k"), "is_home").sort("ts")
        r = left.join_asof(roll.select("ts", "k", *roll_cols).sort("ts"), on="ts", by="k",
                           strategy="backward", allow_exact_matches=False)
        # context window: same venue as this row for the team; opposite venue for the opponent
        venue = pl.col("is_home") if key == "team" else (1.0 - pl.col("is_home"))
        c = left.with_columns(venue.alias("venue")).join_asof(
            ctx.select("ts", "k", pl.col("is_home").alias("venue"), *ctx_cols).sort("ts"),
            on="ts", by=["k", "venue"], strategy="backward", allow_exact_matches=False)
        feats.append(r.select("_row", *roll_cols).join(c.select("_row", *ctx_cols), on="_row"))
    out = base
    for f in feats:
        out = out.join(f, on="_row", how="left")
    return out.drop("_row").sort("ts", "match_id", "is_home")


class WindowModel:
    name = "window"

    def fit(self, hist_feats: pl.DataFrame):
        import lightgbm as lgb
        played = _played(hist_feats)
        self.cols = [c for c in played.columns if c[:2] in ("t_", "o_")] + \
                    ["is_home", "promoted", "opp_promoted", "elo", "opp_elo"]
        self.model = lgb.LGBMRegressor(objective="poisson", n_estimators=300, learning_rate=0.03,
                                       num_leaves=8, min_child_samples=40, subsample=0.8,
                                       subsample_freq=1, colsample_bytree=0.7, reg_lambda=1.0,
                                       verbose=-1, random_state=0)
        self.model.fit(played.select(self.cols).to_numpy(), played["npxg_for"].to_numpy())
        return self

    def predict(self, rows):
        return self.model.predict(rows.select(self.cols).to_numpy())


MEMBERS = ("strength", "window", "elo")


def fit_predict(tm_feats: pl.DataFrame, train_mask: pl.Expr, target_mask: pl.Expr) -> pl.DataFrame:
    """Fit all members on rows matching train_mask; predict rows matching target_mask."""
    hist = tm_feats.filter(train_mask)
    rows = tm_feats.filter(target_mask)
    preds = {
        "strength": StrengthModel().fit(hist).predict(rows),
        "window": WindowModel().fit(hist).predict(rows),
        "elo": EloModel().fit(hist).predict(rows),
    }
    played = _played(hist)
    goal_ratio = float(played["goals_for"].sum() / max(played["npxg_for"].sum(), 1e-9))
    return rows.select("season", "gw", "match_id", "team", "opp", "is_home", "npxg_for", "goals_for",
                       "goals_against", "finished").with_columns(
        *[pl.Series(f"pred_{k}", v) for k, v in preds.items()],
        pl.lit(goal_ratio).alias("goal_ratio"))


def blend(preds: pl.DataFrame, weights: dict[str, float]) -> pl.DataFrame:
    lam = sum(pl.col(f"pred_{k}") * w for k, w in weights.items())
    out = preds.with_columns(lam.alias("lam_npxg"))
    out = out.with_columns((pl.col("lam_npxg") * pl.col("goal_ratio")).alias("lam_goals"))
    opp = out.select("match_id", pl.col("team").alias("opp"), pl.col("lam_goals").alias("lam_goals_against"))
    return out.join(opp, on=["match_id", "opp"], how="left").with_columns(
        (-pl.col("lam_goals_against")).exp().alias("p_cs"))


def fit_blend_weights(oof: pl.DataFrame) -> dict[str, float]:
    from scipy.optimize import nnls
    d = _played(oof) if "finished" in oof.columns else oof
    A = d.select([f"pred_{k}" for k in MEMBERS]).to_numpy()
    w, _ = nnls(A, d["npxg_for"].to_numpy())
    w = w / w.sum() if w.sum() > 0 else np.full(len(MEMBERS), 1 / len(MEMBERS))
    return dict(zip(MEMBERS, map(float, w)))


# ── backtest ─────────────────────────────────────────────────────────────────

def backtest(fixtures: pl.DataFrame, targets: list[tuple[str, int]], horizon: int = 1) -> pl.DataFrame:
    """Out-of-fold member predictions for every team-match in the target gameweeks."""
    from .backtest import _mask_results
    out = []
    for season, gw in targets:
        cutoff = gw - horizon
        if cutoff < 0:
            continue
        masked = _mask_results(fixtures, season, cutoff)
        feats = window_features(team_matches(masked))
        before = (pl.col("season") < season) | ((pl.col("season") == season) & (pl.col("gw") <= cutoff))
        target = (pl.col("season") == season) & (pl.col("gw") == gw)
        preds = fit_predict(feats, before, target)
        truth = team_matches(fixtures).filter(target).select(
            "match_id", "team", pl.col("npxg_for").alias("y_npxg"), pl.col("goals_for").alias("y_goals"),
            pl.col("goals_against").alias("y_ga"), pl.col("finished").alias("y_finished"))
        out.append(preds.drop("npxg_for", "goals_for", "goals_against", "finished")
                   .join(truth, on=["match_id", "team"]).with_columns(pl.lit(horizon).alias("horizon")))
    return pl.concat(out).filter(pl.col("y_finished"))


def evaluate(oof: pl.DataFrame, weights: dict[str, float]) -> dict:
    b = blend(oof.rename({"y_npxg": "npxg_for"}), weights)
    y, lam = b["npxg_for"].to_numpy(), b["lam_npxg"].to_numpy()
    goals, lam_g = b["y_goals"].to_numpy(), b["lam_goals"].to_numpy()
    cs = (b["y_ga"].to_numpy() == 0).astype(float)
    p = np.clip(b["p_cs"].to_numpy(), 1e-6, 1 - 1e-6)
    dev = 2 * np.mean(np.where(goals > 0, goals * np.log(np.maximum(goals, 1e-9) / lam_g), 0) - (goals - lam_g))
    return {"rows": b.height, "npxg_mae": float(np.mean(np.abs(y - lam))),
            "npxg_corr": float(np.corrcoef(y, lam)[0, 1]),
            "goals_poisson_dev": float(dev),
            "cs_brier": float(np.mean((p - cs) ** 2)),
            "cs_logloss": float(-np.mean(cs * np.log(p) + (1 - cs) * np.log(1 - p))),
            "cs_rate": float(cs.mean()), "cs_pred": float(p.mean())}


# ── production ───────────────────────────────────────────────────────────────

# Rolling-origin results (28 Oct 2026, h=1, MAE npxG / CS log-loss on 2026-27,
# a season no weights were fitted on): strength 0.566/0.584, window 0.586/0.604,
# elo 0.602/0.625, venue-mean null 0.613. A 2025-26-fitted blend leaned on Elo
# and generalised worse (0.574/0.599), and strength/window mixes changed MAE by
# <0.001, so production uses the strength model alone; other members stay for
# monitoring. Half-life 240 d and alpha 0.02 were best on both seasons.
PRODUCTION_WEIGHTS = {"strength": 1.0}
MODEL_VERSION = "match-strength-v1"


def forecast(fixtures: pl.DataFrame, season: str, gws: list[int]) -> pl.DataFrame:
    """Per team-fixture forecasts for `gws` in `season`, fitted on every finished match.

    Returns season, gw, match_id, kickoff, team, opp, is_home, lam_npxg, lam_goals,
    lam_goals_against, p_cs.
    """
    tm = team_matches(fixtures)
    target = (pl.col("season") == season) & pl.col("gw").is_in(gws)
    model = StrengthModel().fit(tm)
    rows = tm.filter(target)
    played = _played(tm)
    goal_ratio = float(played["goals_for"].sum() / played["npxg_for"].sum())
    preds = rows.select("season", "gw", "match_id", "kickoff", "team", "opp", "is_home").with_columns(
        pl.Series("pred_strength", model.predict(rows)), pl.lit(goal_ratio).alias("goal_ratio"))
    return blend(preds, PRODUCTION_WEIGHTS).select(
        "season", "gw", "match_id", "kickoff", "team", "opp", "is_home",
        "lam_npxg", "lam_goals", "lam_goals_against", "p_cs")
