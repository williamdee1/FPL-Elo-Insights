"""Player expected points: minutes model + scoring-rule components + direct learner.

Component model (per fixture, then x fixtures in the gameweek):
  appearance   P(appear) + P(60+)
  goals        E[min]/90 x shrunk xG/90 x (lambda_npxg / team ref) x goal points
  assists      same with xA/90 x 3
  clean sheet  P(60+) x P(CS) x CS points
  conceded     GK/DEF: -P(60+) x E[floor(G_against / 2)], G_against ~ Poisson
  saves        GK: E[min]/90 x saves/90 x (lambda_against / team ref) / 3
  def. contrib P(60+) x P(threshold hit) x 2   (rule from 2025-26)
  bonus/cards  E[min]/90 x per-90 rates
Rates are shrunk toward position means with `SHRINK_MINUTES` of prior weight.
The direct learner is a LightGBM regressor on the same features; the final
prediction is a per-position non-negative blend fitted on out-of-fold results.
"""

from __future__ import annotations

import math

import numpy as np
import polars as pl

from .features import FEATURES

GOAL_PTS = {"GK": 10.0, "DEF": 6.0, "MID": 5.0, "FWD": 4.0}
CS_PTS = {"GK": 4.0, "DEF": 4.0, "MID": 1.0, "FWD": 0.0}
SHRINK_MINUTES = {"xg90_l30": 600.0, "xa90_l30": 600.0, "sv90_l20": 450.0,
                  "bon90_l20": 900.0, "yc90_l30": 900.0}
MINUTE_FEATURES = [f for f in FEATURES if not f.startswith("fx_")]


def _lgb(kind: str, **kw):
    import lightgbm as lgb
    common = dict(n_estimators=250, learning_rate=0.04, num_leaves=15, min_child_samples=60,
                  subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=2.0,
                  verbose=-1, random_state=0)
    common.update(kw)
    return lgb.LGBMClassifier(**common) if kind == "clf" else lgb.LGBMRegressor(**common)


def _X(df: pl.DataFrame, cols: list[str]) -> np.ndarray:
    return df.select([pl.col(c).cast(pl.Float64) for c in cols]).to_numpy()


def _poisson_floor_half(lam: np.ndarray, kmax: int = 15) -> np.ndarray:
    """E[floor(X/2)] for X ~ Poisson(lam), elementwise."""
    out = np.zeros_like(lam, dtype=float)
    pmf = np.exp(-lam)
    for k in range(1, kmax + 1):
        pmf = pmf * lam / k
        out += (k // 2) * pmf
    return out


class PlayerModel:
    def fit(self, train: pl.DataFrame) -> "PlayerModel":
        tr = train.filter((pl.col("n_fix") >= 1) & pl.col("fx_lam_npxg").is_not_null() & pl.col("points").is_not_null())
        single = tr.filter(pl.col("n_fix") == 1)
        self.p_app = _lgb("clf").fit(_X(single, MINUTE_FEATURES), (single["minutes"] > 0).to_numpy())
        self.p_60 = _lgb("clf").fit(_X(single, MINUTE_FEATURES), (single["minutes"] >= 60).to_numpy())
        self.direct = _lgb("reg", objective="regression").fit(_X(tr, FEATURES), tr["points"].to_numpy())
        # position priors for shrinkage, from players with real minutes
        regulars = tr.filter(pl.col("mins_sum_l30") >= 900)
        self.priors = {
            pos: {c: float(regulars.filter(pl.col("pos") == pos)[c].fill_nan(None).drop_nulls().mean() or 0.0)
                  for c in [*SHRINK_MINUTES, "dc_rate_l20"]}
            for pos in GOAL_PTS
        }
        return self

    def _shrunk(self, df: pl.DataFrame, col: str) -> np.ndarray:
        mins = df["mins_sum_l30"].fill_null(0).to_numpy()
        rate = df[col].fill_null(0).to_numpy()
        prior = np.array([self.priors[p][col] for p in df["pos"].to_list()])
        k = SHRINK_MINUTES[col]
        return (rate * mins + prior * k) / (mins + k)

    def components(self, df: pl.DataFrame) -> pl.DataFrame:
        n = df["n_fix"].fill_null(0).to_numpy().astype(float)
        has = n > 0
        nf = np.where(has, n, 1.0)
        p_app = self.p_app.predict_proba(_X(df, MINUTE_FEATURES))[:, 1]
        p60 = np.minimum(self.p_60.predict_proba(_X(df, MINUTE_FEATURES))[:, 1], p_app)
        emin = (p60 * 88 + (p_app - p60) * 28) / 90
        pos = df["pos"].to_list()
        gp = np.array([GOAL_PTS[p] for p in pos]); csp = np.array([CS_PTS[p] for p in pos])
        defensive = np.array([p in ("GK", "DEF") for p in pos])
        gk = np.array([p == "GK" for p in pos])
        lam = df["fx_lam_npxg"].fill_null(0).to_numpy() / nf
        lam_ag = df["fx_lam_against"].fill_null(0).to_numpy() / nf
        cs = df["fx_cs"].fill_null(0).to_numpy() / nf
        ref = df["ref_npxg"].fill_null(1.3).to_numpy()
        ref_ag = df["ref_against"].fill_null(1.3).to_numpy()
        att = np.clip(lam / np.maximum(ref, 0.2), 0.3, 3.0)
        dfn = np.clip(lam_ag / np.maximum(ref_ag, 0.2), 0.3, 3.0)
        dc_rate = df["dc_rate_l20"].to_numpy()
        dc_n = df["dc_n_l20"].fill_null(0).to_numpy()
        dc_prior = np.array([self.priors[p]["dc_rate_l20"] for p in pos])
        dc_rate = (np.nan_to_num(dc_rate) * dc_n + dc_prior * 4) / (dc_n + 4)
        dc_live = np.array([s >= "2025-2026" for s in df["season"].to_list()])
        comp = {
            "c_app": p_app + p60,
            "c_goals": emin * self._shrunk(df, "xg90_l30") * att * gp,
            "c_assists": emin * self._shrunk(df, "xa90_l30") * att * 3.0,
            "c_cs": p60 * cs * csp,
            "c_gc": -np.where(defensive, p60 * _poisson_floor_half(lam_ag), 0.0),
            "c_saves": np.where(gk, emin * self._shrunk(df, "sv90_l20") * dfn / 3.0, 0.0),
            "c_dc": np.where(dc_live & ~gk, p60 * dc_rate * 2.0, 0.0),
            "c_bonus": emin * self._shrunk(df, "bon90_l20"),
            "c_cards": -emin * self._shrunk(df, "yc90_l30"),
        }
        per_fix = sum(comp.values())
        return df.select("code").with_columns(
            pl.Series("p_app", p_app), pl.Series("p60", p60),
            *[pl.Series(k, np.where(has, v * n, 0.0)) for k, v in comp.items()],
            pl.Series("xp_component", np.where(has, per_fix * n, 0.0)),
            pl.Series("xp_direct", np.where(has, self.direct.predict(_X(df, FEATURES)), 0.0)),
        )


def backtest(players: pl.DataFrame, match_oof: pl.DataFrame, targets: list[tuple[str, int]],
             horizon: int = 1, target_fixtures: pl.DataFrame | None = None) -> pl.DataFrame:
    """Out-of-fold component/direct predictions, mirroring production at `horizon`.

    Features are computed once: every feature is shifted, so a row's features
    only use earlier rows (see test_fplmodel_player). For horizon h the
    prediction for gw t reuses the feature row of gw t-h+1 (data through t-h),
    swaps in fixture features for gw t from `target_fixtures` (match forecasts
    made at cutoff t-h) and applies the production availability heuristic.
    """
    from .features import fixture_features, player_features
    from .infer import _availability
    feats = player_features(players, fixture_features(match_oof))
    tfx = fixture_features(target_fixtures if target_fixtures is not None else match_oof)
    fx_cols = [c for c in feats.columns if c.startswith(("fx_", "ref_")) or c == "n_fix"]
    out = []
    for season, gw in targets:
        src = gw - horizon + 1
        if src < 1:
            continue
        train = feats.filter((pl.col("season") < season) | ((pl.col("season") == season) & (pl.col("gw") < src)))
        rows = feats.filter((pl.col("season") == season) & (pl.col("gw") == src))
        if rows.height == 0:
            continue
        if horizon > 1:
            rows = rows.drop(fx_cols).join(tfx.filter((pl.col("season") == season) & (pl.col("gw") == gw))
                                           .drop("season", "gw"), on="team", how="left").with_columns(pl.col("n_fix").fill_null(0))
            avail = [_availability(st, ch, horizon) for st, ch in zip(rows["pre_status"].to_list(), rows["pre_chance"].to_list())]
            rows = rows.with_columns(pl.Series("pre_status", [a[0] for a in avail], dtype=pl.Utf8),
                                     pl.Series("pre_chance", [a[1] for a in avail], dtype=pl.Float64)).with_columns(
                pl.col("pre_status").replace_strict({"a": 0, "d": 1, "i": 2, "s": 3, "u": 4, "n": 5}, default=None)
                  .cast(pl.Float64).alias("status_code"),
                pl.when(pl.col("pre_chance").is_not_null()).then(pl.col("pre_chance"))
                  .when(pl.col("pre_status") == "a").then(100.0).otherwise(None).alias("chance"))
        pred = PlayerModel().fit(train).components(rows)
        actual = players.filter((pl.col("season") == season) & (pl.col("gw") == gw)).select(
            "code", "pos", "points", "minutes", "fpl_ep")
        out.append(pred.with_columns(pl.lit(season).alias("season"), pl.lit(gw).alias("gw"), pl.lit(horizon).alias("horizon"))
                   .join(actual, on="code"))
    return pl.concat(out)


def fit_stack(oof: pl.DataFrame) -> dict[str, tuple[float, float]]:
    """Per-position non-negative weights (component, direct)."""
    from scipy.optimize import nnls
    weights = {}
    for pos in GOAL_PTS:
        d = oof.filter(pl.col("pos") == pos)
        w, _ = nnls(d.select("xp_component", "xp_direct").to_numpy(), d["points"].to_numpy())
        weights[pos] = (float(w[0]), float(w[1]))
    return weights


def apply_stack(df: pl.DataFrame, weights: dict[str, tuple[float, float]]) -> pl.Series:
    wc = df["pos"].replace_strict({p: w[0] for p, w in weights.items()}, return_dtype=pl.Float64)
    wd = df["pos"].replace_strict({p: w[1] for p, w in weights.items()}, return_dtype=pl.Float64)
    return (df["xp_component"] * wc + df["xp_direct"] * wd).alias("xp")
