"""Hygiene scan: secrets must never be committed, present or past.

Reads the secret values from .env (never printed, never logged), then scans:
  * every tracked file's current content (`git ls-files`)
  * every historical blob in `git log --all -p` output

A hit is ANY secret value found in scanned text; also flags tracked files
whose names look like they should never be tracked (.env, checkpoints, runs/,
reports/). Exit 1 on any hit, 0 when clean.

All output is redacted against .env values themselves: printed matches are
file/line locations only, never content.
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_TRACKED = (".env", ".browser_profile", "checkpoints.sqlite")
FORBIDDEN_TRACKED_PREFIXES = ("runs/", "reports/")


def redact(text: str, secrets: list[str]) -> str:
    out = text
    for secret in secrets:
        out = out.replace(secret, "***")
    return out


def collect_env_secrets() -> list[str]:
    path = ROOT / ".env"
    secrets: list[str] = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line and not line.startswith("export "):
                name, _, value = line.partition("=")
                value = value.strip().strip("'\"")
                name = name.strip().upper()
                # only *API_KEY / *_TOKEN style entries are credentials
                if value and (name.endswith("API_KEY") or name.endswith("TOKEN") or name.endswith("SECRET")):
                    secrets.append(value)
    return secrets


def scan_text(text: str, source: str, secrets: list[str]) -> int:
    hits = 0
    for index, line in enumerate(text.splitlines(), 1):
        for secret in secrets:
            if secret and secret in line:
                hits += 1
                # location only: never echo the matching line content
                print(f"HIT  {source}:{index} contains a secret value", flush=True)
                break
    return hits


def scan_tracked_files(secrets: list[str]) -> int:
    names = subprocess.run(["git", "ls-files"], cwd=ROOT, check=True, capture_output=True,
                           text=True, encoding="utf-8", errors="replace").stdout.splitlines()
    hits = 0
    for name in names:
        lowered = name.lower()
        if lowered == ".env" \
                or any(lowered.startswith(item) for item in (".browser_profile", "checkpoints.sqlite")) \
                or any(name.startswith(prefix) for prefix in FORBIDDEN_TRACKED_PREFIXES):
            hits += 1
            print(f"HIT  tracked file that must never be tracked: {name}", flush=True)
            continue
        path = ROOT / name
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        hits += scan_text(content, name, secrets)
    return hits


def scan_history(secrets: list[str]) -> int:
    # full patch history of every ref: created blobs, not working-tree files
    result = subprocess.run(["git", "log", "--all", "-p", "-U0"], cwd=ROOT, check=True,
                            capture_output=True, text=False)
    text = result.stdout.decode("utf-8", "replace")
    hits = 0
    for secret in secrets:
        found = False
        position = text.find(secret)
        while position != -1:
            if not found:
                print(f"HIT  a secret value appears in git history", flush=True)
                found = True
            hits += 1
            position = text.find(secret, position + 1)
    return hits


def main() -> None:
    parser = argparse.ArgumentParser(description="Secret hygiene scan (.env values are never printed)")
    parser.add_argument("--quiet", action="store_true", help="print only the verdict")
    args = parser.parse_args()
    secrets = collect_env_secrets()
    if not args.quiet:
        print(f"[secret_scan] loaded {len(secrets)} secret value(s) from .env (values never printed)")
    hits = scan_tracked_files(secrets)
    history_note = scan_history(secrets)
    total = hits + history_note
    print(f"[secret_scan] {'CLEAN' if total == 0 else str(total) + ' HIT(S)'} "
          f"(tracked files {hits}, git history {history_note})")
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
