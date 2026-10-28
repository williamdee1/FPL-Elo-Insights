"""Build a complete immutable insight release in staging; promote the manifest last.

No models are trained here. A missing canonical inference pipeline remains an
explicit prediction-readiness failure rather than invented recommendations.
"""
import argparse
import csv
import hashlib
import importlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

EXPORTS = {
    'formData': 'export_form_data', 'fixtureData': 'export_fixture_data',
    'playerStatsData': 'export_player_stats', 'defconData': 'export_defcon_data',
    'xgDeltaData': 'export_xg_delta_data', 'teamRatingsData': 'export_team_ratings',
}


def source_cutoff(base: Path) -> int:
    with (base / 'gameweek_summaries.csv').open(encoding='utf-8-sig') as stream:
        complete = {int(row['id']) for row in csv.DictReader(stream) if row.get('finished', '').lower() == 'true'}
    cutoff = 0
    for gw in range(1, 39):
        folder = base / 'By Gameweek' / f'GW{gw}'
        if gw not in complete or any(not (folder / filename).is_file() for filename in ['players.csv', 'matches.csv', 'player_gameweek_stats.csv', 'playermatchstats.csv']):
            break
        # A header-only CSV is not evidence of completed performance coverage.
        if any(not next(csv.DictReader((folder / filename).read_text(encoding='utf-8-sig').splitlines()), None)
               for filename in ['players.csv', 'matches.csv', 'player_gameweek_stats.csv', 'playermatchstats.csv']):
            break
        cutoff = gw
    if not cutoff:
        raise ValueError('No contiguous completed gameweeks with required source tables')
    return cutoff


def player_codes(base: Path, cutoff: int) -> dict:
    """player_id -> stable player_code across GW1..cutoff.

    Upstream weekly player lists occasionally omit an active player (Barcola
    is absent from GW6-8 in 2026-27), so one week cannot be the only source.
    A player whose code changes between weeks is an identity conflict.
    """
    codes = {}
    for gw in range(1, cutoff + 1):
        path = base / 'By Gameweek' / f'GW{gw}' / 'players.csv'
        if not path.is_file():
            continue
        with path.open(encoding='utf-8-sig') as stream:
            for row in csv.DictReader(stream):
                code = int(row['player_code'])
                if codes.setdefault(row['player_id'], code) != code:
                    raise ValueError(f"Player {row['player_id']} changes identity in GW{gw}")
    return codes


def recorded_snapshot(base: Path, cutoff: int) -> str | None:
    """Latest snapshot_time for GW1..cutoff, if it is after the cutoff deadline."""
    with (base / 'gameweek_summaries.csv').open(encoding='utf-8-sig') as stream:
        rows = [row for row in csv.DictReader(stream) if int(row['id']) <= cutoff]
    snapshots = [datetime.fromisoformat(row['snapshot_time'].replace('Z', '+00:00')) for row in rows if row.get('snapshot_time')]
    deadline = next((row.get('deadline_time') for row in rows if int(row['id']) == cutoff), '')
    if not snapshots or not deadline or max(snapshots) <= datetime.fromisoformat(deadline.replace('Z', '+00:00')):
        return None
    return max(snapshots).isoformat()


def validate_outputs(payloads: dict, cutoff: int):
    for name in ['formData', 'playerStatsData', 'defconData', 'xgDeltaData']:
        if payloads[name].get('gameweek') != cutoff:
            raise ValueError(f'Coverage mismatch: {name}')
    stats = payloads['playerStatsData']
    if not stats.get('season') or not stats.get('recent') or not stats.get('formRecent'):
        raise ValueError('Required player statistics are empty')
    if not payloads['teamRatingsData'].get('ratings'):
        raise ValueError('Team ratings are empty')
    if any(gw < 1 or gw > 38 for gw in payloads['fixtureData'].get('planningGws', [])):
        raise ValueError('Unsupported fixture gameweek')


def build_release(base: Path, season: str, cutoff: int, output: Path, revision: str, bundle: Path | None = None):
    if not re.fullmatch(r'\d{4}-\d{4}', season) or not 1 <= cutoff <= 38 or not revision:
        raise ValueError('Explicit season, cutoff and source revision are required')
    available = source_cutoff(base)
    if cutoff > available:
        raise ValueError(f'Requested GW{cutoff}; contiguous source coverage stops at GW{available}')
    output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    release_id = f'{season}-gw{cutoff}-{revision[:12]}-{stamp}'
    with tempfile.TemporaryDirectory(dir=output, prefix='staging-') as temporary:
        staged = Path(temporary)
        payloads = {}
        for name, script in EXPORTS.items():
            module = importlib.import_module(script)
            module.DATA_26_27 = base
            if hasattr(module, 'LAST_COMPLETE_GW'):
                module.LAST_COMPLETE_GW = cutoff
            if hasattr(module, 'CURRENT_GW_END'):
                module.CURRENT_GW_END = cutoff
            for attribute in ['OUTPUT_PATH', 'OUTPUT_PATH_NATIVE']:
                if hasattr(module, attribute):
                    setattr(module, attribute, staged / f'{name}.json')
            module.main()
            payloads[name] = json.loads((staged / f'{name}.json').read_text(encoding='utf-8'))
        validate_outputs(payloads, cutoff)
        codes = player_codes(base, cutoff)
        required = set().union(*(set(payloads['playerStatsData'][window]) for window in ['season', 'recent', 'formRecent']))
        if not required.issubset(codes):
            raise ValueError('A player is missing a stable source identity')
        source_files = [file for gw in range(1, cutoff + 1) for file in (base / 'By Gameweek' / f'GW{gw}').glob('*.csv')]
        source_time = datetime.fromtimestamp(max(file.stat().st_mtime for file in source_files), timezone.utc).isoformat()
        # Recorded source snapshot time is preferable to checkout modification time,
        # but only if it postdates the cutoff deadline (upstream has shipped a constant
        # pre-season placeholder for every gameweek).
        source_time = recorded_snapshot(base, cutoff) or source_time
        manifest = {'schemaVersion': 1, 'releaseId': release_id, 'season': season,
                    'generatedAt': datetime.now(timezone.utc).isoformat(), 'sourceUpdatedAt': source_time,
                    'completeThroughGw': cutoff, 'sourceRevision': revision, 'playerCodes': codes, 'files': {}}
        for name, payload in payloads.items():
            payload.update({'seasonKey': season, 'sourceThroughGw': cutoff, 'sourceUpdatedAt': source_time})
            raw = json.dumps(payload, ensure_ascii=True, allow_nan=False, separators=(',', ':')).encode('ascii')
            (staged / f'{name}.json').write_bytes(raw)
            manifest['files'][name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
        (staged / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        target = output / 'releases' / release_id
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise FileExistsError('Immutable release already exists')
        shutil.copytree(staged, target)
        if bundle:
            bundle.mkdir(parents=True, exist_ok=True)
            for name in EXPORTS:
                shutil.copy2(target / f'{name}.json', bundle / f'{name}.json')
            shutil.copy2(target / 'manifest.json', bundle / 'insightsManifest.json')
        temporary_manifest = output / 'manifest.next.json'
        shutil.copy2(target / 'manifest.json', temporary_manifest)
        os.replace(temporary_manifest, output / 'manifest.json')
    return release_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--season', required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--cutoff', type=int)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--bundle-output', type=Path)
    args = parser.parse_args()
    cutoff = args.cutoff if args.cutoff is not None else source_cutoff(args.source)
    print(build_release(args.source, args.season, cutoff, args.output, args.source_revision, args.bundle_output))


if __name__ == '__main__':
    main()
