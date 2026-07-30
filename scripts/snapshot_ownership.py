"""
Daily ownership snapshot for SquadAI Scout tab.

Fetches bootstrap-static from the FPL API and appends today's ownership
percentages to exports/ownershipHistory.json. Keeps the last 30 days.

Run by GitHub Actions daily — do not run manually in production.

Output: FPL-Elo-Insights/exports/ownershipHistory.json
Served at: https://raw.githubusercontent.com/williamdee1/FPL-Elo-Insights/main/exports/ownershipHistory.json
"""

import json
import urllib.request
from datetime import date, timedelta
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent.parent / "exports" / "ownershipHistory.json"
FPL_URL     = "https://fantasy.premierleague.com/api/bootstrap-static/"
KEEP_DAYS   = 30
TODAY       = date.today().isoformat()


def fetch_bootstrap():
    req = urllib.request.Request(FPL_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    print(f"Fetching FPL bootstrap-static for {TODAY} ...")
    data = fetch_bootstrap()

    snapshot: dict[str, float] = {}
    for p in data["elements"]:
        snapshot[str(p["id"])] = float(p["selected_by_percent"])

    print(f"  {len(snapshot)} players captured")

    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            history = json.load(f)
    else:
        history = {"snapshots": {}, "playerNames": {}}

    # Refresh player names (IDs renumber each season)
    for p in data["elements"]:
        history["playerNames"][str(p["id"])] = p["web_name"]

    # Add today's snapshot
    history["snapshots"][TODAY] = snapshot

    # Prune older than KEEP_DAYS
    cutoff = (date.today() - timedelta(days=KEEP_DAYS)).isoformat()
    history["snapshots"] = {
        d: v for d, v in history["snapshots"].items() if d >= cutoff
    }

    dates = sorted(history["snapshots"].keys())
    print(f"  History: {dates[0]} to {dates[-1]} ({len(dates)} snapshots)")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, separators=(",", ":"))

    print(f"Saved -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
