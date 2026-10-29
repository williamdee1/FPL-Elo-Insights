"""Manage the SquadAI Advisor free-access list (users who bypass the paywall).

The list is published by publish_site.yml (docs/ is copied to the Pages site) at
<site>/access/free_access.json. Only salted SHA-256 digests of lower-cased emails
are stored, so the public file does not reveal addresses. The salt must match
SquadAI-native/utils/paywall.ts.

    python scripts/free_access.py add someone@example.com
    python scripts/free_access.py remove someone@example.com
    python scripts/free_access.py check someone@example.com
    python scripts/free_access.py count

Commit and push docs/access/free_access.json to main; the app picks it up on the
next site publish (run the workflow manually to apply it at once).
"""
import argparse
import hashlib
import json
from pathlib import Path

SALT = "squadai-free-access:"
LIST_PATH = Path(__file__).resolve().parent.parent / "docs" / "access" / "free_access.json"


def email_hash(email: str) -> str:
    return hashlib.sha256((SALT + email.strip().lower()).encode("utf-8")).hexdigest()


def load(path: Path = LIST_PATH) -> list[str]:
    if not path.exists():
        return []
    return list(json.loads(path.read_text(encoding="utf-8")).get("sha256", []))


def save(hashes: list[str], path: Path = LIST_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"version": 1, "sha256": sorted(set(hashes))}
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8", newline="\n")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["add", "remove", "check", "count"])
    parser.add_argument("email", nargs="?")
    args = parser.parse_args(argv)
    hashes = load()
    if args.action == "count":
        print(f"{len(hashes)} free-access account(s)")
        return
    if not args.email or "@" not in args.email:
        parser.error("an email address is required")
    digest = email_hash(args.email)
    if args.action == "check":
        print("listed" if digest in hashes else "not listed")
    elif args.action == "add":
        save(hashes + [digest])
        print(f"added ({len(set(hashes + [digest]))} total)")
    else:
        save([h for h in hashes if h != digest])
        print("removed" if digest in hashes else "was not listed")


if __name__ == "__main__":
    main()
