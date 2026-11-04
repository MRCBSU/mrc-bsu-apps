#!/usr/bin/env python3
"""Validate the app index (apps.json) and check that newly added apps are live.

Used by CI on every pull request, but you can run it locally too:

    python validate_index.py index-app/apps.json --base old-apps.json

Structure and duplicates are always checked. URLs are checked only for
entries that are new compared with --base, so one old app going offline
doesn't block everyone else's pull requests.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from add_app import PANELS, check_url, normalise

IN_CI = os.environ.get("GITHUB_ACTIONS") == "true"


def report(message):
    # GitHub shows ::error:: lines as annotations on the pull request.
    print(f"::error::{message}" if IN_CI else f"error: {message}", file=sys.stderr)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def structural_errors(data):
    if not isinstance(data, dict):
        return ["apps.json must contain a JSON object with panel1 and panel2"]

    errors = []
    unknown = set(data) - set(PANELS)
    if unknown:
        errors.append(f"unknown panel(s): {', '.join(sorted(unknown))}")

    seen_urls = {}
    for panel in PANELS:
        entries = data.get(panel, [])
        if not isinstance(entries, list):
            errors.append(f"{panel} must be a list")
            continue
        seen_names = set()
        for i, entry in enumerate(entries):
            where = f"{panel}[{i}]"
            if not isinstance(entry, dict):
                errors.append(f"{where} must be an object")
                continue
            name, url = entry.get("name"), entry.get("url")
            if not isinstance(name, str) or not name.strip():
                errors.append(f"{where}: 'name' is missing or empty")
            if not isinstance(url, str) or not url.strip():
                errors.append(f"{where}: 'url' is missing or empty")
            elif not url.startswith(("http://", "https://")):
                errors.append(f"{where}: url must start with http:// or https://")
            if not isinstance(entry.get("description", ""), str):
                errors.append(f"{where}: 'description' must be text")

            if isinstance(name, str):
                key = name.strip().lower()
                if key in seen_names:
                    errors.append(f"{where}: duplicate name '{name}' in {panel}")
                seen_names.add(key)
            if isinstance(url, str):
                key = normalise(url)
                if key in seen_urls:
                    errors.append(f"{where}: URL already listed at {seen_urls[key]}")
                seen_urls.setdefault(key, where)
    return errors


def all_urls(data):
    return {normalise(e["url"]) for p in PANELS for e in data.get(p, [])
            if isinstance(e, dict) and isinstance(e.get("url"), str)}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("index", type=Path, help="Path to apps.json")
    p.add_argument("--base", type=Path,
                   help="Previous apps.json; only entries not in it get URL checks. "
                        "Without it, every URL is checked.")
    p.add_argument("--no-url-check", action="store_true", help="Skip URL checks.")
    p.add_argument("--timeout", type=float, default=30)
    args = p.parse_args()

    try:
        data = load(args.index)
    except (OSError, json.JSONDecodeError) as e:
        report(f"could not read {args.index}: {e}")
        return 1

    errors = structural_errors(data)
    for message in errors:
        report(message)
    if errors:
        return 1
    print("Structure OK, no duplicates.")

    if args.no_url_check:
        return 0

    old_urls = set()
    if args.base and args.base.exists():
        try:
            old_urls = all_urls(load(args.base))
        except json.JSONDecodeError:
            pass  # unreadable base: treat everything as new

    new_entries = [(panel, e) for panel in PANELS for e in data.get(panel, [])
                   if normalise(e["url"]) not in old_urls]
    if not new_entries:
        print("No new apps to check.")
        return 0

    failed = 0
    for panel, entry in new_entries:
        ok, message = check_url(entry["url"], args.timeout)
        if ok:
            print(f"OK    {panel}: {entry['name']} ({entry['url']})")
        else:
            failed += 1
            report(f"{panel}: '{entry['name']}' at {entry['url']}: {message}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
