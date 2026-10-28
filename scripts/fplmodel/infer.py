"""Production inference: live FPL state + trained models -> app prediction files.

The live FPL API is authoritative for the player list (ids, stable codes,
positions, teams, prices, status/news) and for unplayed fixtures (rescheduled
and double gameweeks). The engine dataset supplies history up to the last
completed gameweek. Output satisfies SquadAI-native/utils/predictionReadiness.ts:
every live player, stable codes, the horizon starting at the next deadline.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import polars as pl
import requests

from . import data, match_model as mm
from .backtest import _mask_results
from .features import fixture_features, player_features
from .player_model import PlayerModel

FPL_API = "https://fantasy.premierleague.com/api"
HORIZON = 6
SCHEMA_VERSION = 1
# Per-position (component, direct) weights from the 28 Oct 2026 rolling-origin
# backtest over 2025-26 GW2-38 and 2026-27 GW2-8 (refit with `--evaluate`).
PRODUCTION_STACK = {"GK": (0.96, 0.0), "DEF": (0.845, 0.09), "MID": (0.756, 0.244), "FWD": (0.563, 0.415)}
MODEL_VERSION = "xp-component-direct-v1+" + mm.MODEL_VERSION
APP_POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
ENGINE_POS = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}


def fetch_live() -> tuple[dict, list[dict]]:
    boot = requests.get(f"{FPL_API}/bootstrap-static/", timeout=30)
    boot.raise_for_status()
    fixtures = requests.get(f"{FPL_API}/fixtures/", timeout=30)
    fixtures.raise_for_status()
    return boot.json(), fixtures.json()


def season_label(boot: dict) -> tuple[str, str]:
    """('2026-2027', '2026-27') from the GW1 deadline year."""
    year = int(next(e for e in boot["events"] if e["id"] == 1)["deadline_time"][:4])
    return f"{year}-{year + 1}", f"{year}-{str(year + 1)[-2:]}"


def upcoming_gw(boot: dict, now: datetime | None = None) -> int | None:
    now = now or datetime.now(timezone.utc)
    future = [e for e in boot["events"]
              if datetime.fromisoformat(e["deadline_time"].replace("Z", "+00:00")) > now]
    return min((e["id"] for e in future), default=None)


def live_fixtures(boot: dict, api_fixtures: list[dict], season: str, history: pl.DataFrame) -> pl.DataFrame:
    """Engine fixtures with this season's unplayed rows replaced by the FPL API schedule."""
    code_of = {t["id"]: t["code"] for t in boot["teams"]}
    unplayed = [{"season": season, "gw": f["event"], "match_id": f"fpl-{f['id']}",
                 "kickoff": (f["kickoff_time"] or "").replace("Z", ""), "home": code_of[f["team_h"]],
                 "away": code_of[f["team_a"]], "finished": False}
                for f in api_fixtures if f["event"] is not None and not f["finished"] and not f["finished_provisional"]]
    kept = history.filter((pl.col("season") != season) | pl.col("finished"))
    if not unplayed:
        return kept
    return pl.concat([kept, pl.DataFrame(unplayed)], how="diagonal_relaxed")


def _match_oof(fixtures: pl.DataFrame) -> pl.DataFrame:
    """Pre-match forecasts for every played gameweek (fixture features for training rows)."""
    tm_all = mm.team_matches(fixtures)
    out = []
    keys = (mm._played(tm_all).select("season", "gw").unique().sort("season", "gw").iter_rows())
    for season, gw in keys:
        tm = mm.team_matches(_mask_results(fixtures, season, gw - 1))
        hist = tm.filter((pl.col("season") < season) | ((pl.col("season") == season) & (pl.col("gw") < gw)))
        if mm._played(hist).height < 100:
            continue
        rows = tm.filter((pl.col("season") == season) & (pl.col("gw") == gw))
        played = mm._played(hist)
        ratio = float(played["goals_for"].sum() / played["npxg_for"].sum())
        p = rows.select("season", "gw", "match_id", "team", "opp", "is_home").with_columns(
            pl.Series("pred_strength", mm.StrengthModel().fit(hist).predict(rows)), pl.lit(ratio).alias("goal_ratio"))
        out.append(mm.blend(p, mm.PRODUCTION_WEIGHTS).select(
            "season", "gw", "match_id", "team", "opp", "is_home", "lam_npxg", "lam_goals", "lam_goals_against", "p_cs"))
    return pl.concat(out)


def _availability(status: str | None, chance: float | None, h: int) -> tuple[str | None, float | None]:
    """Status/chance assumed for a gameweek h weeks after the next deadline (h=1 is next).

    FPL only publishes availability for the next round. Heuristic: doubts clear
    after one week; injuries/suspensions persist for two weeks, then become
    unknown (the model falls back on recent minutes); 'u' (left) and 'n'
    (ineligible) persist.
    """
    if h == 1 or status in (None, "a", "u", "n"):
        return status, chance
    if status == "d":
        return "a", None
    return (status, chance) if h <= 2 else (None, None)


def predict(players: pl.DataFrame, fixtures: pl.DataFrame, boot: dict, api_fixtures: list[dict],
            now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    season, season_short = season_label(boot)
    next_gw = upcoming_gw(boot, now)
    if next_gw is None:
        raise RuntimeError("No upcoming gameweek: season finished.")
    cutoff = int(players.filter(pl.col("season") == season)["gw"].max() or 0)
    if cutoff >= next_gw:
        raise RuntimeError(f"Data through GW{cutoff} but next deadline is GW{next_gw}.")
    gws = list(range(next_gw, min(38, next_gw + HORIZON - 1) + 1))

    fx = live_fixtures(boot, api_fixtures, season, fixtures)
    oof = _match_oof(fx)
    history_fx = fixture_features(oof)
    forecast = mm.forecast(fx, season, gws)
    # future fixture features: team reference lambdas roll on from the history
    future_fx = fixture_features(pl.concat([oof, forecast.select(oof.columns)]))
    history = player_features(players, history_fx)
    model = PlayerModel().fit(history)

    code_of_team = {t["id"]: t["code"] for t in boot["teams"]}
    short_of_team = {t["id"]: t["short_name"] for t in boot["teams"]}
    live = pl.DataFrame([{
        "season": season, "gw": next_gw, "element": e["id"], "code": e["code"], "name": e["web_name"],
        "pos": ENGINE_POS[e["element_type"]], "team": code_of_team[e["team"]], "price": e["now_cost"] / 10,
        "_status": e["status"], "_chance": e["chance_of_playing_next_round"],
        "_selected": float(e["selected_by_percent"]), "_tin": float(e["transfers_in_event"]),
        "_tout": float(e["transfers_out_event"]), "_app_pos": APP_POS[e["element_type"]],
        "_short": short_of_team[e["team"]], "_news": e.get("news") or "",
    } for e in boot["elements"]])
    frame = pl.concat([players.filter(pl.col("code").is_in(live["code"])),
                       live.select([c for c in players.columns if c in live.columns])], how="diagonal_relaxed")
    feats = player_features(frame, future_fx).filter((pl.col("season") == season) & (pl.col("gw") == next_gw))
    base = feats.drop("pre_status", "chance", "status_code", "pre_tin", "pre_tout", "pre_selected", "price") \
                .join(live.select("code", "price", "_status", "_chance", "_selected", "_tin", "_tout"), on="code")

    preds = []
    for h, gw in enumerate(gws, start=1):
        rows = base.drop([c for c in base.columns if c.startswith(("fx_", "ref_")) or c == "n_fix"]).with_columns(
            pl.lit(gw).alias("gw"))
        rows = rows.join(future_fx.filter((pl.col("season") == season) & (pl.col("gw") == gw)).drop("season", "gw"),
                         on="team", how="left").with_columns(pl.col("n_fix").fill_null(0))
        avail = [_availability(s, c, h) for s, c in zip(rows["_status"].to_list(), rows["_chance"].to_list())]
        rows = rows.with_columns(
            pl.Series("pre_status", [a[0] for a in avail], dtype=pl.Utf8),
            pl.Series("pre_chance", [a[1] for a in avail], dtype=pl.Float64),
            pl.col("_selected").alias("pre_selected"), pl.col("_tin").alias("pre_tin"), pl.col("_tout").alias("pre_tout"),
        ).with_columns(
            pl.col("pre_status").replace_strict({"a": 0, "d": 1, "i": 2, "s": 3, "u": 4, "n": 5}, default=None)
              .cast(pl.Float64).alias("status_code"),
            pl.when(pl.col("pre_chance").is_not_null()).then(pl.col("pre_chance"))
              .when(pl.col("pre_status") == "a").then(100.0).otherwise(None).alias("chance"),
        )
        comp = model.components(rows)
        wc = rows["pos"].replace_strict({p: w[0] for p, w in PRODUCTION_STACK.items()}, return_dtype=pl.Float64)
        wd = rows["pos"].replace_strict({p: w[1] for p, w in PRODUCTION_STACK.items()}, return_dtype=pl.Float64)
        preds.append(comp.with_columns(pl.lit(gw).alias("gw"),
                                       (pl.col("xp_component") * wc + pl.col("xp_direct") * wd).alias("xp")))
    allp = pl.concat(preds)
    return _export(live, allp, forecast, boot, season_short, cutoff, gws, now)


def _export(live, allp, forecast, boot, season_short, cutoff, gws, now) -> dict:
    by_code = {c: g for c, g in allp.group_by("code")}
    team_short = {t["code"]: t["short_name"] for t in boot["teams"]}
    players_out = []
    for r in live.iter_rows(named=True):
        g = by_code[(r["code"],)].sort("gw")
        gw_preds = {str(gw): round(float(x), 2) for gw, x in zip(g["gw"], g["xp"])}
        first = g.row(0, named=True)
        total = round(sum(gw_preds.values()), 2)
        players_out.append({
            "id": str(r["element"]), "code": int(r["code"]), "name": f"{r['name']} ({r['_short']})",
            "pos": r["_app_pos"], "subpos": r["_app_pos"], "price": float(r["price"]),
            "availGw30": round(float(first["p_app"]), 3),     # legacy key: P(appears) next gameweek
            "p60": round(float(first["p60"]), 3),
            "gwPreds": gw_preds, "totalPred": total, "avgPred": round(total / len(gws), 2),
            "breakdown": {k[2:]: round(float(first[k]), 2) for k in first if k.startswith("c_")},
            "status": r["_status"], "news": r["_news"],
        })
    players_out.sort(key=lambda p: -p["totalPred"])
    fixtures_out = [{
        "gw": int(f["gw"]), "team": team_short.get(f["team"], str(f["team"])),
        "opp": team_short.get(f["opp"], str(f["opp"])), "home": bool(f["is_home"]),
        "xg": round(float(f["lam_goals"]), 2), "xga": round(float(f["lam_goals_against"]), 2),
        "csPct": round(float(f["p_cs"]) * 100, 1),
    } for f in forecast.sort("gw", "team").iter_rows(named=True)]
    meta = {"schemaVersion": SCHEMA_VERSION, "season": season_short, "modelVersion": MODEL_VERSION,
            "generatedAt": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sourceThroughGw": cutoff, "trainedUpTo": f"GW{cutoff}", "predGws": gws}
    return {"predictions": {**meta, "players": players_out},
            "matchForecast": {**meta, "fixtures": fixtures_out}}
