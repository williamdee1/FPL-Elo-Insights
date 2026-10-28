"""CLI: python -m fplmodel run --out DIR [--evaluate]

run        fetch live FPL state, train on all history, write
           mlPredictionsData.json and matchForecastData.json to DIR.
--evaluate also rerun the rolling-origin backtest and write modelCard.json.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import data, infer


def _write(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def evaluate() -> dict:
    import polars as pl
    from . import backtest as bt, player_model as pm
    players, fixtures = data.load_all()
    season = max(players["season"].unique().to_list())
    last = int(players.filter(pl.col("season") == season)["gw"].max())
    prev = sorted(s for s in players["season"].unique().to_list() if s < season)[-1]
    targets = [(prev, g) for g in range(2, 39)] + [(season, g) for g in range(2, last + 1)]
    oof = pm.backtest(players, infer._match_oof(fixtures), targets)
    stack = pm.fit_stack(oof)
    oof = oof.with_columns(pm.apply_stack(oof, stack), pl.col("fpl_ep").fill_null(0))
    rows = []
    for (s, g), d in oof.group_by(["season", "gw"]):
        actual = d.select("code", "points", "minutes", "pos")
        for m in ("xp", "fpl_ep"):
            rows.append({"season": s, "model": m, **bt.score_gw(d.select("code", pl.col(m).alias("pred")), actual)})
    summary = pl.DataFrame(rows).group_by("season", "model").agg(
        pl.len().alias("gws"), *[pl.col(c).mean().round(4) for c in
                                 ("mae", "spearman", "top20_precision", "captain_pts", "top11_pts")])
    return {"modelVersion": infer.MODEL_VERSION, "stack": stack,
            "note": ("Horizon-1 rolling-origin backtest: every prediction uses only data available before its "
                     "deadline. Stack weights are refitted on these same rows, so xp is slightly optimistic; "
                     "fpl_ep is FPL's own pre-deadline expected points."),
            "backtest": summary.sort("season", "model").to_dicts()}


def main() -> None:
    ap = argparse.ArgumentParser(prog="fplmodel")
    ap.add_argument("command", choices=["run"])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--evaluate", action="store_true")
    args = ap.parse_args()
    players, fixtures = data.load_all()
    boot, api_fixtures = infer.fetch_live()
    result = infer.predict(players, fixtures, boot, api_fixtures)
    _write(args.out / "mlPredictionsData.json", result["predictions"])
    _write(args.out / "matchForecastData.json", result["matchForecast"])
    p = result["predictions"]
    print(f"{p['modelVersion']}: {len(p['players'])} players, GW{p['predGws'][0]}-{p['predGws'][-1]}, "
          f"data through GW{p['sourceThroughGw']}")
    if args.evaluate:
        card = evaluate()
        _write(args.out / "modelCard.json", card)
        print(json.dumps(card["backtest"], indent=1))


if __name__ == "__main__":
    main()
