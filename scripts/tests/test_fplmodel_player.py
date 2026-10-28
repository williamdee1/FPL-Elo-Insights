import math
import sys
import unittest
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fplmodel import data  # noqa: E402
from fplmodel import features as fe  # noqa: E402
from fplmodel import player_model as pm  # noqa: E402


def _players(n_players=40, n_gws=10, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    positions = ["GK", "DEF", "MID", "FWD"]
    for code in range(1, n_players + 1):
        pos = positions[code % 4]
        for gw in range(1, n_gws + 1):
            mins = float(rng.choice([0, 30, 90], p=[0.2, 0.2, 0.6]))
            rows.append({"season": "2025-2026", "gw": gw, "element": code, "code": code, "name": f"p{code}",
                         "pos": pos, "team": code % 4 + 1, "minutes": mins, "starts": float(mins == 90),
                         "points": float(rng.poisson(2 + mins / 45)), "xg": rng.random() * mins / 90,
                         "xa": rng.random() * mins / 180, "goals": 0.0, "assists": 0.0, "saves": 1.0,
                         "bonus": 0.0, "bps": 10.0, "yellow": 0.0, "dc": float(rng.integers(0, 15)),
                         "xgc": 1.0, "price": 5.0, "snap_status": "a" if gw % 3 else "i",
                         "snap_chance_next": None if gw % 3 else 25.0, "snap_selected": 5.0,
                         "snap_transfers_in": 100.0, "snap_transfers_out": 50.0})
    df = pl.DataFrame(rows)
    return df.with_columns(*[pl.lit(None, t).alias(c) for c, t in data.PLAYER_GW_SCHEMA.items()
                             if c not in df.columns]).select(list(data.PLAYER_GW_SCHEMA))


def _match_preds(n_gws=10):
    return pl.DataFrame([{"season": "2025-2026", "gw": gw, "team": t, "lam_npxg": 1.0 + t / 10,
                          "lam_goals": 1.1, "lam_goals_against": 1.2, "p_cs": 0.3, "is_home": float(t % 2)}
                         for gw in range(1, n_gws + 1) for t in range(1, 5)])


class FeatureLeakageTests(unittest.TestCase):
    def test_features_ignore_current_and_future_outcomes(self):
        players, fx = _players(), fe.fixture_features(_match_preds())
        t = 7
        hidden = players.with_columns(*[
            pl.when(pl.col("gw") >= t).then(None).otherwise(pl.col(c)).alias(c)
            for c in ["points", "minutes", "starts", "xg", "xa", "saves", "bonus", "bps", "dc", "yellow", "xgc"]])
        # the snapshot after gw t is also future information
        hidden = hidden.with_columns(*[pl.when(pl.col("gw") >= t).then(None).otherwise(pl.col(c)).alias(c)
                                       for c in ["snap_status", "snap_chance_next", "snap_selected",
                                                 "snap_transfers_in", "snap_transfers_out"]])
        cols = [c for c in fe.FEATURES]
        full = fe.player_features(players, fx).filter(pl.col("gw") == t).sort("code").select(cols)
        blind = fe.player_features(hidden, fx).filter(pl.col("gw") == t).sort("code").select(cols)
        self.assertTrue(full.equals(blind))

    def test_snapshot_comes_from_previous_gameweek_only(self):
        f = fe.player_features(_players(), fe.fixture_features(_match_preds()))
        row = f.filter((pl.col("code") == 1) & (pl.col("gw") == 4)).row(0, named=True)
        self.assertEqual(row["pre_status"], "i")      # snapshot after gw 3
        self.assertEqual(row["chance"], 25.0)
        first = f.filter((pl.col("code") == 1) & (pl.col("gw") == 1)).row(0, named=True)
        self.assertIsNone(first["pre_status"])


class PlayerModelTests(unittest.TestCase):
    def test_blank_gameweek_predicts_zero_and_components_sum(self):
        players = _players(n_gws=8)
        feats = fe.player_features(players, fe.fixture_features(_match_preds(8)))
        model = pm.PlayerModel().fit(feats.filter(pl.col("gw") < 8))
        rows = feats.filter(pl.col("gw") == 8).with_columns(
            pl.when(pl.col("code") == 1).then(0).otherwise(pl.col("n_fix")).alias("n_fix"))
        out = model.components(rows)
        blank = out.filter(pl.col("code") == 1).row(0, named=True)
        self.assertEqual(blank["xp_component"], 0.0)
        self.assertEqual(blank["xp_direct"], 0.0)
        comps = [c for c in out.columns if c.startswith("c_")]
        total = out.select(pl.sum_horizontal(comps)).to_series()
        self.assertTrue(np.allclose(total.to_numpy(), out["xp_component"].to_numpy()))
        self.assertTrue(((out["p60"] <= out["p_app"] + 1e-12)).all())

    def test_poisson_floor_half(self):
        lam = np.array([0.0, 1.0, 3.0])
        expected = [sum((k // 2) * np.exp(-l) * l ** k / math.factorial(k) for k in range(40)) for l in lam]
        self.assertTrue(np.allclose(pm._poisson_floor_half(lam, 39), expected))


if __name__ == "__main__":
    unittest.main()
