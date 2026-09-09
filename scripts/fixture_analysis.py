"""
Team Attack/Defence Fixture Analysis
Generates two colour-coded HTML tables:
  1. Attacker Appeal (MID/FWD): own attack strength × opponent defensive weakness
  2. Defender Appeal (GK/DEF): own defence strength × opponent attacking weakness
All scores H/A adjusted. Team ratings computed from the last 6 completed GWs with
recency weighting (most recent 2 GWs weighted ×2).

Current GW is auto-detected via utils. The only manual input needed each
week is DGW_EXTRA_FIXTURES below — add confirmed/likely second-leg reschedules here.
"""

import csv
import sys
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).parent.parent / "data" / "2025-2026"

# Manual config: extra fixtures for DGW weeks not yet in the data files.
DGW_EXTRA_FIXTURES = [
    (36, 31, 43),   # CRY(H) vs MCI(A) — likely DGW36
]

def load_team_map(last_completed_gw, base=None):
    base = base or BASE
    path = base / "By Gameweek" / f"GW{last_completed_gw}" / "teams.csv"
    code_to_short = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code_to_short[int(float(row["code"]))] = row["short_name"]
    return code_to_short

def short_to_code(code_to_short):
    return {v: k for k, v in code_to_short.items()}

def atk_raw(r, ha):
    return (
        r[f'xg_{ha}']  * 0.40 +
        r[f'xg_{ha}']  * 0.20 +
        r[f'bc_{ha}']  * 0.20 +
        r[f'sot_{ha}'] * 0.10 +
        r[f'tib_{ha}'] * 0.10
    )

def def_raw(r, ha):
    return (
        r[f'xga_{ha}']  * 0.40 +
        r[f'xga_{ha}']  * 0.20 +
        r[f'bcc_{ha}']  * 0.20 +
        r[f'sotc_{ha}'] * 0.10 +
        r[f'gc_{ha}']   * 0.10
    )

def load_team_ratings(gw_start, gw_end, recent_cutoff, base=None):
    stats = defaultdict(lambda: {k: 0.0 for k in [
        'xg_h', 'xg_a', 'xga_h', 'xga_a',
        'npxg_h', 'npxg_a', 'npxga_h', 'npxga_a',
        'bc_h', 'bc_a', 'bcc_h', 'bcc_a',
        'sot_h', 'sot_a', 'sotc_h', 'sotc_a',
        'gs_h', 'gs_a', 'gc_h', 'gc_a',
        'tib_h', 'tib_a',
        'n_h', 'n_a',
    ]})

    _base = base or BASE
    for gw in range(gw_start, gw_end + 1):
        weight = 2.0 if gw >= recent_cutoff else 1.0
        fixtures_path = _base / "By Gameweek" / f"GW{gw}" / "fixtures.csv"
        if not fixtures_path.exists():
            continue
        with open(fixtures_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("tournament") not in ("prem", "premier-league"):
                    continue
                if not row.get("finished", "").lower() == "true":
                    continue

                def val(k, default=0.0):
                    v = row.get(k, "")
                    try:
                        return float(v) if v not in ("", None) else default
                    except (ValueError, TypeError):
                        return default

                ht = int(float(row["home_team"]))
                at = int(float(row["away_team"]))
                h_xg   = val("home_expected_goals_xg")
                a_xg   = val("away_expected_goals_xg")
                h_npxg = val("home_non_penalty_xg")
                a_npxg = val("away_non_penalty_xg")
                h_bc   = val("home_big_chances")
                a_bc   = val("away_big_chances")
                h_sot  = val("home_shots_on_target")
                a_sot  = val("away_shots_on_target")
                h_gs   = val("home_score")
                a_gs   = val("away_score")
                h_tib  = val("home_touches_in_opposition_box")
                a_tib  = val("away_touches_in_opposition_box")

                h_xg_blend   = 0.70 * h_xg   + 0.30 * h_gs
                a_xg_blend   = 0.70 * a_xg   + 0.30 * a_gs
                h_npxg_blend = 0.70 * h_npxg + 0.30 * h_gs
                a_npxg_blend = 0.70 * a_npxg + 0.30 * a_gs

                s = stats[ht]
                s['xg_h']    += h_xg_blend  * weight
                s['npxg_h']  += h_npxg_blend * weight
                s['bc_h']    += h_bc  * weight
                s['sot_h']   += h_sot * weight
                s['tib_h']   += h_tib * weight
                s['gs_h']    += h_gs  * weight
                s['xga_h']   += a_xg_blend  * weight
                s['npxga_h'] += a_npxg_blend * weight
                s['bcc_h']   += a_bc  * weight
                s['sotc_h']  += a_sot * weight
                s['gc_h']    += a_gs  * weight
                s['n_h']     += weight

                s = stats[at]
                s['xg_a']    += a_xg_blend  * weight
                s['npxg_a']  += a_npxg_blend * weight
                s['bc_a']    += a_bc  * weight
                s['sot_a']   += a_sot * weight
                s['tib_a']   += a_tib * weight
                s['gs_a']    += a_gs  * weight
                s['xga_a']   += h_xg_blend  * weight
                s['npxga_a'] += h_npxg_blend * weight
                s['bcc_a']   += h_bc  * weight
                s['sotc_a']  += h_sot * weight
                s['gc_a']    += h_gs  * weight
                s['n_a']     += weight

    ratings = {}
    for team, s in stats.items():
        def pg(key, n_key):
            n = s[n_key]
            return s[key] / n if n > 0 else 0.0
        ratings[team] = {
            'xg_home':   pg('xg_h',   'n_h'),
            'xg_away':   pg('xg_a',   'n_a'),
            'xga_home':  pg('xga_h',  'n_h'),
            'xga_away':  pg('xga_a',  'n_a'),
            'gs_home':   pg('gs_h',   'n_h'),
            'gs_away':   pg('gs_a',   'n_a'),
            'gc_home':   pg('gc_h',   'n_h'),
            'gc_away':   pg('gc_a',   'n_a'),
            'bc_home':   pg('bc_h',   'n_h'),
            'bc_away':   pg('bc_a',   'n_a'),
            'bcc_home':  pg('bcc_h',  'n_h'),
            'bcc_away':  pg('bcc_a',  'n_a'),
            'sot_home':  pg('sot_h',  'n_h'),
            'sot_away':  pg('sot_a',  'n_a'),
            'sotc_home': pg('sotc_h', 'n_h'),
            'sotc_away': pg('sotc_a', 'n_a'),
            'tib_home':  pg('tib_h',  'n_h'),
            'tib_away':  pg('tib_a',  'n_a'),
            'n_home':    s['n_h'],
            'n_away':    s['n_a'],
        }

    atk_h_vals = [atk_raw(r, 'home') for r in ratings.values()]
    atk_a_vals = [atk_raw(r, 'away') for r in ratings.values()]
    def_h_vals = [def_raw(r, 'home') for r in ratings.values()]
    def_a_vals = [def_raw(r, 'away') for r in ratings.values()]

    def normalise(val, vals, lo=1.0, hi=10.0):
        mn, mx = min(vals), max(vals)
        if mx == mn:
            return 5.0
        return lo + (val - mn) / (mx - mn) * (hi - lo)

    for team, r in ratings.items():
        r['atk_home_score'] = normalise(atk_raw(r, 'home'), atk_h_vals)
        r['atk_away_score'] = normalise(atk_raw(r, 'away'), atk_a_vals)
        r['def_home_score'] = normalise(def_raw(r, 'home'), def_h_vals, lo=10.0, hi=1.0)
        r['def_away_score'] = normalise(def_raw(r, 'away'), def_a_vals, lo=10.0, hi=1.0)

    return ratings

def load_upcoming_fixtures(planning_gws, extra_fixtures=None, base=None):
    _base = base or BASE
    fixtures = []
    def read_pl_fixtures(gw):
        path = _base / "By Gameweek" / f"GW{gw}" / "fixtures.csv"
        rows = []
        if not path.exists():
            return rows
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("tournament") not in ("prem", "premier-league"):
                    continue
                try:
                    ht = int(float(row["home_team"]))
                    at = int(float(row["away_team"]))
                    rows.append((gw, ht, at))
                except (ValueError, TypeError):
                    continue
        return rows

    for gw in planning_gws:
        fixtures.extend(read_pl_fixtures(gw))

    if extra_fixtures:
        fixtures.extend(extra_fixtures)
    return fixtures

def score_fixture(home_team, away_team, ratings, perspective_team):
    is_home = (perspective_team == home_team)
    opponent = away_team if is_home else home_team
    opp_is_home = not is_home

    r_own = ratings.get(perspective_team, {})
    r_opp = ratings.get(opponent, {})

    own_ha = 'home' if is_home else 'away'
    opp_ha = 'home' if opp_is_home else 'away'

    own_atk = r_own.get(f'atk_{own_ha}_score', 5.0)
    own_def = r_own.get(f'def_{own_ha}_score', 5.0)
    opp_atk = r_opp.get(f'atk_{opp_ha}_score', 5.0)
    opp_def = r_opp.get(f'def_{opp_ha}_score', 5.0)

    opp_def_weakness = 11.0 - opp_def
    attacker_score = (own_atk * 0.5) + (opp_def_weakness * 0.5)

    opp_atk_weakness = 11.0 - opp_atk
    defender_score = (own_def * 0.5) + (opp_atk_weakness * 0.5)

    return {
        'attacker': round(attacker_score, 1),
        'defender': round(defender_score, 1),
        'own_atk':  round(own_atk, 1),
        'own_def':  round(own_def, 1),
        'opp_atk':  round(opp_atk, 1),
        'opp_def':  round(opp_def, 1),
        'ha':       'H' if is_home else 'A',
        'opponent': opponent,
    }

def build_team_schedule(fixtures, ratings, code_to_short):
    all_teams = set(code_to_short.keys())
    schedule = {t: defaultdict(list) for t in all_teams}
    for gw, ht, at in fixtures:
        for team in (ht, at):
            if team in all_teams:
                schedule[team][gw].append(score_fixture(ht, at, ratings, team))
    return schedule

def team_totals(schedule, team, planning_gws):
    total_atk = total_def = n_games = 0
    for gw in planning_gws:
        for s in schedule[team].get(gw, []):
            total_atk += s['attacker']
            total_def += s['defender']
            n_games += 1
    return total_atk, total_def, n_games

def score_colour(score, lo=1.0, hi=10.0):
    t = max(0.0, min(1.0, (score - lo) / (hi - lo)))
    if t < 0.5:
        r = int(231 + (243 - 231) * (t / 0.5))
        g = int(76  + (156 - 76)  * (t / 0.5))
        b = int(60  + (18  - 60)  * (t / 0.5))
    else:
        t2 = (t - 0.5) / 0.5
        r = int(243 + (39  - 243) * t2)
        g = int(156 + (174 - 156) * t2)
        b = int(18  + (96  - 18)  * t2)
    return f"#{r:02x}{g:02x}{b:02x}"

def text_colour(bg_hex):
    r = int(bg_hex[1:3], 16)
    g = int(bg_hex[3:5], 16)
    b = int(bg_hex[5:7], 16)
    lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#000" if lum > 0.5 else "#fff"

def render_cell(scores, metric, code_to_short):
    if not scores:
        return '<td class="blank">BGW</td>'
    parts = []
    for s in scores:
        val = s[metric]
        opp_short = code_to_short.get(s['opponent'], '???')
        bg = score_colour(val)
        tc = text_colour(bg)
        if metric == 'attacker':
            tip = f"Own Atk: {s['own_atk']} | Opp Def Weak: {round(11 - s['opp_def'], 1)}"
        else:
            tip = f"Own Def: {s['own_def']} | Opp Atk Weak: {round(11 - s['opp_atk'], 1)}"
        parts.append(
            f'<div class="fix-cell" style="background:{bg};color:{tc}" title="{tip}">'
            f'<span class="fix-score">{val:.1f}</span>'
            f'<span class="fix-opp">{opp_short} ({s["ha"]})</span>'
            f'<span class="fix-sub">{tip}</span>'
            f'</div>'
        )
    return f'<td class="{"dgw" if len(scores) > 1 else ""}">' + "".join(parts) + '</td>'

def build_html(schedule, ratings, code_to_short, planning_gws, current_gw, ratings_start, ratings_end, recent_cutoff):
    dgw_gws = {gw for gw, _, _ in DGW_EXTRA_FIXTURES}
    last_gw = planning_gws[-1]

    def totals(team):
        return team_totals(schedule, team, planning_gws)

    teams_sorted_atk = sorted(code_to_short.keys(), key=lambda t: totals(t)[0], reverse=True)
    teams_sorted_def = sorted(code_to_short.keys(), key=lambda t: totals(t)[1], reverse=True)

    gw_range_str = f"GW{current_gw}–{last_gw}"
    gw_headers = "".join(
        f'<th class="dgw-header">GW{gw}<br><small>DGW?</small></th>' if gw in dgw_gws else f'<th>GW{gw}</th>'
        for gw in planning_gws
    )

    def render_table(teams_order, metric, title, subtitle):
        rows = ""
        for rank, team in enumerate(teams_order, 1):
            short = code_to_short.get(team, str(team))
            total_atk, total_def, n_games = totals(team)
            total = total_atk if metric == 'attacker' else total_def
            avg = total / n_games if n_games else 0
            bg = score_colour(avg)
            tc = text_colour(bg)
            cells = "".join(render_cell(schedule[team].get(gw, []), metric, code_to_short) for gw in planning_gws)
            rows += (f'<tr><td class="rank">{rank}</td><td class="team-name"><strong>{short}</strong></td>'
                     f'{cells}<td class="total" style="background:{bg};color:{tc}">{total:.1f}<br><small>{n_games} gms</small></td></tr>')
        return f'<div class="table-section"><h2>{title}</h2><p class="subtitle">{subtitle}</p><table><thead><tr><th>#</th><th>Team</th>{gw_headers}<th>Total</th></tr></thead><tbody>{rows}</tbody></table></div>'

    attacker_table = render_table(teams_sorted_atk, 'attacker', f'Attacker Fixture Appeal (MID/FWD) — {gw_range_str}', 'Score = 50% own attack strength + 50% opponent defensive weakness. Higher = more goal/assist potential. H/A adjusted.')
    defender_table = render_table(teams_sorted_def, 'defender', f'Defender/GK Fixture Appeal — {gw_range_str}', 'Score = 50% own defensive strength + 50% opponent attacking weakness. Higher = cleaner sheet potential. H/A adjusted.')

    # Team Ratings Reference table — sorted by home attack score descending
    def rat_colour(val, lo=1.0, hi=10.0):
        return score_colour(val, lo, hi)

    teams_sorted_ratings = sorted(code_to_short.keys(), key=lambda t: ratings.get(t, {}).get('atk_home_score', 0), reverse=True)
    ref_rows = ""
    for team in teams_sorted_ratings:
        short = code_to_short.get(team, str(team))
        r = ratings.get(team, {})
        def rc(val, invert=False):
            lo, hi = (10.0, 1.0) if invert else (1.0, 10.0)
            bg = score_colour(val, lo, hi)
            tc = text_colour(bg)
            return f'<td style="background:{bg};color:{tc}">{val:.1f}</td>'
        ref_rows += (
            f'<tr><td class="team-name"><strong>{short}</strong></td>'
            f'<td>{r.get("xg_home", 0):.2f}</td><td>{r.get("xg_away", 0):.2f}</td>'
            f'<td>{r.get("xga_home", 0):.2f}</td><td>{r.get("xga_away", 0):.2f}</td>'
            f'<td>{r.get("gc_home", 0):.2f}</td><td>{r.get("gc_away", 0):.2f}</td>'
            f'<td>{r.get("bc_home", 0):.2f}</td><td>{r.get("bc_away", 0):.2f}</td>'
            f'<td>{r.get("bcc_home", 0):.2f}</td><td>{r.get("bcc_away", 0):.2f}</td>'
            f'{rc(r.get("atk_home_score", 5))}{rc(r.get("atk_away_score", 5))}'
            f'{rc(r.get("def_home_score", 5))}{rc(r.get("def_away_score", 5))}'
            f'</tr>'
        )

    dgw_note = f"GW{min(g for g,_,_ in DGW_EXTRA_FIXTURES)} = likely DGW (see DGW_EXTRA_FIXTURES)" if DGW_EXTRA_FIXTURES else ""
    meta_parts = [
        f"Team ratings: GW{ratings_start}–{ratings_end} Premier League",
        f"Recency weighted (GW{recent_cutoff}–{ratings_end} × 2)",
        "xG blend: 70% xG + 30% actual goals",
    ]
    if dgw_note:
        meta_parts.append(dgw_note)
    meta_parts.append("Score range: 1 (hardest) → 10 (easiest)")

    ratings_table = f"""<div class="table-section">
  <h2>Team Ratings Reference (GW{ratings_start}–{ratings_end}, recency weighted)</h2>
  <p class="subtitle">Sorted by home attack score. xG blend = 70% xG + 30% goals. Recency: GW{recent_cutoff}–{ratings_end} × 2; GW{ratings_start}–{recent_cutoff - 1} × 1.</p>
  <table>
    <thead><tr>
      <th>Team</th>
      <th>xG/g H</th><th>xG/g A</th>
      <th>xGA/g H</th><th>xGA/g A</th>
      <th>GC/g H</th><th>GC/g A</th>
      <th>BC/g H</th><th>BC/g A</th>
      <th>BCc/g H</th><th>BCc/g A</th>
      <th>Atk H</th><th>Atk A</th>
      <th>Def H</th><th>Def A</th>
    </tr></thead>
    <tbody>{ref_rows}</tbody>
  </table>
</div>"""

    legend = """<div class="legend">
  <strong>Score:</strong>
  <span class="leg-box" style="background:#e74c3c;color:#fff">&lt;4 Hard</span>
  <span class="leg-box" style="background:#f39c12;color:#000">4–6 Med</span>
  <span class="leg-box" style="background:#27ae60;color:#fff">&gt;7 Easy</span>
  &nbsp;&nbsp;DGW cells show two fixtures stacked
</div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>FPL Fixture Analysis {gw_range_str}</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; background: #1a1a2e; color: #eee; margin: 0; padding: 20px; }}
  h1 {{ color: #00ff87; text-align: center; margin-bottom: 4px; }}
  .meta {{ text-align: center; color: #aaa; margin-bottom: 8px; font-size: 13px; }}
  .legend {{ font-size: 13px; color: #ccc; margin-bottom: 30px; }}
  .leg-box {{ display: inline-block; padding: 2px 8px; border-radius: 4px; margin: 0 4px; font-weight: bold; }}
  .table-section {{ margin-bottom: 50px; }}
  h2 {{ color: #00ff87; border-bottom: 2px solid #00ff87; padding-bottom: 6px; }}
  .subtitle {{ color: #bbb; font-size: 13px; margin-bottom: 12px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  th {{ background: #37003c; color: #fff; padding: 8px 6px; text-align: center; position: sticky; top: 0; }}
  td {{ padding: 4px 6px; text-align: center; vertical-align: top; border: 1px solid #333; }}
  td.rank {{ color: #888; width: 28px; }}
  td.team-name {{ text-align: left; background: #2a2a40; padding-left: 10px; white-space: nowrap; }}
  td.blank {{ color: #555; background: #1a1a2e; font-style: italic; font-size: 11px; }}
  td.total {{ font-weight: bold; font-size: 14px; }}
  td.dgw {{ background: #1e1e38; }}
  th.dgw-header {{ background: #6a0080; color: #fff; }}
  .fix-cell {{ border-radius: 6px; padding: 4px 6px; margin: 2px 0; display: flex; flex-direction: column; align-items: center; cursor: default; }}
  .fix-score {{ font-size: 15px; font-weight: bold; line-height: 1.2; }}
  .fix-opp {{ font-size: 11px; line-height: 1.2; opacity: 0.9; }}
  .fix-sub {{ font-size: 10px; line-height: 1.2; opacity: 0.7; margin-top: 1px; }}
  tr:hover td {{ filter: brightness(1.15); }}
</style>
</head>
<body>
<h1>FPL Fixture Analysis: {gw_range_str}</h1>
<p class="meta">{" | ".join(meta_parts)}</p>
{legend}
{ratings_table}
{attacker_table}
{defender_table}
</body>
</html>"""

def run(current_gw=None):
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.utils import find_current_gameweek

    if current_gw is None:
        current_gw = find_current_gameweek()['current_gw']

    last_completed = current_gw - 1
    ratings_end = last_completed
    ratings_start = max(1, ratings_end - 5)
    recent_cutoff = ratings_end - 1
    season_end = 38
    planning_gws = list(range(current_gw, season_end + 1))

    output_dir = Path(__file__).parent.parent / "claude_data" / f"gw_{current_gw}"
    output_dir.mkdir(parents=True, exist_ok=True)

    code_to_short = load_team_map(last_completed)
    ratings = load_team_ratings(ratings_start, ratings_end, recent_cutoff)
    fixtures = load_upcoming_fixtures(planning_gws, DGW_EXTRA_FIXTURES)
    schedule = build_team_schedule(fixtures, ratings, code_to_short)

    html = build_html(schedule, ratings, code_to_short, planning_gws, current_gw, ratings_start, ratings_end, recent_cutoff)
    out_path = output_dir / "fixture_analysis.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Fixture analysis saved to: {out_path}")

if __name__ == "__main__":
    gw_arg = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run(gw_arg)