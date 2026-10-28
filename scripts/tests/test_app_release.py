import csv
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_app_release import source_cutoff, validate_outputs, build_release, player_codes, recorded_snapshot


class ReleaseTests(unittest.TestCase):
    def test_export_failure_keeps_last_manifest_and_bundled_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / 'source'; output = base / 'output'; bundle = base / 'bundle'
            source.mkdir(); output.mkdir(); bundle.mkdir()
            (source / 'gameweek_summaries.csv').write_text('id,finished\n1,True\n')
            folder = source / 'By Gameweek' / 'GW1'; folder.mkdir(parents=True)
            for name in ['players.csv', 'matches.csv', 'player_gameweek_stats.csv', 'playermatchstats.csv']:
                (folder / name).write_text('id\n1\n')
            (output / 'manifest.json').write_text('previous verified release')
            (bundle / 'formData.json').write_text('previous bundled data')
            def fail():
                raise RuntimeError('partial export failure')
            with patch('build_app_release.importlib.import_module', return_value=SimpleNamespace(main=fail)):
                with self.assertRaisesRegex(RuntimeError, 'partial'):
                    build_release(source, '2026-2027', 1, output, 'revision', bundle)
            self.assertEqual((output / 'manifest.json').read_text(), 'previous verified release')
            self.assertEqual((bundle / 'formData.json').read_text(), 'previous bundled data')
            self.assertFalse((output / 'releases').exists())

    def test_cutoff_requires_contiguous_finished_source_coverage(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            (base / 'gameweek_summaries.csv').write_text('id,finished\n1,True\n2,False\n3,True\n')
            for gw in [1, 3]:
                folder = base / 'By Gameweek' / f'GW{gw}'
                folder.mkdir(parents=True)
                for name in ['players.csv', 'matches.csv', 'player_gameweek_stats.csv', 'playermatchstats.csv']:
                    (folder / name).write_text('id\n1\n')
            self.assertEqual(source_cutoff(base), 1)
            (base / 'By Gameweek' / 'GW1' / 'matches.csv').unlink()
            with self.assertRaises(ValueError):
                source_cutoff(base)

    def test_empty_and_mixed_coverage_releases_cannot_publish(self):
        payloads = {name: {'gameweek': 4} for name in ['formData', 'playerStatsData', 'defconData', 'xgDeltaData']}
        payloads['teamRatingsData'] = {'ratings': {'ABC': {}}}
        payloads['fixtureData'] = {'planningGws': [5, 6]}
        with self.assertRaisesRegex(ValueError, 'empty'):
            validate_outputs(payloads, 4)
        payloads['playerStatsData'].update({window: {'1': {}} for window in ['season', 'recent', 'formRecent']})
        validate_outputs(payloads, 4)
        payloads['fixtureData']['planningGws'] = [39]
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            validate_outputs(payloads, 4)

    def test_player_codes_survive_a_week_that_omits_a_player(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            weeks = {1: '10,1\n20,2\n', 2: '10,1\n10,1\n', 3: '10,1\n30,3\n'}
            for gw, rows in weeks.items():
                folder = base / 'By Gameweek' / f'GW{gw}'
                folder.mkdir(parents=True)
                (folder / 'players.csv').write_text('player_code,player_id\n' + rows)
            self.assertEqual(player_codes(base, 3), {'1': 10, '2': 20, '3': 30})
            self.assertEqual(player_codes(base, 2), {'1': 10, '2': 20})
            (base / 'By Gameweek' / 'GW3' / 'players.csv').write_text('player_code,player_id\n11,1\n')
            with self.assertRaisesRegex(ValueError, 'identity'):
                player_codes(base, 3)

    def test_placeholder_snapshot_before_cutoff_deadline_is_ignored(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            header = 'id,deadline_time,snapshot_time\n'
            (base / 'gameweek_summaries.csv').write_text(header
                + '1,2026-08-21T17:30:00+00:00,2026-07-23T15:00:00+00:00\n'
                + '2,2026-08-28T17:30:00Z,2026-07-23T15:00:00+00:00\n')
            self.assertIsNone(recorded_snapshot(base, 2))
            (base / 'gameweek_summaries.csv').write_text(header
                + '1,2026-08-21T17:30:00+00:00,2026-08-25T09:00:00+00:00\n'
                + '2,2026-08-28T17:30:00Z,2026-09-01T09:00:00Z\n')
            self.assertEqual(recorded_snapshot(base, 2), '2026-09-01T09:00:00+00:00')
