import sys
import unittest
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fplmodel import backtest as bt  # noqa: E402
from fplmodel import data  # noqa: E402


def _players():
    rows = []
    for season in ("2024-2025", "2025-2026"):
        for gw in range(1, 6):
            for code, team in ((1, 10), (2, 20)):
                rows.append({"season": season, "gw": gw, "element": code, "code": code, "name": f"p{code}",
                             "pos": "MID", "team": team, "points": float(gw * code), "minutes": 90.0,
                             "fpl_ep": 1.0, "snap_status": "a", "snap_chance_next": 100.0,
                             "snap_ep_next": float(gw)})
    df = pl.DataFrame(rows)
    return df.with_columns(*[pl.lit(None, dtype).alias(c) for c, dtype in data.PLAYER_GW_SCHEMA.items()
                             if c not in df.columns]).select(list(data.PLAYER_GW_SCHEMA))


def _fixtures():
    rows = [{"season": s, "gw": g, "match_id": f"{s}-{g}", "kickoff": "", "home": 10, "away": 20,
             "finished": True, "home_goals": 1.0, "away_goals": 0.0, "home_elo": 1500.0, "away_elo": 1500.0}
            for s in ("2024-2025", "2025-2026") for g in range(1, 6)]
    return pl.DataFrame(rows)


class ContextTests(unittest.TestCase):
    def setUp(self):
        self._orig = data.team_fixture_counts
        data.team_fixture_counts = lambda season: pl.DataFrame(
            {"season": [season] * 2, "gw": [4, 4], "team": [10, 20], "n_fixtures": [1, 2]})

    def tearDown(self):
        data.team_fixture_counts = self._orig

    def test_history_stops_at_cutoff_and_includes_prior_seasons(self):
        ctx = bt.build_context(_players(), _fixtures(), "2025-2026", 4, horizon=2)
        cur = ctx.players.filter(pl.col("season") == "2025-2026")
        self.assertEqual(cur["gw"].max(), 2)
        self.assertEqual(ctx.players.filter(pl.col("season") == "2024-2025").height, 10)

    def test_candidates_carry_no_outcomes_and_use_cutoff_snapshot(self):
        ctx = bt.build_context(_players(), _fixtures(), "2025-2026", 4, horizon=1)
        for col in bt.OUTCOME_COLS:
            self.assertNotIn(col, ctx.candidates.columns)
        self.assertEqual(set(ctx.candidates["snap_ep_next"].to_list()), {3.0})
        self.assertEqual(dict(zip(ctx.candidates["code"], ctx.candidates["n_fixtures"])), {1: 1, 2: 2})

    def test_future_results_are_masked_but_schedule_and_elo_remain(self):
        ctx = bt.build_context(_players(), _fixtures(), "2025-2026", 4, horizon=1)
        fx = ctx.fixtures.filter(pl.col("season") == "2025-2026")
        future = fx.filter(pl.col("gw") > 3)
        self.assertEqual(future.height, 2)
        self.assertTrue(future["home_goals"].is_null().all())
        self.assertFalse(future["finished"].any())
        self.assertFalse(future["home_elo"].is_null().any())
        self.assertFalse(fx.filter(pl.col("gw") <= 3)["home_goals"].is_null().any())

    def test_fpl_ep_hidden_beyond_one_week(self):
        ctx = bt.build_context(_players(), _fixtures(), "2025-2026", 4, horizon=2)
        self.assertTrue(ctx.candidates["fpl_ep"].is_null().all())


class ScoreTests(unittest.TestCase):
    def test_perfect_prediction(self):
        actual = pl.DataFrame({"code": list(range(30)), "points": [float(i) for i in range(30)],
                               "minutes": [90.0] * 30, "pos": ["MID"] * 30})
        s = bt.score_gw(actual.select("code", pl.col("points").alias("pred")), actual)
        self.assertEqual(s["mae"], 0.0)
        self.assertAlmostEqual(s["spearman"], 1.0)
        self.assertEqual(s["top20_precision"], 1.0)
        self.assertEqual(s["captain_pts"], 29.0)
        self.assertEqual(s["top11_pts"], sum(range(19, 30)))

    def test_missing_prediction_counts_as_zero(self):
        actual = pl.DataFrame({"code": [1, 2], "points": [4.0, 2.0], "minutes": [90.0, 0.0], "pos": ["MID"] * 2})
        s = bt.score_gw(pl.DataFrame({"code": [1], "pred": [4.0]}), actual)
        self.assertEqual(s["mae"], 1.0)
        self.assertEqual(s["mae_played"], 0.0)


if __name__ == "__main__":
    unittest.main()
