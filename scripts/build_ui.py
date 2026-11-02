"""Build the Next.js UI into web/out for single-process serving.

Runs `npm ci` and `npm run build` inside web/ (shell=True on Windows only, so
npm resolves to npm.cmd there). Prints the output path the runner serves.

Usage:  python scripts/build_ui.py
Exits non-zero when either npm command fails.
"""

import os
import subprocess
import sys
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parents[1] / "web"


def main() -> None:
    if not (WEB_DIR / "package.json").is_file():
        sys.exit(f"missing {WEB_DIR / 'package.json'}")
    for command in (["npm", "ci"], ["npm", "run", "build"]):
        print(f"[build_ui] {command[1]}...", flush=True)
        cmd = " ".join(command) if os.name == "nt" else command
        try:
            subprocess.run(cmd, cwd=WEB_DIR, shell=os.name == "nt", check=True)
        except subprocess.CalledProcessError as error:
            sys.exit(f"{command[1]} failed with exit code {error.returncode}")
    out = WEB_DIR / "out"
    if not (out / "index.html").is_file():
        sys.exit("build finished but web/out/index.html is missing")
    print(f"[build_ui] UI built: {out}")


if __name__ == "__main__":
    main()
