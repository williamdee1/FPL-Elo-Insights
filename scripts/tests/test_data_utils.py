"""League-only export regressions, using isolated synthetic CSV snapshots."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from data_utils import accumulate_player_stats, compute_player_stat_record, load_gw_matchstats, prem_match_ids, defcon_samples


class LeagueMatchStatsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.gw = self.base / "By Gameweek" / "GW2"
        self.gw.mkdir(parents=True)
        self.write("matches.csv", ["match_id", "tournament"], [
            ["league-a", "prem"], ["league-b", "premier-league"],
            ["cup", "efl-cup"], ["europe", "champions-league"],
        ])
        self.write("playermatchstats.csv", ["player_id", "match_id", "xg", "xa", "total_shots", "minutes_played"], [
            ["1", "league-a", .5, .2, 2, 90],
            ["1", "league-b", .3, .1, 1, 60],
            ["1", "cup", 4, 3, 12, 90],
            ["1", "europe", 5, 4, 15, 90],
            ["2", "cup", 2, 1, 9, 90],
            ["3", "unknown", 9, 9, 20, 90],
        ])

    def write(self, name, columns, rows):
        with (self.gw / name).open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)

    def test_both_supported_league_aliases(self):
        self.assertEqual(prem_match_ids(2, self.base), {"league-a", "league-b"})

    def test_defcon_samples_use_official_gameweek_values_and_count_league_matches(self):
        self.write('playermatchstats.csv', ['player_id', 'match_id', 'minutes_played'], [
            ['1', 'league-a', 90], ['1', 'league-b', 60], ['1', 'cup', 90],
            ['4', 'cup', 90], ['4', 'league-a', 0],
        ])
        self.write('player_gameweek_stats.csv', ['id', 'minutes', 'defensive_contribution'], [
            ['1', 150, 15], ['2', 0, 0], ['3', 90, ''], ['4', 90, 11], ['5', 90, 9],
        ])
        # 1: double gameweek (cup excluded); 2: did not play; 3: missing value;
        # 4/5: one match even when the match-level source misses the league row.
        self.assertEqual(defcon_samples(2, 2, self.base), {'1': [(15.0, 2)], '4': [(11.0, 1)], '5': [(9.0, 1)]})

    def test_stat_record_defcon_is_per_appearance(self):
        self.write("player_gameweek_stats.csv", ["id", "minutes", "defensive_contribution"], [["1", 150, 15]])
        totals = accumulate_player_stats(2, 2, self.base)["1"]
        totals["games"] = 3
        self.assertEqual(compute_player_stat_record(totals)["defcon"], 5.0)

    def test_mixed_week_keeps_both_league_matches_only(self):
        stats = load_gw_matchstats(2, self.base)
        self.assertEqual(set(stats), {"1"})
        self.assertAlmostEqual(stats["1"]["xg"], .8)
        self.assertAlmostEqual(stats["1"]["xa"], .3)
        self.assertEqual(stats["1"]["total_shots"], 3)
        self.assertEqual(stats["1"]["minutes_played"], 150)

    def test_aggregate_does_not_mix_cup_stats_into_fpl_totals(self):
        self.write("player_gameweek_stats.csv", ["id", "minutes", "goals_scored", "event_points"], [["1", 150, 1, 8]])
        stats = accumulate_player_stats(2, 2, self.base)["1"]
        self.assertAlmostEqual(stats["xg"], .8)
        self.assertEqual(stats["total_shots"], 3)
        self.assertEqual(stats["minutes"], 150)
        self.assertEqual(stats["goals_scored"], 1)
        self.assertEqual(stats["event_points"], 8)
        self.assertEqual(stats["points_history"], [8])
        self.assertEqual(stats['matchesPlayed'], 2)
        self.assertEqual(stats['gameweeksObserved'], 1)

    def test_missing_fixture_file_stops_export(self):
        (self.gw / "matches.csv").unlink()
        with self.assertRaises(FileNotFoundError):
            load_gw_matchstats(2, self.base)

    def test_missing_classification_stops_export(self):
        for columns, rows in [(["match_id"], [["league-a"]]),
                              (["match_id", "tournament"], [["league-a", ""]])]:
            with self.subTest(columns=columns):
                self.write("matches.csv", columns, rows)
                with self.assertRaises(ValueError):
                    load_gw_matchstats(2, self.base)

    def test_conflicting_fixture_classification_stops_export(self):
        self.write("matches.csv", ["match_id", "tournament"], [["same", "prem"], ["same", "efl-cup"]])
        with self.assertRaises(ValueError):
            load_gw_matchstats(2, self.base)

    def test_missing_player_match_join_column_stops_export(self):
        self.write("playermatchstats.csv", ["player_id", "xg"], [["1", 9]])
        with self.assertRaises(ValueError):
            load_gw_matchstats(2, self.base)

    def test_cup_only_week_produces_no_league_stats(self):
        self.write("matches.csv", ["match_id", "tournament"], [["cup", "efl-cup"]])
        self.assertEqual(load_gw_matchstats(2, self.base), {})

    def test_missing_optional_matchstats_remains_supported(self):
        (self.gw / "playermatchstats.csv").unlink()
        self.assertEqual(load_gw_matchstats(2, self.base), {})


if __name__ == "__main__":
    unittest.main()
