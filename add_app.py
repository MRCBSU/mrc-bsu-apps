#!/usr/bin/env python3
"""Add a new app to the organisation's Shiny app index and republish it.

The index app reads its list of apps from a JSON file inside the app
directory (apps.json by default), shaped like:

    {
      "panel1": [{"name": ..., "url": ..., "description": ..., "added": ...}],
      "panel2": [...]
    }

Example:
    python add_app.py --panel panel1 \\
        --name "Sample Size Calculator" \\
        --url https://myorg.shinyapps.io/sample-size/ \\
        --description "Power and sample size for two-arm trials" \\
        --app-dir ./index-app --account myorg
"""

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

PANELS = ("panel1", "panel2")
USER_AGENT = "org-app-index-updater/1.0"


def parse_args():
    p = argparse.ArgumentParser(
        description="Add an app to the organisation's Shiny app index and republish it."
    )
    p.add_argument("--panel", required=True, choices=PANELS,
                   help="Which panel of the index app the new entry goes in.")
    p.add_argument("--name", required=True, help="Display name of the app.")
    p.add_argument("--url", required=True, help="Where the app lives.")
    p.add_argument("--description", required=True, help="Short description of the app.")
    p.add_argument("--app-dir", type=Path, default=Path("."),
                   help="Directory of the index Shiny app (default: current directory).")
    p.add_argument("--data-file", default="apps.json",
                   help="JSON file, relative to --app-dir, holding the app list (default: apps.json).")
    p.add_argument("--engine", choices=("r", "python"), default="r",
                   help="Is the index app written in R or Python? Picks the rsconnect tool (default: r).")
    p.add_argument("--account", help="shinyapps.io / Connect account (server) name to deploy to.")
    p.add_argument("--app-name", help="Deployed name (R) or title (Python) of the index app.")
    p.add_argument("--timeout", type=float, default=30,
                   help="Seconds to wait when checking the URL (default: 30; sleeping apps can be slow to wake).")
    p.add_argument("--skip-verify", action="store_true", help="Don't check that the URL responds.")
    p.add_argument("--skip-deploy", action="store_true", help="Update the list but don't republish.")
    p.add_argument("--dry-run", action="store_true",
                   help="Validate and verify only; change nothing and don't deploy.")
    return p.parse_args()


def check_url(url, timeout):
    """Return (ok, message). Tries HEAD first, falls back to GET if HEAD isn't allowed."""
    if not url.startswith(("http://", "https://")):
        return False, "URL must start with http:// or https://"

    status = None
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.status
        except urllib.error.HTTPError as e:
            status = e.code
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            return False, f"could not reach URL ({getattr(e, 'reason', e)})"

        if status == 200:
            return True, "200 OK"
        # Some servers reject HEAD; retry with GET before giving up.
        if method == "HEAD" and status in (403, 405, 501):
            continue
        break
    return False, f"expected 200 OK, got HTTP {status}"


def normalise(url):
    return url.strip().rstrip("/").lower()


def load_index(path):
    if not path.exists():
        return {panel: [] for panel in PANELS}
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    for panel in PANELS:
        data.setdefault(panel, [])
    return data


def save_index(path, data):
    """Write atomically so a crash never leaves a half-written file behind."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def find_duplicate(data, name, url, panel):
    for p in PANELS:
        for entry in data[p]:
            if normalise(entry.get("url", "")) == normalise(url):
                return f"that URL is already listed in {p} as '{entry.get('name')}'"
    for entry in data[panel]:
        if entry.get("name", "").strip().lower() == name.strip().lower():
            return f"an app named '{entry['name']}' is already in {panel}"
    return None


def r_string(s):
    # JSON string escaping is valid R string syntax.
    return json.dumps(s)


def build_deploy_command(args):
    app_dir = str(args.app_dir.resolve())
    if args.engine == "python":
        cmd = ["rsconnect", "deploy", "shiny", app_dir]
        if args.account:
            cmd += ["--name", args.account]
        if args.app_name:
            cmd += ["--title", args.app_name]
        return cmd

    params = [f"appDir = {r_string(app_dir)}", "forceUpdate = TRUE", "launch.browser = FALSE"]
    if args.app_name:
        params.append(f"appName = {r_string(args.app_name)}")
    if args.account:
        params.append(f"account = {r_string(args.account)}")
    return ["Rscript", "-e", f"rsconnect::deployApp({', '.join(params)})"]


def deploy(args):
    cmd = build_deploy_command(args)
    print("Republishing:", " ".join(shlex.quote(c) for c in cmd))
    try:
        return subprocess.run(cmd).returncode
    except FileNotFoundError:
        tool = "rsconnect (pip install rsconnect-python)" if args.engine == "python" else "Rscript"
        print(f"error: {tool} was not found on your PATH", file=sys.stderr)
        return 127


def main():
    args = parse_args()
    name, url, description = args.name.strip(), args.url.strip(), args.description.strip()
    if not name or not url or not description:
        sys.exit("error: name, url and description must not be empty")

    if not args.app_dir.is_dir():
        sys.exit(f"error: app directory not found: {args.app_dir}")
    data_path = args.app_dir / args.data_file

    try:
        data = load_index(data_path)
    except json.JSONDecodeError as e:
        sys.exit(f"error: {data_path} is not valid JSON ({e})")

    problem = find_duplicate(data, name, url, args.panel)
    if problem:
        sys.exit(f"error: {problem}")

    if args.skip_verify:
        print("Skipping URL check.")
    else:
        print(f"Checking {url} ...")
        ok, message = check_url(url, args.timeout)
        if not ok:
            sys.exit(f"error: {message}")
        print(f"  {message}")

    entry = {"name": name, "url": url, "description": description,
             "added": date.today().isoformat()}

    if args.dry_run:
        print(f"Dry run: would add to {args.panel} in {data_path}:")
        print(json.dumps(entry, indent=2, ensure_ascii=False))
        return 0

    data[args.panel].append(entry)
    save_index(data_path, data)
    print(f"Added '{name}' to {args.panel} in {data_path}.")

    if args.skip_deploy:
        print("Skipping deployment.")
        return 0

    code = deploy(args)
    if code != 0:
        print("error: deployment failed. The entry was saved, so fix the problem "
              "and republish without re-adding it.", file=sys.stderr)
        return code
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
