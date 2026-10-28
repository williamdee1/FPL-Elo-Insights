import sys
import unittest
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fplmodel import match_model as mm  # noqa: E402


def _fixtures(n_rounds=6):
    """Team 1 dominates, team 4 is weak; four teams, round robin each gw."""
    strength = {1: 2.2, 2: 1.3, 3: 1.1, 4: 0.6}
    pairs = [(1, 4), (2, 3), (4, 2), (3, 1), (1, 2), (3, 4)]
    rows = []
    for gw in range(1, n_rounds + 1):
        for i, (h, a) in enumerate(pairs[(gw - 1) % 3 * 2:(gw - 1) % 3 * 2 + 2]):
            day = f"2025-0{8 + gw // 5}-{10 + (gw % 5) * 3:02d}T15:00:00"
            rows.append({"season": "2025-2026", "gw": gw, "match_id": f"m{gw}{i}", "kickoff": day,
                         "home": h, "away": a, "finished": gw < n_rounds,
                         "home_npxg": strength[h] / strength[a] if gw < n_rounds else None,
                         "away_npxg": strength[a] / strength[h] if gw < n_rounds else None,
                         "home_goals": 1.0 if gw < n_rounds else None, "away_goals": 0.0 if gw < n_rounds else None,
                         "home_elo": 1500.0, "away_elo": 1500.0})
    df = pl.DataFrame(rows)
    for side in ("home", "away"):
        for stat in ("xgot", "sot", "big_chances", "box_touches", "possession"):
            df = df.with_columns(pl.lit(1.0).alias(f"{side}_{stat}"))
    return df


class MatchModelTests(unittest.TestCase):
    def test_two_rows_per_fixture_with_mirrored_stats(self):
        tm = mm.team_matches(_fixtures())
        self.assertEqual(tm.height, 2 * _fixtures().height)
        row = tm.filter((pl.col("match_id") == "m10") & (pl.col("is_home") == 1.0)).row(0, named=True)
        mirror = tm.filter((pl.col("match_id") == "m10") & (pl.col("is_home") == 0.0)).row(0, named=True)
        self.assertEqual(row["npxg_for"], mirror["npxg_against"])

    def test_strength_model_ranks_teams(self):
        tm = mm.team_matches(_fixtures())
        model = mm.StrengthModel(alpha=1e-3).fit(tm)
        probe = pl.DataFrame({"team": [1, 4], "opp": [3, 3], "is_home": [1.0, 1.0],
                              "promoted": [0.0, 0.0], "opp_promoted": [0.0, 0.0]})
        strong, weak = model.predict(probe)
        self.assertGreater(strong, weak)

    def test_window_features_use_only_prior_matches(self):
        fx = _fixtures()
        feats = mm.window_features(mm.team_matches(fx))
        first = feats.filter(pl.col("gw") == 1)
        self.assertTrue(first["t_npxg_for_s"].is_null().all())
        # changing a later result must not change earlier features
        bumped = fx.with_columns(pl.when(pl.col("gw") == 4).then(99.0).otherwise(pl.col("home_npxg")).alias("home_npxg"))
        a = feats.filter(pl.col("gw") <= 4).select("match_id", "team", "t_npxg_for_l")
        b = mm.window_features(mm.team_matches(bumped)).filter(pl.col("gw") <= 4).select("match_id", "team", "t_npxg_for_l")
        self.assertTrue(a.sort("match_id", "team").equals(b.sort("match_id", "team")))

    def test_forecast_gives_clean_sheet_probabilities(self):
        out = mm.forecast(_fixtures(), "2025-2026", [6])
        self.assertEqual(out.height, 4)
        self.assertTrue(((out["p_cs"] > 0) & (out["p_cs"] < 1)).all())
        strong = out.filter(pl.col("team") == 1)
        self.assertLess(strong["lam_goals_against"].item(), strong["lam_goals"].item())

    def test_promoted_teams_detected_from_previous_season(self):
        fx = pl.concat([_fixtures().with_columns(pl.lit("2024-2025").alias("season")),
                        _fixtures().with_columns(pl.when(pl.col("home") == 4).then(9).otherwise(pl.col("home")).alias("home"))])
        promo = mm.promoted_teams(fx)
        self.assertEqual(promo["2025-2026"], {9})


if __name__ == "__main__":
    unittest.main()
